/**
 * @file hardware.cpp
 * @brief Shared hardware bus registry implementation.
 *
 * Wraps the global SPI singleton and the ACS37800 bus behind the hardware::
 * API. See hardware.h for usage.
 */

#include <Arduino.h>
#include "hardware.h"
#include "gpio_expander.h"
#include "pin_config.h"
#include "esp_log.h"

// ACS37800 dedicated SPI bus (SPI3_HOST) — separate from the main bus because
// the ACS37800 keeps MISO driven when CS is high.
static SPIClass sAcsSpi(HSPI);

namespace hardware {
    // -------------------------------------------------------------------------
    // init
    // -------------------------------------------------------------------------

    module::InitStatus init() {
        auto spiStatus = initSPI();

        // A missing expander is not fatal: the WS2812 still shows status and the
        // hardware amplifier interlock does not depend on it.
        if (!gpio_expander::begin(SPI)) {
            ESP_LOGW("hardware", "GPIO expander not found");
        }

        auto acsSpiStatus = initAcsSPI();

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

        // Deselect every SPI device before bus init. These are decoder outputs
        // (spi_select.cpp), and the first call also sets up the decoder pins.
        for (uint8_t cs : { MCP4921_CS, AD9833_CS, LSM6DSOX_CS, INA239_CS, ADS1220_CS,
                            EXPANDER_CS_PIN, DISP_CS_PIN, TOUCH_CS_PIN }) {
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

    SPIClass& spi()    { return SPI;   }
    SPIClass& acsSpi() { return sAcsSpi; }

} // namespace hardware
