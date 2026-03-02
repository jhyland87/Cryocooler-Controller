/**
 * @file dac.h
 * @brief MCP4921 12-bit SPI DAC interface
 */

#ifndef DAC_H
#define DAC_H

#include <stdint.h>
#include "module.h"

namespace dac {

/**
 * Initialize the MCP4921 DAC (configure CS pin, set output to 0).
 * @return MODULE_INIT_SUCCESS always (GPIO init cannot fail).
 */
module::InitStatus init();

/**
 * Write a 12-bit value (0-4095) directly to the MCP4921.
 * Values are clamped to AMPLIFIER_RESOLUTION.
 * Skips the SPI transaction if the value has not changed.
 *
 * @param dacVal  12-bit output value
 */
void update(uint16_t dacVal);

/**
 * Rate-limited step toward a target DAC value.
 *
 * Each call moves the current output at most AMPLIFIER_MAX_STEP_PER_INTERVAL
 * counts in the direction of @p target.  This enforces a maximum slew
 * rate on the DAC output so the cooler power ramps gradually.
 *
 * The actual SPI write is only issued when the value changes.
 *
 * @param target  Desired 12-bit output value (0-4095)
 */
void rampToward(uint16_t target);

/**
 * Fast rate-limited step toward a target DAC value (used during shutdown).
 *
 * Each call moves the current output at most AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL
 * counts in the direction of @p target.  This allows rapid shutdown (few
 * seconds) without stressing the motor, while still being gradual enough
 * to prevent voltage spikes.
 *
 * The actual SPI write is only issued when the value changes.
 *
 * @param target  Desired 12-bit output value (0-4095)
 */
void rampTowardShutdown(uint16_t target);

/**
 * Return the current DAC output value (last value written to hardware).
 */
uint16_t getCurrent();

// ── Module interface ──────────────────────────────────────────────────────────
//
// dac is a pure actuator module — it has no independent periodic loop work.
// Module::service() inherits the default no-op from ModuleBase.
// Output is driven by the state machine via rampToward() / rampTowardShutdown().

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = dac::init(); }
    // service() — inherited no-op from ModuleBase; dac is state-machine driven.
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace dac

#endif // DAC_H
