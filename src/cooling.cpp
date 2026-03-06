/**
 * @file cooling.cpp
 * @brief Cooling system — fan controller, pump management, and coolant sensors.
 *
 * The EMC2101 fan controller runs in LUT (Lookup Table) mode: it reads its
 * temperature sensor and automatically sets the fan PWM duty cycle according
 * to the configured temperature→speed curve.  No software heartbeat is needed;
 * the IC owns the fan.
 *
 * Coolant sensors (Alphacool ES High Flow + Temperature):
 *   - Temperature: NTC 10 kΩ thermistor read via a 3.3 V / 10 kΩ voltage
 *     divider on COOLING_TEMP_ADC_PIN, converted with the Beta equation.
 *   - Flow rate:   Hall-effect RPM pulse on COOLING_FLOW_PIN, converted to
 *     L/min via the Alphacool lookup table (RPM → L/h → L/min).
 *
 * Both channels are oversampled / averaged (running average over a 10 s
 * window) to suppress noise before the tracking monitors see them.
 *
 * Software responsibilities:
 *   - Configure and enable the LUT on init().
 *   - Track the pump enable state (no hardware GPIO yet — flag only).
 *   - Expose enable()/disable() for the pump; fan is IC-controlled.
 *   - Allow manual fan override via setFanSpeed(pct, force=true), which
 *     switches to manual mode.  enable() re-activates the LUT.
 *   - Sample coolant temperature and flow rate every COOLING_SENSOR_SAMPLE_MS.
 *   - Update tracking monitors every COOLING_CHECK_CYCLE_MS.
 */

#include <Arduino.h>
#include <Adafruit_EMC2101.h>
#include <RunningAverage.h>
#include <math.h>
#include "cooling.h"
#include "config.h"
#include "esp_log.h"
#include "sensor_mock.h"
#include "module.h"
#include "hardware.h"
#include "tracking.h"


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
// Flow lookup table (Alphacool ES, RPM → L/h)
//
// From the Alphacool ES manual; stored as {rpm, lph} pairs sorted ascending
// by RPM.  service() interpolates L/h from the measured RPM average, then
// converts to L/min for the tracking monitor and telemetry.
// ---------------------------------------------------------------------------
struct FlowPoint {
    uint16_t rpm;
    float    lph;
};

static constexpr FlowPoint kFlowTable[] = {
    {  327,  40.0f }, {  369,  50.0f }, {  404,  60.0f },
    {  449,  70.0f }, {  493,  80.0f }, {  510,  90.0f },
    {  560, 100.0f }, {  640, 110.0f }, {  700, 120.0f },
    {  737, 130.0f }, {  783, 140.0f }, {  850, 150.0f },
    {  960, 160.0f }, { 1034, 170.0f }, { 1064, 180.0f },
    { 1110, 190.0f }, { 1192, 200.0f }, { 1228, 210.0f },
    { 1275, 220.0f }, { 1322, 230.0f }, { 1398, 240.0f },
    { 1430, 250.0f }, { 1477, 260.0f }, { 1560, 270.0f },
    { 1608, 280.0f }, { 1640, 290.0f }, { 1685, 300.0f },
};
static constexpr uint8_t kFlowTableLen =
    static_cast<uint8_t>(sizeof(kFlowTable) / sizeof(kFlowTable[0]));

// ---------------------------------------------------------------------------
// Flow sensor ISR state
// ---------------------------------------------------------------------------
static volatile uint32_t flowPulseCount_ = 0;

void IRAM_ATTR onFlowPulse() {
    ++flowPulseCount_;
}

// ---------------------------------------------------------------------------
// Running averages (sensor noise rejection)
// ---------------------------------------------------------------------------
static RunningAverage rpmAvg_(COOLING_SENSOR_AVG_SAMPLES);
static RunningAverage tempAvg_(COOLING_SENSOR_AVG_SAMPLES);

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------
static volatile bool    enabled_        = false;
static volatile bool    coolingPumpOn_  = false;
static volatile float   coolantTemperature_ = 0.0f;
static volatile float   coolantFlowRate_    = 0.0f;
static volatile uint8_t fanSpeed_   = 0;      // only meaningful in manual-override mode
static volatile bool    forceFanSpeed_ = false;

// Cached EMC2101 readings — updated once per COOLING_CHECK_CYCLE_MS in
// service().  Accessors return these values instead of reading the IC live,
// which eliminates concurrent I2C transactions between the service loop and
// the telemetry emit path (the root cause of the Wire repeated-start error).
static uint8_t  cachedDutyCycle_ = 0u;
static uint16_t cachedFanRpm_    = 0u;

