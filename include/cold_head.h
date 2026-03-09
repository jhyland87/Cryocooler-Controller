/**
 * @file cold_head.h
 * @brief Cold-head temperature sensor interface
 *
 * Manages the MAX31865 RTD sensor connected to the cold head.
 */

#ifndef COLD_HEAD_H
#define COLD_HEAD_H

#include <stdint.h>
#include "module.h"
#include "tracking.h"

namespace cold_head {

/**
 * Initialize the MAX31865 RTD sensor.
 * Prints a diagnostic message to Serial.
 * @return MODULE_INIT_SUCCESS if begin() succeeds, MODULE_INIT_HARDWARE_ERROR otherwise.
 */
module::InitStatus init();
module::InitStatus initACS();
module::InitStatus initRTD();

/**
 * Read RTD resistance and temperature from hardware.
 * Stores the result internally and prints to Serial.
 * Must be called periodically (every LOOP_INTERVAL_MS).
 *
 * @param nowMs  Current millis() value (injected for testability)
 */
void read(uint32_t nowMs);

inline void read() { read(millis()); }
/**
 * Inject mock sensor readings directly into the module's cached state without
 * touching any hardware.  Call every control tick instead of read() when the
 * sensor is not physically present (e.g. hardware-free FSM testing).
 *
 * After this call, getLastTempK(), getCoolingRateKPerMin(), and isStalled()
 * all return the injected values until the next real read() is called.
 *
 * @param nowMs              Current millis() (used to timestamp the sample)
 * @param tempK              Cold-stage temperature in Kelvin
 * @param coolingRateKPerMin Cooling rate in K/min (negative = cooling)
 * @param stalled            True if the stage should appear stalled
 */
void setLastReadings(uint32_t nowMs, float tempK,
                     float coolingRateKPerMin, bool stalled, float rmsVoltageV, float rmsCurrentA);

//float readAmbientTemperature();

/**
 * Return the most recently measured ambient temperature in Celsius.
 * Returns 0.0f before the first successful read.
 */
float getLastAmbientTempC();

float getLastTempCBelowAmbient();


/**
 * Check for MAX31865 fault conditions and report via Serial.
 * Clears the fault register after reading.
 */
void checkFaults();

/**
 * Return true if the most recent read() detected a sensor fault:
 * either the MAX31865 hardware fault register was non-zero, or the
 * computed temperature was outside [MIN_PLAUSIBLE_TEMP_K, MAX_PLAUSIBLE_TEMP_K].
 *
 * The flag self-clears as soon as a clean, in-range reading is obtained,
 * but the state machine latches into Fault state until clearFault() is called.
 */
bool hasSensorFault();

/**
 * Return the most recently measured temperature in Kelvin.
 * Returns 0.0f before the first successful read.
 */
float getLastTempK();

/**
 * Return the most recently measured temperature in Celsius.
 * Returns 0.0f before the first successful read.
 */
float getLastTempC();

/**
 * Return the current cooling rate in Kelvin per minute (positive = cooling).
 * Computed over the oldest and newest samples in the ring buffer.
 * Returns 0.0f if fewer than 2 samples are available.
 */
float getCoolingRateKPerMin();

float getLastRmsVoltage();

float getLastRmsCurrent();

/**
 * Return true if the temperature has stalled: the cold stage has not dropped
 * by STALL_MIN_DROP_K within the most recent STALL_DETECT_WINDOW_MS.
 *
 * Only meaningful during cool-down states -- the caller (state machine)
 * is responsible for checking this only when actively cooling.
 */
bool isStalled();

/**
 * Return the temperature as a percentage of the maximum temperature.
 * 0% = 298K, 100% = 78K
 */
float getTemperatureToPercent();

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

/**
 * Set the temperature the system is currently trying to reach.
 * Should be called by the state machine whenever the target changes
 * (e.g. CoarseCooldown → FineCooldown → Settle).
 *
 * Resets the tracking timer when the new target differs from the current
 * one by more than the hysteresis band, so the monitor does not inherit
 * stale elapsed time from the previous setpoint.
 *
 * @param targetK  Desired cold-stage temperature in Kelvin.
 */
void setTargetTempK(float targetK);

/**
 * Construct the temperature tracking monitor and begin tracking.
 * Must be called when the FSM enters the Operating state.
 */
void startTemperatureTracking();

/**
 * Destroy the temperature tracking monitor and stop tracking.
 * Must be called when the FSM leaves the Operating state.
 */
void stopTemperatureTracking();

/**
 * Tracking score for the cold-stage temperature.
 * 1.0 = measured temperature exactly matches the target.
 * 0.0 = error >= COLD_HEAD_TRACK_FULL_SCALE_K.
 */
float getTemperatureScore();

/**
 * Current state of the temperature tracking monitor.
 * IN_RANGE → value is within the hysteresis band.
 * WARNING  → value has been outside the band for >= COLD_HEAD_TRACK_WARNING_MS.
 * FAULT    → value has been outside the band for >= COLD_HEAD_TRACK_FAULT_MS.
 */
TrackingMonitor<float>::State getTemperatureTrackingState();

// ---------------------------------------------------------------------------
// Module-local RTD mock
//
// Enables the cold_head module to operate without a physical MAX31865 probe,
// independently of the global sensor_mock layer.  Only the temperature
// reading is faked; all other hardware (amplifier, cooling fan, relay) runs
// normally on real hardware.
//
// Typical use (probe not yet installed):
//   mock coldhead 300    — enable at 300 K (room temperature)
//   reinit               — cold_head init bypasses MAX31865 hardware
//   start                — rest of system runs normally
//   mock coldhead 85     — adjust temperature at any time, even while running
//   mock coldhead off    — disable; next reinit uses real probe
// ---------------------------------------------------------------------------

/**
 * Enable the module-local RTD mock.
 *
 * While active, init() skips all MAX31865 hardware access and succeeds
 * immediately, and read() returns @p tempK instead of a real RTD reading.
 * The global sensor_mock layer takes precedence if it is also active.
 *
 * Safe to call at any time; takes effect on the next read() tick.
 * Changing the temperature while running is allowed and takes effect
 * immediately without requiring a reinit.
 *
 * @param tempK  Temperature to report in Kelvin.  Defaults to 300 K.
 */
void enableMock(float tempK = 300.0f);

/**
 * Disable the module-local RTD mock.
 * Takes full effect after the next reinit() — init() will attempt to
 * communicate with the real MAX31865 hardware.
 */
void disableMock();

/** Returns true while the module-local RTD mock is active. */
bool isMockEnabled();

// ── Module interface ──────────────────────────────────────────────────────────
//
// read() accepts a nowMs argument so cooling-rate history is correctly
// timestamped and remains directly testable on native builds with injected
// time values.
//
// Module::service() samples millis() internally, which is correct for the
// Arduino loop() context.  Guarded by #ifdef ARDUINO because millis() is not
// available in native (host) unit-test builds — those call read(nowMs) directly.

#ifdef ARDUINO
struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = cold_head::init(); }
    /** Calls temperature::read(millis()) — must be called every loop tick. */
    static module::ServiceStatus service() { cold_head::read(millis()); return _serviceStatus = module::MODULE_SERVICE_OK; }
};

ASSERT_MODULE_INTERFACE(Module);
#endif // ARDUINO

} // namespace cold_head

#endif // COLD_HEAD_H
