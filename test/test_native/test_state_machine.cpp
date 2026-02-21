/**
 * @file test_state_machine.cpp
 * @brief Native unit tests for the cryocooler state machine
 *
 * The state machine has no hardware dependencies so it compiles cleanly on
 * the host PC.  Tests inject synthetic temperature / RMS values and verify
 * that the correct transitions, DAC targets, relay states, and indicator
 * modes are produced.
 *
 * Run with:  pio test -e native
 */

#include <cstring>
#include <unity.h>
#include "state_machine.h"
#include "indicator.h"
#include "config.h"

// Stub millis() control (provided by stubs/arduino_stub.cpp)
extern "C" void stub_setMillis(uint32_t ms);

// Serial command tests (defined in test_serial_commands.cpp)
void run_serial_command_tests();

// ---------------------------------------------------------------------------
// Helper: fast-forward the state machine by skipping time
// ---------------------------------------------------------------------------

/**
 * Repeatedly call update() with a fixed set of inputs, advancing nowMs by
 * @p stepMs on each call, until the state machine reaches @p target or
 * @p maxMs of simulated time has elapsed.
 *
 * @return  Final nowMs value when the target state was first observed,
 *          or 0 if the state was never reached within maxMs.
 */
static uint32_t advanceUntil(state_machine::State  target,
                              float    tempK,
                              float    coolingRate,
                              float    rmsV,
                              bool     stalled,
                              uint32_t startMs,
                              uint32_t stepMs,
                              uint32_t maxMs)
{
    uint32_t nowMs = startMs;
    while (nowMs < (startMs + maxMs)) {
        stub_setMillis(nowMs);
        auto out = state_machine::update(tempK, coolingRate, rmsV, stalled, nowMs);
        if (out.state == target) return nowMs;
        nowMs += stepMs;
    }
    return 0;  // did not reach target
}

/**
 * Helper: init the state machine (enters Off), then call start() to enter
 * CoarseCooldown.
 *
 * @return  The nowMs timestamp at which CoarseCooldown was entered.
 */
static uint32_t initAndStart() {
    state_machine::init(0);
    const uint32_t tStart = 100;
    stub_setMillis(tStart);
    state_machine::start(tStart);
    return tStart;
}

/**
 * Helper: init, start, then stop — ending in Idle.
 *
 * @return  The nowMs timestamp at which Idle was entered.
 */
static uint32_t initStartAndStop() {
    const uint32_t tStart = initAndStart();
    const uint32_t tStop  = tStart + 1000;
    state_machine::stop(tStop);
    return tStop;
}

// ---------------------------------------------------------------------------
// setUp / tearDown
// ---------------------------------------------------------------------------

void setUp(void) {
    stub_setMillis(0);
    state_machine::init(0);
}

void tearDown(void) {}

// ---------------------------------------------------------------------------
// State: Off (initial state after init)
// ---------------------------------------------------------------------------

