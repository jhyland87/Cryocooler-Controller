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

// GPIO stubs
void     pinMode(uint8_t pin, uint8_t mode);
void     digitalWrite(uint8_t pin, uint8_t val);

#ifdef __cplusplus
}
#endif

// F() macro: in Arduino, places string literals in flash memory.
// In native tests it is a no-op — string literals already live in RAM.
#ifndef F
#  define F(str) (str)
#endif

// SPI stub class (minimal C++ interface)
class SPISettings {
public:
    SPISettings(uint32_t clock, uint8_t bitOrder, uint8_t dataMode)
        : clock_(clock), bitOrder_(bitOrder), dataMode_(dataMode) {}
    uint32_t clock_;
    uint8_t bitOrder_;
    uint8_t dataMode_;
};

class SPIClass {
public:
    void beginTransaction(SPISettings settings);
    void endTransaction(void);
    uint16_t transfer16(uint16_t data);
};

extern SPIClass SPI;

#endif // ARDUINO_STUB_H
