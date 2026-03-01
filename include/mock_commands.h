/**
 * @file mock_commands.h
 * @brief Serial command handler for sensor mock mode.
 *
 * Provides a single entry point — handleMock() — that is registered in the
 * command table in commands.cpp under the "mock" keyword.  All subcommand
 * parsing lives in mock_commands.cpp so that the mock-related code stays
 * out of the main command dispatcher.
 *
 * Only compiled for the embedded target; the native test build does not
 * include sensor_mock or mock_commands.
 */

#ifndef MOCK_COMMANDS_H
#define MOCK_COMMANDS_H

#ifdef ARDUINO

// Forward declaration — resolved by <Arduino.h> on target.
class Print;

namespace mock_commands {

/**
 * Dispatch a "mock" subcommand.
 *
 * @param args  Everything after the word "mock" (leading whitespace stripped).
 * @param out   Response sink (Serial, TCP client, etc.).
 *
 * Subcommands:
 *   (empty) / status    Print current override values and active state
 *   enable              Activate mock mode
 *   disable             Deactivate mock mode, return to real hardware
 *   temp   <K>          Cold-stage temperature (Kelvin)
 *   rate   <K/min>      Cooling rate (negative = getting colder)
 *   rms    <V>          Back-EMF RMS voltage
 *   current <A>         INA260 current
 *   voltage <V>         INA260 bus voltage
 *   stall  <0|1>        Temperature-stall flag
 *   stroke <0|1>        Back-EMF overstroke flag
 */
void handleMock(const char* args, Print& out);

} // namespace mock_commands

#endif // ARDUINO
#endif // MOCK_COMMANDS_H
