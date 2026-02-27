/**
 * @file commands.cpp
 * @brief Generic command dispatcher — sources: Serial, TCP (Serial Studio), etc.
 *
 * processLine() is transport-agnostic: it accepts any Print& as the response
 * sink, so the same command table works for serial input and TCP input.
 *
 * service() handles the Serial-specific accumulation (non-blocking).
 * The TCP path calls processLine() directly from the AsyncTCP data callback.
 */

#ifdef ARDUINO
#  include <Arduino.h>
#else
#  include <cstdio>
#  include <cstring>
#  include "Arduino.h"  // native stub — provides millis() and Print
#endif

#include "commands.h"
#include "state_machine.h"
#include "telemetry.h"
#include "temperature.h"
#include "rms.h"
#include "dac.h"
#include "indicator.h"
#include "cooling.h"
#ifdef ARDUINO
#include "dashboard.h"
#endif

namespace commands {

// ─── Line buffer (serial accumulator) ────────────────────────────────────────

static constexpr uint8_t kMaxLineLen = 80;
static char    lineBuf[kMaxLineLen + 1];
static uint8_t lineLen = 0;

// ─── Command handler type and dispatch table ──────────────────────────────────

// args: everything after the command name (leading whitespace stripped).
// Empty string ("") when no argument was provided.
using HandlerFn = void (*)(const char* args, Print& out);

struct Command {
    const char* name;
    HandlerFn   handler;
    const char* help;
};

// Forward declaration so handleHelp can reference commands[] below.
static void handleHelp(const char* args, Print& out);

// ─── Individual command handlers ──────────────────────────────────────────────

static void handleStart(const char* /*args*/, Print& out) {
    if (state_machine::isRunning()) {
        out.println("[ERR] Already running");
        return;
    }
    if (state_machine::getState() != state_machine::State::Idle &&
        state_machine::getState() != state_machine::State::Off) {
        out.println("[ERR] Cannot start: not in Idle or Off state");
        return;
    }
    state_machine::start(millis());
    out.println("[OK] Process started");
}

static void handleStop(const char* /*args*/, Print& out) {
    if (!state_machine::isRunning()) {
        out.println("[ERR] Not currently running");
        return;
    }
    state_machine::stop(millis());
    out.println("[OK] Process stopped");
}

static void handleOff(const char* /*args*/, Print& out) {
    if (state_machine::getState() == state_machine::State::Off) {
        out.println("[ERR] System is already off");
        return;
    }
    state_machine::off(millis());
    out.println("[OK] System turned off");
}

static void handleStatus(const char* /*args*/, Print& out) {
    char buf[96];
    snprintf(buf, sizeof(buf), "[OK] %s (%d) | running: %s",
             state_machine::stateName(state_machine::getState()),
             static_cast<int8_t>(state_machine::getState()),
             state_machine::isRunning() ? "yes" : "no");
    out.println(buf);
}

static void handleTelemetryOff(const char* /*args*/, Print& out) {
    telemetry::disable();
    out.println("[OK] Telemetry disabled");
}

static void handleTelemetryOn(const char* /*args*/, Print& out) {
    telemetry::enable();
    out.println("[OK] Telemetry enabled");
}

static void handleTelemetryDeltaOff(const char* /*args*/, Print& out) {
    telemetry::disableDelta();
    out.println("[OK] Telemetry delta mode disabled (full frame each emit)");
}

static void handleTelemetryDeltaOn(const char* /*args*/, Print& out) {
    telemetry::enableDelta();
    out.println("[OK] Telemetry delta mode enabled (only changed values emitted)");
}

#ifdef ARDUINO
static void handleDashboardOff(const char* /*args*/, Print& out) {
    dashboard::disable();
    out.println("[OK] Dashboard disabled");
}

static void handleDashboardOn(const char* /*args*/, Print& out) {
    dashboard::enable();
    out.println("[OK] Dashboard enabled");
}
#endif


static void handleCoolingOn(const char* /*args*/, Print& out) {
    cooling::enable();
    out.println("[OK] Cooling enabled");
}

static void handleCoolingOff(const char* /*args*/, Print& out) {
    cooling::disable();
    out.println("[OK] Cooling disabled");
}

static void handleCoolingFan(const char* args, Print& out) {
    if (*args == '\0') {
        out.println("[ERR] Usage: cooling fan <0-100>");
        return;
    }

    // Parse up to 4 digits (anything ≥ 1000 will fail the range check).
    uint16_t val    = 0;
    uint8_t  digits = 0;
    const char* p = args;
    while (*p >= '0' && *p <= '9' && digits < 4u) {
        val = static_cast<uint16_t>(val * 10u + static_cast<uint16_t>(*p - '0'));
        ++p;
        ++digits;
    }

    // Reject: no digits, trailing non-whitespace garbage, or out-of-range.
    if (digits == 0 || (*p != '\0' && *p != ' ' && *p != '\t') || val > 100u) {
        char buf[64];
        snprintf(buf, sizeof(buf),
                 "[ERR] cooling fan: invalid argument '%s' (expected 0-100)", args);
        out.println(buf);
        return;
    }

    cooling::setFanSpeed(static_cast<uint8_t>(val), true);
    char buf[48];
    snprintf(buf, sizeof(buf), "[OK] Fan speed set to %u%%", static_cast<unsigned>(val));
    out.println(buf);
}

static void handleBoard(const char* /*args*/, Print& out) {
    out.println("[OK] Board info:");
#ifdef ARDUINO_VARIANT
    out.println("  ARDUINO_VARIANT:        " ARDUINO_VARIANT);
#endif
#ifdef CONFIG_IDF_TARGET
    out.println("  CONFIG_IDF_TARGET:      " CONFIG_IDF_TARGET);
#endif
#ifdef ARDUINO_BOARD
    out.println("  ARDUINO_BOARD:          " ARDUINO_BOARD);
#endif
#ifdef CONFIG_ARDUINO_VARIANT
    out.println("  CONFIG_ARDUINO_VARIANT: " CONFIG_ARDUINO_VARIANT);
#endif
#ifdef CONFIG_ARDUINO_BOARD
    out.println("  CONFIG_ARDUINO_BOARD:   " CONFIG_ARDUINO_BOARD);
#endif
#ifdef ARDUINO_ARCH_ESP32
    out.println("  ARDUINO_ARCH_ESP32");
#endif
#ifdef ESP32S3
    out.println("  ESP32S3");
#elif defined(ESP32)
    out.println("  ESP32");
#endif
#if !defined(ARDUINO_VARIANT) && !defined(CONFIG_IDF_TARGET) && \
    !defined(ARDUINO_BOARD)   && !defined(ESP32)
    out.println("  (native / host build — no board macros defined)");
#endif
}

static void handleSummary(const char* /*args*/, Print& out) {
    const uint32_t durationMs = state_machine::getOnStateDuration();
    const uint32_t durSec     = durationMs / 1000u;
    char hmsBuf[12];
    snprintf(hmsBuf, sizeof(hmsBuf), "%02lu:%02lu:%02lu",
             static_cast<unsigned long>(durSec / 3600u),
             static_cast<unsigned long>((durSec % 3600u) / 60u),
             static_cast<unsigned long>(durSec % 60u));

    char buf[96];

    out.println("[OK] --- Cryocooler Summary ---");

    snprintf(buf, sizeof(buf), "  State           : %s (%d) | running: %s",
             state_machine::stateName(state_machine::getState()),
             static_cast<int8_t>(state_machine::getState()),
             state_machine::isRunning() ? "yes" : "no");
    out.println(buf);

    snprintf(buf, sizeof(buf), "  On duration     : %s", hmsBuf);
    out.println(buf);

#ifdef ARDUINO
    out.println("  --- Temperature ---");
    snprintf(buf, sizeof(buf), "  Cold stage      : %.2f C  /  %.2f K",
             temperature::getLastTempC(), temperature::getLastTempK());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Ambient         : %.2f C",
             temperature::getLastAmbientTempC());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Below ambient   : %.2f C",
             temperature::getLastTempCBelowAmbient());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Cooling rate    : %.3f K/min",
             temperature::getCoolingRateKPerMin());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Cooldown        : %.1f %%",
             temperature::getTemperatureToPercent());
    out.println(buf);

    out.println("  --- Electrical ---");
    snprintf(buf, sizeof(buf), "  Current         : %.3f A",
             rms::getCurrentA());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Voltage (RMS)   : %.2f V",
             rms::getVoltage());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  DAC output      : %u",
             static_cast<unsigned>(dac::getCurrent()));
    out.println(buf);

    out.println("  --- Indicators ---");
    snprintf(buf, sizeof(buf), "  Fault LED       : %s",
             indicator::isFaultOn() ? "ON" : "off");
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Ready LED       : %s",
             indicator::isReadyOn() ? "ON" : "off");
    out.println(buf);
