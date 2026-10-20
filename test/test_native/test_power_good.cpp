/**
 * @file test_power_good.cpp
 * @brief Native unit tests for PowerGoodMonitor (debounced power-good changes).
 *
 * This file has no main().  It exposes run_power_good_tests(), which is called
 * from test_state_machine.cpp::main() so all native tests share one binary.
 *
 * Run with:  pio test -e native
 */

#include <unity.h>
#include "power_good.h"

using Event = PowerGoodMonitor::Event;

void test_pg_begin_raises_no_event(void) {
    PowerGoodMonitor monitor(50);
    monitor.begin(true, 1000);
    TEST_ASSERT_TRUE(monitor.isGood());
    TEST_ASSERT_EQUAL_UINT32(0, monitor.changeCount());
    TEST_ASSERT_EQUAL(Event::None, monitor.update(true, 1100));
}

void test_pg_loss_reported_after_debounce(void) {
    PowerGoodMonitor monitor(50);
    monitor.begin(true, 0);
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 100));  // first differing sample
    TEST_ASSERT_TRUE(monitor.isGood());
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 140));  // 40 ms: still debouncing
    TEST_ASSERT_EQUAL(Event::Lost, monitor.update(false, 150));  // 50 ms: confirmed
    TEST_ASSERT_FALSE(monitor.isGood());
    TEST_ASSERT_EQUAL_UINT32(1, monitor.changeCount());
}

void test_pg_loss_reported_only_once(void) {
    PowerGoodMonitor monitor(0);
    monitor.begin(true, 0);
    TEST_ASSERT_EQUAL(Event::Lost, monitor.update(false, 10));
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 20));
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 30));
    TEST_ASSERT_EQUAL_UINT32(1, monitor.changeCount());
}

void test_pg_glitch_shorter_than_debounce_ignored(void) {
    PowerGoodMonitor monitor(50);
    monitor.begin(true, 0);
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 100));
    TEST_ASSERT_EQUAL(Event::None, monitor.update(true, 120));   // back before 50 ms
    TEST_ASSERT_EQUAL(Event::None, monitor.update(true, 400));
    TEST_ASSERT_TRUE(monitor.isGood());
    TEST_ASSERT_EQUAL_UINT32(0, monitor.changeCount());
}

void test_pg_glitch_restarts_the_debounce_timer(void) {
    PowerGoodMonitor monitor(50);
    monitor.begin(true, 0);
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 100));
    TEST_ASSERT_EQUAL(Event::None, monitor.update(true, 130));   // glitch ends
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 140));  // new attempt starts at 140
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 180));
    TEST_ASSERT_EQUAL(Event::Lost, monitor.update(false, 190));
}

void test_pg_restore_reports_outage_length(void) {
    PowerGoodMonitor monitor(50);
    monitor.begin(true, 0);
    monitor.update(false, 1000);
    TEST_ASSERT_EQUAL(Event::Lost, monitor.update(false, 1050));
    monitor.update(true, 3000);
    TEST_ASSERT_EQUAL(Event::Restored, monitor.update(true, 3050));
    TEST_ASSERT_TRUE(monitor.isGood());
    // dated from the first differing samples: 3000 - 1000
    TEST_ASSERT_EQUAL_UINT32(2000, monitor.lastOutageMs());
    TEST_ASSERT_EQUAL_UINT32(2, monitor.changeCount());
    TEST_ASSERT_EQUAL_UINT32(3000, monitor.lastChangeMs());
}

void test_pg_starts_bad_then_restores(void) {
    PowerGoodMonitor monitor(50);
    monitor.begin(false, 0);
    TEST_ASSERT_FALSE(monitor.isGood());
    monitor.update(true, 500);
    TEST_ASSERT_EQUAL(Event::Restored, monitor.update(true, 550));
    TEST_ASSERT_EQUAL_UINT32(500, monitor.lastOutageMs());
}

void test_pg_millis_wraparound(void) {
    PowerGoodMonitor monitor(50);
    monitor.begin(true, 0xFFFFFF00u);
    TEST_ASSERT_EQUAL(Event::None, monitor.update(false, 0xFFFFFFF0u));
    TEST_ASSERT_EQUAL(Event::Lost, monitor.update(false, 0x00000040u));  // 80 ms later, past the wrap
}

void run_power_good_tests() {
    RUN_TEST(test_pg_begin_raises_no_event);
    RUN_TEST(test_pg_loss_reported_after_debounce);
    RUN_TEST(test_pg_loss_reported_only_once);
    RUN_TEST(test_pg_glitch_shorter_than_debounce_ignored);
    RUN_TEST(test_pg_glitch_restarts_the_debounce_timer);
    RUN_TEST(test_pg_restore_reports_outage_length);
    RUN_TEST(test_pg_starts_bad_then_restores);
    RUN_TEST(test_pg_millis_wraparound);
}
