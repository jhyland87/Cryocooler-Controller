/**
 * @file amplifier.cpp
 * @brief amplifier control implementation
 *
 * Controls the amplifier connected to the cold head.
 */

 #include <Arduino.h>
 #include <Adafruit_MAX31865.h>
 #include <RunningAverage.h>
 #include <ACS37800.h>

 #include "pin_config.h"
 #include "config.h"
 #include "amplifier.h"
 #include "conversions.h"
 #include "module.h"
 #include "imu.h"
 #include "sensor_mock.h"
 #include "hardware.h"
// ---------------------------------------------------------------------------
// Module-private types and state
// ---------------------------------------------------------------------------

static module::InitStatus initStatus = module::MODULE_INIT_NOT_STARTED;
static module::ServiceStatus serviceStatus = module::MODULE_SERVICE_NOT_STARTED;
static bool enabled = false;
// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace amplifier {

module::InitStatus init() {
    if (!checkDependencies() && !sensor_mock::isActive()) {
        initStatus = module::MODULE_INIT_DEPENDENCY_ERROR;
        return initStatus;
    }

    Serial.println(F("[amplifier] Initializing ACS37800..."));

    initStatus = module::MODULE_INIT_SUCCESS;
    return initStatus;
}


bool checkDependencies(){
  return true;
}

bool isEnabled(){
  return enabled;
}

void setFrequency(float frequencyHz){
  // TODO: Implement
}

float getFrequency(){
  return 0.0f;
}

void enable(){
  enabled = true;
}

void disable(){
  enabled = false;
}

float getLastRmsVoltageV(){
  return 0.0f;
}

float getLastRmsCurrentA(){
  return 0.0f;
}

void setRmsVoltage(float rmsVoltageV){
  // TODO: Implement
}

void rampToVoltageV(float targetVoltageV){
  // TODO: Implement
}

void rampTowardShutdown(float targetVoltageV){
  // TODO: Implement
}

float getCurrentVoltage(){
  return 0.0f;
}

} // namespace amplifier
