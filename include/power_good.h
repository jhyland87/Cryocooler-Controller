/**
 * @file power_good.h
 * @brief Power-good helpers: rail flag decoding and the power-off gate.
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
 * The +-15 V power-good flags the MCP23S08 GPIO expander reads (LT3097 PGP and
 * PGN). Each node is high (true) when its rail is good.
 */
struct RailFlags {
    bool posLdo;     ///< LT3097 +15 V output (PGP)
    bool negLdo;     ///< LT3097 -15 V output (PGN)

    /** True when every rail reports good. */
    bool allGood() const { return posLdo && negLdo; }
};

/**
 * Decode the GPIO expander port byte into rail flags.
 * @param ioState  Bit n = level of expander pin n.
 * @param bitPosLdo, bitNegLdo  Expander pin numbers of the two flags
 *                 (EXPANDER_PIN_* in pin_config.h).
 * @return The decoded flags.
 * @code
 * RailFlags flags = decodeRailFlags(0b00011, 0, 1);  // all good
 * @endcode
 */
inline RailFlags decodeRailFlags(uint8_t ioState, uint8_t bitPosLdo, uint8_t bitNegLdo) {
    // Not named "bit": Arduino.h defines a bit(b) macro that would replace the call.
    auto pinIsHigh = [ioState](uint8_t pin) { return ((ioState >> pin) & 1u) != 0; };
    return RailFlags{pinIsHigh(bitPosLdo), pinIsHigh(bitNegLdo)};
}

/**
 * Decide when a button power-off may release the supply: once the amplitude is
 * at zero, or when the timeout expires so a stuck ramp cannot block power-off.
 * @param dacCounts Current DAC code.
 * @param elapsedMs Time since the button asked for power-off.
 * @param timeoutMs Longest wait.  Keep it under the LTC2954 6.4 s forced-off time.
 * @return true when KILL# should be driven low.
 * @code
 * powerOffReady(0, 100, 5000);    // true: amplitude is at zero
 * powerOffReady(832, 100, 5000);  // false: still ramping
 * @endcode
 */
inline bool powerOffReady(uint16_t dacCounts, uint32_t elapsedMs, uint32_t timeoutMs) {
    return dacCounts == 0 || elapsedMs >= timeoutMs;
}
