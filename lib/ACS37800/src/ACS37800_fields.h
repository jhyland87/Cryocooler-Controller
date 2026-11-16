/**
 * @file ACS37800_fields.h
 * @brief Pure decoders for ACS37800 register bit fields (no Arduino dependency).
 */

#pragma once

#include <stdint.h>

namespace acs37800 {

/**
 * Decodes PFACTOR from a register 0x22 word.
 *
 * ACS37800 datasheet, Register 0x22 / Table 23: bits 26:16, signed 11-bit
 * fixed point with 10 fractional bits.
 *
 * @param apparentPowerReg Raw 32-bit contents of register 0x22.
 * @return Power factor, -1.0 to just under 1.0.
 */
inline float decodePowerFactor(uint32_t apparentPowerReg)
{
  int32_t code = static_cast<int32_t>((apparentPowerReg >> 16) & 0x7FF);
  if (code & 0x400) { code -= 0x800; }
  return static_cast<float>(code) / 1024.0f;
}

/**
 * Decodes POSANGLE from a register 0x22 word.
 *
 * ACS37800 datasheet, Register 0x22: bit 27, 0 = current leading the voltage,
 * 1 = current lagging.  Taken from zero-crossing timing, so it is only
 * meaningful for a linear load.
 *
 * @param apparentPowerReg Raw 32-bit contents of register 0x22.
 * @return true when the current lags the voltage (inductive load).
 */
inline bool decodeCurrentLagging(uint32_t apparentPowerReg)
{
  return (apparentPowerReg & (1UL << 27)) != 0;
}

/**
 * Tells whether a register 0x20 word is what an unpowered chip returns.
 *
 * With the isolated supply off the isolator's MISO output idles high, so every
 * read is 0xFFFFFFFF.  A live chip cannot report full-scale VRMS and IRMS at
 * the same time.
 *
 * @param rmsReg Raw 32-bit contents of register 0x20.
 * @return true when the word is all ones.
 */
inline bool isBusIdleWord(uint32_t rmsReg)
{
  return rmsReg == 0xFFFFFFFFUL;
}

} // namespace acs37800
