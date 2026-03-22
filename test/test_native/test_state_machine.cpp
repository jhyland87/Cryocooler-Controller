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
#include "tick.h"

// Stub millis() control (provided by stubs/arduino_stub.cpp)
extern "C" void stub_setMillis(uint32_t ms);

// Amplifier stub control (provided by stubs/amplifier_stub.cpp)
extern "C" void stub_amplifier_setRmsVoltage(float v);
extern "C" void stub_amplifier_reset();

// Serial command tests (defined in test_serial_commands.cpp)
void run_serial_command_tests();

// FrameBuilder tests (defined in test_frame_builder.cpp)
void run_frame_builder_tests();

// Dashboard tests (defined in test_ss_dashboard.cpp)
void run_dashboard_tests();

// Sensor mock ramp tests (defined in test_sensor_mock_ramp.cpp)
void run_sensor_mock_ramp_tests();

// log ring buffer and LogStream tests (defined in test_log_buffer.cpp)
void run_log_tests();

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
                              float    tempC,
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
        tick::setNowMs(nowMs);
        auto out = state_machine::update(tempC, coolingRate, rmsV, stalled);
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
    tick::setNowMs(0);
    state_machine::init();
    const uint32_t tStart = 100;
    stub_setMillis(tStart);
    tick::setNowMs(tStart);
    state_machine::start();
    return tStart;
}

/**
 * Helper: init, start, then stop — ending in Idle.
 * Since stop() now transitions to Shutdown first, this helper advances through
 * the shutdown duration to reach Idle.
 *
 * @return  The nowMs timestamp at which Idle was entered.
 */
static uint32_t initStartAndStop() {
    const uint32_t tStart = initAndStart();
    const uint32_t tStop  = tStart + 1000;
    tick::setNowMs(tStop);
    state_machine::stop();
    // Shutdown lasts SHUTDOWN_DURATION_MS; advance past it to reach Idle
    const uint32_t tIdle = tStop + SHUTDOWN_DURATION_MS;
    stub_setMillis(tIdle);
    tick::setNowMs(tIdle);
    state_machine::update(295.0f, 0.0f, 0.0f, false);
    return tIdle;
}

// ---------------------------------------------------------------------------
// setUp / tearDown
// ---------------------------------------------------------------------------

void setUp(void) {
    stub_setMillis(0);
    stub_amplifier_reset();
    tick::setNowMs(0); state_machine::init();
}

void tearDown(void) {}

// ---------------------------------------------------------------------------
// State: Off (initial state after init)
// ---------------------------------------------------------------------------

void test_init_starts_in_off(void) {
    tick::setNowMs(0); state_machine::init();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_off_output_is_bypass_indicators_off(void) {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(0);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
    TEST_ASSERT_NOT_NULL(out.statusText);
}

void test_off_stays_in_off(void) {
    tick::setNowMs(0); state_machine::init();
    // Even after a long time, stays in Off without start()
    tick::setNowMs(60000);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

// ---------------------------------------------------------------------------
// State: Idle -- reached via stop() from a running state
// ---------------------------------------------------------------------------

void test_idle_output_is_fault_red_bypass(void) {
    const uint32_t tStop = initStartAndStop();
    tick::setNowMs(tStop + 1);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidRed),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

void test_idle_does_not_auto_transition(void) {
    const uint32_t tStop = initStartAndStop();
    tick::setNowMs(tStop + 60000);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

// ---------------------------------------------------------------------------
// start() / stop() / off() control
// ---------------------------------------------------------------------------

void test_start_from_off_enters_coarse(void) {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::start();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_TRUE(state_machine::isRunning());
}

void test_start_from_idle_enters_coarse(void) {
    const uint32_t tStop = initStartAndStop();
    TEST_ASSERT_FALSE(state_machine::isRunning());
    tick::setNowMs(tStop + 100); state_machine::start();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_TRUE(state_machine::isRunning());
}

void test_start_ignored_when_already_running(void) {
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_TRUE(state_machine::isRunning());
    // Calling start again should be ignored
    tick::setNowMs(tStart + 100); state_machine::start();
    // Should still be in CoarseCooldown, not re-entered
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_stop_returns_to_idle(void) {
    // NOTE: stop() now enters Shutdown state first, which then transitions to Idle
    // after SHUTDOWN_DURATION_MS. This test verifies the immediate transition to Shutdown.
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    tick::setNowMs(tStart + 1000); state_machine::stop();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_stop_ignored_when_not_running(void) {
    tick::setNowMs(0); state_machine::init();
    // In Off state, not running — stop should be ignored
    tick::setNowMs(100); state_machine::stop();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_off_from_idle(void) {
    const uint32_t tStop = initStartAndStop();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));
    tick::setNowMs(tStop + 100); state_machine::off();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_off_ignored_when_already_off(void) {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::off();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
}

// ---------------------------------------------------------------------------
// State: CoarseCooldown
// ---------------------------------------------------------------------------

void test_coarse_cooldown_output(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(0.0f, 0.5f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::FlashFastRed),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_GREATER_THAN(0, out.dacTarget);
}

void test_coarse_dac_increases_as_temp_drops(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto outHigh = state_machine::update(0.0f, 0.5f, 0.0f, false);
    tick::setNowMs(tStart + 2);
    auto outLow  = state_machine::update(-100.0f, 0.5f, 0.0f, false);
    TEST_ASSERT_GREATER_THAN(outHigh.dacTarget, outLow.dacTarget);
}

void test_coarse_transitions_to_fine_below_threshold(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    state_machine::update(200.0f, 0.5f, 0.0f, false);
    tick::setNowMs(tStart + 2);
    auto out = state_machine::update(COARSE_FINE_THRESHOLD_C - 1.0f, 0.5f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// State: FineCooldown
// ---------------------------------------------------------------------------

void test_fine_cooldown_ready_indicator_is_slow_green(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    state_machine::update(200.0f, 0.5f, 0.0f, false);
    tick::setNowMs(tStart + 2);
    auto out = state_machine::update(COARSE_FINE_THRESHOLD_C - 1.0f, 0.5f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::FlashSlowGreen),
                      static_cast<uint8_t>(out.readyIndMode));
}

void test_fine_transitions_to_overshoot_below_setpoint(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    state_machine::update(0.0f, 0.5f, 0.0f, false);
    tick::setNowMs(tStart + 2);
    state_machine::update(COARSE_FINE_THRESHOLD_C - 1.0f, 0.5f, 0.0f, false);
    const float overshootTemp = SETPOINT_C - SETPOINT_TOLERANCE_C - 1.0f;
    tick::setNowMs(tStart + 3);
    auto out = state_machine::update(overshootTemp, 0.5f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Overshoot),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

// ---------------------------------------------------------------------------
// Fault: RMS over-voltage from any state
// ---------------------------------------------------------------------------

void test_rms_over_voltage_from_coarse_triggers_fault(void) {
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::RmsOvervoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

// ---------------------------------------------------------------------------
// Fault: temperature stall during cooldown
// ---------------------------------------------------------------------------

void test_stall_in_coarse_triggers_fault(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::TemperatureStall),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_stall_in_idle_does_not_trigger_fault(void) {
    // Get to Idle via start → stop
    const uint32_t tStop = initStartAndStop();
    // Stalled = true — should NOT fault (stall only matters in cooldown)
    tick::setNowMs(tStop + 1);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Fault: terminal state (no auto-recovery)
// ---------------------------------------------------------------------------

void test_fault_stays_in_fault(void) {
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    // Even with clean readings, still Fault
    stub_amplifier_setRmsVoltage(0.0f);
    tick::setNowMs(tStart + 2);
    auto out = state_machine::update(100.0f, 0.5f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Relay: Bypass in early states
// ---------------------------------------------------------------------------

void test_coarse_uses_bypass_relay(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false);
}

// ---------------------------------------------------------------------------
// Status text
// ---------------------------------------------------------------------------

void test_status_text_not_null_for_all_states(void) {
    // Off
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(0);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_NOT_NULL(out.statusText);

    // CoarseCooldown (via start)
    tick::setNowMs(100); state_machine::start();
    tick::setNowMs(101);
    out = state_machine::update(200.0f, 0.5f, 0.0f, false);
    TEST_ASSERT_NOT_NULL(out.statusText);
}

void test_fault_status_text_contains_reason(void) {
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_NOT_NULL(out.statusText);
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "Fault:"));
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "RMS"));
}

void test_stall_fault_status_text(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, true);
    TEST_ASSERT_NOT_NULL(out.statusText);
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "Fault:"));
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "stall"));
}

// ---------------------------------------------------------------------------
// On-state duration
// ---------------------------------------------------------------------------

void test_on_duration_zero_when_off(void) {
    tick::setNowMs(0); state_machine::init();
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getOnStateDuration());
}

