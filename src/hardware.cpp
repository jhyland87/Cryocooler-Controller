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
    // init
    // -------------------------------------------------------------------------

    module::InitStatus init() {
        auto spiStatus = initSPI();

        auto i2cStatus = initI2C();

        if (i2cStatus != module::InitStatus::MODULE_INIT_SUCCESS) {
            return i2cStatus;
        }

        if (spiStatus != module::InitStatus::MODULE_INIT_SUCCESS) {
            return spiStatus;
        }

        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    module::InitStatus initSPI() {
        log_i("[hardware] Initialising SPI bus (CLK=%d MISO=%d MOSI=%d)", SPI_CLK, SPI_MISO, SPI_MOSI);
        SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);
        log_i("[hardware] SPI bus initialised (CLK=%d MISO=%d MOSI=%d)", SPI_CLK, SPI_MISO, SPI_MOSI);
        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    module::InitStatus initI2C() {
        log_i("[hardware] Initialising I2C bus (SDA=%d SCL=%d)", SDA_PIN, SCL_PIN);
        // Initialise the shared Wire bus once with the correct pins.
        Wire.begin(SDA_PIN, SCL_PIN);

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
