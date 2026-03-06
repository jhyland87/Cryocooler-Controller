/**
 * @file espnow.cpp
 * @brief ESP-NOW peer-to-peer telemetry bridge — implementation.
 *
 * Architecture
 * ────────────
 * A dedicated FreeRTOS task (Core 0, alongside the WiFi/TCPIP stack) owns all
 * ESP-NOW I/O.  The Arduino loop task (Core 1) never touches ESP-NOW directly;
 * espnow::service() is a no-op stub that satisfies the ModuleBase interface.
 *
 * Why Core 0?
 * ───────────
 * esp_now_send() is documented to be callable from any task, but internally it
 * posts to the WiFi driver running on Core 0.  Placing the sender on the same
 * core eliminates cross-core IPC overhead and lets the sender yield (via
 * vTaskDelay) without introducing latency on the control loop.
 *
 * Coexistence with WiFi
 * ─────────────────────
 * WiFi (STA) and ESP-NOW share the same 2.4 GHz radio under the ESP-IDF
 * software MAC.  When the STA interface is associated with an AP, ESP-NOW
 * automatically uses the AP's channel for all outbound frames — no explicit
 * channel configuration is required on this device.
 *
 * The peer ESP32 must be configured to listen on the same channel.  If the
 * peer is not associated with the same AP, use esp_wifi_set_channel() there.
 * Run `Serial.println(WiFi.channel())` on this board to find the channel.
 *
 * Wire format
 * ───────────
 * Each transmission is a single esp_now_send() call carrying
 * sizeof(TelemetryPacket) bytes (currently 137 bytes).  The struct fits within
 * the 250-byte ESP-NOW frame limit, so no fragmentation or reassembly is
 * required.  The receiver casts the incoming data pointer directly to
 * const TelemetryPacket* after verifying the length.
 */

#include "espnow.h"

#if ENABLE_ESPNOW

#include "config.h"
#include "commands.h"
#include "state_machine.h"
#include "cold_head.h"
#include "amplifier.h"
#include "sysinfo.h"
#include "imu.h"
#include "cooling.h"
#include "indicator.h"
#include "esp_log.h"

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <time.h>

static constexpr char TAG[] = "espnow";

namespace espnow {

// ─── FreeRTOS task parameters ─────────────────────────────────────────────────

/** Task stack in bytes (NOTE: ESP-IDF xTaskCreate takes bytes, not words). */
static constexpr uint32_t    TASK_STACK_BYTES = 4096;

/** Low priority — yields freely; does not compete with the control loop. */
static constexpr UBaseType_t TASK_PRIORITY    = 1;

// ─── Module state ──────────────────────────────────────────────────────────────

static volatile bool     ready_     = false;
static volatile uint32_t sentCount_ = 0;   ///< Successful packet deliveries
static volatile uint32_t failCount_ = 0;   ///< Failed packet deliveries
static uint8_t           peerMac_[6] = ESPNOW_PEER_MAC;

// ─── Send-complete callback ────────────────────────────────────────────────────

/**
 * Called by the ESP-NOW driver (in the WiFi task context) once the MAC-layer
 * delivery attempt for a single frame is complete.
 */
static void onSent(const uint8_t* /*mac*/, esp_now_send_status_t status) {
    if (status == ESP_NOW_SEND_SUCCESS) {
        ++sentCount_;
        if (sentCount_ % 100 == 0) {
            ESP_LOGI(TAG, "onSent SUCCESS (%lu deliveries)", static_cast<unsigned long>(sentCount_));
        }
    } else {
        ++failCount_;
        if (failCount_ % 100 == 0) {
            ESP_LOGW(TAG, "onSent FAIL status=%d (%lu failures)", static_cast<int>(status), static_cast<unsigned long>(failCount_));
        }
    }
}

// ─── Receive callback ─────────────────────────────────────────────────────────

/**
 * Called by the ESP-NOW driver when a frame arrives from any peer.
 *
 * The payload is treated as a raw command string — identical to a line typed
 * into the serial console.  The bytes are copied into a local null-terminated
 * buffer, any trailing CR/LF is stripped, and the result is forwarded to
 * commands::processLine() with Serial as the response sink.
 *
 * This callback runs in the WiFi task context (same as the TCP command path),
 * so it is safe to call commands::processLine() here.
 */
static void onReceived(const uint8_t* mac, const uint8_t* data, int len) {
    ESP_LOGI(TAG, "onReceived from %02X:%02X:%02X:%02X:%02X:%02X, len=%d",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], len);
    if (len <= 0) return;

