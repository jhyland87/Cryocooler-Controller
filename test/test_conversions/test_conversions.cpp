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
    TEST_ASSERT_EQUAL_FLOAT(0.0f, conversions::rtdRawToResistance(0, RTD_RREF));
}

void test_rtdRawToResistance_fullScale(void) {
    TEST_ASSERT_EQUAL_FLOAT(RTD_RREF, conversions::rtdRawToResistance(32768, RTD_RREF));
}

void test_rtdRawToResistance_halfScale(void) {
    float expected = RTD_RREF / 2.0f;
    TEST_ASSERT_FLOAT_WITHIN(0.01f, expected, conversions::rtdRawToResistance(16384, RTD_RREF));
}

void test_rtdRawToResistance_knownPT100(void) {
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
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -40.0f, conversions::celsiusToFahrenheit(-40.0f));
}

void test_celsiusToFahrenheit_liquidNitrogen(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.1f, -320.8f, conversions::celsiusToFahrenheit(-196.0f));
}

// ── kelvinToCelsius ─────────────────────────────────────────────────────────

void test_kelvinToCelsius_absoluteZero(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -273.15f, conversions::kelvinToCelsius(0.0f));
}

void test_kelvinToCelsius_freezing(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, conversions::kelvinToCelsius(273.15f));
}

void test_kelvinToCelsius_boiling(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 100.0f, conversions::kelvinToCelsius(373.15f));
}

void test_kelvinToCelsius_bodyTemp(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 37.0f, conversions::kelvinToCelsius(310.15f));
}

void test_kelvinToCelsius_negative(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -40.0f, conversions::kelvinToCelsius(233.15f));
}

void test_kelvinToCelsius_liquidNitrogen(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -196.0f, conversions::kelvinToCelsius(77.15f));
}

// ── fahrenheitToCelsius ─────────────────────────────────────────────────────

void test_fahrenheitToCelsius_freezing(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, conversions::fahrenheitToCelsius(32.0f));
}

void test_fahrenheitToCelsius_boiling(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 100.0f, conversions::fahrenheitToCelsius(212.0f));
}

void test_fahrenheitToCelsius_liquidNitrogen(void) {
    TEST_ASSERT_FLOAT_WITHIN(0.1f, -196.0f, conversions::fahrenheitToCelsius(-320.8f));
}

void test_celsius_fahrenheit_roundTrip(void) {
    float original = 23.45f;
    float result   = conversions::fahrenheitToCelsius(conversions::celsiusToFahrenheit(original));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, original, result);
}

// ── tempCToDacValue ─────────────────────────────────────────────────────────

void test_tempCToDacValue_aboveAmbient(void) {
    // Temperature at or above ambient -> DAC must be 0
    // 300K = 26.85C, 295K = 21.85C, 78K = -195.15C
    TEST_ASSERT_EQUAL_UINT16(0, conversions::tempCToDacValue(26.85f, 21.85f, -195.15f, 4095));
    TEST_ASSERT_EQUAL_UINT16(0, conversions::tempCToDacValue(21.85f, 21.85f, -195.15f, 4095));
}

void test_tempCToDacValue_atSetpoint(void) {
    // Temperature at or below setpoint -> DAC must be maximum
    TEST_ASSERT_EQUAL_UINT16(4095, conversions::tempCToDacValue(-195.15f, 21.85f, -195.15f, 4095));
    TEST_ASSERT_EQUAL_UINT16(4095, conversions::tempCToDacValue(-203.15f, 21.85f, -195.15f, 4095));
}

void test_tempCToDacValue_midpoint(void) {
    // Halfway between ambient (21.85) and setpoint (-195.15): temp = -86.65 -> DAC ~2047
    const float midTemp = (21.85f + (-195.15f)) / 2.0f;
    const uint16_t result = conversions::tempCToDacValue(midTemp, 21.85f, -195.15f, 4095);
    TEST_ASSERT_FLOAT_WITHIN(5.0f, 2047.0f, static_cast<float>(result));
}

