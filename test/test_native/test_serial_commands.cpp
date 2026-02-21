/**
 * @file test_serial_commands.cpp
 * @brief Unit tests for the custom serial command handler.
 *
 * Tests call processLine() directly with a stub Print so that responses
 * can be inspected without real hardware.  main() lives in test_state_machine.cpp
 * and calls run_serial_command_tests() defined at the bottom of this file.
 */

#include <unity.h>
#include <cstring>
#include "Print.h"
#include "serial_commands.h"
#include "state_machine.h"
#include "telemetry.h"

extern "C" void stub_setMillis(uint32_t ms);

// ---------------------------------------------------------------------------
// Test helper: reset all state before each serial command test.
// ---------------------------------------------------------------------------

static void resetAll() {
    stub_setMillis(0);
    state_machine::init(0);
    serial_commands::init();
    telemetry::enable();  // always start with telemetry on
}

// ---------------------------------------------------------------------------
// Dispatch / parsing
// ---------------------------------------------------------------------------

void test_sc_empty_line_produces_no_output() {
    resetAll();
    Print p;
    serial_commands::processLine("", p);
    TEST_ASSERT_EQUAL_UINT32(0, p.length());
}

void test_sc_whitespace_only_produces_no_output() {
    resetAll();
    Print p;
    serial_commands::processLine("   \t  ", p);
    TEST_ASSERT_EQUAL_UINT32(0, p.length());
}

