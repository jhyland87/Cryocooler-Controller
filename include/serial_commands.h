/**
 * @file serial_commands.h
 * @brief Backward-compatibility shim — use commands.h / commands:: directly.
 *
 * The command handler was renamed to the transport-agnostic `commands` module.
 * This header keeps existing code and tests compiling unchanged via a
 * namespace alias.
 */

#ifndef SERIAL_COMMANDS_H
#define SERIAL_COMMANDS_H

#include "commands.h"

// Alias so all existing serial_commands:: call sites continue to compile.
namespace serial_commands = commands;

#endif // SERIAL_COMMANDS_H
