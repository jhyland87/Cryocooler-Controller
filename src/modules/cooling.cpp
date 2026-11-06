/**
 * @file cooling.cpp
 * @brief Cooling system — fan & pump control from ESP32 GPIOs, coolant sensors.
 *
 * LEDC drives each 4-pin PWM input at 25 kHz through a BSS138, and PCNT counts
 * each tach line.  Temperature→duty-cycle mapping is performed in software
 * using the NTC coolant temperature reading.
 *
 * Software LUT behaviour:
 *   - Entries are sorted ascending by temperature.
 *   - The highest entry whose threshold ≤ current temperature wins.
 *   - Hysteresis prevents rapid hunting when temp hovers near a threshold.
 *   - Duty cycle is only written when it actually changes.
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
 *   - Configure PWM and tach counting for both channels on init().
 *   - Evaluate the fan and pump software LUTs every COOLING_CHECK_CYCLE_MS
 *     using the averaged coolant temperature.
 *   - Track the pump enable state.
 *   - Expose enable()/disable() for the cooling system.
 *   - Allow manual fan override via setFanSpeed(pct, force=true), which
 *     disables the software LUT for the fan.  enable() re-activates it.
 *   - Sample coolant temperature and flow rate every COOLING_SENSOR_SAMPLE_MS.
 *   - Update tracking monitors every COOLING_CHECK_CYCLE_MS.
 */

#include <Arduino.h>
#include <RunningAverage.h>
#include <driver/pcnt.h>
#include <math.h>
#include "cooling.h"
#include "config.h"
#include "conversions.h"
#include "esp_log.h"
#include "sensor_mock.h"
#include "module.h"
#include "pin_config.h"
#include "tracking.h"
#include "logger.h"

