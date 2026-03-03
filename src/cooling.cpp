/**
 * @file cooling.cpp
 * @brief Cooling system — fan controller and pump management.
 *
 * The EMC2101 fan controller runs in LUT (Lookup Table) mode: it reads its
 * temperature sensor and automatically sets the fan PWM duty cycle according
 * to the configured temperature→speed curve.  No software heartbeat is needed;
 * the IC owns the fan.
 *
 * Software responsibilities:
 *   - Configure and enable the LUT on init().
 *   - Track the pump enable state (no hardware GPIO yet — flag only).
 *   - Expose enable()/disable() for the pump; fan is IC-controlled.
 *   - Allow manual fan override via setFanSpeed(pct, force=true), which
 *     switches to manual mode.  enable() re-activates the LUT.
 */

#include <Arduino.h>
#include <Adafruit_EMC2101.h>
#include "cooling.h"
#include "config.h"
#include "esp_log.h"
#include "sensor_mock.h"
#include "module.h"
#include "hardware.h"


static Adafruit_EMC2101 fanController_;

namespace cooling {

static constexpr char TAG[] = "cooling";

// ---------------------------------------------------------------------------
// LUT configuration
//
// Eight entries mapping temperature (°C) → fan PWM (%).
// Must be sorted ascending by temperature.
// The IC uses the highest entry whose threshold ≤ current temperature.
// If temp < first threshold → IC uses entry 0 speed (minimum speed).
// If no external diode is connected, the IC reports a fault at 127 °C
// and applies the last (highest) entry — full speed, which is the safe
// default for a cryocooler compressor.
// ---------------------------------------------------------------------------
static constexpr struct { uint8_t tempC; uint8_t pwmPct; } kLut[] = {
    {  0,  2 },   //  0 °C →  50 % (minimum — keeps the fan spinning at all times)
    { 25,  4 },   // 25 °C →  55 %
    { 35,  6 },   // 35 °C →  60 %
    { 45,  8 },   // 45 °C →  65 %
    { 50,  10 },   // 50 °C →  75 %
    { 55,  12 },   // 55 °C →  85 %
    { 60,  14 },   // 60 °C →  95 %
    { 65,  16 },   // 65 °C → 100 %
};
static constexpr uint8_t kLutCount = static_cast<uint8_t>(sizeof(kLut) / sizeof(kLut[0]));
static_assert(kLutCount <= 8, "EMC2101 LUT has only 8 entries");

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------
static volatile bool    enabled_        = false;
static volatile bool    coolingPumpOn_  = false;
static volatile float   coolantTemperature_ = 0.0f;
static volatile float   coolantFlowRate_    = 0.0f;
static volatile uint8_t fanSpeed_   = 0;      // only meaningful in manual-override mode
static volatile bool    forceFanSpeed_ = false;

uint32_t lastCheckCycleMs = millis();


// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------
module::InitStatus init() {
  ESP_LOGD(TAG, "Initializing cooling system");

  if (!fanController_.begin(EMC2101_I2CADDR_DEFAULT, &hardware::i2c())) {
    ESP_LOGE(TAG, "Failed to find EMC2101 chip");
    return module::MODULE_INIT_HARDWARE_ERROR;
  }

  // begin() → _init() leaves the IC in manual mode (LUT disabled, duty=100%).
  // Log its state so we can confirm I2C is working.
  ESP_LOGD(TAG, "init: post-begin LUT=%s dutyCycle=%u%% internalTemp=%d°C rpm=%u",
           fanController_.LUTEnabled() ? "ENABLED" : "disabled",
           fanController_.getDutyCycle(),
           fanController_.getInternalTemperature(),
           fanController_.getFanRPM());

  // _init() configures the clock as: configPWMClock(clksel=1→1.4 kHz) + setPWMFrequency(0x1F)
  // → 1400 / (2 * 32) ≈ 22 Hz — far too slow for a standard 4-wire PWM fan (spec: 25 kHz).
  // Low PWM frequency causes many fans to stall at partial duty cycles even though they
  // spin fine at 100 %.  Reconfigure for ~25.7 kHz:
  //   360 kHz base clock,  FDIV = 6  →  360 000 / (2 * (6+1)) = 25 714 Hz ≈ 25.7 kHz
  if (!fanController_.configPWMClock(false, false)) {          // select 360 kHz base clock
    ESP_LOGW(TAG, "init: configPWMClock failed");
  }
  if (!fanController_.setPWMFrequency(6)) {                    // 360 kHz / 14 ≈ 25.7 kHz
    ESP_LOGW(TAG, "init: setPWMFrequency failed");
  }
  ESP_LOGD(TAG, "init: PWM clock reconfigured: 360 kHz base, FDIV=6 → ~25.7 kHz");

  // Program the LUT entries.  setLUT() temporarily disables the LUT while
  // writing each entry, then restores the previous LUT state.
  for (uint8_t i = 0; i < kLutCount; ++i) {
    if (!fanController_.setLUT(i, kLut[i].tempC, kLut[i].pwmPct)) {
      ESP_LOGW(TAG, "init: setLUT(%u, %u°C, %u%%) failed", i, kLut[i].tempC, kLut[i].pwmPct);
    }
  }

  // Configure spinup: drive at 100 % for 3.2 s whenever the fan transitions
  // from stopped (0 %) to a non-zero target.  This overcomes static friction
  // that prevents the fan from starting at low duty cycles.
  // spinup_drive = 2 → 100 %,  spinup_time = 6 → 3.2 s
  if (!fanController_.configFanSpinup(2, 6)) {
    ESP_LOGW(TAG, "init: configFanSpinup failed");
  }

  // Enable LUT — the IC takes over fan control from here.
  if (!fanController_.LUTEnabled(true)) {
    ESP_LOGW(TAG, "init: LUTEnabled(true) failed");
  }

  enabled_       = true;
  coolingPumpOn_ = true;
  fanSpeed_      = 0;    // IC-controlled; track as 0 in manual-mode terms
  forceFanSpeed_ = false;
  enable();
  ESP_LOGD(TAG, "init: LUT configured (%u entries), IC fan control active", kLutCount);
  ESP_LOGD(TAG, "init: post-LUT LUT=%s internalTemp=%d°C externalTemp=%f°C rpm=%u",
           fanController_.LUTEnabled() ? "ENABLED" : "disabled",
           fanController_.getInternalTemperature(),
           fanController_.getExternalTemperature(),
           fanController_.getFanRPM());

  return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// service
// ---------------------------------------------------------------------------
module::ServiceStatus service() {
  const uint32_t nowMs = millis();
  if (nowMs - lastCheckCycleMs < COOLING_CHECK_CYCLE_MS) {
    return module::MODULE_SERVICE_SKIPPED;
  }
  lastCheckCycleMs = nowMs;

  // Log the IC state each tick for monitoring.  The IC manages the fan; we
  // just observe and surface the data.  RPM is not logged — TACH is non-functional.
  const uint8_t dc      = fanController_.getDutyCycle();
  const int8_t  intTemp = fanController_.getInternalTemperature();
  const bool    lutOn   = fanController_.LUTEnabled();

  ESP_LOGD(TAG, "service: enabled=%d LUT=%s dutyCycle=%u%% intTemp=%d°C externalTemp=%f°C rpm=%u",
           static_cast<int>(enabled_),
           lutOn ? "on" : "off(manual)",
           dc, intTemp,
           fanController_.getExternalTemperature(),
           fanController_.getFanRPM());

  return module::MODULE_SERVICE_OK;
}

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------
bool    isCoolingPumpOn()       { return coolingPumpOn_; }
// isCoolingFanOn uses duty cycle rather than RPM because the TACH signal
// may not be connected, causing getFanRPM() to always return 0 even when
// the fan is spinning.  A non-zero duty cycle is the reliable proxy.
bool    isCoolingFanOn()        { return fanController_.getDutyCycle() > 0; }
float   getCoolantTemperature() { return coolantTemperature_; }
float   getCoolantFlowRate()    { return coolantFlowRate_; }

uint8_t getFanSpeed() {
  if (sensor_mock::isActive()) {
    return fanSpeed_;
  }
  return fanController_.getDutyCycle();
}

uint16_t getFanRPM() {
  return fanController_.getFanRPM();
}

// ---------------------------------------------------------------------------
// setFanSpeed — manual override
//
// With force=true: disables LUT and drives the fan at the given percentage
// until enable() is called (which re-activates the LUT).
// With force=false: no-op while LUT is active; the IC controls the speed.
// ---------------------------------------------------------------------------
void setFanSpeed(uint8_t percentage, bool force) {
  if (!force) {
    ESP_LOGD(TAG, "setFanSpeed(%u): ignored — LUT is active (use force=true to override)", percentage);
    return;
  }

  ESP_LOGI(TAG, "setFanSpeed(%u): manual override — disabling LUT", percentage);
  forceFanSpeed_ = true;

  if (!fanController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "setFanSpeed: LUTEnabled(false) failed");
  }
  if (!fanController_.setDutyCycle(percentage)) {
    ESP_LOGW(TAG, "setFanSpeed: setDutyCycle(%u) failed", percentage);
  }
  // Post-write LUTEnabled(false) to override setDutyCycle()'s LUT-state restore.
  if (!fanController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "setFanSpeed: LUTEnabled(false) post-write failed");
  }

