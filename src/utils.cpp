/**
 * @file utils.cpp
 * @brief Miscellaneous hardware utility functions.
 */

#include "utils.h"

#ifdef ARDUINO
#include <Wire.h>
#include "hardware.h"

namespace utils {

void i2cScan(Print& out) {
    out.println("Scanning I2C bus (0x01-0x7E)...");

    uint8_t found = 0;
    TwoWire& wire = hardware::i2c();

    for (uint8_t addr = 0x01u; addr <= 0x7Eu; ++addr) {
        wire.beginTransmission(addr);
        if (wire.endTransmission() == 0) {
            out.printf("  0x%02X\n", addr);
            ++found;
        }
    }

    if (found == 0) {
        out.println("No devices found.");
    } else {
        out.printf("%u device(s) found.\n", static_cast<unsigned>(found));
    }
}

} // namespace utils

#endif // ARDUINO
