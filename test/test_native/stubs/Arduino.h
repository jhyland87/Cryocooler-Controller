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
#include <cstdarg>   // va_list — needed by SerialStub::printf
#include <cstdlib>   // free, malloc, realloc — used by Fsm.cpp
#include <cstring>   // memset, memcpy — commonly needed by Arduino libs
#include "Print.h"  // stub Print class (needed by serial_commands.cpp)

// ─── Serial stub ─────────────────────────────────────────────────────────────
// Provides no-op implementations of the Serial methods used in source files.
// This lets code that calls Serial.printf() / Serial.println() etc. compile and
// link in native (host) test builds without scattering #ifdef ARDUINO guards
// through every debug print site.
class SerialStub {
public:
    void begin(unsigned long /*baud*/) {}

    // printf — variadic, matches Arduino's HardwareSerial::printf signature.
    int printf(const char* /*fmt*/, ...) { return 0; }  // NOLINT

    // print / println overloads (templated to accept any type).
    template<typename T> size_t print(T)   { return 0; }
    template<typename T> size_t println(T) { return 0; }
    size_t println() { return 0; }

    // Stream interface — used by the command handler.
    int  available() { return 0; }
    int  read()      { return -1; }
    void flush()     {}
};

extern SerialStub Serial;

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

// Arduino digital I/O constants
static constexpr uint8_t HIGH   = 1;
static constexpr uint8_t LOW    = 0;
static constexpr uint8_t INPUT  = 0;
static constexpr uint8_t OUTPUT = 1;

// Additional Arduino stubs needed by hardware library dependencies.
#ifdef __cplusplus
extern "C" {
#endif

uint8_t  digitalRead(uint8_t /*pin*/);
void     delayMicroseconds(unsigned int /*us*/);

#ifdef __cplusplus
}
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
