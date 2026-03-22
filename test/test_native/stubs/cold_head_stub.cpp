/**
 * @file cold_head_stub.cpp
 * @brief Minimal cold_head module stub for native (host-PC) unit tests.
 */

#include "cold_head.h"

namespace cold_head {

module::InitStatus    init()    { return module::MODULE_INIT_SUCCESS; }
module::InitStatus    initACS() { return module::MODULE_INIT_SUCCESS; }
module::InitStatus    initRTD() { return module::MODULE_INIT_SUCCESS; }

module::ServiceStatus service() { return module::MODULE_SERVICE_OK; }

void  read()                    {}
bool  hasSensorFault()              { return false; }
void  setTargetTempC(float)         {}
void  startTemperatureTracking()    {}
void  stopTemperatureTracking()     {}
float getLastTempC()                { return 0.0f; }
float getCoolingRateCPerMin()       { return 0.0f; }
float getTemperatureToPercent()     { return 0.0f; }

} // namespace cold_head
