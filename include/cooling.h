/**
 * @file cooling.h
 * @brief For manaing the water recirculation and fans
 */

#ifndef COOLING_H
#define COOLING_H

#include <stdint.h>
#include "module.h"
#include "tracking.h"

namespace cooling {

/**
 * Initialize the cooling system.
 * @return MODULE_INIT_SUCCESS always.
 */
module::InitStatus init();

/**
 * Periodic cooling-system tick.
 * @return SERVICE_OK      — ran and updated state normally.
 *         SERVICE_SKIPPED — called before the check interval elapsed.
 */
module::ServiceStatus service();

bool isCoolingPumpOn();

bool isCoolingFanOn();

float getCoolantTemperature();

float getCoolantFlowRate();

uint8_t getFanSpeed();


void setFanSpeed(uint8_t speedPercentage, bool force = false);
uint16_t getFanRPM();

uint8_t  getPumpSpeed();
uint16_t getPumpRPM();
void enable();
void disable();
bool isEnabled();

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

/**
 * Fan duty-cycle tracking score (forced/manual mode only).
 * 1.0 = actual duty cycle matches the requested speed exactly.
 * 0.0 = error >= COOLING_FAN_TRACK_FULL_SCALE_PCT.
 * Always 1.0 while the IC's LUT is in control (no explicit setpoint).
 */
float getFanSpeedScore();

/** Current state of the fan speed tracking monitor. */
TrackingMonitor<float>::State getFanSpeedTrackingState();

/**
 * Coolant temperature tracking score.
 * 1.0 = coolant is at COOLING_COOLANT_NOMINAL_TEMP_C.
 * 0.0 = deviation >= COOLING_COOLANT_TRACK_FULL_SCALE_C.
 * Always 1.0 while the coolant temperature sensor is not connected (= 0).
 */
float getCoolantTempScore();

/** Current state of the coolant temperature tracking monitor. */
TrackingMonitor<float>::State getCoolantTempTrackingState();

/**
 * Coolant flow rate tracking score.
 * 1.0 = flow rate matches COOLING_FLOW_NOMINAL_LPM.
 * 0.0 = deviation >= COOLING_FLOW_TRACK_FULL_SCALE_LPM.
 * Always 1.0 while the pump is off or the flow sensor is not connected.
 */
float getCoolantFlowScore();

/** Current state of the coolant flow rate tracking monitor. */
TrackingMonitor<float>::State getCoolantFlowTrackingState();

/**
 * Return the worst (lowest) tracking score across all three cooling monitors.
 * Useful for a single at-a-glance health check by the state machine.
 */
float getWorstTrackingScore();

/** Return the worst (highest severity) state across all three cooling monitors. */
TrackingMonitor<float>::State getWorstTrackingState();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = cooling::init(); }
    static module::ServiceStatus service() { return _serviceStatus = cooling::service(); }
    static void enable()                   { cooling::enable(); }
    static void disable()                  { cooling::disable(); }
    static bool isEnabled()                { return cooling::isEnabled(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace cooling

#endif // COOLING_H
