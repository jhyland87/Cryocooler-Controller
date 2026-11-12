/**
 * @file hardware.cpp
 * @brief Shared hardware bus registry implementation.
 *
 * Wraps the global SPI singleton behind the hardware:: API. See hardware.h
 * for usage.
 */

#include <Arduino.h>
#include "hardware.h"
#include "gpio_expander.h"
#include "pin_config.h"
#include "esp_log.h"

namespace hardware {
    // -------------------------------------------------------------------------
    // init
    // -------------------------------------------------------------------------

    module::InitStatus init() {
        auto spiStatus = initSPI();

        // A missing expander is not fatal: the WS2812 still shows status and the
        // hardware amplifier interlock does not depend on it.
        if (!gpio_expander::begin()) {
            ESP_LOGW("hardware", "GPIO expander not found");
        }

        return spiStatus;
    }

    module::InitStatus initSPI() {
        static bool sInitDone = false;

        // Deselect every SPI device before bus init. All but ACS37800_CS (a
        // GPIO) are decoder outputs (spi_select.cpp), and the first call also
        // sets up the decoder pins.
        for (uint8_t cs : { AD5453_SYNC, AD9833_CS, LSM6DSOX_CS, INA239_CS, ADS1220_CS,
                            EXPANDER_CS_PIN, DISP_CS_PIN, TOUCH_CS_PIN, ACS37800_CS }) {
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

    void idleSpiClockLow() {
        static const SPISettings idleLowSettings(1e6, MSBFIRST, SPI_MODE0);
        SPI.beginTransaction(idleLowSettings);
        SPI.transfer(0x00);
        SPI.endTransaction();
    }

    SPIClass& spi() { return SPI; }

} // namespace hardware