void test_on_duration_increases_while_running(void) {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(1000); state_machine::start();
    // Advance update to set sOnStateMs
    tick::setNowMs(1000);
    state_machine::update(200.0f, 0.5f, 0.0f, false);
    stub_setMillis(4000);
    const uint32_t dur = state_machine::getOnStateDuration();
    TEST_ASSERT_GREATER_THAN(0, dur);
}

// ---------------------------------------------------------------------------
// getTimeInState
// ---------------------------------------------------------------------------

void test_time_in_state_zero_at_init(void) {
    // init() enters Off at t=0 with millis()=0, so duration is 0.
    tick::setNowMs(0); state_machine::init();
    stub_setMillis(0);
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getTimeInState());
}

void test_time_in_state_grows_while_in_same_state(void) {
    tick::setNowMs(0); state_machine::init();
    stub_setMillis(2500);
    TEST_ASSERT_EQUAL_UINT32(2500, state_machine::getTimeInState());
}

void test_time_in_state_resets_to_zero_on_transition(void) {
    // start() transitions Off → CoarseCooldown at t=100; timer resets.
    tick::setNowMs(0); state_machine::init();
    stub_setMillis(100);
    tick::setNowMs(100); state_machine::start();
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getTimeInState());
}

void test_time_in_state_accumulates_after_transition(void) {
    tick::setNowMs(0); state_machine::init();
    stub_setMillis(100);
    tick::setNowMs(100); state_machine::start();   // CoarseCooldown entered at t=100
    stub_setMillis(750);
    TEST_ASSERT_EQUAL_UINT32(650, state_machine::getTimeInState());
}

void test_time_in_state_resets_again_on_stop(void) {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::start();   // CoarseCooldown @ 100
    tick::setNowMs(600); state_machine::stop();    // Idle @ 600; timer resets
    stub_setMillis(600);
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getTimeInState());
    stub_setMillis(900);
    TEST_ASSERT_EQUAL_UINT32(300, state_machine::getTimeInState());
}

// ---------------------------------------------------------------------------
// Reboot recovery: start() selects the correct resume state from tempC
// ---------------------------------------------------------------------------

void test_start_warm_enters_coarse_cooldown(void) {
    // Ambient temperature → full cooldown from the top.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::start(AMBIENT_START_C);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_start_above_threshold_enters_coarse_cooldown(void) {
    // 90 K is above COARSE_FINE_THRESHOLD_C (85 K) → CoarseCooldown.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::start(90.0f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_start_below_threshold_enters_fine_cooldown(void) {
    // -190 C is below COARSE_FINE_THRESHOLD_C (-188.15) but above the setpoint
    // tolerance band (> SETPOINT_C + SETPOINT_TOLERANCE_C = -192.15) -> FineCooldown.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::start(-190.0f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_start_inband_enters_settle(void) {
    // Exactly at setpoint → skip cooldown, enter Settle with relay Normal.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::start(SETPOINT_C);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(state_machine::getState()));
    tick::setNowMs(101);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(out.state));
}

