/**
 * @file temperature.h
 * @brief MAX31865 RTD temperature sensor interface
 */

#ifndef TEMPERATURE_H
#define TEMPERATURE_H

#include <Adafruit_MAX31865.h>

namespace temperature {
/**
 * Initialize the MAX31865 RTD sensor.
 * Halts execution if the sensor cannot be reached.
 */
void init();

/**
 * Read RTD resistance and temperature, print results to Serial.
 */
void read();

/**
 * Check for MAX31865 fault conditions and report via Serial.
 */
void checkFaults();
} // namespace temperature

#endif // TEMPERATURE_H
