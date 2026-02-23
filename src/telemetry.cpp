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
#include "frame_builder.h"
#include "temperature.h"
#include "telemetry.h"
#include "state_machine.h"
#include "rms.h"
#include "dac.h"
#include "indicator.h"
#include "conversions.h"
#include "waveform.h"
#include "device.h"

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

namespace telemetry {

static bool         enabled    = true;
static FrameBuilder lastFrame_;   // always holds the most recently emitted frame

// ---------------------------------------------------------------------------
// Enable / disable
// ---------------------------------------------------------------------------

void disable()   { enabled = false; }
void enable()    { enabled = true; }
bool isEnabled() { return enabled; }

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
        .field("state_no",              "%d",   static_cast<int8_t>(out.state))             //  1
        .field("state_name",            "%s",   state_machine::stateName(out.state))         //  2
        .field("status_text",           "%s",   state_machine::getStatusText())              //  3
        .field("temp_k",                "%.2f", temperature::getLastTempK())                 //  4
        .field("temp_c",                "%.2f", temperature::getLastTempC())                 //  5
        .field("ambient_temp_c",        "%.2f", temperature::getLastAmbientTempC())          //  6
        .field("cooling_rate",          "%.3f", temperature::getCoolingRateKPerMin())        //  7
        .field("dac_target",            "%u",   static_cast<unsigned>(out.dacTarget))        //  8
        .field("dac_actual",            "%u",   static_cast<unsigned>(dacActual))            //  9
        .field("rms_v",                 "%.2f", rms::getVoltage())                           // 10
        .field("relay_normal",          "%u",   static_cast<uint8_t>(!out.bypassRelay))      // 11
        .field("alarm_relay",           "%u",   static_cast<uint8_t>(out.alarmRelay))        // 12
        .field("red_led",               "%d",   indicator::isFaultOn())                      // 13
        .field("green_led",             "%d",   indicator::isReadyOn())                      // 14
        .field("on_duration_ms",        "%lu",  static_cast<unsigned long>(durationMs))      // 15
        .field("on_duration",           "%s",   hmsBuf)                                      // 16
        .field("cooldown_pct",          "%.2f", temperature::getTemperatureToPercent())      // 17
        .field("time_in_state",         "%s",   tisHmsBuf)                                   // 18
        .field("current_a",             "%.2f", rms::getCurrentA())                          // 19
        .field("backoff_count",         "%u",   static_cast<unsigned>(out.backoffCount))     // 20
        .field("delta_below_ambient_c", "%.2f", temperature::getLastTempCBelowAmbient())     // 21
        .field("voltage_v",             "%.2f", device::getVoltage())                        // 22
        .field("voltage_raw",           "%.2f", device::getVoltageRaw())                     // 23
        .field("waveform_status",       "%u",   waveform::getStatus())                       // 24
        .field("frequency_hz",          "%.2f", waveform::getFrequency());                   // 25

    lastFrame_.sendSerial(Serial);
#else
    (void)out;
#endif
}

} // namespace telemetry
