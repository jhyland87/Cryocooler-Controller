/**
 * @file sysinfo.cpp
 * @brief Device voltage monitoring implementation
 */

#include <Arduino.h>
#include <Adafruit_INA260.h>

#include "pin_config.h"
#include "config.h"
#include "sysinfo.h"
#include "accelerometer.h"

// System voltage in volts
static float    voltageV         = 0.0f;
static float    currentA         = 0.0f;
static float    powerW           = 0.0f;

namespace sysinfo {

Adafruit_INA260 ina260 = Adafruit_INA260();


module::InitStatus init() {
    if (!ina260.begin()) {
        Serial.println("[sysinfo] Couldn't find INA260 chip");
        while (1);
    }

    Serial.println("[sysinfo] INA260 found and initialized");
    analogReadResolution(ADC_RESOLUTION);
    return module::MODULE_INIT_SUCCESS;
}


module::ServiceStatus service() {
    voltageV = ina260.readBusVoltage()/1000.0f;
    currentA = ina260.readCurrent()/1000.0f;
    powerW = ina260.readPower()/1000.0f;
    return module::MODULE_SERVICE_OK;
}

float getVoltage() {
    return voltageV;
}

float getCurrent() {
    return currentA;
}

float getPower() {
    return powerW;
}

float getAmbientTemperature() {
    return accelerometer::getTemperature();
}
} // namespace sysinfo
