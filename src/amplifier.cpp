/**
 * @file amplifier.cpp
 * @brief Amplifier control implementation
 *
 * Owns the full amplifier signal chain:
 *   AD9833 waveform generator  →  amplifier board  →  ACS37800 power monitor
 *   MCP4921 12-bit SPI DAC                            (amplitude control)
 *
 * The former dac / waveform / rms modules have been consolidated here.
 *
 * MCP4921 16-bit SPI packet format:
 *   [15]    ~A/B  : 0 = DAC A
 *   [14]    BUF   : 1 = Buffered Vref
 *   [13]    ~GA   : 1 = 1x gain
 *   [12]    ~SHDN : 1 = Output active
 *   [11:0]  D11-D0: 12-bit data
 *   Control nibble 0b0111 -> top 4 bits = 0x3000
 */

#include <Arduino.h>
#include <SPI.h>
#include <ACS37800.h>
#include <MD_AD9833.h>

#include "pin_config.h"
#include "config.h"
#include "amplifier.h"
#include "conversions.h"
#include "module.h"
#include "imu.h"
#include "sensor_mock.h"
#include "hardware.h"

// ---------------------------------------------------------------------------
// Module-private state
// ---------------------------------------------------------------------------

// Waveform generator (AD9833 over SPI)
static MD_AD9833 ad9833_(AD9833_CS);

// RMS power monitor (ACS37800 over I2C)
static ACS37800 acs_;

// MCP4921 12-bit SPI DAC — amplitude control
static constexpr uint16_t MCP4921_CTRL_BITS = 0x3000; // ~A/B=0, BUF=1, ~GA=1, ~SHDN=1
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

static module::InitStatus    initStatus_    = module::MODULE_INIT_NOT_STARTED;
static module::ServiceStatus serviceStatus_ = module::MODULE_SERVICE_NOT_STARTED;
static bool enabled_ = false;

// ---------------------------------------------------------------------------
// Internal DAC helpers
// ---------------------------------------------------------------------------

static void dacWriteSpi(uint16_t dacVal) {
    if (dacVal > static_cast<uint16_t>(AMPLIFIER_RESOLUTION)) {
        dacVal = static_cast<uint16_t>(AMPLIFIER_RESOLUTION);
    }
    if (dacCurrent_ == dacVal) return;

    dacCurrent_ = dacVal;
    const uint16_t packet = MCP4921_CTRL_BITS | dacVal;

    SPI.beginTransaction(SPISettings(AMPLIFIER_DAC_SPI_SPEED, MSBFIRST, SPI_MODE0));
    digitalWrite(MCP4921_CS, LOW);
    SPI.transfer16(packet);
    digitalWrite(MCP4921_CS, HIGH);
    SPI.endTransaction();
}

/**
 * Rate-limited step toward @p target by at most @p maxStep counts per call.
 */
static void dacRampInternal(uint16_t target, uint16_t maxStep) {
    if (target > static_cast<uint16_t>(AMPLIFIER_RESOLUTION)) {
        target = static_cast<uint16_t>(AMPLIFIER_RESOLUTION);
    }
    uint16_t next = dacCurrent_;
    if (next < target) {
        const uint16_t step = target - next;
        next += (step > maxStep) ? maxStep : step;
    } else if (next > target) {
        const uint16_t step = next - target;
        next -= (step > maxStep) ? maxStep : step;
    }
    dacWriteSpi(next);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace amplifier {

module::InitStatus init() {
    if (!checkDependencies() && !sensor_mock::isActive()) {
        initStatus_ = module::MODULE_INIT_DEPENDENCY_ERROR;
        return initStatus_;
    }

    // -- MCP4921 DAC ----------------------------------------------------------
    Serial.println(F("[amplifier] Initializing MCP4921 DAC..."));
    initStatus_ = initDac();
    if (initStatus_ != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[amplifier] MCP4921 initialization failed: %d\n",
                      static_cast<int>(initStatus_));
        return initStatus_;
    }
    Serial.println(F("[amplifier] MCP4921 DAC initialized"));

    // -- ACS37800 -------------------------------------------------------------
    Serial.println(F("[amplifier] Initializing ACS37800..."));
    initStatus_ = initAcs();
    if (initStatus_ != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[amplifier] ACS37800 initialization failed: %d\n",
                      static_cast<int>(initStatus_));
        return initStatus_;
    }
    Serial.println(F("[amplifier] ACS37800 initialized"));

    // -- AD9833 waveform generator --------------------------------------------
    Serial.println(F("[amplifier] Initializing AD9833..."));
    initStatus_ = initWaveform();
    if (initStatus_ != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[amplifier] AD9833 initialization failed: %d\n",
                      static_cast<int>(initStatus_));
        return initStatus_;
    }
    Serial.println(F("[amplifier] AD9833 initialized"));

    Serial.println(F("[amplifier] Initialization successful"));
    initStatus_ = module::MODULE_INIT_SUCCESS;
    return initStatus_;
}

