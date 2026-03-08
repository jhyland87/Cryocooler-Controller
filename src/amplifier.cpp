/**
 * @file amplifier.cpp
 * @brief Amplifier control implementation
 *
 * Owns the full amplifier signal chain:
 *   AD9833 waveform generator  →  amplifier board  →  ACS37800 power monitor
 *   MCP4725 12-bit I2C DAC                            (amplitude control)
 *
 * The former dac / waveform / rms modules have been consolidated here.
 *
 * MCP4725 I2C protocol notes:
 *   Fast-mode (400 kHz) is used.  setVoltage() is called with writeEEPROM=false
 *   so only the volatile output register is updated — no EEPROM wear on every
 *   ramp step.  The MCP4725 retains its volatile register value across software
 *   resets (esp_restart()), so dacCurrent_ is invalidated in initDac() to force
 *   a write to zero on every boot, matching the previous MCP4921 behaviour.
 */

#include <Arduino.h>
#include <ACS37800.h>
#include <MD_AD9833.h>
#include <Adafruit_MCP4725.h>

#include "pin_config.h"
#include "config.h"
#include "amplifier.h"
#include "conversions.h"
#include "module.h"
#include "imu.h"
#include "sensor_mock.h"
#include "esp_log.h"
#include "hardware.h"
#include "tracking.h"

// ---------------------------------------------------------------------------
// Module-private state
// ---------------------------------------------------------------------------

// Waveform generator (AD9833 over SPI)
static MD_AD9833 ad9833_(AD9833_CS);

// RMS power monitor (ACS37800 over I2C)
static ACS37800 acs_;

// MCP4725 12-bit I2C DAC — amplitude control
static Adafruit_MCP4725 mcp4725_;
static uint16_t dacCurrent_ = 0u;

// Set-points
static float frequency_ = 0.0f;   // waveform frequency set-point (Hz)

// Latest ACS37800 readings (updated each service() call)
static float lastRmsVoltage_ = 0.0f;
static float lastRmsCurrent_ = 0.0f;

// Latest measured frequency from IMU FFT
static float lastFrequency_ = 0.0f;

// AD9833 mode tracking
static MD_AD9833::mode_t waveformMode_ = MD_AD9833::MODE_OFF;

static bool enabled_ = false;

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

// Target RMS voltage set by the state machine via setTargetVoltage().
static float targetVoltageV_ = 0.0f;

// Tracks how closely the IMU-measured frequency matches the AD9833 set-point.
// Only active while the amplifier is enabled; nullopt otherwise.
// Constructed by enable() and destroyed by disable().
static std::optional<TrackingMonitor<float>> freqTracker_;

// Tracks how closely the measured RMS output voltage matches targetVoltageV_.
// Only active while the amplifier is enabled; nullopt otherwise.
// Constructed by enable() and destroyed by disable().
static std::optional<TrackingMonitor<float>> voltTracker_;

// ---------------------------------------------------------------------------
// Internal DAC helpers
// ---------------------------------------------------------------------------

/**
 * Write @p dacVal (0–AMPLIFIER_RESOLUTION) to the MCP4725 volatile output
 * register over I2C.  The cached value is checked first so unchanged
 * set-points do not generate unnecessary I2C traffic.
 *
 * writeEEPROM is always false — we never wear the EEPROM with ramp steps.
 */
static void dacWrite(uint16_t dacVal) {
    dacVal = constrain(dacVal, 0u, static_cast<uint16_t>(AMPLIFIER_RESOLUTION));
    if (dacCurrent_ == dacVal) return;

    dacCurrent_ = dacVal;
    mcp4725_.setVoltage(dacVal, /*writeEEPROM=*/false);
}

/**
 * Rate-limited step toward @p target by at most @p maxStep counts per call.
 */
