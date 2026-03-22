/**
 * @file mock_commands.cpp
 * @brief Serial command handler for sensor mock mode.
 *
 * Registered in commands.cpp as the handler for the "mock" keyword.
 * Subcommand parsing and output formatting live here so that commands.cpp
 * stays focused on dispatch mechanics.
 *
 * Adding a new subcommand:
 *   1. Write a static handler:  static void handleFoo(const char* args, Print& out) { ... }
 *   2. Add one row to kSubCommands[] below.
 *   3. Update the doc-comment in mock_commands.h.
 */

#ifdef ARDUINO

#include <Arduino.h>
#include <cstdlib>   // strtof
#include <cstring>   // strncmp

#include "mock_commands.h"
#include "sensor_mock.h"
#include "cold_head.h"
#include "config_advanced.h"
#include "amplifier.h"
#include "compressor.h"

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

// ─── Subcommand handlers ──────────────────────────────────────────────────────
//
// Each handler receives everything *after* its keyword with leading whitespace
// already stripped.  args is never null but may be an empty string.

static void handleEnable(const char* /*args*/, Print& out) {
    sensor_mock::enable();
    out.println("[OK] Mock mode enabled — hardware reads bypassed");
}

static void handleDisable(const char* /*args*/, Print& out) {
    sensor_mock::disable();
    out.println("[OK] Mock mode disabled — using real hardware");
}

static void handleTemp(const char* args, Print& out) {
    float v;
    if (!parseFloat(args, &v)) {
        out.println("[ERR] Usage: mock temp <C>  (e.g. mock temp -188.15)");
        return;
    }
    // Cancel any active temp ramp so the static value is not overwritten next tick.
    sensor_mock::stopRamp(sensor_mock::RampField::Temp);
    sensor_mock::get().tempC = v;
    char buf[56];
    snprintf(buf, sizeof(buf), "[OK] mock.temp = %.3f C", v);
    out.println(buf);
}

static void handleRate(const char* args, Print& out) {
    float v;
    if (!parseFloat(args, &v)) {
        out.println("[ERR] Usage: mock rate <C/min>  (e.g. mock rate -1.5)");
        return;
    }
    sensor_mock::get().coolingRate = v;
    char buf[48];
    snprintf(buf, sizeof(buf), "[OK] mock.rate = %.3f K/min", v);
    out.println(buf);
}

static void handleRms(const char* args, Print& out) {
    float v;
    if (!parseFloat(args, &v)) {
        out.println("[ERR] Usage: mock rms <V>  (e.g. mock rms 1.2)");
        return;
    }
    sensor_mock::stopRamp(sensor_mock::RampField::Rms);
    sensor_mock::get().rmsVoltageV = v;
    char buf[48];
    snprintf(buf, sizeof(buf), "[OK] mock.rms = %.3f V", v);
    out.println(buf);
}

static void handleCurrent(const char* args, Print& out) {
    float v;
    if (!parseFloat(args, &v)) {
        out.println("[ERR] Usage: mock current <A>  (e.g. mock current 2.5)");
        return;
    }
    sensor_mock::get().current = v;
    char buf[48];
    snprintf(buf, sizeof(buf), "[OK] mock.current = %.3f A", v);
    out.println(buf);
}

static void handleVoltage(const char* args, Print& out) {
    float v;
    if (!parseFloat(args, &v)) {
        out.println("[ERR] Usage: mock voltage <V>  (e.g. mock voltage 12.0)");
        return;
    }
    sensor_mock::stopRamp(sensor_mock::RampField::Voltage);
    sensor_mock::get().voltage = v;
    char buf[48];
    snprintf(buf, sizeof(buf), "[OK] mock.voltage = %.3f V", v);
    out.println(buf);
}

static void handleStall(const char* args, Print& out) {
    bool v;
    if (!parseBool(args, &v)) {
        out.println("[ERR] Usage: mock stall <0|1>");
        return;
    }
    sensor_mock::get().stalled = v;
    char buf[40];
    snprintf(buf, sizeof(buf), "[OK] mock.stall = %d", static_cast<int>(v));
    out.println(buf);
}