void test_sc_unknown_command_returns_error() {
    resetAll();
    Print p;
    serial_commands::processLine("frobniculate", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
}

void test_sc_command_with_leading_whitespace() {
    resetAll();
    Print p;
    serial_commands::processLine("  status", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
}

void test_sc_command_with_trailing_garbage_still_matches() {
    // Parser only matches on the first token, so "status blah" == "status".
    resetAll();
    Print p;
    serial_commands::processLine("status blah blah", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
}

// ---------------------------------------------------------------------------
// start
// ---------------------------------------------------------------------------

void test_sc_start_from_off_succeeds() {
    resetAll();
    Print p;
    serial_commands::processLine("start", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_start_from_idle_succeeds() {
    resetAll();
    state_machine::start(100);    // CoarseCooldown
    state_machine::stop(200);     // → Idle
    Print p;
    stub_setMillis(300);
    serial_commands::processLine("start", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_start_when_already_running_returns_error() {
    resetAll();
    state_machine::start(100);  // already running
    Print p;
    serial_commands::processLine("start", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
    // State must not change.
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

// ---------------------------------------------------------------------------
// stop
// ---------------------------------------------------------------------------

void test_sc_stop_when_running_succeeds() {
    resetAll();
    state_machine::start(100);
    stub_setMillis(200);
    Print p;
    serial_commands::processLine("stop", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_FALSE(state_machine::isRunning());
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_stop_when_not_running_returns_error() {
    resetAll();  // Off, not running
    Print p;
    serial_commands::processLine("stop", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
}

// ---------------------------------------------------------------------------
// off
// ---------------------------------------------------------------------------

void test_sc_off_from_running_succeeds() {
    resetAll();
    state_machine::start(100);
    stub_setMillis(200);
    Print p;
    serial_commands::processLine("off", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_off_from_idle_succeeds() {
    resetAll();
    state_machine::start(100);
    state_machine::stop(200);   // → Idle
    Print p;
    stub_setMillis(300);
    serial_commands::processLine("off", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_off_when_already_off_returns_error() {
    resetAll();  // starts in Off
    Print p;
    serial_commands::processLine("off", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

// ---------------------------------------------------------------------------
// status
// ---------------------------------------------------------------------------

void test_sc_status_returns_ok() {
    resetAll();
    Print p;
    serial_commands::processLine("status", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
}

void test_sc_status_contains_state_name() {
    resetAll();
    Print p;
    serial_commands::processLine("status", p);
    // In Off state the state name is "Off"
    TEST_ASSERT_TRUE(p.contains("Off"));
}

void test_sc_status_shows_running_yes_when_running() {
    resetAll();
    state_machine::start(100);
    Print p;
    serial_commands::processLine("status", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_TRUE(p.contains("yes"));
}

void test_sc_status_shows_running_no_when_stopped() {
    resetAll();
    Print p;
    serial_commands::processLine("status", p);
    TEST_ASSERT_TRUE(p.contains("no"));
}

// ---------------------------------------------------------------------------
// help
// ---------------------------------------------------------------------------

void test_sc_help_lists_all_commands() {
    resetAll();
    Print p;
    serial_commands::processLine("help", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_TRUE(p.contains("start"));
    TEST_ASSERT_TRUE(p.contains("stop"));
    TEST_ASSERT_TRUE(p.contains("off"));
    TEST_ASSERT_TRUE(p.contains("status"));
    TEST_ASSERT_TRUE(p.contains("board"));
    TEST_ASSERT_TRUE(p.contains("help"));
}

// ---------------------------------------------------------------------------
// board
// ---------------------------------------------------------------------------

void test_sc_board_returns_ok() {
    resetAll();
    Print p;
    serial_commands::processLine("board", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
}

// ---------------------------------------------------------------------------
// telemetry on / off
// ---------------------------------------------------------------------------

void test_sc_telemetry_off_disables() {
    resetAll();
    TEST_ASSERT_TRUE(telemetry::isEnabled());
    Print p;
    serial_commands::processLine("telemetry off", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_FALSE(telemetry::isEnabled());
}

void test_sc_telemetry_on_enables() {
    resetAll();
    telemetry::disable();  // start disabled
    Print p;
    serial_commands::processLine("telemetry on", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_TRUE(telemetry::isEnabled());
}

void test_sc_telemetry_off_idempotent() {
    // Disabling twice should not error.
    resetAll();
    Print p;
    serial_commands::processLine("telemetry off", p);
    p.reset();
    serial_commands::processLine("telemetry off", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_FALSE(telemetry::isEnabled());
}

// ---------------------------------------------------------------------------
// Entry point called by the shared test runner in test_state_machine.cpp
// ---------------------------------------------------------------------------

void run_serial_command_tests() {
    // Dispatch / parsing
    RUN_TEST(test_sc_empty_line_produces_no_output);
    RUN_TEST(test_sc_whitespace_only_produces_no_output);
    RUN_TEST(test_sc_unknown_command_returns_error);
    RUN_TEST(test_sc_command_with_leading_whitespace);
    RUN_TEST(test_sc_command_with_trailing_garbage_still_matches);

    // start
    RUN_TEST(test_sc_start_from_off_succeeds);
    RUN_TEST(test_sc_start_from_idle_succeeds);
    RUN_TEST(test_sc_start_when_already_running_returns_error);

    // stop
    RUN_TEST(test_sc_stop_when_running_succeeds);
    RUN_TEST(test_sc_stop_when_not_running_returns_error);

    // off
    RUN_TEST(test_sc_off_from_running_succeeds);
    RUN_TEST(test_sc_off_from_idle_succeeds);
    RUN_TEST(test_sc_off_when_already_off_returns_error);

    // status
    RUN_TEST(test_sc_status_returns_ok);
    RUN_TEST(test_sc_status_contains_state_name);
    RUN_TEST(test_sc_status_shows_running_yes_when_running);
    RUN_TEST(test_sc_status_shows_running_no_when_stopped);

    // help
    RUN_TEST(test_sc_help_lists_all_commands);

    // board
    RUN_TEST(test_sc_board_returns_ok);

    // telemetry on / off
    RUN_TEST(test_sc_telemetry_off_disables);
    RUN_TEST(test_sc_telemetry_on_enables);
    RUN_TEST(test_sc_telemetry_off_idempotent);
}