namespace cooling {
static LogStream _Log = Log.createChildLogger("cooling");

static constexpr char TAG[] = "cooling";

// ---------------------------------------------------------------------------
// Fan and pump channels
//
// The BSS138 inverts: GPIO high pulls the fan's PWM input low.  A gate pull-up
// holds both channels at 0 % drive until init() takes over the pins.
// ---------------------------------------------------------------------------
struct FanChannel {
    uint8_t     pwmPin;
    uint8_t     tachPin;
    uint8_t     ledcChannel;
    pcnt_unit_t pcntUnit;
};

static constexpr uint8_t FAN_CHANNEL  = 0;
static constexpr uint8_t PUMP_CHANNEL = 1;

static const FanChannel CHANNELS[] = {
    {COOLING_FAN_PWM_PIN,  COOLING_FAN_TACH_PIN,  0, PCNT_UNIT_0},
    {COOLING_PUMP_PWM_PIN, COOLING_PUMP_TACH_PIN, 1, PCNT_UNIT_1},
};

static constexpr uint32_t PWM_FREQUENCY_HZ    = 25000u;  // Intel 4-wire spec: 21-28 kHz
static constexpr uint8_t  PWM_RESOLUTION_BITS = 8u;
static constexpr uint8_t  PWM_FULL_SCALE      = 255u;
static constexpr uint16_t TACH_GLITCH_FILTER_APB_TICKS = 1023u;  // 12.8 us, PCNT maximum
static constexpr uint32_t TACH_PULSES_PER_REV = 2u;              // Intel 4-wire spec

static uint8_t commandedDuty_[2] = {0u, 0u};  // 0-255 drive requested on each channel
static bool    channelsReady_    = false;

// Tach-based stall detection: a channel with non-zero drive and no tach pulses.
static bool     fanFaultActive_ = false;
static bool     stallTimerOn_   = false;
static uint32_t stallSinceMs_   = 0u;

// ---------------------------------------------------------------------------
// Software LUT — data structures
//
// Each entry maps a temperature
// threshold to a PWM duty cycle (0–255).  Entries MUST be sorted ascending
// by temperature.  Hysteresis prevents rapid hunting when the temperature
// oscillates around a threshold boundary.
// ---------------------------------------------------------------------------
struct LUTEntry {
    int8_t  tempC;     ///< Temperature threshold (°C)
    uint8_t duty;      ///< PWM duty cycle (0–255)
};

static constexpr uint8_t LUT_MAX_ENTRIES = 8;

struct SoftLUT {
    uint8_t  numEntries;
    LUTEntry entries[LUT_MAX_ENTRIES];
    uint8_t  hysteresisC;   ///< Degrees C of hysteresis
    int8_t   activeIndex;   ///< Currently active LUT row (-1 = below all)
    bool     enabled;       ///< false = manual override, LUT suspended
};

// ---------------------------------------------------------------------------
// Fan software LUT
//
// Eight entries mapping coolant temperature (°C) → fan PWM duty (0–255).
// Duty is 0–255 raw, not percentage.
// ---------------------------------------------------------------------------
static SoftLUT fanLut_ = {
    .numEntries  = 5,
    .entries     = {
        {  0,  13 },   //  0 °C → ~5 %  (testing — keep fan slow)
        { 30,  20 },   // 30 °C → ~8 %
        { 40,  30 },   // 40 °C → ~12 %
        { 50,  40 },   // 50 °C → ~16 %
        { 60,  51 },   // 60 °C → ~20 %
    },
    .hysteresisC = COOLING_FAN_LUT_HYSTERESIS_C,
    .activeIndex = -1,
    .enabled     = true,
};

// ---------------------------------------------------------------------------
// Pump speed normalisation helpers
//
// All user-facing pump speeds are expressed in a normalised 0–100 % range.
// The actual hardware duty is 0–COOLING_PUMP_MAX_DUTY_PCT (0–255 scale).
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
// Pump software LUT (forced-temperature mode replacement)
//
// NOTE: This pump stalls above ~4400 RPM.
// COOLING_PUMP_MAX_DUTY_PCT = 51 raw ≈ 20 % of 255.
//
// Values below are in **normalised 0–100 %** space, converted to HW duty
// via pumpNormToHw() when evaluated.
//
//   Index  Temp (°C)  Norm (%)  HW duty  Est. RPM    Notes
//   ─────  ─────────  ────────  ───────  ────────    ──────────────────────
//     0       20         10       ~5     ~2360       Idle / cool — minimum
//     1       25         15       ~8     ~2720       Normal room temp
//     2       30         20      ~10     ~3280       Warm coolant
//     3       35         70      ~36     ~3620       Above ambient
//     4       40         85      ~43     ~4160       Hot — approaching limit
//     5       45        100      ~51     ~4400       Max — stall headroom
// ---------------------------------------------------------------------------
static SoftLUT pumpLut_ = {
    .numEntries  = 6,
    .entries     = {
        { 20,  pumpNormToHw( 10) },
        { 25,  pumpNormToHw( 15) },
        { 30,  pumpNormToHw( 20) },
        { 35,  pumpNormToHw( 70) },
        { 40,  pumpNormToHw( 85) },
        { 45,  pumpNormToHw(100) },
    },
    .hysteresisC = COOLING_PUMP_LUT_HYSTERESIS_C,
    .activeIndex = -1,
    .enabled     = true,
};

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

static constexpr FlowPoint pumpFlowTable[] = {
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
static constexpr uint8_t flowTableLen =
    static_cast<uint8_t>(sizeof(pumpFlowTable) / sizeof(pumpFlowTable[0]));

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
);  // pump tach smoothing

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------
static volatile bool    enabled_            = false;
static volatile bool    coolingPumpOn_      = false;
static volatile float   coolantTemperature_ = 0.0f;
static volatile float   coolantFlowRate_    = 0.0f;
static volatile uint8_t fanSpeed_           = 0;      // only meaningful in manual-override mode
static volatile bool    forceFanSpeed_      = false;

// Tach readings, updated once per COOLING_CHECK_CYCLE_MS in service().
static uint16_t cachedFanRpm_         = 0u;
static uint16_t cachedPumpRpm_        = 0u;

static uint32_t lastCheckCycleMs      = 0;
static uint32_t lastSampleMs_         = 0;

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

// Fan duty-cycle tracker — only active in forced/manual mode.
// Reset to IN_RANGE while the software LUT is in control (no explicit setpoint).
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
// setChannelDuty — request 0–255 drive; the output is inverted for the BSS138
// ---------------------------------------------------------------------------
static void setChannelDuty(uint8_t duty, uint8_t channel) {
    commandedDuty_[channel] = duty;
    if (!channelsReady_) return;
    ledcWrite(CHANNELS[channel].ledcChannel, PWM_FULL_SCALE - duty);
}

// ---------------------------------------------------------------------------
// readTachRpm — convert the pulses counted since the last call to RPM
// ---------------------------------------------------------------------------
static uint16_t readTachRpm(uint8_t channel, uint32_t elapsedMs) {
    if (elapsedMs == 0u) return 0u;
    int16_t pulses = 0;
    pcnt_get_counter_value(CHANNELS[channel].pcntUnit, &pulses);
    pcnt_counter_clear(CHANNELS[channel].pcntUnit);
    if (pulses <= 0) return 0u;
    static constexpr uint32_t MS_PER_MINUTE = 6e4;
    const uint32_t rpm = (static_cast<uint32_t>(pulses) * MS_PER_MINUTE) /
                         (TACH_PULSES_PER_REV * elapsedMs);
    return (rpm > UINT16_MAX) ? UINT16_MAX : static_cast<uint16_t>(rpm);
}

// ---------------------------------------------------------------------------
// updateStallFault — flag a channel with drive applied but no tach pulses
//
// Telemetry and logs only; it does not fault the state machine.
// ---------------------------------------------------------------------------
static void updateStallFault(uint32_t nowMs) {
    const bool fanStalled  = (commandedDuty_[FAN_CHANNEL]  > 0u) && (cachedFanRpm_ == 0u);
    const bool pumpStalled = (commandedDuty_[PUMP_CHANNEL] > 0u) && (cachedPumpRpm_ == 0u);

    if (!fanStalled && !pumpStalled) {
        if (fanFaultActive_) {
            _Log.println(F("Tach pulses restored"));
        }
        fanFaultActive_ = false;
        stallTimerOn_   = false;
        return;
    }
    if (!stallTimerOn_) {
        stallTimerOn_ = true;
        stallSinceMs_ = nowMs;
        return;
    }
    if (fanFaultActive_ || (nowMs - stallSinceMs_) < COOLING_TACH_STALL_MS) {
        return;
    }
    fanFaultActive_ = true;
    _Log.printf("No tach pulses — fan %s, pump %s\n",
                fanStalled ? "stalled" : "ok", pumpStalled ? "stalled" : "ok");
}

// ---------------------------------------------------------------------------
// evaluateLUT — software lookup-table engine
//
// Walks entries from highest to lowest threshold.  On rising temperature the
// duty cycle increases immediately on threshold crossing.  On falling
// temperature the reading must drop below (threshold − hysteresis) before
// stepping down.
//
// Returns the duty cycle to apply (0–255).  Only writes the output if the
// active row actually changed.
// ---------------------------------------------------------------------------
static uint8_t evaluateLUT(SoftLUT &lut, float tempC, uint8_t channel) {
    if (lut.numEntries == 0) return 0;

    int8_t newIndex = -1;

    // Walk from highest threshold down
    for (int8_t entryIndex = static_cast<int8_t>(lut.numEntries) - 1; entryIndex >= 0; --entryIndex) {
        const int8_t thresh = lut.entries[entryIndex].tempC;

        if (entryIndex <= lut.activeIndex) {
            // Falling: stay at current row until temp drops below threshold − hysteresis
            if (tempC >= static_cast<float>(thresh - static_cast<int8_t>(lut.hysteresisC))) {
                newIndex = entryIndex;
                break;
            }
        } else {
            // Rising: switch up immediately on crossing
            if (tempC >= static_cast<float>(thresh)) {
                newIndex = entryIndex;
                break;
            }
        }
    }

    uint8_t duty;
    if (newIndex < 0) {
        duty = 0;  // below all thresholds
    } else {
        duty = lut.entries[newIndex].duty;
    }

    // Only write the output when the active row changes
    if (newIndex != lut.activeIndex) {
        _Log.printf("LUT ch%u: row %d->%d duty=%u tempC=%.1f\n",
                    channel, lut.activeIndex, newIndex, duty, tempC);
        lut.activeIndex = newIndex;
        setChannelDuty(duty, channel);
    }

    return duty;
}

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
    if (rpm < static_cast<float>(pumpFlowTable[0].rpm)) {
        const float slope = (pumpFlowTable[1].lph - pumpFlowTable[0].lph) /
                            static_cast<float>(pumpFlowTable[1].rpm - pumpFlowTable[0].rpm);
        const float val = pumpFlowTable[0].lph +
                          slope * (rpm - static_cast<float>(pumpFlowTable[0].rpm));
        return (val > 0.0f) ? val : 0.0f;
    }

