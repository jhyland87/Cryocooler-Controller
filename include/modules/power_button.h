/**
 * @file power_button.h
 * @brief Graceful power-off from the LTC2954 push-button controller.
 *
 * A button press pulses INT# (PWR_INT_PIN) low.  This module stops the state
 * machine, waits for the amplitude to ramp to zero, then drives KILL#
 * (PWR_KILL_PIN) low to release the supply.  Holding the button 6.4 s cuts power
 * in hardware whatever the firmware is doing.
 */

#ifndef POWER_BUTTON_H
#define POWER_BUTTON_H

#include "module.h"

namespace power_button {

/**
 * Configure the INT# input and its falling-edge interrupt.  INT# can pulse for
 * only 32 ms, so an interrupt catches it however long a loop() tick takes.
 * @return MODULE_INIT_SUCCESS always.
 */
module::InitStatus init();

/**
 * Run the power-off sequence once INT# has fallen.  Does not block.
 * @return MODULE_SERVICE_SKIPPED until the button is pressed, then MODULE_SERVICE_OK.
 */
module::ServiceStatus service();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = power_button::init(); }
    static module::ServiceStatus service() { return _serviceStatus = power_button::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace power_button

#endif // POWER_BUTTON_H
