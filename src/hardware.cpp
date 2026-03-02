/**
 * @file hardware.cpp
 * @brief Shared hardware bus registry implementation.
 *
 * Wraps the global Wire and SPI singletons behind the hardware:: API.
 * See hardware.h for rationale and usage.
 */

#include "hardware.h"
#include "pin_config.h"
#include "esp32-hal-i2c.h"      // i2cIsInit(), i2cBusHandle() (Core 3.x / IDF 5.x)
#if ESP_ARDUINO_VERSION_MAJOR >= 3
#include "driver/i2c_master.h"  // i2c_master_bus_reset() — IDF 5.x only
#endif

namespace hardware {
    // -------------------------------------------------------------------------
    // I2C bus scan
    // -------------------------------------------------------------------------

    /**
     * Probe every 7-bit I2C address and log any that respond.
     *
     * Implementation note — Wire API, not i2c_master_probe():
     *   Adafruit_I2CDevice::begin() calls _wire->begin() on every sensor probe
     *   attempt.  On the ESP32-S3 new-gen IDF I2C driver this can cause the
     *   internal i2c_master_bus_handle_t to be re-created with a fresh handle
     *   value that differs from what i2cBusHandle(0) subsequently returns.
     *   Passing that mismatched handle to i2c_master_probe() gives it a struct
     *   whose cmd_semphr field contains garbage (observed: 0x0000BED4), and
     *   xQueueSemaphoreTake(0x0000BED4) panics with StoreProhibited because
     *   0x0000BED4 is in the read-only ROM region.
     *
     *   Using Wire.beginTransmission()/endTransmission() instead bypasses the
     *   raw IDF probe API entirely.  The Wire layer returns error codes rather
     *   than panicking when a device is absent or the bus is recovering.
     *
     * @param timeoutMs  Per-address probe timeout in ms.
     * @return           Number of devices that responded.
     */
    uint8_t scanI2c(uint32_t timeoutMs) {
        TwoWire& wire = Wire;

        // Apply the requested per-address timeout through the Wire API.
        // Wire::setTimeOut() takes uint16_t ms; clamp to avoid truncation.
        const uint16_t wireTimeout = (timeoutMs > 0xFFFF)
                                   ? static_cast<uint16_t>(0xFFFF)
                                   : static_cast<uint16_t>(timeoutMs);
        wire.setTimeOut(wireTimeout);

        uint8_t found = 0;
        log_i("[hardware] I2C bus scan (SDA=%d SCL=%d):", SDA_PIN, SCL_PIN);
        for (uint8_t addr = 1; addr < 127; ++addr) {
            wire.beginTransmission(addr);
            const uint8_t err = wire.endTransmission();
            if (err == 0) {
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
        // No sensor library should call Wire.begin() again after this.
        //
        // Adafruit_I2CDevice::begin() (used by every Adafruit sensor) calls
        // _wire->begin() on the passed-in TwoWire reference.  On this target
        // (ESP32-S3, new-gen IDF I2C driver) the Arduino HAL detects the bus
        // is already initialised and logs "Bus already started in Master Mode"
        // then returns without re-creating the IDF driver.  However the extra
        // call can leave the IDF state machine in a non-IDLE state after a
        // failed device-detect transaction, which is why scanI2c() uses the
        // Wire API rather than i2c_master_probe() directly.
        //
        // The QMI8658 library is vendored in lib/QMI8658/ with its internal
        // Wire.begin() call removed — see lib/QMI8658/src/QMI8658.cpp.
        Wire.begin(SDA_PIN, SCL_PIN);

        // scanI2c(100);

        // // scanI2c() probes every 7-bit address with a bare write-address+STOP.
        // // Some slaves (e.g. QMI8658) don't cleanly reset their internal I2C
        // // state machine after receiving an address byte with no data register
        // // and an immediate STOP.  A bus recovery here resets master and slaves
        // // to a known-idle state before any real module initialisation touches
        // // the bus — mirroring the clean-bus condition a standalone sketch has
        // // when it calls Wire.begin() and then immediately talks to one device.
        // recoverI2c();

        // Verify at the HAL level that the ESP-IDF I2C master driver actually
        // came up.  i2cIsInit() / i2cBusHandle() are only available in the
        // Core 3.x new-gen driver headers; skip this check on Core 2.x where
        // Wire.begin() failures must be caught differently.
#if ESP_ARDUINO_VERSION_MAJOR >= 3
        if (!i2cIsInit(0)) {
            log_e("[hardware] Wire.begin() returned but i2cIsInit(0) is false — I2C driver failed to start");
            return module::InitStatus::MODULE_INIT_HARDWARE_ERROR;
        }
        log_d("[hardware] I2C bus 0 initialised (SDA=%d SCL=%d, handle=%p)",
              SDA_PIN, SCL_PIN, i2cBusHandle(0));
#else
        log_i("[hardware] I2C bus initialised (SDA=%d SCL=%d)", SDA_PIN, SCL_PIN);
#endif

        // SPI — CS is managed per-device; -1 means no default CS pin.
        SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    void recoverI2c() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
        // IDF 5.x new-gen driver: Wire.end() alone cannot clear a stuck
        // `trans_done` flag after a failed transaction.  Use
        // i2c_master_bus_reset() (the IDF 5.x-sanctioned path) which toggles
        // SCL, issues a STOP, and clears all internal error flags without
        // destroying the bus handle.  Fall back to Wire.end/begin only if the
        // API call itself fails.
        // i2cBusHandle() returns void* — cast to the concrete IDF handle type.
        auto handle = static_cast<i2c_master_bus_handle_t>(i2cBusHandle(0));
        if (handle != nullptr) {
            const esp_err_t err = i2c_master_bus_reset(handle);
            if (err == ESP_OK) {
                log_i("[hardware] I2C bus reset via i2c_master_bus_reset()");
                return;
            }
            log_w("[hardware] i2c_master_bus_reset() failed (%d) — falling back to Wire.end/begin",
                  static_cast<int>(err));
        }
#endif
        // Core 2.x (IDF 4.x old-gen driver): Wire.end() correctly tears down
        // the driver handle and Wire.begin() recreates it in a clean state.
        // Also used as a last-resort fallback on Core 3.x if bus_reset fails.
        Wire.end();
        Wire.begin(SDA_PIN, SCL_PIN);
        log_i("[hardware] I2C bus recovered via Wire.end/Wire.begin");
    }

    TwoWire&  i2c() { return Wire; }
    SPIClass& spi() { return SPI;  }

} // namespace hardware
