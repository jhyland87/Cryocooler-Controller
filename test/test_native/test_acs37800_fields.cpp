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

using acs37800::decodePowerFactor;

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

void run_acs37800_fields_tests() {
    RUN_TEST(test_power_factor_zero);
    RUN_TEST(test_power_factor_positive);
    RUN_TEST(test_power_factor_negative);
    RUN_TEST(test_power_factor_ignores_neighbouring_fields);
}
