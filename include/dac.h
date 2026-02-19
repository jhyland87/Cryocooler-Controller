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
 * Write a 12-bit value (0–4095) to the MCP4921.
 * Values are clamped to MCP4921_MAX_VALUE.
 * Skips the SPI transaction if the value hasn't changed.
 *
 * @param dacVal  12-bit output value
 */
void update(uint16_t dacVal);
} // namespace dac

#endif // DAC_H
