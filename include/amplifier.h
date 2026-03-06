/**
 * @file amplifier.h
 * @brief Amplifier interface
 *
 * Owns the full amplifier signal chain:
 *   AD9833 waveform generator  →  amplifier board  →  ACS37800 power monitor
 *   MCP4921 DAC                                       (amplitude control)
 *
 * The legacy dac / waveform / rms modules have been consolidated here.
 */

#ifndef AMPLIFIER_H
#define AMPLIFIER_H

#include <stdint.h>
#include "module.h"
#include "tracking.h"

namespace amplifier {

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

/**
 * Initialise all amplifier sub-systems (DAC, AD9833 waveform generator,
 * ACS37800 power monitor).
 * @return MODULE_INIT_SUCCESS on success, MODULE_INIT_HARDWARE_ERROR otherwise.
 */
module::InitStatus init();

/** Initialise the AD9833 waveform generator and start the sine wave. */
module::InitStatus initWaveform();

/** Initialise the ACS37800 RMS power monitor over I2C. */
module::InitStatus initAcs();

/** Initialise the MCP4921 12-bit SPI DAC (CS pin + zero output). */
module::InitStatus initDac();

/** Read latest ACS37800 values; update lastRmsVoltage / lastRmsCurrent. */
module::ServiceStatus service();

/**
 * Return true if all hardware dependencies were detected at init time.
 * Currently always returns true (caller may override with mock).
 */
bool checkDependencies();

// ---------------------------------------------------------------------------
// Enable / disable waveform output
// ---------------------------------------------------------------------------

/** True when the AD9833 is producing a sine wave. */
bool isEnabled();

/** Start the AD9833 sine wave output. */
void enable();

/** Stop the AD9833 output (MODE_OFF). */
void disable();

// ---------------------------------------------------------------------------
// Waveform frequency
// ---------------------------------------------------------------------------

/**
 * Set the AD9833 output frequency.
 * @param frequencyHz  Desired frequency in Hz.
 */
void setFrequency(float frequencyHz);

/**
 * Return the currently programmed output frequency in Hz.
 * (This is the set-point, not a measured value.)
 */
float getFrequency();

// ---------------------------------------------------------------------------
// DAC / amplitude control
// ---------------------------------------------------------------------------

/**
 * Rate-limited ramp of the MCP4921 DAC toward @p dacTarget.
 * Each call advances at most AMPLIFIER_MAX_STEP_PER_INTERVAL counts.
 *
 * @param dacTarget  Desired 12-bit DAC value (0–4095).
 */
void rampToVoltage(uint16_t dacTarget, uint16_t rampRate = AMPLIFIER_RAMP_RATE_SLOW);

/**
 * Fast rate-limited ramp toward @p dacTarget (used during Shutdown).
 * Each call advances at most AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL counts.
 *
 * @param dacTarget  Desired 12-bit DAC value (0–4095).
 */
void rampTowardShutdown(uint16_t dacTarget);

/**
 * Immediately write 0 to the DAC hardware, bypassing the rate limiter and
 * the cached-value guard.  Call from any hard power-off or emergency-stop
 * path to guarantee the MCP4921 output is zeroed regardless of the current
 * cached DAC value.
 */
void hardStop();

void initCoarseCooldown();

void initFineCooldown();

/**
 * Write @p dacTarget directly to the DAC with no rate limiting.
 * @param dacTarget  12-bit DAC value (0–4095).
 */
void setRmsVoltage(uint16_t dacTarget);

/** Return the current MCP4921 DAC output value (0–4095). */
uint16_t getDacCurrent();

// ---------------------------------------------------------------------------
// ACS37800 power monitor readings
// ---------------------------------------------------------------------------

/**
 * Most recently measured RMS output voltage in Volts.
 * Returns 0.0f before the first successful service() call.
 */
float getLastRmsVoltage();

/**
 * Most recently measured RMS output current in Amps.
 * Returns 0.0f before the first successful service() call.
 */
float getLastRmsCurrent();

/** Alias for getLastRmsVoltage(). */
float getOutputRmsVoltage();

/** Alias for getLastRmsCurrent(). */
float getOutputRmsCurrent();

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

/**
 * Set the expected RMS output voltage (V) for tracking purposes.
 * Should be called by the state machine whenever the DAC target changes.
 * Resets the voltage tracking timer when the target changes by more than
 * the hysteresis band.
 *
 * @param volts  Expected RMS output voltage in Volts.
 */
void setTargetVoltage(float volts);

/**
 * Tracking score for the output frequency.
 * Compares the IMU-measured frequency against the AD9833 set-point.
 * 1.0 = measured frequency exactly matches the programmed set-point.
 * 0.0 = error >= AMPLIFIER_FREQ_TRACK_FULL_SCALE_HZ.
 * Returns 1.0 when no valid IMU frequency is available yet (NAN).
 */
float getFrequencyScore();

/** Current state of the frequency tracking monitor. */
TrackingMonitor<float>::State getFrequencyTrackingState();

/**
 * Tracking score for the RMS output voltage.
 * 1.0 = measured voltage exactly matches the target set by setTargetVoltage().
 * 0.0 = error >= AMPLIFIER_VOLT_TRACK_FULL_SCALE_V.
 * Only meaningful while the amplifier is enabled.
 */
float getVoltageScore();

/** Current state of the voltage tracking monitor. */
TrackingMonitor<float>::State getVoltageTrackingState();

// ---------------------------------------------------------------------------
// Output validation
// ---------------------------------------------------------------------------

/**
 * Verify that the linear motor is running at the programmed frequency by
 * reading the most recent IMU FFT result from imu::getFrequency() and
 * comparing it against the AD9833 set-point returned by getFrequency().
 *
 * The IMU updates its frequency estimate automatically via imu::service()
 * every FFT_INTERVAL_MS.  Call imu::calculateFrequency() beforehand if an
 * immediate (blocking) measurement is needed.
 *
 * @param toleranceHz  Acceptance band around the programmed frequency.
 * @return true when the measured frequency is within @p toleranceHz of the
 *         set-point.  Returns false if no valid IMU frequency is available
 *         yet (NAN).
 */
bool verifyFrequency(float toleranceHz = 0.5f);

/**
 * Return true when the most recently measured voltage and frequency are
 * within @p tolerance of their respective set-points.
 * Always returns true until a full implementation is in place.
 */
bool checkOutput(float tolerance = 0.15f);


// ---------------------------------------------------------------------------
// Module interface (CRTP)
// ---------------------------------------------------------------------------

#ifdef ARDUINO
struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = amplifier::init(); }
    static module::ServiceStatus service() { return _serviceStatus = amplifier::service(); }
};

ASSERT_MODULE_INTERFACE(Module);
#endif // ARDUINO

} // namespace amplifier

#endif // AMPLIFIER_H
