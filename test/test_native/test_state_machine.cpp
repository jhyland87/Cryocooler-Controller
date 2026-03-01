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

// FrameBuilder tests (defined in test_frame_builder.cpp)
void run_frame_builder_tests();

// Dashboard tests (defined in test_ss_dashboard.cpp)
void run_dashboard_tests();

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
 * Since stop() now transitions to Shutdown first, this helper advances through
 * the shutdown duration to reach Idle.
 *
 * @return  The nowMs timestamp at which Idle was entered.
 */
static uint32_t initStartAndStop() {
    const uint32_t tStart = initAndStart();
    const uint32_t tStop  = tStart + 1000;
    state_machine::stop(tStop);
    // Shutdown lasts SHUTDOWN_DURATION_MS; advance past it to reach Idle
    const uint32_t tIdle = tStop + SHUTDOWN_DURATION_MS;
    stub_setMillis(tIdle);
    state_machine::update(295.0f, 0.0f, 0.0f, false, tIdle);
    return tIdle;
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
    // NOTE: stop() now enters Shutdown state first, which then transitions to Idle
    // after SHUTDOWN_DURATION_MS. This test verifies the immediate transition to Shutdown.
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    state_machine::stop(tStart + 1000);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
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
// getTimeInState
// ---------------------------------------------------------------------------

void test_time_in_state_zero_at_init(void) {
    // init() enters Off at t=0 with millis()=0, so duration is 0.
    state_machine::init(0);
    stub_setMillis(0);
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getTimeInState());
}

void test_time_in_state_grows_while_in_same_state(void) {
    state_machine::init(0);
    stub_setMillis(2500);
    TEST_ASSERT_EQUAL_UINT32(2500, state_machine::getTimeInState());
}

void test_time_in_state_resets_to_zero_on_transition(void) {
    // start() transitions Off → CoarseCooldown at t=100; timer resets.
    state_machine::init(0);
    stub_setMillis(100);
    state_machine::start(100);
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getTimeInState());
}

void test_time_in_state_accumulates_after_transition(void) {
    state_machine::init(0);
    stub_setMillis(100);
    state_machine::start(100);   // CoarseCooldown entered at t=100
    stub_setMillis(750);
    TEST_ASSERT_EQUAL_UINT32(650, state_machine::getTimeInState());
}

void test_time_in_state_resets_again_on_stop(void) {
    state_machine::init(0);
    state_machine::start(100);   // CoarseCooldown @ 100
    state_machine::stop(600);    // Idle @ 600; timer resets
    stub_setMillis(600);
    TEST_ASSERT_EQUAL_UINT32(0, state_machine::getTimeInState());
    stub_setMillis(900);
    TEST_ASSERT_EQUAL_UINT32(300, state_machine::getTimeInState());
}

// ---------------------------------------------------------------------------
// Reboot recovery: start() selects the correct resume state from tempK
// ---------------------------------------------------------------------------

void test_start_warm_enters_coarse_cooldown(void) {
    // Ambient temperature → full cooldown from the top.
    state_machine::init(0);
    state_machine::start(100, AMBIENT_START_K);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_start_above_threshold_enters_coarse_cooldown(void) {
    // 90 K is above COARSE_FINE_THRESHOLD_K (85 K) → CoarseCooldown.
    state_machine::init(0);
    state_machine::start(100, 90.0f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_start_below_threshold_enters_fine_cooldown(void) {
    // 82 K is below COARSE_FINE_THRESHOLD_K (85 K) but above the setpoint
    // tolerance band (> SETPOINT_K + SETPOINT_TOLERANCE_K = 80 K) → FineCooldown.
    state_machine::init(0);
    state_machine::start(100, 82.0f);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(state_machine::getState()));
}

void test_start_inband_enters_settle(void) {
    // Exactly at setpoint → skip cooldown, enter Settle with relay Normal.
    state_machine::init(0);
    state_machine::start(100, SETPOINT_K);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(state_machine::getState()));
    // Relay must be Normal (bypassRelay == false) in Settle.
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, 101);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
}

void test_start_overshot_enters_overshoot(void) {
    // 1 K below the tolerance band (< SETPOINT_K - SETPOINT_TOLERANCE_K = 76 K)
    // → Overshoot; DAC target must be 0.
    state_machine::init(0);
    const float overshootTemp = SETPOINT_K - SETPOINT_TOLERANCE_K - 1.0f;
    state_machine::start(100, overshootTemp);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Overshoot),
                      static_cast<int8_t>(state_machine::getState()));
    auto out = state_machine::update(overshootTemp, 0.0f, 0.0f, false, 101);
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

void test_start_resume_fine_no_stall_fault(void) {
    // On a fresh reboot, stalled is always false (no history yet).
    // Resuming into FineCooldown with a stable cold temperature must NOT fault.
    state_machine::init(0);
    state_machine::start(100, 82.0f);  // → FineCooldown
    auto out = state_machine::update(82.0f, 0.0f, 0.0f, false, 101);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(out.alarmRelay);
}

// ---------------------------------------------------------------------------
// Back-EMF backoff: overstroke detection → DAC reduction → fault
// ---------------------------------------------------------------------------

