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
        auto out = state_machine::update(tempK, coolingRate, rmsV, stalled, nowMs);
        if (out.state == target) return nowMs;
        nowMs += stepMs;
    }
    return 0;  // did not reach target
}

/**
 * Helper: init the state machine, advance through Initialize → Idle,
 * then call start() to enter CoarseCooldown.
 *
 * @return  The nowMs timestamp at which CoarseCooldown was entered.
 */
static uint32_t initAndStart() {
    state_machine::init(0);
    // Advance past Initialize → Idle
    state_machine::update(295.0f, 0.0f, 0.0f, false, INDICATOR_INIT_AMBER_MS);
    // Start the process
    const uint32_t tStart = INDICATOR_INIT_AMBER_MS + 100;
    state_machine::start(tStart);
    return tStart;
}

// ---------------------------------------------------------------------------
// setUp / tearDown
// ---------------------------------------------------------------------------

void setUp(void) {
    // Re-initialise the state machine before each test so tests are isolated
    state_machine::init(0);
}

void tearDown(void) {}

// ---------------------------------------------------------------------------
// State: Initialize
// ---------------------------------------------------------------------------

void test_init_starts_in_initialize(void) {
    state_machine::init(0);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Initialize),
                      static_cast<uint8_t>(state_machine::getState()));
}

void test_initialize_output_is_bypass_and_amber(void) {
    state_machine::init(0);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, 0);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Initialize),
                      static_cast<uint8_t>(out.state));
    TEST_ASSERT_TRUE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidAmber),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidAmber),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
    TEST_ASSERT_NOT_NULL(out.statusText);
}

void test_initialize_transitions_to_idle_after_amber_period(void) {
    state_machine::init(0);
    // Still in Initialize just before period elapses
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false,
                                     INDICATOR_INIT_AMBER_MS - 1);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Initialize),
                      static_cast<uint8_t>(out.state));
    // Transitions to Idle at exactly INDICATOR_INIT_AMBER_MS
    out = state_machine::update(295.0f, 0.0f, 0.0f, false, INDICATOR_INIT_AMBER_MS);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Idle),
                      static_cast<uint8_t>(out.state));
}

// ---------------------------------------------------------------------------
// State: Idle -- stays until start() is called
// ---------------------------------------------------------------------------

void test_idle_output_is_fault_red_bypass(void) {
    state_machine::init(0);
    // Jump past Initialize
    state_machine::update(295.0f, 0.0f, 0.0f, false, INDICATOR_INIT_AMBER_MS);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false,
                                     INDICATOR_INIT_AMBER_MS + 1);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Idle),
                      static_cast<uint8_t>(out.state));
    TEST_ASSERT_TRUE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::SolidRed),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    TEST_ASSERT_EQUAL_UINT16(0, out.dacTarget);
}

void test_idle_does_not_auto_transition(void) {
    state_machine::init(0);
    // Skip Initialize
    state_machine::update(295.0f, 0.0f, 0.0f, false, INDICATOR_INIT_AMBER_MS);
    // Even after a long time, stays in Idle without start()
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false,
                                     INDICATOR_INIT_AMBER_MS + 60000);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Idle),
                      static_cast<uint8_t>(out.state));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

// ---------------------------------------------------------------------------
// start() / stop() control
// ---------------------------------------------------------------------------

void test_start_from_idle_enters_coarse(void) {
    state_machine::init(0);
    state_machine::update(295.0f, 0.0f, 0.0f, false, INDICATOR_INIT_AMBER_MS);
    state_machine::start(INDICATOR_INIT_AMBER_MS + 100);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::CoarseCooldown),
                      static_cast<uint8_t>(state_machine::getState()));
    TEST_ASSERT_TRUE(state_machine::isRunning());
}

void test_start_ignored_when_not_idle(void) {
    state_machine::init(0);
    // Still in Initialize
    state_machine::start(0);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Initialize),
                      static_cast<uint8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_stop_returns_to_idle(void) {
    const uint32_t tStart = initAndStart();
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::CoarseCooldown),
                      static_cast<uint8_t>(state_machine::getState()));
    state_machine::stop(tStart + 1000);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Idle),
                      static_cast<uint8_t>(state_machine::getState()));
    TEST_ASSERT_FALSE(state_machine::isRunning());
}

void test_stop_clears_fault(void) {
    const uint32_t tStart = initAndStart();
    // Trigger RMS fault
    state_machine::update(200.0f, 0.5f, RMS_MAX_VOLTAGE_VDC + 1.0f,
                          false, tStart + 1);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Fault),
                      static_cast<uint8_t>(state_machine::getState()));
    // Stop should clear fault and return to Idle
    state_machine::stop(tStart + 2);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Idle),
                      static_cast<uint8_t>(state_machine::getState()));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::None),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_stop_ignored_during_initialize(void) {
    state_machine::init(0);
    state_machine::stop(0);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Initialize),
                      static_cast<uint8_t>(state_machine::getState()));
}

