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
#include <time.h>
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
#include "sysinfo.h"
#include "cooling.h"
#include "hardware.h"
#include "relay.h"
#include "commands.h"
#include "dashboard.h"

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
    "timestamp.epoch",
    "timestamp.local"
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

    const time_t now = time(nullptr);
    char localBuf[20];
    strftime(localBuf, sizeof(localBuf), "%Y-%m-%d %H:%M:%S", localtime(&now));

    // Build the frame.
    // To add a field: append one .field(name, fmt, value) call here AND
    // update the field list in telemetry.h.
    lastFrame_.reset();
    lastFrame_
        // Unix epoch seconds (UTC).  Populated by SNTP once WiFi syncs;
        // returns 0 until the first sync completes.  Replace with RTC read
        // when hardware is available.
        .field("timestamp.epoch",                  "%lld", static_cast<int64_t>(time(nullptr)))
        .field("timestamp.local",                  "%s",   localBuf)
        .field("state.id",                         "%d",   static_cast<int8_t>(out.state))
        .field("state.name",                       "%s",   state_machine::stateName(out.state))
        .field("state.status_text",                 "%s",   state_machine::getStatusText())
        .field("cold_head.temp_k",                  "%.2f", cold_head::getLastTempK())
        .field("cold_head.temp_c",                  "%.2f", cold_head::getLastTempC())
        //.field("cold_head.ambient_temp_c",          "%.2f", cold_head::getLastAmbientTempC())
        .field("cold_head.cooling_rate",            "%.3f", cold_head::getCoolingRateKPerMin())
        .field("dac.target",                        "%u",   static_cast<unsigned>(out.dacTarget))
        .field("dac.actual",                        "%u",   static_cast<unsigned>(dacActual))
        .field("rms.voltage",                       "%.2f", rms::getVoltage())
        .field("relay.normal",                      "%u",   static_cast<uint8_t>(!out.bypassRelay))
        .field("relay.alarm",                       "%u",   static_cast<uint8_t>(out.alarmRelay))
        .field("indicator.fault",                   "%d",   indicator::isFaultOn())
        .field("indicator.ready",                   "%d",   indicator::isReadyOn())
        .field("status.on_duration_ms",             "%lu",  static_cast<unsigned long>(durationMs))
        .field("status.on_duration",                "%s",   hmsBuf)
        .field("cold_head.cooldown_pct",            "%.2f", cold_head::getTemperatureToPercent())
        .field("status.time_in_state",              "%s",   tisHmsBuf)
        .field("rms.current_a",                     "%.2f", rms::getCurrentA())
        .field("status.backoff_count",              "%u",   static_cast<unsigned>(out.backoffCount))
        .field("cold_head.delta_below_ambient_c",   "%.2f", cold_head::getLastTempCBelowAmbient())
        .field("system.voltage_v",                  "%.2f", sysinfo::getVoltage())
        .field("system.voltage_raw_v",              "%.2f", sysinfo::getVoltageRaw())
        .field("waveform.status",                   "%u",   waveform::getStatus())
        .field("waveform.frequency_hz",             "%.2f", waveform::getFrequency())
        .field("accelerometer.roll_deg",            "%.2f", accelerometer::getRoll())
        .field("accelerometer.pitch_deg",           "%.2f", accelerometer::getPitch())
        .field("accelerometer.yaw_deg",             "%.2f", accelerometer::getYaw())
        .field("accelerometer.accel_mag",           "%.2f", accelerometer::getAccelMag())
        .field("accelerometer.gyro_mag",            "%.2f", accelerometer::getGyroMag())
        .field("accelerometer.temp_c",              "%.1f", accelerometer::getTemperature())
        .field("accelerometer.motion",              "%u",   static_cast<uint8_t>(accelerometer::isMotionDetected()))
        .field("accelerometer.x",                   "%.3f", accelerometer::getAccelX())
        .field("accelerometer.y",                   "%.3f", accelerometer::getAccelY())
        .field("accelerometer.z",                   "%.3f", accelerometer::getAccelZ())
        .field("cooling.status",                    "%d",   cooling::isEnabled())
        .field("cooling.temp_c",                    "%.2f", cooling::getCoolantTemperature())
        .field("cooling.flow_rate_lpm",             "%.2f", cooling::getCoolantFlowRate())
        .field("cooling.fan_speed",                 "%u",   cooling::getFanSpeed())
        .field("rms.voltage_v",                     "%.2f", rms::getVoltage())
        // ── Module init / service status ─────────────────────────────────────
        .field("mod.hardware.init",                 "%s",   module::initStatusName(hardware::Module::getInitStatus()))
        .field("mod.hardware.service",              "%s",   module::serviceStatusName(hardware::Module::getServiceStatus()))
        .field("mod.sysinfo.init",                  "%s",   module::initStatusName(sysinfo::Module::getInitStatus()))
        .field("mod.sysinfo.service",               "%s",   module::serviceStatusName(sysinfo::Module::getServiceStatus()))
        .field("mod.accelerometer.init",            "%s",   module::initStatusName(accelerometer::Module::getInitStatus()))
        .field("mod.accelerometer.service",         "%s",   module::serviceStatusName(accelerometer::Module::getServiceStatus()))
        .field("mod.cooling.init",                  "%s",   module::initStatusName(cooling::Module::getInitStatus()))
        .field("mod.cooling.service",               "%s",   module::serviceStatusName(cooling::Module::getServiceStatus()))
        .field("mod.dashboard.init",                "%s",   module::initStatusName(dashboard::Module::getInitStatus()))
        .field("mod.dashboard.service",             "%s",   module::serviceStatusName(dashboard::Module::getServiceStatus()))
        .field("mod.waveform.init",                 "%s",   module::initStatusName(waveform::Module::getInitStatus()))
        .field("mod.waveform.service",              "%s",   module::serviceStatusName(waveform::Module::getServiceStatus()))
        .field("mod.cold_head.init",                "%s",   module::initStatusName(cold_head::Module::getInitStatus()))
        .field("mod.cold_head.service",             "%s",   module::serviceStatusName(cold_head::Module::getServiceStatus()))
        .field("mod.dac.init",                      "%s",   module::initStatusName(dac::Module::getInitStatus()))
        .field("mod.dac.service",                   "%s",   module::serviceStatusName(dac::Module::getServiceStatus()))
        .field("mod.rms.init",                      "%s",   module::initStatusName(rms::Module::getInitStatus()))
        .field("mod.rms.service",                   "%s",   module::serviceStatusName(rms::Module::getServiceStatus()))
        .field("mod.relay.init",                    "%s",   module::initStatusName(relay::Module::getInitStatus()))
        .field("mod.relay.service",                 "%s",   module::serviceStatusName(relay::Module::getServiceStatus()))
        .field("mod.indicator.init",                "%s",   module::initStatusName(indicator::Module::getInitStatus()))
        .field("mod.indicator.service",             "%s",   module::serviceStatusName(indicator::Module::getServiceStatus()))
        .field("mod.state_machine.init",            "%s",   module::initStatusName(state_machine::Module::getInitStatus()))
        .field("mod.state_machine.service",         "%s",   module::serviceStatusName(state_machine::Module::getServiceStatus()))
        .field("mod.commands.init",                 "%s",   module::initStatusName(commands::Module::getInitStatus()))
        .field("mod.commands.service",              "%s",   module::serviceStatusName(commands::Module::getServiceStatus()))
        .field("mod.telemetry.init",                "%s",   module::initStatusName(telemetry::Module::getInitStatus()))
        .field("mod.telemetry.service",             "%s",   module::serviceStatusName(telemetry::Module::getServiceStatus()));

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