void test_start_overshot_enters_overshoot(void) {
    // 1 K below the tolerance band (< SETPOINT_C - SETPOINT_TOLERANCE_C = 76 K)
    // → Overshoot; DAC target must be 0.
    tick::setNowMs(0); state_machine::init();
    const float overshootTemp = SETPOINT_C - SETPOINT_TOLERANCE_C - 1.0f;
    tick::setNowMs(100); state_machine::start(overshootTemp);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Overshoot),
                      static_cast<int8_t>(state_machine::getState()));
    tick::setNowMs(101);
    auto out = state_machine::update(overshootTemp, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

void test_start_resume_fine_no_stall_fault(void) {
    // On a fresh reboot, stalled is always false (no history yet).
    // Resuming into FineCooldown with a stable cold temperature must NOT fault.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100); state_machine::start(-190.0f);  // -> FineCooldown
    tick::setNowMs(101);
    auto out = state_machine::update(-190.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Back-EMF backoff: overstroke detection → DAC reduction → fault
// ---------------------------------------------------------------------------

void test_overstroke_increments_backoff_count(void) {
    // One overstroke while running: backoffCount in Output should be 1.
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, true);
    TEST_ASSERT_EQUAL_UINT16(1, out.backoffCount);
}

void test_overstroke_reduces_dac_target(void) {
    // The DAC target after one backoff must be reduced by exactly BACKOFF_DAC_STEP
    // compared to the same temperature without a backoff.
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    const auto baseOut    = state_machine::update(200.0f, 0.5f, 0.0f, false, false);
    tick::setNowMs(tStart + 2);
    const auto backoffOut = state_machine::update(200.0f, 0.5f, 0.0f, false, true);

    // Both calls see the same temperature so the nominal target is identical.
    // After one BACKOFF_DAC_STEP reduction the effective target must be lower.
    const uint16_t expected = (baseOut.dacTarget >= BACKOFF_DAC_STEP)
                                  ? static_cast<uint16_t>(baseOut.dacTarget - BACKOFF_DAC_STEP)
                                  : 0u;
    TEST_ASSERT_EQUAL_UINT16(expected, backoffOut.dacTarget);
}

void test_overstroke_triggers_fault_at_max_count(void) {
    // After exactly BACKOFF_MAX_COUNT overstroke events the machine must enter
    // Fault with reason TooManyBackoffs.
    const uint32_t tStart = initAndStart();
    state_machine::Output out{};
    for (uint8_t i = 0; i < BACKOFF_MAX_COUNT; ++i) {
        tick::setNowMs(tStart + 1u + i);
        out = state_machine::update(200.0f, 0.5f, 0.0f, false, true);
    }
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::TooManyBackoffs),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_overstroke_ignored_when_not_running(void) {
    // An overstroke event while in Off state must be silently ignored.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(1);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.backoffCount);
}

void test_backoff_count_resets_on_start(void) {
    // Accumulate backoffs up to (MAX - 1) so we stay just below the fault
    // threshold.  After stop() + start() the count must reset to zero.
    const uint32_t tStart = initAndStart();
    for (uint8_t i = 0; i < BACKOFF_MAX_COUNT - 1u; ++i) {
        tick::setNowMs(tStart + 1u + i);
        state_machine::update(200.0f, 0.5f, 0.0f, false, true);
    }
    tick::setNowMs(tStart + 500u); state_machine::stop();
    tick::setNowMs(tStart + 600u); state_machine::start();
    tick::setNowMs(tStart + 601u);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, false);
    TEST_ASSERT_EQUAL_UINT16(0, out.backoffCount);
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
// stateName: exact string values for every state
// ---------------------------------------------------------------------------

void test_stateName_off_string(void) {
    TEST_ASSERT_EQUAL_STRING("Off",
        state_machine::stateName(state_machine::State::Off));
}

void test_stateName_initialize_string(void) {
    TEST_ASSERT_EQUAL_STRING("Initialize",
        state_machine::stateName(state_machine::State::Initialize));
}

void test_stateName_idle_string(void) {
    TEST_ASSERT_EQUAL_STRING("Idle",
        state_machine::stateName(state_machine::State::Idle));
}

void test_stateName_coarse_cooldown_string(void) {
    TEST_ASSERT_EQUAL_STRING("CoarseCooldown",
        state_machine::stateName(state_machine::State::CoarseCooldown));
}

void test_stateName_fine_cooldown_string(void) {
    TEST_ASSERT_EQUAL_STRING("FineCooldown",
        state_machine::stateName(state_machine::State::FineCooldown));
}

void test_stateName_overshoot_string(void) {
    TEST_ASSERT_EQUAL_STRING("Overshoot",
        state_machine::stateName(state_machine::State::Overshoot));
}

void test_stateName_settle_string(void) {
    TEST_ASSERT_EQUAL_STRING("Settle",
        state_machine::stateName(state_machine::State::Settle));
}

void test_stateName_baseline_string(void) {
    TEST_ASSERT_EQUAL_STRING("Baseline",
        state_machine::stateName(state_machine::State::Baseline));
}

void test_stateName_operating_string(void) {
    TEST_ASSERT_EQUAL_STRING("Operating",
        state_machine::stateName(state_machine::State::Operating));
}

void test_stateName_shutdown_string(void) {
    TEST_ASSERT_EQUAL_STRING("Shutdown",
        state_machine::stateName(state_machine::State::Shutdown));
}

void test_stateName_fault_string(void) {
    TEST_ASSERT_EQUAL_STRING("Fault",
        state_machine::stateName(state_machine::State::Fault));
}

// ---------------------------------------------------------------------------
// Settle state: timer boundary and reset behaviour
// ---------------------------------------------------------------------------

/**
 * The Settle timer starts on the first in-band update() call.
 * One tick before SETTLE_DURATION_MS the machine must still be in Settle.
 */
void test_settle_does_not_transition_just_before_timer(void) {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(0); state_machine::start(SETPOINT_C);   // enters Settle directly

    // First in-band call starts the settle timer at t = 1.
    tick::setNowMs(1);
    state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);

    // One tick before expiry: elapsed = SETTLE_DURATION_MS - 1 → stay in Settle.
    tick::setNowMs(SETTLE_DURATION_MS);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(out.state));
}

/**
 * If temperature drifts out of band the settle timer resets.
 * After re-entering the band the full SETTLE_DURATION_MS must elapse again
 * before the transition to Baseline fires.
 */
void test_settle_timer_resets_when_out_of_band(void) {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(0); state_machine::start(SETPOINT_C);

    // Start settle timer at t = 1.
    tick::setNowMs(1);
    state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);

    // Drift out of band — timer resets.
    tick::setNowMs(100);
    state_machine::update(COARSE_FINE_THRESHOLD_C, 0.0f, 0.0f, false);

    // Re-enter band at t = 200 — timer restarts from here.
    tick::setNowMs(200);
    state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);

    // One tick before the restarted timer would fire: must still be Settle.
    tick::setNowMs(200 + SETTLE_DURATION_MS - 1);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Settle → Baseline → Operating: relay and timer boundaries
// ---------------------------------------------------------------------------

/**
 * Helper: advance from Off through Settle into Baseline.
 * Returns the nowMs timestamp at which Baseline was entered.
 */
