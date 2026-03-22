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
#include <esp_idf_version.h>

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
            ESP_LOGV(TAG, "onSent SUCCESS (%lu deliveries)", static_cast<unsigned long>(sentCount_));
        }
    } else {
        ++failCount_;
        if (failCount_ % 100 == 0) {
            ESP_LOGV(TAG, "onSent FAIL status=%d (%lu failures)", static_cast<int>(status), static_cast<unsigned long>(failCount_));
        }
    }
}

// ─── ESP-NOW response sink ────────────────────────────────────────────────────

/**
 * Arduino Print subclass that buffers output from commands::processLine() and
 * ships it back to the command sender via esp_now_send().
 *
 * Rationale
 * ─────────
 * commands::processLine(line, Print& out) is transport-agnostic.  By passing
 * an EspNowPrint instead of Serial, every response line (status text, error
 * messages, "OK", etc.) is sent back to the control panel over the air rather
 * than (only) appearing on the USB console.
 *
 * Wire behaviour
 * ──────────────
 * Output is accumulated into a 246-byte chunk buffer.  When the chunk is full,
 * or when the object is destroyed (end of processLine's scope), the buffered
 * bytes are sent as a single esp_now_send() call.  Each chunk therefore fits
 * inside the 250-byte ESP-NOW frame limit with four bytes of headroom.
 *
 * Calling esp_now_send() from within the recv callback (WiFi-task context) is
 * explicitly supported by ESP-IDF; the maximum payload is 250 bytes.
 *
 * The sender MAC must already be registered as an ESP-NOW peer (peerMac_ is
 * registered during init(), so any packet from that peer can be replied to).
 */
class EspNowPrint : public Print {
public:
    explicit EspNowPrint(const uint8_t* mac) noexcept {
        memcpy(mac_, mac, 6);
    }

    ~EspNowPrint() { flush(); }

    size_t write(uint8_t c) override {
        buf_[len_++] = static_cast<char>(c);
        if (len_ >= kChunkSize) { flush(); }
        return 1;
    }

    size_t write(const uint8_t* data, size_t size) override {
        size_t written = 0;
        while (written < size) {
            const size_t space = kChunkSize - len_;
            const size_t copy  = (size - written) < space ? (size - written) : space;
            memcpy(buf_ + len_, data + written, copy);
            len_    += copy;
            written += copy;
            if (len_ >= kChunkSize) { flush(); }
        }
        return size;
    }

    void flush() override {
        if (len_ == 0) return;
        const esp_err_t err = esp_now_send(
            mac_,
            reinterpret_cast<const uint8_t*>(buf_),
            len_);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "EspNowPrint::flush esp_now_send failed: 0x%x",
                     static_cast<unsigned>(err));
        }
        len_ = 0;
    }

private:
    /** Leave 4 bytes headroom inside the 250-byte ESP-NOW frame limit. */
    static constexpr size_t kChunkSize = 246;

    uint8_t mac_[6];
    char    buf_[kChunkSize];
    size_t  len_ = 0;
};

// ─── Receive callback ─────────────────────────────────────────────────────────

/**
 * Called by the ESP-NOW driver when a frame arrives from any peer.
 *
 * The payload is treated as a raw command string — identical to a line typed
 * into the serial console.  The bytes are copied into a local null-terminated
 * buffer, any trailing CR/LF is stripped, and the result is forwarded to
 * commands::processLine() with an EspNowPrint sink so the response text is
 * sent back to the sender over the air.
 *
 * This callback runs in the WiFi task context (same as the TCP command path),
 * so it is safe to call both commands::processLine() and esp_now_send() here.
 *
 * Callback signature: ESP-IDF 5.x changed esp_now_recv_cb_t so the first
 * argument is const esp_now_recv_info_t* rather than const uint8_t* (MAC).
 * The version guard below keeps this compiling on both IDF 4.x and 5.x.
 */
#if ESP_IDF_VERSION_MAJOR >= 5
static void onReceived(const esp_now_recv_info_t* info, const uint8_t* data, int len) {
    const uint8_t* mac = info->src_addr;
#else
static void onReceived(const uint8_t* mac, const uint8_t* data, int len) {
#endif
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

    // Route the response back to the sender over ESP-NOW.
    // EspNowPrint buffers write() calls and flushes via esp_now_send() on
    // destruction, so the complete response is transmitted when processLine()
    // returns and espNowOut goes out of scope.
    EspNowPrint espNowOut(mac);
    commands::processLine(buf, espNowOut);
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
    pkt.faults_count_10m       = state_machine::countRecentFaults(600000u);
    pkt.faults_count_30m       = state_machine::countRecentFaults(1800000u);
    pkt.faults_count_60m       = state_machine::countRecentFaults(3600000u);

    // Cold head
    pkt.cold_head_temp_c                  = cold_head::getLastTempC();
    pkt.cold_head_ambient_temp_c          = cold_head::getLastAmbientTempC();
    pkt.cold_head_delta_below_ambient_c   = cold_head::getLastTempCBelowAmbient();
    pkt.cold_head_cooling_rate            = cold_head::getCoolingRateCPerMin();
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
    pkt.cooling_pump_speed    = cooling::getPumpSpeed();
    pkt.cooling_pump_rpm      = cooling::getPumpRPM();
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

    // ── Backoff state ──────────────────────────────────────────────────────────
    // After FAIL_THRESHOLD consecutive send failures the task stops logging and
    // skips sends for BACKOFF_TICKS ticks (~30 s at the default 1 Hz send rate).
    // This prevents the serial output from being flooded when the peer is off.
    // The first FAIL_THRESHOLD failures are still logged so the cause is visible.
    static constexpr uint8_t  FAIL_THRESHOLD  = 5;
    static constexpr uint32_t BACKOFF_TICKS   = 30;

    uint8_t  consecutiveFails = 0;
    uint32_t backoffRemaining = 0;

    for (;;) {
        // Accurate period regardless of fill / send duration.
        vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(ESPNOW_SEND_INTERVAL_MS));

        if (!ready_) continue;

        // ── Backoff: skip silently until the cooldown expires ──────────────
        if (backoffRemaining > 0) {
            if (--backoffRemaining == 0) {
                ESP_LOGI(TAG, "Backoff expired — retrying peer");
                consecutiveFails = 0;
            }
            continue;
        }

        fillPacket(pkt);

        const esp_err_t err = esp_now_send(
            peerMac_,
            reinterpret_cast<const uint8_t*>(&pkt),
            sizeof(pkt));

        if (err != ESP_OK) {
            ++failCount_;
            ++consecutiveFails;
            if (consecutiveFails < FAIL_THRESHOLD) {
                // Log each of the first few failures so the error is visible.
                ESP_LOGE(TAG, "esp_now_send failed: 0x%x", static_cast<unsigned>(err));
            } else if (consecutiveFails == FAIL_THRESHOLD) {
                // One final warning, then go silent for BACKOFF_TICKS ticks.
                ESP_LOGW(TAG, "Peer unreachable after %u consecutive fails "
                              "(err 0x%x) — suppressing logs for %lu s",
                         static_cast<unsigned>(consecutiveFails),
                         static_cast<unsigned>(err),
                         static_cast<unsigned long>(
                             BACKOFF_TICKS * ESPNOW_SEND_INTERVAL_MS / 1000u));
                backoffRemaining = BACKOFF_TICKS;
            }
            // While backoffRemaining > 0, the top-of-loop guard handles silence.
        } else {
            // Successful send — reset backoff state.
            if (consecutiveFails > 0) {
                ESP_LOGI(TAG, "Peer reachable again");
            }
            consecutiveFails = 0;
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
