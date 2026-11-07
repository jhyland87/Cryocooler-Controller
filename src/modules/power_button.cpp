/**
 * @file power_button.cpp
 * @brief Graceful power-off from the LTC2954 push-button controller.
 */

#include "power_button.h"

#include <Arduino.h>

#include "amplifier.h"
#include "config.h"
#include "logger.h"
#include "pin_config.h"
#include "power_good.h"
#include "state_machine.h"
#include "tick.h"

namespace power_button {

static LogStream _Log = Log.createChildLogger("power_button");

static volatile bool sInterruptSeen = false;
static bool     sPoweringOff = false;
static bool     sKillAsserted = false;
static uint32_t sPowerOffStartMs = 0;

static void IRAM_ATTR onPowerInterrupt() { sInterruptSeen = true; }

module::InitStatus init() {
    // R8 pulls INT# up; the LTC2954 output is open drain.
    pinMode(PWR_INT_PIN, INPUT);
    attachInterrupt(digitalPinToInterrupt(PWR_INT_PIN), onPowerInterrupt, FALLING);
    return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    if (!sInterruptSeen || sKillAsserted) {
        return module::MODULE_SERVICE_SKIPPED;
    }
    const uint32_t now = tick::nowMs();
    if (!sPoweringOff) {
        sPoweringOff = true;
        sPowerOffStartMs = now;
        _Log.println(F("Power button pressed: stopping, then releasing the supply"));
        // The Shutdown state ramps the DAC to zero; every other state already holds it there.
        state_machine::stop();
        return module::MODULE_SERVICE_OK;
    }
    const uint16_t dacCounts = amplifier::getDacCurrent();
    const uint32_t elapsedMs = static_cast<uint32_t>(now - sPowerOffStartMs);
    if (!powerOffReady(dacCounts, elapsedMs, POWER_OFF_TIMEOUT_MS)) {
        return module::MODULE_SERVICE_OK;
    }
    if (dacCounts != 0) {
        _Log.printf("WARNING: power-off timed out with DAC at %u, forcing it to zero\n", dacCounts);
    }
    amplifier::hardStop();
    sKillAsserted = true;
    _Log.println(F("Releasing the supply (KILL low)"));
    digitalWrite(PWR_KILL_PIN, LOW);
    pinMode(PWR_KILL_PIN, OUTPUT);
    return module::MODULE_SERVICE_OK;
}

}  // namespace power_button
