/**
 * @file sysinfo.cpp
 * @brief Device voltage monitoring implementation
 */

#include <Arduino.h>
#include <Adafruit_INA260.h>
#include <Wire.h>
#include <esp32-hal-i2c.h>
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
    int retries = 0;
    Serial.println(F("[sysinfo] Looking for INA260 chip..."));
    if ( i2cIsInit(INA260_I2CADDR_DEFAULT)) {
        Serial.println(F("[sysinfo] I2C bus already open, trying to reuse it"));
        while (!ina260.begin(INA260_I2CADDR_DEFAULT, &Wire) && retries < 10) {
            //Serial.print(".");
            retries++;
            delay(100);
        }
    }
    else {
        while (!ina260.begin() && retries < 10) {
            //Serial.print(".");
            retries++;
            delay(100);
        }
    }


    if (retries == 10) {
        Serial.println(F("[sysinfo] INA260 chip not found"));
        return module::MODULE_INIT_HARDWARE_ERROR;
    }

    Serial.println(F("[sysinfo] INA260 chip found and initialized"));
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
