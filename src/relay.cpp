/**
 * @file relay.cpp
 * @brief Compressor and amplifier relay implementation
 */

#include <Arduino.h>
#include "SparkFun_Qwiic_Relay.h"

#include "pin_config.h"
#include "relay.h"
#include "config.h"
#include "hardware.h"

Qwiic_Relay compressorRelay(RELAY_COMPRESSOR_I2C_ADDRESS);
Qwiic_Relay amplifierRelay(RELAY_AMPLIFIER_I2C_ADDRESS);

static constexpr char TAG[] = "relay";

static bool sMockEnabled = false;
static bool sMockCompressorState = false;
static bool sMockAmplifierState = false;
static bool sInitialized = false;

namespace relay {

module::InitStatus init() {
    ESP_LOGI(TAG, "Initializing relays...");
    uint8_t successCount = 0;
    uint8_t failCount = 0;

    if (sMockEnabled) {
        ESP_LOGI(TAG, "Mock enabled, skipping relay initialization");
        sInitialized = true;
        return module::MODULE_INIT_SUCCESS;
    }

    if(!compressorRelay.begin(hardware::i2c())) {
        ESP_LOGE(TAG, "Failed to initialize compressor relay");
        failCount++;
    }
    else {
        ESP_LOGD(TAG, "Compressor relay initialized successfully (Relay controller version: %s)", compressorRelay.singleRelayVersion());
        successCount++;
        setCompressorState(false);
    }

    if(!amplifierRelay.begin(hardware::i2c())) {
        ESP_LOGE(TAG, "Failed to initialize amplifier relay");
        failCount++;
    }
    else {
        ESP_LOGD(TAG, "Amplifier relay initialized successfully (Relay controller version: %s)", amplifierRelay.singleRelayVersion());
        successCount++;
        setAmplifierState(false);
    }

    sInitialized = true;

    if(failCount > 0) {
        ESP_LOGE(TAG, "%i relay(s) failed to initialize (%i were successful)", failCount, successCount);
        return module::MODULE_INIT_HARDWARE_ERROR;
    }
    else {
        ESP_LOGI(TAG, "All %i relays initialized successfully!", successCount);
        return module::MODULE_INIT_SUCCESS;
    }
}

void enableMock() {
    sMockEnabled = true;
    ESP_LOGI(TAG, "Mock enabled");
}

void disableMock() {
    sMockEnabled = false;
    ESP_LOGI(TAG, "Mock disabled");
}

void setCompressorState(bool on) {
    if (!sInitialized) {
        ESP_LOGD(TAG, "setCompressorState called before init — ignored");
        return;
    }
    if (sMockEnabled) {
        ESP_LOGD(TAG, "Mocking compressor state to %s", on ? "ON" : "OFF");
        sMockCompressorState = on;
        return;
    }
    if (on == getCompressorState()) {
        ESP_LOGD(TAG, "Compressor state is already %s", on ? "ON" : "OFF");
        return;
    }
    ESP_LOGD(TAG, "Setting compressor state to %s", on ? "ON" : "OFF");
    if(on) {
        compressorRelay.turnRelayOn();
    } else {
        compressorRelay.turnRelayOff();
    }
}


void setAmplifierState(bool on) {
    if (!sInitialized) {
        ESP_LOGD(TAG, "setAmplifierState called before init — ignored");
        return;
    }
    if (sMockEnabled) {
        ESP_LOGD(TAG, "Mocking amplifier state to %s", on ? "ON" : "OFF");
        sMockAmplifierState = on;
        return;
    }
    if (on == getAmplifierState()) {
        ESP_LOGD(TAG, "Amplifier state is already %s", on ? "ON" : "OFF");
        return;
    }
    ESP_LOGD(TAG, "Setting amplifier state to %s", on ? "ON" : "OFF");
    if(on) {
        amplifierRelay.turnRelayOn();
    } else {
        amplifierRelay.turnRelayOff();
    }
}

bool getCompressorState() {
    if (sMockEnabled)  return sMockCompressorState;

    return compressorRelay.getState();
}

bool getAmplifierState() {
    if (sMockEnabled)  return sMockAmplifierState;
    return amplifierRelay.getState();
}

bool isMockEnabled() {
    return sMockEnabled;
}

} // namespace relay
