/**
 * @file test_dac.cpp
 * @brief Native unit tests for the MCP4921 DAC controller
 *
 * Tests the ramp rate limiting logic without hardware dependencies.
 * The DAC module can be tested on the host PC because it's pure logic
 * (no interrupt handlers, no blocking calls).
 *
 * Run with: pio test -e native
 */

#include <unity.h>
#include <cstdint>
#include "dac.h"
#include "config.h"

// Track SPI transfers for verification
extern uint16_t stub_getLastSpiTransfer(void);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Helper: Get the current DAC value after an update.
 * Since getCurrent() is public, we can call it directly.
 */
static uint16_t getDacValue(void) {
    return dac::getCurrent();
}

// ---------------------------------------------------------------------------
// setUp / tearDown
// ---------------------------------------------------------------------------

void setUp(void) {
    dac::init();  // Reset DAC to 0
}

void tearDown(void) {}

// ---------------------------------------------------------------------------
// Init and basic behavior
// ---------------------------------------------------------------------------

void test_dac_init_sets_output_to_zero(void) {
    dac::init();
    TEST_ASSERT_EQUAL_UINT16(0, dac::getCurrent());
}

void test_dac_update_sets_value_directly(void) {
    dac::update(2000);
    TEST_ASSERT_EQUAL_UINT16(2000, dac::getCurrent());
}

void test_dac_update_clamps_to_max_value(void) {
    dac::update(5000);  // Greater than MCP4921_MAX_VALUE (4095)
    TEST_ASSERT_EQUAL_UINT16(MCP4921_MAX_VALUE, dac::getCurrent());
}

// ---------------------------------------------------------------------------
// Normal ramp (rampToward with DAC_MAX_STEP_PER_INTERVAL)
// ---------------------------------------------------------------------------

void test_dac_ramp_up_small_step(void) {
    dac::init();
    // Current = 0, target = 100 (less than DAC_MAX_STEP_PER_INTERVAL = 5)
    // Should step by exactly 100 in one call
    dac::rampToward(100);
    TEST_ASSERT_EQUAL_UINT16(5, dac::getCurrent());  // Step limited to 5
}

void test_dac_ramp_up_respects_max_step(void) {
    dac::init();
    // Current = 0, target = 4095 (full scale)
    // Should only step by DAC_MAX_STEP_PER_INTERVAL
    dac::rampToward(4095);
    TEST_ASSERT_EQUAL_UINT16(DAC_MAX_STEP_PER_INTERVAL, dac::getCurrent());
}

void test_dac_ramp_down_respects_max_step(void) {
    dac::update(2000);  // Set to 2000
    dac::rampToward(0);
    // Should step down by DAC_MAX_STEP_PER_INTERVAL
    TEST_ASSERT_EQUAL_UINT16(2000 - DAC_MAX_STEP_PER_INTERVAL, dac::getCurrent());
}

void test_dac_ramp_reaches_exact_target(void) {
    dac::init();
    dac::update(10);  // Start at 10
    // Target is 12, which is less than step size
    // Should reach exactly 12 in one call
    dac::rampToward(12);
    TEST_ASSERT_EQUAL_UINT16(12, dac::getCurrent());
}

void test_dac_ramp_multiple_iterations_to_target(void) {
    dac::init();
    // Ramp from 0 to 50 with DAC_MAX_STEP_PER_INTERVAL = 5
    for (int i = 0; i < 10; ++i) {
        dac::rampToward(50);
        if (dac::getCurrent() == 50) break;
    }
    TEST_ASSERT_EQUAL_UINT16(50, dac::getCurrent());
}

void test_dac_ramp_stops_at_target(void) {
    dac::init();
    // Get to 100
    for (int i = 0; i < 25; ++i) {
        dac::rampToward(100);
    }
    TEST_ASSERT_EQUAL_UINT16(100, dac::getCurrent());

    // Continue calling with same target shouldn't change value
    const uint16_t before = dac::getCurrent();
    dac::rampToward(100);
    TEST_ASSERT_EQUAL_UINT16(before, dac::getCurrent());
}

// ---------------------------------------------------------------------------
// Fast ramp (rampTowardShutdown with DAC_SHUTDOWN_STEP_PER_INTERVAL)
// ---------------------------------------------------------------------------

void test_dac_shutdown_ramp_faster_than_normal(void) {
    // DAC_SHUTDOWN_STEP_PER_INTERVAL should be > DAC_MAX_STEP_PER_INTERVAL
    TEST_ASSERT_GREATER_THAN(DAC_MAX_STEP_PER_INTERVAL, DAC_SHUTDOWN_STEP_PER_INTERVAL);
}

void test_dac_shutdown_ramp_respects_max_step(void) {
    dac::update(2000);  // Set to 2000
    dac::rampTowardShutdown(0);
    // Should step down by DAC_SHUTDOWN_STEP_PER_INTERVAL
    TEST_ASSERT_EQUAL_UINT16(2000 - DAC_SHUTDOWN_STEP_PER_INTERVAL, dac::getCurrent());
}

