/**
 * @file test_acs37800_fields.cpp
 * @brief Native unit tests for the ACS37800 register field decoders.
 *
 * This file has no main().  It exposes run_acs37800_fields_tests(), which is
 * called from test_state_machine.cpp::main() so all native tests share one binary.
 *
 * Run with:  pio test -e native
 */

#include <unity.h>

#include "ACS37800_fields.h"

using acs37800::decodeCurrentLagging;
using acs37800::decodePowerFactor;
using acs37800::isBusIdleWord;

void test_power_factor_zero(void) {
    TEST_ASSERT_EQUAL_FLOAT(0.0f, decodePowerFactor(0x00000000u));
}

void test_power_factor_positive(void) {
    TEST_ASSERT_EQUAL_FLOAT(0.5f, decodePowerFactor(0x200u << 16));
    TEST_ASSERT_EQUAL_FLOAT(1023.0f / 1024.0f, decodePowerFactor(0x3FFu << 16));
}

void test_power_factor_negative(void) {
    TEST_ASSERT_EQUAL_FLOAT(-0.5f, decodePowerFactor(0x600u << 16));
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, decodePowerFactor(0x400u << 16));
}

void test_power_factor_ignores_neighbouring_fields(void) {
    // PAPPARENT (15:0), POSANGLE (27), POSPF (28) and the unused top bits all set.
    TEST_ASSERT_EQUAL_FLOAT(0.5f, decodePowerFactor(0xF800FFFFu | (0x200u << 16)));
}

void test_current_lagging_reads_bit_27(void) {
    TEST_ASSERT_TRUE(decodeCurrentLagging(1UL << 27));
    TEST_ASSERT_FALSE(decodeCurrentLagging(0x00000000u));
    // Every other bit set: PAPPARENT, PFACTOR, POSPF.
    TEST_ASSERT_FALSE(decodeCurrentLagging(~(1UL << 27)));
}

void test_bus_idle_word_is_all_ones_only(void) {
    TEST_ASSERT_TRUE(isBusIdleWord(0xFFFFFFFFu));
    TEST_ASSERT_FALSE(isBusIdleWord(0x00000000u));
    // Full-scale voltage alone is a real reading.
    TEST_ASSERT_FALSE(isBusIdleWord(0x0000FFFFu));
}

void run_acs37800_fields_tests() {
    RUN_TEST(test_power_factor_zero);
    RUN_TEST(test_power_factor_positive);
    RUN_TEST(test_power_factor_negative);
    RUN_TEST(test_power_factor_ignores_neighbouring_fields);
    RUN_TEST(test_current_lagging_reads_bit_27);
    RUN_TEST(test_bus_idle_word_is_all_ones_only);
}
