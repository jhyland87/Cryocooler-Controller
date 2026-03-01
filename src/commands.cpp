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
#include "cold_head.h"
#include "rms.h"
#include "dac.h"
#include "indicator.h"
#include "cooling.h"
#ifdef ARDUINO
#include "dashboard.h"
#include "mock_commands.h"
#include "sensor_mock.h"
#endif

namespace commands {

// ─── Line buffer (serial accumulator) ────────────────────────────────────────

static constexpr uint8_t  kMaxLineLen       = 80;
static constexpr uint32_t kCommandTimeoutMs = 100;  ///< dispatch after this many ms with no new byte

static char     lineBuf[kMaxLineLen + 1];
static uint8_t  lineLen    = 0;
static uint32_t lastCharMs = 0;  ///< millis() of the most recently buffered printable byte

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
    // Use mock temperature when active so the FSM picks the right entry
    // state (coarse vs fine vs settle) even without real hardware.
    // Native test builds fall back to the header default (AMBIENT_START_K).
#ifdef ARDUINO
    const float tempK = sensor_mock::isActive()
                            ? sensor_mock::get().tempK
                            : cold_head::getLastTempK();
    state_machine::start(millis(), tempK);
#else
    state_machine::start(millis());
#endif
    out.println("[OK] Process started");
}

#ifdef ARDUINO
static void handleReinit(const char* /*args*/, Print& out) {
    // Reset the FSM back to the Off state.  Useful after a fault, or when
    // entering mock mode mid-session without rebooting.
    state_machine::Module::init();
    char buf[72];
    snprintf(buf, sizeof(buf), "[OK] FSM reinitialized — state: %s | mock: %s",
             state_machine::stateName(state_machine::getState()),
             sensor_mock::isActive() ? "ACTIVE" : "inactive");
    out.println(buf);
}
#endif

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
#ifdef ARDUINO
    // Also silence the TCP dashboard stream — both transports carry telemetry.
    // Use `dashboard on` to re-enable the TCP stream independently if needed.
    dashboard::disable();
#endif
    out.println("[OK] Telemetry disabled");
}

static void handleTelemetryOn(const char* /*args*/, Print& out) {
    telemetry::enable();
#ifdef ARDUINO
    dashboard::enable();
#endif
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
    out.println("  --- Cold Head ---");
    snprintf(buf, sizeof(buf), "  Cold stage      : %.2f C  /  %.2f K",
             cold_head::getLastTempC(), cold_head::getLastTempK());
    out.println(buf);

    // snprintf(buf, sizeof(buf), "  Ambient         : %.2f C",
    //          cold_head::getLastAmbientTempC());
    // out.println(buf);

    snprintf(buf, sizeof(buf), "  Below ambient   : %.2f C",
             cold_head::getLastTempCBelowAmbient());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Cooling rate    : %.3f K/min",
             cold_head::getCoolingRateKPerMin());
    out.println(buf);

    snprintf(buf, sizeof(buf), "  Cooldown        : %.1f %%",
             cold_head::getTemperatureToPercent());
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
#ifdef ARDUINO
    {"reinit",        handleReinit,       "Reset FSM to Off state (use with mock mode)"},
#endif
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
    // "mock" is a catch-all; subcommands are parsed inside mock_commands::handleMock().
    // Must follow any more-specific "mock ..." entries if those are ever added.
    {"mock",          mock_commands::handleMock, "Sensor mock: enable|disable|status|temp|rate|rms|current|voltage|stall|stroke"},
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

module::ServiceStatus service() {
#ifdef ARDUINO
    while (Serial.available()) {
        const char c = static_cast<char>(Serial.read());
        if (c == '\r' || c == '\n') {
            // Accept \r, \n, and \r\n line endings.
            // For \r\n: \r processes the line; the following \n sees an empty
            // buffer (lineLen == 0) and is a no-op — no double dispatch.
            if (lineLen > 0) {
                lineBuf[lineLen] = '\0';
                processLine(lineBuf, Serial);
                lineLen = 0;
            }
        } else if (lineLen < kMaxLineLen) {
            lineBuf[lineLen++] = c;
            lastCharMs = millis();
        }
        // Characters beyond kMaxLineLen are silently dropped until next newline.
    }

    // Timeout-based dispatch: if bytes accumulated but no line terminator
    // arrived within kCommandTimeoutMs, treat the buffer as a complete command.
    // Handles monitors / tools (e.g. PlatformIO IDE with "None" EOL) that send
    // the full string as one USB-CDC packet without appending \r or \n.
    if (lineLen > 0 && (millis() - lastCharMs) >= kCommandTimeoutMs) {
        lineBuf[lineLen] = '\0';
        processLine(lineBuf, Serial);
        lineLen = 0;
    }
#endif
    return module::MODULE_SERVICE_OK;
}

} // namespace commands
