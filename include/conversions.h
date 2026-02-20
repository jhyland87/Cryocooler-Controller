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

namespace conversions {

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
 * Convert Celsius to Kelvin.
 */
inline float celsiusToKelvin(float tempC) {
    return tempC + 273.15f;
}

/**
 * Convert Fahrenheit to Celsius.
 */
inline float fahrenheitToCelsius(float tempF) {
    return (tempF - 32.0f) * 5.0f / 9.0f;
}

/**
 * Map a temperature in Kelvin to a 12-bit DAC output value.
 *
 * The DAC output is 0 when the temperature is at or above @p ambientK
 * (the warm / start-of-cooldown reference) and rises linearly to @p maxDac
 * when the temperature reaches @p setpointK.  Values are clamped to [0, maxDac].
 *
 * This function is pure math with no Arduino or hardware dependencies, making
 * it safe to call from native unit tests.
 *
 * @param tempK      Current temperature in Kelvin
 * @param ambientK   Reference "warm" temperature (DAC = 0 here)
 * @param setpointK  Target cold temperature (DAC = maxDac here)
 * @param maxDac     Maximum DAC output value (e.g. 4095 for 12-bit)
 * @return           Proportional DAC value clamped to [0, maxDac]
 */
inline uint16_t tempKToDacValue(float tempK,
                                float ambientK,
                                float setpointK,
                                uint16_t maxDac)
{
    if (tempK >= ambientK)   return 0;
    if (tempK <= setpointK)  return maxDac;

    const float span     = ambientK - setpointK;
    const float dropped  = ambientK - tempK;
    const float fraction = dropped / span;

    // Cast via int32 to avoid undefined behaviour on negative fraction edge
    auto raw = static_cast<int32_t>(fraction * static_cast<float>(maxDac));
    if (raw < 0)                         return 0;
    if (raw > static_cast<int32_t>(maxDac)) return maxDac;
    return static_cast<uint16_t>(raw);
}

} // namespace conversions

#endif // CONVERSIONS_H
