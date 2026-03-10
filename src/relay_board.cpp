/**
 * @file relay_board.cpp
 * @brief Shared PCAL9535A driver for the dual-relay board.
 */

#include <Arduino.h>
#include "PCAL9535A.h"

#include "relay_board.h"
#include "pin_config.h"
#include "hardware.h"
#include "esp_log.h"

namespace relay_board {

static constexpr char TAG[] = "relay_board";

// Single PCAL9535A instance shared by both relay channels.
static PCAL9535A::PCAL9535A<TwoWire> sGpio(hardware::i2c());

// Cached output states — indexed directly by pin number.
static bool sPinState[2] = { false, false };

static bool sInitialized = false;

// ---------------------------------------------------------------------------

module::InitStatus init() {
    if (sInitialized) return module::MODULE_INIT_SUCCESS;

    ESP_LOGI(TAG, "Initialising PCAL9535A dual-relay board (addr=0x%02X)",
             static_cast<unsigned>(COMPRESSOR_RELAY_PCAL_ADDR));

    // begin() resets all pin-direction registers — call it exactly once.
    sGpio.begin(COMPRESSOR_RELAY_PCAL_ADDR);

    // Configure both relay pins as outputs and drive them LOW.
    sGpio.pinMode(COMPRESSOR_RELAY_PIN, OUTPUT);
    sGpio.pinMode(AMPLIFIER_RELAY_PIN,  OUTPUT);
    sGpio.digitalWrite(COMPRESSOR_RELAY_PIN, LOW);
    sGpio.digitalWrite(AMPLIFIER_RELAY_PIN,  LOW);

    sPinState[COMPRESSOR_RELAY_PIN] = false;
    sPinState[AMPLIFIER_RELAY_PIN]  = false;
    sInitialized = true;

    ESP_LOGI(TAG, "PCAL9535A initialised — both relays OFF");
    return module::MODULE_INIT_SUCCESS;
}

void setPin(uint8_t pin, bool on) {
    if (pin >= 2u) return;
    if (on == sPinState[pin]) return;   // no-op if already in target state
    sPinState[pin] = on;
    sGpio.digitalWrite(pin, on ? HIGH : LOW);
    ESP_LOGD(TAG, "pin %u → %s", static_cast<unsigned>(pin), on ? "ON" : "OFF");
}

bool getPin(uint8_t pin) {
    if (pin >= 2u) return false;
    return sPinState[pin];
}

} // namespace relay_board