void test_init_starts_in_off(void) {
    state_machine::init(0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_off_output_is_bypass_indicators_off(void) {
    state_machine::init(0);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, 0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_TRUE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
    TEST_ASSERT_NOT_NULL(out.statusText);
}

void test_off_stays_in_off(void) {
    state_machine::init(0);
    // Even after a long time, stays in Off without start()
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, 60000);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

// ---------------------------------------------------------------------------
// State: Idle -- reached via stop() from a running state
// ---------------------------------------------------------------------------

void test_idle_output_is_fault_red_bypass(void) {
    const uint32_t tStop = initStartAndStop();
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, tStop + 1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_TRUE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidRed),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

void test_idle_does_not_auto_transition(void) {
    const uint32_t tStop = initStartAndStop();
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, tStop + 60000);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

// ---------------------------------------------------------------------------
// start() / stop() / off() control
// ---------------------------------------------------------------------------

void test_start_from_off_enters_coarse(void) {
    state_machine::init(0);
    state_machine::start(100);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_TRUE(state_machine::isRunning());
}

void test_start_from_idle_enters_coarse(void) {
    const uint32_t tStop = initStartAndStop();
    TEST_ASSERT_FALSE(state_machine::isRunning());
    state_machine::start(tStop + 100);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_TRUE(state_machine::isRunning());
}

void test_start_ignored_when_already_running(void) {
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_TRUE(state_machine::isRunning());
    // Calling start again should be ignored
    state_machine::start(tStart + 100);
    // Should still be in CoarseCooldown, not re-entered
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_stop_returns_to_idle(void) {
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    state_machine::stop(tStart + 1000);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_stop_ignored_when_not_running(void) {
    state_machine::init(0);
    // In Off state, not running — stop should be ignored
    state_machine::stop(100);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_off_from_idle(void) {
    const uint32_t tStop = initStartAndStop();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));
    state_machine::off(tStop + 100);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_off_ignored_when_already_off(void) {
    state_machine::init(0);
    state_machine::off(100);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

// ---------------------------------------------------------------------------
// State: CoarseCooldown
// ---------------------------------------------------------------------------

void test_coarse_cooldown_output(void) {
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_TRUE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::FlashFastRed),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_GREATER_THAN(0, out.dacTarget);
}

void test_coarse_dac_increases_as_temp_drops(void) {
    const uint32_t tStart = initAndStart();
    auto outHigh = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1);
    auto outLow  = state_machine::update(100.0f, 0.5f, 0.0f, false, tStart + 2);
    TEST_ASSERT_GREATER_THAN(outHigh.dacTarget, outLow.dacTarget);
}

void test_coarse_transitions_to_fine_below_threshold(void) {
    const uint32_t tStart = initAndStart();
    state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1);
    auto out = state_machine::update(
        COARSE_FINE_THRESHOLD_K - 1.0f, 0.5f, 0.0f, false, tStart + 2);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// State: FineCooldown
// ---------------------------------------------------------------------------

void test_fine_cooldown_ready_indicator_is_slow_green(void) {
    const uint32_t tStart = initAndStart();
    state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1);
    auto out = state_machine::update(
        COARSE_FINE_THRESHOLD_K - 1.0f, 0.5f, 0.0f, false, tStart + 2);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::FlashSlowGreen),
                      static_cast<uint8_t>(out.readyIndMode));
}

void test_fine_transitions_to_overshoot_below_setpoint(void) {
    const uint32_t tStart = initAndStart();
    state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1);
    state_machine::update(84.0f, 0.5f, 0.0f, false, tStart + 2);
    const float overshootTemp = SETPOINT_K - SETPOINT_TOLERANCE_K - 1.0f;
    auto out = state_machine::update(overshootTemp, 0.5f, 0.0f, false, tStart + 3);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Overshoot),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

// ---------------------------------------------------------------------------
// Fault: RMS over-voltage from any state
// ---------------------------------------------------------------------------

void test_rms_over_voltage_from_coarse_triggers_fault(void) {
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f,
                                     RMS_MAX_VOLTAGE_VDC + 1.0f,
                                     false, tStart + 1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_TRUE(out.alarmRelay);
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::RmsOvervoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

// ---------------------------------------------------------------------------
// Fault: temperature stall during cooldown
// ---------------------------------------------------------------------------

void test_stall_in_coarse_triggers_fault(void) {
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, true, tStart + 1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_TRUE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::TemperatureStall),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_stall_in_idle_does_not_trigger_fault(void) {
    // Get to Idle via start → stop
    const uint32_t tStop = initStartAndStop();
    // Stalled = true — should NOT fault (stall only matters in cooldown)
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, true, tStop + 1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(out.alarmRelay);
}

// ---------------------------------------------------------------------------
// Fault: terminal state (no auto-recovery)
// ---------------------------------------------------------------------------

void test_fault_stays_in_fault(void) {
    const uint32_t tStart = initAndStart();
    state_machine::update(200.0f, 0.5f,
                           RMS_MAX_VOLTAGE_VDC + 1.0f,
                           false, tStart + 1);
    // Even with clean readings, still Fault
    auto out = state_machine::update(100.0f, 0.5f, 0.0f, false, tStart + 2);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Relay: Bypass in early states
// ---------------------------------------------------------------------------

void test_coarse_uses_bypass_relay(void) {
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1);
    TEST_ASSERT_TRUE(out.bypassRelay);
}

// ---------------------------------------------------------------------------
// Status text
// ---------------------------------------------------------------------------

void test_status_text_not_null_for_all_states(void) {
    // Off
    state_machine::init(0);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, 0);
    TEST_ASSERT_NOT_NULL(out.statusText);

    // CoarseCooldown (via start)
    state_machine::start(100);
    out = state_machine::update(200.0f, 0.5f, 0.0f, false, 101);
    TEST_ASSERT_NOT_NULL(out.statusText);
}

