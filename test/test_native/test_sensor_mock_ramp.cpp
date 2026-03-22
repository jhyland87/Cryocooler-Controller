/**
 * @file test_sensor_mock_ramp.cpp
 * @brief Unit tests for sensor_mock ramp subsystem.
 *
 * Verifies that:
 *  - startRamp() snaps the override to the start value immediately.
 *  - service() advances the override value linearly with time.
 *  - service() clamps to endVal and deactivates the ramp when done.
 *  - Downward ramps (e.g. cooling) work correctly.
 *  - Temp ramp auto-derives coolingRate.
 *  - stopRamp() freezes the current value without a jump.
 *  - stopAllRamps() cancels every ramp.
 *  - A static `mock temp` value (after stopRamp) is not overwritten.
 *
 * Run with:  pio test -e native
 *
 * All temperature values are in Celsius.
 */

#include <unity.h>
#include "sensor_mock.h"
#include "tick.h"

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Reset all mock state between tests. Enables mock mode — ramps only advance when active. */
static void resetMock() {
    sensor_mock::stopAllRamps();
    sensor_mock::get() = sensor_mock::Overrides{};  // reset to safe defaults
    sensor_mock::enable();
}

// ─── Tests ────────────────────────────────────────────────────────────────────

// startRamp snaps to startVal immediately
void test_ramp_start_snaps_to_start_value() {
    resetMock();
    // 26.85 °C (≈ room temp) → -196.15 °C (≈ liquid nitrogen) at 5 °C/min
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 26.85f, sensor_mock::get().tempC);
}

// After half the expected duration, value should be ~halfway
void test_ramp_temp_midpoint() {
    resetMock();
    // 26.85 °C -> -196.15 °C at 5 °C/min: full duration = (26.85 - (-196.15))/5 = 44.6 min
    // At t = 22.3 min = 1 338 000 ms, value should be ~26.85 - 5*22.3 = -84.65 °C
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    tick::setNowMs(1338000);
    sensor_mock::service();   // 22.3 minutes
    const float expected = 26.85f - 5.0f * 22.3f;   // ~-84.65 °C
    TEST_ASSERT_FLOAT_WITHIN(0.5f, expected, sensor_mock::get().tempC);
}

// After the full duration the value should be clamped to endVal
void test_ramp_temp_clamps_to_end_value() {
    resetMock();
    // 26.85 -> -196.15 at 5 °C/min: done after 44.6 min = 2 676 000 ms
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    tick::setNowMs(3000000);
    sensor_mock::service();   // well past the end
    TEST_ASSERT_FLOAT_WITHIN(0.001f, -196.15f, sensor_mock::get().tempC);
}

// After ramp completes the RampSpec should be marked inactive
void test_ramp_deactivates_when_complete() {
    resetMock();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    tick::setNowMs(3000000);
    sensor_mock::service();
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Temp).active);
}

// Upward ramp (warming) should increase the value
void test_ramp_upward_increases_value() {
    resetMock();
    // -196.15 -> 26.85 at 10 °C/min: at t = 5 min = 300 000 ms expect ~-146.15 °C
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, -196.15f, 26.85f, 10.0f);
    tick::setNowMs(300000);
    sensor_mock::service();
    const float expected = -196.15f + 10.0f * 5.0f;   // -146.15 °C
    TEST_ASSERT_FLOAT_WITHIN(0.5f, expected, sensor_mock::get().tempC);
}

// Temp ramp should auto-derive a positive coolingRate when cooling (downward)
void test_ramp_temp_sets_cooling_rate_positive_when_cooling() {
    resetMock();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    tick::setNowMs(60000);
    sensor_mock::service();   // 1 minute in
    // coolingRate should be +5 °C/min (positive = stage getting colder)
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 5.0f, sensor_mock::get().coolingRate);
}

// Temp ramp should auto-derive a negative coolingRate when warming (upward)
void test_ramp_temp_sets_cooling_rate_negative_when_warming() {
    resetMock();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, -196.15f, 26.85f, 5.0f);
    tick::setNowMs(60000);
    sensor_mock::service();
    // coolingRate should be -5 °C/min (negative = stage warming up)
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -5.0f, sensor_mock::get().coolingRate);
}

