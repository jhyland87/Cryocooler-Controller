/**
 * @file relay.h
 * @brief Bypass and alarm relay control
 *
 * Two relays are managed:
 *
 *   RELAY_COMPRESSOR_I2C_ADDRESS - I2C address of the compressor relay controller.
 *   RELAY_AMPLIFIER_I2C_ADDRESS - I2C address of the amplifier relay controller.
 */

#ifndef RELAY_H
#define RELAY_H

#include "module.h"

namespace relay {

/**
 * Initialize relay GPIO pins (outputs, defaulting to Compressor / Amplifier off).
 * @return MODULE_INIT_SUCCESS always (GPIO init cannot fail).
 */
module::InitStatus init();

/**
 * Switch the bypass relay.
 * @param normal  true = Normal mode (HIGH), false = Bypass mode (LOW).
 */
void setCompressorState(bool on);



void setAmplifierState(bool on);

bool getCompressorState();

bool getAmplifierState();


void enableMock();
void disableMock();
bool isMockEnabled();
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
