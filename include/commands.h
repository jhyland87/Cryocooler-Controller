/**
 * @file commands.h
 * @brief Generic command handler — dispatches text commands from any source.
 *
 * Commands can arrive from:
 *   - Serial (USB CDC): via service(), which accumulates bytes non-blocking.
 *   - TCP client (Serial Studio): call processLine() directly from the data
 *     callback with an AsyncClientPrint as the output stream.
 *
 * Available commands:
 *   start                - Begin the cooldown process (from Off or Idle)
 *   stop                 - Abort the process and return to Idle
 *   off                  - Power off the system entirely
 *   status               - Print current state and running flag
 *   summary              - Print a full snapshot of all system values
 *   board                - Print compile-time board/platform info
 *   help                 - List available commands
 *   telemetry off        - Disable telemetry
 *   telemetry on         - Enable telemetry
 *   dashboard off        - Disable dashboard TCP broadcasts
 *   dashboard on         - Enable dashboard TCP broadcasts
 *   cooling fan <0-100>  - Set cooling fan speed (percentage)
 *   cooling on           - Enable cooling system
 *   cooling off          - Disable cooling system
 *
 * Usage:
 *   Call commands::init() once in setup() after Serial.begin().
 *   Call commands::service() every loop() iteration for serial input.
 *   Call commands::processLine() from any context with any Print sink.
 *
 * Testing:
 *   Call commands::processLine() directly with a stub Print to verify
 *   command dispatch and responses without hardware.
 */

#ifndef COMMANDS_H
#define COMMANDS_H

#include "module.h"

// Forward declaration — resolved by <Arduino.h> on target, Print.h stub on native.
class Print;

namespace commands {

/**
 * Initialise the serial line buffer.  Call after Serial.begin().
 * @return MODULE_INIT_SUCCESS always.
 */
module::InitStatus init();

/**
 * Non-blocking serial service call.  Reads available bytes from Serial,
 * accumulates them into a line buffer, and calls processLine() on each
 * newline.  Call every loop() iteration.
 */
void service();

/**
 * Parse and dispatch one null-terminated command line.
 * Exposed for unit testing and multi-transport use: inject any Print to
 * capture the response.
 *
 * @param line  Null-terminated string (will not be modified).
 * @param out   Output stream for the response (Serial, AsyncClientPrint, stub…).
 */
void processLine(const char* line, Print& out);

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    /** Initialise the serial line buffer.  Call after Serial.begin(). */
    static module::InitStatus init() { return commands::init(); }
    /** Read and dispatch available serial bytes (non-blocking). */
    static void service()            { commands::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace commands

#endif // COMMANDS_H
