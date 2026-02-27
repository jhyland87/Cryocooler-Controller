/**
 * @file telemetry.cpp
 * @brief Serial Studio CSV telemetry implementation.
 *
 * emit() captures a snapshot of all module state into a FrameBuilder, sends
 * it to Serial in Serial Studio wire format, and stores it as lastFrame_ so
 * that other modules (e.g. http_api) can serve the same data in other formats
 * (JSON, etc.) without re-reading hardware registers.
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include "accelerometer.h"
#include "frame_builder.h"
#include "cold_head.h"
#include "telemetry.h"
#include "state_machine.h"
#include "rms.h"
#include "dac.h"
#include "indicator.h"
#include "conversions.h"
#include "waveform.h"
#include "device.h"
#include "cooling.h"

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

namespace telemetry {

static bool         enabled      = true;
static bool         deltaEnabled = true;
static FrameBuilder lastFrame_;   // always holds the most recently emitted frame
static FrameBuilder prevFrame_;   // copy of the frame before the last emit (for delta)

// ---------------------------------------------------------------------------
// Passive-field list for delta mode
//
// Fields named here will NOT trigger serial output on their own when they
// change.  They are still included in the output line when another (non-
// passive) field triggers it.
//
// Add or remove entries to taste.  Field names must match exactly the strings
// used in the .field() calls in emit() below.
// ---------------------------------------------------------------------------
static const char* const kPassiveFields[] = {
    "status.time_in_state",   // resets on state change; ticks every second otherwise
    "status.on_duration",     // ticks every second while running
    "status.on_duration_ms",  // ticks every millisecond while running
};
static constexpr uint8_t kPassiveFieldCount =
    static_cast<uint8_t>(sizeof(kPassiveFields) / sizeof(kPassiveFields[0]));

// ---------------------------------------------------------------------------
// Enable / disable
// ---------------------------------------------------------------------------

void disable()        { enabled      = false; }
void enable()         { enabled      = true;  }
bool isEnabled()      { return enabled;        }

void enableDelta()    { deltaEnabled = true;   }
void disableDelta()   { deltaEnabled = false;  }
bool isDeltaEnabled() { return deltaEnabled;   }

// ---------------------------------------------------------------------------
// Frame access
// ---------------------------------------------------------------------------

const FrameBuilder& getLastFrame() {
    return lastFrame_;
}

void fillJson(JsonDocument& doc) {
    lastFrame_.fillJson(doc);
}

// ---------------------------------------------------------------------------
// Emit
// ---------------------------------------------------------------------------

void emit(const state_machine::Output& out)
{
#ifdef ARDUINO
    if (!enabled) return;

    const uint16_t dacActual = dac::getCurrent();

    // On-state duration (total time running since start())
    const uint32_t durationMs = state_machine::getOnStateDuration();
    const uint32_t durSec     = durationMs / 1000u;
    char hmsBuf[12];
    snprintf(hmsBuf, sizeof(hmsBuf), "%02lu:%02lu:%02lu",
             static_cast<unsigned long>(durSec / 3600u),
             static_cast<unsigned long>((durSec % 3600u) / 60u),
             static_cast<unsigned long>(durSec % 60u));

    // Time in current state (resets on every state transition)
    const uint32_t stateMs  = state_machine::getTimeInState();
    const uint32_t stateSec = stateMs / 1000u;
    char tisHmsBuf[12];
    snprintf(tisHmsBuf, sizeof(tisHmsBuf), "%02lu:%02lu:%02lu",
             static_cast<unsigned long>(stateSec / 3600u),
             static_cast<unsigned long>((stateSec % 3600u) / 60u),
             static_cast<unsigned long>(stateSec % 60u));

    // Build the frame.
    // To add a field: append one .field(name, fmt, value) call here AND
    // update the field list in telemetry.h.
    lastFrame_.reset();
    lastFrame_
        .field("state.id",                          "%d",   static_cast<int8_t>(out.state))             //  1
        .field("state.name",                        "%.2f",   state_machine::stateName(out.state))         //  2
        .field("state.status_text",                 "%s",   state_machine::getStatusText())              //  3
        .field("temperature.k",                     "%.2f", cold_head::getLastTempK())                 //  4
        .field("temperature.c",                     "%.2f", cold_head::getLastTempC())                 //  5
        .field("temperature.ambient_c",             "%.2f", cold_head::getLastAmbientTempC())          //  6
        .field("temperature.cooling_rate",          "%.3f", cold_head::getCoolingRateKPerMin())        //  7
        .field("dac.target",                        "%u",   static_cast<unsigned>(out.dacTarget))        //  8
        .field("dac.actual",                        "%u",   static_cast<unsigned>(dacActual))            //  9
        .field("rms.voltage",                       "%.2f", rms::getVoltage())                           // 10
        .field("relay.normal",                      "%u",   static_cast<uint8_t>(!out.bypassRelay))      // 11
        .field("relay.alarm",                       "%u",   static_cast<uint8_t>(out.alarmRelay))        // 12
        .field("indicator.fault",                   "%d",   indicator::isFaultOn())                      // 13
        .field("indicator.ready",                   "%d",   indicator::isReadyOn())                      // 14
        .field("status.on_duration_ms",             "%lu",  static_cast<unsigned long>(durationMs))      // 15
        .field("status.on_duration",                "%s",   hmsBuf)                                      // 16
        .field("cold_head.cooldown_pct",            "%.2f", cold_head::getTemperatureToPercent())      // 17
        .field("status.time_in_state",              "%s",   tisHmsBuf)                                   // 18
        .field("rms.amps",                          "%.2f", rms::getCurrentA())                          // 19
        .field("status.backoff_count",              "%u",   static_cast<unsigned>(out.backoffCount))     // 20
        .field("cold_head.delta_below_ambient_c",   "%.2f", cold_head::getLastTempCBelowAmbient())     // 21
        .field("voltage.v",                         "%.2f", device::getVoltage())                        // 22
        .field("voltage.raw",                       "%.2f", device::getVoltageRaw())                     // 23
        .field("waveform.status",                   "%u",   waveform::getStatus())                       // 24
        .field("waveform.frequency_hz",             "%.2f", waveform::getFrequency())                    // 25
        .field("accel.roll_deg",                    "%.2f", accelerometer::getRoll())                    // 26
        .field("accel.pitch_deg",                   "%.2f", accelerometer::getPitch())                   // 27
        .field("accel.yaw_deg",                     "%.2f", accelerometer::getYaw())                     // 28
        .field("accel.accel_mag",                   "%.2f", accelerometer::getAccelMag())                // 29
        .field("accel.gyro_mag",                    "%.2f", accelerometer::getGyroMag())                 // 30
        .field("accel.temp_c",                      "%.1f", accelerometer::getTemperature())             // 31
        .field("accel.motion",                      "%u",   static_cast<uint8_t>(accelerometer::isMotionDetected())) // 32
        .field("accel.x",                           "%.3f", accelerometer::getAccelX())                  // 33
        .field("accel.y",                           "%.3f", accelerometer::getAccelY())                  // 34
        .field("accel.z",                           "%.3f", accelerometer::getAccelZ())                  // 35
        //.field("cooling.pump_on",                   "%u",   static_cast<uint8_t>(cooling::isCoolingPumpOn())) // 36
        //.field("cooling.fan_on",                    "%u",   static_cast<uint8_t>(cooling::isCoolingFanOn())) // 37
        .field("cooling.temperature_c",             "%.2f", cooling::getCoolantTemperature())             // 38
        .field("cooling.flow_rate_lpm",             "%.2f", cooling::getCoolantFlowRate())               // 39
        .field("cooling.fan_speed",                 "%u", cooling::getFanSpeed());                       // 40

    // Serial output: full frame or delta (changed fields only).
    // fillJson() / getLastFrame() always use lastFrame_ — never delta-filtered.
    if (deltaEnabled) {
        lastFrame_.sendSerialDelta(Serial, prevFrame_, kPassiveFields, kPassiveFieldCount);
    } else {
        lastFrame_.sendSerial(Serial);
    }

    // Snapshot for the next delta comparison.
    prevFrame_ = lastFrame_;
#else
    (void)out;
#endif
}

} // namespace telemetry
