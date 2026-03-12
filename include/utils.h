/**
 * @file utils.h
 * @brief Miscellaneous hardware utility functions.
 *
 * Functions here are standalone diagnostics — no init() or service() call
 * required.  They are driven on-demand (e.g. from serial commands).
 */

#pragma once

#ifdef ARDUINO
#include <Print.h>

namespace utils {

/**
 * Probe every valid 7-bit I2C address (0x01–0x7E) and print the ones that
 * respond with an ACK.  The I2C bus must already be initialised via
 * hardware::init() before calling this.
 */
void i2cScan(Print& out);

} // namespace utils

#endif // ARDUINO