  fanSpeed_ = percentage;
  ESP_LOGD(TAG, "setFanSpeed(%u): dutyCycle=%u%% LUT=%s",
           percentage, fanController_.getDutyCycle(),
           fanController_.LUTEnabled() ? "ENABLED(!)" : "disabled");
}

// ---------------------------------------------------------------------------
// enable / disable
// ---------------------------------------------------------------------------

/**
 * Activate the cooling system: turn on the pump and re-engage the IC's LUT
 * so the fan is temperature-controlled.  Safe to call when already enabled.
 */
void enable() {
  ESP_LOGI(TAG, "enable(): pump on, LUT fan control active");
  enabled_       = true;
  coolingPumpOn_ = true;
  forceFanSpeed_ = false;

  if (!fanController_.LUTEnabled(true)) {
    ESP_LOGW(TAG, "enable(): LUTEnabled(true) failed");
  }
  ESP_LOGD(TAG, "enable(): LUT=%s internalTemp=%d°C",
           fanController_.LUTEnabled() ? "on" : "off(!)",
           fanController_.getInternalTemperature());
}

/**
 * Deactivate the cooling system: turn off the pump and stop the fan.
 * LUT is disabled; the fan will not restart until enable() is called.
 */
void disable() {
  ESP_LOGI(TAG, "disable(): pump off, fan stopped");
  enabled_       = false;
  coolingPumpOn_ = false;
  forceFanSpeed_ = false;

  if (!fanController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "disable(): LUTEnabled(false) failed");
  }
  if (!fanController_.setDutyCycle(0)) {
    ESP_LOGW(TAG, "disable(): setDutyCycle(0) failed");
  }
  // Post-write LUTEnabled(false) to override setDutyCycle()'s LUT-state restore.
  if (!fanController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "disable(): LUTEnabled(false) post-write failed");
  }
  ESP_LOGD(TAG, "disable(): dutyCycle=%u%% LUT=%s",
           fanController_.getDutyCycle(),
           fanController_.LUTEnabled() ? "ENABLED(!)" : "disabled");
}

bool isEnabled() { return enabled_; }

} // namespace cooling
