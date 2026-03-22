/**
 * @file amplifier_stub.cpp
 * @brief Minimal amplifier module stub for native (host-PC) unit tests.
 *
 * Provides controllable state so tests can inject RMS voltage/current
 * values that the state machine reads via amplifier::getLastRmsVoltage().
 */

#include "amplifier.h"

static float sLastRmsVoltage = 0.0f;
static float sLastRmsCurrent = 0.0f;
static float sVoutOverride   = -1.0f;  // < 0 means no override
static bool  sRelayState     = false;
static float sTargetVoltage  = 0.0f;

namespace amplifier {

module::InitStatus    init()        { return module::MODULE_INIT_SUCCESS; }
module::InitStatus    initWaveform(){ return module::MODULE_INIT_SUCCESS; }
module::InitStatus    initAcs()     { return module::MODULE_INIT_SUCCESS; }
module::InitStatus    initDac()     { return module::MODULE_INIT_SUCCESS; }
module::InitStatus    initRelay()   { return module::MODULE_INIT_SUCCESS; }
module::ServiceStatus service()     { return module::MODULE_SERVICE_OK; }
bool  checkDependencies()           { return true; }

void  setRelayState(bool on)        { sRelayState = on; }
bool  getRelayState()               { return sRelayState; }
bool  isEnabled()                   { return false; }
void  enable()                      {}
void  disable()                     {}
void  setFrequency(float)           {}
float getFrequency()                { return 0.0f; }
void  rampTo(float, uint16_t)       {}
void  rampTowardShutdown()          {}
void  hardStop()                    { sLastRmsVoltage = 0.0f; sLastRmsCurrent = 0.0f; }
void  initCoarseCooldown()          {}
void  initFineCooldown()            {}
void  setOutput(float)              {}
uint16_t getDacCurrent()            { return 0; }
void  setVoutOverride(float f)      { sVoutOverride = f; }
void  clearVoutOverride()           { sVoutOverride = -1.0f; }
bool  hasVoutOverride()             { return sVoutOverride >= 0.0f; }
float getVoutOverride()             { return sVoutOverride >= 0.0f ? sVoutOverride : 0.0f; }
float getLastRmsVoltage()           { return sLastRmsVoltage; }
float getLastRmsCurrent()           { return sLastRmsCurrent; }
void  setTargetVoltage(float v)     { sTargetVoltage = v; }

} // namespace amplifier

// ── Test helpers for injecting mock values ──────────────────────────────────

extern "C" {

void stub_amplifier_setRmsVoltage(float v) {
    sLastRmsVoltage = v;
}

void stub_amplifier_setRmsCurrent(float a) {
    sLastRmsCurrent = a;
}

void stub_amplifier_reset() {
    sLastRmsVoltage = 0.0f;
    sLastRmsCurrent = 0.0f;
    sVoutOverride   = -1.0f;
    sRelayState     = false;
    sTargetVoltage  = 0.0f;
}

}
