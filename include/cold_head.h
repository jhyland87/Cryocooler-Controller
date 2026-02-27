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

namespace cold_head {

/**
 * Initialize the MAX31865 RTD sensor.
 * Prints a diagnostic message to Serial.
 * @return MODULE_INIT_SUCCESS if begin() succeeds, MODULE_INIT_HARDWARE_ERROR otherwise.
 */
module::InitStatus init();

/**
 * Read RTD resistance and temperature from hardware.
 * Stores the result internally and prints to Serial.
 * Must be called periodically (every LOOP_INTERVAL_MS).
 *
 * @param nowMs  Current millis() value (injected for testability)
 */
void read(uint32_t nowMs);

float readAmbientTemperature();

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
    static module::InitStatus init() { return cold_head::init(); }
    /** Calls temperature::read(millis()) — must be called every loop tick. */
    static module::ServiceStatus service() { cold_head::read(millis()); return module::MODULE_SERVICE_OK; }
};

ASSERT_MODULE_INTERFACE(Module);
#endif // ARDUINO

} // namespace cold_head

#endif // COLD_HEAD_H