// ---------------------------------------------------------------------------
// State: CoarseCooldown
// ---------------------------------------------------------------------------

void test_coarse_cooldown_output(void) {
    const uint32_t tStart = initAndStart();
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, false, tStart + 1);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::CoarseCooldown),
                      static_cast<uint8_t>(out.state));
    TEST_ASSERT_TRUE(out.bypassRelay);
    TEST_ASSERT_FALSE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::FlashFastRed),
                      static_cast<uint8_t>(out.faultIndMode));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(indicator::Mode::Off),
                      static_cast<uint8_t>(out.readyIndMode));
    // DAC target must be > 0 when temp is below ambient
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

    // Temperature dips below COARSE_FINE_THRESHOLD_K
    auto out = state_machine::update(
        COARSE_FINE_THRESHOLD_K - 1.0f, 0.5f, 0.0f, false, tStart + 2);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::FineCooldown),
                      static_cast<uint8_t>(out.state));
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

    // Temp well below setpoint -> Overshoot
    const float overshootTemp = SETPOINT_K - SETPOINT_TOLERANCE_K - 1.0f;
    auto out = state_machine::update(overshootTemp, 0.5f, 0.0f, false, tStart + 3);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Overshoot),
                      static_cast<uint8_t>(out.state));
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
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Fault),
                      static_cast<uint8_t>(out.state));
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

    // Stall = true while in CoarseCooldown
    auto out = state_machine::update(200.0f, 0.5f, 0.0f, true, tStart + 1);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Fault),
                      static_cast<uint8_t>(out.state));
    TEST_ASSERT_TRUE(out.alarmRelay);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::FaultReason::TemperatureStall),
                      static_cast<uint8_t>(state_machine::getFaultReason()));
}

void test_stall_in_idle_does_not_trigger_fault(void) {
    state_machine::init(0);
    state_machine::update(295.0f, 0.0f, 0.0f, false, INDICATOR_INIT_AMBER_MS);
    // Idle, stalled = true — should NOT fault (stall only matters in cooldown)
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, true,
                                     INDICATOR_INIT_AMBER_MS + 1);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Idle),
                      static_cast<uint8_t>(out.state));
    TEST_ASSERT_FALSE(out.alarmRelay);
}

// ---------------------------------------------------------------------------
// Fault: terminal state (no auto-recovery, but stop() clears it)
// ---------------------------------------------------------------------------

void test_fault_stays_in_fault(void) {
    const uint32_t tStart = initAndStart();
    // Trigger fault
    state_machine::update(200.0f, 0.5f,
                           RMS_MAX_VOLTAGE_VDC + 1.0f,
                           false, tStart + 1);
    // Even with clean readings, still Fault
    auto out = state_machine::update(100.0f, 0.5f, 0.0f, false, tStart + 2);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(state_machine::State::Fault),
                      static_cast<uint8_t>(out.state));
}

// ---------------------------------------------------------------------------
// Relay: Normal mode only in states 5-7
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
    state_machine::init(0);
    auto out = state_machine::update(295.0f, 0.0f, 0.0f, false, 0);
    TEST_ASSERT_NOT_NULL(out.statusText);

    // Idle
    out = state_machine::update(295.0f, 0.0f, 0.0f, false, INDICATOR_INIT_AMBER_MS);
    TEST_ASSERT_NOT_NULL(out.statusText);
}

void test_fault_status_text_contains_reason(void) {
    const uint32_t tStart = initAndStart();
    // RMS fault
    auto out = state_machine::update(200.0f, 0.5f,
                                     RMS_MAX_VOLTAGE_VDC + 1.0f,
                                     false, tStart + 1);
    TEST_ASSERT_NOT_NULL(out.statusText);
    // Should contain "Fault:"
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
// stateName helper
// ---------------------------------------------------------------------------

void test_stateName_returns_non_null(void) {
    TEST_ASSERT_NOT_NULL(state_machine::stateName(state_machine::State::Initialize));
    TEST_ASSERT_NOT_NULL(state_machine::stateName(state_machine::State::Fault));
    TEST_ASSERT_NOT_NULL(state_machine::stateName(state_machine::State::Operating));
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

int main(int argc, char **argv) {
    UNITY_BEGIN();

    // Initialize state
    RUN_TEST(test_init_starts_in_initialize);
    RUN_TEST(test_initialize_output_is_bypass_and_amber);
    RUN_TEST(test_initialize_transitions_to_idle_after_amber_period);

    // Idle state
    RUN_TEST(test_idle_output_is_fault_red_bypass);
    RUN_TEST(test_idle_does_not_auto_transition);

    // Start / Stop control
    RUN_TEST(test_start_from_idle_enters_coarse);
    RUN_TEST(test_start_ignored_when_not_idle);
    RUN_TEST(test_stop_returns_to_idle);
    RUN_TEST(test_stop_clears_fault);
    RUN_TEST(test_stop_ignored_during_initialize);

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

    // Helpers
    RUN_TEST(test_stateName_returns_non_null);

    return UNITY_END();
}
