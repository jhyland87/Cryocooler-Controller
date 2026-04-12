/**
 * @file cooling.cpp
 * @brief Cooling system — fan & pump control via EMC2303, coolant sensors.
 *
 * A single EMC2303 three-channel PWM fan controller drives the fan (channel 0)
 * and the pump (channel 1).  Channel 2 is unused.  The EMC230x family has no built-in temperature
 * sensor or hardware LUT, so temperature→duty-cycle mapping is performed
 * in software using the NTC coolant temperature reading.
 *
 * Software LUT behaviour mirrors the EMC2101's hardware LUT:
 *   - Entries are sorted ascending by temperature.
 *   - The highest entry whose threshold ≤ current temperature wins.
 *   - Hysteresis prevents rapid hunting when temp hovers near a threshold.
 *   - Duty cycle is only written to the IC when it actually changes.
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
 *   - Initialise the EMC2303 and configure both channels on init().
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
#include <EMC230x.h>
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

// ---------------------------------------------------------------------------
// EMC2303 — single dual-channel fan controller
// ---------------------------------------------------------------------------
static EMC230x controller_(3);   // 3 channels (EMC2303); fan=ch0, pump=ch1, ch2 unused

// Channel assignments
static constexpr uint8_t FAN_CHANNEL  = 0;
static constexpr uint8_t PUMP_CHANNEL = 1;

// Last duty we intentionally wrote to each channel.  Used by the
// hot-plug / drive-fail guard in service() to detect when the chip's
// actual duty diverges from what we commanded.
static uint8_t expectedDuty_[2] = {0, 0};

// ---------------------------------------------------------------------------
// EMC2303 ALERT# pin fault detection
//
// The EMC2303's open-drain ALERT# output latches LOW when a stall, spin-up
// failure, or drive failure is detected on either channel.  It remains LOW
// until the firmware reads the corresponding status register, which clears
// the latch and releases the pin (external pull-up returns it HIGH).
//
// GPIO COOLING_FAN_FAULT_INDICATOR_PIN is connected to ALERT# via an external pull-up
// resistor.  We sample the pin every service() tick:
//   HIGH → no fault (or fault was just cleared)
//   LOW  → EMC2303 has latched a fault
//
// When a LOW is detected we read all four status registers (fan status,
// stall, spin, drive-fail), log the decoded fault bits, and clear the
// latch.  The fault flag stays active for one full check cycle so that
// telemetry and the state machine can observe it.
// ---------------------------------------------------------------------------
static bool     fanFaultActive_   = false;
static uint32_t fanFaultSinceMs_  = 0;      // millis() of the first assertion
static uint8_t  lastFanStatus_    = 0;
static uint8_t  lastStallStatus_  = 0;
static uint8_t  lastSpinStatus_   = 0;
static uint8_t  lastDriveStatus_  = 0;

namespace cooling {
static LogStream _Log = Log.createChildLogger("cooling");

static constexpr char TAG[] = "cooling";

// ---------------------------------------------------------------------------
// Software LUT — data structures
//
// These replace the EMC2101's hardware LUT.  Each entry maps a temperature
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
// The EMC2303 uses 0–255 raw duty, not percentage — these map directly.
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
// The actual EMC2303 hardware duty is 0–COOLING_PUMP_MAX_DUTY_PCT (0–255 scale).
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
// The EMC2303 uses 0–255 raw duty (unlike the EMC2101's 0–63 hw steps).
// COOLING_PUMP_MAX_DUTY_PCT = 51 raw ≈ 20 % of 255, giving headroom
// above the old EMC2101 equivalent (~41 raw).
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
);  // pump EMC2303 TACH smoothing

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------
static volatile bool    enabled_            = false;
static volatile bool    coolingPumpOn_      = false;
static volatile float   coolantTemperature_ = 0.0f;
static volatile float   coolantFlowRate_    = 0.0f;
static volatile uint8_t fanSpeed_           = 0;      // only meaningful in manual-override mode
static volatile bool    forceFanSpeed_      = false;

// Cached EMC2303 readings — updated once per COOLING_CHECK_CYCLE_MS in
// service().  Accessors return these values instead of reading the IC live,
// which eliminates concurrent I2C transactions between the service loop and
// the telemetry emit path (the root cause of Wire repeated-start errors).
static uint8_t  cachedDutyCycle_      = 0u;
static uint16_t cachedFanRpm_         = 0u;

// Cached pump EMC2303 readings — same pattern as the fan channel.
static uint8_t  cachedPumpDutyCycle_  = 0u;
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
// evaluateLUT — software lookup-table engine
//
// Walks entries from highest to lowest threshold.  On rising temperature the
// duty cycle increases immediately on threshold crossing.  On falling
// temperature the reading must drop below (threshold − hysteresis) before
// stepping down — the same behaviour as the EMC2101's hardware LUT.
//
// Returns the duty cycle to apply (0–255).  Only writes to the EMC2303 if
// the active row actually changed.
// ---------------------------------------------------------------------------
static uint8_t evaluateLUT(SoftLUT &lut, float tempC, uint8_t channel) {
    if (lut.numEntries == 0) return 0;

    int8_t newIndex = -1;

    // Walk from highest threshold down
    for (int8_t i = static_cast<int8_t>(lut.numEntries) - 1; i >= 0; --i) {
        const int8_t thresh = lut.entries[i].tempC;

        if (i <= lut.activeIndex) {
            // Falling: stay at current row until temp drops below threshold − hysteresis
            if (tempC >= static_cast<float>(thresh - static_cast<int8_t>(lut.hysteresisC))) {
                newIndex = i;
                break;
            }
        } else {
            // Rising: switch up immediately on crossing
            if (tempC >= static_cast<float>(thresh)) {
                newIndex = i;
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

    // Only write to the chip when the active row changes
    if (newIndex != lut.activeIndex) {
        _Log.printf("LUT ch%u: row %d->%d duty=%u tempC=%.1f\n",
                    channel, lut.activeIndex, newIndex, duty, tempC);
        lut.activeIndex = newIndex;
        controller_.setDutyCycle(duty, channel);
        expectedDuty_[channel] = duty;
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
// controllerInit — configure the EMC2303
//
// Both fan (channel 0) and pump (channel 1) are configured for direct-drive
// PWM mode.  The software LUT evaluator sets duty cycles in service().
// ---------------------------------------------------------------------------
static module::InitStatus controllerInit() {
    if (!controller_.begin(EMC2303_I2C_ADDRESS, &hardware::i2c())) {
        return module::MODULE_INIT_HARDWARE_ERROR;
    }

    // Allow the chip to finish any POR spin-up handshake before writing
    // configuration registers — ensures register writes are not ignored.
    delay(5);

    // ── Global configuration (register 0x20) ────────────────────────────
    // Bit 0: USE_EXT_CLK = 0 → use internal oscillator (no external clock)
    // Bit 2: CLK_OVR     = 1 → override CLK pin to use internal clock
    //                          even if the CLK pin is floating or unconnected
    // Result: 0x04
    controller_.writeRegister(EMC230X_REG_CONFIGURATION, 0x04);

    // ── Configure all three channels for direct-drive PWM ───────────────
    // For each channel: disable RPM closed-loop, clear minimum drive,
    // disable spin-up (prevents full-speed blasts on tach stall), set
    // tach parameters, and apply the initial LUT duty.
    // Channel 2 is unused but configured to prevent stall alerts.
    for (uint8_t ch = 0; ch < 3; ch++) {
        controller_.enableRPMControl(false, ch);
        controller_.setMinimumDrive(0, ch);
        // NOKICK=1, drive=0 %, time=0 — spin-up completely disabled
        controller_.writeRegister(0x36 + ch * 0x10, 0x20);
        // Set Valid TACH Count to maximum (0xFF) — raises the stall
        // threshold so slow fans at low duty aren't flagged.
        controller_.writeRegister(0x39 + ch * 0x10, 0xFF);
        controller_.setFanPoles(2, ch);
        controller_.setPWMBaseFrequency(EMC230X_PWM_BASEFREQ_26KHZ, ch);
        controller_.setPWMDivisor(1, ch);
    }

    // Disable all fan interrupts — in direct-drive mode we don't need the
    // chip to assert ALERT# for stall / spin-up / drive-fail conditions.
    // Written AFTER per-channel config to ensure no method re-enables bits.
    controller_.writeRegister(EMC230X_REG_FAN_INTERRUPT_EN, 0x00);

    // Clear any latched status from POR / channel config by reading all
    // status registers.  This releases ALERT# (open-drain returns HIGH).
    (void)controller_.getFanStatusRegister();
    (void)controller_.getStallStatusRegister();
    (void)controller_.getSpinStatusRegister();
    (void)controller_.getDriveFailStatusRegister();

    controller_.setTachRange(EMC230X_RANGE_500RPM, FAN_CHANNEL);
    controller_.setTachRange(EMC230X_RANGE_500RPM, PUMP_CHANNEL);

    // Apply initial duty from the lowest LUT entry for each channel.
    expectedDuty_[FAN_CHANNEL] = fanLut_.entries[0].duty;
    controller_.setDutyCycle(expectedDuty_[FAN_CHANNEL], FAN_CHANNEL);

    expectedDuty_[PUMP_CHANNEL] = pumpLut_.entries[0].duty;
    controller_.setDutyCycle(expectedDuty_[PUMP_CHANNEL], PUMP_CHANNEL);

    _Log.printf("EMC2303 configured — fan duty=%u  pump duty=%u\n",
                expectedDuty_[FAN_CHANNEL], expectedDuty_[PUMP_CHANNEL]);

    return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------
module::InitStatus init() {
    _Log.println(F("Initializing cooling system"));

    // ── EMC2303 ───────────────────────────────────────────────────────────
    {
        const module::InitStatus controllerStatus = controllerInit();
        if (controllerStatus != module::MODULE_INIT_SUCCESS) {
            // A failed I2C transaction can leave the ESP32's I2C driver
            // in a stuck state; recover so downstream modules init cleanly.
            hardware::recoverI2c();
            return controllerStatus;
        }
    }

    // ── ALERT# fault input ────────────────────────────────────────────────
    // External pull-up holds the line HIGH; EMC2303 pulls LOW on fault.
    pinMode(COOLING_FAN_FAULT_INDICATOR_PIN, INPUT);
    fanFaultActive_ = false;

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
    _Log.println(F("Cooling system initialized (EMC2303)"));
    return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// service
// ---------------------------------------------------------------------------
module::ServiceStatus service() {
    // ── Deferred init recovery ───────────────────────────────────────────
    // The EMC2303 is powered from a 3.3 V regulator stepped down from the
    // 12 V rail.  If 12 V is absent at boot, init() fails and service()
    // would permanently bail out.  Retry controllerInit() once per second
    // until the chip appears, then promote the module to INIT_SUCCESS.
    //
    // UNDERVOLTAGE is an intentional shutdown — do not attempt recovery.
    // The operator must reinit once system voltage is restored.
    if (Module::getInitStatus() == module::MODULE_INIT_UNDERVOLTAGE) {
        return module::MODULE_SERVICE_NOT_STARTED;
    }
    if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS) {
        static uint32_t lastRetryMs = 0;
        const uint32_t now = millis();
        if ((now - lastRetryMs) >= 1000u) {
            lastRetryMs = now;
            // Recover the bus before retrying — a previous failed transaction
            // may have left SDA stuck low, blocking all other I2C devices.
            hardware::recoverI2c();
            if (controllerInit() == module::MODULE_INIT_SUCCESS) {
                _Log.println(F("EMC2303 appeared — deferred init succeeded"));

                // Complete the rest of init that was skipped on first attempt
                pinMode(COOLING_FAN_FAULT_INDICATOR_PIN, INPUT);
                fanFaultActive_ = false;
                rpmAvg_.clear();
                pumpRpmAvg_.clear();
                flowPulseCount_ = 0u;
                pinMode(COOLING_FLOW_PIN, INPUT_PULLUP);
                attachInterrupt(digitalPinToInterrupt(COOLING_FLOW_PIN), onFlowPulse, FALLING);
                tempAvg_.clear();
                analogReadResolution(ADC_RESOLUTION);
                analogSetPinAttenuation(COOLING_TEMP_ADC_PIN, ADC_11db);

                const uint32_t initMs = millis();
                lastSampleMs_    = initMs;
                // Force the check cycle to fire immediately on the next
                // service() tick so the LUT evaluates and cachedDutyCycle_
                // is read from the chip right away — prevents the chart
                // from showing the POR default (255 = 100 %) for a full
                // second while waiting for the normal 1 s interval.
                lastCheckCycleMs = initMs - COOLING_CHECK_CYCLE_MS;

                enabled_       = true;
                coolingPumpOn_ = true;
                fanSpeed_      = 0u;
                forceFanSpeed_ = false;
                fanLut_.enabled  = true;
                pumpLut_.enabled = true;
                fanLut_.activeIndex  = -1;
                pumpLut_.activeIndex = -1;

                // Promote to SUCCESS so service() runs normally from here on
                Module::overrideInitStatus(module::MODULE_INIT_SUCCESS);
            }
        }
        return module::MODULE_SERVICE_NOT_STARTED;
    }

    const uint32_t nowMs = millis();
    bool didWork = false;

    // ── 100 ms flow-sensor sampling ─────────────────────────────────────
    // The Hall-effect flow sensor is purely GPIO / ISR-based — it must be
    // sampled independently of the EMC2303 I2C health check below so that
    // transient I2C NACKs don't zero-out the flow reading.
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
            (static_cast<float>(elapsed) / 60000.0f);

        rpmAvg_.addValue(sampledRpm);

        // Convert average RPM → L/h → L/min
        coolantFlowRate_ = rpmToLph(rpmAvg_.getAverage()) / 60.0f;

        didWork = true;
    }

    // ── I2C liveness check ──────────────────────────────────────────────
    // If the 12 V rail drops after boot, the EMC2303 loses power and I2C
    // reads return NACK.  Demote init status so the deferred-init retry
    // path (above) reconfigures the chip when 12 V returns.
    //
    // Require CONSECUTIVE failures before demoting — a single transient
    // NACK (common on a shared bus) should not trigger a full re-init,
    // which resets duty cycles and causes stall alerts.
    static constexpr uint8_t I2C_FAIL_THRESHOLD = 3;
    static uint8_t consecutiveI2cFailures = 0;

    if (!sensor_mock::isActive()) {
        TwoWire& i2c = hardware::i2c();
        i2c.beginTransmission(EMC2303_I2C_ADDRESS);
        if (i2c.endTransmission() != 0) {
            ++consecutiveI2cFailures;
            if (consecutiveI2cFailures >= I2C_FAIL_THRESHOLD) {
                _Log.printf("I2C: %u consecutive failures — demoting to HARDWARE_ERROR\n",
                            consecutiveI2cFailures);
                hardware::reportI2cError();
                hardware::recoverI2c();
                coolantTemperature_ = NAN;
                consecutiveI2cFailures = 0;
                Module::overrideInitStatus(module::MODULE_INIT_HARDWARE_ERROR);
            }
            return module::MODULE_SERVICE_OK;
        }
        consecutiveI2cFailures = 0;  // reset on success
    }

    // ── 1000 ms tracker update ──────────────────────────────────────────
    if ((nowMs - lastCheckCycleMs) < COOLING_CHECK_CYCLE_MS) {
        return didWork ? module::MODULE_SERVICE_OK : module::MODULE_SERVICE_SKIPPED;
    }

    lastCheckCycleMs = nowMs;
    didWork = true;

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

    // ── EMC2303 reads (cached) ──────────────────────────────────────────
    // Snapshot all values here.  Accessors return these cached copies so
    // that the telemetry emit path never touches the I2C bus outside
    // this function.
    cachedDutyCycle_ = controller_.getDutyCycle(FAN_CHANNEL);
    cachedFanRpm_    = controller_.getFanRPM(FAN_CHANNEL);

    // ── Self-healing guard ──────────────────────────────────────────────
    // After a 12 V power cycle the EMC2303 POR can leave the chip in its
    // default 100 % duty / RPM-control state.  If the cached duty diverges
    // from what we last programmed, reconfigure the channel immediately.
    for (uint8_t ch = 0; ch < 2; ++ch) {
        const uint8_t actual   = (ch == FAN_CHANNEL)
                                 ? cachedDutyCycle_
                                 : controller_.getDutyCycle(PUMP_CHANNEL);
        if (actual != expectedDuty_[ch]) {
            _Log.printf("ch%u duty mismatch: expected=%u actual=%u — re-applying\n",
                        ch, expectedDuty_[ch], actual);
            controller_.enableRPMControl(false, ch);
            controller_.writeRegister(0x36 + ch * 0x10, 0x20); // NOKICK
            controller_.setDutyCycle(expectedDuty_[ch], ch);
        }
    }
    // Re-read after potential fix-up
    cachedDutyCycle_ = controller_.getDutyCycle(FAN_CHANNEL);

    const uint8_t  rawPumpDuty = controller_.getDutyCycle(PUMP_CHANNEL);
    const uint16_t rawPumpRpm  = controller_.getFanRPM(PUMP_CHANNEL);

    cachedPumpDutyCycle_ = rawPumpDuty;
    pumpRpmAvg_.addValue(static_cast<float>(rawPumpRpm));
    cachedPumpRpm_ = static_cast<uint16_t>(pumpRpmAvg_.getAverage());

    // ── Per-second RPM / duty logging (always visible) ──────────────────
    ESP_LOGV(TAG, "fan: duty=%u rpm=%u  |  pump: hwDuty=%u norm=%u%% rpm=%u avgRpm=%u  |  coolantT=%.1f\n",
                cachedDutyCycle_, cachedFanRpm_,
                rawPumpDuty, pumpHwToNorm(rawPumpDuty),
                rawPumpRpm, cachedPumpRpm_, coolantTemperature_);

    // Flag when raw RPM drops to zero — indicates a TACH dropout.
    if (rawPumpRpm == 0) {
        ESP_LOGW(TAG, "pump: TACH dropout — rawRPM=0 (hwDuty=%u, norm=%u%%)",
                 rawPumpDuty, pumpHwToNorm(rawPumpDuty));
    }

    // ── EMC2303 ALERT# fault detection ──────────────────────────────────
    // ALERT# is active-low, latched.  We only read status registers when
    // the pin is actually asserted — this avoids unnecessary I2C traffic
    // every tick and gives us a reliable "fault active right now" signal.
    const bool alertAsserted = (digitalRead(COOLING_FAN_FAULT_INDICATOR_PIN) == LOW);

    if (alertAsserted) {
        // Read all four status registers — this also clears the latch.
        const uint8_t fanStatusReg       = controller_.getFanStatusRegister();
        const uint8_t stallStatusReg     = controller_.getStallStatusRegister();
        const uint8_t spinStatusReg      = controller_.getSpinStatusRegister();
        const uint8_t driveFailStatusReg = controller_.getDriveFailStatusRegister();

        // 0xFF on ANY register likely means the I2C read failed (bus
        // returned all-ones for that byte).  Discard the entire set —
        // partial garbage is not actionable.
        const bool bogusRead = (fanStatusReg == 0xFF || stallStatusReg == 0xFF ||
                                spinStatusReg == 0xFF || driveFailStatusReg == 0xFF);

        if (!bogusRead) {
            if (!fanFaultActive_) {
                // Rising edge — first detection this episode
                fanFaultActive_  = true;
                fanFaultSinceMs_ = nowMs;
            }

            // Log only when the status pattern changes (avoids spam from
            // sustained low-duty stall at low RPM).
            if (fanStatusReg != lastFanStatus_ || stallStatusReg != lastStallStatus_ ||
                spinStatusReg != lastSpinStatus_ || driveFailStatusReg != lastDriveStatus_) {
                lastFanStatus_   = fanStatusReg;
                lastStallStatus_ = stallStatusReg;
                lastSpinStatus_  = spinStatusReg;
                lastDriveStatus_ = driveFailStatusReg;

                _Log.printf("ALERT# asserted — fan=0x%02X stall=0x%02X spin=0x%02X drive=0x%02X\n",
                            fanStatusReg, stallStatusReg, spinStatusReg, driveFailStatusReg);

                // Decode individual bits (3 channels → bits 0, 1, 2)
                if (stallStatusReg & 0x01) _Log.println(F("  ch0 (fan):  STALL detected"));
                if (stallStatusReg & 0x02) _Log.println(F("  ch1 (pump): STALL detected"));
                if (spinStatusReg  & 0x01) _Log.println(F("  ch0 (fan):  spin-up FAIL"));
                if (spinStatusReg  & 0x02) _Log.println(F("  ch1 (pump): spin-up FAIL"));
                if (driveFailStatusReg & 0x01) _Log.println(F("  ch0 (fan):  drive FAIL"));
                if (driveFailStatusReg & 0x02) _Log.println(F("  ch1 (pump): drive FAIL"));
            }
        }
    } else {
        // ALERT# released — fault cleared
        if (fanFaultActive_) {
            const uint32_t durationMs = nowMs - fanFaultSinceMs_;
            _Log.printf("ALERT# cleared after %lu ms\n",
                        static_cast<unsigned long>(durationMs));
            fanFaultActive_  = false;
            lastFanStatus_   = 0;
            lastStallStatus_ = 0;
            lastSpinStatus_  = 0;
            lastDriveStatus_ = 0;
        }
    }

    const uint8_t fanDutyCycle = cachedDutyCycle_;

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
        const float normPumpPct = static_cast<float>(pumpHwToNorm(cachedPumpDutyCycle_));
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
// With force=true: disables the software LUT and drives the fan at the given
// duty cycle until enable() is called (which re-activates the LUT).
// With force=false: no-op while the LUT is active.
// ---------------------------------------------------------------------------
void setFanSpeed(uint8_t percentage, bool force) {
    if (!force) {
        ESP_LOGD(TAG, "setFanSpeed(%u): ignored — LUT is active (use force=true to override)", percentage);
        return;
    }

    // Convert 0–100 % → 0–255 raw duty for the EMC2303.
    const uint8_t duty = static_cast<uint8_t>((static_cast<uint16_t>(percentage) * 255u) / 100u);

    _Log.printf("setFanSpeed(%u%% -> duty %u/255): LUT disabled\n", percentage, duty);
    forceFanSpeed_  = true;
    fanLut_.enabled = false;

    controller_.setDutyCycle(duty, FAN_CHANNEL);
    expectedDuty_[FAN_CHANNEL] = duty;

    fanSpeed_ = percentage;
    fanTracker_.reset();
}

// ---------------------------------------------------------------------------
// setPumpSpeed — manual override for diagnostic testing
//
// Accepts a normalised pump speed (0–100 %).  Converts to the hardware
// duty range (0–COOLING_PUMP_MAX_DUTY_PCT) before writing to the EMC2303.
// Disables the pump LUT; call enable() to restore LUT control.
// ---------------------------------------------------------------------------
void setPumpSpeed(uint8_t percentage) {
    const uint8_t hwDuty = pumpNormToHw(percentage);

    _Log.printf("setPumpSpeed(%u%% norm -> %u hw): LUT disabled\n", percentage, hwDuty);

    pumpLut_.enabled = false;
    controller_.setDutyCycle(hwDuty, PUMP_CHANNEL);
    expectedDuty_[PUMP_CHANNEL] = hwDuty;
}

// ---------------------------------------------------------------------------
// setFanDutyCycle — raw duty override (0–255)
//
// Bypasses percentage conversion; writes the value directly to the EMC2303.
// Disables the fan LUT; call enable() to restore LUT control.
// ---------------------------------------------------------------------------
void setFanDutyCycle(uint8_t duty) {
    _Log.printf("setFanDutyCycle(%u): LUT disabled\n", duty);
    forceFanSpeed_  = true;
    fanLut_.enabled = false;

    controller_.setDutyCycle(duty, FAN_CHANNEL);
    expectedDuty_[FAN_CHANNEL] = duty;

    fanSpeed_ = 0;
    fanTracker_.reset();
}

// ---------------------------------------------------------------------------
// setPumpDutyCycle — raw duty override (0–255)
//
// Bypasses normalised-percentage conversion; writes the value directly to the
// EMC2303.  Disables the pump LUT; call enable() to restore LUT control.
// ---------------------------------------------------------------------------
void setPumpDutyCycle(uint8_t duty) {
    _Log.printf("setPumpDutyCycle(%u): LUT disabled\n", duty);

    pumpLut_.enabled = false;
    controller_.setDutyCycle(duty, PUMP_CHANNEL);
    expectedDuty_[PUMP_CHANNEL] = duty;
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
    controller_.setDutyCycle(0, FAN_CHANNEL);
    controller_.setDutyCycle(0, PUMP_CHANNEL);
    expectedDuty_[FAN_CHANNEL]  = 0;
    expectedDuty_[PUMP_CHANNEL] = 0;

    ESP_LOGD(TAG, "disable(): fan and pump stopped, LUTs disabled");
}

bool isEnabled() { return enabled_; }

bool hasFanFault() { return fanFaultActive_; }

uint32_t getFanFaultDurationMs() {
    if (!fanFaultActive_) return 0;
    return millis() - fanFaultSinceMs_;
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
    using S = TrackingMonitor<float>::State;
    const auto a = fanTracker_.getState();
    const auto b = coolantTempTracker_.getState();
    const auto c = flowTracker_.getState();
    if (a == S::FAULT || b == S::FAULT || c == S::FAULT) return S::FAULT;
    if (a == S::WARNING || b == S::WARNING || c == S::WARNING) return S::WARNING;
    return S::IN_RANGE;
}

} // namespace cooling
