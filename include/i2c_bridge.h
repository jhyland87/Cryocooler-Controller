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

/**
 * Check for the bridge again without pulsing RESET, so it can be called from
 * service().  Sets the I2C clock when found, which also covers a bridge that
 * lost power after boot.
 * @return true if the bridge answered the version command.
 */
bool redetect();

/** Pulse RESET and reconfigure the bridge (bus recovery).  Blocks about 6 ms; no-op if absent. */
void recover();

/** @return true if the last begin() or redetect() found the bridge. */
bool isPresent();

/** The EMC230xBus view of the I2C bus behind the bridge. */
EMC230xBus& bus();

}  // namespace i2c_bridge