void test_overstroke_increments_backoff_count(void) {
    // One overstroke while running: backoffCount in Output should be 1.
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1, true);
    TEST_ASSERT_EQUAL_UINT16(1, out.backoffCount);
}

void test_overstroke_reduces_dac_target(void) {
    // The DAC target after one backoff must be reduced by exactly BACKOFF_DAC_STEP
    // compared to the same temperature without a backoff.
    const uint32_t tStart = initAndStart();
    const auto baseOut    = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1, false);
    const auto backoffOut = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 2, true);

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
        out = state_machine::update(200.0f, 0.5f, 0.0f, false,
                                    tStart + 1u + i, true);
    }
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_TRUE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::TooManyBackoffs),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_overstroke_ignored_when_not_running(void) {
    // An overstroke event while in Off state must be silently ignored.
    state_machine::init(0);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, 1, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.backoffCount);
    TEST_ASSERT_FALSE(out.alarmRelay);
}

void test_backoff_count_resets_on_start(void) {
    // Accumulate backoffs up to (MAX - 1) so we stay just below the fault
    // threshold.  After stop() + start() the count must reset to zero.
    const uint32_t tStart = initAndStart();
    for (uint8_t i = 0; i < BACKOFF_MAX_COUNT - 1u; ++i) {
        state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1u + i, true);
    }
    state_machine::stop(tStart + 500u);
    state_machine::start(tStart + 600u);
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 601u, false);
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
    state_machine::init(0);
    state_machine::start(0, SETPOINT_K);   // enters Settle directly

    // First in-band call starts the settle timer at t = 1.
    state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, 1);

    // One tick before expiry: elapsed = SETTLE_DURATION_MS - 1 → stay in Settle.
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false,
                                     SETTLE_DURATION_MS);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(out.state));
}

/**
 * If temperature drifts out of band the settle timer resets.
 * After re-entering the band the full SETTLE_DURATION_MS must elapse again
 * before the transition to Baseline fires.
 */
void test_settle_timer_resets_when_out_of_band(void) {
    state_machine::init(0);
    state_machine::start(0, SETPOINT_K);

    // Start settle timer at t = 1.
    state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, 1);

    // Drift out of band — timer resets.
    state_machine::update(COARSE_FINE_THRESHOLD_K, 0.0f, 0.0f, false, 100);

    // Re-enter band at t = 200 — timer restarts from here.
    state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, 200);

    // One tick before the restarted timer would fire: must still be Settle.
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false,
                                     200 + SETTLE_DURATION_MS - 1);
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
    state_machine::init(0);
    state_machine::start(0, SETPOINT_K);            // → Settle at t = 0

    // Start settle timer at t = 1, then fire it.
    state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, 1);
    const uint32_t baselineEntryMs = 1u + SETTLE_DURATION_MS;
    state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, baselineEntryMs);
    return baselineEntryMs;
}

void test_baseline_uses_normal_relay(void) {
    const uint32_t baselineEntry = advanceToBaseline();
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false,
                                     baselineEntry + 1u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Baseline),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
}

/** One tick before BASELINE_DURATION_MS expires the machine must stay in Baseline. */
void test_baseline_does_not_transition_just_before_timer(void) {
    const uint32_t baselineEntry = advanceToBaseline();
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false,
                                     baselineEntry + BASELINE_DURATION_MS - 1u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Baseline),
                      static_cast<int8_t>(out.state));
}

void test_operating_uses_normal_relay(void) {
    const uint32_t baselineEntry = advanceToBaseline();
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false,
                                     baselineEntry + BASELINE_DURATION_MS);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Operating),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
}

// ---------------------------------------------------------------------------
// State: Shutdown
// ---------------------------------------------------------------------------

void test_stop_enters_shutdown(void) {
    // stop() from a running state should transition to Shutdown, not Idle
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(state_machine::getState()));
    state_machine::stop(tStart + 1000);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_shutdown_returns_dac_zero(void) {
    // Shutdown state should target DAC = 0 to allow rampToward() to gradually reduce
    const uint32_t tStart = initAndStart();
    state_machine::stop(tStart + 1000);
    const auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, tStart + 1001);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(0, out.dacTarget);
}

void test_shutdown_uses_bypass_relay(void) {
    const uint32_t tStart = initAndStart();
    state_machine::stop(tStart + 1000);
    const auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, tStart + 1001);
    TEST_ASSERT_TRUE(out.bypassRelay);
}