#endif
}

// ─── Command table ────────────────────────────────────────────────────────────
// Multi-word commands ("telemetry off") must appear before any shorter prefix
// command ("telemetry on") so the match loop finds the most specific one first.

static const Command kCommands[] = {
    {"start",         handleStart,        "Begin the cooldown process (from Off or Idle)"},
    {"stop",          handleStop,         "Abort the process and return to Idle"},
    {"off",           handleOff,          "Power off the system entirely"},
    {"status",        handleStatus,       "Print current state and running flag"},
    {"summary",       handleSummary,      "Print a full snapshot of all system values"},
    {"board",         handleBoard,        "Print compile-time board/platform info"},
    {"help",          handleHelp,         "Show available commands"},
    // "telemetry delta ..." must precede "telemetry on/off" so the longer
    // prefix is matched first by the linear scan in processLine().
    {"telemetry delta off", handleTelemetryDeltaOff, "Emit full frame each tick (default)"},
    {"telemetry delta on",  handleTelemetryDeltaOn,  "Emit only changed values each tick"},
    {"telemetry off",       handleTelemetryOff,      "Disable telemetry output"},
    {"telemetry on",        handleTelemetryOn,       "Enable telemetry output"},
    // "cooling fan <N>" must precede "cooling on/off" so the longer prefix wins.
    {"cooling fan",         handleCoolingFan,         "Set cooling fan speed percentage (0-100)"},
    {"cooling on",          handleCoolingOn,           "Enable cooling system"},
    {"cooling off",         handleCoolingOff,          "Disable cooling system"},
#ifdef ARDUINO
    {"dashboard off", handleDashboardOff, "Disable dashboard TCP broadcasts"},
    {"dashboard on",  handleDashboardOn,  "Enable dashboard TCP broadcasts"},
#endif
};

