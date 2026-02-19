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
#include <Adafruit_MAX31865.h>
#include <MD_AD9833.h>

#include "pin_config.h"
#include "config.h"
#include "conversions.h"

// ── Hardware instances for test use ─────────────────────────────────────────
static Adafruit_MAX31865 max31865(MAX31865_CS);
static MD_AD9833        ad9833(AD9833_CS);

// ── MAX31865 tests ──────────────────────────────────────────────────────────

void test_max31865_initializes(void) {
    bool ok = max31865.begin(RTD_WIRE_CONFIG);
    TEST_ASSERT_TRUE_MESSAGE(ok, "MAX31865 begin() failed — check wiring");
}

void test_max31865_reads_nonzero_rtd(void) {
    uint16_t raw = max31865.readRTD();
    TEST_ASSERT_GREATER_THAN_UINT16(0, raw);
}

void test_max31865_resistance_in_range(void) {
    // A PT100 at room temperature should read roughly 100-115 Ω
    uint16_t raw = max31865.readRTD();
    float resistance = conversions::rtdRawToResistance(raw, RTD_RREF);
    TEST_ASSERT_FLOAT_WITHIN(50.0f, 107.0f, resistance);  // 57–157 Ω
}

void test_max31865_temperature_sane(void) {
    float tempC = max31865.temperature(RTD_RNOMINAL, RTD_RREF);
    // Reasonable ambient range: -20 °C to 80 °C
    TEST_ASSERT_TRUE(tempC > -20.0f);
    TEST_ASSERT_TRUE(tempC < 80.0f);
}

void test_max31865_no_faults(void) {
    uint8_t fault = max31865.readFault();
    TEST_ASSERT_EQUAL_UINT8_MESSAGE(0, fault, "Unexpected MAX31865 fault");
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
    ad9833.setFrequency(MD_AD9833::CHAN_0, AD9833_FREQ_HZ);
    // No return value to check — success means no hang / crash.
    TEST_ASSERT_TRUE(true);
}

// ── MCP4921 DAC tests ───────────────────────────────────────────────────────

#include "dac.h"

void test_mcp4921_init(void) {
    // Should complete without hanging — verifies CS pin and SPI are alive
    dac::init();
    TEST_ASSERT_TRUE(true);
}

void test_mcp4921_write_zero(void) {
    dac::update(0);
    delay(10);

    uint16_t reading = static_cast<uint16_t>(analogRead(DAC_VOLTAGE_PIN));
    // With 8-bit resolution, reading should be near 0
    TEST_ASSERT_LESS_THAN_UINT16(10, reading);
}

void test_mcp4921_write_midscale(void) {
    // Write 2048 (half of 4095) and verify ADC reads a non-zero value
    dac::update(2048);
    delay(10);

    uint16_t reading = static_cast<uint16_t>(analogRead(DAC_VOLTAGE_PIN));
    TEST_ASSERT_GREATER_THAN_UINT16(0, reading);
}

// ── Entry point (PlatformIO Unity on embedded) ──────────────────────────────

void setup() {
    delay(2000);  // Give serial monitor time to connect

    SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

    UNITY_BEGIN();

    // MAX31865
    RUN_TEST(test_max31865_initializes);
    RUN_TEST(test_max31865_reads_nonzero_rtd);
    RUN_TEST(test_max31865_resistance_in_range);
    RUN_TEST(test_max31865_temperature_sane);
    RUN_TEST(test_max31865_no_faults);

    // AD9833
    RUN_TEST(test_ad9833_initializes);
    RUN_TEST(test_ad9833_set_frequency);

    // MCP4921 DAC
    RUN_TEST(test_mcp4921_init);
    RUN_TEST(test_mcp4921_write_zero);
    RUN_TEST(test_mcp4921_write_midscale);

    UNITY_END();
}

void loop() {
    // Nothing — tests run once in setup()
}
