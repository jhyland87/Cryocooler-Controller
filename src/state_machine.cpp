/**
 * @file state_machine.cpp
 * @brief Cryocooler system state machine — implemented with jonblack/arduino-fsm.
 *
 * Architecture
 * ============
 * The arduino-fsm library manages state objects and event-driven transitions.
 * Each state has an on_enter callback that records the active state enum value
 * and entry timestamp.  All transition decisions that depend on sensor readings
 * (temperature, RMS voltage, stall flag) are evaluated inside update(), which
 * calls Fsm::trigger() with the appropriate event and then calls
 * Fsm::run_machine() to execute on_state callbacks.
 *
 * Timed transitions (Baseline→Operating, Shutdown→Idle, Initialize→Idle)
 * are also driven from update() using the injected nowMs argument rather than
 * add_timed_transition() so that native unit tests — which stub millis() at 0
 * and pass explicit timestamps — behave identically to the embedded target.
 *
 * Pure logic — no Serial.print, no hardware calls.
 * All inputs are injected via update(); all outputs are returned in the
 * Output struct so that callers (main.cpp) handle I/O.
 */
#include <Arduino.h>
#include "tick.h"
#include "state_machine.h"
#include "state_machine_history.h"
#include "config.h"
#include "conversions.h"
#include "indicator.h"
#include "amplifier.h"
#include "cold_head.h"
#include "cooling.h"
#include "esp_log.h"
#include "logger.h"
#include <Fsm.h>

namespace state_machine {

static constexpr char TAG[] = "state_machine";

static LogStream _Log = Log.createChildLogger("state_machine");
// ---------------------------------------------------------------------------
// Events — passed to Fsm::trigger()
// ---------------------------------------------------------------------------
enum : int {
    // Control events (fired by start() / stop() / off())
    EVT_START_COARSE    =  1,  ///< start() when tempC >= COARSE_FINE_THRESHOLD_C
    EVT_START_FINE      =  2,  ///< start() when below threshold but above setpoint band
    EVT_START_SETTLE    =  3,  ///< start() when already in setpoint band
    EVT_START_OVERSHOOT =  4,  ///< start() when below setpoint band
    EVT_STOP            =  5,  ///< stop() from a running state → Shutdown
    EVT_POWER_OFF       =  6,  ///< off() from any state → Off

    // Condition events (fired by update() each tick)
    EVT_BELOW_COARSE    =  7,  ///< CoarseCooldown → FineCooldown
    EVT_ABOVE_COARSE    =  8,  ///< FineCooldown → CoarseCooldown
    EVT_OVERSHOT        =  9,  ///< FineCooldown → Overshoot
    EVT_IN_BAND         = 10,  ///< Fine/Overshoot → Settle
    EVT_SETTLE_DONE     = 11,  ///< Settle → Baseline   (settle timer expired)
    EVT_INIT_DONE       = 12,  ///< Initialize → Idle   (amber-flash timer expired)
    EVT_BASELINE_DONE   = 13,  ///< Baseline → Operating (baseline timer expired)
    EVT_SHUTDOWN_DONE   = 14,  ///< Shutdown → Idle      (shutdown timer expired)

    // Fault events
    EVT_FAULT_RMS         = 15,  ///< RMS overvoltage from any non-Fault state
    EVT_FAULT_STALL       = 16,  ///< Temperature stall in Coarse or Fine cooldown
    EVT_FAULT_BACKOFFS    = 17,  ///< Too many back-EMF backoff events
    EVT_FAULT_LOW_VOLTAGE   = 21,  ///< DC supply voltage below MIN_SYSTEM_VOLTAGE_VDC
    EVT_FAULT_OSCILLATION   = 25,  ///< FSM bouncing between the same two states repeatedly

    // Fault-clear event
    EVT_FAULT_CLEARED   = 22,  ///< clearFault() → Idle (resets fault reason & backoffs)

    // Re-initialize event
    EVT_REINITIALIZE    = 23,  ///< reinit() → Initialize from Off or Idle

    // Generic fault event — used by the bitmask fault detection path.
    // All fault conditions (single or composite) fire this one event so the
    // combined faultReason bitmask is captured before the FSM transitions.
    EVT_FAULT           = 26,  ///< any combination of fault bits → Fault from any non-Fault state

