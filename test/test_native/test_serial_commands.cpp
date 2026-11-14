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
#include "cooling.h"
#include "config.h"
#include "tick.h"
#include "wifi_credentials.h"
#include "dashboard.h"
#include "wifi_stub.h"

extern "C" void stub_setMillis(uint32_t ms);

// ---------------------------------------------------------------------------
// Test helper: reset all state before each serial command test.
// ---------------------------------------------------------------------------

static void resetAll() {
    stub_setMillis(0);
    tick::setNowMs(0); state_machine::init();
    serial_commands::init();
    telemetry::enable();  // always start with telemetry on
    cooling::disable();   // reset fan speed and enabled state
    wifi_stub::reset();
}

// ---------------------------------------------------------------------------
// Dispatch / parsing
// ---------------------------------------------------------------------------

void test_sc_empty_line_produces_no_output() {
    resetAll();
    Print output;
    serial_commands::processLine("", output);
    TEST_ASSERT_EQUAL_UINT32(0, output.length());
}

void test_sc_whitespace_only_produces_no_output() {
    resetAll();
    Print output;
    serial_commands::processLine("   \t  ", output);
    TEST_ASSERT_EQUAL_UINT32(0, output.length());
}

void test_sc_unknown_command_returns_error() {
    resetAll();
    Print output;
    serial_commands::processLine("frobniculate", output);
    TEST_ASSERT_TRUE(output.contains("[ERR]"));
}