static void handleStroke(const char* args, Print& out) {
    bool v;
    if (!parseBool(args, &v)) {
        out.println("[ERR] Usage: mock stroke <0|1>");
        return;
    }
    sensor_mock::get().overstroke = v;
    char buf[40];
    snprintf(buf, sizeof(buf), "[OK] mock.stroke = %d", static_cast<int>(v));
    out.println(buf);
}

/**
 * Handle: mock coldhead [<K> | off]
 *
 * Examples:
 *   mock coldhead        -- print cold-head mock status
 *   mock coldhead 300    -- inject 300 K into the cold-head RTD
 *   mock coldhead off    -- disable cold-head RTD mock
 */
static void handleColdhead(const char* args, Print& out) {
    if (args == nullptr || *args == '\0') {
        if (cold_head::isMockEnabled()) {
            char buf[72];
            snprintf(buf, sizeof(buf),
                     "[OK] Cold head RTD mock: ACTIVE  (%.3f C)",
                     cold_head::getLastTempC());
            out.println(buf);
        } else {
            out.println("[OK] Cold head RTD mock: inactive (real ADS122C04)");
        }
        return;
    }

    if (strncmp(args, "off", 3) == 0 &&
        (args[3] == '\0' || args[3] == ' ' || args[3] == '\t')) {
        cold_head::disableMock();
        out.println("[OK] Cold head RTD mock disabled (takes full effect after reinit)");
        return;
    }

    float v;
    if (!parseFloat(args, &v)) {
        out.println("[ERR] Usage: mock coldhead <K>  (e.g. mock coldhead 300)");
        out.println("      or:    mock coldhead off");
        return;
    }
    cold_head::enableMock(v);
    char buf[80];
    snprintf(buf, sizeof(buf),
             "[OK] Cold head RTD mock set to %.3f K (%.3f C)",
             v, v - 273.15f);
    out.println(buf);
}

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

    sensor_mock::startRamp(field, startVal, endVal, ratePerMin);

    {
        const char* fieldName = (field == sensor_mock::RampField::Temp)    ? "temp"
                              : (field == sensor_mock::RampField::Rms)     ? "rms"
                                                                           : "voltage";
        const char* units     = (field == sensor_mock::RampField::Temp)    ? "K" : "V";
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

/**
 * Handle: mock relay [<amplifier|compressor> <on|off>]
 *
 * Examples:
 *   mock relay                   -- print current relay states
 *   mock relay amplifier on      -- energise amplifier relay
 *   mock relay amplifier off     -- de-energise amplifier relay
 *   mock relay compressor on     -- energise compressor relay
 *   mock relay compressor off    -- de-energise compressor relay
 */
static void handleRelay(const char* args, Print& out) {
    // ── status (no args) ──────────────────────────────────────────────────────
    if (args == nullptr || *args == '\0') {
        char buf[64];
        snprintf(buf, sizeof(buf), "  compressor : %s",
                 compressor::getStatus() ? "ON" : "off");
        out.println(buf);
        snprintf(buf, sizeof(buf), "  amplifier  : %s",
                 amplifier::getRelayState() ? "ON" : "off");
        out.println(buf);
        return;
    }

    // ── identify target relay ─────────────────────────────────────────────────
    bool isAmplifier = false;
    const char* rest = nullptr;

    if (strncmp(args, "amplifier", 9) == 0 &&
        (args[9] == ' ' || args[9] == '\t' || args[9] == '\0')) {
        isAmplifier = true;
        rest = skipWs(args + 9);
    } else if (strncmp(args, "compressor", 10) == 0 &&
               (args[10] == ' ' || args[10] == '\t' || args[10] == '\0')) {
        isAmplifier = false;
        rest = skipWs(args + 10);
    } else {
        out.println("[ERR] Usage: mock relay <amplifier|compressor> <on|off>");
        return;
    }

    // ── parse on / off ────────────────────────────────────────────────────────
    if (rest == nullptr || *rest == '\0') {
        out.println("[ERR] Usage: mock relay <amplifier|compressor> <on|off>");
        return;
    }

    bool state = false;
    if (strncmp(rest, "on",  2) == 0 && (rest[2] == '\0' || rest[2] == ' ' || rest[2] == '\t')) {
        state = true;
    } else if (strncmp(rest, "off", 3) == 0 && (rest[3] == '\0' || rest[3] == ' ' || rest[3] == '\t')) {
        state = false;
    } else {
        out.println("[ERR] Usage: mock relay <amplifier|compressor> <on|off>");
        return;
    }

    // ── apply ─────────────────────────────────────────────────────────────────
    const char* name = isAmplifier ? "amplifier" : "compressor";
    if (isAmplifier) {
        amplifier::setRelayState(state);
    } else {
        compressor::setRelayState(state);
    }

    char buf[48];
    snprintf(buf, sizeof(buf), "[OK] relay.%s = %s", name, state ? "ON" : "off");
    out.println(buf);
}

/** Print full mock status (called when no subcommand is matched). */
static void handleStatus(const char* /*args*/, Print& out) {
    const sensor_mock::Overrides& mo = sensor_mock::get();
    char buf[80];

    out.println(sensor_mock::isActive()
                    ? "[OK] Mock mode: ACTIVE"
                    : "[OK] Mock mode: inactive (real hardware)");

    snprintf(buf, sizeof(buf), "  temp     : %.3f C", mo.tempC);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  rate     : %.3f C/min", mo.coolingRate);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  rms      : %.3f V", mo.rmsVoltageV);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  current  : %.3f A", mo.current);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  voltage  : %.3f V", mo.voltage);
    out.println(buf);
    snprintf(buf, sizeof(buf), "  stall    : %s", mo.stalled    ? "true" : "false");
    out.println(buf);
    snprintf(buf, sizeof(buf), "  stroke   : %s", mo.overstroke ? "true" : "false");
    out.println(buf);

    // Relay states (always shown; state machine may override next tick)
    snprintf(buf, sizeof(buf), "  relay.compressor : %s",
             compressor::getStatus() ? "ON" : "off");
    out.println(buf);
    snprintf(buf, sizeof(buf), "  relay.amplifier  : %s",
             amplifier::getRelayState() ? "ON" : "off");
    out.println(buf);

    // Cold-head module-local RTD mock (independent of global mock mode)
    if (cold_head::isMockEnabled()) {
        snprintf(buf, sizeof(buf),
                 "  coldhead : MOCKED  %.3f C",
                 cold_head::getLastTempC());
    } else {
        snprintf(buf, sizeof(buf), "  coldhead : real ADS122C04");
    }
    out.println(buf);

    // Show active ramps
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

