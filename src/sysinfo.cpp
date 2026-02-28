/**
 * @file sysinfo.cpp
 * @brief Device voltage monitoring implementation
 */

#include <Arduino.h>

#include "pin_config.h"
#include "config.h"
#include "sysinfo.h"
#include "accelerometer.h"

// System voltage in volts
static float    voltageV         = 0.0f;
static int  voltageRaw       = 0;

namespace sysinfo {

module::InitStatus init() {
    analogReadResolution(ADC_RESOLUTION);
    return module::MODULE_INIT_SUCCESS;
}


module::ServiceStatus service() {
    voltageRaw = analogRead(VOLTAGE_12_TEST_PIN);
    // Scale the raw voltage to the actual voltage (given the voltage divider ratio);
    voltageV = map(voltageRaw, 0, 4095, 0, 19200)/1000.0f;
    //Serial.print(voltageRaw);
    //Serial.printf(" - Voltage: %.3f V (%d raw)\n", voltageV, voltageRaw);
    return module::MODULE_SERVICE_OK;
}

float getVoltage() {
    return voltageV;
}

int16_t getVoltageRaw() {
    return voltageRaw;
}

float getAmbientTemperature() {
    return accelerometer::getTemperature();
}
} // namespace sysinfo
