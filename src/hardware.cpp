/**
 * @file hardware.cpp
 * @brief Shared hardware bus registry implementation.
 *
 * Wraps the global SPI singleton, the ACS37800 bus and the SC18IS604
 * SPI-to-I2C bridge behind the hardware:: API. See hardware.h for usage.
 */

#include "hardware.h"
#include "i2c_bridge.h"
#include "tick.h"
#include "pin_config.h"
#include "esp_log.h"
#include "logger.h"


static LogStream _Log = Log.createChildLogger("hardware");

// ---------------------------------------------------------------------------
// I2C error monitor — counts failed bridge transactions, logs periodic
// summaries, and resets the bridge when a threshold is exceeded.
// ---------------------------------------------------------------------------

static uint32_t sI2cErrorCount    = 0;   // errors since last summary window
static uint32_t sI2cErrorTotal    = 0;   // lifetime total
static uint32_t sI2cLastSummaryMs = 0;
static uint32_t sI2cRecoveryCount = 0;   // how many bus resets performed

static constexpr uint32_t I2C_SUMMARY_INTERVAL_MS = 10'000;
static constexpr uint32_t I2C_RECOVERY_THRESHOLD  = 10;  // errors per window

// ACS37800 dedicated SPI bus (SPI3_HOST) — separate from the main bus because
// the ACS37800 keeps MISO driven when CS is high.
static SPIClass sAcsSpi(HSPI);

namespace hardware {
    // -------------------------------------------------------------------------
    // init
    // -------------------------------------------------------------------------

    module::InitStatus init() {
        auto spiStatus = initSPI();

        auto acsSpiStatus = initAcsSPI();

        auto i2cStatus = initI2C();

        if (i2cStatus != module::InitStatus::MODULE_INIT_SUCCESS) {
            return i2cStatus;
        }

        if (spiStatus != module::InitStatus::MODULE_INIT_SUCCESS) {
            return spiStatus;
        }

        if (acsSpiStatus != module::InitStatus::MODULE_INIT_SUCCESS) {
            return acsSpiStatus;
        }

        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    module::InitStatus initSPI() {
        static bool sInitDone = false;

        // Drive all SPI CS pins HIGH before bus init to prevent
        // accidental device selection during power-up.
        for (uint8_t cs : { MCP4921_CS, AD9833_CS, LSM6DSOX_CS, INA239_CS, ADS1220_CS, BRIDGE_CS_PIN }) {
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

    module::InitStatus initAcsSPI() {
        pinMode(ACS37800_CS, OUTPUT);
        digitalWrite(ACS37800_CS, HIGH);

        sAcsSpi.begin(ACS37800_SPI_CLK, ACS37800_SPI_MISO, ACS37800_SPI_MOSI, -1);
        ESP_LOGI("hardware", "ACS37800 SPI bus initialised (HSPI, CLK=%d MISO=%d MOSI=%d CS=%d)",
                 ACS37800_SPI_CLK, ACS37800_SPI_MISO, ACS37800_SPI_MOSI, ACS37800_CS);
        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    module::InitStatus initI2C() {
        // The I2C bus lives behind the SC18IS604 bridge on the main SPI bus,
        // so the SPI bus must be up first. A missing bridge is not fatal:
        // the modules behind it fail their own init.
        if (!i2c_bridge::begin(SPI)) {
            _Log.println(F("SC18IS604 I2C bridge not found — I2C devices unavailable"));
        }
        return module::InitStatus::MODULE_INIT_SUCCESS;
    }

    void recoverI2c() {
        i2c_bridge::recover();
    }

    EMC230xBus& i2c() { return i2c_bridge::bus(); }
    SPIClass& spi()    { return SPI;   }
    SPIClass& acsSpi() { return sAcsSpi; }

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
