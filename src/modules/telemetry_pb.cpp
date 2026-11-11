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
// encodeProtobuf() is only called from the dashboard FreeRTOS task, so no
// reentrancy. Other callers of fillFrame() pass their own frame.
static cryocooler_TelemetryFrame frame_;

// Helper to safely copy a string into a fixed-size Nanopb char array.
static void copyStr(char* dst, size_t dstSize, const char* src) {
    if (!src) { dst[0] = '\0'; return; }
    strncpy(dst, src, dstSize - 1);
    dst[dstSize - 1] = '\0';
}

void fillFrame(cryocooler_TelemetryFrame& frame) {
    // Zero the frame so proto3 defaults apply for any fields we don't set.
    memset(&frame, 0, sizeof(frame));

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
    frame.has_timestamp = true;
    frame.timestamp.epoch = static_cast<int64_t>(time(nullptr));
    {
        const time_t now = time(nullptr);
        strftime(frame.timestamp.local, sizeof(frame.timestamp.local),
                 "%Y-%m-%d %H:%M:%S", localtime(&now));
    }

    // ── State machine ────────────────────────────────────────────────────────
    frame.has_state = true;
    frame.state.id = static_cast<int32_t>(state_machine::getState());
    copyStr(frame.state.name, sizeof(frame.state.name),
            state_machine::stateName(state_machine::getState()));
    copyStr(frame.state.status_text, sizeof(frame.state.status_text),
            state_machine::getStatusText());

    // ── Status ───────────────────────────────────────────────────────────────
    frame.has_status = true;
    {
        const uint32_t durationMs = state_machine::getOnStateDuration();
        frame.status.on_duration_ms = durationMs;

        const uint32_t durSec = durationMs / 1000u;
        snprintf(frame.status.on_duration, sizeof(frame.status.on_duration),
                 "%02lu:%02lu:%02lu",
                 static_cast<unsigned long>(durSec / 3600u),
                 static_cast<unsigned long>((durSec % 3600u) / 60u),
                 static_cast<unsigned long>(durSec % 60u));

        const uint32_t stateMs  = state_machine::getTimeInState();
        const uint32_t stateSec = stateMs / 1000u;
        snprintf(frame.status.time_in_state, sizeof(frame.status.time_in_state),
                 "%02lu:%02lu:%02lu",
                 static_cast<unsigned long>(stateSec / 3600u),
                 static_cast<unsigned long>((stateSec % 3600u) / 60u),
                 static_cast<unsigned long>(stateSec % 60u));

        frame.status.backoff_count = 0;
    }

    // ── Cold head ────────────────────────────────────────────────────────────
    frame.has_cold_head = true;
    if (coldHeadOk && !cold_head::hasSensorFault()) {
        frame.cold_head.temp_c   = cold_head::getLastTempC();
        frame.cold_head.has_temp = true;
        frame.cold_head.cooldown_pct          = cold_head::getTemperatureToPercent();
        frame.cold_head.delta_below_ambient_c = cold_head::getLastTempCBelowAmbient();
    } else {
        frame.cold_head.temp_c   = NAN;
        frame.cold_head.has_temp = false;
        frame.cold_head.cooldown_pct          = NAN;
        frame.cold_head.delta_below_ambient_c = NAN;
    }
    // voltage_v / current_a come from the amplifier module, gate on its status
    frame.cold_head.voltage_v  = amplifierOk ? cold_head::getLastRmsVoltage()  : NAN;
    frame.cold_head.current_a  = amplifierOk ? cold_head::getLastRmsCurrent()  : NAN;
    // ambient_temp_c comes from the IMU module, gate on its status
    frame.cold_head.ambient_temp_c = imuOk ? cold_head::getLastAmbientTempC() : NAN;
    frame.cold_head.target_temp_c  = cold_head::getTargetTempC();

    // ── Amplifier ────────────────────────────────────────────────────────────
    frame.has_amplifier = true;
    if (amplifierOk) {
        frame.amplifier.voltage_v = amplifier::getLastRmsVoltage();
        frame.amplifier.current_a = amplifier::getLastRmsCurrent();
        frame.amplifier.power_w   = amplifier::getApparentPowerWatts();
    } else {
        frame.amplifier.voltage_v = NAN;
        frame.amplifier.current_a = NAN;
        frame.amplifier.power_w   = NAN;
    }

    // ── System ───────────────────────────────────────────────────────────────
    frame.has_system = true;
    if (sysinfoOk) {
        frame.system.voltage_v           = sysinfo::getVoltage();
        frame.system.current_a           = sysinfo::getCurrent();
        frame.system.power_w             = sysinfo::getPower();
    } else {
        frame.system.voltage_v           = NAN;
        frame.system.current_a           = NAN;
        frame.system.power_w             = NAN;
    }
    // CPU/heap/PSRAM metrics come from the ESP32 itself (always available)
    frame.system.cpu_usage_percent   = sysinfo::getCpuUsagePercent();
    frame.system.cpu_freq_mhz        = sysinfo::getCpuFreqMHz();
    frame.system.heap_usage_percent  = sysinfo::getHeapUsagePercent();
    frame.system.psram_usage_percent = sysinfo::getPsramUsagePercent();
    frame.system.total_heap_bytes    = sysinfo::getTotalHeapBytes();
    frame.system.total_psram_bytes   = sysinfo::getTotalPsramBytes();
    frame.system.uptime_ms           = sysinfo::getUptimeMs();
    frame.system.num_cores           = static_cast<uint32_t>(sysinfo::getNumCores());

    // ── IMU ──────────────────────────────────────────────────────────────────
    frame.has_imu = true;
    if (imuOk) {
        frame.imu.roll_deg  = imu::getRoll();
        frame.imu.pitch_deg = imu::getPitch();
        frame.imu.yaw_deg   = imu::getYaw();
        frame.imu.accel_mag = imu::getAccelMag();
        frame.imu.temp_c    = imu::getTemperature();
        frame.imu.motion    = imu::isMotionDetected() ? 1u : 0u;
        frame.imu.x         = imu::getAccelX();
        frame.imu.y         = imu::getAccelY();
        frame.imu.z         = imu::getAccelZ();
        {
            const float freq = imu::getFrequency();
            frame.imu.freq_hz = isnan(freq) ? 0.0f : freq;
        }
    } else {
        frame.imu.roll_deg  = NAN;
        frame.imu.pitch_deg = NAN;
        frame.imu.yaw_deg   = NAN;
        frame.imu.accel_mag = NAN;
        frame.imu.temp_c    = NAN;
        frame.imu.motion    = 0u;
        frame.imu.x         = NAN;
        frame.imu.y         = NAN;
        frame.imu.z         = NAN;
        frame.imu.freq_hz   = NAN;
    }

    // ── Cooling ──────────────────────────────────────────────────────────────
    frame.has_cooling = true;
    if (coolingOk) {
        frame.cooling.status        = cooling::isEnabled() ? 1 : 0;
        frame.cooling.pump_on       = cooling::isCoolingPumpOn() ? 1 : 0;
        frame.cooling.temp_c        = cooling::getCoolantTemperature();
        frame.cooling.flow_rate_lpm = cooling::getCoolantFlowRate();
        frame.cooling.fan_speed     = static_cast<float>(cooling::getFanSpeed());
        frame.cooling.fan_rpm       = cooling::getFanRPM();
        frame.cooling.pump_speed    = static_cast<float>(cooling::getPumpSpeed());
        frame.cooling.pump_rpm      = cooling::getPumpRPM();
    } else {
        frame.cooling.status        = 0;
        frame.cooling.pump_on       = 0;
        frame.cooling.temp_c        = NAN;
        frame.cooling.flow_rate_lpm = NAN;
        frame.cooling.fan_speed     = NAN;
        frame.cooling.fan_rpm       = 0;
        frame.cooling.pump_speed    = NAN;
        frame.cooling.pump_rpm      = 0;
    }

    // ── Compressor ───────────────────────────────────────────────────────────
    frame.has_compressor = true;
    frame.compressor.status = compressor::getStatus() ? 1 : 0;

    // ── Relays ───────────────────────────────────────────────────────────────
    frame.has_relay = true;
    frame.relay.compressor_state = compressor::getStatus() ? 1 : 0;
    frame.relay.amplifier_state  = amplifier::getRelayState() ? 1 : 0;

    // ── Indicators ───────────────────────────────────────────────────────────
    frame.has_indicator = true;
    frame.indicator.fault = indicator::isFaultOn() ? 1 : 0;
    frame.indicator.ready = indicator::isReadyOn() ? 1 : 0;

    // ── Faults ───────────────────────────────────────────────────────────────
    frame.has_faults = true;
    frame.faults.count_10m = state_machine::countRecentFaults(600000u);
    frame.faults.count_30m = state_machine::countRecentFaults(1800000u);
    frame.faults.count_60m = state_machine::countRecentFaults(3600000u);

    // ── Firmware ─────────────────────────────────────────────────────────────
    frame.has_firmware = true;
    copyStr(frame.firmware.version, sizeof(frame.firmware.version),
            ota::getFirmwareVersion());
    copyStr(frame.firmware.build_date, sizeof(frame.firmware.build_date),
            ota::getFirmwareBuildDate());
    frame.firmware.ota_flash_ts = ota::getLastFlashTime();
    {
        const int64_t flashTs = ota::getLastFlashTime();
        if (flashTs > 0) {
            const time_t ft = static_cast<time_t>(flashTs);
            strftime(frame.firmware.ota_flash_local,
                     sizeof(frame.firmware.ota_flash_local),
                     "%Y-%m-%d %H:%M:%S", localtime(&ft));
        } else {
            copyStr(frame.firmware.ota_flash_local,
                    sizeof(frame.firmware.ota_flash_local), "never");
        }
    }

    // ── Scores ───────────────────────────────────────────────────────────────
    frame.has_score = true;
    frame.score.has_cooling = true;
    frame.score.cooling.fan_speed    = cooling::getFanSpeedScore();
    frame.score.cooling.coolant_temp = cooling::getCoolantTempScore();
    frame.score.cooling.coolant_flow = cooling::getCoolantFlowScore();
    frame.score.cooling.worst        = cooling::getWorstTrackingScore();

    // ── Module status ────────────────────────────────────────────────────────
    frame.has_modules = true;

    #define FILL_MOD(field, ns) do { \
        frame.modules.has_##field = true; \
        copyStr(frame.modules.field.init, sizeof(frame.modules.field.init), \
                module::initStatusName(ns::Module::getInitStatus())); \
        copyStr(frame.modules.field.service, sizeof(frame.modules.field.service), \
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
    frame.log_epoch = logger::getLastLogEpoch();
}

size_t encodeProtobuf(uint8_t* buf, size_t bufSize) {
    fillFrame(frame_);

    // ── Encode ───────────────────────────────────────────────────────────────
    pb_ostream_t stream = pb_ostream_from_buffer(buf, bufSize);
    if (!pb_encode(&stream, cryocooler_TelemetryFrame_fields, &frame_)) {
        return 0;
    }
    return stream.bytes_written;
}

} // namespace telemetry
