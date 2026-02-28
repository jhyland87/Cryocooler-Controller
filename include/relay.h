/**
 * @file relay.h
 * @brief Bypass and alarm relay control
 *
 * Two relays are managed:
 *
 *   BYPASS_RELAY_PIN  - LOW = Bypass mode (default / safe),
 *                       HIGH = Normal mode (states 5, 6, 7 only).
 *
 *   ALARM_RELAY_PIN   - LOW = idle, HIGH = alarm (state 8 / Fault only).
 */

#ifndef RELAY_H
#define RELAY_H

#include "module.h"

namespace relay {

/**
 * Initialize relay GPIO pins (outputs, defaulting to Bypass / alarm-off).
 * @return MODULE_INIT_SUCCESS always (GPIO init cannot fail).
 */
module::InitStatus init();

/**
 * Switch the bypass relay.
 * @param normal  true = Normal mode (HIGH), false = Bypass mode (LOW).
 */
void setBypass(bool normal);

/**
 * Drive the alarm relay.
 * @param active  true = alarm on (HIGH), false = alarm off (LOW).
 */
void setAlarm(bool active);

// ── Module interface ──────────────────────────────────────────────────────────
//
// relay is a pure actuator module — it has no periodic loop work.
// Module::service() inherits the default no-op from ModuleBase.
// Relay state is driven by the state machine via setBypass() / setAlarm().

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = relay::init(); }
    // service() — inherited no-op from ModuleBase; relay is state-machine driven.
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace relay

#endif // RELAY_H
