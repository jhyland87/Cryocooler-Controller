/**
 * @file arduino_stub.cpp
 * @brief Arduino API stubs for native unit tests
 *
 * Provides minimal implementations of millis(), GPIO, and SPI APIs
 * so that hardware-dependent modules can compile in test environment.
 */

#include "Arduino.h"

static uint32_t sStubMillis = 0;

// SPI stub state
static uint16_t sLastSpiTransfer = 0;

extern "C" {

uint32_t millis(void) {
    return sStubMillis;
}

void stub_setMillis(uint32_t ms) {
    sStubMillis = ms;
}

void pinMode(uint8_t pin, uint8_t mode) {
    // No-op for testing
    (void)pin;
    (void)mode;
}

void digitalWrite(uint8_t pin, uint8_t val) {
    // No-op for testing
    (void)pin;
    (void)val;
}

} // extern "C"

// SPI stub implementation
void SPIClass::beginTransaction(SPISettings settings) {
    (void)settings;
}

void SPIClass::endTransaction(void) {
}

uint16_t SPIClass::transfer16(uint16_t data) {
    sLastSpiTransfer = data;
    return 0;  // Return value not used in DAC
}

// Global SPI instance
SPIClass SPI;

// Global Serial stub instance
SerialStub Serial;