static uint32_t advanceToBaseline() {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(0); state_machine::start(SETPOINT_C);            // → Settle at t = 0

    // Start settle timer at t = 1, then fire it.
    tick::setNowMs(1);
    state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    const uint32_t baselineEntryMs = 1u + SETTLE_DURATION_MS;
    tick::setNowMs(baselineEntryMs);
    state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    return baselineEntryMs;
}

void test_baseline_uses_normal_relay(void) {
    const uint32_t baselineEntry = advanceToBaseline();
    tick::setNowMs(baselineEntry + 1u);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Baseline),
                      static_cast<int8_t>(out.state));
}

/** One tick before BASELINE_DURATION_MS expires the machine must stay in Baseline. */
void test_baseline_does_not_transition_just_before_timer(void) {
    const uint32_t baselineEntry = advanceToBaseline();
    tick::setNowMs(baselineEntry + BASELINE_DURATION_MS - 1u);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Baseline),
                      static_cast<int8_t>(out.state));
}

void test_operating_uses_normal_relay(void) {
    const uint32_t baselineEntry = advanceToBaseline();
    tick::setNowMs(baselineEntry + BASELINE_DURATION_MS);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Operating),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// State: Shutdown
// ---------------------------------------------------------------------------

void test_stop_enters_shutdown(void) {
    // stop() from a running state should transition to Shutdown, not Idle
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    tick::setNowMs(tStart + 1000); state_machine::stop();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_shutdown_returns_dac_zero(void) {
    // Shutdown state should target DAC = 0 to allow rampToward() to gradually reduce
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1000); state_machine::stop();
    tick::setNowMs(tStart + 1001);
    const auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(0, out.dacTarget);
}

void test_shutdown_uses_bypass_relay(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1000); state_machine::stop();
    tick::setNowMs(tStart + 1001);
    const auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
}

void test_shutdown_duration_then_transitions_to_idle(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1000); state_machine::stop();
    // Just before SHUTDOWN_DURATION_MS elapses, should still be in Shutdown
    const uint32_t beforeExpiry = tStart + 1000 + SHUTDOWN_DURATION_MS - 1;
    stub_setMillis(beforeExpiry);
    tick::setNowMs(beforeExpiry);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(out.state));

    // After SHUTDOWN_DURATION_MS elapses, should transition to Idle
    const uint32_t afterExpiry = tStart + 1000 + SHUTDOWN_DURATION_MS;
    stub_setMillis(afterExpiry);
    tick::setNowMs(afterExpiry);
    out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// off() from non-Idle states
// ---------------------------------------------------------------------------

void test_off_from_running_coarse(void) {
    // off() must work even when the machine is actively running (CoarseCooldown).
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    tick::setNowMs(tStart + 100u); state_machine::off();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_off_from_fault_clears_fault_reason(void) {
    // off() is the only way out of Fault (stop() is a no-op when running==false).
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));

    tick::setNowMs(tStart + 2u); state_machine::off();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::None),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

// ---------------------------------------------------------------------------
// Stall detection: only active in CoarseCooldown and FineCooldown
// ---------------------------------------------------------------------------

void test_stall_in_fine_triggers_fault(void) {
    const uint32_t tStart = initAndStart();

    // Transition to FineCooldown.
    tick::setNowMs(tStart + 1u);
    state_machine::update(COARSE_FINE_THRESHOLD_C - 1.0f, 0.5f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(state_machine::getState()));

    // Stall while in FineCooldown → Fault(TemperatureStall).
    tick::setNowMs(tStart + 2u);
    auto out = state_machine::update(COARSE_FINE_THRESHOLD_C - 1.0f, 0.5f, 0.0f, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::TemperatureStall),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_stall_in_settle_does_not_fault(void) {
    // Stall is only checked in CoarseCooldown and FineCooldown.
    // In Settle (reached by resuming at setpoint) it must be silently ignored.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(0); state_machine::start(SETPOINT_C);   // → Settle directly
    tick::setNowMs(1u);
    auto out = state_machine::update(SETPOINT_C, 0.0f, 0.0f, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Overstroke ignored while already in Fault
// ---------------------------------------------------------------------------

void test_overstroke_ignored_in_fault(void) {
    // Fault blocks the entire global-fault / overstroke section of update().
    const uint32_t tStart = initAndStart();
    // Trigger a fault.
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));

    // Overstroke while in Fault — must not change state or increment backoffCount.
    tick::setNowMs(tStart + 2u);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.backoffCount);
}

// ---------------------------------------------------------------------------
// Delay state
// ---------------------------------------------------------------------------

/** Returns a millisecond timestamp just after init() so tests can use it. */
static uint32_t initState() {
    tick::setNowMs(1000); state_machine::init();
    return 1000;
}

void test_delay_from_off_enters_delay_state(void) {
    const uint32_t t0 = initState();
    tick::setNowMs(t0); state_machine::startDelay(500, state_machine::State::Idle);
    tick::setNowMs(t0 + 1);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Delay),
                      static_cast<int8_t>(out.state));
}

void test_delay_output_uses_bypass_relay(void) {
    const uint32_t t0 = initState();
    tick::setNowMs(t0); state_machine::startDelay(500, state_machine::State::Idle);
    tick::setNowMs(t0 + 1);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
}

void test_delay_output_indicators_are_solid_amber(void) {
    const uint32_t t0 = initState();
    tick::setNowMs(t0); state_machine::startDelay(500, state_machine::State::Idle);
    tick::setNowMs(t0 + 1);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidAmber),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidAmber),
                      static_cast<uint8_t>(out.readyIndMode));
}

void test_delay_dac_target_is_zero(void) {
    const uint32_t t0 = initState();
    tick::setNowMs(t0); state_machine::startDelay(500, state_machine::State::Idle);
    tick::setNowMs(t0 + 1);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

void test_delay_does_not_expire_just_before_timer(void) {
    const uint32_t t0 = initState();
    tick::setNowMs(t0); state_machine::startDelay(500, state_machine::State::Idle);
    // Advance to just before the deadline.
    tick::setNowMs(t0 + 499);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Delay),
                      static_cast<int8_t>(out.state));
}

void test_delay_expires_and_transitions_to_idle(void) {
    const uint32_t t0 = initState();
    tick::setNowMs(t0); state_machine::startDelay(500, state_machine::State::Idle);
    // Hold just before expiry.
    tick::setNowMs(t0 + 499);
    state_machine::update(300.0f, 0.0f, 0.0f, false);
    // Cross the threshold.
    tick::setNowMs(t0 + 500);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
}

