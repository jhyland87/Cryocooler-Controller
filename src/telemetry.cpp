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
#ifdef ARDUINO
#  include "ota.h"
#endif
#include "imu.h"
#include "frame_builder.h"
#include "cold_head.h"
#include "telemetry.h"
#include "state_machine.h"
#include "indicator.h"
#include "conversions.h"
#include "sysinfo.h"
#include "cooling.h"
#include "hardware.h"
#include "relay.h"
#include "commands.h"
#include "dashboard.h"
#include "amplifier.h"
#include "tracking.h"
#include "compressor.h"

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

namespace telemetry {

static bool         enabled      = true;
static bool         deltaEnabled = true;
static FrameBuilder lastFrame_;   // always holds the most recently emitted frame
static FrameBuilder prevFrame_;   // copy of the frame before the last emit (for delta)
static FrameBuilder safeFrame_;   // scratch frame used by fillJsonSafe() during startup

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
    "timestamp.local",
    "system.cpu_usage_percent",
    "system.cpu_freq_mhz",
    "system.total_heap_bytes",
    "system.free_heap_bytes",
    "system.min_free_heap_bytes",
    "system.max_alloc_bytes",
    "system.heap_usage_percent",
    "system.total_psram_bytes",
    "system.free_psram_bytes",
    // Fault-rate counters age out slowly; suppress delta noise between faults.
    "faults.count_10m",
    "faults.count_30m",
    "faults.count_60m",
    // Firmware info is constant for the lifetime of a boot — never trigger delta.
    "firmware.version",
    "firmware.build_date",
    "firmware.ota_flash_local",
    "firmware.ota_flash_ts",
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
// buildStartupFrame — shared helper for fillJsonSafe() and emitSafe()
//
// Populates @p frame with a full snapshot of current module state.
// For each module that has not yet completed init(), its data fields are
// written as empty strings so the dashboard structure is always complete.
// Module init/service status fields are always written with their real values
// so startup progress is visible.
//
// Called only from ARDUINO builds; guard with #ifdef at call sites.
// ---------------------------------------------------------------------------

static void buildStartupFrame(FrameBuilder& frame)
{
    frame.reset();

    const auto ready = [](module::InitStatus s) {
        return s == module::MODULE_INIT_SUCCESS;
    };

    const bool smReady          = ready(state_machine::Module::getInitStatus());
    const bool coldHeadReady    = ready(cold_head::Module::getInitStatus());
    const bool amplifierReady   = ready(amplifier::Module::getInitStatus());
    const bool relayReady       = ready(relay::Module::getInitStatus());
    const bool indicatorReady   = ready(indicator::Module::getInitStatus());
    const bool sysinfoReady     = ready(sysinfo::Module::getInitStatus());
    const bool accelReady       = ready(imu::Module::getInitStatus());
    const bool coolingReady     = ready(cooling::Module::getInitStatus());
    const float amplifierVoltageScore = amplifier::getVoltageScore();
    const float amplifierFrequencyScore = amplifier::getFrequencyScore();
    const float coolingFanSpeedScore = cooling::getFanSpeedScore();
    const float coolingCoolantTempScore = cooling::getCoolantTempScore();
    const float coolingCoolantFlowScore = cooling::getCoolantFlowScore();
    const float coolingWorstTrackingScore = cooling::getWorstTrackingScore();
    const float coldHeadTempScore = cold_head::getTemperatureScore();
    // ── Timestamps (always valid) ──────────────────────────────────────────
    const time_t now = time(nullptr);
    char localBuf[20];
    strftime(localBuf, sizeof(localBuf), "%Y-%m-%d %H:%M:%S", localtime(&now));

    frame
        .field("timestamp.epoch", "%lld", static_cast<int64_t>(now))
        .field("timestamp.local", "%s",   localBuf)
        .field("score.amplifier.voltage", "%.2f", static_cast<float>(amplifierVoltageScore))
        .field("score.amplifier.frequency", "%.2f", static_cast<float>(amplifierFrequencyScore))
        .field("score.cooling.fan_speed", "%.2f", static_cast<float>(coolingFanSpeedScore))
        .field("score.cooling.coolant_temp", "%.2f", static_cast<float>(coolingCoolantTempScore))
        .field("score.cooling.coolant_flow", "%.2f", static_cast<float>(coolingCoolantFlowScore))
        .field("score.cooling.worst", "%.2f", static_cast<float>(coolingWorstTrackingScore))
        .field("score.cold_head.temp", "%.2f", static_cast<float>(coldHeadTempScore));

    // ── State machine ──────────────────────────────────────────────────────
    if (smReady) {
        const auto st = state_machine::getState();

        const uint32_t durationMs = state_machine::getOnStateDuration();
        const uint32_t durSec     = durationMs / 1000u;
        char hmsBuf[12];
        snprintf(hmsBuf, sizeof(hmsBuf), "%02lu:%02lu:%02lu",
                 static_cast<unsigned long>(durSec / 3600u),
                 static_cast<unsigned long>((durSec % 3600u) / 60u),
                 static_cast<unsigned long>(durSec % 60u));

        const uint32_t stateMs  = state_machine::getTimeInState();
        const uint32_t stateSec = stateMs / 1000u;
        char tisHmsBuf[12];
        snprintf(tisHmsBuf, sizeof(tisHmsBuf), "%02lu:%02lu:%02lu",
                 static_cast<unsigned long>(stateSec / 3600u),
                 static_cast<unsigned long>((stateSec % 3600u) / 60u),
                 static_cast<unsigned long>(stateSec % 60u));

        const uint32_t nowMs = millis();
        frame
            .field("state.id",              "%d",  static_cast<int8_t>(st))
            .field("state.name",            "%s",  state_machine::stateName(st))
            .field("state.status_text",      "%s",  state_machine::getStatusText())
            .field("status.on_duration_ms", "%lu", static_cast<unsigned long>(durationMs))
            .field("status.on_duration",    "%s",  hmsBuf)
            .field("status.time_in_state",  "%s",  tisHmsBuf)
            .field("faults.count_10m",      "%u",  static_cast<unsigned>(state_machine::countRecentFaults(600000u,  nowMs)))
            .field("faults.count_30m",      "%u",  static_cast<unsigned>(state_machine::countRecentFaults(1800000u, nowMs)))
            .field("faults.count_60m",      "%u",  static_cast<unsigned>(state_machine::countRecentFaults(3600000u, nowMs)));
    } else {
        frame
            .field("state.id",              "%s", "")
            .field("state.name",            "%s", "")
            .field("state.status_text",      "%s", "")
            .field("status.on_duration_ms", "%s", "")
            .field("status.on_duration",    "%s", "")
            .field("status.time_in_state",  "%s", "")
            .field("faults.count_10m",      "%s", "")
            .field("faults.count_30m",      "%s", "")
            .field("faults.count_60m",      "%s", "");
    }
    // backoff_count comes from the state-machine Output struct produced by
    // update(); no standalone getter exists, so always emit "" here.
    frame.field("status.backoff_count", "%s", "");

    // ── Relay ───────────────────────────────────────────────────────────────
    if (relayReady) {
        frame
            .field("relay.compressor_state", "%d", relay::getCompressorState())
            .field("relay.amplifier_state",  "%d", relay::getAmplifierState());
    } else {
        frame
            .field("relay.compressor_state", "%s", "")
            .field("relay.amplifier_state",  "%s", "");
    }

    // // ── DAC ───────────────────────────────────────────────────────────────
    // if (dacReady) {
    //     frame
    //         .field("dac.target", "%s",  "")  // target is in Output only
    //         .field("dac.actual", "%u",  static_cast<unsigned>(dac::getCurrent()));
    // } else {
    //     frame
    //         .field("dac.target", "%s", "")
    //         .field("dac.actual", "%s", "");
    // }

    // ── Amplifier ───────────────────────────────────────────────────────────
    if (amplifierReady) {
        frame
            .field("amplifier.voltage_v", "%.2f", amplifier::getLastRmsVoltage())
            .field("amplifier.current_a", "%.2f", amplifier::getLastRmsCurrent());
    } else {
        frame
            .field("amplifier.voltage_v", "%s", "")
            .field("amplifier.current_a", "%s", "");
    }
    // ── Cold head ─────────────────────────────────────────────────────────
    if (coldHeadReady) {
        frame
            .field("cold_head.temp_k",                "%.2f", cold_head::getLastTempK())
            .field("cold_head.temp_c",                "%.2f", cold_head::getLastTempC())
            .field("cold_head.cooling_rate",          "%.3f", cold_head::getCoolingRateKPerMin())
            .field("cold_head.cooldown_pct",          "%.2f", cold_head::getTemperatureToPercent())
            .field("cold_head.delta_below_ambient_c", "%.2f", cold_head::getLastTempCBelowAmbient())
            .field("cold_head.ambient_temp_c",        "%.2f", cold_head::getLastAmbientTempC())
            .field("cold_head.voltage_v",             "%.2f", cold_head::getLastRmsVoltage())
            .field("cold_head.current_a",             "%.2f", cold_head::getLastRmsCurrent());
    } else {
        frame
            .field("cold_head.temp_k",                "%s", "")
            .field("cold_head.temp_c",                "%s", "")
            .field("cold_head.cooling_rate",          "%s", "")
            .field("cold_head.cooldown_pct",          "%s", "")
            .field("cold_head.delta_below_ambient_c", "%s", "")
            .field("cold_head.ambient_temp_c",        "%s", "")
            .field("cold_head.voltage_v",             "%s", "")
            .field("cold_head.current_a",             "%s", "");
    }

    // ── RMS ───────────────────────────────────────────────────────────────
    // if (rmsReady) {
    //     frame
    //         .field("rms.voltage",   "%.2f", rms::getVoltage())
    //         .field("rms.current_a", "%.2f", rms::getCurrentA())
    //         .field("rms.voltage_v", "%.2f", rms::getVoltage());
    // } else {
    //     frame
    //         .field("rms.voltage",   "%s", "")
    //         .field("rms.current_a", "%s", "")
    //         .field("rms.voltage_v", "%s", "");
    // }

    // ── Indicator ─────────────────────────────────────────────────────────
    if (indicatorReady) {
        frame
            .field("indicator.fault", "%d", indicator::isFaultOn())
            .field("indicator.ready", "%d", indicator::isReadyOn());
    } else {
        frame
            .field("indicator.fault", "%s", "")
            .field("indicator.ready", "%s", "");
    }


    // ── Sysinfo ───────────────────────────────────────────────────────────
    if (sysinfoReady) {
        frame
            .field("system.voltage_vdc",     "%.2f", sysinfo::getVoltage())
            .field("system.current_a",    "%.2f", sysinfo::getCurrent())
            .field("system.power_w",      "%.2f", sysinfo::getPower())
            .field("system.cpu_usage_percent", "%.2f", sysinfo::getCpuUsagePercent())
            .field("system.cpu_freq_mhz", "%.2f", sysinfo::getCpuFreqMHz())
            .field("system.total_heap_bytes", "%.2f", sysinfo::getTotalHeapBytes())
            .field("system.free_heap_bytes", "%.2f", sysinfo::getFreeHeapBytes())
            .field("system.min_free_heap_bytes", "%.2f", sysinfo::getMinFreeHeapBytes())
            .field("system.max_alloc_bytes", "%.2f", sysinfo::getMaxAllocBytes())
            .field("system.heap_usage_percent", "%.2f", sysinfo::getHeapUsagePercent())
            .field("system.total_psram_bytes", "%.2f", sysinfo::getTotalPsramBytes())
            .field("system.free_psram_bytes", "%.2f", sysinfo::getFreePsramBytes())
            .field("system.psram_usage_percent", "%.2f", sysinfo::getPsramUsagePercent())
            .field("system.uptime_ms", "%.2f", sysinfo::getUptimeMs())
            .field("system.num_cores", "%.2f", sysinfo::getNumCores())
            .field("system.chip_model", "%s", sysinfo::getChipModel());
    } else {
        frame
            .field("system.voltage_v",     "%s", "")
            .field("system.current_a",    "%s", "")
            .field("system.power_w",      "%s", "")
            .field("system.cpu_usage_percent", "%s", "")
            .field("system.cpu_freq_mhz", "%s", "")
            .field("system.total_heap_bytes", "%s", "")
            .field("system.free_heap_bytes", "%s", "")
            .field("system.min_free_heap_bytes", "%s", "")
            .field("system.max_alloc_bytes", "%s", "")
            .field("system.heap_usage_percent", "%s", "")
            .field("system.total_psram_bytes", "%s", "")
            .field("system.free_psram_bytes", "%s", "")
            .field("system.psram_usage_percent", "%s", "")
            .field("system.uptime_ms", "%s", "")
            .field("system.num_cores", "%s", "")
            .field("system.chip_model", "%s", "");
    }

    // // ── Waveform ──────────────────────────────────────────────────────────
    // if (waveformReady) {
    //     frame
    //         .field("waveform.status",       "%u",   waveform::isEnabled())
    //         .field("waveform.frequency_hz", "%.2f", waveform::getFrequency());
    // } else {
    //     frame
    //         .field("waveform.status",       "%s", "")
    //         .field("waveform.frequency_hz", "%s", "");
    // }

    // ── Accelerometer ─────────────────────────────────────────────────────
    if (accelReady) {
        frame
            .field("imu.roll_deg",  "%.2f", imu::getRoll())
            .field("imu.pitch_deg", "%.2f", imu::getPitch())
            .field("imu.yaw_deg",   "%.2f", imu::getYaw())
            .field("imu.accel_mag", "%.2f", imu::getAccelMag())
            //.field("imu.gyro_mag",  "%.2f", imu::getGyroMag())
            .field("imu.temp_c",    "%.1f", imu::getTemperature())
            .field("imu.motion",    "%u",   static_cast<uint8_t>(imu::isMotionDetected()))
            .field("imu.x",         "%.3f", imu::getAccelX())
            .field("imu.y",         "%.3f", imu::getAccelY())
            .field("imu.z",         "%.3f", imu::getAccelZ());
    } else {
        frame
            .field("imu.roll_deg",  "%s", "")
            .field("imu.pitch_deg", "%s", "")
            .field("imu.yaw_deg",   "%s", "")
            .field("imu.accel_mag", "%s", "")
            //.field("imu.gyro_mag",  "%s", "")
            .field("imu.temp_c",    "%s", "")
            .field("imu.motion",    "%s", "")
            .field("imu.x",         "%s", "")
            .field("imu.y",         "%s", "")
            .field("imu.z",         "%s", "");
    }

    // ── Cooling ───────────────────────────────────────────────────────────
    if (coolingReady) {
        frame
            .field("cooling.status",        "%d",   cooling::isEnabled())
            .field("cooling.pump_on",       "%d",   cooling::isCoolingPumpOn())
            .field("cooling.temp_c",        "%.2f", cooling::getCoolantTemperature())
            .field("cooling.flow_rate_lpm", "%.3f", cooling::getCoolantFlowRate())
            .field("cooling.fan_speed",     "%u",   cooling::getFanSpeed())
            .field("cooling.fan_rpm",       "%u",   cooling::getFanRPM())
            .field("cooling.pump_speed",    "%u",   cooling::getPumpSpeed())
            .field("cooling.pump_rpm",      "%u",   cooling::getPumpRPM());
    } else {
        frame
            .field("cooling.status",        "%s", "")
            .field("cooling.pump_on",       "%s", "")
            .field("cooling.temp_c",        "%s", "")
            .field("cooling.flow_rate_lpm", "%s", "")
            .field("cooling.fan_speed",     "%s", "")
            .field("cooling.fan_rpm",       "%s", "")
            .field("cooling.pump_speed",    "%s", "")
            .field("cooling.pump_rpm",      "%s", "");
    }

    // ── Compressor ────────────────────────────────────────────────────────
    {
        const bool compressorReady = ready(compressor::Module::getInitStatus());
        if (compressorReady) {
            frame.field("compressor.status", "%d", compressor::getStatus());
        } else {
            frame.field("compressor.status", "%s", "");
        }
    }

    // ── Firmware info (always real — sourced from app desc + NVS) ────────────
    {
        const int64_t flashTs = ota::getLastFlashTime();
        char flashBuf[20];
        if (flashTs > 0) {
            const time_t ft = static_cast<time_t>(flashTs);
            strftime(flashBuf, sizeof(flashBuf), "%Y-%m-%d %H:%M:%S", localtime(&ft));
        } else {
            snprintf(flashBuf, sizeof(flashBuf), "never");
        }
        frame
            .field("firmware.version",         "%s",   ota::getFirmwareVersion())
            .field("firmware.build_date",       "%s",   ota::getFirmwareBuildDate())
            .field("firmware.ota_flash_ts",     "%lld", flashTs)
            .field("firmware.ota_flash_local",  "%s",   flashBuf);
    }

    // ── Module init / service status (always real) ─────────────────────────
    frame
        .field("mod.hardware.init",             "%s", module::initStatusName(hardware::Module::getInitStatus()))
        .field("mod.hardware.service",          "%s", module::serviceStatusName(hardware::Module::getServiceStatus()))
        .field("mod.sysinfo.init",              "%s", module::initStatusName(sysinfo::Module::getInitStatus()))
        .field("mod.sysinfo.service",           "%s", module::serviceStatusName(sysinfo::Module::getServiceStatus()))
        .field("mod.imu.init",                  "%s", module::initStatusName(imu::Module::getInitStatus()))
        .field("mod.imu.service",               "%s", module::serviceStatusName(imu::Module::getServiceStatus()))
        .field("mod.amplifier.init",            "%s", module::initStatusName(amplifier::Module::getInitStatus()))
        .field("mod.amplifier.service",         "%s", module::serviceStatusName(amplifier::Module::getServiceStatus()))
        .field("mod.cooling.init",              "%s", module::initStatusName(cooling::Module::getInitStatus()))
        .field("mod.cooling.service",           "%s", module::serviceStatusName(cooling::Module::getServiceStatus()))
        .field("mod.dashboard.init",            "%s", module::initStatusName(dashboard::Module::getInitStatus()))
        .field("mod.dashboard.service",         "%s", module::serviceStatusName(dashboard::Module::getServiceStatus()))
        // .field("mod.waveform.init",             "%s", module::initStatusName(waveform::Module::getInitStatus()))
        // .field("mod.waveform.service",          "%s", module::serviceStatusName(waveform::Module::getServiceStatus()))
        .field("mod.cold_head.init",            "%s", module::initStatusName(cold_head::Module::getInitStatus()))
        .field("mod.cold_head.service",         "%s", module::serviceStatusName(cold_head::Module::getServiceStatus()))
        // .field("mod.dac.init",                  "%s", module::initStatusName(dac::Module::getInitStatus()))
        // .field("mod.dac.service",               "%s", module::serviceStatusName(dac::Module::getServiceStatus()))
        .field("mod.relay.init",                "%s", module::initStatusName(relay::Module::getInitStatus()))
        .field("mod.relay.service",             "%s", module::serviceStatusName(relay::Module::getServiceStatus()))
        .field("mod.indicator.init",            "%s", module::initStatusName(indicator::Module::getInitStatus()))
        .field("mod.indicator.service",         "%s", module::serviceStatusName(indicator::Module::getServiceStatus()))
        .field("mod.state_machine.init",        "%s", module::initStatusName(state_machine::Module::getInitStatus()))
        .field("mod.state_machine.service",     "%s", module::serviceStatusName(state_machine::Module::getServiceStatus()))
        .field("mod.commands.init",             "%s", module::initStatusName(commands::Module::getInitStatus()))
        .field("mod.commands.service",          "%s", module::serviceStatusName(commands::Module::getServiceStatus()))
        .field("mod.telemetry.init",            "%s", module::initStatusName(telemetry::Module::getInitStatus()))
        .field("mod.telemetry.service",         "%s", module::serviceStatusName(telemetry::Module::getServiceStatus()));
}

// ---------------------------------------------------------------------------
// fillJsonSafe — always safe, even before the first emit()
// ---------------------------------------------------------------------------

void fillJsonSafe(JsonDocument& doc)
{
#ifdef ARDUINO
    // Fast path: emit() has run at least once, so lastFrame_ is fully populated.
    if (lastFrame_.fieldCount() > 0) {
        lastFrame_.fillJson(doc);
        return;
    }

    // Slow path: setup still in progress.  Build a live snapshot and serve it.
    buildStartupFrame(safeFrame_);
    safeFrame_.fillJson(doc);
#else
    (void)doc;
#endif
}

// ---------------------------------------------------------------------------
// emitSafe — startup telemetry pulse, one call per initModule() completion
//
// Builds a full startup-safe frame into lastFrame_ (so the dashboard fast-path
// picks it up on its next tick) and emits it to Serial in the same wire format
// as emit().  This lets Serial Studio / the serial monitor show each module
// coming online as it happens, rather than waiting for setup to complete.
//
// prevFrame_ is updated so the first real emit() delta only reports the fields
// that actually changed during the final setup step.
// ---------------------------------------------------------------------------

void emitSafe()
{
#ifdef ARDUINO
    if (!enabled) return;

    buildStartupFrame(lastFrame_);
    lastFrame_.sendSerial(Serial);
    prevFrame_ = lastFrame_;
#endif
}

// ---------------------------------------------------------------------------
// Emit
// ---------------------------------------------------------------------------

void emit(const state_machine::Output& out)
{
#ifdef ARDUINO
    if (!enabled) return;

    //const uint16_t dacActual = dac::getCurrent();

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
        .field("timestamp.epoch",                   "%lld", static_cast<int64_t>(time(nullptr)))
        .field("timestamp.local",                   "%s",   localBuf)
        .field("state.id",                          "%d",   out.state)
        .field("state.name",                        "%s",   state_machine::stateName(out.state))
        .field("state.status_text",                 "%s",   state_machine::getStatusText())
        .field("cold_head.temp_k",                  "%.2f", cold_head::getLastTempK())
        .field("cold_head.temp_c",                  "%.2f", cold_head::getLastTempC())
        //.field("cold_head.ambient_temp_c",          "%.2f", cold_head::getLastAmbientTempC())
        .field("cold_head.cooling_rate",            "%.3f", cold_head::getCoolingRateKPerMin())
        //.field("dac.target",                        "%u",   static_cast<unsigned>(out.dacTarget))
        //.field("dac.actual",                        "%u",   static_cast<unsigned>(dacActual))
        .field("cold_head.voltage_v",               "%.2f", cold_head::getLastRmsVoltage())
        .field("cold_head.current_a",               "%.2f", cold_head::getLastRmsCurrent())
        .field("relay.compressor_state",            "%d",   relay::getCompressorState())
        .field("relay.amplifier_state",             "%d",   relay::getAmplifierState())
        .field("indicator.fault",                   "%d",   indicator::isFaultOn())
        .field("indicator.ready",                   "%d",   indicator::isReadyOn())
        .field("status.on_duration_ms",             "%lu",  static_cast<unsigned long>(durationMs))
        .field("status.on_duration",                "%s",   hmsBuf)
        .field("amplifier.voltage_v",               "%.2f", amplifier::getLastRmsVoltage())
        .field("amplifier.current_a",               "%.2f", amplifier::getLastRmsCurrent())
        .field("cold_head.cooldown_pct",            "%.2f", cold_head::getTemperatureToPercent())
        .field("status.time_in_state",              "%s",   tisHmsBuf)
        .field("status.backoff_count",              "%u",   static_cast<unsigned>(out.backoffCount))
        .field("faults.count_10m",                  "%u",   static_cast<unsigned>(state_machine::countRecentFaults(600000u)))
        .field("faults.count_30m",                  "%u",   static_cast<unsigned>(state_machine::countRecentFaults(1800000u)))
        .field("faults.count_60m",                  "%u",   static_cast<unsigned>(state_machine::countRecentFaults(3600000u)))
        .field("cold_head.delta_below_ambient_c",   "%.2f", cold_head::getLastTempCBelowAmbient())
        .field("cold_head.ambient_temp_c",          "%.2f", cold_head::getLastAmbientTempC())
        .field("system.voltage_v",                  "%.2f", sysinfo::getVoltage())
        .field("system.current_a",                  "%.2f", sysinfo::getCurrent())
        .field("system.power_w",                    "%.2f", sysinfo::getPower())
        // .field("waveform.status",                   "%u",   waveform::isEnabled())
        // .field("waveform.frequency_hz",             "%.2f", waveform::getFrequency())
        .field("imu.roll_deg",                      "%.2f", imu::getRoll())
        .field("imu.pitch_deg",                     "%.2f", imu::getPitch())
        .field("imu.yaw_deg",                       "%.2f", imu::getYaw())
        .field("imu.accel_mag",                     "%.2f", imu::getAccelMag())
        //.field("imu.gyro_mag",                      "%.2f", imu::getGyroMag())
        .field("imu.temp_c",                        "%.1f", imu::getTemperature())
        .field("imu.motion",                        "%u",   imu::isMotionDetected())
        .field("imu.x",                             "%.3f", imu::getAccelX())
        .field("imu.y",                             "%.3f", imu::getAccelY())
        .field("imu.z",                             "%.3f", imu::getAccelZ())
        .field("cooling.status",                    "%d",   cooling::isEnabled())
        .field("cooling.pump_on",                   "%d",   cooling::isCoolingPumpOn())
        .field("cooling.temp_c",                    "%.2f", cooling::getCoolantTemperature())
        .field("cooling.flow_rate_lpm",             "%.3f", cooling::getCoolantFlowRate())
        .field("cooling.fan_speed",                 "%u",   cooling::getFanSpeed())
        .field("cooling.fan_rpm",                   "%u",   cooling::getFanRPM())
        .field("cooling.pump_speed",                "%u",   cooling::getPumpSpeed())
        .field("cooling.pump_rpm",                  "%u",   cooling::getPumpRPM())
        .field("score.cooling.fan_speed",           "%.2f", cooling::getFanSpeedScore())
        .field("score.cooling.coolant_temp",        "%.2f", cooling::getCoolantTempScore())
        .field("score.cooling.coolant_flow",        "%.2f", cooling::getCoolantFlowScore())
        .field("score.cooling.worst",               "%.2f", cooling::getWorstTrackingScore())
        .field("compressor.status",                  "%d",  compressor::getStatus());

    // ── Firmware info ─────────────────────────────────────────────────────────
    {
        const int64_t flashTs = ota::getLastFlashTime();
        char flashBuf[20];
        if (flashTs > 0) {
            const time_t ft = static_cast<time_t>(flashTs);
            strftime(flashBuf, sizeof(flashBuf), "%Y-%m-%d %H:%M:%S", localtime(&ft));
        } else {
            snprintf(flashBuf, sizeof(flashBuf), "never");
        }
        lastFrame_
            .field("firmware.version",         "%s",   ota::getFirmwareVersion())
            .field("firmware.build_date",       "%s",   ota::getFirmwareBuildDate())
            .field("firmware.ota_flash_ts",     "%lld", flashTs)
            .field("firmware.ota_flash_local",  "%s",   flashBuf);
    }

    lastFrame_
        // ── Module init / service status ─────────────────────────────────────
        .field("mod.hardware.init",                 "%s",   module::initStatusName(hardware::Module::getInitStatus()))
        .field("mod.hardware.service",              "%s",   module::serviceStatusName(hardware::Module::getServiceStatus()))
        .field("mod.sysinfo.init",                  "%s",   module::initStatusName(sysinfo::Module::getInitStatus()))
        .field("mod.sysinfo.service",               "%s",   module::serviceStatusName(sysinfo::Module::getServiceStatus()))
        .field("mod.imu.init",                      "%s",   module::initStatusName(imu::Module::getInitStatus()))
        .field("mod.imu.service",                   "%s",   module::serviceStatusName(imu::Module::getServiceStatus()))
        .field("mod.cooling.init",                  "%s",   module::initStatusName(cooling::Module::getInitStatus()))
        .field("mod.cooling.service",               "%s",   module::serviceStatusName(cooling::Module::getServiceStatus()))
        .field("mod.dashboard.init",                "%s",   module::initStatusName(dashboard::Module::getInitStatus()))
        .field("mod.dashboard.service",             "%s",   module::serviceStatusName(dashboard::Module::getServiceStatus()))
        .field("mod.cold_head.init",                "%s",   module::initStatusName(cold_head::Module::getInitStatus()))
        .field("mod.cold_head.service",             "%s",   module::serviceStatusName(cold_head::Module::getServiceStatus()))
        // .field("mod.dac.init",                      "%s",   module::initStatusName(dac::Module::getInitStatus()))
        // .field("mod.dac.service",                   "%s",   module::serviceStatusName(dac::Module::getServiceStatus()))
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
