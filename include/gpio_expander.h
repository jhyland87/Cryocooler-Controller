/**
 * @file gpio_expander.h
 * @brief MCP23S08 8-bit SPI GPIO expander driver.
 *
 * Holds the slow signals that have no ESP32 pin of their own: the four
 * power-good flags, the display backlight enable and the READY and FAULT LEDs
 * (EXPANDER_PIN_* in pin_config.h).  SPI mode 0 on the shared bus, chip select
 * EXPANDER_CS_PIN.  RESET is tied high and INT is not wired to the MCU.
 */

#pragma once

#include <Arduino.h>
#include <SPI.h>

namespace gpio_expander {

/**
 * Configure the pin directions and confirm the device answers by reading the
 * direction register back.  Outputs start low.
 * @param spi Shared SPI bus (already started).
 * @return true if the expander answered.
 * @code
 * gpio_expander::begin(SPI);
 * @endcode
 */
bool begin(SPIClass& spi);

/** @return true if begin() found the expander. */
bool isPresent();

/**
 * Drive one output pin.  SPI traffic only happens when the level changes, so
 * this is safe to call every loop() tick.
 * @param pin   Expander pin 0-7, configured as an output (EXPANDER_PIN_*).
 * @param level Output level.
 * @return false if the expander is absent or @p pin is not an output.
 * @code
 * gpio_expander::writePin(EXPANDER_PIN_DISP_BL, true);
 * @endcode
 */
bool writePin(uint8_t pin, bool level);

/**
 * Read the level of all eight pins.
 * @return Bit n = level of pin n, or -1 if the expander is absent.
 * @code
 * const int16_t levels = gpio_expander::readPins();  // e.g. 0b10001111
 * @endcode
 */
int16_t readPins();

}  // namespace gpio_expander