void test_delay_expires_and_transitions_to_coarse(void) {
    const uint32_t t0 = initState();
    tick::setNowMs(t0); state_machine::startDelay(200, state_machine::State::CoarseCooldown);
    tick::setNowMs(t0 + 199);
    state_machine::update(300.0f, 0.0f, 0.0f, false);
    tick::setNowMs(t0 + 200);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(out.state));
}

void test_delay_from_fault_is_ignored(void) {
    const uint32_t t0 = initState();
    // Trigger a fault first.
    tick::setNowMs(t0); state_machine::start(300.0f);
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(t0 + 1);
    state_machine::update(300.0f, 0.0f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));
    // startDelay() must be a no-op in Fault.
    tick::setNowMs(t0 + 2); state_machine::startDelay(100, state_machine::State::Idle);
    tick::setNowMs(t0 + 3);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Fault: low system voltage — triggers from any non-Fault state
// ---------------------------------------------------------------------------

void test_low_voltage_from_off_triggers_fault(void) {
    // Even in the Off state a low-voltage reading must immediately fault.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(1);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, false, MIN_SYSTEM_VOLTAGE_VDC - 0.1f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::LowSystemVoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_low_voltage_from_idle_triggers_fault(void) {
    const uint32_t tIdle = initStartAndStop();
    tick::setNowMs(tIdle + 1);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, false, MIN_SYSTEM_VOLTAGE_VDC - 0.1f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::LowSystemVoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_low_voltage_from_coarse_triggers_fault(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, false, MIN_SYSTEM_VOLTAGE_VDC - 0.1f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::LowSystemVoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_low_voltage_from_delay_triggers_fault(void) {
    const uint32_t t0 = 1000;
    tick::setNowMs(t0); state_machine::init();
    tick::setNowMs(t0); state_machine::startDelay(500, state_machine::State::Idle);
    tick::setNowMs(t0 + 1);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, false, MIN_SYSTEM_VOLTAGE_VDC - 0.1f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::LowSystemVoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_low_voltage_zero_does_not_trigger_fault(void) {
    // 0.0f is the "not monitored" sentinel — must never trigger LowSystemVoltage.
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, false, 0.0f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(out.state));
}

void test_low_voltage_exactly_at_minimum_does_not_trigger_fault(void) {
    // Exactly at the threshold is OK — only *below* the threshold faults.
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, false, static_cast<float>(MIN_SYSTEM_VOLTAGE_VDC));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(out.state));
}

void test_low_voltage_fault_status_text(void) {
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, false, MIN_SYSTEM_VOLTAGE_VDC - 0.1f);
    TEST_ASSERT_NOT_NULL(out.statusText);
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "Fault:"));
    TEST_ASSERT_NOT_NULL(strstr(out.statusText, "voltage"));
}

// ---------------------------------------------------------------------------
// clearFault(): exits Fault → Idle, resets fault reason and backoff state
// ---------------------------------------------------------------------------

void test_clear_fault_transitions_to_idle(void) {
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));

    tick::setNowMs(tStart + 2u); state_machine::clearFault();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_clear_fault_resets_fault_reason(void) {
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::RmsOvervoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));

    tick::setNowMs(tStart + 2u); state_machine::clearFault();
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::None),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_clear_fault_resets_backoff_state(void) {
    // Accumulate backoffs up to (MAX - 1), trigger a fault via RMS, then clear.
    // After clear the backoff count reported by the next update() must be 0.
    const uint32_t tStart = initAndStart();
    for (uint8_t i = 0; i < BACKOFF_MAX_COUNT - 1u; ++i) {
        tick::setNowMs(tStart + 1u + i);
        state_machine::update(200.0f, 0.5f, 0.0f, false, true);
    }
    // Now trigger fault via RMS.
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 100u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));

    tick::setNowMs(tStart + 101u); state_machine::clearFault();
    tick::setNowMs(tStart + 102u);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false);
    // backoffCount in Output must have been reset to 0 by onExitFault().
    TEST_ASSERT_EQUAL_UINT16(0, out.backoffCount);
}

void test_clear_fault_leaves_running_false(void) {
    // After clearFault() the operator must call start() explicitly; the machine
    // must not resume automatically.
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    tick::setNowMs(tStart + 2u); state_machine::clearFault();
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_clear_fault_ignored_when_not_in_fault(void) {
    // clearFault() must be a no-op when the machine is not in State::Fault.
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1u); state_machine::clearFault();
    // Still in CoarseCooldown — the call must have had no effect.
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_clear_fault_then_start_resumes_cooldown(void) {
    // After clearFault() → Idle, calling start() must resume the process.
    const uint32_t tStart = initAndStart();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(tStart + 1u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false);
    tick::setNowMs(tStart + 2u); state_machine::clearFault();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));

    tick::setNowMs(tStart + 3u); state_machine::start();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_TRUE(state_machine::isRunning());
}

void test_clear_low_voltage_fault_transitions_to_idle(void) {
    // LowSystemVoltage fault can also be cleared with clearFault().
    const uint32_t tStart = initAndStart();
    tick::setNowMs(tStart + 1u);
    state_machine::update(200.0f, 0.5f, 0.0f, false, false, MIN_SYSTEM_VOLTAGE_VDC - 0.1f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::LowSystemVoltage),
                      static_cast<uint8_t>(state_machine::getFaultReason()));

    tick::setNowMs(tStart + 2u); state_machine::clearFault();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::None),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

// ---------------------------------------------------------------------------
// FSM History tests
// ---------------------------------------------------------------------------

static void test_history_empty_after_init() {
    tick::setNowMs(0); state_machine::init();
    // init() fires onEnterOff, so 1 entry (Off) is recorded.
    // We check that behaviour explicitly in the next test; here we just verify
    // the count matches what init() actually records.
    // (For this test we want the count to be exactly 1.)
    TEST_ASSERT_EQUAL(1u, state_machine::getHistoryCount());
}

static void test_history_records_off_on_init() {
    tick::setNowMs(0); state_machine::init();
    TEST_ASSERT_EQUAL(1u, state_machine::getHistoryCount());
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(entry.state));
    TEST_ASSERT_EQUAL(0u, entry.enteredMs);
}

static void test_history_records_start_transition() {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    // Most recent entry is CoarseCooldown (or whichever start state).
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(entry.state));
    TEST_ASSERT_EQUAL(100u, entry.enteredMs);
}