module::InitStatus initDac() {
    pinMode(MCP4921_CS, OUTPUT);
    digitalWrite(MCP4921_CS, HIGH);
    dacWriteSpi(0u);
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initWaveform() {
    ad9833_.begin();
    ad9833_.setMode(MD_AD9833::MODE_SINE);
    waveformMode_ = MD_AD9833::MODE_SINE;
    setFrequency(static_cast<float>(AMPLIFIER_FREQ_HZ));
    Serial.printf("[amplifier] AD9833 generating %u Hz sine wave\n",
                  static_cast<unsigned>(AMPLIFIER_FREQ_HZ));
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initAcs() {
    acs_.setBus(&hardware::i2c());
    acs_.setBoardPololu(4);
    acs_.setSampleCount(0);

    if (acs_.getLastError()) {
        Serial.printf("[amplifier] ACS37800 init error: %d\n",
                      static_cast<int>(acs_.getLastError()));
        return module::MODULE_INIT_HARDWARE_ERROR;
    }
    return module::MODULE_INIT_SUCCESS;
}

bool checkDependencies() {
    return true;
}

bool isEnabled() {
    return enabled_ && (waveformMode_ != MD_AD9833::MODE_OFF);
}

void setFrequency(float frequencyHz) {
    frequency_ = frequencyHz;
    ad9833_.setFrequency(MD_AD9833::CHAN_0, frequencyHz);
}

float getFrequency() {
    return frequency_;
}

void enable() {
    ad9833_.setMode(MD_AD9833::MODE_SINE);
    waveformMode_ = MD_AD9833::MODE_SINE;
    enabled_ = true;
}

void disable() {
    ad9833_.setMode(MD_AD9833::MODE_OFF);
    waveformMode_ = MD_AD9833::MODE_OFF;
    enabled_ = false;
}

// ---------------------------------------------------------------------------
// DAC / amplitude control
// ---------------------------------------------------------------------------

void rampToVoltageV(uint16_t dacTarget) {
    dacRampInternal(dacTarget,
                    static_cast<uint16_t>(AMPLIFIER_MAX_STEP_PER_INTERVAL));
}

void rampTowardShutdown(uint16_t dacTarget) {
    dacRampInternal(dacTarget,
                    static_cast<uint16_t>(AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL));
}

void setRmsVoltageV(uint16_t dacTarget) {
    dacWriteSpi(dacTarget);
}

uint16_t getDacCurrent() {
    return dacCurrent_;
}

// ---------------------------------------------------------------------------
// Service -- reads ACS37800; must be called every main-loop tick
// ---------------------------------------------------------------------------

module::ServiceStatus service() {
    acs_.readRMSVoltageAndCurrent();
    lastRmsVoltage_ = static_cast<float>(acs_.rmsVoltageMillivolts) / 1000.0f;
    lastRmsCurrent_ = static_cast<float>(acs_.rmsCurrentMilliamps)  / 1000.0f;
    lastFrequency_  = imu::getFrequencyHz();
    serviceStatus_  = module::MODULE_SERVICE_OK;
    return serviceStatus_;
}

// ---------------------------------------------------------------------------
// ACS37800 getters
// ---------------------------------------------------------------------------

float getLastRmsVoltageV()   { return lastRmsVoltage_; }
float getLastRmsCurrentA()   { return lastRmsCurrent_; }
float getOutputRmsVoltageV() { return lastRmsVoltage_; }
float getOutputRmsCurrentA() { return lastRmsCurrent_; }

// ---------------------------------------------------------------------------
// Output validation
// ---------------------------------------------------------------------------

bool verifyFrequency(float toleranceHz) {
    const float measured = imu::getFrequencyHz();
    if (!isfinite(measured)) return false;
    return fabsf(measured - frequency_) <= toleranceHz;
}

bool checkOutput(float tolerance) {
    // @todo Verify lastRmsVoltage_ is within tolerance of programmed set-point.
    (void)tolerance;
    return verifyFrequency();
}

} // namespace amplifier
