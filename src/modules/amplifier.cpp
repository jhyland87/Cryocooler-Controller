/**
 * @file amplifier.cpp
 * @brief Amplifier control implementation
 *
 * Owns the full amplifier signal chain:
 *   AD9833 waveform generator  →  amplifier board  →  ACS37800 power monitor
 *   MCP4921 12-bit SPI DAC                              (amplitude control)
 *
 * The former dac / waveform / rms modules have been consolidated here.
 *
 * MCP4921 SPI protocol notes:
 *   16-bit frame: [0 BUF GA SHDN D7..D0 xxxx].  We use unbuffered, 1× gain,
 *   active mode (0x3000 | data<<4).  SPI Mode 0, up to 20 MHz clock.
 *   The DAC output is volatile — resets to 0 on power cycle.
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
#include "esp_log.h"
#include "hardware.h"
#include "tracking.h"
#include "tick.h"
#include "logger.h"

// ---------------------------------------------------------------------------
// Module-private state
// ---------------------------------------------------------------------------

static constexpr char TAG[] = "amplifier";
static LogStream _Log = Log.createChildLogger("amplifier");


/// Set true by initDac() once the MCP4921 CS pin is configured and a test
/// write completes.  Guards dacWrite() so that hardStop() / setOutput()
/// never fire SPI transactions before init.
static bool sDacAvailable = false;

/// True while the relay output is energised (cached).
static bool sRelayOn = false;

// Waveform generator (AD9833 over SPI)
static MD_AD9833 ad9833_(AD9833_CS);

// RMS power monitor (ACS37800 over SPI — dedicated SPI3 bus)
static ACS37800 acs_(&hardware::acsSpi(), ACS37800_CS);
static bool sAcsAvailable = false;

// MCP4921 12-bit SPI DAC — amplitude control
// SPI settings: Mode 0 (CPOL=0 CPHA=0), MSB first, 4 MHz (MCP4921 supports up to 20 MHz)
static const SPISettings sMcp4901Spi(4000000, MSBFIRST, SPI_MODE0);
uint16_t dacCurrent_ = 0u;

// Manual vout override — set by the "set vout" command to prevent the FSM
// tick from re-applying its computed cooldown target each cycle.
// Cleared automatically when the FSM enters Idle, Shutdown, or Fault.
static bool  voutOverrideActive_ = false;
static float voutOverride_       = 0.0f;

// Set-points
float frequency_ = 0.0f;   // waveform frequency set-point (Hz)

// Latest ACS37800 readings (updated each service() call)
float lastRmsVoltage_      = 0.0f;
float lastRmsCurrent_      = 0.0f;
float lastApparentPowerW_  = 0.0f;

// Latest measured frequency from IMU FFT
float lastFrequency_ = 0.0f;

// AD9833 mode tracking
MD_AD9833::mode_t waveformMode_ = MD_AD9833::MODE_OFF;

bool enabled_ = false;

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
// Internal relay helper
// ---------------------------------------------------------------------------

/**
 * Drive the relay via a GPIO pin (HIGH = closed, LOW = open).
 */
static void setRelay(bool on) {
    if (on == sRelayOn) return;
    sRelayOn = on;
    digitalWrite(AMPLIFIER_RELAY_PIN, on ? HIGH : LOW);
    ESP_LOGD(TAG, "Relay → %s", on ? "ON" : "OFF");
}

// ---------------------------------------------------------------------------
// Internal DAC helpers
// ---------------------------------------------------------------------------

/**
 * Write @p dacVal (0–AMPLIFIER_RESOLUTION) to the MCP4921 DAC via SPI.
 * The cached value is checked first so unchanged set-points do not
 * generate unnecessary SPI traffic.
 *
 * MCP4921 16-bit command frame:
 *   Bit 15   : 0      (channel A — only channel on MCP4921)
 *   Bit 14   : BUF=0  (unbuffered Vref input)
 *   Bit 13   : GA=1   (1× output gain)
 *   Bit 12   : SHDN=1 (active mode, output enabled)
 *   Bits 11-0: D11..D0 (12-bit data)
 */
