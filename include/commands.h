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
 *   fsm state            - Print current FSM state with time-in-state and status text
 *   fsm history          - Print recent FSM state transitions (newest first, up to FSM_HISTORY_LIMIT)
 *   fault history        - Print fault log with reason and clear method (newest first, up to FAULT_HISTORY_LIMIT)
 *   fault clear          - Clear an active fault and return to Idle
 *   board                - Print compile-time board/platform info
 *   help                 - List available commands
 *   telemetry off        - Disable telemetry
 *   telemetry on         - Enable telemetry
 *   dashboard off        - Disable dashboard TCP broadcasts
 *   dashboard on         - Enable dashboard TCP broadcasts
 *   cooling fan <0-100>  - Set cooling fan speed (percentage)
 *   cooling on           - Enable cooling system
 *   cooling off          - Disable cooling system
 *   mock                 - Print current mock sensor values and active state
 *   mock enable          - Activate sensor mock mode (bypass real hardware)
 *   mock disable         - Deactivate sensor mock mode (return to hardware)
 *   mock temp <K>        - Set cold-stage temperature (Kelvin)
 *   mock rate <K/min>    - Set cooling rate (negative = cooling down)
 *   mock rms <V>         - Set back-EMF RMS voltage
 *   mock current <A>     - Set INA237 current
 *   mock voltage <V>     - Set INA237 bus voltage
 *   mock stall <0|1>     - Set temperature-stall flag
 *   mock stroke <0|1>    - Set back-EMF overstroke flag
 *   ota status           - Print OTA partition info, firmware version, and upload URL
 *   update image         - Flash new firmware via browser upload (prompts for confirmation)
 *   log level <0-5|off>  - Set runtime log level (0=off, 1=error … 5=verbose)
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

// Forward declaration — resolved by <Arduino.h> on target, Print.h stub on native.
class Print;

namespace commands {

/** Initialise the serial line buffer.  Call after Serial.begin(). */
void init();

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

} // namespace commands

#endif // COMMANDS_H
