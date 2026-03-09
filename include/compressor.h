/**
 * @file compressor.h
 * @brief Air compressor relay control.
 *
 * The compressor is driven through a single output pin on a PCAL9535A I2C
 * GPIO expander (address / pin configured in pin_config.h).  It may only be
 * started via a timed run — there is no indefinite-on mode — and the run
 * duration is hard-capped by COMPRESSOR_MAX_RUN_MS (config.h).
 *
 * Typical flow:
 *   compressor::startRun(millis(), durationMs);   // turns relay ON
 *   // ... call compressor::service(millis()) every loop tick ...
 *   // relay turns OFF automatically when the timer expires, or call:
 *   compressor::stopRun(millis());
 */

#ifndef COMPRESSOR_H
#define COMPRESSOR_H

#include <stdint.h>
#ifdef ARDUINO
#include <Arduino.h>
#endif
#include "module.h"

namespace compressor {

/**
 * Initialise the PCAL9535A GPIO expander and drive the relay pin LOW (off).
 * Must be called once before any other function in this namespace.
 * @return MODULE_INIT_SUCCESS on success, MODULE_INIT_HARDWARE_ERROR if the
 *         expander does not acknowledge on the I2C bus.
 */
module::InitStatus init();

/**
 * Start a timed compressor run.
 *
 * Turns the relay ON immediately and schedules it to turn OFF after
 * @p durationMs milliseconds.  If a run is already active it is restarted
 * with the new duration.  The duration is clamped to COMPRESSOR_MAX_RUN_MS.
 *
 * @param nowMs      Current millis() value (injected for testability).
 * @param durationMs How long to run the compressor (milliseconds).
 */
void startRun(uint32_t nowMs, uint32_t durationMs);

/**
 * Stop an active compressor run early and turn the relay OFF immediately.
 * Has no effect if the compressor is already off.
 *
 * @param nowMs  Current millis() value (injected for testability).
 */
void stopRun(uint32_t nowMs);

/**
 * Advance the compressor timer.  Must be called every loop tick.
 * Turns the relay OFF and resets run state when the scheduled duration
 * has elapsed.
 *
 * @param nowMs  Current millis() value (injected for testability).
 */
void service(uint32_t nowMs);

/// Convenience overload — calls service(millis()).  Arduino loop() use only.
inline void service() { service(millis()); }

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------

/** Returns true while the relay is physically energised. */
bool getStatus();

/** Returns true while a timed run is active (relay is ON and timer running). */
bool isTimedRunActive();

/**
 * Milliseconds elapsed since the current timed run started.
 * Returns 0 if no timed run is active.
 * @param nowMs  Current millis() value.
 */
uint32_t getElapsedMs(uint32_t nowMs);

/**
 * Milliseconds remaining in the current timed run.
 * Returns 0 if no timed run is active or the timer has already expired.
 * @param nowMs  Current millis() value.
 */
uint32_t getRemainingMs(uint32_t nowMs);

// ---------------------------------------------------------------------------
// Module interface
// ---------------------------------------------------------------------------

#ifdef ARDUINO
struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = compressor::init(); }
    static module::ServiceStatus service() {
        compressor::service(millis());
        return _serviceStatus = module::MODULE_SERVICE_OK;
    }
};

ASSERT_MODULE_INTERFACE(Module);
#endif  // ARDUINO

}  // namespace compressor

#endif  // COMPRESSOR_H
