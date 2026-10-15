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
#include <ADS1220_WE.h>
#include <MD_AD9833.h>

#include "pin_config.h"
#include "config.h"
#include "conversions.h"

// ── Hardware instances for test use ─────────────────────────────────────────
static ADS1220_WE    ads1220(&SPI, ADS1220_CS, -1, false, true);
static MD_AD9833     ad9833(AD9833_CS);

// ── ADS1220 tests ───────────────────────────────────────────────────────────

// Reads one single-shot conversion (20 SPS takes about 50 ms) as a signed
// 24-bit value.
static int32_t readAdcSample() {
    ads1220.start();
    delay(100);
    return ads1220.getRawData();
}

void test_ads1220_initializes(void) {
    bool ok = ads1220.init();
    TEST_ASSERT_TRUE_MESSAGE(ok, "ADS1220 init() failed — check SPI wiring");
}

void test_ads1220_configures_4wire(void) {
    ads1220.setCompareChannels(ADS1220_MUX_1_0);
    ads1220.setGain(ADS1220_GAIN_1);
    ads1220.bypassPGA(true);
    ads1220.setDataRate(ADS1220_DR_LVL_0);
    ads1220.setConversionMode(ADS1220_SINGLE_SHOT);
    ads1220.setVRefSource(ADS1220_VREF_REFP0_REFN0);
    ads1220.setFIRFilter(ADS1220_50HZ_60HZ);
    ads1220.setIdacCurrent(ADS1220_IDAC_250_MU_A);
    ads1220.setIdac1Routing(ADS1220_IDAC_AIN3_REFN1);
    ads1220.setNonBlockingMode(true);
    TEST_ASSERT_TRUE(ads1220.isPGABypassed());
}

void test_ads1220_reads_nonzero(void) {
    int32_t raw = readAdcSample();
    TEST_ASSERT_TRUE(raw != 0);
    TEST_ASSERT_TRUE(raw != -1);
}

void test_ads1220_resistance_in_range(void) {
    // A PT1000 at room temperature should read roughly 1000-1100 Ω
    int32_t raw = readAdcSample();
    float resistance = (static_cast<float>(raw) / ADS1220_ADC_FULL_SCALE)
                       * PT1000_REF_R / PT1000_GAIN;
    TEST_ASSERT_FLOAT_WITHIN(200.0f, 1050.0f, resistance);  // 850–1250 Ω
}

void test_ads1220_temperature_sane(void) {
    int32_t raw = readAdcSample();
    float resistance = (static_cast<float>(raw) / ADS1220_ADC_FULL_SCALE)
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

    pinMode(ADS1220_CS, OUTPUT);
    digitalWrite(ADS1220_CS, HIGH);
    SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

    UNITY_BEGIN();

    // ADS1220
    RUN_TEST(test_ads1220_initializes);
    RUN_TEST(test_ads1220_configures_4wire);
    RUN_TEST(test_ads1220_reads_nonzero);
    RUN_TEST(test_ads1220_resistance_in_range);
    RUN_TEST(test_ads1220_temperature_sane);

    // AD9833
    RUN_TEST(test_ad9833_initializes);
    RUN_TEST(test_ad9833_set_frequency);

    UNITY_END();
}

void loop() {
    // Nothing — tests run once in setup()
}
