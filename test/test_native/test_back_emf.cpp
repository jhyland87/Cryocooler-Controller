/**
 * @file test_back_emf.cpp
 * @brief Native unit tests for the back-EMF estimate and overstroke detector.
 *
 * This file has no main().  It exposes run_back_emf_tests(), which is called
 * from test_state_machine.cpp::main() so all native tests share one binary.
 *
 * Run with:  pio test -e native
 */

#include <math.h>
#include <unity.h>

#include "back_emf.h"

using back_emf::CoilModel;
using back_emf::Detector;
using back_emf::DetectorConfig;
using back_emf::Reading;
using back_emf::Trip;
using back_emf::estimateVrms;

static const CoilModel kCoil{3.5f, 0.0025f};   // 60 Hz reactance = 0.94248 ohm
static const float kFrequencyHz = 60.0f;
static const float kMinCurrentA = 0.3f;

// 500 ms smoothing, 10 s baseline, 5 s settle, 2 s hold-off.
static DetectorConfig makeConfig(float limitVrms, float impedanceDropFraction) {
    return DetectorConfig{limitVrms, impedanceDropFraction, 500u, 10000u, 5000u, 2000u};
}

/** Feeds the same reading every 100 ms and returns the last trip seen. */
static Trip feed(Detector& detector, float backEmfVrms, float impedanceOhm,
                 uint32_t& nowMs, uint32_t durationMs) {
    Trip last = Trip::None;
    for (uint32_t elapsedMs = 0; elapsedMs < durationMs; elapsedMs += 100u) {
        nowMs += 100u;
        const Trip trip = detector.update(backEmfVrms, impedanceOhm, nowMs);
        if (trip != Trip::None) { last = trip; }
    }
    return last;
}

// ── estimateVrms ─────────────────────────────────────────────────────────────

void test_back_emf_zero_for_stalled_coil(void) {
    // A coil with no motion is just R + jwL: V = 2 A * (3.5 + j0.94248) ohm.
    const Reading reading{7.2493f, 2.0f, 14.0f, true};
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, estimateVrms(reading, kCoil, kFrequencyHz, kMinCurrentA));
}

void test_back_emf_in_phase_with_current(void) {
    // E = 20 V in phase with 2 A: V = 27 + j1.88496, P = 54 W.
    const Reading reading{27.0657f, 2.0f, 54.0f, true};
    TEST_ASSERT_FLOAT_WITHIN(0.02f, 20.0f, estimateVrms(reading, kCoil, kFrequencyHz, kMinCurrentA));
}

void test_back_emf_with_leading_current(void) {
    // E = 10 - j5 V at 2 A: V = 17 - j3.11504, P = 34 W, current leads.
    const Reading reading{17.2831f, 2.0f, 34.0f, false};
    TEST_ASSERT_FLOAT_WITHIN(0.02f, 11.1803f, estimateVrms(reading, kCoil, kFrequencyHz, kMinCurrentA));
}

void test_back_emf_ignores_power_sign(void) {
    // Swapping J11 / J12 flips the sign of real power only.
    const Reading reading{27.0657f, 2.0f, -54.0f, true};
    TEST_ASSERT_FLOAT_WITHIN(0.02f, 20.0f, estimateVrms(reading, kCoil, kFrequencyHz, kMinCurrentA));
}

void test_back_emf_clamps_power_above_apparent(void) {
    const CoilModel noCoil{0.0f, 0.0f};
    const Reading reading{10.0f, 1.0f, 10.5f, true};
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 10.0f, estimateVrms(reading, noCoil, kFrequencyHz, kMinCurrentA));
}

void test_back_emf_nan_below_min_current(void) {
    const Reading reading{27.0f, 0.29f, 5.0f, true};
    TEST_ASSERT_TRUE(isnan(estimateVrms(reading, kCoil, kFrequencyHz, kMinCurrentA)));
}

void test_back_emf_nan_for_missing_reading(void) {
    TEST_ASSERT_TRUE(isnan(estimateVrms(Reading{NAN, 2.0f, 54.0f, true}, kCoil, kFrequencyHz, kMinCurrentA)));
    TEST_ASSERT_TRUE(isnan(estimateVrms(Reading{27.0f, NAN, 54.0f, true}, kCoil, kFrequencyHz, kMinCurrentA)));
    TEST_ASSERT_TRUE(isnan(estimateVrms(Reading{27.0f, 2.0f, NAN, true}, kCoil, kFrequencyHz, kMinCurrentA)));
    TEST_ASSERT_TRUE(isnan(estimateVrms(Reading{27.0f, 2.0f, 54.0f, true}, kCoil, 0.0f, kMinCurrentA)));
}

// ── Detector: back-EMF limit ─────────────────────────────────────────────────

void test_detector_no_trip_when_disabled(void) {
    Detector detector(makeConfig(0.0f, 0.0f));
    uint32_t nowMs = 0;
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None),
                      static_cast<int>(feed(detector, 500.0f, 1.0f, nowMs, 10000u)));
}

void test_detector_no_trip_below_limit(void) {
    Detector detector(makeConfig(50.0f, 0.0f));
    uint32_t nowMs = 0;
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None),
                      static_cast<int>(feed(detector, 49.0f, 20.0f, nowMs, 10000u)));
}

void test_detector_trips_above_limit(void) {
    Detector detector(makeConfig(50.0f, 0.0f));
    uint32_t nowMs = 0;
    feed(detector, 40.0f, 20.0f, nowMs, 2000u);
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::BackEmfLimit),
                      static_cast<int>(feed(detector, 60.0f, 20.0f, nowMs, 2000u)));
}

