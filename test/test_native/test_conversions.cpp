/**
 * @file test_conversions.cpp
 * @brief Native unit tests for pure conversion / math utilities
 *
 * Run with:  pio test -e native
 */

#include <unity.h>
#include "conversions.h"
#include "config.h"

// ── rtdRawToResistance ──────────────────────────────────────────────────────

void test_rtdRawToResistance_zero(void) {
    // Raw value 0 should always give 0 ohms
    TEST_ASSERT_EQUAL_FLOAT(0.0f, conversions::rtdRawToResistance(0, RTD_RREF));
}

void test_rtdRawToResistance_fullScale(void) {
    // Raw value 32768 → ratio = 1.0 → resistance == rRef
    TEST_ASSERT_EQUAL_FLOAT(RTD_RREF, conversions::rtdRawToResistance(32768, RTD_RREF));
}

void test_rtdRawToResistance_halfScale(void) {
    // Raw value 16384 → ratio = 0.5 → resistance == rRef / 2
    float expected = RTD_RREF / 2.0f;
    TEST_ASSERT_FLOAT_WITHIN(0.01f, expected, conversions::rtdRawToResistance(16384, RTD_RREF));
}

void test_rtdRawToResistance_knownPT100(void) {
    // PT100 at 0 °C reads ~100 Ω.  With rRef = 435.3:
    //   raw = (100 / 435.3) * 32768 ≈ 7528
    uint16_t raw = 7528;
    float result = conversions::rtdRawToResistance(raw, 435.3f);
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 100.0f, result);
}

// ── celsiusToFahrenheit ─────────────────────────────────────────────────────

void test_celsiusToFahrenheit_freezing(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 32.0f, conversions::celsiusToFahrenheit(0.0f));
}

void test_celsiusToFahrenheit_boiling(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 212.0f, conversions::celsiusToFahrenheit(100.0f));
}

void test_celsiusToFahrenheit_bodyTemp(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 98.6f, conversions::celsiusToFahrenheit(37.0f));
}

void test_celsiusToFahrenheit_negative(void) {
    // -40 °C == -40 °F  (the crossover point)
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -40.0f, conversions::celsiusToFahrenheit(-40.0f));
}

void test_celsiusToFahrenheit_liquidNitrogen(void) {
    // -196 °C == -320.8 °F
    TEST_ASSERT_FLOAT_WITHIN(0.1f, -320.8f, conversions::celsiusToFahrenheit(-196.0f));
}

// ── celsiusToKelvin ─────────────────────────────────────────────────────────

void test_celsiusToKelvin_absoluteZero(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, conversions::celsiusToKelvin(-273.15f));
}

void test_celsiusToKelvin_freezing(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 273.15f, conversions::celsiusToKelvin(0.0f));
}

void test_celsiusToKelvin_boiling(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 373.15f, conversions::celsiusToKelvin(100.0f));
}

void test_celsiusToKelvin_bodyTemp(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 310.15f, conversions::celsiusToKelvin(37.0f));
}

void test_celsiusToKelvin_negative(void) {
    // -40 °C == 233.15 K
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 233.15f, conversions::celsiusToKelvin(-40.0f));
}

void test_celsiusToKelvin_liquidNitrogen(void) {
    // -196 °C == 77.15 K
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 77.15f, conversions::celsiusToKelvin(-196.0f));
}

// ── fahrenheitToCelsius ─────────────────────────────────────────────────────

void test_fahrenheitToCelsius_freezing(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, conversions::fahrenheitToCelsius(32.0f));
}

void test_fahrenheitToCelsius_boiling(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 100.0f, conversions::fahrenheitToCelsius(212.0f));
}

void test_fahrenheitToCelsius_liquidNitrogen(void) {
    // -320.8 °F == -196 °C
    TEST_ASSERT_FLOAT_WITHIN(0.1f, -196.0f, conversions::fahrenheitToCelsius(-320.8f));
}

// ── Round-trip consistency ──────────────────────────────────────────────────

void test_celsius_fahrenheit_roundTrip(void) {
    float original = 23.45f;
    float result   = conversions::fahrenheitToCelsius(conversions::celsiusToFahrenheit(original));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, original, result);
}

// ── Config sanity checks ────────────────────────────────────────────────────

void test_config_rref_positive(void) {
    TEST_ASSERT_TRUE(RTD_RREF > 0.0f);
}

void test_config_rnominal_positive(void) {
    TEST_ASSERT_TRUE(RTD_RNOMINAL > 0.0f);
}

void test_config_frequency_positive(void) {
    TEST_ASSERT_TRUE(AD9833_FREQ_HZ > 0);
}

void test_config_interval_positive(void) {
    TEST_ASSERT_TRUE(LOOP_INTERVAL_MS > 0);
}

void test_config_adc_resolution_range(void) {
    // ESP32 supports 9-12 bit ADC, plus 8-bit for dacWrite compatibility
    TEST_ASSERT_TRUE(ADC_RESOLUTION >= 8);
    TEST_ASSERT_TRUE(ADC_RESOLUTION <= 12);
}

// ── Entry point ─────────────────────────────────────────────────────────────

int main(int argc, char **argv) {
    UNITY_BEGIN();

    // Resistance conversion
    RUN_TEST(test_rtdRawToResistance_zero);
    RUN_TEST(test_rtdRawToResistance_fullScale);
    RUN_TEST(test_rtdRawToResistance_halfScale);
    RUN_TEST(test_rtdRawToResistance_knownPT100);

    // Temperature conversion
    RUN_TEST(test_celsiusToFahrenheit_freezing);
    RUN_TEST(test_celsiusToFahrenheit_boiling);
    RUN_TEST(test_celsiusToFahrenheit_bodyTemp);
    RUN_TEST(test_celsiusToFahrenheit_negative);
    RUN_TEST(test_celsiusToFahrenheit_liquidNitrogen);
    RUN_TEST(test_celsiusToKelvin_absoluteZero);
    RUN_TEST(test_celsiusToKelvin_freezing);
    RUN_TEST(test_celsiusToKelvin_boiling);
    RUN_TEST(test_celsiusToKelvin_bodyTemp);
    RUN_TEST(test_celsiusToKelvin_negative);
    RUN_TEST(test_celsiusToKelvin_liquidNitrogen);
    RUN_TEST(test_fahrenheitToCelsius_freezing);
    RUN_TEST(test_fahrenheitToCelsius_boiling);
    RUN_TEST(test_fahrenheitToCelsius_liquidNitrogen);
    RUN_TEST(test_celsius_fahrenheit_roundTrip);

    // Config sanity
    RUN_TEST(test_config_rref_positive);
    RUN_TEST(test_config_rnominal_positive);
    RUN_TEST(test_config_frequency_positive);
    RUN_TEST(test_config_interval_positive);
    RUN_TEST(test_config_adc_resolution_range);

    return UNITY_END();
}
