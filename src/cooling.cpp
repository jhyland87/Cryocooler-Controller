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
#include "conversions.h"
#include "esp_log.h"
#include "sensor_mock.h"
#include "module.h"
#include "hardware.h"
#include "tracking.h"
#include "logger.h"


static Adafruit_EMC2101 fanController_;
static Adafruit_EMC2101 pumpController_;

namespace cooling {
static LogStream _Log = Log.createChildLogger("cooling");

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
// Pump speed normalisation helpers
//
// All user-facing pump speeds are expressed in a normalised 0–100 % range.
// The actual EMC2101 hardware duty is 0–COOLING_PUMP_MAX_DUTY_PCT %.
// These two helpers convert at the boundary between application code and HW.
// ---------------------------------------------------------------------------
static uint8_t pumpNormToHw(uint8_t normPct) {
    return static_cast<uint8_t>(
        (static_cast<uint16_t>(normPct) * COOLING_PUMP_MAX_DUTY_PCT + 50u) / 100u);
}

static uint8_t pumpHwToNorm(uint8_t hwPct) {
    if (hwPct == 0u) return 0u;
    const uint8_t norm = static_cast<uint8_t>(
        (static_cast<uint16_t>(hwPct) * 100u + COOLING_PUMP_MAX_DUTY_PCT / 2u) / COOLING_PUMP_MAX_DUTY_PCT);
    return (norm > 100u) ? 100u : norm;
}

// ---------------------------------------------------------------------------
// Pump LUT configuration (forced-temperature mode)
//
// The pump EMC2101 uses setForcedTemperature() to receive the NTC-averaged
// coolant temperature from software.  Its LUT then maps that temperature
// to a pump PWM duty cycle autonomously.
//
// NOTE: This pump stalls above ~4400 RPM (~16 % hardware duty).
// Manual override testing showed:
//   hw  4 % → ~2360 RPM (steady)     hw 14 % → ~4160 RPM (steady)
//   hw  9 % → ~3280 RPM (steady)     hw 16 % → ~4400 RPM (stall limit)
//
// Values below are in **normalised 0–100 %** space.  pumpNormToHw()
// converts them to hardware duty (×0.16) when programming the EMC2101 LUT.
//
//   Index  Temp (°C)  Norm (%)  HW (%)  Est. RPM    Notes
//   ─────  ─────────  ────────  ──────  ────────    ──────────────────────
//     0       20         30       5     ~2360       Idle / cool — minimum
//     1       25         40       6     ~2720       Normal room temp
//     2       30         55       9     ~3280       Warm coolant
//     3       35         70      11     ~3620       Above ambient
//     4       40         85      14     ~4160       Hot — approaching limit
//     5       45        100      16     ~4400       Max — at the stall limit
// ---------------------------------------------------------------------------
static constexpr struct { uint8_t tempC; uint8_t pwmPct; } kPumpLut[] = {
    { 20,  30 },
    { 25,  40 },
    { 30,  55 },
    { 35,  70 },
    { 40,  85 },
    { 45, 100 },
};
static constexpr uint8_t kPumpLutCount = static_cast<uint8_t>(sizeof(kPumpLut) / sizeof(kPumpLut[0]));
static_assert(kPumpLutCount <= 8, "EMC2101 LUT has only 8 entries");

// ---------------------------------------------------------------------------
// Flow lookup table (Alphacool ES, RPM → L/h)
//
// From the Alphacool ES manual; stored as {rpm, lph} pairs sorted ascending
// by RPM.  service() interpolates L/h from the measured RPM average, then
// converts to L/min for the tracking monitor and telemetry.
// Above the table maximum, rpmToLph() extrapolates linearly up to COOLING_FLOW_MAX_LPH.
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
static RunningAverage rpmAvg_(COOLING_SENSOR_AVG_SAMPLES);   // coolant flow hall-effect RPM
static RunningAverage tempAvg_(COOLING_SENSOR_AVG_SAMPLES);  // coolant NTC temperature
// Pump RPM is read once per COOLING_CHECK_CYCLE_MS (1 s), so fewer samples
// are needed to match the same ~10 s smoothing window as the 100 ms sensors.
static RunningAverage pumpRpmAvg_(
    COOLING_SENSOR_AVG_SAMPLES / (COOLING_CHECK_CYCLE_MS / COOLING_SENSOR_SAMPLE_MS)
);  // pump EMC2101 TACH smoothing

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------
static volatile bool    enabled_            = false;
static volatile bool    coolingPumpOn_      = false;
static volatile float   coolantTemperature_ = 0.0f;
static volatile float   coolantFlowRate_    = 0.0f;
static volatile uint8_t fanSpeed_           = 0;      // only meaningful in manual-override mode
static volatile bool    forceFanSpeed_      = false;

// Cached EMC2101 readings — updated once per COOLING_CHECK_CYCLE_MS in
// service().  Accessors return these values instead of reading the IC live,
// which eliminates concurrent I2C transactions between the service loop and
// the telemetry emit path (the root cause of the Wire repeated-start error).
static uint8_t  cachedDutyCycle_      = 0u;
static uint16_t cachedFanRpm_         = 0u;

// Cached pump EMC2101 readings — same pattern as the fan controller.
static uint8_t  cachedPumpDutyCycle_  = 0u;
static uint16_t cachedPumpRpm_        = 0u;

static uint32_t lastCheckCycleMs      = 0;
static uint32_t lastSampleMs_         = 0;

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

