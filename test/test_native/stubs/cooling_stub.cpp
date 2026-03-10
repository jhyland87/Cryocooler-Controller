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

module::InitStatus    init()    { sEnabled = true; return module::MODULE_INIT_SUCCESS; }
module::ServiceStatus service() { return module::MODULE_SERVICE_OK; }

void    enable()           { sEnabled = true; }
void    disable()          { sEnabled = false; sLastFanSpeed = 0; }
bool    isEnabled()        { return sEnabled; }

bool    isCoolingPumpOn()        { return sEnabled; }
bool    isCoolingFanOn()         { return sLastFanSpeed > 0u; }
float   getCoolantTemperature()  { return 0.0f; }
float   getCoolantFlowRate()     { return 0.0f; }
uint8_t  getFanSpeed()           { return sLastFanSpeed; }
uint16_t getFanRPM()             { return sLastFanSpeed > 0u ? static_cast<uint16_t>(1200) : static_cast<uint16_t>(0); }

uint8_t  getPumpSpeed()          { return 0; }
uint16_t getPumpRPM()            { return 0; }

void setFanSpeed(uint8_t percentage, bool force) {
    (void)force;
    sLastFanSpeed = percentage;
}

} // namespace cooling