static const uint8_t kCommandCount =
    static_cast<uint8_t>(sizeof(kCommands) / sizeof(kCommands[0]));

static void handleHelp(const char* /*args*/, Print& out) {
    out.println(F("[OK] Available commands:"));
    for (uint8_t i = 0; i < kCommandCount; ++i) {
        char line[80];
        snprintf(line, sizeof(line), "  %-16s  %s",
                 kCommands[i].name, kCommands[i].help);
        out.println(line);
    }
}

// ─── Public API ───────────────────────────────────────────────────────────────

void processLine(const char* line, Print& out) {
    // Skip leading whitespace.
    while (*line == ' ' || *line == '\t') { ++line; }
    if (*line == '\0') return;

    // Match command names by prefix: the name must exactly fill the start of
    // the line, followed by end-of-string, space, or tab.  Multi-word names
    // like "telemetry off" win over shorter prefixes because of table order.
    for (uint8_t i = 0; i < kCommandCount; ++i) {
        const size_t nameLen = strlen(kCommands[i].name);
        if (strncmp(kCommands[i].name, line, nameLen) == 0 &&
            (line[nameLen] == '\0' || line[nameLen] == ' ' || line[nameLen] == '\t')) {
            // Strip leading whitespace from whatever follows the command name.
            const char* args = line + nameLen;
            while (*args == ' ' || *args == '\t') { ++args; }
            kCommands[i].handler(args, out);
            return;
        }
    }

    // Unknown — show just the first token so the message stays tidy.
    const char* end = line;
    while (*end && *end != ' ' && *end != '\t') { ++end; }
    char msg[80];
    snprintf(msg, sizeof(msg),
             "[ERR] Unknown command: '%.*s'  (type 'help')",
             static_cast<int>(end - line), line);
    out.println(msg);
}

module::InitStatus init() {
    lineLen    = 0;
    lineBuf[0] = '\0';
    return module::MODULE_INIT_SUCCESS;
}

void service() {
#ifdef ARDUINO
    while (Serial.available()) {
        const char c = static_cast<char>(Serial.read());
        if (c == '\r') continue;
        if (c == '\n') {
            lineBuf[lineLen] = '\0';
            if (lineLen > 0) {
                processLine(lineBuf, Serial);
            }
            lineLen = 0;
        } else if (lineLen < kMaxLineLen) {
            lineBuf[lineLen++] = c;
        }
        // Characters beyond kMaxLineLen are silently dropped until next newline.
    }
#endif
}

} // namespace commands
