/**
 * @file sysinfo.cpp
 * @brief Device voltage monitoring implementation
 */

#include <Arduino.h>
#include <Adafruit_INA260.h>
#include "config.h"
#include "sysinfo.h"
#include "hardware.h"
#include "imu.h"
#include "driver/i2c_master.h"
#include "sensor_mock.h"

// System voltage in volts
static float    voltageV         = 0.0f;
static float    currentA         = 0.0f;
static float    powerW           = 0.0f;

namespace sysinfo {

Adafruit_INA260 ina260 = Adafruit_INA260();


module::InitStatus init() {
    Serial.println(F("[sysinfo] Looking for INA260 chip..."));

    TwoWire& i2c = hardware::i2c();

    for (uint8_t attempt = 0; attempt < 2; ++attempt) {
        if (ina260.begin(INA260_I2CADDR_DEFAULT, &i2c)) {
            Serial.println(F("[sysinfo] INA260 chip found and initialized"));
            analogReadResolution(ADC_RESOLUTION);
            return module::MODULE_INIT_SUCCESS;
        }
        delay(100);
    }

    Serial.println(F("[sysinfo] INA260 chip not found after 10 attempts"));
    return module::MODULE_INIT_HARDWARE_ERROR;
}


module::ServiceStatus service() {
    if (sensor_mock::isActive()) {
        const auto& mo = sensor_mock::get();
        setLastReadings(mo.voltageV, mo.currentA, mo.voltageV * mo.currentA);
        return module::MODULE_SERVICE_OK;
    }
    voltageV = ina260.readBusVoltage()/1000.0f;
    currentA = ina260.readCurrent()/1000.0f;
    powerW   = ina260.readPower()/1000.0f;
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
    return imu::getTemperature();
}

void setLastReadings(float v, float a, float w) {
    voltageV = v;
    currentA = a;
    powerW   = w;
}
} // namespace sysinfo
