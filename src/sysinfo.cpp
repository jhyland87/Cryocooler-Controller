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
#include "sensor_mock.h"

// System voltage in millivolts
static float    voltage         = 0.0f;
static float    current         = 0.0f;
static float    power           = 0.0f;

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
        setLastReadings(mo.voltage, mo.current, mo.voltage * mo.current);
        return module::MODULE_SERVICE_OK;
    }
    voltage = ina260.readBusVoltage();
    current = ina260.readCurrent();
    power   = ina260.readPower();
    return module::MODULE_SERVICE_OK;
}

float getVoltage() {
    return voltage;
}

float getCurrent() {
    return current;
}

float getPower() {
    return power;
}

float getAmbientTemperature() {
    return imu::getTemperature();
}

void setLastReadings(float v, float a, float w) {
    voltage = v;
    current = a;
    power   = w;
}
} // namespace sysinfo
