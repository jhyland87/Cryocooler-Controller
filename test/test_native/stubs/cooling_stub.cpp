/**
 * @file cooling_stub.cpp
 * @brief Minimal cooling module stub for native (host-PC) unit tests.
 *
 * Provides lightweight implementations of the cooling:: API so that
 * commands.cpp can be compiled and tested without any Arduino hardware
 * dependencies.  State is kept in plain static variables; tests can
 * inspect it via the public cooling:: getters.
 */

#include "cooling.h"

namespace cooling {

static uint8_t sLastFanSpeed = 0;
static bool    sEnabled      = false;

module::InitStatus init()  { return module::MODULE_INIT_SUCCESS; }
void service()             {}

void    enable()           { sEnabled = true; }
void    disable()          { sEnabled = false; sLastFanSpeed = 0; }
bool    isEnabled()        { return sEnabled; }

bool    isCoolingPumpOn()        { return sEnabled; }
bool    isCoolingFanOn()         { return sLastFanSpeed > 0u; }
float   getCoolantTemperature()  { return 0.0f; }
float   getCoolantFlowRate()     { return 0.0f; }
uint8_t getFanSpeed()            { return sLastFanSpeed; }

void setFanSpeed(uint8_t percentage) {
    sLastFanSpeed = percentage;
}

} // namespace cooling