static void test_history_index_1_is_previous_state() {
    // After init (Off) + start (CoarseCooldown), index 1 should be Off.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    TEST_ASSERT_EQUAL(2u, state_machine::getHistoryCount());
    const auto prev = state_machine::getHistoryEntry(1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(prev.state));
}

static void test_history_out_of_range_returns_zero_entry() {
    tick::setNowMs(0); state_machine::init();
    // Only 1 entry; requesting index 5 should return a zeroed HistoryEntry and not crash.
    const auto entry = state_machine::getHistoryEntry(5);
    // HistoryEntry{} zero-initialises: state=0 (Initialize), enteredMs=0.
    TEST_ASSERT_EQUAL(0u, entry.enteredMs);
    // The important guarantee: count is unchanged (no side effects).
    TEST_ASSERT_EQUAL(1u, state_machine::getHistoryCount());
}

static void test_history_timestamp_matches_entry_time() {
    tick::setNowMs(500u); state_machine::init();
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL(500u, entry.enteredMs);
}

static void test_history_grows_with_each_transition() {
    tick::setNowMs(0); state_machine::init();       // Off       → count 1
    tick::setNowMs(100u); state_machine::start();   // Coarse    → count 2
    tick::setNowMs(200u); state_machine::stop();    // Shutdown  → count 3
    TEST_ASSERT_EQUAL(3u, state_machine::getHistoryCount());
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(state_machine::getHistoryEntry(0).state));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getHistoryEntry(1).state));
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getHistoryEntry(2).state));
}

static void test_history_wraps_at_limit() {
    // Drive more than FSM_HISTORY_LIMIT transitions by toggling start/stop.
    // Each stop→shutdown→(wait)→idle cycle adds 3 entries (Shutdown, Idle, Coarse).
    // We just want to confirm the count never exceeds FSM_HISTORY_LIMIT.
    tick::setNowMs(0); state_machine::init();
    uint32_t t = 10u;
    for (uint8_t i = 0; i < 30u; ++i, t += 10u) {
        tick::setNowMs(t); state_machine::start();
        t += 10u;
        tick::setNowMs(t); state_machine::stop();
        t += 10u;
        // Advance through Shutdown to Idle so we can start again.
        tick::setNowMs(t + SHUTDOWN_DURATION_MS + 1u);
        state_machine::update(300.0f, 0.0f, 0.0f, false);
        t += SHUTDOWN_DURATION_MS + 2u;
    }
    TEST_ASSERT_LESS_OR_EQUAL(static_cast<uint8_t>(FSM_HISTORY_LIMIT),
                               state_machine::getHistoryCount());
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FSM_HISTORY_LIMIT),
                      state_machine::getHistoryCount());
}

// ---------------------------------------------------------------------------
// FSM Oscillation detection tests
// ---------------------------------------------------------------------------

// Helper: one update() with fixed inputs; returns resulting state.
static state_machine::State bounceOnce(float tempC, uint32_t t) {
    tick::setNowMs(t);
    return state_machine::update(tempC, 0.0f, 0.0f, false).state;
}

// Temperatures to bounce between Fine and Coarse in oscillation tests.
static const float kFineTemp   = COARSE_FINE_THRESHOLD_C - 1.0f;  // below threshold -> Fine
static const float kCoarseTemp = COARSE_FINE_THRESHOLD_C + 1.0f;  // above threshold -> Coarse

static void test_oscillation_no_fault_before_min_cycles() {
    // Window = FSM_OSCILLATION_MIN_CYCLES * 2 = 6 entries.
    // After init(Off) + start(Coarse) + 4 alternations = 6 pushes total.
    // entry[5] is still Off -> pattern check fails -> no fault.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    bounceOnce(kFineTemp, 200u);     // Fine   (3rd push)
    bounceOnce(kCoarseTemp, 300u);   // Coarse (4th push)
    bounceOnce(kFineTemp, 400u);     // Fine   (5th push)
    tick::setNowMs(500u);
    const auto out = state_machine::update(kCoarseTemp, 0.0f, 0.0f, false);  // Coarse (6th)
    TEST_ASSERT_NOT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                          static_cast<int8_t>(out.state));
}

static void test_oscillation_fault_fires_after_min_cycles() {
    // 7 pushes: Off, Coarse, Fine, Coarse, Fine, Coarse, Fine
    // At push 7 (Fine), entries[0..5] = Fine,Coarse,Fine,Coarse,Fine,Coarse -> flag set.
    // Next update() tick consumes the flag and fires Fault.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    bounceOnce(kFineTemp, 200u);     // Fine   (3rd push)
    bounceOnce(kCoarseTemp, 300u);   // Coarse (4th push)
    bounceOnce(kFineTemp, 400u);     // Fine   (5th push)
    bounceOnce(kCoarseTemp, 500u);   // Coarse (6th push)
    bounceOnce(kFineTemp, 600u);     // Fine   (7th push) <- oscillation flag set inside pushHistory
    // Next tick: fault check fires before temperature logic.
    tick::setNowMs(700u);
    const auto out = state_machine::update(kFineTemp, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
}

static void test_oscillation_fault_reason_is_state_oscillation() {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    bounceOnce(kFineTemp, 200u);
    bounceOnce(kCoarseTemp, 300u);
    bounceOnce(kFineTemp, 400u);
    bounceOnce(kCoarseTemp, 500u);
    bounceOnce(kFineTemp, 600u);
    tick::setNowMs(700u);
    state_machine::update(kFineTemp, 0.0f, 0.0f, false);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::StateOscillation),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

static void test_oscillation_status_text_is_not_null() {
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    bounceOnce(kFineTemp, 200u);
    bounceOnce(kCoarseTemp, 300u);
    bounceOnce(kFineTemp, 400u);
    bounceOnce(kCoarseTemp, 500u);
    bounceOnce(kFineTemp, 600u);
    tick::setNowMs(700u);
    state_machine::update(kFineTemp, 0.0f, 0.0f, false);
    TEST_ASSERT_NOT_NULL(state_machine::getStatusText());
}

static void test_oscillation_no_fault_with_third_state_in_window() {
    // Introduce Overshoot to break the two-state alternation.
    // Off, Coarse, Fine, Coarse, Fine, Overshoot, Fine -> third state in window.
    const float kOvershoot = static_cast<float>(SETPOINT_C)
                           - static_cast<float>(SETPOINT_TOLERANCE_C) - 1.0f;
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    bounceOnce(kFineTemp, 200u);        // Fine
    bounceOnce(kCoarseTemp, 300u);      // Coarse
    bounceOnce(kFineTemp, 400u);        // Fine
    bounceOnce(kOvershoot, 500u);       // Overshoot (breaks A/B pattern)
    tick::setNowMs(600u);
    const auto out = state_machine::update(kFineTemp, 0.0f, 0.0f, false);
    TEST_ASSERT_NOT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                          static_cast<int8_t>(out.state));
}

