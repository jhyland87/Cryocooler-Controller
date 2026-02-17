/**
 * @file temperature.h
 * @brief MAX31865 RTD temperature sensor interface
 */

#ifndef TEMPERATURE_H
#define TEMPERATURE_H

#include <Adafruit_MAX31865.h>

/**
 * Initialize the MAX31865 RTD sensor.
 * Halts execution if the sensor cannot be reached.
 */
void temperature_init();

/**
 * Read RTD resistance and temperature, print results to Serial.
 */
void temperature_read();

/**
 * Check for MAX31865 fault conditions and report via Serial.
 */
void temperature_checkFaults();

#endif // TEMPERATURE_H
