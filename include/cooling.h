/**
 * @file cooling.h
 * @brief For manaing the water recirculation and fans
 */

#ifndef COOLING_H
#define COOLING_H

#include <stdint.h>
#include "module.h"

namespace cooling {

/**
 * Initialize the cooling system.
 * @return MODULE_INIT_SUCCESS always.
 */
module::InitStatus init();

void service();

bool isCoolingPumpOn();

bool isCoolingFanOn();

float getCoolantTemperature();

float getCoolantFlowRate();

float getFanRPM();

void setFanRPM(float rpm);

void enable();
void disable();
bool isEnabled();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return cooling::init(); }
    static void service()            { cooling::service(); }
    static void enable()             { cooling::enable(); }
    static void disable()            { cooling::disable(); }
    static bool isEnabled()          { return cooling::isEnabled(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace cooling

#endif // COOLING_H