void test_sc_command_with_leading_whitespace() {
    resetAll();
    Print output;
    serial_commands::processLine("  status", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
}

void test_sc_command_with_trailing_garbage_still_matches() {
    // Parser only matches on the first token, so "status blah" == "status".
    resetAll();
    Print output;
    serial_commands::processLine("status blah blah", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
}

// ---------------------------------------------------------------------------
// start
// ---------------------------------------------------------------------------

void test_sc_start_from_off_succeeds() {
    resetAll();
    Print output;
    serial_commands::processLine("start", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_start_from_idle_succeeds() {
    resetAll();
    tick::setNowMs(100); state_machine::start();    // → CoarseCooldown
    tick::setNowMs(200); state_machine::stop();     // → Shutdown (not Idle directly)
    // Advance through the Shutdown duration so the state machine reaches Idle.
    const uint32_t tIdle = 200 + SHUTDOWN_DURATION_MS;
    stub_setMillis(tIdle);
    tick::setNowMs(tIdle);
    state_machine::update(295.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));
    Print output;
    stub_setMillis(tIdle + 100);
    serial_commands::processLine("start", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_start_when_already_running_returns_error() {
    resetAll();
    tick::setNowMs(100); state_machine::start();  // already running
    Print output;
    serial_commands::processLine("start", output);
    TEST_ASSERT_TRUE(output.contains("[ERR]"));
    // State must not change.
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

// ---------------------------------------------------------------------------
// stop
// ---------------------------------------------------------------------------

void test_sc_stop_when_running_succeeds() {
    resetAll();
    tick::setNowMs(100); state_machine::start();
    stub_setMillis(200);
    tick::setNowMs(200);
    Print output;
    serial_commands::processLine("stop", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_FALSE(state_machine::isRunning());
    // stop() enters Shutdown first; Idle is only reached after SHUTDOWN_DURATION_MS.
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_stop_when_not_running_returns_error() {
    resetAll();  // Off, not running
    Print output;
    serial_commands::processLine("stop", output);
    TEST_ASSERT_TRUE(output.contains("[ERR]"));
}

// ---------------------------------------------------------------------------
// off
// ---------------------------------------------------------------------------

void test_sc_off_from_running_succeeds() {
    resetAll();
    tick::setNowMs(100); state_machine::start();
    stub_setMillis(200);
    tick::setNowMs(200);
    Print output;
    serial_commands::processLine("off", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_off_from_idle_succeeds() {
    resetAll();
    tick::setNowMs(100); state_machine::start();
    tick::setNowMs(200); state_machine::stop();   // → Shutdown
    Print output;
    stub_setMillis(300);
    tick::setNowMs(300);
    serial_commands::processLine("off", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_sc_off_when_already_off_returns_error() {
    resetAll();  // starts in Off
    Print output;
    serial_commands::processLine("off", output);
    TEST_ASSERT_TRUE(output.contains("[ERR]"));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

// ---------------------------------------------------------------------------
// status
// ---------------------------------------------------------------------------

void test_sc_status_returns_ok() {
    resetAll();
    Print output;
    serial_commands::processLine("status", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
}

void test_sc_status_contains_state_name() {
    resetAll();
    Print output;
    serial_commands::processLine("status", output);
    // In Off state the state name is "Off"
    TEST_ASSERT_TRUE(output.contains("Off"));
}

void test_sc_status_shows_running_yes_when_running() {
    resetAll();
    tick::setNowMs(100); state_machine::start();
    Print output;
    serial_commands::processLine("status", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_TRUE(output.contains("yes"));
}

void test_sc_status_shows_running_no_when_stopped() {
    resetAll();
    Print output;
    serial_commands::processLine("status", output);
    TEST_ASSERT_TRUE(output.contains("no"));
}

// ---------------------------------------------------------------------------
// help
// ---------------------------------------------------------------------------

void test_sc_help_lists_all_commands() {
    resetAll();
    Print output;
    serial_commands::processLine("help", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_TRUE(output.contains("start"));
    TEST_ASSERT_TRUE(output.contains("stop"));
    TEST_ASSERT_TRUE(output.contains("off"));
    TEST_ASSERT_TRUE(output.contains("status"));
    TEST_ASSERT_TRUE(output.contains("board"));
    TEST_ASSERT_TRUE(output.contains("help"));
}

// ---------------------------------------------------------------------------
// board
// ---------------------------------------------------------------------------

void test_sc_board_returns_ok() {
    resetAll();
    Print output;
    serial_commands::processLine("board", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
}

// ---------------------------------------------------------------------------
// summary
// ---------------------------------------------------------------------------

void test_sc_summary_returns_ok() {
    resetAll();
    Print output;
    serial_commands::processLine("summary", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
}

void test_sc_summary_contains_state_name() {
    resetAll();
    Print output;
    serial_commands::processLine("summary", output);
    // In Off state the machine reports "Off"
    TEST_ASSERT_TRUE(output.contains("Off"));
}

void test_sc_summary_shows_running_status() {
    resetAll();
    tick::setNowMs(100); state_machine::start();
    Print output;
    serial_commands::processLine("summary", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_TRUE(output.contains("yes"));  // running: yes
}

void test_sc_help_lists_summary() {
    resetAll();
    Print output;
    serial_commands::processLine("help", output);
    TEST_ASSERT_TRUE(output.contains("summary"));
}

// ---------------------------------------------------------------------------
// telemetry on / off
// ---------------------------------------------------------------------------

void test_sc_telemetry_off_disables() {
    resetAll();
    TEST_ASSERT_TRUE(telemetry::isEnabled());
    Print output;
    serial_commands::processLine("telemetry off", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_FALSE(telemetry::isEnabled());
}

void test_sc_telemetry_on_enables() {
    resetAll();
    telemetry::disable();  // start disabled
    Print output;
    serial_commands::processLine("telemetry on", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_TRUE(telemetry::isEnabled());
}

void test_sc_telemetry_off_idempotent() {
    // Disabling twice should not error.
    resetAll();
    Print output;
    serial_commands::processLine("telemetry off", output);
    output.reset();
    serial_commands::processLine("telemetry off", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_FALSE(telemetry::isEnabled());
}

// ---------------------------------------------------------------------------
// telemetry serial on / off
// ---------------------------------------------------------------------------

void test_sc_telemetry_serial_on_enables() {
    resetAll();
    telemetry::disableSerial();
    Print output;
    serial_commands::processLine("telemetry serial on", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_TRUE(telemetry::isSerialEnabled());
    // Must not be swallowed by the shorter "telemetry on" command.
    TEST_ASSERT_TRUE(telemetry::isEnabled());
}

void test_sc_telemetry_serial_off_disables() {
    resetAll();
    telemetry::enableSerial();
    Print output;
    serial_commands::processLine("telemetry serial off", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_FALSE(telemetry::isSerialEnabled());
}

// ---------------------------------------------------------------------------
// cooling fan <N>
// ---------------------------------------------------------------------------

void test_sc_cooling_fan_sets_speed() {
    resetAll();
    Print output;
    serial_commands::processLine("cooling fan 40%", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_EQUAL_UINT8(40u, cooling::getFanSpeed());
}

void test_sc_cooling_fan_zero_turns_off_fan() {
    resetAll();
    cooling::setFanSpeed(75);  // pre-set non-zero
    Print output;
    serial_commands::processLine("cooling fan 0%", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_EQUAL_UINT8(0u, cooling::getFanSpeed());
}

void test_sc_cooling_fan_100_percent() {
    resetAll();
    Print output;
    serial_commands::processLine("cooling fan 100%", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    TEST_ASSERT_EQUAL_UINT8(100u, cooling::getFanSpeed());
}

void test_sc_cooling_fan_no_arg_returns_error() {
    resetAll();
    Print output;
    serial_commands::processLine("cooling fan", output);
    TEST_ASSERT_TRUE(output.contains("[ERR]"));
}

void test_sc_cooling_fan_out_of_range_returns_error() {
    resetAll();
    Print output;
    serial_commands::processLine("cooling fan 101%", output);
    TEST_ASSERT_TRUE(output.contains("[ERR]"));
    // Fan speed must not have changed.
    TEST_ASSERT_EQUAL_UINT8(0u, cooling::getFanSpeed());
}

void test_sc_cooling_fan_non_numeric_returns_error() {
    resetAll();
    Print output;
    serial_commands::processLine("cooling fan abc", output);
    TEST_ASSERT_TRUE(output.contains("[ERR]"));
    TEST_ASSERT_EQUAL_UINT8(0u, cooling::getFanSpeed());
}

void test_sc_cooling_fan_does_not_match_cooling_on() {
    // Sending "cooling fan 50%" must not accidentally trigger "cooling on".
    resetAll();
    Print output;
    serial_commands::processLine("cooling fan 50%", output);
    TEST_ASSERT_TRUE(output.contains("[OK]"));
    // cooling::enable() sets the pump on; it should NOT have been called.
    TEST_ASSERT_FALSE(cooling::isCoolingPumpOn());
    TEST_ASSERT_EQUAL_UINT8(50u, cooling::getFanSpeed());
}

// ---------------------------------------------------------------------------
// wifi credentials
// ---------------------------------------------------------------------------

void test_sc_wifi_set_echo_hides_network_name() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi set MyNetwork", p);
    TEST_ASSERT_TRUE(p.contains("wifi set <hidden>"));
    TEST_ASSERT_FALSE(p.contains("MyNetwork"));
}

void test_sc_wifi_set_saves_and_requests_reconnect() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi set My Network  ", p);
    TEST_ASSERT_FALSE(wifi_stub::hasSaved());  // nothing saved until the passphrase arrives
    serial_commands::processLine("correct horse", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_EQUAL_STRING("My Network", wifi_stub::savedSsid());  // spaces kept, trailing trimmed
    TEST_ASSERT_EQUAL_STRING("correct horse", wifi_stub::savedPassphrase());
    TEST_ASSERT_TRUE(wifi_stub::reloadRequested());
}

void test_sc_wifi_passphrase_never_printed() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi set MyNetwork", p);
    serial_commands::processLine("hunter2hunter2", p);
    TEST_ASSERT_FALSE(p.contains("hunter2"));
    TEST_ASSERT_FALSE(p.contains("MyNetwork"));
}

void test_sc_wifi_passphrase_is_not_run_as_a_command() {
    resetAll();
    state_machine::init();
    Print p;
    serial_commands::processLine("wifi set MyNetwork", p);
    serial_commands::processLine("start now please", p);
    TEST_ASSERT_FALSE(state_machine::isRunning());
    TEST_ASSERT_EQUAL_STRING("start now please", wifi_stub::savedPassphrase());
}

void test_sc_wifi_set_open_network() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi set Guest", p);
    serial_commands::processLine("open", p);
    TEST_ASSERT_TRUE(wifi_stub::hasSaved());
    TEST_ASSERT_EQUAL_STRING("", wifi_stub::savedPassphrase());
}

void test_sc_wifi_set_short_passphrase_saves_nothing() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi set MyNetwork", p);
    serial_commands::processLine("short", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
    TEST_ASSERT_FALSE(p.contains("short\n"));
    TEST_ASSERT_FALSE(wifi_stub::hasSaved());
    TEST_ASSERT_FALSE(wifi_stub::reloadRequested());

    // The prompt is over: the next line is an ordinary command again.
    p.reset();
    serial_commands::processLine("status", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
}

void test_sc_wifi_set_rejects_bad_ssid() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi set", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
    p.reset();
    serial_commands::processLine("wifi set 123456789012345678901234567890123", p);  // 33
    TEST_ASSERT_TRUE(p.contains("[ERR]"));

    // No prompt was opened, so this is a command, not a passphrase.
    p.reset();
    serial_commands::processLine("status", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_FALSE(wifi_stub::hasSaved());
}

void test_sc_wifi_set_times_out() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi set MyNetwork", p);
    stub_setMillis(60000);
    serial_commands::processLine("status", p);
    TEST_ASSERT_TRUE(p.contains("timed out"));
    TEST_ASSERT_TRUE(p.contains("Received > status"));
    TEST_ASSERT_FALSE(wifi_stub::hasSaved());
}

void test_sc_wifi_set_reports_flash_failure() {
    resetAll();
    wifi_stub::setSaveFails(true);
    Print p;
    serial_commands::processLine("wifi set MyNetwork", p);
    serial_commands::processLine("hunter2hunter2", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
    TEST_ASSERT_FALSE(wifi_stub::reloadRequested());
}

void test_sc_wifi_forget_erases_and_reloads() {
    resetAll();
    wifi_credentials::save("MyNetwork", "hunter2hunter2");
    Print p;
    serial_commands::processLine("wifi forget", p);
    TEST_ASSERT_TRUE(p.contains("[OK]"));
    TEST_ASSERT_FALSE(wifi_stub::hasSaved());
    TEST_ASSERT_TRUE(wifi_stub::reloadRequested());
}

void test_sc_wifi_on_off_do_not_touch_the_boot_setting() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi off", p);
    TEST_ASSERT_FALSE(dashboard::isWifiEnabled());
    TEST_ASSERT_TRUE(wifi_stub::onBoot());
    serial_commands::processLine("wifi on", p);
    TEST_ASSERT_TRUE(dashboard::isWifiEnabled());
}

void test_sc_wifi_onboot_accepts_each_spelling() {
    static const char* const offWords[] = {"false", "0", "off", "FALSE", "Off"};
    static const char* const onWords[]  = {"true", "1", "on", "TRUE", "On"};
    char line[32];
    for (size_t wordIndex = 0; wordIndex < 5; ++wordIndex) {
        resetAll();
        Print p;
        snprintf(line, sizeof(line), "wifi onboot %s", offWords[wordIndex]);
        serial_commands::processLine(line, p);
        TEST_ASSERT_FALSE_MESSAGE(wifi_stub::onBoot(), line);
        snprintf(line, sizeof(line), "wifi onboot %s", onWords[wordIndex]);
        serial_commands::processLine(line, p);
        TEST_ASSERT_TRUE_MESSAGE(wifi_stub::onBoot(), line);
        TEST_ASSERT_TRUE(dashboard::isWifiEnabled());  // the running state is untouched
    }
}

void test_sc_wifi_onboot_rejects_other_words() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi onboot maybe", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
    TEST_ASSERT_TRUE(wifi_stub::onBoot());
}

void test_sc_wifi_onboot_without_argument_prints_setting() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi onboot off", p);
    p.reset();
    serial_commands::processLine("wifi onboot", p);
    TEST_ASSERT_TRUE(p.contains("on boot: off"));
}

void test_sc_wifi_scan_refused_while_off() {
    resetAll();
    Print p;
    serial_commands::processLine("wifi off", p);
    serial_commands::processLine("wifi scan", p);
    TEST_ASSERT_TRUE(p.contains("[ERR]"));
    TEST_ASSERT_FALSE(wifi_stub::scanRequested());

    serial_commands::processLine("wifi on", p);
    serial_commands::processLine("wifi scan", p);
    TEST_ASSERT_TRUE(wifi_stub::scanRequested());
}

void test_wifi_ssid_length_limits() {
    TEST_ASSERT_FALSE(wifi_credentials::isValidSsid(""));
    TEST_ASSERT_TRUE(wifi_credentials::isValidSsid("a"));
    TEST_ASSERT_TRUE(wifi_credentials::isValidSsid("12345678901234567890123456789012"));    // 32
    TEST_ASSERT_FALSE(wifi_credentials::isValidSsid("123456789012345678901234567890123"));  // 33
}

void test_wifi_passphrase_length_limits() {
    char passphrase[66];
    memset(passphrase, 'x', sizeof(passphrase));

    passphrase[0] = '\0';
    TEST_ASSERT_TRUE(wifi_credentials::isValidPassphrase(passphrase));   // open network
    memset(passphrase, 'x', sizeof(passphrase));
    passphrase[7] = '\0';
    TEST_ASSERT_FALSE(wifi_credentials::isValidPassphrase(passphrase));
    passphrase[7] = 'x';
    passphrase[8] = '\0';
    TEST_ASSERT_TRUE(wifi_credentials::isValidPassphrase(passphrase));
    passphrase[8]  = 'x';
    passphrase[64] = '\0';
    TEST_ASSERT_TRUE(wifi_credentials::isValidPassphrase(passphrase));
    passphrase[64] = 'x';
    passphrase[65] = '\0';
    TEST_ASSERT_FALSE(wifi_credentials::isValidPassphrase(passphrase));
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
    RUN_TEST(test_sc_help_lists_summary);

    // board
    RUN_TEST(test_sc_board_returns_ok);

    // summary
    RUN_TEST(test_sc_summary_returns_ok);
    RUN_TEST(test_sc_summary_contains_state_name);
    RUN_TEST(test_sc_summary_shows_running_status);

    // telemetry on / off
    RUN_TEST(test_sc_telemetry_off_disables);
    RUN_TEST(test_sc_telemetry_on_enables);
    RUN_TEST(test_sc_telemetry_off_idempotent);
    RUN_TEST(test_sc_telemetry_serial_on_enables);
    RUN_TEST(test_sc_telemetry_serial_off_disables);

    // cooling fan <N>
    RUN_TEST(test_sc_cooling_fan_sets_speed);
    RUN_TEST(test_sc_cooling_fan_zero_turns_off_fan);
    RUN_TEST(test_sc_cooling_fan_100_percent);
    RUN_TEST(test_sc_cooling_fan_no_arg_returns_error);
    RUN_TEST(test_sc_cooling_fan_out_of_range_returns_error);
    RUN_TEST(test_sc_cooling_fan_non_numeric_returns_error);
    RUN_TEST(test_sc_cooling_fan_does_not_match_cooling_on);

    // wifi credentials
    RUN_TEST(test_sc_wifi_set_echo_hides_network_name);
    RUN_TEST(test_sc_wifi_set_saves_and_requests_reconnect);
    RUN_TEST(test_sc_wifi_passphrase_never_printed);
    RUN_TEST(test_sc_wifi_passphrase_is_not_run_as_a_command);
    RUN_TEST(test_sc_wifi_set_open_network);
    RUN_TEST(test_sc_wifi_set_short_passphrase_saves_nothing);
    RUN_TEST(test_sc_wifi_set_rejects_bad_ssid);
    RUN_TEST(test_sc_wifi_set_times_out);
    RUN_TEST(test_sc_wifi_set_reports_flash_failure);
    RUN_TEST(test_sc_wifi_forget_erases_and_reloads);
    RUN_TEST(test_sc_wifi_on_off_do_not_touch_the_boot_setting);
    RUN_TEST(test_sc_wifi_onboot_accepts_each_spelling);
    RUN_TEST(test_sc_wifi_onboot_rejects_other_words);
    RUN_TEST(test_sc_wifi_onboot_without_argument_prints_setting);
    RUN_TEST(test_sc_wifi_scan_refused_while_off);
    RUN_TEST(test_wifi_ssid_length_limits);
    RUN_TEST(test_wifi_passphrase_length_limits);
}
