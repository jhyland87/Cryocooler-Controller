/**
 * @file spi_select.h
 * @brief Chip-select logic for the SN74LVC138A decoder (U32) on the shared SPI bus.
 *
 * The eight shared-bus chip selects are outputs of a 3-to-8 decoder rather than
 * GPIOs. Each has an ID above the real GPIO numbers (see pin_config.h), which
 * src/spi_select.cpp catches in strong overrides of pinMode() and digitalWrite(),
 * so the SPI libraries work unchanged. This header holds the logic, free of
 * Arduino dependencies so the native tests can run it.
 */

#ifndef SPI_SELECT_H
#define SPI_SELECT_H

#include <stdint.h>

#include "pin_config.h"

namespace spi_select {

/** Value of the selected-output state when every decoder output is high. */
constexpr uint8_t NO_OUTPUT_SELECTED = 0xFF;

/**
 * @brief Tells whether a pin number is a decoder chip-select ID.
 * @param pin Pin number passed to pinMode() or digitalWrite().
 * @return True for an ID from CS_ID_BASE to CS_ID_BASE + 7.
 */
constexpr bool isChipSelectId(uint8_t pin) {
    return pin >= CS_ID_BASE && pin < CS_ID_BASE + CS_OUTPUT_COUNT;
}

/**
 * @brief Applies a chip-select write to the decoder.
 *
 * LOW sets the address with the decoder disabled, then enables it, so no other
 * output glitches low. HIGH disables the decoder only if this output is the one
 * selected, so initialising one driver can't deselect another's device.
 *
 * @param chipSelectId   Chip-select ID, for which isChipSelectId() is true.
 * @param level          Requested line level (0 selects).
 * @param selectedOutput Decoder output now selected; updated by this call.
 * @param writePin       Callable taking (uint8_t gpio, uint8_t level).
 *
 * @code
 * uint8_t selected = NO_OUTPUT_SELECTED;
 * applyChipSelect(ADS1220_CS, 0, selected, writeGpio);  // enable high, A=0 B=1 C=1, enable low
 * applyChipSelect(ADS1220_CS, 1, selected, writeGpio);  // enable high
 * @endcode
 */
template <typename PinWriter>
inline void applyChipSelect(uint8_t chipSelectId, uint8_t level, uint8_t& selectedOutput,
                            PinWriter writePin) {
    const uint8_t output = chipSelectId - CS_ID_BASE;
    if (level != 0) {
        if (output == selectedOutput) {
            writePin(CS_ENABLE_PIN, 1);
            selectedOutput = NO_OUTPUT_SELECTED;
        }
        return;
    }
    writePin(CS_ENABLE_PIN, 1);
    writePin(CS_ADDR_A_PIN, output & 1);
    writePin(CS_ADDR_B_PIN, (output >> 1) & 1);
    writePin(CS_ADDR_C_PIN, (output >> 2) & 1);
    writePin(CS_ENABLE_PIN, 0);
    selectedOutput = output;
}

}  // namespace spi_select

#endif  // SPI_SELECT_H
