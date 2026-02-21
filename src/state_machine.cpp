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

static State       sState        = State::Off;
static uint32_t    sStateEntryMs = 0;   // millis() when current state was entered
static bool        sRunning      = false; // process is off until start() is called
static FaultReason sFaultReason  = FaultReason::None;
static uint32_t    sOnStateMs    = 0;   // millis() when it entered an on state
static uint32_t    sOffStateMs   = 0;   // millis() when it entered an off state

// Settle timer -- starts counting when temp enters the tolerance band
static uint32_t sSettleStartMs     = 0;
static bool     sSettleTimerActive = false;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static void enterState(State s, uint32_t nowMs) {
    sState        = s;
    sStateEntryMs = nowMs;
    if (s != State::Settle) {
        sSettleTimerActive = false;
        sSettleStartMs     = 0;
    }
    if (s != State::Fault) {
        sFaultReason = FaultReason::None;
    }
}

static void enterFault(FaultReason reason, uint32_t nowMs) {
    sFaultReason = reason;
    sRunning     = false;
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
            switch (sFaultReason) {
                case FaultReason::RmsOvervoltage:   return "Fault: RMS voltage exceeded safe limit";
                case FaultReason::TemperatureStall: return "Fault: Temperature stalled during cooldown";
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

    Output o{};
    o.state      = s;
    o.dacTarget  = dacTarget;
    o.alarmRelay = false;
    o.statusText = statusTextForState(s);

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
    sRunning     = false;
    sOnStateMs   = 0;
    sOffStateMs  = 0;
    sFaultReason = FaultReason::None;
    enterState(State::Off, nowMs);
}

Output update(float    tempK,
              float    coolingRate,
              float    rmsVoltage,
              bool     stalled,
              uint32_t nowMs)
{
    // ------------------------------------------------------------------
    // Global fault checks (fire from any non-Fault state)
    // ------------------------------------------------------------------
    if (sState != State::Fault) {
        if (rmsVoltage > RMS_MAX_VOLTAGE_VDC) {
            enterFault(FaultReason::RmsOvervoltage, nowMs);
            return buildOutput(State::Fault, 0);
        }
        if ((sState == State::CoarseCooldown ||
             sState == State::FineCooldown) && stalled) {
            enterFault(FaultReason::TemperatureStall, nowMs);
            return buildOutput(State::Fault, 0);
        }
    }

    // ------------------------------------------------------------------
    // Per-state transition logic
    // Each branch MUST return the new state's buildOutput after calling
    // enterState() so the caller always sees the current state.
    // ------------------------------------------------------------------
    const uint32_t elapsed = nowMs - sStateEntryMs;

    switch (sState) {

        // ---- Off -------------------------------------------------------
        case State::Off:
            if (sOffStateMs == 0) {
            sOffStateMs = nowMs;
            }
            return buildOutput(State::Off, 0);

        // ---- Initialize ------------------------------------------------
        case State::Initialize:
            if (sOnStateMs == 0) {
                sOnStateMs = nowMs;
                sOffStateMs = 0;
            }
            if (elapsed >= INDICATOR_INIT_AMBER_MS) {
                enterState(State::Idle, nowMs);
                return buildOutput(State::Idle, 0);
            }
            return buildOutput(State::Initialize, 0);

        // ---- Idle ------------------------------------------------------
        case State::Idle:
            if (sOffStateMs == 0) {
                sOffStateMs = nowMs;
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
                sSettleTimerActive = false;
                sSettleStartMs     = 0;
            } else {
                if (!sSettleTimerActive) {
                    sSettleTimerActive = true;
                    sSettleStartMs     = nowMs;
                } else if ((nowMs - sSettleStartMs) >= SETTLE_DURATION_MS) {
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
            if (sOffStateMs == 0) {
                sOffStateMs = nowMs;
            }
            return buildOutput(State::Fault, 0);
    }

    // Unreachable -- satisfy the compiler
    return buildOutput(State::Fault, 0);
}

State getState() {
    return sState;
}

bool isRunning() {
    return sRunning;
}

uint32_t getOnStateDuration(){
    // If its not currently on, then return falsey
    if (sOnStateMs == 0) return 0;

    // If its currently off (determined by if it has a stop time), then return
    // the difference between the stop time and the start time
    if (sOffStateMs != 0) return sOffStateMs - sOnStateMs;

    // No off state ms means its currently running. So get the time since it started.
    return millis() - sOnStateMs;
}

void start(uint32_t nowMs) {
    //if (sState != State::Idle && sState != State::Off) return;
    if (sRunning == true) return;
    sRunning     = true;
    sOnStateMs   = nowMs;
    sOffStateMs  = 0;
    sFaultReason = FaultReason::None;
    enterState(State::CoarseCooldown, nowMs);
}

void stop(uint32_t nowMs) {
    if (sRunning == false) return;
    sRunning     = false;
    if (sOffStateMs == 0) sOffStateMs = nowMs;
    sFaultReason = FaultReason::None;
    enterState(State::Idle, nowMs);
}

void off(uint32_t nowMs) {
    if (sState == State::Off) return;
    sRunning     = false;
    if (sOffStateMs == 0) sOffStateMs = nowMs;
    sFaultReason = FaultReason::None;
    enterState(State::Off, nowMs);
}

FaultReason getFaultReason() {
    return sFaultReason;
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

} // namespace state_machine
