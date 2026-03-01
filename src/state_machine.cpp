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
    EVT_FAULT_LOW_VOLTAGE = 21,  ///< DC supply voltage below MIN_SYSTEM_VOLTAGE_VDC

    // Fault-clear event
    EVT_FAULT_CLEARED   = 22,  ///< clearFault() → Idle (resets fault reason & backoffs)

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
    Serial.printf("cooldownDacTarget() tempK=%.2f coolingRate=%.2f\n", tempK, coolingRate);
    (void)coolingRate;   // rate guard reserved for future use
    return conversions::tempKToDacValue(
        tempK, AMBIENT_START_K, SETPOINT_K, MCP4921_MAX_VALUE);
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
}

static void onEnterOff()            { setStateEntry(State::Off); }
static void onEnterInitialize()     { setStateEntry(State::Initialize); }
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
    faultReason      = FaultReason::None;
    backoffCount     = 0;
    backoffDacOffset = 0;
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

    delete fsm;
    fsm = new Fsm(&sFsmOff);
    buildFsm();

    // First run_machine() call initialises the library (sets m_initialized,
    // fires onEnterOff) so that subsequent trigger() calls are not no-ops.
    fsm->run_machine();

    return module::MODULE_INIT_SUCCESS;
}

Output update(float    tempK,
              float    coolingRate,
              float    rmsVoltage,
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
        if (rmsVoltage > RMS_MAX_VOLTAGE_VDC) {
            faultReason = FaultReason::RmsOvervoltage;
            Serial.printf("Fault: RMS voltage exceeded safe limit\n");
            fsm->trigger(EVT_FAULT_RMS);

        } else if (systemVoltage > 0.0f && systemVoltage < MIN_SYSTEM_VOLTAGE_VDC) {
            faultReason = FaultReason::LowSystemVoltage;
            Serial.printf("Fault: DC system voltage %.2fV below minimum %.2fV\n",
                          systemVoltage, static_cast<float>(MIN_SYSTEM_VOLTAGE_VDC));
            fsm->trigger(EVT_FAULT_LOW_VOLTAGE);

        } else if ((currentState == State::CoarseCooldown ||
                    currentState == State::FineCooldown) && stalled) {
            faultReason = FaultReason::TemperatureStall;
            Serial.printf("Fault: Temperature stalled during cooldown\n");
            fsm->trigger(EVT_FAULT_STALL);

        } else if (overstroke && running) {
            Serial.printf("Backoff count: %d\n", backoffCount);
            // @todo: add a delay here to prevent the backoff count from being incremented too quickly
            ++backoffCount;
            const uint32_t newOffset =
                static_cast<uint32_t>(backoffDacOffset) +
                static_cast<uint32_t>(BACKOFF_DAC_STEP);
            backoffDacOffset = (newOffset > static_cast<uint32_t>(MCP4921_MAX_VALUE))
                                   ? static_cast<uint16_t>(MCP4921_MAX_VALUE)
                                   : static_cast<uint16_t>(newOffset);
            if (backoffCount >= static_cast<uint16_t>(BACKOFF_MAX_COUNT)) {
                faultReason = FaultReason::TooManyBackoffs;
                Serial.printf("Fault: Too many back-EMF stroke events; output backed off\n");
                fsm->trigger(EVT_FAULT_BACKOFFS);
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
                    fsm->trigger(EVT_INIT_DONE);
                }
                break;

            case State::CoarseCooldown:
                if (tempK < COARSE_FINE_THRESHOLD_K) {
                    Serial.printf("Triggering EVT_BELOW_COARSE\n");
                    fsm->trigger(EVT_BELOW_COARSE);
                }
                break;

            case State::FineCooldown:
                if (tempK > COARSE_FINE_THRESHOLD_K) {
                    Serial.printf("Triggering EVT_ABOVE_COARSE\n");
                    fsm->trigger(EVT_ABOVE_COARSE);
                }
                else if (overshot(tempK)) {
                    Serial.printf("Triggering EVT_OVERSHOT\n");
                    fsm->trigger(EVT_OVERSHOT);
                }
                else if (inBand(tempK)) {
                    Serial.printf("Triggering EVT_IN_BAND\n");
                    fsm->trigger(EVT_IN_BAND);
                }
                break;

            case State::Overshoot:
                if (inBand(tempK)) {
                    Serial.printf("Triggering EVT_IN_BAND\n");
                    fsm->trigger(EVT_IN_BAND);
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
                    fsm->trigger(EVT_SETTLE_DONE);
                }
                break;

            case State::Baseline:
                if (elapsed >= BASELINE_DURATION_MS) {
                    Serial.printf("Triggering EVT_BASELINE_DONE\n");
                    fsm->trigger(EVT_BASELINE_DONE);
                }
                break;

            case State::Shutdown:
                if (elapsed >= SHUTDOWN_DURATION_MS) {
                    Serial.printf("Triggering EVT_SHUTDOWN_DONE\n");
                    fsm->trigger(EVT_SHUTDOWN_DONE);
                }
                break;

            case State::Delay:
                if (elapsed >= sDelayMs) {
                    Serial.printf("Triggering delay exit event %d\n", sDelayNextEvent);
                    fsm->trigger(sDelayNextEvent);
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
        fsm->trigger(EVT_START_COARSE);
    } else if (overshot(tempK)) {
        Serial.printf("Triggering EVT_START_OVERSHOOT\n");
        fsm->trigger(EVT_START_OVERSHOOT);
    } else if (inBand(tempK)) {
        Serial.printf("Triggering EVT_START_SETTLE\n");
        fsm->trigger(EVT_START_SETTLE);
    } else {
        Serial.printf("Triggering EVT_START_FINE\n");
        fsm->trigger(EVT_START_FINE);
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
    fsm->trigger(EVT_STOP);
}

void clearFault(uint32_t nowMs) {
    if (currentState != State::Fault) return;
    Serial.printf("clearFault()\n");
    ESP_LOGD(TAG, "clearFault()");
    sNowMs = nowMs;
    // onExitFault() fires synchronously inside trigger() → make_transition(),
    // resetting faultReason, backoffCount, and backoffDacOffset before Idle
    // is entered.  running remains false; the operator must call start() to resume.
    fsm->trigger(EVT_FAULT_CLEARED);
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
    fsm->trigger(EVT_ENTER_DELAY);
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
    fsm->trigger(EVT_POWER_OFF);
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
