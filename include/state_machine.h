/**
 * @file state_machine.h
 * @brief Cryocooler system state machine
 *
 * Implements the ten-state control sequence:
 *
 *   -1 Off           - System powered down (not running)
 *    0 Initialize    - Power-up: AMBER flash, relay Bypass, DAC = 0
 *    1 Idle          - Warm / standby: FAULT RED, relay Bypass, DAC = 0
 *    2 CoarseCooldown - Cooling above 85 K: FAULT flash fast RED, ramp DAC
 *    3 FineCooldown   - Cooling below 85 K: + READY flash slow GREEN
 *    4 Overshoot      - Below setpoint, integrator settling: READY flash fast GREEN
 *    5 Settle         - Near setpoint, Normal relay engaged
 *    6 Baseline       - Collecting baseline: READY ON GREEN
 *    7 Operating      - Normal run: READY ON GREEN
 *    8 Shutdown       - Graceful stop: ramp DAC to 0 over ~5 seconds, then → Idle
 *    9 Delay          - Timed wait: hold for N ms, then advance to configured next state
 *  127 Fault          - Any fault condition: FAULT flash fast RED, alarm relay active (terminal state)
 *
 * Transition inputs on every update() call:
 *   - tempK          : current cold-stage temperature in Kelvin
 *   - coolingRate    : K/min (positive = cooling)
 *   - rmsVoltage     : measured RMS voltage (stub; 0.0 until implemented)
 *   - stalled        : true when temp has not dropped enough in STALL_DETECT_WINDOW_MS
 *   - nowMs          : current millis()
 *
 * The module is pure logic — no Serial or hardware calls — so it can be
 * unit-tested on the native (host-PC) platform.
 */

#ifndef STATE_MACHINE_H
#define STATE_MACHINE_H

#include <stdint.h>
#include <time.h>
#include "config.h"
#include "indicator.h"
#include "module.h"