    // Delay state events
    EVT_ENTER_DELAY     = 18,  ///< Enter Delay state (fired by startDelay())
    EVT_DELAY_TO_IDLE   = 19,  ///< Delay → Idle  (fired when delay timer expires)
    EVT_DELAY_TO_COARSE = 20,  ///< Delay → CoarseCooldown (fired when delay timer expires)
};

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------
static State        currentState        = State::Off;
static uint32_t     currentStateEntryMs = 0;
static bool         running             = false;
static bool         deferredStop_       = false;   ///< set by stop() while in Fault
static FaultReason  faultReason         = FaultReason::None;
static uint32_t     onStateMs           = 0;
static uint32_t     offStateMs          = 0;

// Settle timer — managed manually in update() so nowMs (not millis()) drives it
static uint32_t     settleStartMs       = 0;
static bool         settleTimerActive   = false;

// Back-EMF backoff tracking
static uint16_t     backoffCount        = 0;
static uint16_t     backoffDacOffset    = 0;

// Delay state configuration — set by startDelay() before EVT_ENTER_DELAY fires.
static uint32_t     delayMs           = 0;  ///< duration to hold in Delay state
static int          delayNextEvent    = EVT_DELAY_TO_IDLE; ///< event fired when timer expires

// Injected timestamp — set before every trigger() call so on_enter callbacks
// can capture the correct entry time without calling millis() directly.
// Named sNowMs (not nowMs) to prevent shadowing by same-named function parameters.
static uint32_t     sNowMs            = 0;

// Optional callback invoked when the FSM enters the Initialize state.
// Registered by main.cpp via setOnInitializeCallback() to re-run control
// module inits on every reinit().
static void (*onInitializeCb)() = nullptr;

// Set by checkRunningModules() inside any running-state on_enter callback;
// consumed at the top of the next update() tick — same deferred pattern as
// the oscillation fault flag in state_machine_history.  The check lives in
// the states (not in start() or in commands) so it fires regardless of how
// the state transition was triggered.
static bool dependencyFaultPending = false;

// ---------------------------------------------------------------------------
// Module dependency checker — Arduino only (native builds stub this away)
// ---------------------------------------------------------------------------
//
// Called from every running-state on_enter callback.  If any required module
// is not initialised, sets dependencyFaultPending so the next update() tick
// fires EVT_FAULT with FaultReason::ModuleNotReady.
//
// Keeping the check here (rather than in commands or in start()) means it
// fires regardless of what triggered the state transition.
// ---------------------------------------------------------------------------

#ifdef ARDUINO
#include "module.h"
static void checkRunningModules() {
    const char* missing = nullptr;
    if (cooling::Module::getInitStatus()   != module::MODULE_INIT_SUCCESS) missing = "cooling";
    else if (amplifier::Module::getInitStatus() != module::MODULE_INIT_SUCCESS) missing = "amplifier";
    else if (cold_head::Module::getInitStatus() != module::MODULE_INIT_SUCCESS) missing = "cold_head";

    if (missing) {
        ESP_LOGE(TAG, "Module '%s' not ready — deferring fault", missing);
        _Log.printf("Module '%s' not ready — fault will fire next tick\n", missing);
        dependencyFaultPending = true;
    }
}
#endif  // ARDUINO

// ---------------------------------------------------------------------------
// Forward declarations for FSM state callbacks
// ---------------------------------------------------------------------------
static void onEnterOff();
static void onEnterInitialize();
static void onEnterIdle();
static void onEnterCoarseCooldown();
static void onEnterFineCooldown();
static void onEnterOvershoot();
static void onEnterSettle();
static void onEnterBaseline();
static void onEnterOperating();
static void onExitOperating();
static void onEnterShutdown();
static void onEnterDelay();
static void onEnterFault();
static void onExitFault();

// ---------------------------------------------------------------------------
// Library ::State objects
// Qualified as ::State to avoid shadowing the state_machine::State enum.
// ---------------------------------------------------------------------------
static ::State fsmStateOff       (onEnterOff,             nullptr, nullptr);
static ::State fsmStateInit      (onEnterInitialize,      nullptr, nullptr);
static ::State fsmStateIdle      (onEnterIdle,            nullptr, nullptr);
static ::State fsmStateCoarse    (onEnterCoarseCooldown,  nullptr, nullptr);
static ::State fsmStateFine      (onEnterFineCooldown,    nullptr, nullptr);
static ::State fsmStateOvershoot (onEnterOvershoot,       nullptr, nullptr);
static ::State fsmStateSettle    (onEnterSettle,          nullptr, nullptr);
static ::State fsmStateBaseline  (onEnterBaseline,        nullptr, nullptr);
static ::State fsmStateOperating (onEnterOperating,       nullptr, onExitOperating);
static ::State fsmStateShutdown  (onEnterShutdown,        nullptr, nullptr);
static ::State fsmStateDelay     (onEnterDelay,           nullptr, nullptr);
static ::State fsmStateFault     (onEnterFault,           nullptr, onExitFault);

// Heap-allocated so it can be fully reset between test cases via init().
static Fsm* fsm = nullptr;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** True when the cold stage temperature is within the setpoint tolerance band. */
static bool inBand(float tempC) {
    return (tempC >= (SETPOINT_C - SETPOINT_TOLERANCE_C)) &&
           (tempC <= (SETPOINT_C + SETPOINT_TOLERANCE_C));
}

/** True when the cold stage has clearly overshot (gone below) the setpoint. */
static bool overshot(float tempC) {
    return tempC < (SETPOINT_C - SETPOINT_TOLERANCE_C);
}

/**
 * Compute the target DAC value for cooldown states.
 * Proportional to how far the temperature has dropped from AMBIENT_START_C
 * toward SETPOINT_C.  Returns a fraction (0.0 – 1.0).
 */

/**
 * Return the human-readable status string for a state.
 * State::Fault is resolved dynamically from faultReason before the
 * macro-generated switch, which carries nullptr for the Fault row.
 * All other states are generated from STATE_MACHINE_STATES.
 */
static const char* statusTextForState(State s) {
    if (s == State::Fault) {
        const uint8_t mask = static_cast<uint8_t>(faultReason);
        if (mask == 0u) return "Fault: Unknown reason";
        // More than one bit set — composite fault; direct operator to the log.
        if ((mask & (mask - 1u)) != 0u) {
            return "Fault: Multiple conditions active — use 'fault history' for details";
        }
        // Exactly one bit set — return the specific description.
        switch (faultReason) {
            case FaultReason::RmsOvervoltage:   return "Fault: RMS voltage exceeded safe limit";
            case FaultReason::TemperatureStall: return "Fault: Temperature stalled during cooldown";
            case FaultReason::TooManyBackoffs:  return "Fault: Too many back-EMF stroke events; output backed off";
            case FaultReason::LowSystemVoltage: return "Fault: DC system voltage below minimum threshold";
            case FaultReason::StateOscillation: return "Fault: FSM oscillating between states — manual clearFault() required";
            case FaultReason::SensorFault:      return "Fault: Temperature sensor hardware fault or reading out of range";
            case FaultReason::RmsOvercurrent:   return "Fault: RMS output current exceeded safe limit";
            case FaultReason::ModuleNotReady:   return "Fault: A required control module was not initialised — reinit and try again";
            default:                            return "Fault: Unknown reason";
        }
    }
    switch (s) {
#define X(name, value, sname, status) case State::name: return status;
        STATE_MACHINE_STATES(X)
#undef X
    }
    return "Unknown state";
}

/**
 * Build the Output struct for a given state.
 * Relay and indicator assignments follow the design spec exactly.
 */
static Output buildOutput(State s, float fraction) {
    using Mode = indicator::Mode;

    // Convert fraction to DAC counts for the Output struct.
    uint16_t dacTarget = static_cast<uint16_t>(
        fraction * static_cast<float>(AMPLIFIER_RESOLUTION));

    // Apply accumulated backoff reduction (floor at 0).
    if (backoffDacOffset > 0 && dacTarget > 0) {
        dacTarget = (backoffDacOffset >= dacTarget)
                        ? static_cast<uint16_t>(0)
                        : static_cast<uint16_t>(dacTarget - backoffDacOffset);
    }

    Output o{};
    o.state        = s;
    o.dacTarget    = dacTarget;
    // o.compressorRelay = false;
    // o.amplifierRelay = false;
    o.statusText   = statusTextForState(s);
    o.backoffCount = backoffCount;

    switch (s) {
        case State::Off:
            //o.amplifierRelay  = LOW;
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::Off;
            break;

        case State::Initialize:
            //o.amplifierRelay  = LOW;
            o.faultIndMode = Mode::SolidAmber;
            o.readyIndMode = Mode::SolidAmber;
            break;

        case State::Idle:
            //o.amplifierRelay  = LOW;
            o.faultIndMode = Mode::SolidRed;
            o.readyIndMode = Mode::Off;
            break;

        case State::CoarseCooldown:
            //o.amplifierRelay  = HIGH;
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::Off;
            break;

        case State::FineCooldown:
            //o.amplifierRelay  = HIGH;
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::FlashSlowGreen;
            break;

        case State::Overshoot:
            //o.amplifierRelay  = HIGH;
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::FlashFastGreen;
            break;

        case State::Settle:
            //o.amplifierRelay  = HIGH;   // Normal
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::FlashFastGreen;
            break;

        case State::Baseline:
            //o.amplifierRelay  = HIGH;   // Normal
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::SolidGreen;
            break;

        case State::Operating:
            //o.amplifierRelay  = HIGH;   // Normal
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::SolidGreen;
            break;

        case State::Shutdown:
            //o.amplifierRelay  = LOW;
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::Off;
            break;

        case State::Delay:
            //o.amplifierRelay  = HIGH;
            o.faultIndMode = Mode::SolidAmber;
            o.readyIndMode = Mode::SolidAmber;
            break;

        case State::Fault:
            //o.amplifierRelay  = LOW;
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::Off;
            break;
    }
    return o;
}

// ---------------------------------------------------------------------------
// on_enter callbacks — invoked synchronously by Fsm::make_transition()
// ---------------------------------------------------------------------------

/**
 * Common housekeeping executed on every state entry.
 * Updates currentState and records the entry timestamp from sNowMs (which must
 * be set by the caller before trigger() is invoked).
 */
static void setStateEntry(State s) {
    _Log.printf("-> %s\n", stateName(s));
    ESP_LOGD(TAG, "Entering state %s", stateName(s));
    currentState        = s;
    currentStateEntryMs = sNowMs;
    // Clear settle timer for every state except Settle itself.
    if (s != State::Settle) {
        settleTimerActive = false;
        settleStartMs     = 0;
    }
    // Preserve faultReason when entering Fault; clear it for all other states.
    if (s != State::Fault) {
        faultReason = FaultReason::None;
    }
    histPushHistory(s, sNowMs);
}

static void onEnterOff(){
    setStateEntry(State::Off);
    cold_head::setTargetTempC(NAN);
    // Relay is cut first; DAC is zeroed immediately — no ramp needed here
    // because the load is already disconnected.  Shutdown handles the
    // graceful ramp for the normal stop path (running → Shutdown → Idle).
    amplifier::setRelayState(false);
    amplifier::hardStop();
}
static void onEnterInitialize() {
    setStateEntry(State::Initialize);
    if (onInitializeCb) {
        // onInitializeCb() calls initControlModules() → cooling::init(),
        // which configures the EMC2303 and enables software-LUT fan/pump control.
        onInitializeCb();
    }
}
static void onEnterIdle() {
    setStateEntry(State::Idle);
    cold_head::setTargetTempC(NAN);
    amplifier::clearVoutOverride();
    // Relay off, then immediately zero the DAC.  rampTo() is a
    // single-step call — it only decrements by one rampRate on each
    // invocation, so calling it once here would leave the DAC stranded at
    // a high value.  The Shutdown state is the right place for a gradual
    // ramp; by the time the normal stop path reaches Idle the DAC is already
    // 0.  For paths that bypass Shutdown (clearFault → Idle, reinit → Idle)
    // hardStop() guarantees the DAC is zeroed immediately.
    amplifier::setRelayState(false);
    amplifier::hardStop();
}
static void onEnterCoarseCooldown() {
    setStateEntry(State::CoarseCooldown);
    cold_head::setTargetTempC(SETPOINT_C);
    amplifier::setRelayState(true);
    amplifier::initCoarseCooldown();
#ifdef ARDUINO
    checkRunningModules();
#endif
}
static void onEnterFineCooldown() {
    setStateEntry(State::FineCooldown);
    amplifier::setRelayState(true);
    amplifier::initFineCooldown();
#ifdef ARDUINO
    checkRunningModules();
#endif
}
static void onEnterOvershoot() {
    setStateEntry(State::Overshoot);
    amplifier::setRelayState(true);
#ifdef ARDUINO
    checkRunningModules();
#endif
}
static void onEnterSettle() {
    setStateEntry(State::Settle);
    amplifier::setRelayState(true);
#ifdef ARDUINO
    checkRunningModules();
#endif
}
static void onEnterBaseline() {
    setStateEntry(State::Baseline);
    amplifier::setRelayState(true);
#ifdef ARDUINO
    checkRunningModules();
#endif
}
static void onEnterOperating() {
    setStateEntry(State::Operating);
    amplifier::setRelayState(true);
    cold_head::startTemperatureTracking();
#ifdef ARDUINO
    checkRunningModules();
#endif
}
static void onExitOperating()       {
    // Relay control is delegated to the destination state's on_enter handler.
    // Shutdown keeps it ON for the ramp-down; Fault/Off/Idle turn it OFF.
    cold_head::stopTemperatureTracking();
}
static void onEnterShutdown()       {
    setStateEntry(State::Shutdown);
    amplifier::clearVoutOverride();
    amplifier::rampTowardShutdown();
    // Relay stays ON so the load sees the ramp-down.  The relay is turned
    // off only after the DAC reaches 0, when we transition to Idle.
    amplifier::setRelayState(true);
}

static void onEnterDelay() {
    setStateEntry(State::Delay);
    _Log.printf("Delay for %lu ms\n", static_cast<unsigned long>(delayMs));
}

static void onEnterFault() {
    setStateEntry(State::Fault);   // faultReason is preserved (set before trigger())
    deferredStop_ = false;         // reset — operator hasn't deferred stop yet
    cold_head::setTargetTempC(NAN);
    amplifier::clearVoutOverride();
    // Relay off first, then immediately zero the DAC.  The load is now
    // disconnected, so there is no reason to leave the DAC at the pre-fault
    // level.  This also ensures that if clearFault() → start() resumes into
    // a running state, the ramp begins cleanly from 0.
    amplifier::setRelayState(false);
    amplifier::hardStop();
    running = false;
    if (offStateMs == 0) offStateMs = sNowMs;

    // Push a new fault record into the history ring buffer.
    histPushFaultRecord(faultReason, sNowMs);
}

/**
 * Called by the FSM whenever the machine leaves State::Fault.
 * Resets all fault-related and backoff state so the system starts clean
 * on the next start() call.
 *
 * The pendingCause tracked by state_machine_history is still valid here
 * (consumed by histPushHistory() when entering the next state), so
 * histCloseFaultRecord() uses it to record how the fault was cleared.
 */
static void onExitFault() {
    _Log.printf("Fault cleared (was: %d); resetting backoff state\n",
                  static_cast<int>(faultReason));
    ESP_LOGD(TAG, "Fault cleared (reason %d); backoffCount=%u dacOffset=%u reset",
             static_cast<int>(faultReason), backoffCount, backoffDacOffset);

    // Complete the most recent fault record with clear timestamp and cause.
    histCloseFaultRecord(sNowMs);

    faultReason            = FaultReason::None;
    backoffCount           = 0;
    backoffDacOffset       = 0;
    histTakeOscillationFaultPending();  // drain deferred flag; restart oscillation window
    dependencyFaultPending = false;     // clear any pending dependency fault from a previous run attempt
}

// ---------------------------------------------------------------------------
// FSM construction — called once per init()
// ---------------------------------------------------------------------------

static void buildFsm() {
    // ── Start events from Off and Idle ────────────────────────────────────
    // start() selects the correct resume state based on the current temperature.
    ::State* startableStates[] = { &fsmStateOff, &fsmStateIdle };
    for (auto* from : startableStates) {
        fsm->add_transition(from, &fsmStateCoarse,    EVT_START_COARSE,    nullptr);
        fsm->add_transition(from, &fsmStateFine,      EVT_START_FINE,      nullptr);
        fsm->add_transition(from, &fsmStateSettle,    EVT_START_SETTLE,    nullptr);
        fsm->add_transition(from, &fsmStateOvershoot, EVT_START_OVERSHOOT, nullptr);
    }

    // ── Re-initialize: Off, Idle, Initialize, or Fault → Initialize ───────
    // Triggered by reinit().  onEnterInitialize fires the registered callback
    // so control modules are re-initialised on every transition to Initialize.
    // Fault is included so the operator can reinit directly after clearing a
    // fault without a separate clearFault() + off() sequence.
    // onExitFault() fires automatically on the Fault → Initialize transition,
    // resetting faultReason and backoff state before Initialize is entered.
    // Initialize is included so that a failed startup (stuck in Initialize)
    // can be retried with a single reinit command rather than off + reinit.
    fsm->add_transition(&fsmStateOff,   &fsmStateInit, EVT_REINITIALIZE, nullptr);
    fsm->add_transition(&fsmStateIdle,  &fsmStateInit, EVT_REINITIALIZE, nullptr);
    fsm->add_transition(&fsmStateInit,  &fsmStateInit, EVT_REINITIALIZE, nullptr);
    fsm->add_transition(&fsmStateFault, &fsmStateInit, EVT_REINITIALIZE, nullptr);

    // ── Initialize → Idle ─────────────────────────────────────────────────
    // Timer driven in update() using nowMs (not add_timed_transition).
    fsm->add_transition(&fsmStateInit, &fsmStateIdle, EVT_INIT_DONE, nullptr);

    // ── Cooldown transitions ───────────────────────────────────────────────
    fsm->add_transition(&fsmStateCoarse,    &fsmStateFine,      EVT_BELOW_COARSE, nullptr);
    fsm->add_transition(&fsmStateFine,      &fsmStateCoarse,    EVT_ABOVE_COARSE, nullptr);
    fsm->add_transition(&fsmStateFine,      &fsmStateOvershoot, EVT_OVERSHOT,     nullptr);
    fsm->add_transition(&fsmStateFine,      &fsmStateSettle,    EVT_IN_BAND,      nullptr);
    fsm->add_transition(&fsmStateOvershoot, &fsmStateSettle,    EVT_IN_BAND,      nullptr);

    // ── Settle → Baseline (timer-driven in update()) ──────────────────────
    fsm->add_transition(&fsmStateSettle,   &fsmStateBaseline,  EVT_SETTLE_DONE,  nullptr);

    // ── Baseline → Operating (timer-driven in update()) ───────────────────
    fsm->add_transition(&fsmStateBaseline, &fsmStateOperating, EVT_BASELINE_DONE, nullptr);

    // ── Shutdown → Idle (timer-driven in update()) ────────────────────────
    fsm->add_transition(&fsmStateShutdown, &fsmStateIdle,      EVT_SHUTDOWN_DONE, nullptr);

    // ── Stop: all running states → Shutdown ───────────────────────────────
    // Delay is included so stop() can interrupt a pending wait.
    ::State* stoppableStates[] = {
        &fsmStateCoarse, &fsmStateFine, &fsmStateOvershoot,
        &fsmStateSettle, &fsmStateBaseline, &fsmStateOperating, &fsmStateDelay
    };
    for (auto* from : stoppableStates) {
        fsm->add_transition(from, &fsmStateShutdown, EVT_STOP, nullptr);
    }

    // ── Fault: generic EVT_FAULT fires from every non-Fault state ─────────
    // All fault conditions — whether single or composite — now accumulate into
    // a bitmask and fire this single event, so the full set of concurrent
    // reasons is captured in faultReason before the transition occurs.
    ::State* allNonFaultStates[] = {
        &fsmStateOff, &fsmStateInit, &fsmStateIdle,
        &fsmStateCoarse, &fsmStateFine, &fsmStateOvershoot,
        &fsmStateSettle, &fsmStateBaseline, &fsmStateOperating, &fsmStateShutdown, &fsmStateDelay
    };
    for (auto* from : allNonFaultStates) {
        fsm->add_transition(from, &fsmStateFault, EVT_FAULT, nullptr);
    }

    // Legacy per-type fault events retained for backward compatibility with
    // any external tooling that may reference them; they are no longer fired
    // by update() but their FSM transitions remain registered.
    for (auto* from : allNonFaultStates) {
        fsm->add_transition(from, &fsmStateFault, EVT_FAULT_RMS,         nullptr);
        fsm->add_transition(from, &fsmStateFault, EVT_FAULT_LOW_VOLTAGE,  nullptr);
        fsm->add_transition(from, &fsmStateFault, EVT_FAULT_OSCILLATION,  nullptr);
    }
    fsm->add_transition(&fsmStateCoarse, &fsmStateFault, EVT_FAULT_STALL,    nullptr);
    fsm->add_transition(&fsmStateFine,   &fsmStateFault, EVT_FAULT_STALL,    nullptr);
    for (auto* from : stoppableStates) {
        fsm->add_transition(from, &fsmStateFault, EVT_FAULT_BACKOFFS, nullptr);
    }

    // ── Fault clear: Fault → Idle (fired by clearFault()) ─────────────────
    // onExitFault() resets faultReason, backoff counter, and DAC offset.
    fsm->add_transition(&fsmStateFault, &fsmStateIdle, EVT_FAULT_CLEARED, nullptr);

    // ── Power-off: any state → Off ─────────────────────────────────────────
    ::State* powerOffableStates[] = {
        &fsmStateInit, &fsmStateIdle,
        &fsmStateCoarse, &fsmStateFine, &fsmStateOvershoot,
        &fsmStateSettle, &fsmStateBaseline, &fsmStateOperating,
        &fsmStateShutdown, &fsmStateDelay, &fsmStateFault
    };
    for (auto* from : powerOffableStates) {
        fsm->add_transition(from, &fsmStateOff, EVT_POWER_OFF, nullptr);
    }

    // ── Delay entry: from all non-Fault, non-Delay states ─────────────────
    // Called by startDelay() via EVT_ENTER_DELAY.
    ::State* delayableStates[] = {
        &fsmStateOff, &fsmStateInit, &fsmStateIdle,
        &fsmStateCoarse, &fsmStateFine, &fsmStateOvershoot,
        &fsmStateSettle, &fsmStateBaseline, &fsmStateOperating, &fsmStateShutdown
    };
    for (auto* from : delayableStates) {
        fsm->add_transition(from, &fsmStateDelay, EVT_ENTER_DELAY, nullptr);
    }

    // ── Delay exit: timer-driven in update() ──────────────────────────────
    fsm->add_transition(&fsmStateDelay, &fsmStateIdle,   EVT_DELAY_TO_IDLE,   nullptr);
    fsm->add_transition(&fsmStateDelay, &fsmStateCoarse, EVT_DELAY_TO_COARSE, nullptr);
}

// ---------------------------------------------------------------------------
// Trigger helper — passes the cause label to state_machine_history before
// firing an FSM event so the on_enter callback (via histPushHistory) can
// record why the transition occurred.
// ---------------------------------------------------------------------------
static void fsmTrigger(int event, const char* cause) {
    histSetPendingCause(cause);
    fsm->trigger(event);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init() {
    sNowMs                  = tick::nowMs();
    running                 = false;
    onStateMs               = 0;
    offStateMs              = 0;
    faultReason             = FaultReason::None;
    backoffCount            = 0;
    backoffDacOffset        = 0;
    settleTimerActive       = false;
    settleStartMs           = 0;
    delayMs                 = 0;
    delayNextEvent          = EVT_DELAY_TO_IDLE;
    dependencyFaultPending  = false;
    histReset();

    delete fsm;
    fsm = new Fsm(&fsmStateOff);
    buildFsm();

    // First run_machine() call initialises the library (sets m_initialized,
    // fires onEnterOff) so that subsequent trigger() calls are not no-ops.
    histSetPendingCause("init");
    fsm->run_machine();

    return module::MODULE_INIT_SUCCESS;
}

Output update(float    tempC,
              float    coolingRate,
              float    amplifierVoltageV,
              bool     stalled,
              bool     overstroke,
              float    systemVoltage)
{
    const uint32_t nowMs = tick::nowMs();
    sNowMs = nowMs;

    // ------------------------------------------------------------------
    // 1. Fault detection — all conditions checked independently so that
    //    multiple simultaneous faults are all captured in one transition.
    // ------------------------------------------------------------------
    if (currentState != State::Fault) {
        uint8_t faultMask = 0;

        // Module dependency: deferred flag set by checkRunningModules() inside
        // a running-state on_enter callback to avoid re-entrant FSM calls.
        if (dependencyFaultPending) {
            dependencyFaultPending = false;
            //faultMask |= static_cast<uint8_t>(FaultReason::ModuleNotReady);
            _Log.println(F("Fault: required module not ready for cooling"));
        }

        // Oscillation: deferred flag set by checkOscillation() on a previous
        // tick to avoid re-entrant FSM calls from inside an on_enter callback.
        if (histTakeOscillationFaultPending()) {
            faultMask |= static_cast<uint8_t>(FaultReason::StateOscillation);
            _Log.println(F("Fault: FSM oscillating between states"));
        }

        // RMS overvoltage — proportional to cold-head temperature.
        // The allowable voltage scales linearly from 0 V at ambient to
        // AMPLIFIER_MAX_VOLTAGE_VAC at setpoint, plus a fixed margin (VAC)
        // to absorb measurement noise and transient overshoot.
        // Checked only while running (relay energised, amplifier driving load).
        if (running) {
            const float fraction = conversions::tempCToFraction(
                tempC, AMBIENT_START_C, SETPOINT_C);
            const float allowedV =
                fraction * AMPLIFIER_MAX_VOLTAGE_VAC
                + static_cast<float>(AMPLIFIER_OVERVOLTAGE_MARGIN_VAC);
            if (amplifier::getLastRmsVoltage() > allowedV) {
                faultMask |= static_cast<uint8_t>(FaultReason::RmsOvervoltage);
                _Log.printf("Fault: RMS voltage %.1fV exceeded proportional limit %.1fV (tempC=%.1f)\n",
                            amplifier::getLastRmsVoltage(), allowedV, tempC);
            }
        }

        if (systemVoltage > 0.0f && systemVoltage < MIN_SYSTEM_VOLTAGE_VDC) {
            faultMask |= static_cast<uint8_t>(FaultReason::LowSystemVoltage);
            _Log.printf("Fault: DC system voltage %.2fV below minimum %.2fV\n",
                          systemVoltage, static_cast<float>(MIN_SYSTEM_VOLTAGE_VDC));
        }

        if ((currentState == State::CoarseCooldown ||
             currentState == State::FineCooldown) && stalled) {
            faultMask |= static_cast<uint8_t>(FaultReason::TemperatureStall);
            _Log.println(F("Fault: Temperature stalled during cooldown"));
        }

        // RTD hardware fault or implausible temperature reading — checked only
        // while running so we don't false-fault before the first sensor read.
        if (running && cold_head::hasSensorFault()) {
            faultMask |= static_cast<uint8_t>(FaultReason::SensorFault);
            _Log.printf("Fault: Sensor fault detected (tempC=%.2f)\n", tempC);
        }

        // RMS overcurrent — checked only while running (amplifier is active).
        // AMPLIFIER_MAX_CURRENT_A = 0.0f disables this check.
        if (running &&
            static_cast<float>(AMPLIFIER_MAX_CURRENT_A) > 0.0f &&
            amplifier::getLastRmsCurrent() > static_cast<float>(AMPLIFIER_MAX_CURRENT_A)) {
            faultMask |= static_cast<uint8_t>(FaultReason::RmsOvercurrent);
            _Log.printf("Fault: RMS current %.2fA exceeded limit %.2fA\n",
                          amplifier::getLastRmsCurrent(),
                          static_cast<float>(AMPLIFIER_MAX_CURRENT_A));
        }

        // Overstroke / back-EMF backoff — accumulates a counter independently
        // of other fault conditions so both can be recorded simultaneously.
        if (overstroke && running) {
            _Log.printf("Backoff count: %d\n", backoffCount);
            // @todo: add a delay here to prevent the backoff count from being incremented too quickly
            ++backoffCount;
            const uint32_t newOffset =
                static_cast<uint32_t>(backoffDacOffset) +
                static_cast<uint32_t>(BACKOFF_DAC_STEP);
            backoffDacOffset = (newOffset > static_cast<uint32_t>(AMPLIFIER_RESOLUTION))
                                   ? static_cast<uint16_t>(AMPLIFIER_RESOLUTION)
                                   : static_cast<uint16_t>(newOffset);
            if (backoffCount >= static_cast<uint16_t>(BACKOFF_MAX_COUNT)) {
                faultMask |= static_cast<uint8_t>(FaultReason::TooManyBackoffs);
                _Log.println(F("Fault: Too many back-EMF stroke events; output backed off"));
            }
        }

        // Trigger a single Fault transition carrying the full composite mask.
        if (faultMask != 0) {
            faultReason = static_cast<FaultReason>(faultMask);
            const bool multi = (faultMask & (faultMask - 1u)) != 0u;
            const char* cause =
                multi                                                                     ? "multi_fault"
                : (faultMask & static_cast<uint8_t>(FaultReason::StateOscillation)) != 0u ? "oscillation"
                : (faultMask & static_cast<uint8_t>(FaultReason::RmsOvervoltage))   != 0u ? "rms_overvoltage"
                : (faultMask & static_cast<uint8_t>(FaultReason::LowSystemVoltage)) != 0u ? "low_voltage"
                : (faultMask & static_cast<uint8_t>(FaultReason::TemperatureStall)) != 0u ? "stall"
                : (faultMask & static_cast<uint8_t>(FaultReason::TooManyBackoffs))  != 0u ? "too_many_backoffs"
                : (faultMask & static_cast<uint8_t>(FaultReason::SensorFault))      != 0u ? "sensor_fault"
                : (faultMask & static_cast<uint8_t>(FaultReason::RmsOvercurrent))   != 0u ? "rms_overcurrent"
                :                                                                             "fault";
            fsmTrigger(EVT_FAULT, cause);
        }
    }

    // ------------------------------------------------------------------
    // 2. Per-state conditional and timed transitions
    //    Skipped if this tick already transitioned to Fault above.
    // ------------------------------------------------------------------
    if (currentState != State::Fault) {
        const uint32_t elapsed = nowMs - currentStateEntryMs;

        switch (currentState) {

            case State::Initialize:
                if (elapsed >= INDICATOR_INIT_AMBER_MS) {
                    _Log.println(F("Triggering EVT_INIT_DONE"));
                    fsmTrigger(EVT_INIT_DONE, "init_timer");
                }
                break;

            case State::CoarseCooldown:
                if (tempC < COARSE_FINE_THRESHOLD_C) {
                    _Log.println(F("Triggering EVT_BELOW_COARSE"));
                    fsmTrigger(EVT_BELOW_COARSE, "below_threshold");
                }
                break;

            case State::FineCooldown:
                if (tempC > COARSE_FINE_THRESHOLD_C) {
                    _Log.println(F("Triggering EVT_ABOVE_COARSE"));
                    fsmTrigger(EVT_ABOVE_COARSE, "above_threshold");
                }
                else if (overshot(tempC)) {
                    _Log.println(F("Triggering EVT_OVERSHOT"));
                    fsmTrigger(EVT_OVERSHOT, "overshoot");
                }
                else if (inBand(tempC)) {
                    _Log.println(F("Triggering EVT_IN_BAND"));
                    fsmTrigger(EVT_IN_BAND, "in_band");
                }
                break;

            case State::Overshoot:
                if (inBand(tempC)) {
                    _Log.println(F("Triggering EVT_IN_BAND"));
                    fsmTrigger(EVT_IN_BAND, "in_band");
                }
                break;

            case State::Settle:
                if (!inBand(tempC)) {
                    // Drifted out of band — reset the settle timer.
                    settleTimerActive = false;
                    settleStartMs     = 0;
                } else if (!settleTimerActive) {
                    settleTimerActive = true;
                    settleStartMs     = nowMs;
                } else if ((nowMs - settleStartMs) >= SETTLE_DURATION_MS) {
                    _Log.println(F("Triggering EVT_SETTLE_DONE"));
                    fsmTrigger(EVT_SETTLE_DONE, "settle_timer");
                }
                break;

            case State::Baseline:
                if (elapsed >= BASELINE_DURATION_MS) {
                    _Log.println(F("Triggering EVT_BASELINE_DONE"));
                    fsmTrigger(EVT_BASELINE_DONE, "baseline_timer");
                }
                break;

            case State::Shutdown:
                // The relay stays ON during Shutdown so the load sees the
                // ramp-down.  SHUTDOWN_DURATION_MS is sized to let the DAC
                // reach 0; on transition to Idle the relay is switched off.
                if (elapsed >= SHUTDOWN_DURATION_MS) {
                    _Log.println(F("Triggering EVT_SHUTDOWN_DONE"));
                    fsmTrigger(EVT_SHUTDOWN_DONE, "shutdown_timer");
                }
                break;

            case State::Delay:
                if (elapsed >= delayMs) {
                    _Log.printf("Triggering delay exit event %d\n", delayNextEvent);
                    fsmTrigger(delayNextEvent, "delay_timer");
                }
                break;

            default:
                break;
        }
    }

    // ------------------------------------------------------------------
    // 3. Advance the FSM (fires on_state callbacks; on_state is null for
    //    all states so this is primarily here to satisfy the library contract
    //    and to keep m_initialized consistent).
    // ------------------------------------------------------------------
    fsm->run_machine();

    // ------------------------------------------------------------------
    // 4. Compute output fraction, drive amplifier, and assemble output
    // ------------------------------------------------------------------
    float fraction = 0.0f;
    if (currentState == State::CoarseCooldown ||
        currentState == State::FineCooldown) {
        // Honour a manual "set vout" override; fall back to temperature-proportional target.
        fraction = amplifier::hasVoutOverride()
                       ? amplifier::getVoutOverride()
                       : conversions::tempCToFraction(tempC, AMBIENT_START_C, SETPOINT_C);
        amplifier::rampTo(fraction);
    } else if (currentState == State::Shutdown) {
        amplifier::rampTowardShutdown();
    }

    // Keep the voltage tracking monitor's setpoint in sync with the
    // proportional target so the tracker can detect real deviations
    // rather than faulting on a stale / zero target.
    if (running) {
        const float trackFraction = conversions::tempCToFraction(
            tempC, AMBIENT_START_C, SETPOINT_C);
        amplifier::setTargetVoltage(trackFraction * AMPLIFIER_MAX_VOLTAGE_VAC);
    }

    return buildOutput(currentState, fraction);
}

State getState() {
    return currentState;
}

bool isRunning() {
    return running;
}

uint32_t getOnStateDuration() {
    if (onStateMs == 0) return 0;
    if (offStateMs != 0) return offStateMs - onStateMs;
    return millis() - onStateMs;
}

void start(float tempC) {
    _Log.printf("start() tempC=%.2f\n", tempC);
    if (running) return;

    const uint32_t nowMs = tick::nowMs();
    running          = true;
    sNowMs          = nowMs;
    onStateMs        = nowMs;
    offStateMs       = 0;
    faultReason      = FaultReason::None;
    backoffCount     = 0;
    backoffDacOffset = 0;

    ESP_LOGD(TAG, "start() tempC=%.2f", tempC);

    // Select the resumption state based on the current cold-stage temperature
    // so the system can resume correctly after a reboot.
    if (tempC >= COARSE_FINE_THRESHOLD_C) {
        fsmTrigger(EVT_START_COARSE, "start");
    } else if (overshot(tempC)) {
        _Log.println(F("Triggering EVT_START_OVERSHOOT"));
        fsmTrigger(EVT_START_OVERSHOOT, "start");
    } else if (inBand(tempC)) {
        _Log.println(F("Triggering EVT_START_SETTLE"));
        fsmTrigger(EVT_START_SETTLE, "start");
    } else {
        _Log.println(F("Triggering EVT_START_FINE"));
        fsmTrigger(EVT_START_FINE, "start");
    }
}

void stop() {
    // While in Fault, defer the stop so clearFault() skips auto-start.
    if (currentState == State::Fault) {
        deferredStop_ = true;
        return;
    }
    if (!running) return;
    const uint32_t nowMs = tick::nowMs();
    running = false;
    sNowMs = nowMs;
    if (offStateMs == 0) offStateMs = nowMs;
    ESP_LOGD(TAG, "stop()");
    _Log.println(F("Triggering EVT_STOP"));
    fsmTrigger(EVT_STOP, "stop");
}

void clearFault() {
    if (currentState != State::Fault) return;
    ESP_LOGD(TAG, "clearFault()");
    sNowMs = tick::nowMs();
    // onExitFault() fires synchronously inside trigger() → make_transition(),
    // resetting faultReason, backoffCount, and backoffDacOffset before Idle
    // is entered.  running remains false; the operator must call start() to resume.
    fsmTrigger(EVT_FAULT_CLEARED, "clearFault");
}

bool takeDeferredStop() {
    const bool val = deferredStop_;
    deferredStop_ = false;
    return val;
}

void startDelay(uint32_t durationMs, State nextState) {
    if (currentState == State::Fault) return;
    delayMs = durationMs;
    switch (nextState) {
        case State::CoarseCooldown: delayNextEvent = EVT_DELAY_TO_COARSE; break;
        default:                    delayNextEvent = EVT_DELAY_TO_IDLE;   break;
    }
    sNowMs = tick::nowMs();
    _Log.printf("startDelay() durationMs=%lu nextEvent=%d\n",
                  static_cast<unsigned long>(durationMs), delayNextEvent);
    fsmTrigger(EVT_ENTER_DELAY, "startDelay");
}

void off() {
    if (currentState == State::Off) return;
    const uint32_t nowMs = tick::nowMs();
    sNowMs     = nowMs;
    running     = false;
    if (offStateMs == 0) offStateMs = nowMs;
    faultReason = FaultReason::None;
    ESP_LOGD(TAG, "off()");
    fsmTrigger(EVT_POWER_OFF, "off");
}

void setOnInitializeCallback(void (*cb)()) {
    onInitializeCb = cb;
}

void reinit() {
    ESP_LOGD(TAG, "reinit()");
    // Reset module state variables without recreating the FSM.
    // The arduino-fsm library's destructor does not free the realloc-managed
    // transitions buffer, so calling delete+new crashes when the FSM already
    // exists.  We keep the existing FSM (all transitions remain valid) and
    // simply reset our own state then trigger EVT_REINITIALIZE, which moves
    // the machine to Initialize where onEnterInitialize fires onInitializeCb.
    sNowMs              = tick::nowMs();
    running             = false;
    onStateMs           = 0;
    offStateMs          = 0;
    faultReason         = FaultReason::None;
    backoffCount        = 0;
    backoffDacOffset    = 0;
    settleTimerActive   = false;
    settleStartMs       = 0;
    delayMs             = 0;
    delayNextEvent      = EVT_DELAY_TO_IDLE;
    histReset();
    // Transition current state → Initialize.
    // Valid from Off, Idle, and Fault (all three transitions are registered
    // in buildFsm()).  onEnterInitialize() fires onInitializeCb.
    fsmTrigger(EVT_REINITIALIZE, "reinit");
}

FaultReason getFaultReason() {
    return faultReason;
}

const char* getStatusText() {
    return statusTextForState(currentState);
}

uint32_t getTimeInState() {
    return millis() - currentStateEntryMs;
}

} // namespace state_machine
