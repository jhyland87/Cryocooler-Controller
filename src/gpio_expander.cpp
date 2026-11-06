/**
 * @file gpio_expander.cpp
 * @brief MCP23S08 8-bit SPI GPIO expander driver (Microchip DS20001919F).
 *
 * Each transfer is opcode, register, data.  A1 and A0 are tied low, so the
 * opcodes are 0x40 (write) and 0x41 (read).
 */

#include "gpio_expander.h"

#include "esp_log.h"
#include "pin_config.h"
#include "spi_device.h"

namespace gpio_expander {

static const char* const TAG = "gpio_expander";

// The datasheet allows 10 MHz from 2.7 V; there is no need to run that fast.
static const SpiDevice sExpander(EXPANDER_CS_PIN, SPISettings(5e6, MSBFIRST, SPI_MODE0));

static constexpr uint8_t OPCODE_WRITE = 0x40;
static constexpr uint8_t OPCODE_READ  = 0x41;

static constexpr uint8_t REG_IODIR = 0x00;
static constexpr uint8_t REG_GPPU  = 0x06;
static constexpr uint8_t REG_GPIO  = 0x09;
static constexpr uint8_t REG_OLAT  = 0x0A;

static constexpr uint8_t OUTPUT_MASK = (1u << EXPANDER_PIN_DISP_BL) |
                                       (1u << EXPANDER_PIN_READY_IND) |
                                       (1u << EXPANDER_PIN_FAULT_IND);
// The unused pin is an input, so its weak pull-up stops it floating.
static constexpr uint8_t PULLUP_MASK = 1u << EXPANDER_PIN_SPARE;

static bool sPresent = false;
static uint8_t sOutputLevels = 0;

static void writeRegister(uint8_t reg, uint8_t value) {
    SpiTransaction transaction(sExpander);
    transaction.transfer(OPCODE_WRITE);
    transaction.transfer(reg);
    transaction.transfer(value);
}

static uint8_t readRegister(uint8_t reg) {
    SpiTransaction transaction(sExpander);
    transaction.transfer(OPCODE_READ);
    transaction.transfer(reg);
    return transaction.transfer(0x00);
}

bool begin() {
    sExpander.begin();

    // Latch the outputs low before enabling their drivers.
    writeRegister(REG_OLAT, sOutputLevels);
    writeRegister(REG_GPPU, PULLUP_MASK);
    const uint8_t direction = static_cast<uint8_t>(~OUTPUT_MASK);
    writeRegister(REG_IODIR, direction);

    // A missing device leaves MISO all ones or all zeros, never this pattern.
    sPresent = (readRegister(REG_IODIR) == direction);
    if (!sPresent) {
        ESP_LOGW(TAG, "MCP23S08 not found (CS decoder Y%d)", sExpander.chipSelectId() - CS_ID_BASE);
        return false;
    }
    ESP_LOGI(TAG, "MCP23S08 found");
    return true;
}

bool isPresent() { return sPresent; }

bool writePin(uint8_t pin, bool level) {
    if (!sPresent || pin > 7 || (OUTPUT_MASK & (1u << pin)) == 0) {
        return false;
    }
    const uint8_t updated = level ? static_cast<uint8_t>(sOutputLevels | (1u << pin))
                                  : static_cast<uint8_t>(sOutputLevels & ~(1u << pin));
    if (updated == sOutputLevels) {
        return true;
    }
    sOutputLevels = updated;
    writeRegister(REG_OLAT, sOutputLevels);
    return true;
}

int16_t readPins() {
    if (!sPresent) {
        return -1;
    }
    return readRegister(REG_GPIO);
}

}  // namespace gpio_expander
