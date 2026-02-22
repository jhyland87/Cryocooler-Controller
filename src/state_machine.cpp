/**
 * @file state_machine.cpp
 * @brief Cryocooler system state machine implementation
 *
 * Pure logic -- no Serial.print, no hardware calls.
 * All inputs are injected via update(); all outputs are returned in the
 * Output struct so that callers (main.cpp) handle I/O.
 */

#include "state_machine.h"
#include "config.h"
#include "conversions.h"
#include "indicator.h"
#include <Arduino.h>

namespace state_machine {

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static State       currentState    = State::Off;
static uint32_t    currentStateEntryMs = 0;   // millis() when current state was entered
static bool        running         = false; // process is off until start() is called
static FaultReason faultReason     = FaultReason::None;
static uint32_t    onStateMs       = 0;   // millis() when it entered an on state
static uint32_t    offStateMs      = 0;   // millis() when it entered an off state

// Settle timer -- starts counting when temp enters the tolerance band
static uint32_t settleStartMs     = 0;
static bool     settleTimerActive = false;

// Back-EMF backoff tracking
static uint16_t backoffCount      = 0;   // total backoff events in this run
static uint16_t backoffDacOffset  = 0;   // cumulative DAC reduction (counts)

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static void enterState(State s, uint32_t nowMs) {
    currentState        = s;
    currentStateEntryMs = nowMs;
    if (s != State::Settle) {
        settleTimerActive = false;
        settleStartMs     = 0;
    }
    if (s != State::Fault) {
        faultReason = FaultReason::None;
    }
}

static void enterFault(FaultReason reason, uint32_t nowMs) {
    faultReason = reason;
    running     = false;
    enterState(State::Fault, nowMs);
}

/** Return the status description string for a given state. */
static const char* statusTextForState(State s) {
    switch (s) {
        case State::Off:            return "System is off";
        case State::Initialize:     return "Initial power up state";
        case State::Idle:           return "Cold stage is warm; dewar is not cooling";
        case State::CoarseCooldown: return "Cooling; cold stage is above 85K";
        case State::FineCooldown:   return "Cooling; cold stage is below 85K";
        case State::Overshoot:      return "Cold stage is cooler than set point; integrator is settling";
        case State::Settle:         return "Cold stage temperature is settling; circuits switched to Normal";
        case State::Baseline:       return "Cold stage temperature has settled; collecting baseline data";
        case State::Operating:      return "System is operating normally; checking for deviations from baseline";
        case State::Fault:
            switch (faultReason) {
                case FaultReason::RmsOvervoltage:   return "Fault: RMS voltage exceeded safe limit";
                case FaultReason::TemperatureStall: return "Fault: Temperature stalled during cooldown";
                case FaultReason::TooManyBackoffs:  return "Fault: Too many back-EMF stroke events; output backed off";
                default:                            return "Fault: Unknown reason";
            }
    }
    return "Unknown state";
}

/** True when the cold stage temperature is within the setpoint tolerance band. */
static bool inBand(float tempK) {
    return (tempK >= (SETPOINT_K - SETPOINT_TOLERANCE_K)) &&
           (tempK <= (SETPOINT_K + SETPOINT_TOLERANCE_K));
}

/** True when the cold stage has clearly overshot (gone below) the setpoint. */
static bool overshot(float tempK) {
    return (tempK < (SETPOINT_K - SETPOINT_TOLERANCE_K));
}

/**
 * Compute the target DAC value for cooldown states.
 *
 * The output is proportional to how far the temperature has dropped from
 * AMBIENT_START_K toward SETPOINT_K.  The coolingRate guard freezes the
 * target (no further increase) when the stage is already cooling faster
 * than the configured limit.
 */
static uint16_t cooldownDacTarget(float tempK, float coolingRate) {
    const uint16_t proportional = conversions::tempKToDacValue(
        tempK,
        AMBIENT_START_K,
        SETPOINT_K,
        MCP4921_MAX_VALUE);

    // Hold target when cooling rate already exceeds the limit so that the
    // DAC ramp does not push temperature down any faster.
    if (coolingRate > MAX_COOLDOWN_RATE_K_PER_MIN) {
        return proportional;
    }

    return proportional;
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
// Public API
// ---------------------------------------------------------------------------

void init(uint32_t nowMs) {
    running          = false;
    onStateMs        = 0;
    offStateMs       = 0;
    faultReason      = FaultReason::None;
    backoffCount     = 0;
    backoffDacOffset = 0;
    enterState(State::Off, nowMs);
}

Output update(float    tempK,
              float    coolingRate,
              float    rmsVoltage,
              bool     stalled,
              uint32_t nowMs,
              bool     overstroke)
{
    // ------------------------------------------------------------------
    // Global fault checks (fire from any non-Fault state)
    // ------------------------------------------------------------------
    if (currentState != State::Fault) {
        if (rmsVoltage > RMS_MAX_VOLTAGE_VDC) {
            enterFault(FaultReason::RmsOvervoltage, nowMs);
            return buildOutput(State::Fault, 0);
        }
        if ((currentState == State::CoarseCooldown ||
             currentState == State::FineCooldown) && stalled) {
            enterFault(FaultReason::TemperatureStall, nowMs);
            return buildOutput(State::Fault, 0);
        }

        // Back-EMF overstroke: increment backoff counter and apply DAC
        // reduction.  After BACKOFF_MAX_COUNT events the system faults.
        if (overstroke && running) {
            ++backoffCount;
            // Accumulate DAC reduction; cap at full-scale to stay in uint16_t.
            const uint32_t newOffset = static_cast<uint32_t>(backoffDacOffset)
                                       + static_cast<uint32_t>(BACKOFF_DAC_STEP);
            backoffDacOffset = (newOffset > MCP4921_MAX_VALUE)
                                    ? static_cast<uint16_t>(MCP4921_MAX_VALUE)
                                    : static_cast<uint16_t>(newOffset);
            if (backoffCount >= static_cast<uint16_t>(BACKOFF_MAX_COUNT)) {
                enterFault(FaultReason::TooManyBackoffs, nowMs);
                return buildOutput(State::Fault, 0);
            }
        }
    }

    // ------------------------------------------------------------------
    // Per-state transition logic
    // Each branch MUST return the new state's buildOutput after calling
    // enterState() so the caller always sees the current state.
    // ------------------------------------------------------------------
    const uint32_t elapsed = nowMs - currentStateEntryMs;

    switch (currentState) {

        // ---- Off -------------------------------------------------------
        case State::Off:
            if (offStateMs == 0) {
            offStateMs = nowMs;
            }
            return buildOutput(State::Off, 0);

        // ---- Initialize ------------------------------------------------
        case State::Initialize:
            if (onStateMs == 0) {
                onStateMs = nowMs;
                offStateMs = 0;
            }
            if (elapsed >= INDICATOR_INIT_AMBER_MS) {
                enterState(State::Idle, nowMs);
                return buildOutput(State::Idle, 0);
            }
            return buildOutput(State::Initialize, 0);

        // ---- Idle ------------------------------------------------------
        case State::Idle:
            if (offStateMs == 0) {
                offStateMs = nowMs;
            }
            // Remain in Idle until start() is called externally.
            return buildOutput(State::Idle, 0);

        // ---- Coarse Cooldown -------------------------------------------
        case State::CoarseCooldown: {
            const uint16_t target = cooldownDacTarget(tempK, coolingRate);
            if (tempK < COARSE_FINE_THRESHOLD_K) {
                enterState(State::FineCooldown, nowMs);
                return buildOutput(State::FineCooldown, target);
            }
            return buildOutput(State::CoarseCooldown, target);
        }

        // ---- Fine Cooldown ---------------------------------------------
        case State::FineCooldown: {
            // Temperature bounced back above threshold: return to Coarse
            if (tempK > COARSE_FINE_THRESHOLD_K) {
                const uint16_t target = cooldownDacTarget(tempK, coolingRate);
                enterState(State::CoarseCooldown, nowMs);
                return buildOutput(State::CoarseCooldown, target);
            }

            // Clear overshoot: below the tolerance band
            if (overshot(tempK)) {
                enterState(State::Overshoot, nowMs);
                return buildOutput(State::Overshoot, 0);
            }

            // Reached setpoint band without overshoot: skip Overshoot, go to Settle
            if (inBand(tempK)) {
                enterState(State::Settle, nowMs);
                return buildOutput(State::Settle, 0);
            }

            const uint16_t target = cooldownDacTarget(tempK, coolingRate);
            return buildOutput(State::FineCooldown, target);
        }

        // ---- Overshoot -------------------------------------------------
        case State::Overshoot:
            // DAC stays at 0; wait for temperature to rise back into band
            if (inBand(tempK)) {
                enterState(State::Settle, nowMs);
                return buildOutput(State::Settle, 0);
            }
            return buildOutput(State::Overshoot, 0);

        // ---- Settle ----------------------------------------------------
        case State::Settle: {
            const bool stable = inBand(tempK);

            if (!stable) {
                // Drifted out of band -- reset timer
                settleTimerActive = false;
                settleStartMs     = 0;
            } else {
                if (!settleTimerActive) {
                    settleTimerActive = true;
                    settleStartMs     = nowMs;
                } else if ((nowMs - settleStartMs) >= SETTLE_DURATION_MS) {
                    enterState(State::Baseline, nowMs);
                    return buildOutput(State::Baseline, 0);
                }
            }
            return buildOutput(State::Settle, 0);
        }

        // ---- Baseline --------------------------------------------------
        case State::Baseline:
            if (elapsed >= BASELINE_DURATION_MS) {
                enterState(State::Operating, nowMs);
                return buildOutput(State::Operating, 0);
            }
            return buildOutput(State::Baseline, 0);

        // ---- Operating -------------------------------------------------
        case State::Operating:
            return buildOutput(State::Operating, 0);

        // ---- Fault (terminal) ------------------------------------------
        case State::Fault:
            if (offStateMs == 0) {
                offStateMs = nowMs;
            }
            return buildOutput(State::Fault, 0);
    }

    // Unreachable -- satisfy the compiler
    return buildOutput(State::Fault, 0);
}

State getState() {
    return currentState;
}

bool isRunning() {
    return running;
}

uint32_t getOnStateDuration(){
    // If its not currently on, then return falsey
    if (onStateMs == 0) return 0;

    // If its currently off (determined by if it has a stop time), then return
    // the difference between the stop time and the start time
    if (offStateMs != 0) return offStateMs - onStateMs;

    // No off state ms means its currently running. So get the time since it started.
    return millis() - onStateMs;
}

void start(uint32_t nowMs, float tempK) {
    if (running == true) return;
    running          = true;
    onStateMs        = nowMs;
    offStateMs       = 0;
    faultReason      = FaultReason::None;
    backoffCount     = 0;
    backoffDacOffset = 0;

    // Select the resumption state based on current cold-stage temperature.
    // This lets the system pick up where it left off after a reboot without
    // entering a cooldown state that would trigger a spurious stall fault.
    if (tempK >= COARSE_FINE_THRESHOLD_K) {
        // Warm start (or unknown temp): begin full cooldown sequence.
        enterState(State::CoarseCooldown, nowMs);
    } else if (overshot(tempK)) {
        // Below the setpoint tolerance band — DAC held at 0, wait to rise.
        enterState(State::Overshoot, nowMs);
    } else if (inBand(tempK)) {
        // Already within the setpoint band — skip cooldown, settle timer starts.
        enterState(State::Settle, nowMs);
    } else {
        // Below the coarse/fine threshold but above the setpoint band.
        enterState(State::FineCooldown, nowMs);
    }
}

void stop(uint32_t nowMs) {
    if (running == false) return;
    running     = false;
    if (offStateMs == 0) offStateMs = nowMs;
    faultReason = FaultReason::None;
    enterState(State::Idle, nowMs);
}

void off(uint32_t nowMs) {
    if (currentState == State::Off) return;
    running     = false;
    if (offStateMs == 0) offStateMs = nowMs;
    faultReason = FaultReason::None;
    enterState(State::Off, nowMs);
}

FaultReason getFaultReason() {
    return faultReason;
}

const char* stateName(State s) {
    switch (s) {
        case State::Off:            return "Off";
        case State::Initialize:     return "Initialize";
        case State::Idle:           return "Idle";
        case State::CoarseCooldown: return "CoarseCooldown";
        case State::FineCooldown:   return "FineCooldown";
        case State::Overshoot:      return "Overshoot";
        case State::Settle:         return "Settle";
        case State::Baseline:       return "Baseline";
        case State::Operating:      return "Operating";
        case State::Fault:          return "Fault";
    }
    return "Unknown";
}

const char* getStatusText(){
    return statusTextForState(getState());
}

uint32_t getTimeInState() {
    return millis() - currentStateEntryMs;
}

} // namespace state_machine