void test_dac_shutdown_ramp_down_from_full_scale(void) {
    dac::update(MCP4921_MAX_VALUE);  // Start at full scale

    // Calculate how many iterations needed to reach 0
    uint32_t iterations = 0;
    uint16_t current = MCP4921_MAX_VALUE;
    while (current > 0 && iterations < 100) {
        dac::rampTowardShutdown(0);
        current = dac::getCurrent();
        iterations++;
    }

    TEST_ASSERT_EQUAL_UINT16(0, dac::getCurrent());
    // Verify it was reasonably fast (should be ~20 iterations for shutdown)
    // vs ~820 iterations for normal ramp
    TEST_ASSERT_LESS_THAN(50, iterations);
}

void test_dac_shutdown_reaches_exact_target(void) {
    dac::update(250);
    // Target is 200, step size is much larger than 50
    // Should reach exactly 200 in one call
    dac::rampTowardShutdown(200);
    TEST_ASSERT_EQUAL_UINT16(200, dac::getCurrent());
}

void test_dac_shutdown_ramp_stops_at_target(void) {
    dac::update(500);
    dac::rampTowardShutdown(0);
    dac::rampTowardShutdown(0);  // Call again
    TEST_ASSERT_EQUAL_UINT16(0, dac::getCurrent());

    dac::rampTowardShutdown(0);  // And again
    TEST_ASSERT_EQUAL_UINT16(0, dac::getCurrent());
}

// ---------------------------------------------------------------------------
// Comparison: Normal vs Shutdown ramp rates
// ---------------------------------------------------------------------------

void test_dac_shutdown_ramps_faster_than_normal(void) {
    // Test scenario: ramp from 2000 to 0
    // After one iteration, shutdown should have moved further toward target

    // Normal ramp
    dac::update(2000);
    dac::rampToward(0);
    const uint16_t normalAfterOne = dac::getCurrent();

    // Shutdown ramp
    dac::update(2000);
    dac::rampTowardShutdown(0);
    const uint16_t shutdownAfterOne = dac::getCurrent();

    // Shutdown should be closer to 0 (lower value)
    TEST_ASSERT_LESS_THAN(normalAfterOne, shutdownAfterOne);
}

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

void test_dac_ramp_with_zero_target_from_zero(void) {
    dac::init();
    dac::rampToward(0);
    TEST_ASSERT_EQUAL_UINT16(0, dac::getCurrent());
}

void test_dac_ramp_with_max_target(void) {
    dac::init();
    // Ramp all the way to max
    for (int i = 0; i < 1000; ++i) {
        dac::rampToward(MCP4921_MAX_VALUE);
        if (dac::getCurrent() == MCP4921_MAX_VALUE) break;
    }
    TEST_ASSERT_EQUAL_UINT16(MCP4921_MAX_VALUE, dac::getCurrent());
}

void test_dac_oversized_target_gets_clamped(void) {
    dac::init();
    dac::rampToward(10000);  // Way over max
    // Should ramp toward clamped value (MCP4921_MAX_VALUE)
    for (int i = 0; i < 1000; ++i) {
        dac::rampToward(10000);
        if (dac::getCurrent() == MCP4921_MAX_VALUE) break;
    }
    TEST_ASSERT_EQUAL_UINT16(MCP4921_MAX_VALUE, dac::getCurrent());
}

void test_dac_bidirectional_ramp(void) {
    dac::update(1000);
    dac::rampToward(1500);
    TEST_ASSERT_EQUAL_UINT16(1000 + DAC_MAX_STEP_PER_INTERVAL, dac::getCurrent());

    dac::rampToward(500);
    TEST_ASSERT_LESS_THAN(1000 + DAC_MAX_STEP_PER_INTERVAL, dac::getCurrent());
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

int main(void) {
    UNITY_BEGIN();

    // Init and basic
    RUN_TEST(test_dac_init_sets_output_to_zero);
    RUN_TEST(test_dac_update_sets_value_directly);
    RUN_TEST(test_dac_update_clamps_to_max_value);

    // Normal ramp behavior
    RUN_TEST(test_dac_ramp_up_small_step);
    RUN_TEST(test_dac_ramp_up_respects_max_step);
    RUN_TEST(test_dac_ramp_down_respects_max_step);
    RUN_TEST(test_dac_ramp_reaches_exact_target);
    RUN_TEST(test_dac_ramp_multiple_iterations_to_target);
    RUN_TEST(test_dac_ramp_stops_at_target);

    // Shutdown ramp behavior
    RUN_TEST(test_dac_shutdown_ramp_faster_than_normal);
    RUN_TEST(test_dac_shutdown_ramp_respects_max_step);
    RUN_TEST(test_dac_shutdown_ramp_down_from_full_scale);
    RUN_TEST(test_dac_shutdown_reaches_exact_target);
    RUN_TEST(test_dac_shutdown_ramp_stops_at_target);

    // Comparison
    RUN_TEST(test_dac_shutdown_ramps_faster_than_normal);

    // Edge cases
    RUN_TEST(test_dac_ramp_with_zero_target_from_zero);
    RUN_TEST(test_dac_ramp_with_max_target);
    RUN_TEST(test_dac_oversized_target_gets_clamped);
    RUN_TEST(test_dac_bidirectional_ramp);

    return UNITY_END();
}