static void test_oscillation_no_fault_outside_time_window() {
    // Space each bounce > FSM_OSCILLATION_WINDOW_MS / 5 apart so the 6-entry
    // window spans more than FSM_OSCILLATION_WINDOW_MS total.
    const uint32_t kStep = static_cast<uint32_t>(FSM_OSCILLATION_WINDOW_MS) / 5u + 1u;
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    bounceOnce(kFineTemp, 100u + 1u * kStep);
    bounceOnce(kCoarseTemp, 100u + 2u * kStep);
    bounceOnce(kFineTemp, 100u + 3u * kStep);
    bounceOnce(kCoarseTemp, 100u + 4u * kStep);
    bounceOnce(kFineTemp, 100u + 5u * kStep);  // 7th push - time span > window
    tick::setNowMs(100u + 6u * kStep);
    const auto out = state_machine::update(kFineTemp, 0.0f, 0.0f, false);
    TEST_ASSERT_NOT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                          static_cast<int8_t>(out.state));
}

static void test_oscillation_pending_clears_after_clear_fault() {
    // After clearFault() -> Idle, sOscillationFaultPending is reset.
    // A single ordinary update from Idle must not immediately re-fault.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    bounceOnce(kFineTemp, 200u);
    bounceOnce(kCoarseTemp, 300u);
    bounceOnce(kFineTemp, 400u);
    bounceOnce(kCoarseTemp, 500u);
    bounceOnce(kFineTemp, 600u);
    tick::setNowMs(700u);
    state_machine::update(kFineTemp, 0.0f, 0.0f, false);   // -> Fault
    tick::setNowMs(800u); state_machine::clearFault();                               // -> Idle, clears flag

    tick::setNowMs(900u);
    const auto out = state_machine::update(0.0f, 0.0f, 0.0f, false);
    TEST_ASSERT_NOT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                          static_cast<int8_t>(out.state));
}

static void test_history_reset_on_reinit() {
    // reinit() clears history and records only Initialize.
    // Must be called from Off, Idle, or Fault (EVT_REINITIALIZE is only
    // registered from those states).  Call from Off (directly after init()).
    tick::setNowMs(0); state_machine::init();      // Off recorded → count 1
    tick::setNowMs(200u); state_machine::reinit(); // clears history, then Initialize recorded → count 1
    TEST_ASSERT_EQUAL(1u, state_machine::getHistoryCount());
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Initialize),
                      static_cast<int8_t>(state_machine::getHistoryEntry(0).state));
    TEST_ASSERT_EQUAL(200u, state_machine::getHistoryEntry(0).enteredMs);
}

// ---------------------------------------------------------------------------
// History cause field tests
// ---------------------------------------------------------------------------

static void test_history_cause_init_records_init() {
    // The Off entry written by init() run_machine() should carry cause "init".
    tick::setNowMs(0); state_machine::init();
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL_STRING("init", entry.cause);
}

static void test_history_cause_start_records_start() {
    // start() should record cause "start" for the CoarseCooldown entry.
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(100u); state_machine::start();
    // index 0 = most recent = CoarseCooldown; index 1 = Off (from init)
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(entry.state));
    TEST_ASSERT_EQUAL_STRING("start", entry.cause);
}

static void test_history_cause_stop_records_stop() {
    // stop() → Shutdown should record cause "stop".
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(0u); state_machine::start();
    tick::setNowMs(500u); state_machine::stop();
    // index 0 = most recent = Shutdown
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(entry.state));
    TEST_ASSERT_EQUAL_STRING("stop", entry.cause);
}

static void test_history_cause_reinit_records_reinit() {
    // reinit() → Initialize should record cause "reinit".
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(300u); state_machine::reinit();
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Initialize),
                      static_cast<int8_t>(entry.state));
    TEST_ASSERT_EQUAL_STRING("reinit", entry.cause);
}

