/**
 * @file cooling.cpp
 * @brief AD9833 DDS waveform generator implementation
 */

#include <Arduino.h>
#include "state_machine.h"
#include "cooling.h"
#include "config.h"

namespace cooling {

static volatile bool    enabled_ = false;
static volatile bool    coolingPumpOn_ = false;
static volatile bool    coolingFanOn_ = false;
static volatile float    coolantTemperature_ = 0.0f;
static volatile float    coolantFlowRate_ = 0.0f;
static volatile float    fanRPM_ = 0.0f;
uint32_t lastCheckCycleMs = millis();

module::InitStatus init() {
    return module::MODULE_INIT_SUCCESS;
}

void service() {
  const uint32_t nowMs = millis();
  if (nowMs - lastCheckCycleMs < COOLANT_CHECK_CYCLE_MS) {
    return;
  }
  lastCheckCycleMs = nowMs;


  // If the coolnt temp is dipped below the min, then disable the cooling system.
  if (getCoolantTemperature() < COOLANT_OFF_BELOW_TEMP && isEnabled()) {
    disable();
    return;
  }

  if ( !coolingFanOn_ && !coolingPumpOn_ && enabled_) {
    enabled_ = false;
  }

  // If the cryocooler has turned on and autostart is enabled, then enable the cooling system
  // (regardless of the temperature of the coolant);
  if (!Module::isEnabled() && state_machine::isRunning() && COOLANT_AUTOSTART_ENABLED) {
    enable();
  }


}

bool isCoolingPumpOn() {
  return coolingPumpOn_;
}

bool isCoolingFanOn() {
  return coolingFanOn_;
}

float getCoolantTemperature() {
  return coolantTemperature_;
}

float getCoolantFlowRate() {
  return coolantFlowRate_;
}

float getFanRPM() {
  return fanRPM_;
}

void setFanRPM(float rpm) {
  fanRPM_ = rpm;
}


void enable()    { enabled_ = true; coolingPumpOn_ = true; coolingFanOn_ = true; }
void disable()   { enabled_ = false; coolingPumpOn_ = false; coolingFanOn_ = false; }
bool isEnabled() { return enabled_; }

} // namespace cooling
