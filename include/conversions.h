/**
 * @file conversions.h
 * @brief Pure math / conversion utilities (no hardware dependencies)
 *
 * These functions are free of Arduino or peripheral includes so they
 * can be compiled and unit-tested natively on the host PC.
 */

#ifndef CONVERSIONS_H
#define CONVERSIONS_H

#include <Arduino.h>
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

inline void msToHHMMSS(uint32_t durationMs, char* hmsBuf, size_t len)
{
    const uint32_t totalSec = durationMs / 1000u;
    const uint32_t hh       = totalSec / 3600u;
    const uint32_t mm       = (totalSec % 3600u) / 60u;
    const uint32_t ss       = totalSec % 60u;

    snprintf(hmsBuf, len, "%02lu:%02lu:%02lu",
            static_cast<unsigned long>(hh),
            static_cast<unsigned long>(mm),
            static_cast<unsigned long>(ss));
}

/**
 * Parse a human-readable duration string into milliseconds.
 *
 * Accepts any combination of h/m/s components with optional whitespace
 * between tokens.  All components are optional but at least one must be
 * present.  Unit suffixes are case-insensitive.  Examples:
 *   "1h30m0s"  "30m"  "45s"  "2h"  "1h 30m"  "0h0m30s"
 *
 * @param str     Null-terminated input string.
 * @param errOut  Receives a short error description on failure.
 * @param errLen  Size of errOut in bytes.
 * @return        Total milliseconds, or 0 on parse failure (errOut is set).
 */
inline uint32_t parseDurationMs(const char* str, char* errOut, size_t errLen) {
    uint32_t    totalMs = 0u;
    bool        found   = false;
    const char* p       = str;

    while (*p != '\0') {
        while (*p == ' ' || *p == '\t') { ++p; }
        if (*p == '\0') break;

        if (*p < '0' || *p > '9') {
            snprintf(errOut, errLen, "unexpected character '%c'", *p);
            return 0u;
        }
        uint32_t val = 0u;
        while (*p >= '0' && *p <= '9') {
            val = val * 10u + static_cast<uint32_t>(*p - '0');
            ++p;
        }

        const char unit = *p;
        if (unit == 'h' || unit == 'H') {
            totalMs += val * 3600000u;
        } else if (unit == 'm' || unit == 'M') {
            totalMs += val * 60000u;
        } else if (unit == 's' || unit == 'S') {
            totalMs += val * 1000u;
        } else {
            snprintf(errOut, errLen,
                     "unknown unit '%c' — use h, m, or s", unit ? unit : '?');
            return 0u;
        }
        found = true;
        ++p;
    }

    if (!found) {
        snprintf(errOut, errLen, "no duration components found");
        return 0u;
    }
    return totalMs;
}

/**
 * Format a millisecond count as a compact human-readable duration string.
 *
 * Produces "Xh Ym Zs" when hours > 0, or "Ym Zs" for shorter durations,
 * keeping output tidy for display in serial/TCP command responses.
 *
 * @param ms   Duration in milliseconds.
 * @param buf  Output buffer.
 * @param len  Size of buf in bytes.
 */
inline void formatDurationMs(uint32_t ms, char* buf, size_t len) {
    const uint32_t totalSec = ms / 1000u;
    const uint32_t h        = totalSec / 3600u;
    const uint32_t m        = (totalSec % 3600u) / 60u;
    const uint32_t s        = totalSec % 60u;
    if (h > 0u) {
        snprintf(buf, len, "%luh %02lum %02lus",
                 static_cast<unsigned long>(h),
                 static_cast<unsigned long>(m),
                 static_cast<unsigned long>(s));
    } else {
        snprintf(buf, len, "%lum %02lus",
                 static_cast<unsigned long>(m),
                 static_cast<unsigned long>(s));
    }
}

} // namespace conversions

#endif // CONVERSIONS_H
