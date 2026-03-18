/**
 * @file telemetry_pb.cpp
 * @brief Protobuf binary encoder for telemetry WebSocket frames.
 *
 * Reads from the same module getter functions that telemetry::emit() uses
 * and encodes a cryocooler_TelemetryFrame using Nanopb.  The output is
 * sent over WebSocket as a binary message by dashboard.cpp.
 */

#include <Arduino.h>
#include <time.h>
#include <pb_encode.h>
#include "generated/telemetry.pb.h"
#include "telemetry_pb.h"
#include "cold_head.h"
#include "state_machine.h"
#include "indicator.h"
#include "sysinfo.h"
#include "cooling.h"
#include "amplifier.h"
#include "compressor.h"
#include "imu.h"
#include "ota.h"
#include "module.h"
#include "hardware.h"
#include "dashboard.h"
#include "commands.h"
#include "telemetry.h"
#include "logger.h"

namespace telemetry {

// Static frame struct — avoids stack allocation in the dashboard task.
// Only called from the single dashboard FreeRTOS task, so no reentrancy.
static cryocooler_TelemetryFrame frame_;

// Helper to safely copy a string into a fixed-size Nanopb char array.
static void copyStr(char* dst, size_t dstSize, const char* src) {
    if (!src) { dst[0] = '\0'; return; }
    strncpy(dst, src, dstSize - 1);
    dst[dstSize - 1] = '\0';
}

size_t encodeProtobuf(uint8_t* buf, size_t bufSize) {
    // Zero the frame so proto3 defaults apply for any fields we don't set.
    memset(&frame_, 0, sizeof(frame_));

    // ── Timestamp ────────────────────────────────────────────────────────────
    frame_.has_timestamp = true;
    frame_.timestamp.epoch = static_cast<int64_t>(time(nullptr));
    {
        const time_t now = time(nullptr);
        strftime(frame_.timestamp.local, sizeof(frame_.timestamp.local),
                 "%Y-%m-%d %H:%M:%S", localtime(&now));
    }

    // ── State machine ────────────────────────────────────────────────────────
    frame_.has_state = true;
    frame_.state.id = static_cast<int32_t>(state_machine::getState());
    copyStr(frame_.state.name, sizeof(frame_.state.name),
            state_machine::stateName(state_machine::getState()));
    copyStr(frame_.state.status_text, sizeof(frame_.state.status_text),
            state_machine::getStatusText());

    // ── Status ───────────────────────────────────────────────────────────────
    frame_.has_status = true;
    {
        const uint32_t durationMs = state_machine::getOnStateDuration();
        frame_.status.on_duration_ms = durationMs;

        const uint32_t durSec = durationMs / 1000u;
        snprintf(frame_.status.on_duration, sizeof(frame_.status.on_duration),
                 "%02lu:%02lu:%02lu",
                 static_cast<unsigned long>(durSec / 3600u),
                 static_cast<unsigned long>((durSec % 3600u) / 60u),
                 static_cast<unsigned long>(durSec % 60u));

        const uint32_t stateMs  = state_machine::getTimeInState();
        const uint32_t stateSec = stateMs / 1000u;
        snprintf(frame_.status.time_in_state, sizeof(frame_.status.time_in_state),
                 "%02lu:%02lu:%02lu",
                 static_cast<unsigned long>(stateSec / 3600u),
                 static_cast<unsigned long>((stateSec % 3600u) / 60u),
                 static_cast<unsigned long>(stateSec % 60u));

        // backoff_count: not directly accessible without the Output struct,
        // but it's available from the last emit() frame.  For now, read from
        // the last FrameBuilder frame if available.
        // Note: The FrameBuilder stores this as a uint, but we can't easily
        // extract it by name.  Set to 0 as a safe default — the JSON path
        // via fillJsonSafe already has this limitation during startup.
        frame_.status.backoff_count = 0;
    }

    // ── Cold head ────────────────────────────────────────────────────────────
    frame_.has_cold_head = true;
    if (!cold_head::hasSensorFault()) {
        frame_.cold_head.temp_c   = cold_head::getLastTempC();
        frame_.cold_head.has_temp = true;
        frame_.cold_head.cooldown_pct          = cold_head::getTemperatureToPercent();
        frame_.cold_head.delta_below_ambient_c = cold_head::getLastTempCBelowAmbient();
    } else {
        frame_.cold_head.temp_c   = 0.0f;
        frame_.cold_head.has_temp = false;
        frame_.cold_head.cooldown_pct          = 0.0f;
        frame_.cold_head.delta_below_ambient_c = 0.0f;
    }
    frame_.cold_head.voltage_v             = cold_head::getLastRmsVoltage();
    frame_.cold_head.current_a             = cold_head::getLastRmsCurrent();
    frame_.cold_head.ambient_temp_c        = cold_head::getLastAmbientTempC();

    // ── Amplifier ────────────────────────────────────────────────────────────
    frame_.has_amplifier = true;
    frame_.amplifier.voltage_v = amplifier::getLastRmsVoltage();
    frame_.amplifier.current_a = amplifier::getLastRmsCurrent();
    frame_.amplifier.power_w   = amplifier::getApparentPowerWatts();

    // ── System ───────────────────────────────────────────────────────────────
    frame_.has_system = true;
    frame_.system.voltage_v           = sysinfo::getVoltage();
    frame_.system.current_a           = sysinfo::getCurrent();
    frame_.system.power_w             = sysinfo::getPower();
    frame_.system.cpu_usage_percent   = sysinfo::getCpuUsagePercent();
    frame_.system.cpu_freq_mhz        = sysinfo::getCpuFreqMHz();
    frame_.system.heap_usage_percent  = sysinfo::getHeapUsagePercent();
    frame_.system.psram_usage_percent = sysinfo::getPsramUsagePercent();
    frame_.system.total_heap_bytes    = sysinfo::getTotalHeapBytes();
    frame_.system.total_psram_bytes   = sysinfo::getTotalPsramBytes();
    frame_.system.uptime_ms           = sysinfo::getUptimeMs();
    frame_.system.num_cores           = static_cast<uint32_t>(sysinfo::getNumCores());

    // ── IMU ──────────────────────────────────────────────────────────────────
    frame_.has_imu = true;
    frame_.imu.roll_deg  = imu::getRoll();
    frame_.imu.pitch_deg = imu::getPitch();
    frame_.imu.yaw_deg   = imu::getYaw();
    frame_.imu.accel_mag = imu::getAccelMag();
    frame_.imu.temp_c    = imu::getTemperature();
    frame_.imu.motion    = imu::isMotionDetected() ? 1u : 0u;
    frame_.imu.x         = imu::getAccelX();
    frame_.imu.y         = imu::getAccelY();
    frame_.imu.z         = imu::getAccelZ();
    {
        float freq = imu::getFrequency();
        frame_.imu.freq_hz = isnan(freq) ? 0.0f : freq;
    }

    // ── Cooling ──────────────────────────────────────────────────────────────
    frame_.has_cooling = true;
    frame_.cooling.status        = cooling::isEnabled() ? 1 : 0;
    frame_.cooling.pump_on       = cooling::isCoolingPumpOn() ? 1 : 0;
    frame_.cooling.temp_c        = cooling::getCoolantTemperature();
    frame_.cooling.flow_rate_lpm = cooling::getCoolantFlowRate();
    frame_.cooling.fan_speed     = cooling::getFanSpeed();
    frame_.cooling.fan_rpm       = cooling::getFanRPM();
    frame_.cooling.pump_speed    = cooling::getPumpSpeed();
    frame_.cooling.pump_rpm      = cooling::getPumpRPM();

    // ── Compressor ───────────────────────────────────────────────────────────
    frame_.has_compressor = true;
    frame_.compressor.status = compressor::getStatus() ? 1 : 0;

    // ── Relays ───────────────────────────────────────────────────────────────
    frame_.has_relay = true;
    frame_.relay.compressor_state = compressor::getStatus() ? 1 : 0;
    frame_.relay.amplifier_state  = amplifier::getRelayState() ? 1 : 0;

    // ── Indicators ───────────────────────────────────────────────────────────
    frame_.has_indicator = true;
    frame_.indicator.fault = indicator::isFaultOn() ? 1 : 0;
    frame_.indicator.ready = indicator::isReadyOn() ? 1 : 0;

    // ── Faults ───────────────────────────────────────────────────────────────
    frame_.has_faults = true;
    frame_.faults.count_10m = state_machine::countRecentFaults(600000u);
    frame_.faults.count_30m = state_machine::countRecentFaults(1800000u);
    frame_.faults.count_60m = state_machine::countRecentFaults(3600000u);

    // ── Firmware ─────────────────────────────────────────────────────────────
    frame_.has_firmware = true;
    copyStr(frame_.firmware.version, sizeof(frame_.firmware.version),
            ota::getFirmwareVersion());
    copyStr(frame_.firmware.build_date, sizeof(frame_.firmware.build_date),
            ota::getFirmwareBuildDate());
    frame_.firmware.ota_flash_ts = ota::getLastFlashTime();
    {
        const int64_t flashTs = ota::getLastFlashTime();
        if (flashTs > 0) {
            const time_t ft = static_cast<time_t>(flashTs);
            strftime(frame_.firmware.ota_flash_local,
                     sizeof(frame_.firmware.ota_flash_local),
                     "%Y-%m-%d %H:%M:%S", localtime(&ft));
        } else {
            copyStr(frame_.firmware.ota_flash_local,
                    sizeof(frame_.firmware.ota_flash_local), "never");
        }
    }

    // ── Scores ───────────────────────────────────────────────────────────────
    frame_.has_score = true;
    frame_.score.has_cooling = true;
    frame_.score.cooling.fan_speed    = cooling::getFanSpeedScore();
    frame_.score.cooling.coolant_temp = cooling::getCoolantTempScore();
    frame_.score.cooling.coolant_flow = cooling::getCoolantFlowScore();
    frame_.score.cooling.worst        = cooling::getWorstTrackingScore();

    // ── Module status ────────────────────────────────────────────────────────
    frame_.has_modules = true;

    #define FILL_MOD(field, ns) do { \
        frame_.modules.has_##field = true; \
        copyStr(frame_.modules.field.init, sizeof(frame_.modules.field.init), \
                module::initStatusName(ns::Module::getInitStatus())); \
        copyStr(frame_.modules.field.service, sizeof(frame_.modules.field.service), \
                module::serviceStatusName(ns::Module::getServiceStatus())); \
    } while(0)

    FILL_MOD(hardware,      hardware);
    FILL_MOD(sysinfo,       sysinfo);
    FILL_MOD(imu,           imu);
    FILL_MOD(cooling,       cooling);
    FILL_MOD(dashboard,     dashboard);
    FILL_MOD(cold_head,     cold_head);
    FILL_MOD(indicator,     indicator);
    FILL_MOD(state_machine, state_machine);
    FILL_MOD(commands,      commands);
    FILL_MOD(telemetry,     telemetry);

    #undef FILL_MOD

    // ── Log epoch ────────────────────────────────────────────────────────────
    frame_.log_epoch = logger::getLastLogEpoch();

    // ── Encode ───────────────────────────────────────────────────────────────
    pb_ostream_t stream = pb_ostream_from_buffer(buf, bufSize);
    if (!pb_encode(&stream, cryocooler_TelemetryFrame_fields, &frame_)) {
        return 0;
    }
    return stream.bytes_written;
}

} // namespace telemetry
