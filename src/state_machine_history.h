/**
 * @file state_machine_history.h
 * @brief Internal interface between state_machine.cpp and state_machine_history.cpp.
 *
 * Not part of the public API — for that, see include/state_machine.h.
 * This header is included only by state_machine.cpp.
 *
 * state_machine_history.cpp owns the two ring buffers (state-transition history
 * and fault records), the oscillation detector, and all public history/fault
 * accessor implementations.  state_machine.cpp drives those ring buffers
 * through the histXxx() functions declared here.
 */

#pragma once
#include "state_machine.h"  // State, FaultReason, HistoryEntry, FaultRecord

namespace state_machine {

/**
 * Set the cause label for the next FSM transition.
 * Must be called immediately before fsm->trigger() so that histPushHistory()
 * — which fires inside the synchronous on_enter callback — can store the
 * label in the HistoryEntry before resetting it to nullptr.
 */
void histSetPendingCause(const char* cause);

/**
 * Record a state entry in the FSM history ring buffer.
 * Called from setStateEntry() inside every on_enter callback.
 * Internally calls checkOscillation(); if an oscillation pattern is
 * detected it sets the deferred oscillationFaultPending flag.
 */
void histPushHistory(State s, uint32_t enteredMs);

/**
 * Atomically read and clear the oscillation-fault deferred flag.
 * Returns true on the first call after checkOscillation() set the flag;
 * false otherwise.  Called from update() at the top of each tick and from
 * onExitFault() to drain a stale pending flag after a manual fault clear.
 */
bool histTakeOscillationFaultPending();

/**
 * Push a new FaultRecord into the fault history ring buffer.
 * Called from onEnterFault() with the composite fault reason bitmask and
 * the current tick timestamp.
 */
void histPushFaultRecord(FaultReason r, uint32_t enteredMs);

/**
 * Complete the most recent FaultRecord with a clear timestamp.
 * The clearedBy label is taken from the internally tracked pendingCause
 * (set by histSetPendingCause() before the fault-clear trigger fires).
 * Called from onExitFault().
 */
void histCloseFaultRecord(uint32_t clearedMs);

/**
 * Reset all ring buffer and deferred-flag state to power-on defaults.
 * Called from init() and reinit().
 */
void histReset();

}  // namespace state_machine
