/**
 * @file i2c_bridge.cpp
 * @brief SC18IS604 SPI-to-I2C bridge driver (NXP datasheet rev. 1.0).
 *
 * SPI mode 3, up to 1.2 MHz, at least 8 us between SPI bytes and 0.4 us
 * between transactions.  Commands used: 0x00 write, 0x01 read, 0x02 read
 * after write, 0x06 read buffer, 0x20/0x21 write/read register, 0xFE version.
 */

#include "i2c_bridge.h"

#include "esp_log.h"
#include "hardware.h"
#include "pin_config.h"

namespace i2c_bridge {

static constexpr char TAG[] = "i2c_bridge";

static constexpr uint32_t SPI_HZ          = 1'000'000;
static constexpr uint32_t BYTE_GAP_US     = 10;      // datasheet minimum 8 us
static constexpr uint32_t FIRST_POLL_US   = 50;      // t_d = 35 us after the last SCLK
static constexpr uint32_t STATUS_TIMEOUT_US = 10'000;

static constexpr uint8_t CMD_WRITE          = 0x00;
static constexpr uint8_t CMD_READ           = 0x01;
static constexpr uint8_t CMD_READ_AFTER_WR  = 0x02;
static constexpr uint8_t CMD_READ_BUFFER    = 0x06;
static constexpr uint8_t CMD_WRITE_REG      = 0x20;
static constexpr uint8_t CMD_READ_REG       = 0x21;
static constexpr uint8_t CMD_VERSION        = 0xFE;

static constexpr uint8_t REG_I2C_CLOCK      = 0x02;
static constexpr uint8_t REG_I2C_STATUS     = 0x04;
static constexpr uint8_t I2C_CLOCK_100KHZ   = 19;    // Table 7: 99 kHz

static constexpr uint8_t STATUS_OK          = 0xF0;
static constexpr uint8_t STATUS_BUSY        = 0xF3;

static SPIClass* sSpi    = nullptr;
static bool      sPresent = false;

/** One SPI transaction: @p count bytes out (and back into @p rx if given). */
static void transfer(const uint8_t* tx, uint8_t* rx, size_t count) {
    sSpi->beginTransaction(SPISettings(SPI_HZ, MSBFIRST, SPI_MODE3));
    digitalWrite(BRIDGE_CS_PIN, LOW);
    delayMicroseconds(1);
    for (size_t index = 0; index < count; ++index) {
        const uint8_t received = sSpi->transfer(tx[index]);
        if (rx != nullptr) rx[index] = received;
        if (index + 1 < count) delayMicroseconds(BYTE_GAP_US);
    }
    digitalWrite(BRIDGE_CS_PIN, HIGH);
    sSpi->endTransaction();
    delayMicroseconds(1);
}

static void writeRegister(uint8_t reg, uint8_t value) {
    const uint8_t tx[] = {CMD_WRITE_REG, reg, value};
    transfer(tx, nullptr, sizeof(tx));
}

static uint8_t readRegister(uint8_t reg) {
    const uint8_t tx[3] = {CMD_READ_REG, reg, 0x00};
    uint8_t rx[3] = {};
    transfer(tx, rx, sizeof(tx));
    return rx[2];
}

/** Waits for the I2C transaction to finish; returns I2CStat (0 on timeout). */
static uint8_t waitStatus() {
    delayMicroseconds(FIRST_POLL_US);
    const uint32_t startUs = micros();
    do {
        const uint8_t status = readRegister(REG_I2C_STATUS);
        if (status != STATUS_BUSY) return status;
        delayMicroseconds(50);
    } while ((micros() - startUs) < STATUS_TIMEOUT_US);
    return 0;
}

static void readBuffer(uint8_t* data, size_t count) {
    uint8_t tx[1 + 16] = {CMD_READ_BUFFER};
    uint8_t rx[1 + 16] = {};
    if (count > 16) count = 16;
    transfer(tx, rx, 1 + count);
    for (size_t index = 0; index < count; ++index) data[index] = rx[1 + index];
}

static void pulseReset() {
    digitalWrite(BRIDGE_RESET_PIN, LOW);
    delay(1);
    digitalWrite(BRIDGE_RESET_PIN, HIGH);
    delay(5);   // internal oscillator start-up
}

bool begin(SPIClass& spi) {
    sSpi = &spi;
    pinMode(BRIDGE_CS_PIN, OUTPUT);
    digitalWrite(BRIDGE_CS_PIN, HIGH);
    pinMode(BRIDGE_RESET_PIN, OUTPUT);
    digitalWrite(BRIDGE_RESET_PIN, HIGH);
    pulseReset();

    // The version command fills the read buffer with "SC18IS604 1.0.0".
    const uint8_t versionTx[] = {CMD_VERSION};
    transfer(versionTx, nullptr, sizeof(versionTx));
    delayMicroseconds(100);
    uint8_t version[16] = {};
    readBuffer(version, sizeof(version));
    sPresent = (memcmp(version, "SC18IS604", 9) == 0);
    if (!sPresent) {
        ESP_LOGW(TAG, "SC18IS604 not found (CS GPIO%d)", BRIDGE_CS_PIN);
        return false;
    }
    writeRegister(REG_I2C_CLOCK, I2C_CLOCK_100KHZ);
    ESP_LOGI(TAG, "SC18IS604 found: %s", reinterpret_cast<const char*>(version));
    return true;
}

void recover() {
    if (sSpi == nullptr) return;
    pulseReset();
    writeRegister(REG_I2C_CLOCK, I2C_CLOCK_100KHZ);
    ESP_LOGI(TAG, "SC18IS604 reset");
}

bool isPresent() { return sPresent; }

// ---------------------------------------------------------------------------
// EMC230xBus on top of the bridge
// ---------------------------------------------------------------------------

class BridgeBus : public EMC230xBus {
public:
    bool probe(uint8_t addr) override {
        if (!sPresent) return false;
        const uint8_t tx[] = {CMD_READ, 1, static_cast<uint8_t>((addr << 1) | 1)};
        transfer(tx, nullptr, sizeof(tx));
        return finish(waitStatus() == STATUS_OK);
    }

    int16_t readRegister(uint8_t addr, uint8_t reg) override {
        if (!sPresent) return -1;
        const uint8_t tx[] = {CMD_READ_AFTER_WR, 1, 1,
                              static_cast<uint8_t>(addr << 1), reg,
                              static_cast<uint8_t>((addr << 1) | 1)};
        transfer(tx, nullptr, sizeof(tx));
        if (!finish(waitStatus() == STATUS_OK)) return -1;
        uint8_t value = 0;
        readBuffer(&value, 1);
        return value;
    }

    bool writeRegister(uint8_t addr, uint8_t reg, uint8_t value) override {
        if (!sPresent) return false;
        const uint8_t tx[] = {CMD_WRITE, 2, static_cast<uint8_t>(addr << 1), reg, value};
        transfer(tx, nullptr, sizeof(tx));
        return finish(waitStatus() == STATUS_OK);
    }

private:
    // Counts failures for the hardware error monitor.
    static bool finish(bool ok) {
        if (!ok) hardware::reportI2cError();
        return ok;
    }
};

static BridgeBus sBus;

EMC230xBus& bus() { return sBus; }

}  // namespace i2c_bridge
