/**
 * @file hardware.cpp
 * @brief Shared hardware bus registry implementation.
 *
 * Wraps the global Wire and SPI singletons behind the hardware:: API.
 * See hardware.h for rationale and usage.
 */

#include "hardware.h"
#include "pin_config.h"
#include "esp32-hal-i2c.h"          // i2cIsInit(), i2cBusHandle()
#include "driver/i2c_master.h"      // i2c_master_probe(), i2c_master_bus_handle_t

namespace hardware {

    // -------------------------------------------------------------------------
    // I2C bus scan
    // -------------------------------------------------------------------------

    /**
     * Probe every 7-bit I2C address and log any that respond.
     * Uses i2c_master_probe() directly on the HAL bus handle so it bypasses
     * the Wire layer entirely — useful for confirming bus health independent
     * of any library issues.
     *
     * @param timeoutMs  Per-address probe timeout in milliseconds.
     * @return           Number of devices that responded.
     */
    uint8_t scanI2c(uint32_t timeoutMs) {
        auto busHandle = static_cast<i2c_master_bus_handle_t>(i2cBusHandle(0));
        if (!busHandle) {
            log_e("[hardware] i2cBusHandle returned null — bus not initialised");
            return 0;
        }

        uint8_t found = 0;
        log_i("[hardware] I2C bus scan (SDA=%d SCL=%d):", SDA_PIN, SCL_PIN);
        for (uint8_t addr = 1; addr < 127; ++addr) {
            if (i2c_master_probe(busHandle, addr, static_cast<int>(timeoutMs)) == ESP_OK) {
                log_i("[hardware]   0x%02X  ✓", addr);
                ++found;
            }
        }
        if (found == 0) {
            log_w("[hardware]   No devices found — check wiring and pull-ups");
        } else {
            log_i("[hardware]   %u device(s) found", found);
        }
        return found;
    }

    // -------------------------------------------------------------------------
    // init
    // -------------------------------------------------------------------------

    module::InitStatus init() {
        // Initialise the global Wire instance once with the correct pins.
        // No sensor library should call Wire.begin() again after this — any
        // that did (e.g. QMI8658) have been patched in lib/ to skip that call.
        Wire.begin(SDA_PIN, SCL_PIN);

        // Verify at the HAL level that the ESP-IDF I2C master driver actually
        // came up — Wire.begin() doesn't always surface errors to the caller.
        if (!i2cIsInit(0)) {
            log_e("[hardware] Wire.begin() returned but i2cIsInit(0) is false — I2C driver failed to start");
            return module::InitStatus::MODULE_INIT_HARDWARE_ERROR;
        }

        log_d("[hardware] I2C bus 0 initialised (SDA=%d SCL=%d, handle=%p)",
              SDA_PIN, SCL_PIN, i2cBusHandle(0));

        // SPI — CS is managed per-device; -1 means no default CS pin.
        SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    TwoWire&  i2c() { return Wire; }
    SPIClass& spi() { return SPI;  }

} // namespace hardware