void test_detector_ignores_single_spike(void) {
    Detector detector(makeConfig(50.0f, 0.0f));
    uint32_t nowMs = 0;
    feed(detector, 40.0f, 20.0f, nowMs, 2000u);
    nowMs += 20u;
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None),
                      static_cast<int>(detector.update(80.0f, 20.0f, nowMs)));
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None),
                      static_cast<int>(feed(detector, 40.0f, 20.0f, nowMs, 2000u)));
}

void test_detector_holdoff_spaces_trips(void) {
    Detector detector(makeConfig(50.0f, 0.0f));
    uint32_t nowMs = 0;
    uint8_t tripCount = 0;
    // 60 V from the first reading: trips at once, then once per 2 s hold-off.
    for (uint32_t step = 0; step < 50u; ++step) {
        nowMs += 100u;
        if (detector.update(60.0f, 20.0f, nowMs) != Trip::None) { ++tripCount; }
    }
    TEST_ASSERT_EQUAL_UINT8(3, tripCount);
}

void test_detector_missing_reading_resets_filter(void) {
    Detector detector(makeConfig(50.0f, 0.0f));
    uint32_t nowMs = 0;
    feed(detector, 40.0f, 20.0f, nowMs, 1000u);
    nowMs += 100u;
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None),
                      static_cast<int>(detector.update(NAN, NAN, nowMs)));
    TEST_ASSERT_TRUE(isnan(detector.smoothedVrms()));
}

void test_detector_test_limit_only_lowers(void) {
    Detector detector(makeConfig(50.0f, 0.0f));
    detector.setTestLimitVrms(80.0f);
    TEST_ASSERT_EQUAL_FLOAT(50.0f, detector.effectiveLimitVrms());
    detector.setTestLimitVrms(10.0f);
    TEST_ASSERT_EQUAL_FLOAT(10.0f, detector.effectiveLimitVrms());
    detector.setTestLimitVrms(0.0f);
    TEST_ASSERT_EQUAL_FLOAT(50.0f, detector.effectiveLimitVrms());
}

void test_detector_test_limit_enables_disabled_check(void) {
    Detector detector(makeConfig(0.0f, 0.0f));
    detector.setTestLimitVrms(10.0f);
    uint32_t nowMs = 0;
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::BackEmfLimit),
                      static_cast<int>(feed(detector, 12.0f, 20.0f, nowMs, 2000u)));
}

// ── Detector: impedance drop ─────────────────────────────────────────────────

void test_detector_trips_on_impedance_drop(void) {
    Detector detector(makeConfig(0.0f, 0.2f));
    uint32_t nowMs = 0;
    feed(detector, 40.0f, 20.0f, nowMs, 10000u);
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::ImpedanceDrop),
                      static_cast<int>(feed(detector, 40.0f, 14.0f, nowMs, 2000u)));
}

void test_detector_impedance_drop_waits_for_baseline(void) {
    Detector detector(makeConfig(0.0f, 0.2f));
    uint32_t nowMs = 0;
    feed(detector, 40.0f, 20.0f, nowMs, 1000u);
    // Still inside the 5 s settle time.
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None),
                      static_cast<int>(feed(detector, 40.0f, 14.0f, nowMs, 2000u)));
}

void test_detector_slow_impedance_drift_does_not_trip(void) {
    Detector detector(makeConfig(0.0f, 0.2f));
    uint32_t nowMs = 0;
    feed(detector, 40.0f, 20.0f, nowMs, 10000u);
    // 20 -> 14 ohm over 120 s: the baseline follows.
    Trip seen = Trip::None;
    for (uint32_t step = 0; step < 1200u; ++step) {
        nowMs += 100u;
        const float impedanceOhm = 20.0f - 6.0f * static_cast<float>(step) / 1200.0f;
        const Trip trip = detector.update(40.0f, impedanceOhm, nowMs);
        if (trip != Trip::None) { seen = trip; }
    }
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None), static_cast<int>(seen));
}

void test_detector_small_impedance_drop_does_not_trip(void) {
    Detector detector(makeConfig(0.0f, 0.2f));
    uint32_t nowMs = 0;
    feed(detector, 40.0f, 20.0f, nowMs, 10000u);
    TEST_ASSERT_EQUAL(static_cast<int>(Trip::None),
                      static_cast<int>(feed(detector, 40.0f, 17.0f, nowMs, 2000u)));
}

void run_back_emf_tests() {
    RUN_TEST(test_back_emf_zero_for_stalled_coil);
    RUN_TEST(test_back_emf_in_phase_with_current);
    RUN_TEST(test_back_emf_with_leading_current);
    RUN_TEST(test_back_emf_ignores_power_sign);
    RUN_TEST(test_back_emf_clamps_power_above_apparent);
    RUN_TEST(test_back_emf_nan_below_min_current);
    RUN_TEST(test_back_emf_nan_for_missing_reading);
    RUN_TEST(test_detector_no_trip_when_disabled);
    RUN_TEST(test_detector_no_trip_below_limit);
    RUN_TEST(test_detector_trips_above_limit);
    RUN_TEST(test_detector_ignores_single_spike);
    RUN_TEST(test_detector_holdoff_spaces_trips);
    RUN_TEST(test_detector_missing_reading_resets_filter);
    RUN_TEST(test_detector_test_limit_only_lowers);
    RUN_TEST(test_detector_test_limit_enables_disabled_check);
    RUN_TEST(test_detector_trips_on_impedance_drop);
    RUN_TEST(test_detector_impedance_drop_waits_for_baseline);
    RUN_TEST(test_detector_slow_impedance_drift_does_not_trip);
    RUN_TEST(test_detector_small_impedance_drop_does_not_trip);
}
