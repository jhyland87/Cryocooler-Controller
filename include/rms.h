/**
 * @file rms.h
 * @brief AC voltage and current monitoring — RMS converter + ACS712 sensor.
 *
 * Two independent measurements are housed in this module:
 *
 *   1. RMS-to-DC converter (STUBBED)
 *      read()       → samples the converter ADC output.
 *      getVoltage() → returns the latest RMS voltage in VDC.
 *      Still stubbed at 0 V until the hardware driver is implemented.
 *
 *   2. ACS712-05B AC current sensor (back-EMF / overstroke detection)
 *      readCurrent()     → samples the ACS712 and updates the EMA baseline.
 *      getCurrentA()     → returns the latest RMS current in amps.
 *      hasOverstroke()   → true if a spike was detected since the last
 *                          clearOverstroke() call.
 *      clearOverstroke() → resets the overstroke flag after the caller has
 *                          processed the event.
 *
 * Overstroke detection fires when the instantaneous AC current exceeds the
 * exponential-moving-average baseline by more than OVERSTROKE_CURRENT_THRESHOLD_A,
 * subject to a per-event debounce of OVERSTROKE_DEBOUNCE_MS.  The EMA is
 * primed for OVERSTROKE_PRIME_READINGS ticks before spike detection is armed,
 * preventing false triggers on power-on.
 */

#ifndef RMS_H
#define RMS_H

#include <stdint.h>
#include "module.h"

namespace rms {

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

/**
 * Initialise both the RMS-to-DC converter stub and the ACS712 sensor.
 * On hardware, calibrates the ACS712 zero-current offset via begin().
 * Must be called once in setup() before read() or readCurrent().
 * @return MODULE_INIT_SUCCESS always.
 */
module::InitStatus init();

// ---------------------------------------------------------------------------
// RMS voltage (STUBBED — hardware driver pending)
// ---------------------------------------------------------------------------

/** Sample and cache the latest RMS output voltage (stub: always 0 V). */
void read();

/**
 * Inject mock sensor readings directly into the module's cached state without
 * touching any hardware.  Call every control tick instead of read() +
 * readCurrent() when the sensors are not physically present.
 *
 * After this call, getVoltage(), getCurrentA(), and hasOverstroke() all return
 * the injected values until the next real read() / readCurrent() is called.
 *
 * @param voltage    RMS voltage in VDC
 * @param currentA   AC current in amps
 * @param overstroke True to assert the overstroke flag
 */
void setLastReadings(float voltage, float currentA, bool overstroke);

/** Return the most recently measured RMS voltage in VDC (stub: 0.0f). */
float getVoltage();

// ---------------------------------------------------------------------------
// ACS712 AC current and overstroke detection
// ---------------------------------------------------------------------------

/**
 * Sample the ACS712-05B and update the EMA current baseline.
 *
 * Should be called once per main-loop control tick (LOOP_INTERVAL_MS cadence).
 * On the native (test) build this is a no-op; getCurrentA() returns 0.0f.
 */
void readCurrent();

/** Return the latest AC RMS current reading from the ACS712 in amps. */
float getCurrentA();

/**
 * Return true if an overstroke (back-EMF current spike) has been detected
 * since the last clearOverstroke() call.
 *
 * The flag is edge-triggered: set at most once per OVERSTROKE_DEBOUNCE_MS
 * window regardless of how many samples exceed the threshold.
 */
bool hasOverstroke();

/**
 * Clear the overstroke flag so it can be re-armed for the next event.
 * Call this immediately after reading hasOverstroke() == true.
 */
void clearOverstroke();

// ── Module interface ──────────────────────────────────────────────────────────
//
// rms exposes two distinct reads — read() for voltage and readCurrent() for
// the ACS712 — which main.cpp calls at specific points in the control tick
// (after sensor reads, before state machine).  Collapsing both into a single
// service() call would alter their relative ordering with respect to other
// subsystems, so Module::service() is intentionally left as a no-op.
//
// Call rms::read() and rms::readCurrent() explicitly in loop().

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = rms::init(); }
    // service() — inherited no-op; read() and readCurrent() are called
    // explicitly at the correct points in the main control tick.
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace rms

#endif // RMS_H