    // Above maximum — extrapolate linearly, capped at pump max (COOLING_FLOW_MAX_LPH)
    if (rpm >= static_cast<float>(kFlowTable[kFlowTableLen - 1u].rpm)) {
        const uint8_t last = kFlowTableLen - 1u;
        const uint8_t prev = kFlowTableLen - 2u;
        const float slope = (kFlowTable[last].lph - kFlowTable[prev].lph) /
                            static_cast<float>(kFlowTable[last].rpm - kFlowTable[prev].rpm);
        const float val = kFlowTable[last].lph +
                          slope * (rpm - static_cast<float>(kFlowTable[last].rpm));
        return (val < COOLING_FLOW_MAX_LPH) ? val : COOLING_FLOW_MAX_LPH;
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
// TCA9548A I2C multiplexer — channel selection
//
// The TCA9548A is controlled by a single-byte I2C write: bit N enables
// downstream channel N.  We select exactly one channel at a time.
// Only the two EMC2101s are routed through the mux; all other I2C devices
// remain on the main bus.
// ---------------------------------------------------------------------------
static bool selectMuxChannel(uint8_t channel) {
    hardware::i2c().beginTransmission(TCA9548A_I2C_ADDRESS);
    hardware::i2c().write(static_cast<uint8_t>(1u << channel));
    const uint8_t err = hardware::i2c().endTransmission();
    if (err != 0) {
        ESP_LOGE(TAG, "TCA9548A channel select %u failed (I2C error %u)", channel, err);
        return false;
    }
    return true;
}

// Disconnect all downstream channels so the mux no longer adds bus
// capacitance / load to the shared I2C bus between cooling service cycles.
// Other devices (IMU, INA237, relays) communicate on the main bus without
// the extra electrical path through the mux's FET switches.
static void deselectMuxChannels() {
    hardware::i2c().beginTransmission(TCA9548A_I2C_ADDRESS);
    hardware::i2c().write(static_cast<uint8_t>(0x00));
    hardware::i2c().endTransmission();
}

// ---------------------------------------------------------------------------
// fanInit — configure the fan EMC2101 on TCA9548A channel 0
//
// The fan EMC2101 reads its own internal temperature sensor and drives the
// fan PWM duty cycle via its LUT.  No forced-temperature mode is used.
// ---------------------------------------------------------------------------
static module::InitStatus fanInit() {
  if (!selectMuxChannel(TCA9548A_CHANNEL_FAN)) {
    //ESP_LOGE(TAG, "fanInit: mux channel select failed");
    _Log.printf("fanInit: mux channel select failed\n");
    return module::MODULE_INIT_HARDWARE_ERROR;
  }

  if (!fanController_.begin(EMC2101_I2CADDR_DEFAULT, &hardware::i2c())) {
    //ESP_LOGE(TAG, "fanInit: failed to find fan EMC2101");
    _Log.printf("fanInit: failed to find fan EMC2101\n");
    return module::MODULE_INIT_HARDWARE_ERROR;
  }

  // begin() → _init() leaves the IC in manual mode (LUT disabled, duty=100%).
  ESP_LOGD(TAG, "fanInit: post-begin LUT=%s dutyCycle=%u%% internalTemp=%d°C rpm=%u",
           fanController_.LUTEnabled() ? "ENABLED" : "disabled",
           fanController_.getDutyCycle(),
           fanController_.getInternalTemperature(),
           fanController_.getFanRPM());

  // Reconfigure PWM clock for ~25.7 kHz (360 kHz base, FDIV=6).
  // The library default (~22 Hz) is far too slow for 4-wire PWM fans.
  if (!fanController_.configPWMClock(false, false)) {
    ESP_LOGW(TAG, "fanInit: configPWMClock failed");
  }
  if (!fanController_.setPWMFrequency(6)) {
    ESP_LOGW(TAG, "fanInit: setPWMFrequency failed");
  }
  ESP_LOGD(TAG, "fanInit: PWM clock reconfigured: 360 kHz base, FDIV=6 → ~25.7 kHz");

  // Program the fan LUT entries.
  for (uint8_t i = 0u; i < kLutCount; ++i) {
    if (!fanController_.setLUT(i, kLut[i].tempC, kLut[i].pwmPct)) {
      ESP_LOGW(TAG, "fanInit: setLUT(%u, %u°C, %u%%) failed", i, kLut[i].tempC, kLut[i].pwmPct);
    }
  }

  // Configure spinup: 100 % for 3.2 s to overcome static friction.
  if (!fanController_.configFanSpinup(2, 6)) {
    ESP_LOGW(TAG, "fanInit: configFanSpinup failed");
  }

  // Set LUT hysteresis to prevent the IC from rapidly hunting between adjacent
  // duty-cycle steps when the chip temperature oscillates around a threshold.
  fanController_.setLUTHysteresis(COOLING_FAN_LUT_HYSTERESIS_C);
  ESP_LOGD(TAG, "fanInit: LUT hyst = %u °C", fanController_.getLUTHysteresis());

  // Enable LUT — the IC takes over fan control from here.
  if (!fanController_.LUTEnabled(true)) {
    ESP_LOGW(TAG, "fanInit: LUTEnabled(true) failed");
  }

  ESP_LOGD(TAG, "fanInit: LUT configured (%u entries), IC fan control active", kLutCount);
  return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// pumpInit — configure the pump EMC2101 on TCA9548A channel 1
//
// The pump EMC2101 runs in forced-temperature LUT mode: software pushes the
// averaged NTC coolant temperature via setForcedTemperature() every 1000 ms,
// and the IC's LUT drives the pump PWM output accordingly.
// ---------------------------------------------------------------------------
static module::InitStatus pumpInit() {
  if (!selectMuxChannel(TCA9548A_CHANNEL_PUMP)) {
    //ESP_LOGE(TAG, "pumpInit: mux channel select failed");
    _Log.printf("pumpInit: mux channel select failed\n");
    return module::MODULE_INIT_HARDWARE_ERROR;
  }

  if (!pumpController_.begin(EMC2101_I2CADDR_DEFAULT, &hardware::i2c())) {
    //ESP_LOGE(TAG, "pumpInit: failed to find pump EMC2101");
    _Log.printf("pumpInit: failed to find pump EMC2101\n");
    return module::MODULE_INIT_HARDWARE_ERROR;
  }

  ESP_LOGD(TAG, "pumpInit: post-begin LUT=%s dutyCycle=%u%%",
           pumpController_.LUTEnabled() ? "ENABLED" : "disabled",
           pumpController_.getDutyCycle());

  // Start at a safe minimum duty until the LUT takes over.
  // COOLING_PUMP_INITIAL_DUTY_PCT is normalised (0–100 %); convert to HW duty.
  const uint8_t initHwDuty = pumpNormToHw(COOLING_PUMP_INITIAL_DUTY_PCT);
  pumpController_.setDutyCycle(initHwDuty);
  ESP_LOGD(TAG, "pumpInit: initial duty %u%% (hw %u%%)",
           COOLING_PUMP_INITIAL_DUTY_PCT, initHwDuty);

  // Disable spinup entirely for the pump.  Water pumps don't need a
  // high-drive burst to overcome static friction (the liquid provides
  // constant load).  Leaving the IC's power-on default active (75 % drive
  // for ~3 s) causes the spinup to re-trigger whenever the TACH signal
  // has a brief dropout, producing a visible ramp-up / drop / ramp-up
  // oscillation even though getDutyCycle() still reports the LUT target.
  if (!pumpController_.configFanSpinup(0, 0)) {            // drive=bypass, time=0
    ESP_LOGW(TAG, "pumpInit: configFanSpinup(0,0) failed");
  }
  if (!pumpController_.configFanSpinup(false)) {            // disable TACH-based spinup
    ESP_LOGW(TAG, "pumpInit: configFanSpinup(false) failed");
  }

  // Reconfigure PWM clock for ~25.7 kHz (same as fan).
  if (!pumpController_.configPWMClock(false, false)) {
    ESP_LOGW(TAG, "pumpInit: configPWMClock failed");
  }
  if (!pumpController_.setPWMFrequency(6)) {
    ESP_LOGW(TAG, "pumpInit: setPWMFrequency failed");
  }

  // Program the pump LUT entries (normalised → hardware duty conversion).
  for (uint8_t i = 0u; i < kPumpLutCount; ++i) {
    const uint8_t hwDuty = pumpNormToHw(kPumpLut[i].pwmPct);
    if (!pumpController_.setLUT(i, kPumpLut[i].tempC, hwDuty)) {
      ESP_LOGW(TAG, "pumpInit: setLUT(%u, %u°C, %u%% hw) failed",
               i, kPumpLut[i].tempC, hwDuty);
    }
    ESP_LOGD(TAG, "pumpInit: LUT[%u] %u°C → %u%% norm → %u%% hw",
             i, kPumpLut[i].tempC, kPumpLut[i].pwmPct, hwDuty);
  }

  // Set LUT hysteresis to prevent rapid hunting between duty steps.
  pumpController_.setLUTHysteresis(COOLING_PUMP_LUT_HYSTERESIS_C);
  ESP_LOGD(TAG, "pumpInit: LUT hyst = %u °C", pumpController_.getLUTHysteresis());

  // Enable forced-temperature mode so the IC uses our software-pushed NTC
  // reading instead of its own internal diode sensor.
  if (!pumpController_.enableForcedTemperature(true)) {
    ESP_LOGW(TAG, "pumpInit: enableForcedTemperature() failed");
  }

  // Push a safe initial temperature so the LUT applies the minimum duty
  // cycle immediately (20 °C → 30 % normalised / 6 % hardware per the pump LUT).
  pumpController_.setForcedTemperature(static_cast<int8_t>(kPumpLut[0].tempC));

  // Enable LUT — the IC takes over pump PWM based on the forced temperature.
  if (!pumpController_.LUTEnabled(true)) {
    ESP_LOGW(TAG, "pumpInit: LUTEnabled(true) failed");
  }

  ESP_LOGD(TAG, "pumpInit: LUT configured (%u entries), forced-temp mode active", kPumpLutCount);
  ESP_LOGI(TAG, "pumpInit: spinup disabled, LUT hyst=%u°C, initial forcedT=%u°C, hwDuty=%u%% (norm %u%%)",
           pumpController_.getLUTHysteresis(),
           kPumpLut[0].tempC,
           pumpController_.getDutyCycle(),
           pumpHwToNorm(pumpController_.getDutyCycle()));
  return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------
module::InitStatus init() {
  //ESP_LOGD(TAG, "Initializing cooling system");
  _Log.printf("Initializing cooling system\n");

  // ── Verify TCA9548A mux is present ──────────────────────────────────────
  hardware::i2c().beginTransmission(TCA9548A_I2C_ADDRESS);
  if (hardware::i2c().endTransmission() != 0) {
    //ESP_LOGE(TAG, "TCA9548A not found at 0x%02X", TCA9548A_I2C_ADDRESS);
    _Log.printf("TCA9548A not found at 0x%02X\n", TCA9548A_I2C_ADDRESS);
    return module::MODULE_INIT_HARDWARE_ERROR;
  }
  ESP_LOGD(TAG, "TCA9548A found at 0x%02X", TCA9548A_I2C_ADDRESS);

  // ── Fan EMC2101 (mux channel 0) ────────────────────────────────────────
  {
    const module::InitStatus st = fanInit();
    if (st != module::MODULE_INIT_SUCCESS) {
      return st;
    }
  }

  // ── Pump EMC2101 (mux channel 1) ───────────────────────────────────────
  {
    const module::InitStatus st = pumpInit();
    if (st != module::MODULE_INIT_SUCCESS) {
      return st;
    }
  }

  // Disconnect mux channels — no downstream bus segments stay connected
  // while other modules initialise or run their service loops.
  deselectMuxChannels();

  // ── Coolant sensor setup ───────────────────────────────────────────────────

  // Flow sensor: interrupt on the falling edge of each Hall-effect pulse.
  rpmAvg_.clear();
  pumpRpmAvg_.clear();
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

  //ESP_LOGD(TAG, "init: flow sensor GPIO%d, temp ADC GPIO%d",
  //       COOLING_FLOW_PIN, COOLING_TEMP_ADC_PIN);
  _Log.printf("init: flow sensor GPIO%d, temp ADC GPIO%d\n",
           COOLING_FLOW_PIN, COOLING_TEMP_ADC_PIN);
  _Log.println(F("[cooling] Cooling system initialized"));
  return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// service
// ---------------------------------------------------------------------------
module::ServiceStatus service() {
  if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS) {
    return module::MODULE_SERVICE_NOT_STARTED;
  }

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

  // ── Fan EMC2101 reads ───────────────────────────────────────────────────
  // Snapshot all EMC2101 values in one place.  Accessors (getFanSpeed,
  // isCoolingFanOn, getFanRPM) return these cached copies so that the
  // telemetry emit path never touches the I2C bus outside this function.
  if (selectMuxChannel(TCA9548A_CHANNEL_FAN)) {
    cachedDutyCycle_ = fanController_.getDutyCycle();
    cachedFanRpm_ = fanController_.getFanRPM();
    ESP_LOGD(TAG, "fan: duty=%u%% rpm=%u", cachedDutyCycle_, cachedFanRpm_);
  } else {
    ESP_LOGE(TAG, "fan: mux channel select FAILED — skipping fan reads");
  }
  const uint8_t dc = cachedDutyCycle_;

  // ── Pump EMC2101: push forced temperature and cache readings ───────────
  if (selectMuxChannel(TCA9548A_CHANNEL_PUMP)) {
    // Feed the averaged NTC coolant temperature into the pump EMC2101.
    // The IC's LUT will then set the pump duty cycle accordingly.
    int16_t forcedTemp = 0;
    if (coolantTemperature_ > 0.0f) {
      forcedTemp = static_cast<int16_t>(roundf(coolantTemperature_));
      if (forcedTemp < 0)   forcedTemp = 0;
      if (forcedTemp > 127) forcedTemp = 127;
      pumpController_.setForcedTemperature(static_cast<int8_t>(forcedTemp));
    }

    const uint8_t  rawDuty  = pumpController_.getDutyCycle();
    const uint16_t rawRpm   = pumpController_.getFanRPM();
    const int8_t   intTemp  = pumpController_.getInternalTemperature();

    cachedPumpDutyCycle_ = rawDuty;
    pumpRpmAvg_.addValue(static_cast<float>(rawRpm));
    cachedPumpRpm_       = static_cast<uint16_t>(pumpRpmAvg_.getAverage());

    ESP_LOGD(TAG, "pump: forcedT=%d intT=%d hwDuty=%u%% norm=%u%% rawRPM=%u avgRPM=%u coolantT=%.1f",
             forcedTemp, intTemp, rawDuty, pumpHwToNorm(rawDuty),
             rawRpm, cachedPumpRpm_, coolantTemperature_);

    // Flag when raw RPM drops to zero — indicates a TACH dropout that
    // could trigger the EMC2101's built-in spinup logic.
    if (rawRpm == 0) {
      ESP_LOGW(TAG, "pump: TACH dropout — rawRPM=0 (hwDuty=%u%%, norm=%u%%, forcedT=%d)",
               rawDuty, pumpHwToNorm(rawDuty), forcedTemp);
    }
  } else {
    ESP_LOGE(TAG, "pump: mux channel select FAILED — skipping pump reads");
  }

  // Disconnect all mux channels so the downstream bus segments no longer
  // load the shared I2C bus while other modules (IMU, INA237, etc.) talk.
  deselectMuxChannels();

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

  // Flow rate tracker: setpoint scales with current pump speed.
  // COOLING_FLOW_NOMINAL_LPM is the expected flow at 100 % normalised speed;
  // at lower speeds the expected flow is proportionally lower.
  if (coolingPumpOn_ && coolantFlowRate_ > 0.0f) {
      const float normPumpPct = static_cast<float>(pumpHwToNorm(cachedPumpDutyCycle_));
      const float expectedFlowLpm = COOLING_FLOW_NOMINAL_LPM * normPumpPct / 100.0f;
      flowTracker_.update(expectedFlowLpm, coolantFlowRate_, nowMs);
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

uint8_t getPumpSpeed() {
  return pumpHwToNorm(cachedPumpDutyCycle_);
}

uint16_t getPumpRPM() {
  return cachedPumpRpm_;
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

  selectMuxChannel(TCA9548A_CHANNEL_FAN);
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
  deselectMuxChannels();
}

// ---------------------------------------------------------------------------
// setPumpSpeed — manual override for diagnostic testing
//
// Accepts a normalised pump speed (0–100 %).  Converts to the hardware
// duty range (0–COOLING_PUMP_MAX_DUTY_PCT %) before writing to the EMC2101.
// Disables the pump LUT; call enable() to restore LUT control.
// ---------------------------------------------------------------------------
void setPumpSpeed(uint8_t percentage) {
  const uint8_t hwDuty = pumpNormToHw(percentage);
  ESP_LOGI(TAG, "setPumpSpeed(%u%% norm → %u%% hw): manual override — disabling pump LUT",
           percentage, hwDuty);

  selectMuxChannel(TCA9548A_CHANNEL_PUMP);
  if (!pumpController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "setPumpSpeed: LUTEnabled(false) failed");
  }
  if (!pumpController_.setDutyCycle(hwDuty)) {
    ESP_LOGW(TAG, "setPumpSpeed: setDutyCycle(%u) failed", hwDuty);
  }
  // Post-write LUTEnabled(false) to override setDutyCycle()'s LUT-state restore.
  if (!pumpController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "setPumpSpeed: LUTEnabled(false) post-write failed");
  }

  ESP_LOGI(TAG, "setPumpSpeed: norm=%u%% hwDuty=%u%% readback=%u%% LUT=%s",
           percentage, hwDuty, pumpController_.getDutyCycle(),
           pumpController_.LUTEnabled() ? "ENABLED(!)" : "disabled");
  deselectMuxChannels();
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

  selectMuxChannel(TCA9548A_CHANNEL_FAN);
  if (!fanController_.LUTEnabled(true)) {
    ESP_LOGW(TAG, "enable(): fan LUTEnabled(true) failed");
  }

  selectMuxChannel(TCA9548A_CHANNEL_PUMP);
  if (!pumpController_.LUTEnabled(true)) {
    ESP_LOGW(TAG, "enable(): pump LUTEnabled(true) failed");
  }

  deselectMuxChannels();
  ESP_LOGD(TAG, "enable(): fan and pump LUT enabled");
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

  // ── Stop the fan ──────────────────────────────────────────────────────
  selectMuxChannel(TCA9548A_CHANNEL_FAN);
  if (!fanController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "disable(): fan LUTEnabled(false) failed");
  }
  if (!fanController_.setDutyCycle(0)) {
    ESP_LOGW(TAG, "disable(): fan setDutyCycle(0) failed");
  }
  // Post-write LUTEnabled(false) to override setDutyCycle()'s LUT-state restore.
  if (!fanController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "disable(): fan LUTEnabled(false) post-write failed");
  }

  // ── Stop the pump ─────────────────────────────────────────────────────
  selectMuxChannel(TCA9548A_CHANNEL_PUMP);
  if (!pumpController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "disable(): pump LUTEnabled(false) failed");
  }
  if (!pumpController_.setDutyCycle(0)) {
    ESP_LOGW(TAG, "disable(): pump setDutyCycle(0) failed");
  }
  if (!pumpController_.LUTEnabled(false)) {
    ESP_LOGW(TAG, "disable(): pump LUTEnabled(false) post-write failed");
  }

  deselectMuxChannels();
  ESP_LOGD(TAG, "disable(): fan and pump stopped");
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