    // Clamp to the maximum ESP-NOW payload so the buffer is always sufficient.
    static constexpr int CMD_BUF_LEN = 250;
    char buf[CMD_BUF_LEN + 1];

    const int copyLen = (len < CMD_BUF_LEN) ? len : CMD_BUF_LEN;
    memcpy(buf, data, static_cast<size_t>(copyLen));
    buf[copyLen] = '\0';

    // Strip trailing CR / LF so processLine() sees a clean token.
    int end = copyLen - 1;
    while (end >= 0 && (buf[end] == '\r' || buf[end] == '\n')) {
        buf[end--] = '\0';
    }

    if (buf[0] == '\0') return;   // nothing left after stripping

    ESP_LOGI(TAG, "cmd from %02X:%02X:%02X:%02X:%02X:%02X: \"%s\"",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5], buf);

    commands::processLine(buf, Serial);
}

// ─── Packet fill ───────────────────────────────────────────────────────────────

/**
 * Populate @p pkt with a snapshot of the current module state.
 * Mirrors the fields emitted by telemetry::emit() / buildStartupFrame().
 */
static void fillPacket(TelemetryPacket& pkt) {
    // Timestamp
    pkt.timestamp_epoch = static_cast<int64_t>(time(nullptr));

    // State machine
    pkt.state_id               = static_cast<int8_t>(state_machine::getState());
    pkt.status_on_duration_ms  = state_machine::getOnStateDuration();
    pkt.status_time_in_state_ms = state_machine::getTimeInState();
    const uint32_t nowMs       = millis();
    pkt.faults_count_10m       = state_machine::countRecentFaults(600000u,  nowMs);
    pkt.faults_count_30m       = state_machine::countRecentFaults(1800000u, nowMs);
    pkt.faults_count_60m       = state_machine::countRecentFaults(3600000u, nowMs);

    // Cold head
    pkt.cold_head_temp_k                  = cold_head::getLastTempK();
    pkt.cold_head_temp_c                  = cold_head::getLastTempC();
    pkt.cold_head_ambient_temp_c          = cold_head::getLastAmbientTempC();
    pkt.cold_head_delta_below_ambient_c   = cold_head::getLastTempCBelowAmbient();
    pkt.cold_head_cooling_rate            = cold_head::getCoolingRateKPerMin();
    pkt.cold_head_cooldown_pct            = cold_head::getTemperatureToPercent();
    pkt.cold_head_voltage_v               = cold_head::getLastRmsVoltage();
    pkt.cold_head_current_a               = cold_head::getLastRmsCurrent();

    // Amplifier
    pkt.amplifier_voltage_v = amplifier::getLastRmsVoltage();
    pkt.amplifier_current_a = amplifier::getLastRmsCurrent();

    // System supply
    pkt.system_voltage_v = sysinfo::getVoltage();
    pkt.system_current_a = sysinfo::getCurrent();
    pkt.system_power_w   = sysinfo::getPower();

    // IMU
    pkt.imu_roll_deg  = imu::getRoll();
    pkt.imu_pitch_deg = imu::getPitch();
    pkt.imu_yaw_deg   = imu::getYaw();
    pkt.imu_accel_mag = imu::getAccelMag();
    pkt.imu_temp_c    = imu::getTemperature();
    pkt.imu_x         = imu::getAccelX();
    pkt.imu_y         = imu::getAccelY();
    pkt.imu_z         = imu::getAccelZ();
    pkt.imu_motion    = static_cast<uint8_t>(imu::isMotionDetected());

    // Cooling loop
    pkt.cooling_temp_c        = cooling::getCoolantTemperature();
    pkt.cooling_flow_rate_lpm = cooling::getCoolantFlowRate();
    pkt.cooling_fan_speed     = cooling::getFanSpeed();
    pkt.cooling_fan_rpm       = cooling::getFanRPM();
    pkt.cooling_status        = static_cast<uint8_t>(cooling::isEnabled());
    pkt.cooling_pump_on       = static_cast<uint8_t>(cooling::isCoolingPumpOn());

    // Tracking scores
    pkt.score_fan_speed    = cooling::getFanSpeedScore();
    pkt.score_coolant_temp = cooling::getCoolantTempScore();
    pkt.score_coolant_flow = cooling::getCoolantFlowScore();
    pkt.score_worst        = cooling::getWorstTrackingScore();

    // Indicators
    pkt.indicator_fault = static_cast<uint8_t>(indicator::isFaultOn());
    pkt.indicator_ready = static_cast<uint8_t>(indicator::isReadyOn());
}

