/**
 * @file arduino_stub.cpp
 * @brief millis() stub implementation for native unit tests
 */

#include "Arduino.h"

static uint32_t sStubMillis = 0;

extern "C" {

uint32_t millis(void) {
    return sStubMillis;
}

void stub_setMillis(uint32_t ms) {
    sStubMillis = ms;
}

} // extern "C"
