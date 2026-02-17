/**
 * @file conversions.h
 * @brief Pure math / conversion utilities (no hardware dependencies)
 *
 * These functions are free of Arduino or peripheral includes so they
 * can be compiled and unit-tested natively on the host PC.
 */

#ifndef CONVERSIONS_H
#define CONVERSIONS_H

#include <stdint.h>

/**
 * Convert a raw 15-bit RTD register value to resistance (ohms).
 *
 * @param rtdRaw  Raw 15-bit value from MAX31865 readRTD()
 * @param rRef    Reference resistor value (e.g. 435.3 for PT100)
 * @return        Measured resistance in ohms
 */
inline float rtdRawToResistance(uint16_t rtdRaw, float rRef) {
  return rRef * (static_cast<float>(rtdRaw) / 32768.0f);
}

/**
 * Convert Celsius to Fahrenheit.
 */
inline float celsiusToFahrenheit(float tempC) {
  return tempC * 9.0f / 5.0f + 32.0f;
}

/**
 * Convert Fahrenheit to Celsius.
 */
inline float fahrenheitToCelsius(float tempF) {
  return (tempF - 32.0f) * 5.0f / 9.0f;
}

#endif // CONVERSIONS_H
