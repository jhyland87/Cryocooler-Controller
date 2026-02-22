/**
 * @file temperature.h
 * @brief MAX31865 RTD temperature sensor interface
 *
 * In addition to reading the sensor, this module maintains a rolling sample
 * history used by the state machine for:
 *   - Cooling-rate calculation (to enforce the 10 C/10 min limit)
 *   - Temperature-stall detection (fault trigger)
 *
 * This header is free of Adafruit / hardware includes and may be safely
 * included from unit tests compiled on the host PC.
 */

#ifndef TEMPERATURE_H
#define TEMPERATURE_H

#include <stdint.h>

namespace temperature {

/**
 * Initialize the MAX31865 RTD sensor.
 * Prints a diagnostic message to Serial.
 */
void init();

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

} // namespace temperature

#endif // TEMPERATURE_H