namespace state_machine {

/**
 * X-macro table for all system states.
 * Each row:  X(enumerator, int8_t value, short name, status text)
 *
 * The status text for State::Fault is dynamic (it depends on the active
 * FaultReason) and is handled separately in statusTextForState() inside
 * state_machine.cpp.  nullptr is used here as an explicit sentinel; it is
 * never returned to callers at runtime.
 *
 * Usage patterns
 * ──────────────
 * Generate the enum body:
 *   #define X(name, value, sname, status) name = value,
 *   STATE_MACHINE_STATES(X)
 *   #undef X
 *
 * Generate a name-lookup switch:
 *   #define X(name, value, sname, status) case State::name: return sname;
 *   STATE_MACHINE_STATES(X)
 *   #undef X
 */
#define STATE_MACHINE_STATES(X)                                                                                              \
    X(Off,            -1,  "Off",            "System is off")                                                            \
    X(Initialize,      0,  "Initialize",     "Initial power up state")                                                   \
    X(Idle,            1,  "Idle",           "Cold stage is warm; dewar is not cooling")                                 \
    X(CoarseCooldown,  2,  "CoarseCooldown", "Cooling; cold stage is above 85K")                                         \
    X(FineCooldown,    3,  "FineCooldown",   "Cooling; cold stage is below 85K")                                         \
    X(Overshoot,       4,  "Overshoot",      "Cold stage is cooler than set point; integrator is settling")              \
    X(Settle,          5,  "Settle",         "Cold stage temperature is settling; circuits switched to Normal")           \
    X(Baseline,        6,  "Baseline",       "Cold stage temperature has settled; collecting baseline data")              \
    X(Operating,       7,  "Operating",      "System is operating normally; checking for deviations from baseline")      \
    X(Shutdown,        8,  "Shutdown",       "Gracefully shutting down; ramping DAC to zero")                            \
    X(Delay,           9,  "Delay",          "Timed wait; will advance to next state after delay expires")               \
    X(Fault,         127,  "Fault",          nullptr)   /* status text is computed at runtime — see statusTextForState() */

/** System states as per design spec.  Generated from STATE_MACHINE_STATES. */
enum class State : int8_t {
#define X(name, value, sname, status) name = value,
    STATE_MACHINE_STATES(X)
#undef X
};


/** Reason the system entered Fault state. */
enum class FaultReason : uint8_t {
    None              = 0,
    RmsOvervoltage    = 1,
    TemperatureStall  = 2,
    TooManyBackoffs   = 3,  ///< back-EMF backoff event count reached BACKOFF_MAX_COUNT
    LowSystemVoltage  = 4,  ///< DC supply voltage fell below MIN_SYSTEM_VOLTAGE_VDC
    StateOscillation  = 5,  ///< FSM bouncing between the same two states too many times
};

/** Aggregate output produced by update() each loop. */
struct Output {
    State            state;
    uint16_t         dacTarget;       ///< desired DAC value (before ramp limiting)
    bool             bypassRelay;     ///< true = Bypass, false = Normal
    bool             alarmRelay;      ///< true = alarm relay energised (Fault state)
    indicator::Mode  faultIndMode;    ///< desired mode for FAULT indicator
    indicator::Mode  readyIndMode;    ///< desired mode for READY indicator
    const char*      statusText;      ///< human-readable status description
    uint16_t         backoffCount;    ///< cumulative back-EMF backoff events since start()
};

/**
 * Initialise the state machine.
 * Must be called once in setup(); may also be called between tests to reset
 * all internal state.
 *
 * @param nowMs  Current millis() at the time of initialisation (defaults to 0
 *               so native unit tests that call init(0) compile without change).
 * @return MODULE_INIT_SUCCESS always (pure in-memory initialisation).
 */
module::InitStatus init(uint32_t nowMs = 0);

/** Return the duration of the current on state in milliseconds. */
uint32_t getOnStateDuration();

/**
 * Advance the state machine by one tick.
 *
 * @param tempK         Current cold-stage temperature in Kelvin
 * @param coolingRate   Measured cooling rate in K/min (positive = cooling)
 * @param rmsVoltage    Measured RMS voltage in VDC (stub returns 0)
 * @param stalled       True when stall-detection window has expired without a
 *                      sufficient temperature drop
 * @param nowMs         Current millis()
 * @param overstroke    True when the ACS712 detected a back-EMF current spike
 *                      this tick.  Triggers a DAC backoff and increments the
 *                      backoff counter in the returned Output.  Defaults to
 *                      false for backward compatibility.
 * @param systemVoltage DC supply voltage in volts.  Pass 0.0f (default) when
 *                      no measurement is available — 0.0f is treated as "not
 *                      monitored" and never triggers the LowSystemVoltage fault.
 *                      Any positive value below MIN_SYSTEM_VOLTAGE_VDC
 *                      immediately transitions to Fault from any state.
 * @return              Output struct with all actuator targets for this tick
 */
Output update(float    tempK,
              float    coolingRate,
              float    rmsVoltage,
              bool     stalled,
              uint32_t nowMs,
              bool     overstroke    = false,
              float    systemVoltage = 0.0f);


/** Return the current state without advancing the machine. */
State getState();

/** Return true if the process has been started and is actively running. */
bool isRunning();

/**
 * Start (or resume) the cooldown process.
 *
 * The starting state is chosen based on the current cold-stage temperature
 * so the system can resume correctly after a reboot without triggering
 * spurious stall faults:
 *
 *   tempK >= COARSE_FINE_THRESHOLD_K  →  CoarseCooldown  (normal warm start)
 *   tempK in setpoint band            →  Settle           (already at temperature)
 *   tempK below setpoint band         →  Overshoot        (integrator settling)
 *   tempK below threshold but above   →  FineCooldown
 *     setpoint band
 *
 * Has no effect if the machine is already running.
 *
 * @param nowMs   Current millis()
 * @param tempK   Current cold-stage temperature in Kelvin.
 *                Defaults to AMBIENT_START_K (warm start / unknown temp).
 */
void start(uint32_t nowMs, float tempK = AMBIENT_START_K);

/**
 * Stop the cooldown process and return to Idle via the Shutdown ramp.
 * DAC target drops to 0, relay returns to Bypass.
 * Has no effect during Initialize or when the machine is not running.
 *
 * @param nowMs  Current millis()
 */
void stop(uint32_t nowMs);

/**
 * Clear an active fault and return the machine to Idle.
 *
 * This is the only path out of State::Fault (other than off()).
 * On exit from Fault the following actions are taken:
 *   - faultReason is reset to FaultReason::None
 *   - backoff counter and DAC offset are reset to zero
 *   - running flag is left false (operator must call start() to resume)
 *
 * Has no effect when the machine is not in State::Fault.
 *
 * @param nowMs  Current millis()
 */
void clearFault(uint32_t nowMs);

/**
 * Enter the generic Delay state for a fixed duration, then advance to
 * @p nextState automatically.
 *
 * Supported destinations:
 *   State::Idle           — return to standby after the wait
 *   State::CoarseCooldown — resume cooling from the top of the ramp
 *
 * Any other @p nextState value is treated as State::Idle.
 *
 * Can be called from any non-Fault state.  Has no effect if the machine
 * is currently in State::Fault.
 *
 * @param nowMs       Current millis()
 * @param durationMs  How long to hold in the Delay state (milliseconds)
 * @param nextState   The state to enter when the delay expires
 */
void startDelay(uint32_t nowMs, uint32_t durationMs, State nextState = State::Idle);

void off(uint32_t nowMs);

/**
 * Return a short ASCII name for a state (safe for Serial / telemetry).
 * Generated from STATE_MACHINE_STATES — add or rename states there, not here.
 */
inline const char* stateName(State s) {
    switch (s) {
#define X(name, value, sname, status) case State::name: return sname;
        STATE_MACHINE_STATES(X)
#undef X
    }
    return "Unknown";
}

/**
 * Register a callback invoked synchronously when the FSM enters the
 * Initialize state (on_enter).  Use this in main.cpp to re-run control
 * module initialisation every time the machine is re-initialised.
 * Pass nullptr to clear the callback.
 *
 * The callback executes from within fsm->trigger() on the call stack of
 * reinit(), so it may block for as long as the module inits require.
 */
void setOnInitializeCallback(void (*cb)());

/**
 * Reset all FSM state and transition to the Initialize state.
 *
 * Fully equivalent to calling Module::init() (fresh FSM at Off) followed
 * immediately by the Off → Initialize transition.  If an onInitialize
 * callback has been registered via setOnInitializeCallback(), it is invoked
 * synchronously as part of entering Initialize.
 *
 * Typical use:
 *   - At startup: after state_machine::Module::init() and
 *     setOnInitializeCallback(), call reinit(millis()) to kick off the
 *     control-module init sequence without a separate setupModules() loop.
 *   - At runtime: call off() or stop() to bring the machine to a safe state
 *     first, then call reinit(nowMs) to re-run hardware module inits and
 *     return to Idle.
 *
 * @param nowMs  Current millis()
 */
void reinit(uint32_t nowMs);

/** Return the current fault reason (FaultReason::None if not in Fault). */
FaultReason getFaultReason();

// ── FSM History ───────────────────────────────────────────────────────────────

/** A single FSM history record — one state transition. */
struct HistoryEntry {
    State       state;        ///< state that was entered
    uint32_t    enteredMs;    ///< millis() at which the transition occurred (always valid)
    time_t      enteredEpoch; ///< wall-clock Unix timestamp at entry (0 = SNTP not yet synced)
    const char* cause;        ///< what triggered this transition (static string literal, may be nullptr)
};

/**
 * Return the number of history entries currently stored.
 * Starts at 0, grows up to FSM_HISTORY_LIMIT, then wraps (oldest overwritten).
 */
uint8_t getHistoryCount();

/**
 * Return a single history entry by recency index.
 * @param i  0 = most recent entry, 1 = second most recent, …
 * @return   The requested entry, or a zero-initialised entry if i >= getHistoryCount().
 */
HistoryEntry getHistoryEntry(uint8_t i);

/** Return a short ASCII status text for the current state (safe for Serial / telemetry). */
const char* getStatusText();

/**
 * Return how long the machine has been in its current state, in milliseconds.
 * The counter resets to zero on every state transition.
 */
uint32_t getTimeInState();

// ── Module interface ──────────────────────────────────────────────────────────
//
// state_machine::update() requires sensor inputs so it cannot map to service().
// Module::service() inherits the default no-op; update() is called explicitly
// from the main control tick with the current sensor snapshot.

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = state_machine::init(); }
    // service() — inherited no-op; update() is called explicitly from loop().
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace state_machine

#endif // STATE_MACHINE_H
