/**
 * @file compressor.h
 * @brief Air compressor relay control.
 *
 * The compressor is driven through a SparkFun Qwiic Single Relay at I2C
 * address COMPRESSOR_RELAY_ADDR (pin_config.h).  It may only be started via
 * a timed run — there is no indefinite-on mode — and the run duration is
 * hard-capped by COMPRESSOR_MAX_RUN_MS (config.h).
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
#include "config.h"
#include "module.h"
#include "tick.h"

namespace compressor {

/**
 * Initialise the SparkFun Qwiic Single Relay and de-energise it.
 * Must be called once before any other function in this namespace.
 * @return MODULE_INIT_SUCCESS on success, MODULE_INIT_HARDWARE_ERROR if the
 *         relay does not acknowledge on the I2C bus.
 */
module::InitStatus init();

/**
 * Start a timed compressor run.
 *
 * Turns the relay ON immediately and schedules it to turn OFF after
 * @p durationMs milliseconds.  If a run is already active it is restarted
 * with the new duration.  The duration is clamped to COMPRESSOR_MAX_RUN_MS.
 *
 * @param durationMs How long to run the compressor (milliseconds).
 */
void startRun(uint32_t durationMs);

/**
 * Stop an active compressor run early and turn the relay OFF immediately.
 * Has no effect if the compressor is already off.
 */
void stopRun();

/**
 * Advance the compressor timer.  Must be called every loop tick.
 * Turns the relay OFF and resets run state when the scheduled duration
 * has elapsed.  Reads tick::nowMs() internally.
 */
void service();

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------

/** Returns true while the relay is physically energised. */
bool getStatus();

/**
 * Directly energise or de-energise the relay, bypassing the timed-run logic.
 * Intended for diagnostic / mock-command use; prefer startRun() / stopRun()
 * in production code.
 * @param on  true = relay ON, false = relay OFF.
 */
void setRelayState(bool on);

/** Returns true while a timed run is active (relay is ON and timer running). */
bool isTimedRunActive();

/**
 * Milliseconds elapsed since the current timed run started.
 * Returns 0 if no timed run is active.
 */
uint32_t getElapsedMs();

/**
 * Milliseconds remaining in the current timed run.
 * Returns 0 if no timed run is active or the timer has already expired.
 */
uint32_t getRemainingMs();

// ---------------------------------------------------------------------------
// Module interface
// ---------------------------------------------------------------------------

#ifdef ARDUINO
struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = compressor::init(); }
    static module::ServiceStatus service() {
        compressor::service();
        return _serviceStatus = module::MODULE_SERVICE_OK;
    }
    static constexpr float minSystemVoltage() { return MIN_MODULE_VOLTAGE_VDC; }
};

ASSERT_MODULE_INTERFACE(Module);
#endif  // ARDUINO

}  // namespace compressor

#endif  // COMPRESSOR_H
