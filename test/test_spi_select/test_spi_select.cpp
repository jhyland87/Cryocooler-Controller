/**
 * @file test_spi_select.cpp
 * @brief Native unit tests for the SN74LVC138A chip-select logic.
 *
 * Run with:  pio test -e native -f test_spi_select
 */

#include <unity.h>

#include <vector>

#include "spi_select.h"

struct PinWrite {
    uint8_t pin;
    uint8_t level;
};

static std::vector<PinWrite> sWrites;
static uint8_t sSelected;

static void writePin(uint8_t pin, uint8_t level) { sWrites.push_back({pin, level}); }

void setUp(void) {
    sWrites.clear();
    sSelected = spi_select::NO_OUTPUT_SELECTED;
}

void tearDown(void) {}

void test_ids_are_distinct_from_gpios_and_fit_int8(void) {
    TEST_ASSERT_FALSE(spi_select::isChipSelectId(48));
    TEST_ASSERT_FALSE(spi_select::isChipSelectId(97));  // Arduino's RGB_BUILTIN alias
    TEST_ASSERT_TRUE(spi_select::isChipSelectId(CS_ID_BASE));
    TEST_ASSERT_TRUE(spi_select::isChipSelectId(CS_ID_BASE + 7));
    TEST_ASSERT_FALSE(spi_select::isChipSelectId(CS_ID_BASE + 8));
    TEST_ASSERT_LESS_OR_EQUAL(127, CS_ID_BASE + 7);  // Adafruit BusIO stores CS as int8_t
}

void test_ids_match_the_schematic_outputs(void) {
    TEST_ASSERT_EQUAL(0, AD9833_CS - CS_ID_BASE);
    TEST_ASSERT_EQUAL(1, AD5453_SYNC - CS_ID_BASE);
    TEST_ASSERT_EQUAL(2, INA239_CS - CS_ID_BASE);
    TEST_ASSERT_EQUAL(3, EXPANDER_CS_PIN - CS_ID_BASE);
    TEST_ASSERT_EQUAL(4, DISP_CS_PIN - CS_ID_BASE);
    TEST_ASSERT_EQUAL(5, TOUCH_CS_PIN - CS_ID_BASE);
    TEST_ASSERT_EQUAL(6, ADS1220_CS - CS_ID_BASE);
    TEST_ASSERT_EQUAL(7, LSM6DSOX_CS - CS_ID_BASE);
}

void test_select_sets_address_while_disabled(void) {
    spi_select::applyChipSelect(ADS1220_CS, 0, sSelected, writePin);  // Y6: C=1 B=1 A=0
    const PinWrite expected[] = {{CS_ENABLE_PIN, 1},
                                 {CS_ADDR_A_PIN, 0},
                                 {CS_ADDR_B_PIN, 1},
                                 {CS_ADDR_C_PIN, 1},
                                 {CS_ENABLE_PIN, 0}};
    TEST_ASSERT_EQUAL(5, sWrites.size());
    for (size_t index = 0; index < 5; ++index) {
        TEST_ASSERT_EQUAL(expected[index].pin, sWrites[index].pin);
        TEST_ASSERT_EQUAL(expected[index].level, sWrites[index].level);
    }
    TEST_ASSERT_EQUAL(6, sSelected);
}

void test_deselect_only_disables(void) {
    spi_select::applyChipSelect(LSM6DSOX_CS, 0, sSelected, writePin);
    sWrites.clear();
    spi_select::applyChipSelect(LSM6DSOX_CS, 1, sSelected, writePin);
    TEST_ASSERT_EQUAL(1, sWrites.size());
    TEST_ASSERT_EQUAL(CS_ENABLE_PIN, sWrites[0].pin);
    TEST_ASSERT_EQUAL(1, sWrites[0].level);
    TEST_ASSERT_EQUAL(spi_select::NO_OUTPUT_SELECTED, sSelected);
}

void test_deselecting_another_output_leaves_the_selection(void) {
    spi_select::applyChipSelect(AD9833_CS, 0, sSelected, writePin);
    sWrites.clear();
    spi_select::applyChipSelect(DISP_CS_PIN, 1, sSelected, writePin);
    TEST_ASSERT_EQUAL(0, sWrites.size());
    TEST_ASSERT_EQUAL(0, sSelected);
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_ids_are_distinct_from_gpios_and_fit_int8);
    RUN_TEST(test_ids_match_the_schematic_outputs);
    RUN_TEST(test_select_sets_address_while_disabled);
    RUN_TEST(test_deselect_only_disables);
    RUN_TEST(test_deselecting_another_output_leaves_the_selection);
    return UNITY_END();
}