// ─── Subcommand dispatch table ─────────────────────────────────────────────────
//
// To add a new subcommand:
//   1. Write a static handler above.
//   2. Add a row here — order determines priority for prefix matches.

using SubHandlerFn = void (*)(const char* args, Print& out);

struct SubCommand {
    const char*  name;
    SubHandlerFn handler;
};

static const SubCommand kSubCommands[] = {
    { "coldhead", handleColdhead },
    { "current",  handleCurrent  },
    { "disable",  handleDisable  },
    { "enable",   handleEnable   },
    { "ramp",     handleRamp     },
    { "rate",     handleRate     },
    { "relay",    handleRelay    },
    { "rms",      handleRms      },
    { "stall",    handleStall    },
    { "stroke",   handleStroke   },
    { "temp",     handleTemp     },
    { "voltage",  handleVoltage  },
};

// ─── Public handler ───────────────────────────────────────────────────────────

void handleMock(const char* args, Print& out) {
    args = skipWs(args);

    for (const auto& sc : kSubCommands) {
        const size_t n = strlen(sc.name);
        if (strncmp(args, sc.name, n) == 0 &&
            (args[n] == '\0' || args[n] == ' ' || args[n] == '\t')) {
            sc.handler(skipWs(args + n), out);
            return;
        }
    }

    // No subcommand matched — print status.
    handleStatus(nullptr, out);
}

} // namespace mock_commands

#endif // ARDUINO