// ─── ESP-NOW FreeRTOS task ─────────────────────────────────────────────────────

static void espnowTask(void* /*arg*/) {
    // Static buffer — lives in BSS, not on the task stack.
    static TelemetryPacket pkt;

    TickType_t lastWakeTime = xTaskGetTickCount();

    for (;;) {
        // Accurate period regardless of fill / send duration.
        vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(ESPNOW_SEND_INTERVAL_MS));

        if (!ready_) continue;

        fillPacket(pkt);

        const esp_err_t err = esp_now_send(
            peerMac_,
            reinterpret_cast<const uint8_t*>(&pkt),
            sizeof(pkt));

        if (err != ESP_OK) {
            ESP_LOGE(TAG, "esp_now_send failed: 0x%x", static_cast<unsigned>(err));
            ++failCount_;
        }
    }
}

// ─── Public API ────────────────────────────────────────────────────────────────

module::InitStatus init() {
    // ESP-NOW channel follows the STA association — WiFi must be up first.
    if (WiFi.status() != WL_CONNECTED) {
        ESP_LOGE(TAG, "WiFi not connected — skipping ESP-NOW init");
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }

    if (esp_now_init() != ESP_OK) {
        ESP_LOGE(TAG, "esp_now_init() failed");
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }

    ESP_LOGI(TAG, "Registering send/receive callbacks");
    esp_now_register_send_cb(onSent);
    esp_now_register_recv_cb(onReceived);

    ESP_LOGI(TAG, "Registering peer %02X:%02X:%02X:%02X:%02X:%02X",
             peerMac_[0], peerMac_[1], peerMac_[2],
             peerMac_[3], peerMac_[4], peerMac_[5]);

    // channel = 0 means "follow current WiFi STA channel".
    esp_now_peer_info_t peer{};
    memcpy(peer.peer_addr, peerMac_, 6);
    peer.channel = 0;
    peer.encrypt = false;
    peer.ifidx   = WIFI_IF_STA;

    if (esp_now_add_peer(&peer) != ESP_OK) {
        ESP_LOGE(TAG, "esp_now_add_peer() failed");
        esp_now_deinit();
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }

    ESP_LOGI(TAG, "Peer registered on channel %d (WiFi STA)  packet size: %u bytes",
             WiFi.channel(), static_cast<unsigned>(sizeof(TelemetryPacket)));

    // Pin the task to Core 0 so it runs alongside the WiFi/TCPIP stack and
    // vTaskDelayUntil() yields do not stall the control loop on Core 1.
    xTaskCreatePinnedToCore(
        espnowTask,
        "espnow",
        TASK_STACK_BYTES,
        nullptr,
        TASK_PRIORITY,
        nullptr,
        0   // Core 0
    );

    ready_ = true;
    return module::MODULE_INIT_SUCCESS;
}

/**
 * No-op: the ESP-NOW task manages its own schedule.
 * Kept so espnow::Module satisfies the ModuleBase interface.
 */
module::ServiceStatus service() {
    return module::MODULE_SERVICE_SKIPPED;
}

uint32_t getSentCount() { return sentCount_; }
uint32_t getFailCount() { return failCount_; }
bool     isReady()      { return ready_; }

} // namespace espnow

#endif // ENABLE_ESPNOW
