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

} // namespace acs37800