static void dacWrite(uint16_t dacVal) {
    if (!sDacAvailable) return;
    dacVal = constrain(dacVal, 0u, static_cast<uint16_t>(AMPLIFIER_RESOLUTION));
    if (dacCurrent_ == dacVal) return;

    ESP_LOGD(TAG, "Writing DAC value: %u", dacVal);

    const uint16_t cmd = 0x3000u | (dacVal & 0x0FFFu);
    SPI.beginTransaction(sMcp4901Spi);
    digitalWrite(MCP4921_CS, LOW);
    SPI.transfer16(cmd);
    digitalWrite(MCP4921_CS, HIGH);
    SPI.endTransaction();

    dacCurrent_ = dacVal;
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

namespace amplifier {

module::InitStatus init() {
    // -- Qwiic Single Relay ---------------------------------------------------
    _Log.println(F("Initializing amplifier relay (GPIO)..."));
    {
        const module::InitStatus status = initRelay();
        if (status != module::MODULE_INIT_SUCCESS) {
            ESP_LOGE(TAG, "Amplifier relay initialization failed: %d", static_cast<int>(status));
            _Log.printf("Amplifier relay initialization failed: %d\n", static_cast<int>(status));
            return status;
        }
    }
    _Log.println(F("Amplifier relay initialized"));

    // -- MCP4901 DAC -----------------------------------------------------------
    // This is the multiplier voltage that gets passed to the AD633 voltage
    // multiplier to multiply the sine wave output.
    _Log.println(F("Initializing MCP4921 (DAC - Amplitude Control)..."));
    {
        const module::InitStatus status = initDac();
        if (status != module::MODULE_INIT_SUCCESS) {
            ESP_LOGE(TAG, "MCP4921 initialization failed: %d", static_cast<int>(status));
            _Log.printf("MCP4921 initialization failed: %d\n", static_cast<int>(status));
            return status;
        }
    }
    _Log.println(F("MCP4921 DAC initialized"));

    // -- ACS37800 -------------------------------------------------------------
    // This is the power monitor that reads the AC voltage and current coming
    // out of the amplifier.  Uses a dedicated SPI3 bus (see hardware.cpp).
    _Log.println(F("Initializing ACS37800 (VOUT - Power Monitor, SPI)..."));
    {
        const module::InitStatus status = initAcs();
        if (status != module::MODULE_INIT_SUCCESS) {
            ESP_LOGE(TAG, "ACS37800 initialization failed: %d", static_cast<int>(status));
            _Log.printf("ACS37800 initialization failed: %d\n", static_cast<int>(status));
            return status;
        }
    }
    _Log.println(F("ACS37800 initialized"));

    // -- AD9833 waveform generator --------------------------------------------
    // This is the waveform generator that generates the sine wave that is
    // passed to the AD633 voltage multiplier.
    _Log.println(F("Initializing AD9833 (DDS - Waveform Generator)..."));
    {
        const module::InitStatus status = initWaveform();
        if (status != module::MODULE_INIT_SUCCESS) {
            ESP_LOGE(TAG, "AD9833 initialization failed: %d", static_cast<int>(status));
            _Log.printf("AD9833 initialization failed: %d\n", static_cast<int>(status));
            return status;
        }
    }
    _Log.println(F("AD9833 initialized"));
    _Log.println(F("Initialization successful"));

    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initDac() {
    // MCP4921 is an SPI device — no address probing needed.  Just configure
    // the CS pin and write zero to ensure the output starts at 0 V.
    // The SPI bus is already initialised by hardware::initSPI().
    pinMode(MCP4921_CS, OUTPUT);
    digitalWrite(MCP4921_CS, HIGH);   // CS idle high

    sDacAvailable = true;
    dacCurrent_ = UINT16_MAX;         // invalidate cache to force initial write

    // Drive output to 0 V — also serves as a basic connectivity check
    // (SPI has no ACK mechanism, so we trust the write).
    setOutput(0.0f);

    ESP_LOGI(TAG, "MCP4921 SPI DAC initialised (CS=GPIO%d, 12-bit, %u full-scale)",
             MCP4921_CS, AMPLIFIER_RESOLUTION);
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initWaveform() {
    ad9833_.begin();
    // AD9833 library's begin() calls SPI.begin() with no args, which reassigns
    // the SPI peripheral to default pins (GPIO 12/11/13).  Restore our pins.
    hardware::initSPI();
    ad9833_.setMode(MD_AD9833::MODE_SINE);
    waveformMode_ = MD_AD9833::MODE_SINE;
    setFrequency(static_cast<float>(AMPLIFIER_FREQ_HZ));
    ESP_LOGI(TAG, "AD9833 generating %u Hz sine wave",
                  static_cast<unsigned>(AMPLIFIER_FREQ_HZ));
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initAcs() {
    // NOTE: The ACS37800 EN pin must be tied HIGH (or pulled high) for the chip
    // to produce valid readings.  With EN held LOW the chip outputs full-scale
    // values on all channels (~130 VAC / max current), which looks like a real
    // over-voltage reading and will immediately trigger an RmsOvervoltage fault.

    // Probe: read a known register to verify SPI communication works.
    // Reading the RMS register with no load returns all zeros, which is
    // indistinguishable from "no device present".  Instead, read a register
    // that has a known non-zero default.  Register 0x1F (shadow config)
    // has factory defaults that are never all-zero or all-ones on a real chip.
    uint32_t probe = acs_.readReg(0x1F);
    bool connected = (probe != 0x00000000 && probe != 0xFFFFFFFF);

    ESP_LOGI(TAG, "ACS37800 SPI probe: reg 0x1F = 0x%08X (%s)",
             probe, connected ? "connected" : "not found");

    if (!connected) {
        ESP_LOGW(TAG, "ACS37800 not detected on SPI — power monitor disabled");
        _Log.println(F("ACS37800 not found on SPI — power monitor disabled"));
        sAcsAvailable = false;
        return module::MODULE_INIT_SUCCESS;  // non-fatal
    }

    acs_.setBoardPololu(4);
    acs_.setSampleCount(0);

    sAcsAvailable = true;
    ESP_LOGI(TAG, "ACS37800 SPI power monitor initialised (CS=GPIO%d)", ACS37800_CS);
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initRelay() {
    ESP_LOGI(TAG, "Initialising amplifier relay (GPIO %d)", AMPLIFIER_RELAY_PIN);

    pinMode(AMPLIFIER_RELAY_PIN, OUTPUT);
    digitalWrite(AMPLIFIER_RELAY_PIN, LOW);
    sRelayOn = false;

    ESP_LOGI(TAG, "Amplifier relay initialised — relay OFF");
    return module::MODULE_INIT_SUCCESS;
}

bool checkDependencies() {
    return true;
}

// ---------------------------------------------------------------------------
// Relay control
// ---------------------------------------------------------------------------

void setRelayState(bool on) {
    setRelay(on);
}

bool getRelayState() {
    return sRelayOn;
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
    _Log.println(F("Initializing coarse cooldown"));
    rampTo(5.0f / static_cast<float>(AMPLIFIER_RESOLUTION), AMPLIFIER_RAMP_RATE_MEDIUM);
}

void initFineCooldown() {
    ESP_LOGD(TAG, "Initializing fine cooldown");
    _Log.println(F("Initializing fine cooldown"));
    rampTo(10.0f / static_cast<float>(AMPLIFIER_RESOLUTION), AMPLIFIER_RAMP_RATE_SLOW);
}

// ---------------------------------------------------------------------------
// Amplitude control
// ---------------------------------------------------------------------------

/**
 * Clamp a fraction to [0.0, 1.0] and convert to a 16-bit DAC value.
 */
static uint16_t fractionToDac(float fraction) {
    if (fraction < 0.0f) fraction = 0.0f;
    if (fraction > 1.0f) fraction = 1.0f;
    return static_cast<uint16_t>(fraction * static_cast<float>(AMPLIFIER_RESOLUTION));
}

void rampTo(float fraction, uint16_t rampRate) {
    const uint16_t dacTarget = fractionToDac(fraction);
    // Dead-band: ignore ±1 count differences to avoid chasing temperature noise.
    const int32_t diff = static_cast<int32_t>(dacTarget) - static_cast<int32_t>(dacCurrent_);
    if (diff >= -1 && diff <= 1) return;
    dacRampInternal(dacTarget, rampRate);
}

void hardStop() {
    dacCurrent_ = UINT16_MAX;   // invalidate cache so dacWrite() cannot short-circuit
    setOutput(0.0f);
}

void rampTowardShutdown() {
    if (dacCurrent_ == 0u) return;
    dacRampInternal(0u, static_cast<uint16_t>(AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL));
}

void setOutput(float fraction) {
    const uint16_t dacTarget = fractionToDac(fraction);
    const float rmsV = fraction * AMPLIFIER_MAX_VOLTAGE_VAC;
    ESP_LOGD(TAG, "setOutput(%.3f) → %.1fV RMS (DAC %u)", fraction, rmsV, dacTarget);
    _Log.printf("Setting output to %.1f%% (%.1fV RMS, DAC %u)\n",
                fraction * 100.0f, rmsV, dacTarget);
    dacWrite(dacTarget);
}

uint16_t getDacCurrent() {
    return dacCurrent_;
}

void setVoutOverride(float fraction) {
    voutOverrideActive_ = true;
    voutOverride_       = fraction;
}

void clearVoutOverride() {
    voutOverrideActive_ = false;
}

bool hasVoutOverride() {
    return voutOverrideActive_;
}

float getVoutOverride() {
    return voutOverride_;
}

// ---------------------------------------------------------------------------
// Service -- reads ACS37800; must be called every main-loop tick
// ---------------------------------------------------------------------------

module::ServiceStatus service() {
    if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS) {
        return module::MODULE_SERVICE_SKIPPED;
    }

    // -- DEBUG: dump raw ACS37800 register contents periodically -------------
    // Runs regardless of sAcsAvailable so we can see what SPI reads return
    // even when the init probe failed.  Remove once SPI is confirmed working.
    {
        static uint32_t debugCounter = 0;
        if (++debugCounter % 10 == 0) {  // log roughly every 2 s at 200 ms tick
            uint32_t reg1F = acs_.readReg(0x1F);  // shadow config (probed at init)
            uint32_t reg20 = acs_.readReg(0x20);  // RMS V/I codes
            uint32_t reg2A = acs_.readReg(0x2A);  // instantaneous V/I codes
            ESP_LOGI(TAG,
                     "ACS raw: 0x1F=0x%08X 0x20=0x%08X (vrms=%u irms=%u) 0x2A=0x%08X (v=%d i=%d) [avail=%d]",
                     reg1F, reg20,
                     (unsigned)(uint16_t)reg20,
                     (unsigned)(uint16_t)(reg20 >> 16),
                     reg2A,
                     (int)(int16_t)reg2A,
                     (int)(int16_t)(reg2A >> 16),
                     sAcsAvailable ? 1 : 0);
        }
    }

    // Skip all ACS37800 SPI traffic when the chip is absent or offline.
    if (!sAcsAvailable) {
        lastRmsVoltage_     = NAN;
        lastRmsCurrent_     = NAN;
        lastApparentPowerW_ = NAN;
        lastFrequency_      = imu::getFrequency();
        return module::MODULE_SERVICE_OK;
    }

    acs_.readRMSVoltageAndCurrent();

    // Safety net: if the read returned garbage (device gone or SPI error),
    // permanently disable the ACS37800.
    if (acs_.rmsVoltageMillivolts >= 500000) {  // >500V is impossible
        ESP_LOGW(TAG, "ACS37800 read returned garbage (%d mV) — permanently disabled",
                 acs_.rmsVoltageMillivolts);
        _Log.println(F("ACS37800 bad read — disabled"));
        sAcsAvailable = false;
        lastRmsVoltage_     = NAN;
        lastRmsCurrent_     = NAN;
        lastApparentPowerW_ = NAN;
        lastFrequency_      = NAN;
        return module::MODULE_SERVICE_ERROR;
    }

    lastRmsVoltage_     = static_cast<float>(acs_.rmsVoltageMillivolts) / 1000.0f;
    lastRmsCurrent_     = static_cast<float>(acs_.rmsCurrentMilliamps)  / 1000.0f;
    lastApparentPowerW_ = static_cast<float>(acs_.readApparentPowerMilliwatts()) / 1000.0f;
    lastFrequency_  = imu::getFrequency();

    // Frequency tracker: only advance when active and the IMU has a valid FFT
    // result. Skip (don't reset) on NAN — the timer simply doesn't accumulate
    // during data gaps, so no false warnings build up.
    if (freqTracker_ && isfinite(lastFrequency_)) {
        freqTracker_->update(frequency_, lastFrequency_);
    }

    // Voltage tracker: unconditional when active — the tracker only exists
    // while the amplifier is enabled (created in enable(), destroyed in disable()).
    if (voltTracker_) {
        voltTracker_->update(targetVoltageV_, lastRmsVoltage_);
    }

    return module::MODULE_SERVICE_OK;
}

// ---------------------------------------------------------------------------
// ACS37800 getters
// ---------------------------------------------------------------------------

float getLastRmsVoltage()       { return lastRmsVoltage_; }
float getLastRmsCurrent()       { return lastRmsCurrent_; }
float getApparentPowerWatts()   { return lastApparentPowerW_; }
float getOutputRmsVoltage()     { return lastRmsVoltage_; }
float getOutputRmsCurrent()     { return lastRmsCurrent_; }

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
