/**
 * @file waveform.cpp
 * @brief AD9833 DDS waveform generator implementation
 */

#include <Arduino.h>

#include "pin_config.h"
#include "config.h"
#include "device.h"

// System voltage in volts
static float    voltageV         = 0.0f;
static int  voltageRaw       = 0;

namespace device {

void init() {
    analogReadResolution(ADC_RESOLUTION);
}


void service() {
    voltageRaw = analogRead(VOLTAGE_12_TEST_PIN);
    // Scale the raw voltage to the actual voltage (given the voltage divider ratio);
    voltageV = map(voltageRaw, 0, 4095, 0, 19200)/1000.0f;
    //Serial.print(voltageRaw);
    //Serial.printf(" - Voltage: %.3f V (%d raw)\n", voltageV, voltageRaw);
}

float getVoltage() {
    return voltageV;
}

int16_t getVoltageRaw() {
    return voltageRaw;
}

} // namespace device