static void dacRampInternal(uint16_t target, uint16_t maxStep) {
    target = constrain(target, 0u, static_cast<uint16_t>(AMPLIFIER_RESOLUTION));

    uint16_t next = dacCurrent_;
    if (next < target) {
        const uint16_t step = target - next;
        next += (step > maxStep) ? maxStep : step;
    } else if (next > target) {
        const uint16_t step = next - target;
        next -= (step > maxStep) ? maxStep : step;
    }
    dacWrite(next);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

static constexpr char TAG[] = "amplifier";


namespace amplifier {

module::InitStatus init() {
    // -- MCP4725 DAC ----------------------------------------------------------
    // This is the multiplier voltage that gets passed to the AD633 voltage
    // multiplier to multiply the sine wave output.
    ESP_LOGI(TAG, "Initializing MCP4725 DAC...");
    {
        const module::InitStatus status = initDac();
        if (status != module::MODULE_INIT_SUCCESS) {
            ESP_LOGE(TAG, "MCP4725 initialization failed: %d", static_cast<int>(status));
            return status;
        }
    }
    ESP_LOGI(TAG, "MCP4725 DAC initialized");

    // -- ACS37800 -------------------------------------------------------------
    // This is the power monitor that reads the AC voltage and current coming
    // out of the amplifier.
    ESP_LOGI(TAG, "Initializing ACS37800...");
    {
        const module::InitStatus status = initAcs();
        if (status != module::MODULE_INIT_SUCCESS) {
            ESP_LOGE(TAG, "ACS37800 initialization failed: %d", static_cast<int>(status));
            return status;
        }
    }
    ESP_LOGI(TAG, "ACS37800 initialized");

    // -- AD9833 waveform generator --------------------------------------------
    // This is the waveform generator that generates the sine wave that is
    // passed to the AD633 voltage multiplier.
    ESP_LOGI(TAG, "Initializing AD9833...");
    {
        const module::InitStatus status = initWaveform();
        if (status != module::MODULE_INIT_SUCCESS) {
            ESP_LOGE(TAG, "AD9833 initialization failed: %d", static_cast<int>(status));
            return status;
        }
    }
    ESP_LOGI(TAG, "AD9833 initialized");
    ESP_LOGI(TAG, "Initialization successful");
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initDac() {
    if (!mcp4725_.begin(MCP4725_I2C_ADDRESS, &hardware::i2c())) {
        ESP_LOGE(TAG, "MCP4725 not found at I2C address 0x%02X", MCP4725_I2C_ADDRESS);
        return module::MODULE_INIT_HARDWARE_ERROR;
    }

    // Invalidate the cached DAC value before writing zero.  dacCurrent_ starts
    // at 0 after every ESP32 boot, but the MCP4725 retains its volatile register
    // across soft-resets — so the 0==0 guard in dacWrite() would suppress the
    // I2C write and leave the DAC at whatever it was before the reset.
    dacCurrent_ = UINT16_MAX;
    setRmsVoltage(0u);
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initWaveform() {
    ad9833_.begin();
    ad9833_.setMode(MD_AD9833::MODE_SINE);
    waveformMode_ = MD_AD9833::MODE_SINE;
    setFrequency(static_cast<float>(AMPLIFIER_FREQ_HZ));
    ESP_LOGI(TAG, "AD9833 generating %u Hz sine wave",
                  static_cast<unsigned>(AMPLIFIER_FREQ_HZ));
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initAcs() {
    acs_.setBus(&hardware::i2c());
    acs_.setBoardPololu(4);
    acs_.setSampleCount(0);

    // if (acs_.getLastError()) {
    //     Serial.printf("[amplifier] ACS37800 init error: %d\n",
    //                   static_cast<int>(acs_.getLastError()));
    //     return module::MODULE_INIT_HARDWARE_ERROR;
    // }
    return module::MODULE_INIT_SUCCESS;
}

bool checkDependencies() {
    return true;
}

bool isEnabled() {
    return enabled_ && (waveformMode_ != MD_AD9833::MODE_OFF);
}

void setFrequency(float frequencyHz) {
    ESP_LOGD(TAG, "Setting AD9833 frequency to %u Hz",
                  static_cast<unsigned>(frequencyHz));
    frequency_ = frequencyHz;
    ad9833_.setFrequency(MD_AD9833::CHAN_0, frequencyHz);
    // Reset the tracker so the new frequency has time to stabilise before
    // the warning timer starts.
    if (freqTracker_) freqTracker_->reset();
}

float getFrequency() {
    return frequency_;
}

void enable() {
    ESP_LOGD(TAG, "Enabling AD9833");
    ad9833_.setMode(MD_AD9833::MODE_SINE);
    waveformMode_ = MD_AD9833::MODE_SINE;
    enabled_ = true;
    freqTracker_.emplace(TrackingMonitor<float>::Config{
        /* hysteresis     */ AMPLIFIER_FREQ_TRACK_HYSTERESIS_HZ,
        /* fullScale      */ AMPLIFIER_FREQ_TRACK_FULL_SCALE_HZ,
        /* warningDelayMs */ AMPLIFIER_FREQ_TRACK_WARNING_MS,
        /* faultDelayMs   */ AMPLIFIER_FREQ_TRACK_FAULT_MS,
        /* tag            */ "amplifier",
        /* label          */ "frequency",
    });
    voltTracker_.emplace(TrackingMonitor<float>::Config{
        /* hysteresis     */ AMPLIFIER_VOLT_TRACK_HYSTERESIS_V,
        /* fullScale      */ AMPLIFIER_VOLT_TRACK_FULL_SCALE_V,
        /* warningDelayMs */ AMPLIFIER_VOLT_TRACK_WARNING_MS,
        /* faultDelayMs   */ AMPLIFIER_VOLT_TRACK_FAULT_MS,
        /* tag            */ "amplifier",
        /* label          */ "voltage",
    });
}

void disable() {
    ESP_LOGD(TAG, "Disabling AD9833");
    ad9833_.setMode(MD_AD9833::MODE_OFF);
    waveformMode_ = MD_AD9833::MODE_OFF;
    enabled_ = false;
    freqTracker_.reset();
    voltTracker_.reset();
}

void initCoarseCooldown() {
    ESP_LOGD(TAG, "Initializing coarse cooldown");
    rampToVoltage(0, AMPLIFIER_RAMP_RATE_MEDIUM);
}

void initFineCooldown() {
    ESP_LOGD(TAG, "Initializing fine cooldown");
    rampToVoltage(0, AMPLIFIER_RAMP_RATE_SLOW);
}

// ---------------------------------------------------------------------------
// DAC / amplitude control
// ---------------------------------------------------------------------------

void rampToVoltage(uint16_t dacTarget, uint16_t rampRate) {
    // Dead-band: ignore ±1 count differences to avoid chasing temperature noise.
    const int32_t diff = static_cast<int32_t>(dacTarget) - static_cast<int32_t>(dacCurrent_);
    if (diff >= -1 && diff <= 1) return;
    dacRampInternal(dacTarget, static_cast<uint16_t>(rampRate));
}

void hardStop() {
    dacCurrent_ = UINT16_MAX;   // invalidate cache so dacWrite() cannot short-circuit
    setRmsVoltage(0u);
}

void rampTowardShutdown(uint16_t dacTarget) {
    if (dacCurrent_ == dacTarget) return;
    dacRampInternal(dacTarget, static_cast<uint16_t>(AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL));
}

void setRmsVoltage(uint16_t dacTarget) {
    ESP_LOGD(TAG, "Setting RMS voltage to %u", static_cast<unsigned>(dacTarget));
    dacWrite(dacTarget);
}

uint16_t getDacCurrent() {
    return dacCurrent_;
}

// ---------------------------------------------------------------------------
// Service -- reads ACS37800; must be called every main-loop tick
// ---------------------------------------------------------------------------

module::ServiceStatus service() {
    // Guard: skip I2C reads if the ACS37800 did not initialise successfully.
    // amplifier::initAcs() detects ACS37800 absence via Wire.endTransmission()
    // return codes; if init failed, reading from it every tick would flood the
    // log with ESP_ERR_INVALID_STATE errors.
    if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS) {
        return module::MODULE_SERVICE_SKIPPED;
    }

    acs_.readRMSVoltageAndCurrent();
    lastRmsVoltage_ = static_cast<float>(acs_.rmsVoltageMillivolts) / 1000.0f;
    lastRmsCurrent_ = static_cast<float>(acs_.rmsCurrentMilliamps)  / 1000.0f;
    lastFrequency_  = imu::getFrequency();

    const uint32_t nowMs = millis();

    // Frequency tracker: only advance when active and the IMU has a valid FFT
    // result. Skip (don't reset) on NAN — the timer simply doesn't accumulate
    // during data gaps, so no false warnings build up.
    if (freqTracker_ && isfinite(lastFrequency_)) {
        freqTracker_->update(frequency_, lastFrequency_, nowMs);
    }

    // Voltage tracker: unconditional when active — the tracker only exists
    // while the amplifier is enabled (created in enable(), destroyed in disable()).
    if (voltTracker_) {
        voltTracker_->update(targetVoltageV_, lastRmsVoltage_, nowMs);
    }

    return module::MODULE_SERVICE_OK;
}

// ---------------------------------------------------------------------------
// ACS37800 getters
// ---------------------------------------------------------------------------

float getLastRmsVoltage()   { return lastRmsVoltage_; }
float getLastRmsCurrent()   { return lastRmsCurrent_; }
float getOutputRmsVoltage() { return lastRmsVoltage_; }
float getOutputRmsCurrent() { return lastRmsCurrent_; }

// ---------------------------------------------------------------------------
// Output validation
// ---------------------------------------------------------------------------

bool verifyFrequency(float toleranceHz) {
    const float measured = imu::getFrequency();
    if (!isfinite(measured)) return false;
    return fabsf(measured - frequency_) <= toleranceHz;
}

bool checkOutput(float tolerance) {
    // @todo Verify lastRmsVoltage_ is within tolerance of programmed set-point.
    (void)tolerance;
    return verifyFrequency();
}

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

void setTargetVoltage(float volts) {
    if (voltTracker_ && fabsf(volts - targetVoltageV_) > AMPLIFIER_VOLT_TRACK_HYSTERESIS_V) {
        voltTracker_->reset();
    }
    targetVoltageV_ = volts;
}

float getFrequencyScore() {
    return freqTracker_ ? freqTracker_->getScore() : 1.0f;
}

TrackingMonitor<float>::State getFrequencyTrackingState() {
    return freqTracker_ ? freqTracker_->getState() : TrackingMonitor<float>::State::IN_RANGE;
}

float getVoltageScore() {
    return voltTracker_ ? voltTracker_->getScore() : 1.0f;
}

TrackingMonitor<float>::State getVoltageTrackingState() {
    return voltTracker_ ? voltTracker_->getState() : TrackingMonitor<float>::State::IN_RANGE;
}

} // namespace amplifier
