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

    // ── Service-status gating ────────────────────────────────────────────────
    // Mirror the buildStartupFrame() pattern from telemetry.cpp: if a module's
    // service() did not return OK or SKIPPED this tick, emit NAN for all its
    // float fields so the dashboard shows a gap in the chart line.  SKIPPED is
    // treated as valid because time-gated modules (e.g. cooling's 1 s check
    // cycle) return SKIPPED on ticks where they didn't run but their cached
    // readings are still valid.
    const auto svcOk = [](module::ServiceStatus s) {
        return s == module::MODULE_SERVICE_OK
            || s == module::MODULE_SERVICE_SKIPPED;
    };

    const bool coldHeadOk   = svcOk(cold_head::Module::getServiceStatus());
    const bool amplifierOk  = svcOk(amplifier::Module::getServiceStatus());
    const bool sysinfoOk    = svcOk(sysinfo::Module::getServiceStatus());
    const bool imuOk        = svcOk(imu::Module::getServiceStatus());
    const bool coolingOk    = svcOk(cooling::Module::getServiceStatus());

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

        frame_.status.backoff_count = 0;
    }

    // ── Cold head ────────────────────────────────────────────────────────────
    frame_.has_cold_head = true;
    if (coldHeadOk && !cold_head::hasSensorFault()) {
        frame_.cold_head.temp_c   = cold_head::getLastTempC();
        frame_.cold_head.has_temp = true;
        frame_.cold_head.cooldown_pct          = cold_head::getTemperatureToPercent();
        frame_.cold_head.delta_below_ambient_c = cold_head::getLastTempCBelowAmbient();
    } else {
        frame_.cold_head.temp_c   = NAN;
        frame_.cold_head.has_temp = false;
        frame_.cold_head.cooldown_pct          = NAN;
        frame_.cold_head.delta_below_ambient_c = NAN;
    }
    // voltage_v / current_a come from the amplifier module, gate on its status
    frame_.cold_head.voltage_v  = amplifierOk ? cold_head::getLastRmsVoltage()  : NAN;
    frame_.cold_head.current_a  = amplifierOk ? cold_head::getLastRmsCurrent()  : NAN;
    // ambient_temp_c comes from the IMU module, gate on its status
    frame_.cold_head.ambient_temp_c = imuOk ? cold_head::getLastAmbientTempC() : NAN;
    frame_.cold_head.target_temp_c  = cold_head::getTargetTempC();

    // ── Amplifier ────────────────────────────────────────────────────────────
    frame_.has_amplifier = true;
    if (amplifierOk) {
        frame_.amplifier.voltage_v = amplifier::getLastRmsVoltage();
        frame_.amplifier.current_a = amplifier::getLastRmsCurrent();
        frame_.amplifier.power_w   = amplifier::getApparentPowerWatts();
    } else {
        frame_.amplifier.voltage_v = NAN;
        frame_.amplifier.current_a = NAN;
        frame_.amplifier.power_w   = NAN;
    }

    // ── System ───────────────────────────────────────────────────────────────
    frame_.has_system = true;
    if (sysinfoOk) {
        frame_.system.voltage_v           = sysinfo::getVoltage();
        frame_.system.current_a           = sysinfo::getCurrent();
        frame_.system.power_w             = sysinfo::getPower();
    } else {
        frame_.system.voltage_v           = NAN;
        frame_.system.current_a           = NAN;
        frame_.system.power_w             = NAN;
    }
    // CPU/heap/PSRAM metrics come from the ESP32 itself (always available)
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
    if (imuOk) {
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
            const float freq = imu::getFrequency();
            frame_.imu.freq_hz = isnan(freq) ? 0.0f : freq;
        }
    } else {
        frame_.imu.roll_deg  = NAN;
        frame_.imu.pitch_deg = NAN;
        frame_.imu.yaw_deg   = NAN;
        frame_.imu.accel_mag = NAN;
        frame_.imu.temp_c    = NAN;
        frame_.imu.motion    = 0u;
        frame_.imu.x         = NAN;
        frame_.imu.y         = NAN;
        frame_.imu.z         = NAN;
        frame_.imu.freq_hz   = NAN;
    }

    // ── Cooling ──────────────────────────────────────────────────────────────
    frame_.has_cooling = true;
    if (coolingOk) {
        frame_.cooling.status        = cooling::isEnabled() ? 1 : 0;
        frame_.cooling.pump_on       = cooling::isCoolingPumpOn() ? 1 : 0;
        frame_.cooling.temp_c        = cooling::getCoolantTemperature();
        frame_.cooling.flow_rate_lpm = cooling::getCoolantFlowRate();
        frame_.cooling.fan_speed     = static_cast<float>(cooling::getFanSpeed());
        frame_.cooling.fan_rpm       = cooling::getFanRPM();
        frame_.cooling.pump_speed    = static_cast<float>(cooling::getPumpSpeed());
        frame_.cooling.pump_rpm      = cooling::getPumpRPM();
    } else {
        frame_.cooling.status        = 0;
        frame_.cooling.pump_on       = 0;
        frame_.cooling.temp_c        = NAN;
        frame_.cooling.flow_rate_lpm = NAN;
        frame_.cooling.fan_speed     = NAN;
        frame_.cooling.fan_rpm       = 0;
        frame_.cooling.pump_speed    = NAN;
        frame_.cooling.pump_rpm      = 0;
    }

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
