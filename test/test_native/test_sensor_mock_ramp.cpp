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
 */

#include <unity.h>
#include "sensor_mock.h"

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
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 300.0f, sensor_mock::get().tempK);
}

// After half the expected duration, value should be ~halfway
void test_ramp_temp_midpoint() {
    resetMock();
    // 300 K -> 77 K at 5 K/min: full duration = (300-77)/5 = 44.6 min
    // At t = 22.3 min = 1 338 000 ms, value should be ~188.5 K
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    sensor_mock::service(1338000);   // 22.3 minutes
    const float expected = 300.0f - 5.0f * 22.3f;   // ~188.5 K
    TEST_ASSERT_FLOAT_WITHIN(0.5f, expected, sensor_mock::get().tempK);
}

// After the full duration the value should be clamped to endVal
void test_ramp_temp_clamps_to_end_value() {
    resetMock();
    // 300 -> 77 at 5 K/min: done after 44.6 min = 2 676 000 ms
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    sensor_mock::service(3000000);   // well past the end
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 77.0f, sensor_mock::get().tempK);
}

// After ramp completes the RampSpec should be marked inactive
void test_ramp_deactivates_when_complete() {
    resetMock();
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    sensor_mock::service(3000000);
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Temp).active);
}

// Upward ramp (warming) should increase the value
void test_ramp_upward_increases_value() {
    resetMock();
    // 77 -> 300 at 10 K/min: at t = 5 min = 300 000 ms expect ~127 K
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 77.0f, 300.0f, 10.0f, 0);
    sensor_mock::service(300000);
    const float expected = 77.0f + 10.0f * 5.0f;   // 127 K
    TEST_ASSERT_FLOAT_WITHIN(0.5f, expected, sensor_mock::get().tempK);
}

// Temp ramp should auto-derive a positive coolingRate when cooling (downward)
void test_ramp_temp_sets_cooling_rate_positive_when_cooling() {
    resetMock();
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    sensor_mock::service(60000);   // 1 minute in
    // coolingRate should be +5 K/min (positive = stage getting colder)
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 5.0f, sensor_mock::get().coolingRate);
}

// Temp ramp should auto-derive a negative coolingRate when warming (upward)
void test_ramp_temp_sets_cooling_rate_negative_when_warming() {
    resetMock();
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 77.0f, 300.0f, 5.0f, 0);
    sensor_mock::service(60000);
    // coolingRate should be -5 K/min (negative = stage warming up)
    TEST_ASSERT_FLOAT_WITHIN(0.01f, -5.0f, sensor_mock::get().coolingRate);
}

// RMS ramp should update rmsVoltage
void test_ramp_rms_advances_correctly() {
    resetMock();
    // 0 -> 1.5 V at 0.5 V/min: at t = 1 min expect 0.5 V
    sensor_mock::startRamp(sensor_mock::RampField::Rms, 0.0f, 1.5f, 0.5f, 0);
    sensor_mock::service(60000);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.5f, sensor_mock::get().rmsVoltage);
}

// Voltage ramp should update voltage
void test_ramp_voltage_advances_correctly() {
    resetMock();
    // 24 -> 10 V at 2 V/min: at t = 3 min expect 18 V
    sensor_mock::startRamp(sensor_mock::RampField::Voltage, 24.0f, 10.0f, 2.0f, 0);
    sensor_mock::service(180000);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 18.0f, sensor_mock::get().voltage);
}

// stopRamp freezes the current value at whatever it was
void test_stop_ramp_freezes_value() {
    resetMock();
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    sensor_mock::service(60000);   // 1 minute: now ~295 K
    const float frozen = sensor_mock::get().tempK;
    sensor_mock::stopRamp(sensor_mock::RampField::Temp);
    sensor_mock::service(120000);  // advance time further
    // Value should not have changed after stop
    TEST_ASSERT_FLOAT_WITHIN(0.001f, frozen, sensor_mock::get().tempK);
}

// After stopRamp the ramp is marked inactive
void test_stop_ramp_marks_inactive() {
    resetMock();
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    sensor_mock::stopRamp(sensor_mock::RampField::Temp);
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Temp).active);
}

// stopAllRamps cancels every field
void test_stop_all_ramps() {
    resetMock();
    sensor_mock::startRamp(sensor_mock::RampField::Temp,    300.0f, 77.0f,  5.0f, 0);
    sensor_mock::startRamp(sensor_mock::RampField::Rms,     0.0f,   1.5f,   0.1f, 0);
    sensor_mock::startRamp(sensor_mock::RampField::Voltage, 24.0f,  10.0f,  1.0f, 0);
    sensor_mock::stopAllRamps();
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Temp).active);
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Rms).active);
    TEST_ASSERT_FALSE(sensor_mock::getRamp(sensor_mock::RampField::Voltage).active);
}

// service() is a no-op when mock mode is inactive
void test_service_no_op_when_inactive() {
    resetMock();
    sensor_mock::disable();
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f, 5.0f, 0);
    sensor_mock::service(600000);   // 10 minutes
    // Value should remain at startVal since service is gated on isActive()
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 300.0f, sensor_mock::get().tempK);
}

// Calling startRamp twice replaces the previous ramp
void test_start_ramp_replaces_previous() {
    resetMock();
    sensor_mock::enable();
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 300.0f, 77.0f,  5.0f, 0);
    // Replace with a new ramp starting at 200 K, at t = 30 000 ms
    sensor_mock::startRamp(sensor_mock::RampField::Temp, 200.0f, 77.0f, 10.0f, 30000);
    sensor_mock::service(90000);   // 60 s after the new ramp started
    const float expected = 200.0f - 10.0f * 1.0f;  // 190 K (1 minute elapsed)
    TEST_ASSERT_FLOAT_WITHIN(0.5f, expected, sensor_mock::get().tempK);
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
