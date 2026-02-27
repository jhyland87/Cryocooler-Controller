/**
 * @file device.h
 * @brief Handles data about the overall system (`system` was taken as a module name, obv).
 */

#ifndef DEVICE_H
#define DEVICE_H

#include <stdint.h>
#include "module.h"

namespace device {

/**
 * Initialize the voltage monitoring ADC resolution.
 * @return MODULE_INIT_SUCCESS always.
 */
module::InitStatus init();

/**
 * Sample the supply voltage ADC and update internal state.
 * @return SERVICE_OK always.
 */
module::ServiceStatus service();

float getVoltage();

int16_t getVoltageRaw();

/**
 * Get the initialization status of the device.
 * @return The initialization status of the device.
 */
module::InitStatus getInitStatus();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return device::init(); }
    static module::ServiceStatus service() { return device::service(); }
    static module::InitStatus    getInitStatus() { return device::getInitStatus(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace device

#endif // DEVICE_H