void test_shutdown_duration_then_transitions_to_idle(void) {
    const uint32_t tStart = initAndStart();
    state_machine::stop(tStart + 1000);
    // Just before SHUTDOWN_DURATION_MS elapses, should still be in Shutdown
    const uint32_t beforeExpiry = tStart + 1000 + SHUTDOWN_DURATION_MS - 1;
    stub_setMillis(beforeExpiry);
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, beforeExpiry);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Shutdown),
                      static_cast<int8_t>(out.state));

    // After SHUTDOWN_DURATION_MS elapses, should transition to Idle
    const uint32_t afterExpiry = tStart + 1000 + SHUTDOWN_DURATION_MS;
    stub_setMillis(afterExpiry);
    out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, false, afterExpiry);
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
    state_machine::off(tStart + 100u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Off),
                      static_cast<int8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_off_from_fault_clears_fault_reason(void) {
    // off() is the only way out of Fault (stop() is a no-op when running==false).
    const uint32_t tStart = initAndStart();
    state_machine::update(200.0f, 0.5f, RMS_MAX_VOLTAGE_VDC + 1.0f,
                           false, tStart + 1u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));

    state_machine::off(tStart + 2u);
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
    state_machine::update(COARSE_FINE_THRESHOLD_K - 1.0f, 0.5f, 0.0f,
                           false, tStart + 1u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::FineCooldown),
                      static_cast<int8_t>(state_machine::getState()));

    // Stall while in FineCooldown → Fault(TemperatureStall).
    auto out = state_machine::update(COARSE_FINE_THRESHOLD_K - 1.0f, 0.5f, 0.0f,
                                      true, tStart + 2u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::TemperatureStall),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_stall_in_settle_does_not_fault(void) {
    // Stall is only checked in CoarseCooldown and FineCooldown.
    // In Settle (reached by resuming at setpoint) it must be silently ignored.
    state_machine::init(0);
    state_machine::start(0, SETPOINT_K);   // → Settle directly
    auto out = state_machine::update(SETPOINT_K, 0.0f, 0.0f, true, 1u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Settle),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_FALSE(out.alarmRelay);
}

// ---------------------------------------------------------------------------
// Overstroke ignored while already in Fault
// ---------------------------------------------------------------------------

void test_overstroke_ignored_in_fault(void) {
    // Fault blocks the entire global-fault / overstroke section of update().
    const uint32_t tStart = initAndStart();
    // Trigger a fault.
    state_machine::update(200.0f, 0.5f, RMS_MAX_VOLTAGE_VDC + 1.0f,
                           false, tStart + 1u);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));

    // Overstroke while in Fault — must not change state or increment backoffCount.
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 2u, true);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
    TEST_ASSERT_EQUAL_UINT16(0, out.backoffCount);
    TEST_ASSERT_TRUE(out.alarmRelay);
}

// ---------------------------------------------------------------------------
// Delay state
// ---------------------------------------------------------------------------

/** Returns a millisecond timestamp just after init() so tests can use it. */
static uint32_t initState() {
    state_machine::init(1000);
    return 1000;
}

void test_delay_from_off_enters_delay_state(void) {
    const uint32_t t0 = initState();
    state_machine::startDelay(t0, 500, state_machine::State::Idle);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Delay),
                      static_cast<int8_t>(out.state));
}

void test_delay_output_uses_bypass_relay(void) {
    const uint32_t t0 = initState();
    state_machine::startDelay(t0, 500, state_machine::State::Idle);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 1);
    TEST_ASSERT_TRUE(out.bypassRelay);
}

void test_delay_output_indicators_are_solid_amber(void) {
    const uint32_t t0 = initState();
    state_machine::startDelay(t0, 500, state_machine::State::Idle);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 1);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidAmber),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidAmber),
                      static_cast<uint8_t>(out.readyIndMode));
}

void test_delay_dac_target_is_zero(void) {
    const uint32_t t0 = initState();
    state_machine::startDelay(t0, 500, state_machine::State::Idle);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 1);
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

void test_delay_does_not_expire_just_before_timer(void) {
    const uint32_t t0 = initState();
    state_machine::startDelay(t0, 500, state_machine::State::Idle);
    // Advance to just before the deadline.
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 499);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Delay),
                      static_cast<int8_t>(out.state));
}

void test_delay_expires_and_transitions_to_idle(void) {
    const uint32_t t0 = initState();
    state_machine::startDelay(t0, 500, state_machine::State::Idle);
    // Hold just before expiry.
    state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 499);
    // Cross the threshold.
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 500);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Idle),
                      static_cast<int8_t>(out.state));
}

void test_delay_expires_and_transitions_to_coarse(void) {
    const uint32_t t0 = initState();
    state_machine::startDelay(t0, 200, state_machine::State::CoarseCooldown);
    state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 199);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 200);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::CoarseCooldown),
                      static_cast<int8_t>(out.state));
}

void test_delay_from_fault_is_ignored(void) {
    const uint32_t t0 = initState();
    // Trigger a fault first.
    state_machine::start(t0, 300.0f);
    state_machine::update(300.0f, 0.0f, RMS_MAX_VOLTAGE_VDC + 1.0f, false, t0 + 1);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(state_machine::getState()));
    // startDelay() must be a no-op in Fault.
    state_machine::startDelay(t0 + 2, 100, state_machine::State::Idle);
    auto out = state_machine::update(300.0f, 0.0f, 0.0f, false, t0 + 3);
    TEST_ASSERT_EQUAL(static_cast<int8_t>(state_machine::State::Fault),
                      static_cast<int8_t>(out.state));
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

    // Serial command handler
    run_serial_command_tests();

    // FrameBuilder
    run_frame_builder_tests();

    // SS Dashboard library
    run_dashboard_tests();

    return UNITY_END();
}