static uint32_t lastCheckCycleMs = 0;
static uint32_t lastSampleMs_    = 0;

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

// Fan duty-cycle tracker — only active in forced/manual mode.
// Reset to IN_RANGE while the LUT is in control (no explicit setpoint).
static TrackingMonitor<float> fanTracker_(TrackingMonitor<float>::Config{
    /* hysteresis     */ COOLING_FAN_TRACK_HYSTERESIS_PCT,
    /* fullScale      */ COOLING_FAN_TRACK_FULL_SCALE_PCT,
    /* warningDelayMs */ COOLING_FAN_TRACK_WARNING_MS,
    /* faultDelayMs   */ COOLING_FAN_TRACK_FAULT_MS,
    /* tag            */ TAG,
    /* label          */ "fan speed",
});

// Coolant temperature tracker — only updated when the sensor is connected
// (coolantTemperature_ > 0).  Compares against the nominal operating temp.
static TrackingMonitor<float> coolantTempTracker_(TrackingMonitor<float>::Config{
    /* hysteresis     */ COOLING_COOLANT_TRACK_HYSTERESIS_C,
    /* fullScale      */ COOLING_COOLANT_TRACK_FULL_SCALE_C,
    /* warningDelayMs */ COOLING_COOLANT_TRACK_WARNING_MS,
    /* faultDelayMs   */ COOLING_COOLANT_TRACK_FAULT_MS,
    /* tag            */ TAG,
    /* label          */ "coolant temperature",
});

// Coolant flow rate tracker — only updated when the pump is on and the flow
// sensor is returning a non-zero reading.
static TrackingMonitor<float> flowTracker_(TrackingMonitor<float>::Config{
    /* hysteresis     */ COOLING_FLOW_TRACK_HYSTERESIS_LPM,
    /* fullScale      */ COOLING_FLOW_TRACK_FULL_SCALE_LPM,
    /* warningDelayMs */ COOLING_FLOW_TRACK_WARNING_MS,
    /* faultDelayMs   */ COOLING_FLOW_TRACK_FAULT_MS,
    /* tag            */ TAG,
    /* label          */ "coolant flow",
});

// ---------------------------------------------------------------------------
// rpmToLph — linear interpolation over the Alphacool flow lookup table
//
// Returns 0 for non-positive RPM.
// Extrapolates linearly below the table minimum down to 0 L/h.
// Clamps to the table maximum above it.
// ---------------------------------------------------------------------------
static float rpmToLph(float rpm) {
    if (rpm <= 0.0f) return 0.0f;

    // Below minimum — extrapolate toward zero
    if (rpm < static_cast<float>(kFlowTable[0].rpm)) {
        const float slope = (kFlowTable[1].lph - kFlowTable[0].lph) /
                            static_cast<float>(kFlowTable[1].rpm - kFlowTable[0].rpm);
        const float val = kFlowTable[0].lph +
                          slope * (rpm - static_cast<float>(kFlowTable[0].rpm));
        return (val > 0.0f) ? val : 0.0f;
    }

    // Above maximum — clamp
    if (rpm >= static_cast<float>(kFlowTable[kFlowTableLen - 1u].rpm)) {
        return kFlowTable[kFlowTableLen - 1u].lph;
    }

    // Binary search for the surrounding bracket
    uint8_t lo = 0u;
    uint8_t hi = kFlowTableLen - 1u;
    while (hi - lo > 1u) {
        const uint8_t mid = static_cast<uint8_t>((lo + hi) / 2u);
        if (static_cast<float>(kFlowTable[mid].rpm) <= rpm) lo = mid;
        else                                                 hi = mid;
    }

    const float t = (rpm - static_cast<float>(kFlowTable[lo].rpm)) /
                    static_cast<float>(kFlowTable[hi].rpm - kFlowTable[lo].rpm);
    return kFlowTable[lo].lph + t * (kFlowTable[hi].lph - kFlowTable[lo].lph);
}

