/**
 * @file Arduino.h
 * @brief Minimal Arduino stub for native (host-PC) unit tests
 *
 * Provides just enough of the Arduino API so that modules which include
 * <Arduino.h> for millis() etc. can compile in the native test environment.
 */

#ifndef ARDUINO_STUB_H
#define ARDUINO_STUB_H

#include <stdint.h>
#include "Print.h"  // stub Print class (needed by serial_commands.cpp)

// Stub millis() — returns a value set by the test harness
// Default: 0, override via stub_setMillis() before each test if needed.
#ifdef __cplusplus
extern "C" {
#endif

uint32_t millis(void);
void     stub_setMillis(uint32_t ms);

#ifdef __cplusplus
}
#endif

#endif // ARDUINO_STUB_H
