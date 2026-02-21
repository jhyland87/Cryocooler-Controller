/**
 * @file state_machine.h
 * @brief Cryocooler system state machine
 *
 * Implements the nine-state control sequence:
 *
 *   0  Initialize   - Power-up: AMBER flash, relay Bypass, DAC = 0
 *   1  Idle         - Warm / standby: FAULT RED, relay Bypass, DAC = 0
 *   2  CoarseCooldown - Cooling above 85 K: FAULT flash fast RED, ramp DAC
 *   3  FineCooldown   - Cooling below 85 K: + READY flash slow GREEN
 *   4  Overshoot      - Below setpoint, integrator settling: READY flash fast GREEN
 *   5  Settle         - Near setpoint, Normal relay engaged
 *   6  Baseline       - Collecting baseline: READY ON GREEN
 *   7  Operating      - Normal run: READY ON GREEN
 *   8  Fault          - Any fault condition: FAULT ON RED, alarm relay active
 *
 * Transition inputs on every update() call:
 *   - tempK          : current cold-stage temperature in Kelvin
 *   - coolingRate    : K/min (positive = cooling)
 *   - rmsVoltage     : measured RMS voltage (stub; 0.0 until implemented)
 *   - stalled        : true when temp has not dropped enough in STALL_DETECT_WINDOW_MS
 *   - nowMs          : current millis()
 *
 * The module is pure logic — no Serial or hardware calls — so it can be
 * unit-tested on the native (host-PC) platform.
 */

#ifndef STATE_MACHINE_H
#define STATE_MACHINE_H

#include <stdint.h>
#include "indicator.h"

namespace state_machine {

/** System states as per design spec. */
enum class State : int8_t {
    Off             = -1,
    Initialize      = 0,
    Idle            = 1,
    CoarseCooldown  = 2,
    FineCooldown    = 3,
    Overshoot       = 4,
    Settle          = 5,
    Baseline        = 6,
    Operating       = 7,
    Fault           = 8
};


/** Reason the system entered Fault state. */
enum class FaultReason : uint8_t {
    None              = 0,
    RmsOvervoltage    = 1,
    TemperatureStall  = 2,
};

/** Aggregate output produced by update() each loop. */
struct Output {
    State            state;
    uint16_t         dacTarget;       ///< desired DAC value (before ramp limiting)
    bool             bypassRelay;     ///< true = Bypass, false = Normal
    bool             alarmRelay;      ///< true = alarm relay energised (Fault state)
    indicator::Mode  faultIndMode;    ///< desired mode for FAULT indicator
    indicator::Mode  readyIndMode;    ///< desired mode for READY indicator
    const char*      statusText;      ///< human-readable status description
};

/**
 * Initialise the state machine.
 * Must be called once in setup() with the current millis().
 *
 * @param nowMs  Current millis()
 */
void init(uint32_t nowMs);

/** Return the duration of the current on state in milliseconds. */
uint32_t getOnStateDuration();

/**
 * Advance the state machine by one tick.
 *
 * @param tempK        Current cold-stage temperature in Kelvin
 * @param coolingRate  Measured cooling rate in K/min (positive = cooling)
 * @param rmsVoltage   Measured RMS voltage in VDC (stub returns 0)
 * @param stalled      True when stall-detection window has expired without a
 *                     sufficient temperature drop
 * @param nowMs        Current millis()
 * @return             Output struct with all actuator targets for this tick
 */
Output update(float    tempK,
              float    coolingRate,
              float    rmsVoltage,
              bool     stalled,
              uint32_t nowMs);

/** Return the current state without advancing the machine. */
State getState();

/** Return true if the process has been started and is actively running. */
bool isRunning();

/**
 * Start the cooldown process.
 * Transitions from Idle → CoarseCooldown.  Has no effect if the machine
 * is not in the Idle state (e.g. already running, or in Fault).
 *
 * @param nowMs  Current millis()
 */
void start(uint32_t nowMs);

/**
 * Stop the cooldown process and return to Idle.
 * DAC target drops to 0, relay returns to Bypass.
 * Has no effect during Initialize.  When called from Fault the machine
 * is reset to Idle (fault is cleared).
 *
 * @param nowMs  Current millis()
 */
void stop(uint32_t nowMs);

void off(uint32_t nowMs);

/** Return a short ASCII name for a state (safe for Serial / telemetry). */
const char* stateName(State s);

/** Return the current fault reason (FaultReason::None if not in Fault). */
FaultReason getFaultReason();

/** Return a short ASCII status text for the current state (safe for Serial / telemetry). */
const char* getStatusText();

/**
 * Return how long the machine has been in its current state, in milliseconds.
 * The counter resets to zero on every state transition.
 */
uint32_t getTimeInState();

} // namespace state_machine

#endif // STATE_MACHINE_H