// ---------------------------------------------------------------------------
// readCoolantTemp — NTC Beta-equation temperature conversion
//
// Oversamples the ADC COOLING_TEMP_OVERSAMPLE times for noise reduction.
// Returns -999 °C on open/short circuit (sensor not connected).
// ---------------------------------------------------------------------------
static float readCoolantTemp() {
    uint32_t adcSum = 0u;
    for (uint8_t i = 0u; i < COOLING_TEMP_OVERSAMPLE; ++i) {
        adcSum += static_cast<uint32_t>(analogRead(COOLING_TEMP_ADC_PIN));
    }
    const float adcAvg = static_cast<float>(adcSum) /
                         static_cast<float>(COOLING_TEMP_OVERSAMPLE);

    const float vAdc = (adcAvg / COOLING_TEMP_ADC_RESOLUTION) * COOLING_TEMP_ADC_VREF;

    // Guard: reject open (vAdc ≈ 0) or short (vAdc ≈ supply)
    if (vAdc <= 0.01f || vAdc >= COOLING_TEMP_SUPPLY_V - 0.01f) {
        return -999.0f;
    }

    // Voltage divider → sensor resistance:
    //   vAdc = vSupply × R_sensor / (R_ref + R_sensor)
    //   R_sensor = R_ref × vAdc / (vSupply − vAdc)
    const float rSensor = COOLING_TEMP_REF_RESISTOR * vAdc /
                          (COOLING_TEMP_SUPPLY_V - vAdc);

    // Beta equation: 1/T = 1/T0 + (1/β) × ln(R/R0)
    const float tempK = 1.0f / (1.0f / COOLING_TEMP_T0 +
                                (1.0f / COOLING_TEMP_BETA) *
                                logf(rSensor / COOLING_TEMP_R0));

    return tempK - 273.15f;
}

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
  for (uint8_t i = 0u; i < kLutCount; ++i) {
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

  // ── Coolant sensor setup ───────────────────────────────────────────────────

  // Flow sensor: interrupt on the falling edge of each Hall-effect pulse.
  // External 10 kΩ pull-up to 3.3 V is recommended; INPUT_PULLUP is the backup.
  rpmAvg_.clear();
  flowPulseCount_ = 0u;
  pinMode(COOLING_FLOW_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(COOLING_FLOW_PIN), onFlowPulse, FALLING);

  // Temperature ADC: 12-bit, full 0–3.3 V range (ADC_11db attenuation).
  tempAvg_.clear();
  analogReadResolution(ADC_RESOLUTION);
  analogSetPinAttenuation(COOLING_TEMP_ADC_PIN, ADC_11db);

  const uint32_t nowMs = millis();
  lastSampleMs_    = nowMs;
  lastCheckCycleMs = nowMs;

  enabled_       = true;
  coolingPumpOn_ = true;
  fanSpeed_      = 0u;   // IC-controlled; track as 0 in manual-mode terms
  forceFanSpeed_ = false;
  enable();

  ESP_LOGD(TAG, "init: LUT configured (%u entries), IC fan control active", kLutCount);
  ESP_LOGD(TAG, "init: post-LUT LUT=%s internalTemp=%d°C externalTemp=%f°C rpm=%u",
           fanController_.LUTEnabled() ? "ENABLED" : "disabled",
           fanController_.getInternalTemperature(),
           fanController_.getExternalTemperature(),
           fanController_.getFanRPM());
  ESP_LOGD(TAG, "init: flow sensor GPIO%d, temp ADC GPIO%d",
           COOLING_FLOW_PIN, COOLING_TEMP_ADC_PIN);

  return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// service
// ---------------------------------------------------------------------------
module::ServiceStatus service() {
  const uint32_t nowMs = millis();
  bool didWork = false;

  // ── 100 ms sensor sampling ──────────────────────────────────────────────
  // Skipped in mock mode — coolantTemperature_ / coolantFlowRate_ remain
  // at whatever the mock layer last wrote (0 by default, keeping the
  // tracking monitors in their reset state).
  if (!sensor_mock::isActive() &&
      (nowMs - lastSampleMs_) >= COOLING_SENSOR_SAMPLE_MS) {

    const uint32_t elapsed = nowMs - lastSampleMs_;
    lastSampleMs_ = nowMs;

    // Temperature ──────────────────────────────────────────────────────────
    const float tempC = readCoolantTemp();
    if (tempC > -999.0f) {
      tempAvg_.addValue(tempC);
      coolantTemperature_ = tempAvg_.getAverage();
    }

    // Flow rate (RPM → L/min) ──────────────────────────────────────────────
    // Atomically snapshot and reset the ISR pulse counter.
    noInterrupts();
    const uint32_t pulses = flowPulseCount_;
    flowPulseCount_ = 0u;
    interrupts();

    // RPM = (pulses / pulsesPerRev) / (elapsed_ms / 60 000)
    const float sampledRpm =
        (static_cast<float>(pulses) /
         static_cast<float>(COOLING_FLOW_PULSES_PER_REV)) /
        (static_cast<float>(elapsed) / 60000.0f);

    rpmAvg_.addValue(sampledRpm);

    // Convert average RPM → L/h → L/min
    coolantFlowRate_ = rpmToLph(rpmAvg_.getAverage()) / 60.0f;

    didWork = true;
  }

  // ── 1000 ms tracker update ──────────────────────────────────────────────
  if ((nowMs - lastCheckCycleMs) < COOLING_CHECK_CYCLE_MS) {
    return didWork ? module::MODULE_SERVICE_OK : module::MODULE_SERVICE_SKIPPED;
  }

  lastCheckCycleMs = nowMs;
  didWork = true;

  // Snapshot all EMC2101 values in one place.  Accessors (getFanSpeed,
  // isCoolingFanOn, getFanRPM) return these cached copies so that the
  // telemetry emit path never touches the I2C bus outside this function.
  cachedDutyCycle_ = fanController_.getDutyCycle();
  cachedFanRpm_    = fanController_.getFanRPM();
  const uint8_t dc = cachedDutyCycle_;

  // Fan speed tracker: only meaningful in forced/manual mode.
  // In LUT mode the IC owns the duty cycle — no external setpoint exists.
  if (forceFanSpeed_) {
      fanTracker_.update(static_cast<float>(fanSpeed_),
                         static_cast<float>(dc), nowMs);
  } else {
      fanTracker_.reset();
  }

  // Coolant temperature tracker: only advance when the sensor is connected.
  // A reading of exactly 0 °C indicates the hardware is not yet wired up.
  if (coolantTemperature_ > 0.0f) {
      coolantTempTracker_.update(COOLING_COOLANT_NOMINAL_TEMP_C,
                                 coolantTemperature_, nowMs);
  } else {
      coolantTempTracker_.reset();
  }

  // Flow rate tracker: only advance when the pump is running and the flow
  // sensor is returning a non-zero reading.
  if (coolingPumpOn_ && coolantFlowRate_ > 0.0f) {
      flowTracker_.update(COOLING_FLOW_NOMINAL_LPM, coolantFlowRate_, nowMs);
  } else {
      flowTracker_.reset();
  }

  return module::MODULE_SERVICE_OK;
}

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------
bool    isCoolingPumpOn()       { return coolingPumpOn_; }
// isCoolingFanOn uses the cached duty cycle rather than live RPM because the
// TACH signal may not be connected, and we avoid live I2C reads in accessors.
bool    isCoolingFanOn()        { return cachedDutyCycle_ > 0; }
float   getCoolantTemperature() { return coolantTemperature_; }
float   getCoolantFlowRate()    { return coolantFlowRate_; }

uint8_t getFanSpeed() {
  return sensor_mock::isActive() ? fanSpeed_ : cachedDutyCycle_;
}

uint16_t getFanRPM() {
  return cachedFanRpm_;
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
  fanTracker_.reset();   // allow the fan time to reach the new speed
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

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

float getFanSpeedScore()                                { return fanTracker_.getScore();         }
TrackingMonitor<float>::State getFanSpeedTrackingState(){ return fanTracker_.getState();         }

float getCoolantTempScore()                                   { return coolantTempTracker_.getScore(); }
TrackingMonitor<float>::State getCoolantTempTrackingState()   { return coolantTempTracker_.getState(); }

float getCoolantFlowScore()                                   { return flowTracker_.getScore();        }
TrackingMonitor<float>::State getCoolantFlowTrackingState()   { return flowTracker_.getState();        }

float getWorstTrackingScore() {
    const float fanScore     = fanTracker_.getScore();
    const float coolantScore = coolantTempTracker_.getScore();
    const float flowScore    = flowTracker_.getScore();
    if (fanScore <= coolantScore && fanScore <= flowScore) return fanScore;
    if (coolantScore <= flowScore)                         return coolantScore;
    return flowScore;
}

TrackingMonitor<float>::State getWorstTrackingState() {
    // FAULT > WARNING > IN_RANGE
    using S = TrackingMonitor<float>::State;
    const auto a = fanTracker_.getState();
    const auto b = coolantTempTracker_.getState();
    const auto c = flowTracker_.getState();
    if (a == S::FAULT || b == S::FAULT || c == S::FAULT) return S::FAULT;
    if (a == S::WARNING || b == S::WARNING || c == S::WARNING) return S::WARNING;
    return S::IN_RANGE;
}

} // namespace cooling
