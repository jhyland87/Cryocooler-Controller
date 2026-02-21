/**
 * @file serial_commands.h
 * @brief Lightweight serial command handler for the cryocooler controller.
 *
 * Available commands:
 *   start   - Begin the cooldown process (from Off or Idle)
 *   stop    - Abort the process and return to Idle
 *   off     - Power off the system entirely
 *   status  - Print current state and running flag
 *   board   - Print compile-time board/platform info
 *   help    - List available commands
 *
 * Usage:
 *   Call serial_commands::init() once in setup() after Serial.begin().
 *   Call serial_commands::service() every loop() iteration.
 *
 * Testing:
 *   Call serial_commands::processLine() directly with a stub Print to
 *   verify command dispatch and responses without hardware.
 */

#ifndef SERIAL_COMMANDS_H
#define SERIAL_COMMANDS_H

// Forward declaration — resolved by <Arduino.h> on target, Print.h stub on native.
class Print;

namespace serial_commands {

/** Initialise the line buffer.  Call after Serial.begin(). */
void init();

/** Non-blocking service call.  Call every loop() iteration. */
void service();

/**
 * Parse and dispatch one null-terminated command line.
 * Exposed for unit testing: inject any Print to capture the response.
 *
 * @param line  Null-terminated string (will not be modified).
 * @param out   Output stream for the response (Serial on target, stub in tests).
 */
void processLine(const char* line, Print& out);

} // namespace serial_commands

#endif // SERIAL_COMMANDS_H
