/**
 * @file utils.cpp
 * @brief Miscellaneous hardware utility functions.
 */

#include "utils.h"

#ifdef ARDUINO
#include <Wire.h>
#include "hardware.h"
#include "config.h"

namespace utils {

void i2cScan(Print& out) {
    TwoWire& wire = hardware::i2c();

    // ── Recover the bus before scanning ────────────────────────────────────
    // If cooling::service() left the bus mid-transaction, or a previous
    // timeout stuck SDA low, reset the driver so every probe starts clean.
    hardware::recoverI2c();
    delay(5);

#if USE_I2C_MUX
    // ── Ensure all mux channels are deselected before main bus scan ────────
    // A previous failed init may have left a channel selected, which would
    // make downstream devices appear as if they were on the main bus.
    wire.beginTransmission(PCA9548_I2C_ADDRESS);
    wire.write(static_cast<uint8_t>(0x00));
    wire.endTransmission();  // ignore errors — mux may not be present
    delay(1);
#endif

    // ── Main bus scan ───────────────────────────────────────────────────────
    out.println("Scanning main I2C bus (0x08-0x77)...");

    uint8_t found = 0;
    for (uint8_t addr = 0x08u; addr <= 0x77u; ++addr) {
        wire.beginTransmission(addr);
        if (wire.endTransmission() == 0) {
            out.printf("  0x%02X\n", addr);
            ++found;
        }
    }

    if (found == 0) {
        out.println("  No devices found.");
    } else {
        out.printf("  %u device(s) found.\n", static_cast<unsigned>(found));
    }

#if USE_I2C_MUX
    // ── PCA9548 mux channel scan ────────────────────────────────────────────
    // If the PCA9548 is present, select each active channel in turn and
    // report which downstream addresses respond.  Restores all channels
    // deselected when done.
    wire.beginTransmission(PCA9548_I2C_ADDRESS);
    if (wire.endTransmission() != 0) {
        out.printf("PCA9548 not found at 0x%02X — skipping mux scan.\n",
                   PCA9548_I2C_ADDRESS);
        return;
    }

    out.printf("\nScanning PCA9548 mux channels (0x%02X)...\n", PCA9548_I2C_ADDRESS);

    for (uint8_t ch = 0u; ch < 8u; ++ch) {
        // Select this channel
        wire.beginTransmission(PCA9548_I2C_ADDRESS);
        wire.write(static_cast<uint8_t>(1u << ch));
        wire.endTransmission();
        delay(5);

        // Scan downstream addresses
        uint8_t chFound = 0;
        out.printf("  CH%u:", ch);
        for (uint8_t addr = 0x08u; addr <= 0x77u; ++addr) {
            if (addr == PCA9548_I2C_ADDRESS) continue;  // skip the mux itself
            wire.beginTransmission(addr);
            if (wire.endTransmission() == 0) {
                out.printf(" 0x%02X", addr);
                ++chFound;
            }
        }
        if (chFound == 0) {
            out.printf(" (none)");
        }
        out.println();
    }

    // Deselect all channels
    wire.beginTransmission(PCA9548_I2C_ADDRESS);
    wire.write(static_cast<uint8_t>(0x00));
    wire.endTransmission();

    out.println("Mux scan complete.");
#endif
}

} // namespace utils

#endif // ARDUINO
