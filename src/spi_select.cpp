/**
 * @file spi_select.cpp
 * @brief Routes chip-select IDs to the SN74LVC138A decoder.
 *
 * The Arduino core defines pinMode() and digitalWrite() as weak aliases of
 * __pinMode() and __digitalWrite(), so these strong definitions replace them for
 * every driver. Ordinary pins pass straight through.
 */

#ifdef ARDUINO

#include <Arduino.h>

#include "spi_select.h"

extern "C" {
void __pinMode(uint8_t pin, uint8_t mode);
void __digitalWrite(uint8_t pin, uint8_t val);
}

static bool sDecoderPinsReady = false;
static uint8_t sSelectedOutput = spi_select::NO_OUTPUT_SELECTED;

// Static constructors can touch a chip select before setup(), so this runs on
// first use. Enable goes high before the pin becomes an output, to avoid a select.
static void prepareDecoderPins() {
    if (sDecoderPinsReady) {
        return;
    }
    sDecoderPinsReady = true;
    __digitalWrite(CS_ENABLE_PIN, HIGH);
    __pinMode(CS_ENABLE_PIN, OUTPUT);
    for (uint8_t addressPin : {CS_ADDR_A_PIN, CS_ADDR_B_PIN, CS_ADDR_C_PIN}) {
        __pinMode(addressPin, OUTPUT);
    }
}

extern "C" void ARDUINO_ISR_ATTR pinMode(uint8_t pin, uint8_t mode) {
    if (!spi_select::isChipSelectId(pin)) {
        __pinMode(pin, mode);
        return;
    }
    prepareDecoderPins();
}

extern "C" void ARDUINO_ISR_ATTR digitalWrite(uint8_t pin, uint8_t val) {
    if (!spi_select::isChipSelectId(pin)) {
        __digitalWrite(pin, val);
        return;
    }
    prepareDecoderPins();
    spi_select::applyChipSelect(pin, val, sSelectedOutput,
                                [](uint8_t gpio, uint8_t level) { __digitalWrite(gpio, level); });
}

#endif  // ARDUINO
