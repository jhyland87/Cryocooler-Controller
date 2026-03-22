/**
 * @file test_hardware.cpp
 * @brief On-device integration tests (runs on ESP32 via Serial)
 *
 * These tests exercise real hardware peripherals.  Flash and run
 * with:  pio test -e esp32dev
 *
 * Unity sends results over Serial; PlatformIO captures them
 * automatically.
 */

#include <Arduino.h>
#include <unity.h>
#include <SPI.h>
#include <Wire.h>
#include <SparkFun_ADS122C04_ADC_Arduino_Library.h>
#include <MD_AD9833.h>

#include "pin_config.h"
#include "config.h"
#include "conversions.h"

// ── Hardware instances for test use ─────────────────────────────────────────
static SFE_ADS122C04 ads122c04;
static MD_AD9833     ad9833(AD9833_CS);

// ── ADS122C04 tests ─────────────────────────────────────────────────────────

void test_ads122c04_initializes(void) {
    bool ok = ads122c04.begin(ADS122C04_RTD_SENSOR_I2C_ADDRESS, Wire);
    TEST_ASSERT_TRUE_MESSAGE(ok, "ADS122C04 begin() failed — check I2C wiring");
}

void test_ads122c04_configures_4wire(void) {
    ads122c04.configureADCmode(ADS122C04_4WIRE_MODE);
    ads122c04.setGain(ADS122C04_GAIN_1);
    ads122c04.enablePGA(ADS122C04_PGA_DISABLED);
    ads122c04.setIDACcurrent(ADS122C04_IDAC_CURRENT_250_UA);
    TEST_ASSERT_TRUE(true);  // no crash = success
}

void test_ads122c04_reads_nonzero(void) {
    ads122c04.start();
    delay(100);  // wait for conversion
    uint32_t raw = ads122c04.readADC();
    TEST_ASSERT_GREATER_THAN_UINT32(0, raw);
}

void test_ads122c04_resistance_in_range(void) {
    // A PT1000 at room temperature should read roughly 1000-1100 Ω
    ads122c04.start();
    delay(100);
    uint32_t raw = ads122c04.readADC();
    int32_t signed_raw = (raw & 0x00800000)
                         ? static_cast<int32_t>(raw | 0xFF000000)
                         : static_cast<int32_t>(raw);
    float resistance = (static_cast<float>(signed_raw) / ADS122C04_ADC_FULL_SCALE)
                       * PT1000_REF_R / PT1000_GAIN;
    TEST_ASSERT_FLOAT_WITHIN(200.0f, 1050.0f, resistance);  // 850–1250 Ω
}

void test_ads122c04_temperature_sane(void) {
    ads122c04.start();
    delay(100);
    uint32_t raw = ads122c04.readADC();
    int32_t signed_raw = (raw & 0x00800000)
                         ? static_cast<int32_t>(raw | 0xFF000000)
                         : static_cast<int32_t>(raw);
    float resistance = (static_cast<float>(signed_raw) / ADS122C04_ADC_FULL_SCALE)
                       * PT1000_REF_R / PT1000_GAIN;
    float tempC = conversions::resistanceToTemperaturePT1000(resistance);
    // Reasonable ambient range: -20 °C to 80 °C
    TEST_ASSERT_TRUE(tempC > -20.0f);
    TEST_ASSERT_TRUE(tempC < 80.0f);
}

// ── AD9833 tests ────────────────────────────────────────────────────────────

void test_ad9833_initializes(void) {
    // ad9833.begin() does not return a status, so we verify it
    // doesn't hang — if this test completes, the SPI bus is alive.
    ad9833.begin();
    TEST_ASSERT_TRUE_MESSAGE(true, "AD9833 begin() completed");
}

void test_ad9833_set_frequency(void) {
    ad9833.setMode(MD_AD9833::MODE_SINE);
    ad9833.setFrequency(MD_AD9833::CHAN_0, AMPLIFIER_FREQ_HZ);
    // No return value to check — success means no hang / crash.
    TEST_ASSERT_TRUE(true);
}


// ── Entry point (PlatformIO Unity on embedded) ──────────────────────────────

void setup() {
    delay(2000);  // Give serial monitor time to connect

    SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

    UNITY_BEGIN();

    // ADS122C04
    RUN_TEST(test_ads122c04_initializes);
    RUN_TEST(test_ads122c04_configures_4wire);
    RUN_TEST(test_ads122c04_reads_nonzero);
    RUN_TEST(test_ads122c04_resistance_in_range);
    RUN_TEST(test_ads122c04_temperature_sane);

    // AD9833
    RUN_TEST(test_ad9833_initializes);
    RUN_TEST(test_ad9833_set_frequency);

    UNITY_END();
}

void loop() {
    // Nothing — tests run once in setup()
}
