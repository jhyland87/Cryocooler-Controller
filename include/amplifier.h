/**
 * @file amplifier.h
 * @brief Amplifier interface
 *
 * Manages the amplifier connected to the cold head.
 */

 #ifndef AMPLIFIER_H
 #define AMPLIFIER_H

 #include <stdint.h>
 #include "module.h"

 namespace amplifier {

/**
  * Initialize the amplifier.
  * @return MODULE_INIT_SUCCESS if init() succeeds, MODULE_INIT_HARDWARE_ERROR otherwise.
  */
module::InitStatus init();


module::InitStatus initDac();

/**
 * Check if the amplifier is enabled.
 * @return true if the amplifier is enabled, false otherwise.
 */
bool isEnabled();

/**
 * Enable the amplifier. (using the enable switch on the amplifier)
 */
void enable();

/**
 * Disable the amplifier. (using the enable switch on the amplifier)
 */
void disable();

 /**
  * Return the most recently measured RMS voltage in Volts.
  * Returns 0.0f before the first successful read.
  */
float getLastRmsVoltageV();

/**
 * Set the frequency in Hz.
 * @param frequencyHz The frequency in Hz.
 */
void setFrequency(float frequencyHz);

/**
 * Set the frequency in Hz.
 * @param frequencyHz The frequency in Hz.
 */
float getFrequency();

/**
 * Verify the frequency is within the tolerance.
 * @param frequencyHz The target frequency in Hz.
 * @param toleranceHz The tolerance in Hz.
 * @return true if the frequency is within the tolerance, false otherwise.
 */
bool verifyFrequency(float frequencyHz, float toleranceHz = 0.15f);


 /**
  * Return the most recently measured RMS current in Amps.
  * Returns 0.0f before the first successful read.
  */
float getLastRmsCurrentA();

/**
 * Set the RMS voltage in Volts.
 * @param rmsVoltageV The RMS voltage in Volts.
 */
void setRmsVoltageV(float rmsVoltageV);

/**
 * Check if the amplifier has all the dependencies it needs.
 * - IMU
 * - DAC
 * @return true if the amplifier has all the dependencies it needs, false otherwise.
 */
bool checkDependencies();

/**
 * Ramp the voltage toward the target voltage.
 * @param targetVoltageV The target voltage in Volts.
 */
void rampToVoltageV(float targetVoltageV);

/**
 * Ramp the voltage toward shutdown.
 * @param targetVoltageV The target voltage in Volts.
 */
void rampTowardShutdown(float targetVoltageV);

/**
 * Get the current voltage in Volts.
 * @return The current voltage in Volts.
 */
float getCurrentVoltageV();

 // ── Module interface ──────────────────────────────────────────────────────────
 //
 // read() accepts a nowMs argument so cooling-rate history is correctly
 // timestamped and remains directly testable on native builds with injected
 // time values.
 //
 // Module::service() samples millis() internally, which is correct for the
 // Arduino loop() context.  Guarded by #ifdef ARDUINO because millis() is not
 // available in native (host) unit-test builds — those call read(nowMs) directly.

 #ifdef ARDUINO
 struct Module : ModuleBase<Module> {
     static module::InitStatus init() { return _initStatus = amplifier::init(); }
     /** Calls amplifier::read(millis()) — must be called every loop tick. */
     static module::ServiceStatus service() { return _serviceStatus = module::MODULE_SERVICE_OK; }
 };

 ASSERT_MODULE_INTERFACE(Module);
 #endif // ARDUINO

 } // namespace amplifier

 #endif // AMPLIFIER_H
