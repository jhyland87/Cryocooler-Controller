/**
 * @file cooling.cpp
 * @brief AD9833 DDS waveform generator implementation
 */

#include <Arduino.h>
#include "state_machine.h"
#include "cooling.h"
#include "config.h"
#include "esp_log.h"
#include "sensor_mock.h"


namespace cooling {

static constexpr char TAG[] = "cooling";

static volatile bool    enabled_ = false;
static volatile bool    coolingPumpOn_ = false;
static volatile float    coolantTemperature_ = 0.0f;
static volatile float    coolantFlowRate_ = 0.0f;
static volatile uint8_t    fanSpeed_ = 0;
static volatile bool    forceFanSpeed_ = false;
static constexpr int freq       = 25000;
static constexpr int resolution = 8;
const long interval = 1000;  // Calculate RPM every 1 second
volatile int pulseCount = 0;
void IRAM_ATTR countPulses() {
  pulseCount = pulseCount+1;
}


uint32_t lastCheckCycleMs = millis();

module::InitStatus init() {
  pinMode(COOLING_INHIBIT_PIN, OUTPUT);
  digitalWrite(COOLING_INHIBIT_PIN, LOW);

  ledcAttach(COOLING_FAN_PWM_PIN, freq, resolution);
  setFanSpeed(0); // Force fan to 0% on startup

  pinMode(COOLING_FAN_TACHO_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(COOLING_FAN_TACHO_PIN), countPulses, FALLING);

  return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
  //ESP_LOGD(TAG, "Checking cooling system");
  const uint32_t nowMs = millis();
  if (nowMs - lastCheckCycleMs < COOLING_CHECK_CYCLE_MS) {
    return module::MODULE_SERVICE_SKIPPED;
  }
  lastCheckCycleMs = nowMs;

  // // If the coolant temp is dipped below the min, then disable the cooling system.
  // if (getCoolantTemperature() < COOLING_OFF_BELOW_COOLANT_TEMP && isEnabled()) {
  //   disable();
  //   return module::MODULE_SERVICE_OK;
  // }

  // if (fanSpeed_ == 0 && !coolingPumpOn_ && enabled_) {
  //   enabled_ = false;
  // }

  // // If the cryocooler has turned on and autostart is enabled, then enable the cooling system
  // // (regardless of the temperature of the coolant).
  // if (!isEnabled() && state_machine::isRunning() && COOLING_AUTOSTART_ENABLED) {
  //   enable();
  // }

  return module::MODULE_SERVICE_OK;
}

bool isCoolingPumpOn() {
  return coolingPumpOn_;
}

bool isCoolingFanOn() {
  return fanSpeed_ > 0;
}

float getCoolantTemperature() {
  return coolantTemperature_;
}

float getCoolantFlowRate() {
  return coolantFlowRate_;
}

uint8_t getFanSpeed() {
  if ( sensor_mock::isActive() ) {
    return fanSpeed_;
  }
  return (pulseCount / 2) * 60 / interval;
}

void setFanSpeed(uint8_t percentage, bool force) {
  if (forceFanSpeed_ && !force) {
    ESP_LOGD(TAG, "Fan speed already set to %d, not changing (force = %d)", fanSpeed_, force);
    return;
  }
  forceFanSpeed_ = force;
  fanSpeed_ = constrain(percentage, 0, COOLING_FAN_MAX_SPEED);
  int duty = map(fanSpeed_, 0, COOLING_FAN_MAX_SPEED, 0, 255);
  ESP_LOGD(TAG, "Setting fan speed to %d (duty = %d, force = %d)", fanSpeed_, duty, force);
  ledcWrite(COOLING_FAN_PWM_PIN, duty);
}

void enable()    {
  ESP_LOGD(TAG, "Enabling cooling system");
  enabled_ = true;
  coolingPumpOn_ = true;
  digitalWrite(COOLING_INHIBIT_PIN, HIGH);
  setFanSpeed(25);
}

void disable()   {
  ESP_LOGD(TAG, "Disabling cooling system");
  enabled_ = false;
  coolingPumpOn_ = false;
  digitalWrite(COOLING_INHIBIT_PIN, LOW);
  setFanSpeed(0);
}
bool isEnabled() { return enabled_; }

} // namespace cooling
