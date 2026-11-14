/**
 * @file test_session_table.cpp
 * @brief Native unit tests for SessionTable (dashboard login sessions).
 *
 * This file has no main().  It exposes run_session_table_tests(), which is
 * called from test_state_machine.cpp::main() so all native tests share one binary.
 *
 * Run with:  pio test -e native
 */

#include <unity.h>
#include "session_table.h"

static const int64_t EPOCH  = 1800000000;  // a set wall clock
static const int64_t UPTIME = 100;

/** A distinct hash per @p id. */
static const uint8_t* hashOf(uint8_t id) {
    static uint8_t hashes[16][SessionTable::HASH_BYTES];
    memset(hashes[id], 0, SessionTable::HASH_BYTES);
    hashes[id][0]                            = id;
    hashes[id][SessionTable::HASH_BYTES - 1] = static_cast<uint8_t>(id + 1);
    return hashes[id];
}

void test_st_unknown_session_is_refused(void) {
    SessionTable table;
    TEST_ASSERT_FALSE(table.contains(hashOf(1), EPOCH, UPTIME));
}

void test_st_temporary_session_expires_by_uptime(void) {
    SessionTable table;
    table.add(hashOf(1), false, UPTIME + 60);
    TEST_ASSERT_TRUE(table.contains(hashOf(1), EPOCH, UPTIME + 59));
    TEST_ASSERT_FALSE(table.contains(hashOf(1), EPOCH, UPTIME + 60));
    TEST_ASSERT_FALSE(table.contains(hashOf(1), EPOCH, UPTIME));  // gone for good
}

void test_st_remembered_session_expires_by_wall_clock(void) {
    SessionTable table;
    table.add(hashOf(1), true, EPOCH + 3600);
    TEST_ASSERT_TRUE(table.contains(hashOf(1), EPOCH + 3599, UPTIME));
    TEST_ASSERT_FALSE(table.contains(hashOf(1), EPOCH + 3600, UPTIME));
}

void test_st_remembered_session_stays_valid_without_a_clock(void) {
    SessionTable table;
    table.add(hashOf(1), true, EPOCH + 3600);
    TEST_ASSERT_TRUE(table.contains(hashOf(1), 0, UPTIME));
}

void test_st_a_hash_differing_in_one_byte_is_refused(void) {
    SessionTable table;
    table.add(hashOf(1), true, EPOCH + 3600);
    uint8_t nearly[SessionTable::HASH_BYTES];
    memcpy(nearly, hashOf(1), sizeof(nearly));
    nearly[17] ^= 0x01;
    TEST_ASSERT_FALSE(table.contains(nearly, EPOCH, UPTIME));
}

void test_st_full_kind_replaces_its_oldest(void) {
    SessionTable table;
    for (uint8_t id = 1; id <= SessionTable::SLOTS_PER_KIND; ++id) {
        table.add(hashOf(id), true, EPOCH + 3600);
    }
    table.add(hashOf(9), true, EPOCH + 3600);
    TEST_ASSERT_FALSE(table.contains(hashOf(1), EPOCH, UPTIME));  // the oldest went
    TEST_ASSERT_TRUE(table.contains(hashOf(2), EPOCH, UPTIME));
    TEST_ASSERT_TRUE(table.contains(hashOf(9), EPOCH, UPTIME));
    TEST_ASSERT_EQUAL_UINT(SessionTable::SLOTS_PER_KIND, table.count(true));
}

void test_st_kinds_do_not_evict_each_other(void) {
    SessionTable table;
    for (uint8_t id = 1; id <= SessionTable::SLOTS_PER_KIND; ++id) {
        table.add(hashOf(id), true, EPOCH + 3600);
    }
    for (uint8_t id = 5; id <= 4 + SessionTable::SLOTS_PER_KIND + 1; ++id) {
        table.add(hashOf(id), false, UPTIME + 60);  // one more than fits
    }
    for (uint8_t id = 1; id <= SessionTable::SLOTS_PER_KIND; ++id) {
        TEST_ASSERT_TRUE(table.contains(hashOf(id), EPOCH, UPTIME));
    }
    TEST_ASSERT_FALSE(table.contains(hashOf(5), EPOCH, UPTIME));
    TEST_ASSERT_EQUAL_UINT(SessionTable::SLOTS_PER_KIND, table.count(false));
}

void test_st_remove_ends_one_session(void) {
    SessionTable table;
    table.add(hashOf(1), true, EPOCH + 3600);
    table.add(hashOf(2), false, UPTIME + 60);
    TEST_ASSERT_TRUE(table.remove(hashOf(1)));    // remembered: the saved copy needs updating
    TEST_ASSERT_FALSE(table.remove(hashOf(2)));   // temporary: nothing saved
    TEST_ASSERT_FALSE(table.remove(hashOf(3)));   // unknown
    TEST_ASSERT_FALSE(table.contains(hashOf(1), EPOCH, UPTIME));
    TEST_ASSERT_FALSE(table.contains(hashOf(2), EPOCH, UPTIME));
}

void test_st_clear_ends_everything(void) {
    SessionTable table;
    table.add(hashOf(1), true, EPOCH + 3600);
    table.add(hashOf(2), false, UPTIME + 60);
    table.clear();
    TEST_ASSERT_FALSE(table.contains(hashOf(1), EPOCH, UPTIME));
    TEST_ASSERT_FALSE(table.contains(hashOf(2), EPOCH, UPTIME));
}

void test_st_copy_remembered_skips_temporary(void) {
    SessionTable table;
    table.add(hashOf(1), true, EPOCH + 3600);
    table.add(hashOf(2), false, UPTIME + 60);
    table.add(hashOf(3), true, EPOCH + 7200);
    SessionTable::Session saved[SessionTable::SLOTS_PER_KIND];
    TEST_ASSERT_EQUAL_UINT(2, table.copyRemembered(saved));
    TEST_ASSERT_EQUAL_INT64(EPOCH + 3600, saved[0].expires);
    TEST_ASSERT_EQUAL_INT64(EPOCH + 7200, saved[1].expires);
}

void run_session_table_tests() {
    RUN_TEST(test_st_unknown_session_is_refused);
    RUN_TEST(test_st_temporary_session_expires_by_uptime);
    RUN_TEST(test_st_remembered_session_expires_by_wall_clock);
    RUN_TEST(test_st_remembered_session_stays_valid_without_a_clock);
    RUN_TEST(test_st_a_hash_differing_in_one_byte_is_refused);
    RUN_TEST(test_st_full_kind_replaces_its_oldest);
    RUN_TEST(test_st_kinds_do_not_evict_each_other);
    RUN_TEST(test_st_remove_ends_one_session);
    RUN_TEST(test_st_clear_ends_everything);
    RUN_TEST(test_st_copy_remembered_skips_temporary);
}
