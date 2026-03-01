/**
 * @file WProgram.h
 * @brief Compatibility shim for Arduino libraries that include <WProgram.h>
 *        when ARDUINO is not defined (e.g. jonblack/arduino-fsm).
 *
 * Simply re-exports the minimal Arduino stub used by all native tests so
 * that millis(), pinMode(), etc. are declared in the expected header location.
 */
#pragma once
#include "Arduino.h"
