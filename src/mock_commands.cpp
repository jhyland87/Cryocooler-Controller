/**
 * @file mock_commands.cpp
 * @brief Serial command handler for sensor mock mode.
 *
 * Registered in commands.cpp as the handler for the "mock" keyword.
 * Subcommand parsing and output formatting live here so that commands.cpp
 * stays focused on dispatch mechanics.
 */

#ifdef ARDUINO

#include <Arduino.h>
#include <cstdlib>   // strtof
#include <cstring>   // strncmp

#include "mock_commands.h"
#include "sensor_mock.h"

namespace mock_commands {

// ─── Private helpers ──────────────────────────────────────────────────────────

/** Parse a float from s.  Returns true and sets *out on success. */
static bool parseFloat(const char* s, float* out) {
    if (s == nullptr || *s == '\0') return false;
    char* end = nullptr;
    const float v = strtof(s, &end);
    if (end == s) return false;   // no digits consumed
    *out = v;
    return true;
}

/** Parse 0 or 1 from s.  Returns true and sets *out on success. */
static bool parseBool(const char* s, bool* out) {
    if (s == nullptr) return false;
    if (*s == '0' && (*(s + 1) == '\0' || *(s + 1) == ' ')) { *out = false; return true; }
    if (*s == '1' && (*(s + 1) == '\0' || *(s + 1) == ' ')) { *out = true;  return true; }
    return false;
}

/**
 * Skip leading whitespace and return a pointer to the first non-space
 * character in s, or nullptr if s is null.
 */
static const char* skipWs(const char* s) {
    if (s == nullptr) return nullptr;
    while (*s == ' ' || *s == '\t') ++s;
    return s;
}

// ─── Ramp sub-handler ─────────────────────────────────────────────────────────

/**
 * Handle: mock ramp [stop [<field>] | <field> <start> <end> <rate>]
 *
 * Examples:
 *   mock ramp temp 300 77 3.5        -- cool from 300 K to 77 K at 3.5 K/min
 *   mock ramp rms  0 1.5 0.05        -- ramp RMS voltage up
 *   mock ramp voltage 24 10 1.0      -- ramp supply voltage down
 *   mock ramp stop                   -- cancel all ramps
 *   mock ramp stop temp              -- cancel temp ramp only
 */
static void handleRamp(const char* args, Print& out) {
    args = skipWs(args);
    if (args == nullptr || *args == '\0') {
        // Print ramp status
        const char* const fieldNames[] = { "temp", "rms", "voltage" };
        bool anyActive = false;
        for (uint8_t i = 0; i < static_cast<uint8_t>(sensor_mock::RampField::Count); ++i) {
            const auto& r = sensor_mock::getRamp(static_cast<sensor_mock::RampField>(i));
            if (r.active) {
                anyActive = true;
                char buf[80];
                snprintf(buf, sizeof(buf),
                         "  ramp %-8s: %.3f -> %.3f  @ %.3f /min",
                         fieldNames[i], r.startVal, r.endVal, r.ratePerMin);
                out.println(buf);
            }
        }
        if (!anyActive) out.println("  No active ramps.");
        return;
    }

    // ── stop [field] ──────────────────────────────────────────────────────────
    if (strncmp(args, "stop", 4) == 0 && (args[4] == '\0' || args[4] == ' ' || args[4] == '\t')) {
        const char* field = skipWs(args + 4);
        if (field == nullptr || *field == '\0') {
            sensor_mock::stopAllRamps();
            out.println("[OK] All ramps stopped");
        } else if (strncmp(field, "temp",    4) == 0) {
            sensor_mock::stopRamp(sensor_mock::RampField::Temp);
            out.println("[OK] Temp ramp stopped");
        } else if (strncmp(field, "rms",     3) == 0) {
            sensor_mock::stopRamp(sensor_mock::RampField::Rms);
            out.println("[OK] RMS ramp stopped");
        } else if (strncmp(field, "voltage", 7) == 0) {
            sensor_mock::stopRamp(sensor_mock::RampField::Voltage);
            out.println("[OK] Voltage ramp stopped");
        } else {
            out.println("[ERR] Unknown field. Use: temp | rms | voltage");
        }
        return;
    }

    // ── <field> <start> <end> <rate> ──────────────────────────────────────────
    sensor_mock::RampField field;
    const char* rest = nullptr;

    if (strncmp(args, "temp",    4) == 0 && (args[4] == ' ' || args[4] == '\t')) {
        field = sensor_mock::RampField::Temp;
        rest  = skipWs(args + 5);
    } else if (strncmp(args, "rms",  3) == 0 && (args[3] == ' ' || args[3] == '\t')) {
        field = sensor_mock::RampField::Rms;
        rest  = skipWs(args + 4);
    } else if (strncmp(args, "voltage", 7) == 0 && (args[7] == ' ' || args[7] == '\t')) {
        field = sensor_mock::RampField::Voltage;
        rest  = skipWs(args + 8);
    } else {
        out.println("[ERR] Usage: mock ramp <temp|rms|voltage> <start> <end> <rate/min>");
        out.println("      or:    mock ramp stop [temp|rms|voltage]");
        return;
    }

    // Parse three floats: start, end, rate
    float startVal = 0.0f, endVal = 0.0f, ratePerMin = 0.0f;
    char* endPtr = nullptr;

    if (rest == nullptr || *rest == '\0') goto bad_args;
    startVal = strtof(rest, &endPtr);
    if (endPtr == rest) goto bad_args;

    rest = skipWs(endPtr);
    if (rest == nullptr || *rest == '\0') goto bad_args;
    endVal = strtof(rest, &endPtr);
    if (endPtr == rest) goto bad_args;

    rest = skipWs(endPtr);
    if (rest == nullptr || *rest == '\0') goto bad_args;
    ratePerMin = strtof(rest, &endPtr);
    if (endPtr == rest) goto bad_args;

    if (ratePerMin <= 0.0f) {
        out.println("[ERR] Rate must be > 0 (direction is derived from start/end values)");
        return;
    }

    sensor_mock::startRamp(field, startVal, endVal, ratePerMin, millis());

    {
        const char* fieldName = (field == sensor_mock::RampField::Temp)    ? "temp"
                              : (field == sensor_mock::RampField::Rms)     ? "rms"
                                                                           : "voltage";
        const char* units     = (field == sensor_mock::RampField::Temp)    ? "K"
                              : "V";
        char buf[80];
        snprintf(buf, sizeof(buf),
                 "[OK] Ramp started: %s  %.3f %s -> %.3f %s  @ %.3f /min",
                 fieldName, startVal, units, endVal, units, ratePerMin);
        out.println(buf);
    }
    return;

bad_args:
    out.println("[ERR] Usage: mock ramp <temp|rms|voltage> <start> <end> <rate/min>");
    out.println("  e.g.  mock ramp temp 300 77 3.5");
    out.println("  e.g.  mock ramp voltage 24 10 1.0");
}

// ─── Public handler ───────────────────────────────────────────────────────────

void handleMock(const char* args, Print& out) {
    // Strip leading whitespace.
    while (*args == ' ' || *args == '\t') ++args;

    sensor_mock::Overrides& mo = sensor_mock::get();

    // ── enable ───────────────────────────────────────────────────────────────
    if (strncmp(args, "enable", 6) == 0 && (args[6] == '\0' || args[6] == ' ')) {
        sensor_mock::enable();
        out.println("[OK] Mock mode enabled — hardware reads bypassed");
        return;
    }

    // ── disable ──────────────────────────────────────────────────────────────
    if (strncmp(args, "disable", 7) == 0 && (args[7] == '\0' || args[7] == ' ')) {
        sensor_mock::disable();
        out.println("[OK] Mock mode disabled — using real hardware");
        return;
    }

    // ── ramp ... ─────────────────────────────────────────────────────────────
    if (strncmp(args, "ramp", 4) == 0 && (args[4] == '\0' || args[4] == ' ' || args[4] == '\t')) {
        handleRamp(args + 4, out);
        return;
    }

    // ── temp <K> ─────────────────────────────────────────────────────────────
    if (strncmp(args, "temp", 4) == 0 && (args[4] == ' ' || args[4] == '\t')) {
        float v;
        if (!parseFloat(args + 5, &v)) {
            out.println("[ERR] Usage: mock temp <K>  (e.g. mock temp 85.5)");
            return;
        }
        // Cancel any active temp ramp so the static value is not overwritten
        // next tick.
        sensor_mock::stopRamp(sensor_mock::RampField::Temp);
        mo.tempK = v;
        char buf[56];
        snprintf(buf, sizeof(buf), "[OK] mock.temp = %.3f K  (%.3f C)", v, v - 273.15f);
        out.println(buf);
        return;
    }

    // ── rate <K/min> ─────────────────────────────────────────────────────────
    if (strncmp(args, "rate", 4) == 0 && (args[4] == ' ' || args[4] == '\t')) {
        float v;
        if (!parseFloat(args + 5, &v)) {
            out.println("[ERR] Usage: mock rate <K/min>  (e.g. mock rate -1.5)");
            return;
        }
        mo.coolingRate = v;
        char buf[48];
        snprintf(buf, sizeof(buf), "[OK] mock.rate = %.3f K/min", v);
        out.println(buf);
        return;
    }

    // ── rms <V> ──────────────────────────────────────────────────────────────
    if (strncmp(args, "rms", 3) == 0 && (args[3] == ' ' || args[3] == '\t')) {
        float v;
        if (!parseFloat(args + 4, &v)) {
            out.println("[ERR] Usage: mock rms <V>  (e.g. mock rms 1.2)");
            return;
        }
        sensor_mock::stopRamp(sensor_mock::RampField::Rms);
        mo.rmsVoltageV = v;
        char buf[48];
        snprintf(buf, sizeof(buf), "[OK] mock.rms = %.3f V", v);
        out.println(buf);
        return;
    }

    // ── current <A> ──────────────────────────────────────────────────────────
    if (strncmp(args, "current", 7) == 0 && (args[7] == ' ' || args[7] == '\t')) {
        float v;
        if (!parseFloat(args + 8, &v)) {
            out.println("[ERR] Usage: mock current <A>  (e.g. mock current 2.5)");
            return;
        }
        mo.currentA = v;
        char buf[48];
        snprintf(buf, sizeof(buf), "[OK] mock.current = %.3f A", v);
        out.println(buf);
        return;
    }

    // ── voltage <V> ──────────────────────────────────────────────────────────
    if (strncmp(args, "voltage", 7) == 0 && (args[7] == ' ' || args[7] == '\t')) {
        float v;
        if (!parseFloat(args + 8, &v)) {
            out.println("[ERR] Usage: mock voltage <V>  (e.g. mock voltage 12.0)");
            return;
        }
        sensor_mock::stopRamp(sensor_mock::RampField::Voltage);
        mo.voltageV = v;
        char buf[48];
        snprintf(buf, sizeof(buf), "[OK] mock.voltage = %.3f V", v);
        out.println(buf);
        return;
    }

    // ── stall <0|1> ──────────────────────────────────────────────────────────
    if (strncmp(args, "stall", 5) == 0 && (args[5] == ' ' || args[5] == '\t')) {
        bool v;
        if (!parseBool(args + 6, &v)) {
            out.println("[ERR] Usage: mock stall <0|1>");
            return;
        }
        mo.stalled = v;
        char buf[40];
        snprintf(buf, sizeof(buf), "[OK] mock.stall = %d", static_cast<int>(v));
        out.println(buf);
        return;
    }

    // ── stroke <0|1> ─────────────────────────────────────────────────────────
    if (strncmp(args, "stroke", 6) == 0 && (args[6] == ' ' || args[6] == '\t')) {
        bool v;
        if (!parseBool(args + 7, &v)) {
            out.println("[ERR] Usage: mock stroke <0|1>");
            return;
        }
        mo.overstroke = v;
        char buf[40];
        snprintf(buf, sizeof(buf), "[OK] mock.stroke = %d", static_cast<int>(v));
        out.println(buf);
        return;
    }

    // ── status (default / no subcommand) ─────────────────────────────────────
    char buf[80];
    out.println(sensor_mock::isActive()
                    ? "[OK] Mock mode: ACTIVE"
                    : "[OK] Mock mode: inactive (real hardware)");
    snprintf(buf, sizeof(buf), "  temp     : %.3f K  (%.3f C)", mo.tempK, mo.tempK - 273.15f);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  rate     : %.3f K/min", mo.coolingRate);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  rms      : %.3f V", mo.rmsVoltageV);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  current  : %.3f A", mo.currentA);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  voltage  : %.3f V", mo.voltageV);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  stall    : %s", mo.stalled    ? "true" : "false");
    out.println(buf);
    snprintf(buf, sizeof(buf), "  stroke   : %s", mo.overstroke ? "true" : "false");
    out.println(buf);

    // Show active ramps as part of status
    const char* const fieldNames[] = { "temp", "rms", "voltage" };
    for (uint8_t i = 0; i < static_cast<uint8_t>(sensor_mock::RampField::Count); ++i) {
        const auto& r = sensor_mock::getRamp(static_cast<sensor_mock::RampField>(i));
        if (r.active) {
            snprintf(buf, sizeof(buf),
                     "  ramp %-8s: %.3f -> %.3f  @ %.3f /min",
                     fieldNames[i], r.startVal, r.endVal, r.ratePerMin);
            out.println(buf);
        }
    }
}

} // namespace mock_commands

#endif // ARDUINO
