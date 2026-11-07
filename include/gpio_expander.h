/**
 * @file gpio_expander.h
 * @brief MCP23S08 8-bit SPI GPIO expander driver.
 *
 * Holds the slow signals that have no ESP32 pin of their own: the +-15 V
 * power-good flags, the display backlight enable, INA239 ALERT and TSC2046
 * PENIRQ, plus three spare pins (EXPANDER_PIN_* in pin_config.h).  SPI mode 0 on the shared bus, chip select
 * EXPANDER_CS_PIN.  RESET is tied high and INT is not wired to the MCU.
 */

#pragma once

#include <Arduino.h>
#include <SPI.h>

namespace gpio_expander {

/**
 * Configure the pin directions and confirm the device answers by reading the
 * direction register back.  Outputs start low.
 * @return true if the expander answered.
 * @code
 * gpio_expander::begin();
 * @endcode
 */
bool begin();

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

/**
 * Port byte from the latest readPins() call, with no SPI traffic.  amplifier::
 * service() refreshes it every 250 ms.
 * @return Bit n = level of pin n, or -1 before the first successful read.
 * @code
 * const int16_t levels = gpio_expander::lastPins();
 * @endcode
 */
int16_t lastPins();

/**
 * Check one pin of the cached port byte for an active-low input.
 * @param pin Expander pin 0-7 (EXPANDER_PIN_*).
 * @return true if the pin read low; false if it read high or nothing was read yet.
 * @code
 * const bool alert = gpio_expander::pinLow(EXPANDER_PIN_INA239_ALERT);
 * @endcode
 */
bool pinLow(uint8_t pin);

}  // namespace gpio_expander