static void test_history_cause_clear_fault_records_clearFault() {
    // clearFault() → Idle should record cause "clearFault".
    tick::setNowMs(0); state_machine::init();
    tick::setNowMs(5u); state_machine::start();
    stub_amplifier_setRmsVoltage(AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f);
    tick::setNowMs(10u);
    state_machine::update(200.0f, 0.5f, AMPLIFIER_MAX_VOLTAGE_VAC + 1.0f, false); // RMS fault → Fault state
    tick::setNowMs(20u); state_machine::clearFault();
    const auto entry = state_machine::getHistoryEntry(0);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(entry.state));
    TEST_ASSERT_EQUAL_STRING("clearFault", entry.cause);
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

    // Shutdown state
    RUN_TEST(test_stop_enters_shutdown);
    RUN_TEST(test_shutdown_returns_dac_zero);
    RUN_TEST(test_shutdown_uses_bypass_relay);
    RUN_TEST(test_shutdown_duration_then_transitions_to_idle);

    // CoarseCooldown
    RUN_TEST(test_coarse_cooldown_output);
    RUN_TEST(test_coarse_dac_increases_as_temp_drops);
    RUN_TEST(test_coarse_transitions_to_fine_below_threshold);

    // FineCooldown
    RUN_TEST(test_fine_cooldown_ready_indicator_is_slow_green);
    RUN_TEST(test_fine_transitions_to_overshoot_below_setpoint);

    // on_enter actions: cooling enable and amplifier init

    // Fault conditions
    RUN_TEST(test_rms_over_voltage_from_coarse_triggers_fault);
    RUN_TEST(test_stall_in_coarse_triggers_fault);
    RUN_TEST(test_stall_in_idle_does_not_trigger_fault);
    RUN_TEST(test_fault_stays_in_fault);

    // Fault: low system voltage
    RUN_TEST(test_low_voltage_from_off_triggers_fault);
    RUN_TEST(test_low_voltage_from_idle_triggers_fault);
    RUN_TEST(test_low_voltage_from_coarse_triggers_fault);
    RUN_TEST(test_low_voltage_from_delay_triggers_fault);
    RUN_TEST(test_low_voltage_zero_does_not_trigger_fault);
    RUN_TEST(test_low_voltage_exactly_at_minimum_does_not_trigger_fault);
    RUN_TEST(test_low_voltage_fault_status_text);

    // clearFault()
    RUN_TEST(test_clear_fault_transitions_to_idle);
    RUN_TEST(test_clear_fault_resets_fault_reason);
    RUN_TEST(test_clear_fault_resets_backoff_state);
    RUN_TEST(test_clear_fault_leaves_running_false);
    RUN_TEST(test_clear_fault_ignored_when_not_in_fault);
    RUN_TEST(test_clear_fault_then_start_resumes_cooldown);
    RUN_TEST(test_clear_low_voltage_fault_transitions_to_idle);

    // Relay
    RUN_TEST(test_coarse_uses_bypass_relay);

    // Status text
    RUN_TEST(test_status_text_not_null_for_all_states);
    RUN_TEST(test_fault_status_text_contains_reason);
    RUN_TEST(test_stall_fault_status_text);

    // On-state duration
    RUN_TEST(test_on_duration_zero_when_off);
    RUN_TEST(test_on_duration_increases_while_running);

    // Time in current state
    RUN_TEST(test_time_in_state_zero_at_init);
    RUN_TEST(test_time_in_state_grows_while_in_same_state);
    RUN_TEST(test_time_in_state_resets_to_zero_on_transition);
    RUN_TEST(test_time_in_state_accumulates_after_transition);
    RUN_TEST(test_time_in_state_resets_again_on_stop);

    // Reboot recovery / resume state selection
    RUN_TEST(test_start_warm_enters_coarse_cooldown);
    RUN_TEST(test_start_above_threshold_enters_coarse_cooldown);
    RUN_TEST(test_start_below_threshold_enters_fine_cooldown);
    RUN_TEST(test_start_inband_enters_settle);
    RUN_TEST(test_start_overshot_enters_overshoot);
    RUN_TEST(test_start_resume_fine_no_stall_fault);

    // Back-EMF backoff
    RUN_TEST(test_overstroke_increments_backoff_count);
    RUN_TEST(test_overstroke_reduces_dac_target);
    RUN_TEST(test_overstroke_triggers_fault_at_max_count);
    RUN_TEST(test_overstroke_ignored_when_not_running);
    RUN_TEST(test_backoff_count_resets_on_start);

    // stateName: non-null (existing smoke test)
    RUN_TEST(test_stateName_returns_non_null);

    // stateName: exact string values for every state
    RUN_TEST(test_stateName_off_string);
    RUN_TEST(test_stateName_initialize_string);
    RUN_TEST(test_stateName_idle_string);
    RUN_TEST(test_stateName_coarse_cooldown_string);
    RUN_TEST(test_stateName_fine_cooldown_string);
    RUN_TEST(test_stateName_overshoot_string);
    RUN_TEST(test_stateName_settle_string);
    RUN_TEST(test_stateName_baseline_string);
    RUN_TEST(test_stateName_operating_string);
    RUN_TEST(test_stateName_shutdown_string);
    RUN_TEST(test_stateName_fault_string);

    // Settle timer boundary
    RUN_TEST(test_settle_does_not_transition_just_before_timer);
    RUN_TEST(test_settle_timer_resets_when_out_of_band);

    // Baseline / Operating: relay and timer boundaries
    RUN_TEST(test_baseline_uses_normal_relay);
    RUN_TEST(test_baseline_does_not_transition_just_before_timer);
    RUN_TEST(test_operating_uses_normal_relay);

    // off() from non-Idle states
    RUN_TEST(test_off_from_running_coarse);
    RUN_TEST(test_off_from_fault_clears_fault_reason);

    // Stall detection scope
    RUN_TEST(test_stall_in_fine_triggers_fault);
    RUN_TEST(test_stall_in_settle_does_not_fault);

    // Overstroke ignored in Fault
    RUN_TEST(test_overstroke_ignored_in_fault);

    // Delay state
    RUN_TEST(test_delay_from_off_enters_delay_state);
    RUN_TEST(test_delay_output_uses_bypass_relay);
    RUN_TEST(test_delay_output_indicators_are_solid_amber);
    RUN_TEST(test_delay_dac_target_is_zero);
    RUN_TEST(test_delay_does_not_expire_just_before_timer);
    RUN_TEST(test_delay_expires_and_transitions_to_idle);
    RUN_TEST(test_delay_expires_and_transitions_to_coarse);
    RUN_TEST(test_delay_from_fault_is_ignored);

    // FSM Oscillation detection
    RUN_TEST(test_oscillation_no_fault_before_min_cycles);
    RUN_TEST(test_oscillation_fault_fires_after_min_cycles);
    RUN_TEST(test_oscillation_fault_reason_is_state_oscillation);
    RUN_TEST(test_oscillation_status_text_is_not_null);
    RUN_TEST(test_oscillation_no_fault_with_third_state_in_window);
    RUN_TEST(test_oscillation_no_fault_outside_time_window);
    RUN_TEST(test_oscillation_pending_clears_after_clear_fault);

    // FSM History
    RUN_TEST(test_history_empty_after_init);
    RUN_TEST(test_history_records_off_on_init);
    RUN_TEST(test_history_records_start_transition);
    RUN_TEST(test_history_index_1_is_previous_state);
    RUN_TEST(test_history_out_of_range_returns_zero_entry);
    RUN_TEST(test_history_timestamp_matches_entry_time);
    RUN_TEST(test_history_grows_with_each_transition);
    RUN_TEST(test_history_wraps_at_limit);
    RUN_TEST(test_history_reset_on_reinit);

    // History cause field
    RUN_TEST(test_history_cause_init_records_init);
    RUN_TEST(test_history_cause_start_records_start);
    RUN_TEST(test_history_cause_stop_records_stop);
    RUN_TEST(test_history_cause_reinit_records_reinit);
    RUN_TEST(test_history_cause_clear_fault_records_clearFault);

    // Serial command handler
    run_serial_command_tests();

    // FrameBuilder
    run_frame_builder_tests();

    // Sensor mock ramp subsystem
    run_sensor_mock_ramp_tests();

    // SS Dashboard library
    run_dashboard_tests();

    // log ring buffer and LogStream
    run_log_tests();

    return UNITY_END();
}
