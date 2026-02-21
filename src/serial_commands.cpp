/**
 * @file serial_commands.cpp
 * @brief Lightweight serial command handler — no external library dependencies.
 *
 * service() accumulates bytes from Serial into a char[] line buffer and calls
 * processLine() on each newline.  processLine() is exposed separately so it
 * can be called from unit tests with a stub Print object.
 */

#ifdef ARDUINO
#  include <Arduino.h>
#else
#  include <cstdio>
#  include <cstring>
#  include "Arduino.h"  // native stub — provides millis() and Print
#endif

#include "serial_commands.h"
#include "state_machine.h"
#include "telemetry.h"

namespace serial_commands {

// ---------------------------------------------------------------------------
// Line buffer (non-blocking accumulator)
// ---------------------------------------------------------------------------

static constexpr uint8_t kMaxLineLen = 80;
static char    sLineBuf[kMaxLineLen + 1];
static uint8_t sLineLen = 0;

// ---------------------------------------------------------------------------
// Command handler type and dispatch table
// ---------------------------------------------------------------------------

using HandlerFn = void (*)(Print&);

struct Command {
    const char* name;
    HandlerFn   handler;
    const char* help;
};

// Forward declaration so handleHelp can reference kCommands below.
static void handleHelp(Print& out);

// ---------------------------------------------------------------------------
// Individual command handlers
// ---------------------------------------------------------------------------

static void handleStart(Print& out) {
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

static void handleStop(Print& out) {
    if (!state_machine::isRunning()) {
        out.println("[ERR] Not currently running");
        return;
    }
    state_machine::stop(millis());
    out.println("[OK] Process stopped");
}

static void handleOff(Print& out) {
    if (state_machine::getState() == state_machine::State::Off) {
        out.println("[ERR] System is already off");
        return;
    }
    state_machine::off(millis());
    out.println("[OK] System turned off");
}

static void handleStatus(Print& out) {
    char buf[96];
    snprintf(buf, sizeof(buf), "[OK] %s (%d) | running: %s",
             state_machine::stateName(state_machine::getState()),
             static_cast<int8_t>(state_machine::getState()),
             state_machine::isRunning() ? "yes" : "no");
    out.println(buf);
}

static void handleTelemetryOff(Print& out) {
    telemetry::disable();
    out.println("[OK] Telemetry disabled");
}

static void handleTelemetryOn(Print& out) {
    telemetry::enable();
    out.println("[OK] Telemetry enabled");
}

static void handleBoard(Print& out) {
    out.println("[OK] Board info:");
#ifdef ARDUINO_VARIANT
    out.println("  ARDUINO_VARIANT:       " ARDUINO_VARIANT);
#endif
#ifdef CONFIG_IDF_TARGET
    out.println("  CONFIG_IDF_TARGET:     " CONFIG_IDF_TARGET);
#endif
#ifdef ARDUINO_BOARD
    out.println("  ARDUINO_BOARD:         " ARDUINO_BOARD);
#endif
#ifdef CONFIG_ARDUINO_VARIANT
    out.println("  CONFIG_ARDUINO_VARIANT: " CONFIG_ARDUINO_VARIANT);
#endif
#ifdef CONFIG_ARDUINO_BOARD
    out.println("  CONFIG_ARDUINO_BOARD:  " CONFIG_ARDUINO_BOARD);
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

// ---------------------------------------------------------------------------
// Command table  (handleHelp defined below so it can iterate kCommands)
// ---------------------------------------------------------------------------

static const Command kCommands[] = {
    {"start",  handleStart,  "Begin the cooldown process (from Off or Idle)"},
    {"stop",   handleStop,   "Abort the process and return to Idle"},
    {"off",    handleOff,    "Power off the system entirely"},
    {"status", handleStatus, "Print current state and running flag"},
    {"board",  handleBoard,  "Print compile-time board/platform info"},
    {"help",   handleHelp,   "Show available commands"},
    {"telemetry off", handleTelemetryOff, "Disable telemetry"},
    {"telemetry on", handleTelemetryOn, "Enable telemetry"},
};

static constexpr uint8_t kCommandCount =
    static_cast<uint8_t>(sizeof(kCommands) / sizeof(kCommands[0]));

static void handleHelp(Print& out) {
    out.println("[OK] Available commands:");
    for (uint8_t i = 0; i < kCommandCount; ++i) {
        char line[80];
        snprintf(line, sizeof(line), "  %-16s  %s",
                 kCommands[i].name, kCommands[i].help);
        out.println(line);
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void processLine(const char* line, Print& out) {
    // Skip leading whitespace.
    while (*line == ' ' || *line == '\t') { ++line; }
    if (*line == '\0') { return; }

    // Match commands by prefix: the command name must exactly fill the start of
    // the line, followed by end-of-string, a space, or a tab.  This naturally
    // handles multi-word command names like "telemetry off" — longer/more-specific
    // names must appear before shorter prefixes in kCommands to take precedence.
    for (uint8_t i = 0; i < kCommandCount; ++i) {
        const size_t nameLen = strlen(kCommands[i].name);
        if (strncmp(kCommands[i].name, line, nameLen) == 0 &&
            (line[nameLen] == '\0' || line[nameLen] == ' ' || line[nameLen] == '\t')) {
            kCommands[i].handler(out);
            return;
        }
    }

    // Unknown command — show up to the first space so the message stays tidy.
    const char* end = line;
    while (*end && *end != ' ' && *end != '\t') { ++end; }
    char msg[80];
    snprintf(msg, sizeof(msg),
             "[ERR] Unknown command: '%.*s'  (type 'help')",
             static_cast<int>(end - line), line);
    out.println(msg);
}

void init() {
    sLineLen    = 0;
    sLineBuf[0] = '\0';
}

void service() {
#if defined(ARDUINO)
    while (Serial.available()) {
        const char c = static_cast<char>(Serial.read());
        if (c == '\r') { continue; }
        if (c == '\n') {
            sLineBuf[sLineLen] = '\0';
            if (sLineLen > 0) {
                processLine(sLineBuf, Serial);
            }
            sLineLen = 0;
        } else if (sLineLen < kMaxLineLen) {
            sLineBuf[sLineLen++] = c;
        }
        // Characters beyond kMaxLineLen are silently dropped until next newline.
    }
#endif
}

} // namespace serial_commands
