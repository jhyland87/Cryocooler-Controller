/**
 * @file utils.cpp
 * @brief Miscellaneous hardware utility functions.
 */

#include "utils.h"

#ifdef ARDUINO
#include "hardware.h"
#include "i2c_bridge.h"

namespace utils {

void i2cScan(Print& out) {
    EMC230xBus& bus = hardware::i2c();

    if (!i2c_bridge::isPresent()) {
        out.println(F("SC18IS604 I2C bridge not found — nothing to scan."));
        return;
    }

    // Reset the bridge first so a stuck transaction does not hide devices.
    hardware::recoverI2c();
    delay(5);

    // Each probe is a one-byte read through the bridge.
    out.println(F("Scanning I2C bus behind the SC18IS604 (0x08-0x77)..."));

    uint8_t found = 0;
    for (uint8_t addr = 0x08u; addr <= 0x77u; ++addr) {
        if (bus.probe(addr)) {
            out.printf("  0x%02X\n", addr);
            ++found;
        }
    }

    if (found == 0) {
        out.println(F("  No devices found."));
    } else {
        out.printf("  %u device(s) found.\n", static_cast<unsigned>(found));
    }
}

} // namespace utils

#endif // ARDUINO
