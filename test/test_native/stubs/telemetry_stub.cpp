/**
 * @file telemetry_stub.cpp
 * @brief Minimal telemetry stub for native (host-PC) unit tests.
 *
 * The real telemetry module pulls in hardware.h → Wire.h → SPI.h which are
 * Arduino-only.  Tests only exercise enable()/disable()/isEnabled(), so this
 * stub provides just those functions plus no-op implementations for the rest.
 */

#include "telemetry.h"

namespace telemetry {

static bool sEnabled = false;
static bool sDeltaEnabled = false;

void emit(const state_machine::Output&) {}

const FrameBuilder& getLastFrame() {
    static FrameBuilder sEmpty;
    return sEmpty;
}

void fillJson(JsonDocument&) {}
void fillJsonSafe(JsonDocument&) {}
void emitSafe() {}

void enable()           { sEnabled = true; }
void disable()          { sEnabled = false; }
bool isEnabled()        { return sEnabled; }

void enableDelta()      { sDeltaEnabled = true; }
void disableDelta()     { sDeltaEnabled = false; }
bool isDeltaEnabled()   { return sDeltaEnabled; }

} // namespace telemetry
