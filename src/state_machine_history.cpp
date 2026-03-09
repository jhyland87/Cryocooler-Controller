/**
 * @file state_machine_history.cpp
 * @brief FSM state-transition history and fault history ring buffers.
 *
 * Owns the two ring buffers that record every state entry (FSM_HISTORY_LIMIT
 * slots) and every Fault-state entry (FAULT_HISTORY_LIMIT slots).
 * Also owns the oscillation detector and the deferred oscillation-fault flag.
 *
 * The internal interface (histXxx functions) is declared in
 * state_machine_history.h and is used exclusively by state_machine.cpp.
 * The public accessor functions (getHistoryCount, getHistoryEntry, etc.)
 * are declared in include/state_machine.h and called by commands / dashboard.
 */

#include "state_machine_history.h"
#include "config.h"

#include <time.h>
#include <stdio.h>
#include <string.h>

namespace state_machine {

// ---------------------------------------------------------------------------
// FSM state-transition history ring buffer
// historyHead always points to the next write slot; the most recent entry
// is at (historyHead - 1 + FSM_HISTORY_LIMIT) % FSM_HISTORY_LIMIT.
// ---------------------------------------------------------------------------
static HistoryEntry history[FSM_HISTORY_LIMIT] = {};
static uint8_t      historyHead  = 0;
static uint8_t      historyCount = 0;

// ---------------------------------------------------------------------------
// Fault history ring buffer — one record per Fault-state entry.
// faultHistoryHead points to the next write slot.
// ---------------------------------------------------------------------------
static FaultRecord faultHistory[FAULT_HISTORY_LIMIT] = {};
static uint8_t     faultHistoryHead  = 0;
static uint8_t     faultHistoryCount = 0;

// Cause label set just before every fsm->trigger() call; consumed (stored
// into the HistoryEntry and reset to nullptr) by histPushHistory().
static const char* pendingCause = nullptr;

// Set by checkOscillation(); consumed by histTakeOscillationFaultPending()
// at the top of the next update() tick to avoid re-entrant FSM calls from
// inside an on_enter callback.
static bool oscillationFaultPending = false;

// ---------------------------------------------------------------------------
// Internal ring-buffer accessors.  i = 0 → most recent entry.
// ---------------------------------------------------------------------------
static inline const HistoryEntry& ringAt(uint8_t i) {
    const uint8_t idx = static_cast<uint8_t>(
        (static_cast<uint16_t>(FSM_HISTORY_LIMIT) + historyHead - 1u - i)
        % static_cast<uint8_t>(FSM_HISTORY_LIMIT));
    return history[idx];
}

static inline FaultRecord& faultRingAt(uint8_t i) {
    const uint8_t idx = static_cast<uint8_t>(
        (static_cast<uint16_t>(FAULT_HISTORY_LIMIT) + faultHistoryHead - 1u - i)
        % static_cast<uint8_t>(FAULT_HISTORY_LIMIT));
    return faultHistory[idx];
}

// ---------------------------------------------------------------------------
// Oscillation detector — called after every state push.
//
// Examines the last (FSM_OSCILLATION_MIN_CYCLES * 2) history entries.
// If they all alternate between exactly two non-trivial states AND all
// occurred within FSM_OSCILLATION_WINDOW_MS, sets oscillationFaultPending.
// ---------------------------------------------------------------------------
static void checkOscillation() {
    const uint8_t window =
        static_cast<uint8_t>(FSM_OSCILLATION_MIN_CYCLES) * static_cast<uint8_t>(2u);
    if (historyCount < window) return;

    const State stateEven = ringAt(0).state;  // most recent
    const State stateOdd  = ringAt(1).state;  // previous

    // Two distinct, non-trivial states are required.
    if (stateEven == stateOdd) return;
    if (stateEven == State::Off        || stateOdd == State::Off)        return;
    if (stateEven == State::Initialize || stateOdd == State::Initialize) return;
    if (stateEven == State::Fault      || stateOdd == State::Fault)      return;

    // All entries in the window must alternate between exactly those two states.
    for (uint8_t i = 0; i < window; ++i) {
        const State expected = (i % 2u == 0u) ? stateEven : stateOdd;
        if (ringAt(i).state != expected) return;
    }

    // All transitions must have occurred within the configured time window.
    const uint32_t newest = ringAt(0).enteredMs;
    const uint32_t oldest = ringAt(static_cast<uint8_t>(window - 1u)).enteredMs;
    if ((newest - oldest) > static_cast<uint32_t>(FSM_OSCILLATION_WINDOW_MS)) return;

    oscillationFaultPending = true;
}

// ---------------------------------------------------------------------------
// Internal interface — called by state_machine.cpp
// ---------------------------------------------------------------------------

void histSetPendingCause(const char* cause) {
    pendingCause = cause;
}

void histPushHistory(State s, uint32_t enteredMs) {
    history[historyHead] = { s, enteredMs, time(nullptr), pendingCause };
    pendingCause = nullptr;
    historyHead = static_cast<uint8_t>(
        (static_cast<uint16_t>(historyHead) + 1u) % FSM_HISTORY_LIMIT);
    if (historyCount < static_cast<uint8_t>(FSM_HISTORY_LIMIT)) {
        ++historyCount;
    }
    checkOscillation();
}

bool histTakeOscillationFaultPending() {
    const bool val = oscillationFaultPending;
    oscillationFaultPending = false;
    return val;
}

void histPushFaultRecord(FaultReason r, uint32_t enteredMs) {
    faultHistory[faultHistoryHead] = { r, enteredMs, time(nullptr), 0, 0, nullptr };
    faultHistoryHead = static_cast<uint8_t>(
        (static_cast<uint16_t>(faultHistoryHead) + 1u) % FAULT_HISTORY_LIMIT);
    if (faultHistoryCount < static_cast<uint8_t>(FAULT_HISTORY_LIMIT)) {
        ++faultHistoryCount;
    }
}

void histCloseFaultRecord(uint32_t clearedMs) {
    if (faultHistoryCount == 0) return;
    FaultRecord& rec = faultRingAt(0);
    rec.clearedMs    = clearedMs;
    rec.clearedEpoch = time(nullptr);
    rec.clearedBy    = pendingCause ? pendingCause : "unknown";
}

void histReset() {
    historyHead             = 0;
    historyCount            = 0;
    pendingCause            = nullptr;
    oscillationFaultPending = false;
    faultHistoryHead        = 0;
    faultHistoryCount       = 0;
}

// ---------------------------------------------------------------------------
// Public API — declared in include/state_machine.h
// ---------------------------------------------------------------------------

uint8_t getHistoryCount() {
    return historyCount;
}

HistoryEntry getHistoryEntry(uint8_t i) {
    if (i >= historyCount) return HistoryEntry{};
    return ringAt(i);
}

uint8_t getFaultHistoryCount() {
    return faultHistoryCount;
}

FaultRecord getFaultRecord(uint8_t i) {
    if (i >= faultHistoryCount) return FaultRecord{};
    return faultRingAt(i);
}

void formatFaultReasons(FaultReason r, char* buf, size_t len) {
    if (len == 0) return;
    const uint8_t mask = static_cast<uint8_t>(r);
    if (mask == 0u) {
        snprintf(buf, len, "None");
        return;
    }
    buf[0] = '\0';
    bool first = true;
    // Iterate bits in a fixed priority order so the output is deterministic.
    static const struct { FaultReason bit; const char* name; } kBits[] = {
        { FaultReason::RmsOvervoltage,   "RmsOvervoltage"   },
        { FaultReason::TemperatureStall, "TemperatureStall" },
        { FaultReason::TooManyBackoffs,  "TooManyBackoffs"  },
        { FaultReason::LowSystemVoltage, "LowSystemVoltage" },
        { FaultReason::StateOscillation, "StateOscillation" },
        { FaultReason::SensorFault,      "SensorFault"      },
        { FaultReason::RmsOvercurrent,   "RmsOvercurrent"   },
        { FaultReason::ModuleNotReady,   "ModuleNotReady"   },
    };
    for (const auto& b : kBits) {
        if ((mask & static_cast<uint8_t>(b.bit)) == 0u) continue;
        if (!first) strncat(buf, "|", len - strlen(buf) - 1u);
        strncat(buf, b.name, len - strlen(buf) - 1u);
        first = false;
    }
}

uint8_t countRecentFaults(uint32_t windowMs, uint32_t nowMs) {
    uint8_t count = 0;
    for (uint8_t i = 0; i < faultHistoryCount; ++i) {
        const FaultRecord& rec = faultRingAt(i);
        if ((nowMs - rec.enteredMs) <= windowMs) {
            ++count;
        }
    }
    return count;
}

}  // namespace state_machine
