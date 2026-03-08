/**
 * @file espnow.h
 * @brief ESP-NOW peer-to-peer telemetry bridge.
 *
 * Transmits a packed TelemetryPacket snapshot to a single configured peer
 * ESP32 over ESP-NOW while WiFi (STA mode), the HTTP dashboard, and OTA
 * firmware updates continue to operate normally.  Both transports share the
 * same radio; the ESP-NOW channel follows the AP channel automatically.
 *
 * ── Wire format ──────────────────────────────────────────────────────────────
 * Each transmission is a single esp_now_send() call carrying sizeof(TelemetryPacket)
 * bytes (currently 137 bytes).  No fragmentation is required — the struct is
 * intentionally sized to fit within the 250-byte ESP-NOW frame limit.
 *
 * The TelemetryPacket struct is defined in this header so both the sender and
 * the receiver can include it.  Both sides must compile with ENABLE_ESPNOW=true.
 *
 * ── Peer channel requirement ─────────────────────────────────────────────────
 * The peer ESP32 must operate on the same WiFi channel as this device's AP.
 * If the peer is not connected to the same AP, configure it explicitly with:
 *   esp_wifi_set_channel(<channel>, WIFI_SECOND_CHAN_NONE)
 * where <channel> is the value reported by WiFi.channel() on this device.
 *
 * ── Enable / configure ───────────────────────────────────────────────────────
 *   ENABLE_ESPNOW            true / false  (default false — set peer MAC first)
 *   ESPNOW_PEER_MAC          6-byte MAC of the receiving device
 *   ESPNOW_SEND_INTERVAL_MS  Packet period in milliseconds (default 1000)
 *
 * All three are defined in config.h.
 */

#pragma once

#include "config.h"
#include "module.h"
#include <stdint.h>

#if ENABLE_ESPNOW

/**
 * Packed telemetry snapshot transmitted over ESP-NOW.
 *
 * Fits in a single 250-byte ESP-NOW frame (sizeof == 137 bytes), so no
 * fragmentation is required.  The struct layout is shared between the sender
 * and receiver — include this header on both sides.
 *
 * All floating-point fields use IEEE 754 single precision.
 * __attribute__((packed)) removes compiler-inserted padding; unaligned
 * float reads on the ESP32 (Xtensa LX7) are handled transparently in hardware.
 *
 * Field name conventions mirror the telemetry JSON keys used by the dashboard.
 */
struct __attribute__((packed)) TelemetryPacket {
    // ── Timestamp ─────────────────────────────────────────────────────────
    int64_t  timestamp_epoch;               ///< Unix time (UTC); 0 before SNTP sync

    // ── State machine ──────────────────────────────────────────────────────
    int8_t   state_id;                      ///< state_machine::State cast to int8_t
    uint32_t status_on_duration_ms;         ///< cumulative on-state duration in ms
    uint32_t status_time_in_state_ms;       ///< time in current state in ms
    uint8_t  faults_count_10m;              ///< fault entries in last 10 min
    uint8_t  faults_count_30m;              ///< fault entries in last 30 min
    uint8_t  faults_count_60m;              ///< fault entries in last 60 min

    // ── Cold head ─────────────────────────────────────────────────────────
    float    cold_head_temp_k;
    float    cold_head_temp_c;
    float    cold_head_ambient_temp_c;
    float    cold_head_delta_below_ambient_c;
    float    cold_head_cooling_rate;        ///< K/min; positive = cooling
    float    cold_head_cooldown_pct;        ///< 0–100 %
    float    cold_head_voltage_v;
    float    cold_head_current_a;

    // ── Amplifier ─────────────────────────────────────────────────────────
    float    amplifier_voltage_v;
    float    amplifier_current_a;

    // ── System supply ──────────────────────────────────────────────────────
    float    system_voltage_v;
    float    system_current_a;
    float    system_power_w;

    // ── IMU ───────────────────────────────────────────────────────────────
    float    imu_roll_deg;
    float    imu_pitch_deg;
    float    imu_yaw_deg;
    float    imu_accel_mag;
    float    imu_temp_c;
    float    imu_x;
    float    imu_y;
    float    imu_z;
    uint8_t  imu_motion;                    ///< 1 = motion/overstroke detected

    // ── Cooling loop ──────────────────────────────────────────────────────
    float    cooling_temp_c;
    float    cooling_flow_rate_lpm;
    uint16_t cooling_fan_speed;             ///< PWM duty (0–100)
    uint16_t cooling_fan_rpm;
    uint8_t  cooling_status;               ///< 1 = cooling enabled
    uint8_t  cooling_pump_on;              ///< 1 = pump active

    // ── Tracking scores ───────────────────────────────────────────────────
    float    score_fan_speed;
    float    score_coolant_temp;
    float    score_coolant_flow;
    float    score_worst;

    // ── Indicators ────────────────────────────────────────────────────────
    uint8_t  indicator_fault;              ///< 1 = FAULT LED on
    uint8_t  indicator_ready;              ///< 1 = READY LED on
};

static_assert(sizeof(TelemetryPacket) <= 250,
              "TelemetryPacket exceeds the 250-byte ESP-NOW frame limit");

namespace espnow {

/**
 * Initialise ESP-NOW, register the send callback, and add the peer.
 *
 * Must be called after WiFi has connected (i.e. after dashboard::init()).
 * Pins a FreeRTOS task to Core 0 that fills a TelemetryPacket from the current
 * module state and transmits it at ESPNOW_SEND_INTERVAL_MS.
 *
 * Returns:
 *   MODULE_INIT_SUCCESS          — ready to transmit.
 *   MODULE_INIT_DEPENDENCY_ERROR — WiFi not connected, or esp_now_init()/
 *                                  esp_now_add_peer() returned an error.
 */
module::InitStatus init();

/**
 * No-op stub — the ESP-NOW task self-schedules on Core 0.
 * Present so espnow::Module satisfies the ModuleBase interface.
 */
module::ServiceStatus service();

/** Total successful packet deliveries (cumulative since boot). */
uint32_t getSentCount();

/** Total packet delivery failures (cumulative since boot). */
uint32_t getFailCount();

/** True once init() has completed successfully. */
bool isReady();

/**
 * Forward a console log message to the control panel over ESP-NOW.
 *
 * The text is prefixed with a 0x01 marker byte (SOH) so the receiver can
 * distinguish it from command-response packets (which always begin with the
 * printable '[' character).  The caller is responsible for also writing to
 * Serial if UART output is still required.
 *
 * Falls through silently if ESP-NOW is not yet initialised or @p text is
 * empty.  Safe to call from any FreeRTOS task context.
 */
void consoleLog(const char* text);

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return espnow::init(); }
    static module::ServiceStatus service() { return espnow::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace espnow

#endif // ENABLE_ESPNOW