    // Above maximum — extrapolate linearly, capped at pump max (COOLING_FLOW_MAX_LPH)
    if (rpm >= static_cast<float>(pumpFlowTable[flowTableLen - 1u].rpm)) {
        const uint8_t last = flowTableLen - 1u;
        const uint8_t prev = flowTableLen - 2u;
        const float slope = (pumpFlowTable[last].lph - pumpFlowTable[prev].lph) /
                            static_cast<float>(pumpFlowTable[last].rpm - pumpFlowTable[prev].rpm);
        const float val = pumpFlowTable[last].lph +
                          slope * (rpm - static_cast<float>(pumpFlowTable[last].rpm));
        return (val < COOLING_FLOW_MAX_LPH) ? val : COOLING_FLOW_MAX_LPH;
    }

    // Binary search for the surrounding bracket
    uint8_t lo = 0u;
    uint8_t hi = flowTableLen - 1u;
    while (hi - lo > 1u) {
        const uint8_t mid = static_cast<uint8_t>((lo + hi) / 2u);
        if (static_cast<float>(pumpFlowTable[mid].rpm) <= rpm) lo = mid;
        else                                                 hi = mid;
    }

    const float interpFraction = (rpm - static_cast<float>(pumpFlowTable[lo].rpm)) /
                                 static_cast<float>(pumpFlowTable[hi].rpm - pumpFlowTable[lo].rpm);
    return pumpFlowTable[lo].lph + interpFraction * (pumpFlowTable[hi].lph - pumpFlowTable[lo].lph);
}

