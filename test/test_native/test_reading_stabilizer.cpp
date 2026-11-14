/**
 * @file test_reading_stabilizer.cpp
 * @brief Native unit tests for ReadingStabilizer (settling of first sensor readings).
 *
 * This file has no main().  It exposes run_reading_stabilizer_tests(), which is
 * called from test_state_machine.cpp::main() so all native tests share one binary.
 *
 * Run with:  pio test -e native
 */

#include <unity.h>
#include "reading_stabilizer.h"

void test_rs_starts_unstable(void) {
    ReadingStabilizer settled(3, 0.5f);
    TEST_ASSERT_FALSE(settled.isStable());
}

void test_rs_stable_after_required_agreeing_readings(void) {
    ReadingStabilizer settled(3, 0.5f);
    TEST_ASSERT_FALSE(settled.update(20.6f));
    TEST_ASSERT_FALSE(settled.update(20.7f));
    TEST_ASSERT_TRUE(settled.update(20.6f));
    TEST_ASSERT_TRUE(settled.isStable());
}

void test_rs_climbing_start_is_held_back(void) {
    // A reading that ramps up from zero must not count until it flattens out.
    ReadingStabilizer settled(3, 0.5f);
    const float ramp[] = {0.0f, 6.0f, 13.0f, 18.5f, 20.4f};
    for (float reading : ramp) {
        TEST_ASSERT_FALSE(settled.update(reading));
    }
    TEST_ASSERT_FALSE(settled.update(20.6f));
    TEST_ASSERT_TRUE(settled.update(20.6f));
}

void test_rs_jump_restarts_the_run(void) {
    ReadingStabilizer settled(3, 0.5f);
    settled.update(20.0f);
    settled.update(20.1f);
    TEST_ASSERT_FALSE(settled.update(25.0f));  // would have been the third
    TEST_ASSERT_FALSE(settled.update(25.1f));
    TEST_ASSERT_TRUE(settled.update(25.0f));
}

void test_rs_stays_stable_through_a_later_jump(void) {
    ReadingStabilizer settled(2, 0.5f);
    settled.update(20.0f);
    settled.update(20.0f);
    TEST_ASSERT_TRUE(settled.update(-50.0f));
    TEST_ASSERT_TRUE(settled.isStable());
}

void test_rs_reset_requires_settling_again(void) {
    ReadingStabilizer settled(2, 0.5f);
    settled.update(20.0f);
    settled.update(20.0f);
    settled.reset();
    TEST_ASSERT_FALSE(settled.isStable());
    TEST_ASSERT_FALSE(settled.update(20.0f));
    TEST_ASSERT_TRUE(settled.update(20.0f));
}

void test_rs_force_stable(void) {
    ReadingStabilizer settled(5, 0.5f);
    settled.forceStable();
    TEST_ASSERT_TRUE(settled.isStable());
}

void test_rs_single_reading_requirement(void) {
    ReadingStabilizer settled(1, 0.5f);
    TEST_ASSERT_TRUE(settled.update(20.0f));
}

void run_reading_stabilizer_tests() {
    RUN_TEST(test_rs_starts_unstable);
    RUN_TEST(test_rs_stable_after_required_agreeing_readings);
    RUN_TEST(test_rs_climbing_start_is_held_back);
    RUN_TEST(test_rs_jump_restarts_the_run);
    RUN_TEST(test_rs_stays_stable_through_a_later_jump);
    RUN_TEST(test_rs_reset_requires_settling_again);
    RUN_TEST(test_rs_force_stable);
    RUN_TEST(test_rs_single_reading_requirement);
}
