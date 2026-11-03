/**
 * @file i2c_bridge.h
 * @brief SC18IS604 SPI-to-I2C bridge driver.
 *
 * The EMC2303 fan controller sits on an I2C bus owned by an NXP SC18IS604
 * bridge; the ESP32 only talks SPI (mode 3, shared bus, chip select
 * BRIDGE_CS_PIN, active-low reset on BRIDGE_RESET_PIN).  INT# is not wired to
 * the MCU, so completion is polled through the I2CStat register.
 */

#pragma once

#include <Arduino.h>
#include <SPI.h>
#include <EMC230x.h>

namespace i2c_bridge {

/**
 * Reset the bridge, check its version string and set the I2C clock to about
 * 100 kHz.
 * @param spi Shared SPI bus (already started).
 * @return true if the bridge answered the version command.
 */
bool begin(SPIClass& spi);

/** Pulse RESET and reconfigure the bridge (bus recovery). */
void recover();

/** @return true if begin() found the bridge. */
bool isPresent();

/** The EMC230xBus view of the I2C bus behind the bridge. */
EMC230xBus& bus();

/**
 * Configure the bridge GPIOs: GPIO0-3 each as input-only (false) or push-pull
 * output (true); GPIO4 is always an input. All pins power up as inputs.
 * @param outputMask Bit n set = GPIOn is a push-pull output (bits 0-3).
 * @return false if the bridge is absent.
 * @code
 * i2c_bridge::configureGpio(1u << BRIDGE_GPIO_DISP_BL);  // GPIO0 out, 1-4 in
 * @endcode
 */
bool configureGpio(uint8_t outputMask);

/**
 * Drive one output GPIO (configured with configureGpio()).
 * @param pin   GPIO number 0-3.
 * @param level Output level.
 * @return false if the bridge is absent or @p pin is not 0-3.
 */
bool writeGpio(uint8_t pin, bool level);

/**
 * Read the level of all five bridge GPIOs.
 * @return Bit n = level of GPIOn (bits 0-4), or -1 if the bridge is absent.
 */
int16_t readGpio();

}  // namespace i2c_bridge