// RMS ramp should update rmsVoltage
void test_ramp_rms_advances_correctly() {
    resetMock();
    // 0 -> 1.5 V at 0.5 V/min: at t = 1 min expect 0.5 V
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Rms, 0.0f, 1.5f, 0.5f);
    tick::setNowMs(60000);
    sensor_mock::service();
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.5f, sensor_mock::get().rmsVoltageV);
}

// Voltage ramp should update voltage
void test_ramp_voltage_advances_correctly() {
    resetMock();
    // 24 -> 10 V at 2 V/min: at t = 3 min expect 18 V
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Voltage, 24.0f, 10.0f, 2.0f);
    tick::setNowMs(180000);
    sensor_mock::service();
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 18.0f, sensor_mock::get().voltage);
}

// stopRamp freezes the current value at whatever it was
void test_stop_ramp_freezes_value() {
    resetMock();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    tick::setNowMs(60000);
    sensor_mock::service();   // 1 minute: now ~21.85 °C
    const float frozen = sensor_mock::get().tempC;
    sensor_mock::stopRamp(sensor_mock::RampField::Temp);
    tick::setNowMs(120000);
    sensor_mock::service();  // advance time further
    // Value should not have changed after stop
    TEST_ASSERT_FLOAT_WITHIN(0.001f, frozen, sensor_mock::get().tempC);
}

// After stopRamp the ramp is marked inactive
void test_stop_ramp_marks_inactive() {
    resetMock();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    sensor_mock::stopRamp(sensor_mock::RampField::Temp);
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Temp).active);
}

// stopAllRamps cancels every field
void test_stop_all_ramps() {
    resetMock();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp,    26.85f,  -196.15f, 5.0f);
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Rms,     0.0f,      1.5f,  0.1f);
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Voltage, 24.0f,    10.0f,  1.0f);
    sensor_mock::stopAllRamps();
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Temp).active);
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Rms).active);
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Voltage).active);
}

// service() is a no-op when mock mode is inactive
void test_service_no_op_when_inactive() {
    resetMock();
    sensor_mock::disable();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f, 5.0f);
    tick::setNowMs(600000);
    sensor_mock::service();   // 10 minutes
    // Value should remain at startVal since service is gated on isActive()
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 26.85f, sensor_mock::get().tempC);
}

// Calling startRamp twice replaces the previous ramp
void test_start_ramp_replaces_previous() {
    resetMock();
    sensor_mock::enable();
    tick::setNowMs(0);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 26.85f, -196.15f,  5.0f);
    // Replace with a new ramp starting at -73.15 °C, at t = 30 000 ms
    tick::setNowMs(30000);
    sensor_mock::startRamp(sensor_mock::RampField::Temp, -73.15f, -196.15f, 10.0f);
    tick::setNowMs(90000);
    sensor_mock::service();   // 60 s after the new ramp started
    const float expected = -73.15f - 10.0f * 1.0f;  // -83.15 °C (1 minute elapsed)
    TEST_ASSERT_FLOAT_WITHIN(0.5f, expected, sensor_mock::get().tempC);
}

// ─── Entry point ──────────────────────────────────────────────────────────────

void run_sensor_mock_ramp_tests() {
    RUN_TEST(test_ramp_start_snaps_to_start_value);
    RUN_TEST(test_ramp_temp_midpoint);
    RUN_TEST(test_ramp_temp_clamps_to_end_value);
    RUN_TEST(test_ramp_deactivates_when_complete);
    RUN_TEST(test_ramp_upward_increases_value);
    RUN_TEST(test_ramp_temp_sets_cooling_rate_positive_when_cooling);
    RUN_TEST(test_ramp_temp_sets_cooling_rate_negative_when_warming);
    RUN_TEST(test_ramp_rms_advances_correctly);
    RUN_TEST(test_ramp_voltage_advances_correctly);
    RUN_TEST(test_stop_ramp_freezes_value);
    RUN_TEST(test_stop_ramp_marks_inactive);
    RUN_TEST(test_stop_all_ramps);
    RUN_TEST(test_service_no_op_when_inactive);
    RUN_TEST(test_start_ramp_replaces_previous);
}
