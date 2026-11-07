/**
 * @file spi_device.h
 * @brief Standard way for a module to declare and talk to its SPI ICs.
 *
 * A module declares one object per IC in its .cpp file:
 *   - SpiDevice: the module writes the transfers itself, using SpiTransaction.
 *   - SpiChipSelect: a library runs the transfers and applies its own settings.
 *
 * Selecting a decoder output still ends in digitalWrite(), which spi_select.cpp
 * catches, so libraries and these classes share one path to the decoder.
 */

#ifndef SPI_DEVICE_H
#define SPI_DEVICE_H

#include <Arduino.h>
#include <SPI.h>

/**
 * @brief The chip select of an IC whose transfers are run by a library.
 *
 * The constructor touches no hardware, so this is safe to declare as a static
 * and to pass to a library's constructor.
 *
 * @code
 * static constexpr SpiChipSelect sAdcChipSelect(ADS1220_CS);
 * static ADS1220_WE ads1220(&hardware::spi(), sAdcChipSelect.chipSelectId(), -1, false, true);
 * @endcode
 */
class SpiChipSelect {
public:
    /** @param chipSelectId Decoder ID (see pin_config.h) or GPIO number. */
    explicit constexpr SpiChipSelect(uint8_t chipSelectId) : chipSelectId_(chipSelectId) {}

    /** @return The value to pass to digitalWrite() or to a library. */
    constexpr uint8_t chipSelectId() const { return chipSelectId_; }

    /** @brief Sets the chip select up as an output and deselects the IC. */
    void begin() const {
        pinMode(chipSelectId_, OUTPUT);
        digitalWrite(chipSelectId_, HIGH);
    }

private:
    const uint8_t chipSelectId_;
};

/**
 * @brief An SPI IC whose transfers the module writes itself.
 *
 * @code
 * static const SpiDevice sDac(AD5453_SYNC, SPISettings(4e6, MSBFIRST, SPI_MODE1));
 *
 * sDac.begin();                        // once, from init()
 * SpiTransaction transaction(sDac);    // selects the IC
 * transaction.transfer16(0x3000);      // deselected when transaction goes out of scope
 * @endcode
 */
class SpiDevice : public SpiChipSelect {
public:
    /**
     * @param chipSelectId Decoder ID (see pin_config.h) or GPIO number.
     * @param settings     Clock, bit order and SPI mode for this IC.
     * @param bus          Bus the IC is on.
     */
    SpiDevice(uint8_t chipSelectId, const SPISettings& settings, SPIClass& bus = SPI)
        : SpiChipSelect(chipSelectId), settings_(settings), bus_(bus) {}

    /** @return The clock, bit order and SPI mode for this IC. */
    const SPISettings& settings() const { return settings_; }

    /** @return The bus the IC is on. */
    SPIClass& bus() const { return bus_; }

private:
    const SPISettings settings_;
    SPIClass& bus_;
};

/**
 * @brief Holds the bus and selects an IC for as long as this object exists.
 *
 * Takes the bus before selecting and deselects before releasing it, so a transfer
 * can't leave the IC selected, even on an early return.
 *
 * @code
 * static uint8_t readRegister(uint8_t reg) {
 *     SpiTransaction transaction(sImu);
 *     transaction.transfer(reg | 0x80);
 *     return transaction.transfer(0x00);
 * }
 * @endcode
 */
class SpiTransaction {
public:
    /** @param device IC to select. */
    explicit SpiTransaction(const SpiDevice& device) : device_(device) {
        device_.bus().beginTransaction(device_.settings());
        digitalWrite(device_.chipSelectId(), LOW);
    }

    ~SpiTransaction() {
        digitalWrite(device_.chipSelectId(), HIGH);
        device_.bus().endTransaction();
    }

    SpiTransaction(const SpiTransaction&) = delete;
    SpiTransaction& operator=(const SpiTransaction&) = delete;

    /**
     * @brief Sends and receives one byte.
     * @param value Byte to send.
     * @return Byte received.
     */
    uint8_t transfer(uint8_t value) { return device_.bus().transfer(value); }

    /**
     * @brief Sends and receives a 16-bit word.
     * @param value Word to send.
     * @return Word received.
     */
    uint16_t transfer16(uint16_t value) { return device_.bus().transfer16(value); }

private:
    const SpiDevice& device_;
};

#endif  // SPI_DEVICE_H
