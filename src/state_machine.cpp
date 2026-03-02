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

#include "state_machine.h"
#include "config.h"
#include "conversions.h"
#include "indicator.h"
#include "amplifier.h"
#include <Arduino.h>
#include "esp_log.h"
#include <Fsm.h>

namespace state_machine {

static constexpr char TAG[] = "state_machine";

// ---------------------------------------------------------------------------
// Events — passed to Fsm::trigger()
// ---------------------------------------------------------------------------
enum : int {
    // Control events (fired by start() / stop() / off())
    EVT_START_COARSE    =  1,  ///< start() when tempK >= COARSE_FINE_THRESHOLD_K
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
static uint32_t     sDelayMs           = 0;  ///< duration to hold in Delay state
static int          sDelayNextEvent    = EVT_DELAY_TO_IDLE; ///< event fired when timer expires

// Injected timestamp — set before every trigger() call so on_enter callbacks
// can capture the correct entry time without calling millis() directly.
static uint32_t     sNowMs             = 0;

// Optional callback invoked when the FSM enters the Initialize state.
// Registered by main.cpp via setOnInitializeCallback() to re-run control
// module inits on every reinit().
static void (*sOnInitializeCb)() = nullptr;

// ---------------------------------------------------------------------------
// FSM History ring buffer — records every state entry in arrival order.
// historyHead always points to the next slot to write; the most recent
// entry is at (historyHead - 1 + FSM_HISTORY_LIMIT) % FSM_HISTORY_LIMIT.
// ---------------------------------------------------------------------------
static HistoryEntry history[FSM_HISTORY_LIMIT] = {};
static uint8_t      historyHead  = 0;
static uint8_t      historyCount = 0;

// Set just before every fsm->trigger() call via fsmTrigger(); consumed
// (stored into the HistoryEntry and reset to nullptr) by pushHistory().
static const char* pendingCause = nullptr;

// Set by checkOscillation(); consumed at the top of the next update() tick.
// Using a deferred flag avoids triggering a nested FSM transition from inside
// an on_enter callback (which would be a re-entrant FSM call).
static bool oscillationFaultPending = false;

// ---------------------------------------------------------------------------
// Internal ring-buffer accessor (returns a const-ref; no bounds checking).
// i = 0 → most recent entry, i = 1 → previous, etc.
// ---------------------------------------------------------------------------
static inline const HistoryEntry& ringAt(uint8_t i) {
    const uint8_t idx = static_cast<uint8_t>(
        (static_cast<uint16_t>(FSM_HISTORY_LIMIT) + historyHead - 1u - i)
        % static_cast<uint8_t>(FSM_HISTORY_LIMIT));
    return history[idx];
}

// ---------------------------------------------------------------------------
// Oscillation detector — called after every state push.
//
// Examines the last (FSM_OSCILLATION_MIN_CYCLES * 2) history entries.
// If they all alternate between exactly two non-trivial states AND all
// occurred within FSM_OSCILLATION_WINDOW_MS, sets sOscillationFaultPending.
// ---------------------------------------------------------------------------
static void checkOscillation() {
    const uint8_t kWindow =
        static_cast<uint8_t>(FSM_OSCILLATION_MIN_CYCLES) * static_cast<uint8_t>(2u);
    if (historyCount < kWindow) return;

    const State stateEven = ringAt(0).state;   // most recent
    const State stateOdd  = ringAt(1).state;   // previous

    // Two distinct, non-trivial states are required.
    if (stateEven == stateOdd) return;
    if (stateEven == State::Off        || stateOdd == State::Off)        return;
    if (stateEven == State::Initialize || stateOdd == State::Initialize) return;
    if (stateEven == State::Fault      || stateOdd == State::Fault)      return;

    // All entries in the window must alternate between exactly those two states.
    for (uint8_t i = 0; i < kWindow; ++i) {
        const State expected = (i % 2u == 0u) ? stateEven : stateOdd;
        if (ringAt(i).state != expected) return;
    }

    // All transitions must have occurred within the configured time window.
    const uint32_t newest = ringAt(0).enteredMs;
    const uint32_t oldest = ringAt(static_cast<uint8_t>(kWindow - 1u)).enteredMs;
    if ((newest - oldest) > static_cast<uint32_t>(FSM_OSCILLATION_WINDOW_MS)) return;

    oscillationFaultPending = true;
}

static void pushHistory(State s, uint32_t enteredMs) {
    history[historyHead] = { s, enteredMs, pendingCause };
    pendingCause = nullptr;
    historyHead = static_cast<uint8_t>(
        (static_cast<uint16_t>(historyHead) + 1u) % FSM_HISTORY_LIMIT);
    if (historyCount < static_cast<uint8_t>(FSM_HISTORY_LIMIT)) {
        ++historyCount;
    }
    checkOscillation();
}

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
static void onEnterShutdown();
static void onEnterDelay();
static void onEnterFault();
static void onExitFault();

// ---------------------------------------------------------------------------
// Library ::State objects
// Qualified as ::State to avoid shadowing the state_machine::State enum.
// ---------------------------------------------------------------------------
static ::State sFsmOff       (onEnterOff,             nullptr, nullptr);
static ::State sFsmInit      (onEnterInitialize,      nullptr, nullptr);
static ::State sFsmIdle      (onEnterIdle,            nullptr, nullptr);
static ::State sFsmCoarse    (onEnterCoarseCooldown,  nullptr, nullptr);
static ::State sFsmFine      (onEnterFineCooldown,    nullptr, nullptr);
static ::State sFsmOvershoot (onEnterOvershoot,       nullptr, nullptr);
static ::State sFsmSettle    (onEnterSettle,          nullptr, nullptr);
static ::State sFsmBaseline  (onEnterBaseline,        nullptr, nullptr);
static ::State sFsmOperating (onEnterOperating,       nullptr, nullptr);
static ::State sFsmShutdown  (onEnterShutdown,        nullptr, nullptr);
static ::State sFsmDelay     (onEnterDelay,           nullptr, nullptr);
static ::State sFsmFault     (onEnterFault,           nullptr, onExitFault);

// Heap-allocated so it can be fully reset between test cases via init().
static Fsm* fsm = nullptr;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** True when the cold stage temperature is within the setpoint tolerance band. */
static bool inBand(float tempK) {
    return (tempK >= (SETPOINT_K - SETPOINT_TOLERANCE_K)) &&
           (tempK <= (SETPOINT_K + SETPOINT_TOLERANCE_K));
}

/** True when the cold stage has clearly overshot (gone below) the setpoint. */
static bool overshot(float tempK) {
    return tempK < (SETPOINT_K - SETPOINT_TOLERANCE_K);
}

/**
 * Compute the target DAC value for cooldown states.
 * Proportional to how far the temperature has dropped from AMBIENT_START_K
 * toward SETPOINT_K.
 */
static uint16_t cooldownDacTarget(float tempK, float coolingRate) {
    (void)coolingRate;   // rate guard reserved for future use
    return conversions::tempKToDacValue(
        tempK, AMBIENT_START_K, SETPOINT_K, AMPLIFIER_RESOLUTION);
}

/**
 * Return the human-readable status string for a state.
 * State::Fault is resolved dynamically from faultReason before the
 * macro-generated switch, which carries nullptr for the Fault row.
 * All other states are generated from STATE_MACHINE_STATES.
 */
static const char* statusTextForState(State s) {
    if (s == State::Fault) {
        switch (faultReason) {
            case FaultReason::RmsOvervoltage:   return "Fault: RMS voltage exceeded safe limit";
            case FaultReason::TemperatureStall: return "Fault: Temperature stalled during cooldown";
            case FaultReason::TooManyBackoffs:  return "Fault: Too many back-EMF stroke events; output backed off";
            case FaultReason::LowSystemVoltage: return "Fault: DC system voltage below minimum threshold";
            case FaultReason::StateOscillation: return "Fault: FSM oscillating between states — manual clearFault() required";
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
static Output buildOutput(State s, uint16_t dacTarget) {
    using Mode = indicator::Mode;

    // Apply accumulated backoff reduction (floor at 0).
    if (backoffDacOffset > 0 && dacTarget > 0) {
        dacTarget = (backoffDacOffset >= dacTarget)
                        ? static_cast<uint16_t>(0)
                        : static_cast<uint16_t>(dacTarget - backoffDacOffset);
    }

    Output o{};
    o.state        = s;
    o.dacTarget    = dacTarget;
    o.alarmRelay   = false;
    o.statusText   = statusTextForState(s);
    o.backoffCount = backoffCount;

    switch (s) {
        case State::Off:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::Off;
            break;

        case State::Initialize:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::SolidAmber;
            o.readyIndMode = Mode::SolidAmber;
            break;

        case State::Idle:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::SolidRed;
            o.readyIndMode = Mode::Off;
            break;

        case State::CoarseCooldown:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::Off;
            break;

        case State::FineCooldown:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::FlashSlowGreen;
            break;

        case State::Overshoot:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::FlashFastGreen;
            break;

        case State::Settle:
            o.bypassRelay  = false;   // Normal
            o.faultIndMode = Mode::FlashFastRed;
            o.readyIndMode = Mode::FlashFastGreen;
            break;

        case State::Baseline:
            o.bypassRelay  = false;   // Normal
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::SolidGreen;
            break;

        case State::Operating:
            o.bypassRelay  = false;   // Normal
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::SolidGreen;
            break;

        case State::Shutdown:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::Off;
            o.readyIndMode = Mode::Off;
            break;

        case State::Delay:
            o.bypassRelay  = true;
            o.faultIndMode = Mode::SolidAmber;
            o.readyIndMode = Mode::SolidAmber;
            break;

        case State::Fault:
            o.bypassRelay  = true;
            o.alarmRelay   = true;
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
    Serial.printf("[SM] -> %s\n", stateName(s));
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
    pushHistory(s, sNowMs);
}

static void onEnterOff()            { setStateEntry(State::Off); }
static void onEnterInitialize() {
    setStateEntry(State::Initialize);
    if (sOnInitializeCb) {
        sOnInitializeCb();
    }
}
static void onEnterIdle()           { setStateEntry(State::Idle); }
static void onEnterCoarseCooldown() { setStateEntry(State::CoarseCooldown); }
static void onEnterFineCooldown()   { setStateEntry(State::FineCooldown); }
static void onEnterOvershoot()      { setStateEntry(State::Overshoot); }
static void onEnterSettle()         { setStateEntry(State::Settle); }
static void onEnterBaseline()       { setStateEntry(State::Baseline); }
static void onEnterOperating()      { setStateEntry(State::Operating); }
static void onEnterShutdown()       { setStateEntry(State::Shutdown); }

static void onEnterDelay() {
    setStateEntry(State::Delay);
    Serial.printf("[SM] Delay for %lu ms\n", static_cast<unsigned long>(sDelayMs));
}

static void onEnterFault() {
    setStateEntry(State::Fault);   // faultReason is preserved (set before trigger())
    running = false;
    if (offStateMs == 0) offStateMs = sNowMs;
}

/**
 * Called by the FSM whenever the machine leaves State::Fault.
 * Resets all fault-related and backoff state so the system starts clean
 * on the next start() call.
 */
static void onExitFault() {
    Serial.printf("[SM] Fault cleared (was: %d); resetting backoff state\n",
                  static_cast<int>(faultReason));
    ESP_LOGD(TAG, "Fault cleared (reason %d); backoffCount=%u dacOffset=%u reset",
             static_cast<int>(faultReason), backoffCount, backoffDacOffset);
    faultReason              = FaultReason::None;
    backoffCount             = 0;
    backoffDacOffset         = 0;
    oscillationFaultPending = false;  // restart the oscillation window after manual clear
}

// ---------------------------------------------------------------------------
// FSM construction — called once per init()
// ---------------------------------------------------------------------------

static void buildFsm() {
    Serial.printf("buildFsm()\n");
    // ── Start events from Off and Idle ────────────────────────────────────
    // start() selects the correct resume state based on the current temperature.
    ::State* startableStates[] = { &sFsmOff, &sFsmIdle };
    for (auto* from : startableStates) {
        fsm->add_transition(from, &sFsmCoarse,    EVT_START_COARSE,    nullptr);
        fsm->add_transition(from, &sFsmFine,      EVT_START_FINE,      nullptr);
        fsm->add_transition(from, &sFsmSettle,    EVT_START_SETTLE,    nullptr);
        fsm->add_transition(from, &sFsmOvershoot, EVT_START_OVERSHOOT, nullptr);
    }

    // ── Re-initialize: Off, Idle, or Fault → Initialize ───────────────────
    // Triggered by reinit().  onEnterInitialize fires the registered callback
    // so control modules are re-initialised on every transition to Initialize.
    // Fault is included so the operator can reinit directly after clearing a
    // fault without a separate clearFault() + off() sequence.
    // onExitFault() fires automatically on the Fault → Initialize transition,
    // resetting faultReason and backoff state before Initialize is entered.
    fsm->add_transition(&sFsmOff,   &sFsmInit, EVT_REINITIALIZE, nullptr);
    fsm->add_transition(&sFsmIdle,  &sFsmInit, EVT_REINITIALIZE, nullptr);
    fsm->add_transition(&sFsmFault, &sFsmInit, EVT_REINITIALIZE, nullptr);

    // ── Initialize → Idle ─────────────────────────────────────────────────
    // Timer driven in update() using nowMs (not add_timed_transition).
    fsm->add_transition(&sFsmInit, &sFsmIdle, EVT_INIT_DONE, nullptr);

    // ── Cooldown transitions ───────────────────────────────────────────────
    fsm->add_transition(&sFsmCoarse,    &sFsmFine,      EVT_BELOW_COARSE, nullptr);
    fsm->add_transition(&sFsmFine,      &sFsmCoarse,    EVT_ABOVE_COARSE, nullptr);
    fsm->add_transition(&sFsmFine,      &sFsmOvershoot, EVT_OVERSHOT,     nullptr);
    fsm->add_transition(&sFsmFine,      &sFsmSettle,    EVT_IN_BAND,      nullptr);
    fsm->add_transition(&sFsmOvershoot, &sFsmSettle,    EVT_IN_BAND,      nullptr);

    // ── Settle → Baseline (timer-driven in update()) ──────────────────────
    fsm->add_transition(&sFsmSettle,   &sFsmBaseline,  EVT_SETTLE_DONE,  nullptr);

    // ── Baseline → Operating (timer-driven in update()) ───────────────────
    fsm->add_transition(&sFsmBaseline, &sFsmOperating, EVT_BASELINE_DONE, nullptr);

    // ── Shutdown → Idle (timer-driven in update()) ────────────────────────
    fsm->add_transition(&sFsmShutdown, &sFsmIdle,      EVT_SHUTDOWN_DONE, nullptr);

    // ── Stop: all running states → Shutdown ───────────────────────────────
    // Delay is included so stop() can interrupt a pending wait.
    ::State* stoppableStates[] = {
        &sFsmCoarse, &sFsmFine, &sFsmOvershoot,
        &sFsmSettle, &sFsmBaseline, &sFsmOperating, &sFsmDelay
    };
    for (auto* from : stoppableStates) {
        fsm->add_transition(from, &sFsmShutdown, EVT_STOP, nullptr);
    }

    // ── Fault: RMS overvoltage from every non-Fault state ─────────────────
    // Delay is included so an RMS spike during a wait causes a fault.
    ::State* allNonFaultStates[] = {
        &sFsmOff, &sFsmInit, &sFsmIdle,
        &sFsmCoarse, &sFsmFine, &sFsmOvershoot,
        &sFsmSettle, &sFsmBaseline, &sFsmOperating, &sFsmShutdown, &sFsmDelay
    };
    for (auto* from : allNonFaultStates) {
        fsm->add_transition(from, &sFsmFault, EVT_FAULT_RMS, nullptr);
    }

    // ── Fault: low system voltage from every non-Fault state ──────────────
    // Mirrors EVT_FAULT_RMS — any state can immediately fault on low voltage.
    for (auto* from : allNonFaultStates) {
        fsm->add_transition(from, &sFsmFault, EVT_FAULT_LOW_VOLTAGE, nullptr);
    }

    // ── Fault: state oscillation from every non-Fault state ───────────────
    // Fired when checkOscillation() detects repeated A↔B bouncing.
    for (auto* from : allNonFaultStates) {
        fsm->add_transition(from, &sFsmFault, EVT_FAULT_OSCILLATION, nullptr);
    }

    // ── Fault: temperature stall only in cooldown states ──────────────────
    fsm->add_transition(&sFsmCoarse, &sFsmFault, EVT_FAULT_STALL, nullptr);
    fsm->add_transition(&sFsmFine,   &sFsmFault, EVT_FAULT_STALL, nullptr);

    // ── Fault: too many backoffs from any running state ────────────────────
    for (auto* from : stoppableStates) {
        fsm->add_transition(from, &sFsmFault, EVT_FAULT_BACKOFFS, nullptr);
    }

    // ── Fault clear: Fault → Idle (fired by clearFault()) ─────────────────
    // onExitFault() resets faultReason, backoff counter, and DAC offset.
    fsm->add_transition(&sFsmFault, &sFsmIdle, EVT_FAULT_CLEARED, nullptr);

    // ── Power-off: any state → Off ─────────────────────────────────────────
    ::State* powerOffableStates[] = {
        &sFsmInit, &sFsmIdle,
        &sFsmCoarse, &sFsmFine, &sFsmOvershoot,
        &sFsmSettle, &sFsmBaseline, &sFsmOperating,
        &sFsmShutdown, &sFsmDelay, &sFsmFault
    };
    for (auto* from : powerOffableStates) {
        fsm->add_transition(from, &sFsmOff, EVT_POWER_OFF, nullptr);
    }

    // ── Delay entry: from all non-Fault, non-Delay states ─────────────────
    // Called by startDelay() via EVT_ENTER_DELAY.
    ::State* delayableStates[] = {
        &sFsmOff, &sFsmInit, &sFsmIdle,
        &sFsmCoarse, &sFsmFine, &sFsmOvershoot,
        &sFsmSettle, &sFsmBaseline, &sFsmOperating, &sFsmShutdown
    };
    for (auto* from : delayableStates) {
        fsm->add_transition(from, &sFsmDelay, EVT_ENTER_DELAY, nullptr);
    }

    // ── Delay exit: timer-driven in update() ──────────────────────────────
    fsm->add_transition(&sFsmDelay, &sFsmIdle,   EVT_DELAY_TO_IDLE,   nullptr);
    fsm->add_transition(&sFsmDelay, &sFsmCoarse, EVT_DELAY_TO_COARSE, nullptr);
}

// ---------------------------------------------------------------------------
// Trigger helper — sets pendingCause before firing an FSM event so the
// on_enter callback (via pushHistory) can record why the transition occurred.
// ---------------------------------------------------------------------------
static void fsmTrigger(int event, const char* cause) {
    pendingCause = cause;
    fsm->trigger(event);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init(uint32_t nowMs) {
    Serial.printf("init()\n");
    sNowMs           = nowMs;
    running          = false;
    onStateMs        = 0;
    offStateMs       = 0;
    faultReason      = FaultReason::None;
    backoffCount     = 0;
    backoffDacOffset = 0;
    settleTimerActive= false;
    settleStartMs    = 0;
    sDelayMs         = 0;
    sDelayNextEvent  = EVT_DELAY_TO_IDLE;
    historyHead              = 0;
    historyCount             = 0;
    pendingCause             = nullptr;
    oscillationFaultPending  = false;

    delete fsm;
    fsm = new Fsm(&sFsmOff);
    buildFsm();

    // First run_machine() call initialises the library (sets m_initialized,
    // fires onEnterOff) so that subsequent trigger() calls are not no-ops.
    pendingCause = "init";
    fsm->run_machine();

    return module::MODULE_INIT_SUCCESS;
}

Output update(float    tempK,
              float    coolingRate,
              float    amplifierVoltageV,
              bool     stalled,
              uint32_t nowMs,
              bool     overstroke,
              float    systemVoltage)
{
    //Serial.printf("update() tempK=%.2f coolingRate=%.2f rmsV=%.2f stalled=%d overstroke=%d\n",
             //tempK, coolingRate, rmsVoltage, stalled, overstroke);
    //ESP_LOGD(TAG, "update() tempK=%.2f coolingRate=%.2f rmsV=%.2f stalled=%d overstroke=%d",
             //tempK, coolingRate, rmsVoltage, stalled, overstroke);

    sNowMs = nowMs;

    // ------------------------------------------------------------------
    // 1. Global fault checks — fire from any non-Fault state
    // ------------------------------------------------------------------
    if (currentState != State::Fault) {
        if (oscillationFaultPending) {
            // Oscillation detected on a previous tick inside an on_enter callback.
            // Consume the flag here to avoid re-entrant FSM calls.
            oscillationFaultPending = false;
            faultReason = FaultReason::StateOscillation;
            Serial.printf("[SM] Fault: FSM oscillating between states\n");
            fsmTrigger(EVT_FAULT_OSCILLATION, "oscillation");

        } else if (amplifier::getLastRmsVoltageV() > AMPLIFIER_MAX_VOLTAGE) {
            faultReason = FaultReason::RmsOvervoltage;
            Serial.printf("Fault: RMS voltage exceeded safe limit\n");
            fsmTrigger(EVT_FAULT_RMS, "rms_overvoltage");

        } else if (systemVoltage > 0.0f && systemVoltage < MIN_SYSTEM_VOLTAGE_VDC) {
            faultReason = FaultReason::LowSystemVoltage;
            Serial.printf("Fault: DC system voltage %.2fV below minimum %.2fV\n",
                          systemVoltage, static_cast<float>(MIN_SYSTEM_VOLTAGE_VDC));
            fsmTrigger(EVT_FAULT_LOW_VOLTAGE, "low_voltage");

        } else if ((currentState == State::CoarseCooldown ||
                    currentState == State::FineCooldown) && stalled) {
            faultReason = FaultReason::TemperatureStall;
            Serial.printf("Fault: Temperature stalled during cooldown\n");
            fsmTrigger(EVT_FAULT_STALL, "stall");

        } else if (overstroke && running) {
            Serial.printf("Backoff count: %d\n", backoffCount);
            // @todo: add a delay here to prevent the backoff count from being incremented too quickly
            ++backoffCount;
            const uint32_t newOffset =
                static_cast<uint32_t>(backoffDacOffset) +
                static_cast<uint32_t>(BACKOFF_DAC_STEP);
            backoffDacOffset = (newOffset > static_cast<uint32_t>(AMPLIFIER_RESOLUTION))
                                   ? static_cast<uint16_t>(AMPLIFIER_RESOLUTION)
                                   : static_cast<uint16_t>(newOffset);
            if (backoffCount >= static_cast<uint16_t>(BACKOFF_MAX_COUNT)) {
                faultReason = FaultReason::TooManyBackoffs;
                Serial.printf("Fault: Too many back-EMF stroke events; output backed off\n");
                fsmTrigger(EVT_FAULT_BACKOFFS, "too_many_backoffs");
            }
        }
        else {
            // @todo: clear overstroke flag if overstroke has been false for a while
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
                    Serial.printf("Triggering EVT_INIT_DONE\n");
                    fsmTrigger(EVT_INIT_DONE, "init_timer");
                }
                break;

            case State::CoarseCooldown:
                if (tempK < COARSE_FINE_THRESHOLD_K) {
                    Serial.printf("Triggering EVT_BELOW_COARSE\n");
                    fsmTrigger(EVT_BELOW_COARSE, "below_85K");
                }
                break;

            case State::FineCooldown:
                if (tempK > COARSE_FINE_THRESHOLD_K) {
                    Serial.printf("Triggering EVT_ABOVE_COARSE\n");
                    fsmTrigger(EVT_ABOVE_COARSE, "above_85K");
                }
                else if (overshot(tempK)) {
                    Serial.printf("Triggering EVT_OVERSHOT\n");
                    fsmTrigger(EVT_OVERSHOT, "overshoot");
                }
                else if (inBand(tempK)) {
                    Serial.printf("Triggering EVT_IN_BAND\n");
                    fsmTrigger(EVT_IN_BAND, "in_band");
                }
                break;

            case State::Overshoot:
                if (inBand(tempK)) {
                    Serial.printf("Triggering EVT_IN_BAND\n");
                    fsmTrigger(EVT_IN_BAND, "in_band");
                }
                break;

            case State::Settle:
                if (!inBand(tempK)) {
                    // Drifted out of band — reset the settle timer.
                    settleTimerActive = false;
                    settleStartMs     = 0;
                } else if (!settleTimerActive) {
                    settleTimerActive = true;
                    settleStartMs     = nowMs;
                } else if ((nowMs - settleStartMs) >= SETTLE_DURATION_MS) {
                    Serial.printf("Triggering EVT_SETTLE_DONE\n");
                    fsmTrigger(EVT_SETTLE_DONE, "settle_timer");
                }
                break;

            case State::Baseline:
                if (elapsed >= BASELINE_DURATION_MS) {
                    Serial.printf("Triggering EVT_BASELINE_DONE\n");
                    fsmTrigger(EVT_BASELINE_DONE, "baseline_timer");
                }
                break;

            case State::Shutdown:
                if (elapsed >= SHUTDOWN_DURATION_MS) {
                    Serial.printf("Triggering EVT_SHUTDOWN_DONE\n");
                    fsmTrigger(EVT_SHUTDOWN_DONE, "shutdown_timer");
                }
                break;

            case State::Delay:
                if (elapsed >= sDelayMs) {
                    Serial.printf("Triggering delay exit event %d\n", sDelayNextEvent);
                    fsmTrigger(sDelayNextEvent, "delay_timer");
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
    // 4. Compute DAC target and assemble output
    // ------------------------------------------------------------------
    uint16_t dacTarget = 0;
    if (currentState == State::CoarseCooldown ||
        currentState == State::FineCooldown) {
        dacTarget = cooldownDacTarget(tempK, coolingRate);
    }
    return buildOutput(currentState, dacTarget);
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

void start(uint32_t nowMs, float tempK) {
    Serial.printf("start() tempK=%.2f\n", tempK);
    if (running) return;
    running          = true;
    sNowMs           = nowMs;
    onStateMs        = nowMs;
    offStateMs       = 0;
    faultReason      = FaultReason::None;
    backoffCount     = 0;
    backoffDacOffset = 0;

    ESP_LOGD(TAG, "start() tempK=%.2f", tempK);

    // Select the resumption state based on the current cold-stage temperature
    // so the system can resume correctly after a reboot.
    if (tempK >= COARSE_FINE_THRESHOLD_K) {
        fsmTrigger(EVT_START_COARSE, "start");
    } else if (overshot(tempK)) {
        Serial.printf("Triggering EVT_START_OVERSHOOT\n");
        fsmTrigger(EVT_START_OVERSHOOT, "start");
    } else if (inBand(tempK)) {
        Serial.printf("Triggering EVT_START_SETTLE\n");
        fsmTrigger(EVT_START_SETTLE, "start");
    } else {
        Serial.printf("Triggering EVT_START_FINE\n");
        fsmTrigger(EVT_START_FINE, "start");
    }
}

void stop(uint32_t nowMs) {
    Serial.printf("stop()\n");
    if (!running) return;
    running = false;
    sNowMs  = nowMs;
    if (offStateMs == 0) offStateMs = nowMs;
    ESP_LOGD(TAG, "stop()");
    Serial.printf("Triggering EVT_STOP\n");
    fsmTrigger(EVT_STOP, "stop");
}

void clearFault(uint32_t nowMs) {
    if (currentState != State::Fault) return;
    Serial.printf("clearFault()\n");
    ESP_LOGD(TAG, "clearFault()");
    sNowMs = nowMs;
    // onExitFault() fires synchronously inside trigger() → make_transition(),
    // resetting faultReason, backoffCount, and backoffDacOffset before Idle
    // is entered.  running remains false; the operator must call start() to resume.
    fsmTrigger(EVT_FAULT_CLEARED, "clearFault");
}

void startDelay(uint32_t nowMs, uint32_t durationMs, State nextState) {
    if (currentState == State::Fault) return;
    sDelayMs = durationMs;
    switch (nextState) {
        case State::CoarseCooldown: sDelayNextEvent = EVT_DELAY_TO_COARSE; break;
        default:                    sDelayNextEvent = EVT_DELAY_TO_IDLE;   break;
    }
    sNowMs = nowMs;
    Serial.printf("startDelay() durationMs=%lu nextEvent=%d\n",
                  static_cast<unsigned long>(durationMs), sDelayNextEvent);
    fsmTrigger(EVT_ENTER_DELAY, "startDelay");
}

void off(uint32_t nowMs) {
    Serial.printf("off()\n");
    if (currentState == State::Off) return;
    sNowMs      = nowMs;
    running     = false;
    if (offStateMs == 0) offStateMs = nowMs;
    faultReason = FaultReason::None;
    ESP_LOGD(TAG, "off()");
    Serial.printf("Triggering EVT_POWER_OFF\n");
    fsmTrigger(EVT_POWER_OFF, "off");
}

void setOnInitializeCallback(void (*cb)()) {
    sOnInitializeCb = cb;
}

void reinit(uint32_t nowMs) {
    Serial.printf("reinit()\n");
    ESP_LOGD(TAG, "reinit()");
    // Reset module state variables without recreating the FSM.
    // The arduino-fsm library's destructor does not free the realloc-managed
    // transitions buffer, so calling delete+new crashes when the FSM already
    // exists.  We keep the existing FSM (all transitions remain valid) and
    // simply reset our own state then trigger EVT_REINITIALIZE, which moves
    // the machine to Initialize where onEnterInitialize fires sOnInitializeCb.
    sNowMs           = nowMs;
    running          = false;
    onStateMs        = 0;
    offStateMs       = 0;
    faultReason      = FaultReason::None;
    backoffCount     = 0;
    backoffDacOffset = 0;
    settleTimerActive= false;
    settleStartMs    = 0;
    sDelayMs         = 0;
    sDelayNextEvent  = EVT_DELAY_TO_IDLE;
    historyHead              = 0;
    historyCount             = 0;
    pendingCause             = nullptr;
    oscillationFaultPending  = false;
    // Transition current state → Initialize.
    // Valid from Off, Idle, and Fault (all three transitions are registered
    // in buildFsm()).  onEnterInitialize() fires sOnInitializeCb.
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

uint8_t getHistoryCount() {
    return historyCount;
}

HistoryEntry getHistoryEntry(uint8_t i) {
    if (i >= historyCount) return HistoryEntry{};
    return ringAt(i);
}

} // namespace state_machine