void test_tempCToDacValue_quarterPoint(void) {
    // 25% of the way down (75% of range remaining): temp = 21.85 - 0.25*(21.85-(-195.15)) = -32.4
    const float temp = 21.85f - 0.25f * (21.85f - (-195.15f));
    const uint16_t result = conversions::tempCToDacValue(temp, 21.85f, -195.15f, 4095);
    // Expected ~1023
    TEST_ASSERT_FLOAT_WITHIN(5.0f, 1023.0f, static_cast<float>(result));
}

void test_tempCToDacValue_proportionalIncrease(void) {
    // Lower temperature should yield a higher DAC value
    const uint16_t high = conversions::tempCToDacValue(-100.0f, 21.85f, -195.15f, 4095);
    const uint16_t low  = conversions::tempCToDacValue(-150.0f, 21.85f, -195.15f, 4095);
    TEST_ASSERT_TRUE(low > high);
}

void test_tempCToDacValue_customMaxDac(void) {
    // At setpoint with maxDac = 255 -> must return 255
    TEST_ASSERT_EQUAL_UINT16(255, conversions::tempCToDacValue(-195.15f, 21.85f, -195.15f, 255));
}

// ── Config sanity checks ─────────────────────────────────────────────────────

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
    TEST_ASSERT_TRUE(ADC_RESOLUTION >= 8);
    TEST_ASSERT_TRUE(ADC_RESOLUTION <= 12);
}

void test_config_setpoint_below_ambient(void) {
    TEST_ASSERT_TRUE(SETPOINT_C < AMBIENT_START_C);
}

void test_config_coarse_fine_threshold_between_setpoint_and_ambient(void) {
    TEST_ASSERT_TRUE(COARSE_FINE_THRESHOLD_C > SETPOINT_C);
    TEST_ASSERT_TRUE(COARSE_FINE_THRESHOLD_C < AMBIENT_START_C);
}

void test_config_rms_limit_positive(void) {
    TEST_ASSERT_TRUE(RMS_MAX_VOLTAGE_VDC > 0.0f);
}

void test_config_stall_min_drop_positive(void) {
    TEST_ASSERT_TRUE(STALL_MIN_DROP_C > 0.0f);
}

void test_config_temp_history_size_at_least_two(void) {
    TEST_ASSERT_TRUE(TEMP_HISTORY_SIZE >= 2);
}

// ── Entry point ───────────────────────────────────────────────────────────────

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
    RUN_TEST(test_kelvinToCelsius_absoluteZero);
    RUN_TEST(test_kelvinToCelsius_freezing);
    RUN_TEST(test_kelvinToCelsius_boiling);
    RUN_TEST(test_kelvinToCelsius_bodyTemp);
    RUN_TEST(test_kelvinToCelsius_negative);
    RUN_TEST(test_kelvinToCelsius_liquidNitrogen);
    RUN_TEST(test_fahrenheitToCelsius_freezing);
    RUN_TEST(test_fahrenheitToCelsius_boiling);
    RUN_TEST(test_fahrenheitToCelsius_liquidNitrogen);
    RUN_TEST(test_celsius_fahrenheit_roundTrip);

    // tempCToDacValue
    RUN_TEST(test_tempCToDacValue_aboveAmbient);
    RUN_TEST(test_tempCToDacValue_atSetpoint);
    RUN_TEST(test_tempCToDacValue_midpoint);
    RUN_TEST(test_tempCToDacValue_quarterPoint);
    RUN_TEST(test_tempCToDacValue_proportionalIncrease);
    RUN_TEST(test_tempCToDacValue_customMaxDac);

    // Config sanity
    RUN_TEST(test_config_rref_positive);
    RUN_TEST(test_config_rnominal_positive);
    RUN_TEST(test_config_frequency_positive);
    RUN_TEST(test_config_interval_positive);
    RUN_TEST(test_config_adc_resolution_range);
    RUN_TEST(test_config_setpoint_below_ambient);
    RUN_TEST(test_config_coarse_fine_threshold_between_setpoint_and_ambient);
    RUN_TEST(test_config_rms_limit_positive);
    RUN_TEST(test_config_stall_min_drop_positive);
    RUN_TEST(test_config_temp_history_size_at_least_two);

    return UNITY_END();
}
