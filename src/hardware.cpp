/**
 * @file hardware.cpp
 * @brief Shared hardware bus registry implementation.
 *
 * Wraps the global Wire and SPI singletons behind the hardware:: API.
 * See hardware.h for rationale and usage.
 */

#include <cstring>               // strstr()

#include "hardware.h"
#include "tick.h"
#include "pin_config.h"
#include "esp32-hal-i2c.h"      // i2cIsInit(), i2cBusHandle() (Core 3.x / IDF 5.x)
#include "esp_log.h"
#include "logger.h"
#if ESP_ARDUINO_VERSION_MAJOR >= 3
#include "driver/i2c_master.h"  // i2c_master_bus_reset() — IDF 5.x only
#endif


static LogStream _Log = Log.createChildLogger("hardware");

// ---------------------------------------------------------------------------
// I2C error monitor — counts Wire errors, logs periodic summaries, and
// triggers bus recovery when a threshold is exceeded.
// ---------------------------------------------------------------------------

static uint32_t sI2cErrorCount    = 0;   // errors since last summary window
static uint32_t sI2cErrorTotal    = 0;   // lifetime total
static uint32_t sI2cLastSummaryMs = 0;
static uint32_t sI2cRecoveryCount = 0;   // how many bus resets performed

static constexpr uint32_t I2C_SUMMARY_INTERVAL_MS = 10'000;
static constexpr uint32_t I2C_RECOVERY_THRESHOLD  = 10;  // errors per window

// Original vprintf handler — saved so we can chain through for non-Wire logs.
static vprintf_like_t sOriginalVprintf = nullptr;

/**
 * Custom ESP log handler that intercepts Wire.cpp error messages.
 * Wire errors are counted silently; all other log output is passed through
 * to the original handler unchanged.
 */
static int filteredVprintf(const char* fmt, va_list args) {
    // Wire.cpp errors contain the tag "Wire" embedded in the format string
    // via the LOG_FORMAT macro: "[%d][E][Wire.cpp:%d] ..."
    // We detect this by checking for the "[Wire.cpp:" substring in fmt.
    if (fmt != nullptr && strstr(fmt, "[Wire.cpp:") != nullptr) {
        ++sI2cErrorCount;
        ++sI2cErrorTotal;
        return 0;   // suppress output
    }
    return sOriginalVprintf ? sOriginalVprintf(fmt, args) : vprintf(fmt, args);
}

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
        static bool sInitDone = false;

        // Drive all SPI CS pins HIGH before bus init to prevent
        // accidental device selection during power-up.
        for (uint8_t cs : { MCP4921_CS, AD9833_CS, LSM6DSOX_CS }) {
            pinMode(cs, OUTPUT);
            digitalWrite(cs, HIGH);
        }

        SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);
        if (!sInitDone) {
            ESP_LOGI("hardware", "SPI bus initialised (CLK=%d MISO=%d MOSI=%d)", SPI_CLK, SPI_MISO, SPI_MOSI);
            sInitDone = true;
        }
        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    module::InitStatus initI2C() {
        // --- Bus 0 (Wire) — shared sensor/relay bus ---
        ESP_LOGI("hardware", "Initialising I2C bus 0 (SDA=%d SCL=%d)", SDA_PIN, SCL_PIN);
        Wire.begin(SDA_PIN, SCL_PIN);

        // Verify at the HAL level that the ESP-IDF I2C master driver actually
        // came up.  i2cIsInit() / i2cBusHandle() are only available in the
        // Core 3.x new-gen driver headers; skip this check on Core 2.x where
        // Wire.begin() failures must be caught differently.
        #if ESP_ARDUINO_VERSION_MAJOR >= 3
        if (!i2cIsInit(0)) {
            ESP_LOGE("hardware", "Wire.begin() returned but i2cIsInit(0) is false — I2C driver failed to start");
            _Log.println("Wire.begin() returned but i2cIsInit(0) is false — I2C driver failed to start");
            return module::InitStatus::MODULE_INIT_HARDWARE_ERROR;
        }
        ESP_LOGD("hardware", "I2C bus 0 initialised (SDA=%d SCL=%d, handle=%p)",
                SDA_PIN, SCL_PIN, i2cBusHandle(0));
        #else
        ESP_LOGI("hardware", "I2C bus 0 initialised (SDA=%d SCL=%d)", SDA_PIN, SCL_PIN);
        #endif

        // Reduce the Wire timeout from the default (~1 s on ESP32-S3) to 50 ms.
        // A missing or stuck device will NACK/timeout quickly instead of blocking
        // the main loop for a full second per failed transaction.
        Wire.setTimeOut(50);  // ms

        // DAC is now on SPI (MCP4901) — no second I2C bus needed.

        // Install a custom log handler that silently counts Wire.cpp error
        // messages instead of printing them.  All other ESP log output is
        // passed through unchanged.  The I2C health monitor (serviceI2c)
        // logs periodic summaries and triggers bus recovery as needed.
        sOriginalVprintf = esp_log_set_vprintf(filteredVprintf);

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
                ESP_LOGI("hardware", "I2C bus reset via i2c_master_bus_reset()");
                return;
            }
            ESP_LOGW("hardware", "i2c_master_bus_reset() failed (%d) — falling back to Wire.end/begin",
                  static_cast<int>(err));
        }
#endif
        // Core 2.x (IDF 4.x old-gen driver): Wire.end() correctly tears down
        // the driver handle and Wire.begin() recreates it in a clean state.
        // Also used as a last-resort fallback on Core 3.x if bus_reset fails.
        Wire.end();
        Wire.begin(SDA_PIN, SCL_PIN);
        ESP_LOGI("hardware", "I2C bus recovered via Wire.end/Wire.begin");
    }

    TwoWire&  i2c()    { return Wire;  }
    SPIClass& spi()    { return SPI;   }

    // -------------------------------------------------------------------------
    // I2C error monitor
    // -------------------------------------------------------------------------

    void reportI2cError() {
        ++sI2cErrorCount;
        ++sI2cErrorTotal;
    }

    void serviceI2c() {
        const uint32_t nowMs = tick::nowMs();
        if (nowMs - sI2cLastSummaryMs < I2C_SUMMARY_INTERVAL_MS) return;
        sI2cLastSummaryMs = nowMs;
        if (sI2cErrorCount == 0) return;

        _Log.printf("I2C: %u errors in last %us (total: %u, recoveries: %u)\n",
                    sI2cErrorCount,
                    static_cast<unsigned>(I2C_SUMMARY_INTERVAL_MS / 1000),
                    sI2cErrorTotal,
                    sI2cRecoveryCount);

        if (sI2cErrorCount >= I2C_RECOVERY_THRESHOLD) {
            ++sI2cRecoveryCount;
            _Log.printf("I2C: error threshold reached — resetting bus (recovery #%u)\n",
                        sI2cRecoveryCount);
            recoverI2c();
        }

        sI2cErrorCount = 0;
    }

    uint32_t getI2cErrorTotal()    { return sI2cErrorTotal; }
    uint32_t getI2cRecoveryCount() { return sI2cRecoveryCount; }

} // namespace hardware
