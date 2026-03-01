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

    // ── temp <K> ─────────────────────────────────────────────────────────────
    if (strncmp(args, "temp", 4) == 0 && (args[4] == ' ' || args[4] == '\t')) {
        float v;
        if (!parseFloat(args + 5, &v)) {
            out.println("[ERR] Usage: mock temp <K>  (e.g. mock temp 85.5)");
            return;
        }
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
        mo.rmsVoltage = v;
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
    snprintf(buf, sizeof(buf), "  rms      : %.3f V", mo.rmsVoltage);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  current  : %.3f A", mo.currentA);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  voltage  : %.3f V", mo.voltageV);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  stall    : %s", mo.stalled    ? "true" : "false");
    out.println(buf);
    snprintf(buf, sizeof(buf), "  stroke   : %s", mo.overstroke ? "true" : "false");
    out.println(buf);
}

} // namespace mock_commands

#endif // ARDUINO
