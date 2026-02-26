/**
 * @file device.h
 * @brief Device voltage monitoring interface.
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

void service();

float getVoltage();

int16_t getVoltageRaw();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return device::init(); }
    static void service()            { device::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace device

#endif // DEVICE_H