void test_fault_status_text_contains_reason(void) {
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f,
                                     RMS_MAX_VOLTAGE_VDC + 1.0f,
                                     false, tStart + 1);
    TEST_ASSERT_NOT_NULL(out.statusText);
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "Fault:"));
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "RMS"));
}

void test_stall_fault_status_text(void) {
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, true, tStart + 1);
    TEST_ASSERT_NOT_NULL(out.statusText);
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "Fault:"));
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "stall"));
}

// ---------------------------------------------------------------------------
// On-state duration
// ---------------------------------------------------------------------------

void test_on_duration_zero_when_off(void) {
    state_machine::init(0);
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getOnStateDuration());
}

void test_on_duration_increases_while_running(void) {
    state_machine::init(0);
    state_machine::start(1000);
    // Advance update to set sOnStateMs
    state_machine::update(200.0f, 0.5f, 0.0f, false, 1000);
    stub_setMillis(4000);
    const uint32_t dur = state_machine::getOnStateDuration();
    TEST_ASSERT_GREATER_THAN(0, dur);
}

// ---------------------------------------------------------------------------
// stateName helper
// ---------------------------------------------------------------------------

void test_stateName_returns_non_null(void) {
    TEST_ASSERT_NOT_NULL(state_machine::stateName(state_machine::State::Off));
    TEST_ASSERT_NOT_NULL(state_machine::stateName(state_machine::State::Initialize));
    TEST_ASSERT_NOT_NULL(state_machine::stateName(state_machine::State::Fault));
    TEST_ASSERT_NOT_NULL(state_machine::stateName(state_machine::State::Operating));
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;

    UNITY_BEGIN();

    // Off state (initial)
    RUN_TEST(test_init_starts_in_off);
    RUN_TEST(test_off_output_is_bypass_indicators_off);
    RUN_TEST(test_off_stays_in_off);

    // Idle state
    RUN_TEST(test_idle_output_is_fault_red_bypass);
    RUN_TEST(test_idle_does_not_auto_transition);

    // Start / Stop / Off control
    RUN_TEST(test_start_from_off_enters_coarse);
    RUN_TEST(test_start_from_idle_enters_coarse);
    RUN_TEST(test_start_ignored_when_already_running);
    RUN_TEST(test_stop_returns_to_idle);
    RUN_TEST(test_stop_ignored_when_not_running);
    RUN_TEST(test_off_from_idle);
    RUN_TEST(test_off_ignored_when_already_off);

    // CoarseCooldown
    RUN_TEST(test_coarse_cooldown_output);
    RUN_TEST(test_coarse_dac_increases_as_temp_drops);
    RUN_TEST(test_coarse_transitions_to_fine_below_threshold);

    // FineCooldown
    RUN_TEST(test_fine_cooldown_ready_indicator_is_slow_green);
    RUN_TEST(test_fine_transitions_to_overshoot_below_setpoint);

    // Fault conditions
    RUN_TEST(test_rms_over_voltage_from_coarse_triggers_fault);
    RUN_TEST(test_stall_in_coarse_triggers_fault);
    RUN_TEST(test_stall_in_idle_does_not_trigger_fault);
    RUN_TEST(test_fault_stays_in_fault);

    // Relay
    RUN_TEST(test_coarse_uses_bypass_relay);

    // Status text
    RUN_TEST(test_status_text_not_null_for_all_states);
    RUN_TEST(test_fault_status_text_contains_reason);
    RUN_TEST(test_stall_fault_status_text);

    // On-state duration
    RUN_TEST(test_on_duration_zero_when_off);
    RUN_TEST(test_on_duration_increases_while_running);

    // Helpers
    RUN_TEST(test_stateName_returns_non_null);

    // Serial command handler
    run_serial_command_tests();

    return UNITY_END();
}
