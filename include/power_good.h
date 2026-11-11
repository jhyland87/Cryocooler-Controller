/**
 * @file power_good.h
 * @brief Power-good helpers: debounced monitor alias and rail flag decoding.
 *
 * The debounced change detector lives in state_change_monitor.h;
 * PowerGoodMonitor is kept as its name for the power-good inputs.
 */

#pragma once

#include <stdint.h>
#include "state_change_monitor.h"

/** Debounced power-good change detector (see StateChangeMonitor). */
using PowerGoodMonitor = StateChangeMonitor;

/**
 * The four +-15 V power-good flags the MCP23S08 GPIO expander reads (LT3097 PGP /
 * PGN and LT8582 PG1 / PG2). Each node is high (true) when its rail is good.
 */
struct RailFlags {
    bool posLdo;     ///< LT3097 +15 V output (PGP)
    bool negLdo;     ///< LT3097 -15 V output (PGN)
    bool posBoost;   ///< LT8582 +16.4 V boost (PG1)
    bool negInvert;  ///< LT8582 -16.5 V inverter (PG2)

    /** True when every rail reports good. */
    bool allGood() const { return posLdo && negLdo && posBoost && negInvert; }
};

/**
 * Decode the GPIO expander port byte into rail flags.
 * @param ioState  Bit n = level of expander pin n.
 * @param bitPosLdo, bitNegLdo, bitPosBoost, bitNegInvert  GPIO numbers of
 *                 the four flags (EXPANDER_PIN_* in pin_config.h).
 * @return The decoded flags.
 * @code
 * RailFlags flags = decodeRailFlags(0b01111, 0, 1, 2, 3);  // all good
 * @endcode
 */
inline RailFlags decodeRailFlags(uint8_t ioState, uint8_t bitPosLdo, uint8_t bitNegLdo,
                                 uint8_t bitPosBoost, uint8_t bitNegInvert) {
    // Not named "bit": Arduino.h defines a bit(b) macro that would replace the call.
    auto pinIsHigh = [ioState](uint8_t pin) { return ((ioState >> pin) & 1u) != 0; };
    return RailFlags{pinIsHigh(bitPosLdo), pinIsHigh(bitNegLdo), pinIsHigh(bitPosBoost),
                     pinIsHigh(bitNegInvert)};
}