// ---------------------------------------------------------------------------
// readCoolantTemp — NTC Beta-equation temperature conversion
//
// Oversamples the ADC COOLING_TEMP_OVERSAMPLE times for noise reduction.
// Returns -999 °C on open/short circuit (sensor not connected).
// ---------------------------------------------------------------------------
static float readCoolantTemp() {
    uint32_t adcSum = 0u;
    for (uint8_t sampleIndex = 0u; sampleIndex < COOLING_TEMP_OVERSAMPLE; ++sampleIndex) {
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
// channelsInit — configure PWM and tach counting for both channels
// ---------------------------------------------------------------------------
static module::InitStatus channelsInit() {
    channelsReady_ = false;
    commandedDuty_[FAN_CHANNEL]  = fanLut_.entries[0].duty;
    commandedDuty_[PUMP_CHANNEL] = pumpLut_.entries[0].duty;

    for (uint8_t channel = 0u; channel < 2u; ++channel) {
        const FanChannel& pins = CHANNELS[channel];

        if (ledcSetup(pins.ledcChannel, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS) == 0u) {
            _Log.printf("LEDC setup failed on channel %u\n", pins.ledcChannel);
            return module::MODULE_INIT_CONFIG_ERROR;
        }
        // Set the duty before attaching so the pin never drives a stale value.
        ledcWrite(pins.ledcChannel, PWM_FULL_SCALE - commandedDuty_[channel]);
        ledcAttachPin(pins.pwmPin, pins.ledcChannel);

        pinMode(pins.tachPin, INPUT);
        pcnt_config_t tachConfig = {};
        tachConfig.pulse_gpio_num = pins.tachPin;
        tachConfig.ctrl_gpio_num  = PCNT_PIN_NOT_USED;
        tachConfig.channel        = PCNT_CHANNEL_0;
        tachConfig.unit           = pins.pcntUnit;
        tachConfig.pos_mode       = PCNT_COUNT_DIS;
        tachConfig.neg_mode       = PCNT_COUNT_INC;
        tachConfig.lctrl_mode     = PCNT_MODE_KEEP;
        tachConfig.hctrl_mode     = PCNT_MODE_KEEP;
        tachConfig.counter_h_lim  = INT16_MAX;
        tachConfig.counter_l_lim  = 0;
        if (pcnt_unit_config(&tachConfig) != ESP_OK) {
            _Log.printf("PCNT setup failed on tach GPIO%u\n", pins.tachPin);
            return module::MODULE_INIT_CONFIG_ERROR;
        }
        pcnt_set_filter_value(pins.pcntUnit, TACH_GLITCH_FILTER_APB_TICKS);
        pcnt_filter_enable(pins.pcntUnit);
        pcnt_counter_pause(pins.pcntUnit);
        pcnt_counter_clear(pins.pcntUnit);
        pcnt_counter_resume(pins.pcntUnit);
    }

    channelsReady_ = true;
    _Log.printf("Fan and pump PWM ready — fan duty=%u  pump duty=%u\n",
                commandedDuty_[FAN_CHANNEL], commandedDuty_[PUMP_CHANNEL]);
    return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------
module::InitStatus init() {
    _Log.println(F("Initializing cooling system"));

    const module::InitStatus channelStatus = channelsInit();
    if (channelStatus != module::MODULE_INIT_SUCCESS) {
        return channelStatus;
    }

    fanFaultActive_ = false;
    stallTimerOn_   = false;

    // ── Coolant sensor setup ──────────────────────────────────────────────

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
    fanSpeed_      = 0u;   // LUT-controlled; track as 0 in manual-mode terms
    forceFanSpeed_ = false;
    fanLut_.enabled  = true;
    pumpLut_.enabled = true;
    enable();

    _Log.printf("init: flow sensor GPIO%d, temp ADC GPIO%d\n",
             COOLING_FLOW_PIN, COOLING_TEMP_ADC_PIN);
    _Log.println(F("Cooling system initialized"));
    return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// service
// ---------------------------------------------------------------------------
module::ServiceStatus service() {
    // UNDERVOLTAGE is an intentional shutdown; the operator must reinit once
    // system voltage is restored.
    if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS) {
        return module::MODULE_SERVICE_NOT_STARTED;
    }

    const uint32_t nowMs = millis();
    bool didWork = false;

    // ── 100 ms flow-sensor sampling ─────────────────────────────────────
    if (!sensor_mock::isActive() &&
        (nowMs - lastSampleMs_) >= COOLING_SENSOR_SAMPLE_MS) {

        const uint32_t elapsed = nowMs - lastSampleMs_;
        lastSampleMs_ = nowMs;

        // Temperature ─────────────────────────────────────────────────────
        const float tempC = readCoolantTemp();
        if (tempC > -999.0f) {
            tempAvg_.addValue(tempC);
            coolantTemperature_ = tempAvg_.getAverage();
        }

        // Flow rate (RPM → L/min) ─────────────────────────────────────────
        // Atomically snapshot and reset the ISR pulse counter.
        noInterrupts();
        const uint32_t pulses = flowPulseCount_;
        flowPulseCount_ = 0u;
        interrupts();

        // RPM = (pulses / pulsesPerRev) / (elapsed_ms / 60 000)
        const float sampledRpm =
            (static_cast<float>(pulses) /
             static_cast<float>(COOLING_FLOW_PULSES_PER_REV)) /
            (static_cast<float>(elapsed) / 6e4f);

        rpmAvg_.addValue(sampledRpm);

        // Convert average RPM → L/h → L/min
        coolantFlowRate_ = rpmToLph(rpmAvg_.getAverage()) / 60.0f;

        didWork = true;
    }

    // ── 1000 ms tracker update ──────────────────────────────────────────
    if ((nowMs - lastCheckCycleMs) < COOLING_CHECK_CYCLE_MS) {
        return didWork ? module::MODULE_SERVICE_OK : module::MODULE_SERVICE_SKIPPED;
    }

    const uint32_t checkElapsedMs = nowMs - lastCheckCycleMs;
    lastCheckCycleMs = nowMs;

    // ── Software LUT evaluation ─────────────────────────────────────────
    // Use the averaged coolant temperature for both fan and pump LUTs.
    // If the sensor is disconnected (coolantTemperature_ == 0), use a
    // safe default that maps to the lowest LUT entry.
    const float lutTemp = (coolantTemperature_ > 0.0f)
                          ? coolantTemperature_
                          : static_cast<float>(fanLut_.entries[0].tempC);

    if (fanLut_.enabled) {
        evaluateLUT(fanLut_, lutTemp, FAN_CHANNEL);
    }
    if (pumpLut_.enabled) {
        evaluateLUT(pumpLut_, lutTemp, PUMP_CHANNEL);
    }

    // ── Tach readings ───────────────────────────────────────────────────
    cachedFanRpm_ = readTachRpm(FAN_CHANNEL, checkElapsedMs);

    const uint16_t rawPumpRpm = readTachRpm(PUMP_CHANNEL, checkElapsedMs);
    pumpRpmAvg_.addValue(static_cast<float>(rawPumpRpm));
    cachedPumpRpm_ = static_cast<uint16_t>(pumpRpmAvg_.getAverage());

    ESP_LOGV(TAG, "fan: duty=%u rpm=%u  |  pump: hwDuty=%u norm=%u%% rpm=%u avgRpm=%u  |  coolantT=%.1f\n",
                commandedDuty_[FAN_CHANNEL], cachedFanRpm_,
                commandedDuty_[PUMP_CHANNEL], pumpHwToNorm(commandedDuty_[PUMP_CHANNEL]),
                rawPumpRpm, cachedPumpRpm_, coolantTemperature_);

    updateStallFault(nowMs);

    const uint8_t fanDutyCycle = commandedDuty_[FAN_CHANNEL];

    // Fan speed tracker: only meaningful in forced/manual mode.
    // In LUT mode the software LUT owns the duty cycle — no external setpoint exists.
    if (forceFanSpeed_) {
        fanTracker_.update(static_cast<float>(fanSpeed_),
                           static_cast<float>(fanDutyCycle));
    } else {
        fanTracker_.reset();
    }

    // Coolant temperature tracker: only advance when the sensor is connected.
    // A reading of exactly 0 °C indicates the hardware is not yet wired up.
    if (coolantTemperature_ > 0.0f) {
        coolantTempTracker_.update(COOLING_COOLANT_NOMINAL_TEMP_C,
                                   coolantTemperature_);
    } else {
        coolantTempTracker_.reset();
    }

    // Flow rate tracker: setpoint scales with current pump speed.
    // COOLING_FLOW_NOMINAL_LPM is the expected flow at 100 % normalised speed;
    // at lower speeds the expected flow is proportionally lower.
    if (coolingPumpOn_ && coolantFlowRate_ > 0.0f) {
        const float normPumpPct = static_cast<float>(pumpHwToNorm(commandedDuty_[PUMP_CHANNEL]));
        const float expectedFlowLpm = COOLING_FLOW_NOMINAL_LPM * normPumpPct / 100.0f;
        flowTracker_.update(expectedFlowLpm, coolantFlowRate_);
    } else {
        flowTracker_.reset();
    }

    return module::MODULE_SERVICE_OK;
}

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------
bool    isCoolingPumpOn()       { return coolingPumpOn_; }
// isCoolingFanOn uses the commanded duty rather than RPM because the tach
// signal may not be connected.
bool    isCoolingFanOn()        { return commandedDuty_[FAN_CHANNEL] > 0; }
float   getCoolantTemperature() { return coolantTemperature_; }
float   getCoolantFlowRate()    { return coolantFlowRate_; }

uint8_t getFanSpeed() {
    return sensor_mock::isActive() ? fanSpeed_ : commandedDuty_[FAN_CHANNEL];
}

uint16_t getFanRPM() {
    return cachedFanRpm_;
}

uint8_t getPumpSpeed() {
    return pumpHwToNorm(commandedDuty_[PUMP_CHANNEL]);
}

uint16_t getPumpRPM() {
    return cachedPumpRpm_;
}

// ---------------------------------------------------------------------------
// setFanSpeed — manual override
//
// With force=true: disables the software LUT and drives the fan at the given
// duty cycle until enable() is called (which re-activates the LUT).
// With force=false: no-op while the LUT is active.
// ---------------------------------------------------------------------------
void setFanSpeed(uint8_t percentage, bool force) {
    if (!force) {
        ESP_LOGD(TAG, "setFanSpeed(%u): ignored — LUT is active (use force=true to override)", percentage);
        return;
    }

    // Convert 0–100 % → 0–255 raw duty.
    const uint8_t duty = static_cast<uint8_t>((static_cast<uint16_t>(percentage) * 255u) / 100u);

    _Log.printf("setFanSpeed(%u%% -> duty %u/255): LUT disabled\n", percentage, duty);
    forceFanSpeed_  = true;
    fanLut_.enabled = false;

    setChannelDuty(duty, FAN_CHANNEL);

    fanSpeed_ = percentage;
    fanTracker_.reset();
}

// ---------------------------------------------------------------------------
// setPumpSpeed — manual override for diagnostic testing
//
// Accepts a normalised pump speed (0–100 %).  Converts to the hardware
// duty range (0–COOLING_PUMP_MAX_DUTY_PCT) before writing the output.
// Disables the pump LUT; call enable() to restore LUT control.
// ---------------------------------------------------------------------------
void setPumpSpeed(uint8_t percentage) {
    const uint8_t hwDuty = pumpNormToHw(percentage);

    _Log.printf("setPumpSpeed(%u%% norm -> %u hw): LUT disabled\n", percentage, hwDuty);

    pumpLut_.enabled = false;
    setChannelDuty(hwDuty, PUMP_CHANNEL);
}

// ---------------------------------------------------------------------------
// setFanDutyCycle — raw duty override (0–255)
//
// Bypasses percentage conversion and writes the value directly.
// Disables the fan LUT; call enable() to restore LUT control.
// ---------------------------------------------------------------------------
void setFanDutyCycle(uint8_t duty) {
    _Log.printf("setFanDutyCycle(%u): LUT disabled\n", duty);
    forceFanSpeed_  = true;
    fanLut_.enabled = false;

    setChannelDuty(duty, FAN_CHANNEL);

    fanSpeed_ = 0;
    fanTracker_.reset();
}

// ---------------------------------------------------------------------------
// setPumpDutyCycle — raw duty override (0–255)
//
// Bypasses normalised-percentage conversion and writes the value directly.
// Disables the pump LUT; call enable() to restore LUT control.
// ---------------------------------------------------------------------------
void setPumpDutyCycle(uint8_t duty) {
    _Log.printf("setPumpDutyCycle(%u): LUT disabled\n", duty);

    pumpLut_.enabled = false;
    setChannelDuty(duty, PUMP_CHANNEL);
}

// ---------------------------------------------------------------------------
// enable / disable
// ---------------------------------------------------------------------------

/**
 * Activate the cooling system: turn on the pump and re-engage the software
 * LUTs so both fan and pump are temperature-controlled.
 * Safe to call when already enabled.
 */
void enable() {
    ESP_LOGI(TAG, "enable(): pump on, software LUT control active");
    enabled_       = true;
    coolingPumpOn_ = true;
    forceFanSpeed_ = false;

    // Re-enable both software LUTs and reset their active indices so the
    // next evaluateLUT() call will apply the correct duty immediately.
    fanLut_.enabled     = true;
    fanLut_.activeIndex = -1;
    pumpLut_.enabled     = true;
    pumpLut_.activeIndex = -1;

    ESP_LOGD(TAG, "enable(): fan and pump software LUTs re-enabled");
}

/**
 * Deactivate the cooling system: turn off the pump and stop the fan.
 * Software LUTs are disabled; nothing will restart until enable() is called.
 */
void disable() {
    ESP_LOGI(TAG, "disable(): pump off, fan stopped");
    enabled_       = false;
    coolingPumpOn_ = false;
    forceFanSpeed_ = false;

    // Disable software LUTs
    fanLut_.enabled  = false;
    pumpLut_.enabled = false;

    // Stop both channels
    setChannelDuty(0u, FAN_CHANNEL);
    setChannelDuty(0u, PUMP_CHANNEL);

    ESP_LOGD(TAG, "disable(): fan and pump stopped, LUTs disabled");
}

bool isEnabled() { return enabled_; }

bool hasFanFault() { return fanFaultActive_; }

uint32_t getFanFaultDurationMs() {
    if (!fanFaultActive_) return 0;
    return millis() - stallSinceMs_;
}

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
    using TrackerState = TrackingMonitor<float>::State;
    const auto fanState = fanTracker_.getState();
    const auto coolantTempState = coolantTempTracker_.getState();
    const auto flowState = flowTracker_.getState();
    if (fanState == TrackerState::FAULT || coolantTempState == TrackerState::FAULT || flowState == TrackerState::FAULT) return TrackerState::FAULT;
    if (fanState == TrackerState::WARNING || coolantTempState == TrackerState::WARNING || flowState == TrackerState::WARNING) return TrackerState::WARNING;
    return TrackerState::IN_RANGE;
}

} // namespace cooling
