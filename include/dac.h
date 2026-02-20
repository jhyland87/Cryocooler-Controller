/**
 * @file dac.h
 * @brief MCP4921 12-bit SPI DAC interface
 */

#ifndef DAC_H
#define DAC_H

#include <stdint.h>

namespace dac {

/**
 * Initialize the MCP4921 DAC (configure CS pin, set output to 0).
 */
void init();

/**
 * Write a 12-bit value (0-4095) directly to the MCP4921.
 * Values are clamped to MCP4921_MAX_VALUE.
 * Skips the SPI transaction if the value has not changed.
 *
 * @param dacVal  12-bit output value
 */
void update(uint16_t dacVal);

/**
 * Rate-limited step toward a target DAC value.
 *
 * Each call moves the current output at most DAC_MAX_STEP_PER_INTERVAL
 * counts in the direction of @p target.  This enforces a maximum slew
 * rate on the DAC output so the cooler power ramps gradually.
 *
 * The actual SPI write is only issued when the value changes.
 *
 * @param target  Desired 12-bit output value (0-4095)
 */
void rampToward(uint16_t target);

/**
 * Return the current DAC output value (last value written to hardware).
 */
uint16_t getCurrent();

} // namespace dac

#endif // DAC_H
