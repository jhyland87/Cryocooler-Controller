/**
 * @file relay_board.h
 * @brief Shared PCAL9535A driver for the dual-relay board.
 *
 * Both compressor (pin 0) and amplifier (pin 1) relays live on the same
 * PCAL9535A at COMPRESSOR_RELAY_PCAL_ADDR (0x20).  A single driver instance
 * is required because the library's begin() resets all pin-direction registers
 * to inputs — calling it from two separate instances would clobber each
 * other's pinMode() configuration.
 *
 * init() is idempotent: calling it more than once is safe and has no effect
 * after the first successful initialisation.  Modules that need the relay
 * board (compressor, amplifier) each call relay_board::init() at their own
 * init time; whichever runs first actually programmes the hardware.
 */

#ifndef RELAY_BOARD_H
#define RELAY_BOARD_H

#include <stdint.h>
#include "module.h"

namespace relay_board {

/**
 * Initialise the PCAL9535A: call begin() once, set both relay pins as outputs,
 * and drive both LOW.  Safe to call multiple times — only the first call has
 * any effect.
 *
 * @return MODULE_INIT_SUCCESS always (no way to detect PCAL9535A absence via
 *         the current library without a separate endTransmission() probe).
 */
module::InitStatus init();

/**
 * Energise or de-energise a relay pin.
 * @param pin  Physical pin number on the PCAL9535A (0 = compressor, 1 = amplifier).
 * @param on   true = HIGH (energised), false = LOW (de-energised).
 */
void setPin(uint8_t pin, bool on);

/**
 * Return the cached state of a relay pin (does not read hardware).
 * @param pin  Physical pin number on the PCAL9535A.
 */
bool getPin(uint8_t pin);

} // namespace relay_board

#endif // RELAY_BOARD_H
