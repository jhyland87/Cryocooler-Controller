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
 * vTaskDelay) to allow the TX queue to drain between chunks without
 * introducing latency on the control loop.
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
 * Fragmentation
 * ─────────────
 * ESP-NOW frames are limited to 250 bytes.  Telemetry JSON is typically
 * 1–3 KB, so it must be split.  Each chunk carries a 4-byte header:
 *
 *   [0] msg_id       uint8_t  — rolling counter; identifies one logical message
 *   [1] total        uint8_t  — total chunk count for this message
 *   [2] index        uint8_t  — zero-based chunk index (0 … total-1)
 *   [3] len          uint8_t  — JSON payload bytes in this chunk (1–246)
 *   [4 … 4+len-1]   char[]   — UTF-8 JSON fragment
 *
 * The peer collects all chunks with matching msg_id, concatenates them in
 * index order, and parses the resulting string as JSON.
 *
 * Inter-chunk pacing
 * ──────────────────
 * esp_now_send() is non-blocking but posts to a bounded internal TX queue
 * (default depth ≈ 6 frames).  Sending all chunks back-to-back overflows the
 * queue for messages > 6 chunks.  A short vTaskDelay(INTER_CHUNK_DELAY_MS)
 * between chunks yields to the WiFi driver so it can drain the queue before
 * the next submission.  At 5 ms per chunk, a typical 12-chunk message
 * (~2.9 KB) completes in ~60 ms — well within the 1 s send interval.
 */

#include "espnow.h"

#if ENABLE_ESPNOW

#include "config.h"
#include "telemetry.h"

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <ArduinoJson.h>

namespace espnow {

// ─── Protocol constants ────────────────────────────────────────────────────────

/** Hard limit imposed by the ESP-NOW spec (bytes per frame). */
static constexpr size_t ESPNOW_MAX_FRAME   = 250;

/** Bytes consumed by the chunk header. */
static constexpr size_t HEADER_SIZE        = 4;

/** Maximum JSON payload that fits in one ESP-NOW frame. */
static constexpr size_t CHUNK_PAYLOAD      = ESPNOW_MAX_FRAME - HEADER_SIZE;   // 246

/**
 * JSON serialisation buffer.  Sized to match the HTTP /api/telemetry buffer
 * so the same full telemetry snapshot is forwarded over ESP-NOW.
 * Declared as a module-level static so it is not placed on the task stack.
 */
static constexpr size_t JSON_BUF_SIZE      = 8192;

// ─── FreeRTOS task parameters ─────────────────────────────────────────────────

/** Task stack in bytes (NOTE: ESP-IDF xTaskCreate takes bytes, not words). */
static constexpr uint32_t    TASK_STACK_BYTES  = 8192;

/** Low priority — yields freely; does not compete with the control loop. */
static constexpr UBaseType_t TASK_PRIORITY     = 1;

/**
 * Pause between successive chunks (milliseconds).
 * Gives the WiFi TX queue time to drain so esp_now_send() does not return
 * ESP_ERR_ESPNOW_NO_MEM on long messages.
 */
static constexpr uint32_t INTER_CHUNK_DELAY_MS = 5;

// ─── Module state ──────────────────────────────────────────────────────────────

static volatile bool     ready_     = false;
static volatile uint32_t sentCount_ = 0;   ///< Successful chunk deliveries
static volatile uint32_t failCount_ = 0;   ///< Failed chunk deliveries
static uint8_t           msgId_     = 0;   ///< Rolling message counter (wraps at 255)
static uint8_t           peerMac_[6] = ESPNOW_PEER_MAC;

// ─── Send-complete callback ────────────────────────────────────────────────────

/**
 * Called by the ESP-NOW driver (in the WiFi task context) once the MAC-layer
 * delivery attempt for a single frame is complete.
 *
 * Volatile counters are sufficient here: we only need monotone counts for
 * diagnostic display and do not require atomic read-modify-write guarantees.
 */
static void onSent(const uint8_t* /*mac*/, esp_now_send_status_t status) {
    if (status == ESP_NOW_SEND_SUCCESS) {
        ++sentCount_;
    } else {
        ++failCount_;
    }
}

// ─── ESP-NOW FreeRTOS task ─────────────────────────────────────────────────────

static void espnowTask(void* /*arg*/) {
    // Static buffers — must not live on the task stack (8 KB would overflow it).
    static char    jsonBuf[JSON_BUF_SIZE];
    static uint8_t packet[ESPNOW_MAX_FRAME];

    TickType_t lastWakeTime = xTaskGetTickCount();

    for (;;) {
        // Accurate period regardless of serialisation / send duration.
        vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(ESPNOW_SEND_INTERVAL_MS));

        if (!ready_) continue;

        // ── 1. Snapshot and serialise telemetry ────────────────────────────
        // fillJsonSafe() is used for the same reason as in the dashboard task:
        // it returns a fully-populated document even during startup.
        // Stale sensor values are acceptable for a peer monitoring display.
        JsonDocument doc;
        telemetry::fillJsonSafe(doc);

        const size_t jsonLen = serializeJson(doc, jsonBuf, sizeof(jsonBuf));
        if (jsonLen == 0 || jsonLen >= sizeof(jsonBuf)) {
            Serial.println(F("[espnow] JSON serialisation failed — burst skipped"));
            continue;
        }

        // ── 2. Fragment and transmit ───────────────────────────────────────
        const uint8_t totalChunks = static_cast<uint8_t>(
            (jsonLen + CHUNK_PAYLOAD - 1) / CHUNK_PAYLOAD);

        const uint8_t thisMsgId = msgId_++;   // wraps naturally at 255 → 0

        for (uint8_t i = 0; i < totalChunks; ++i) {
            const size_t  offset   = static_cast<size_t>(i) * CHUNK_PAYLOAD;
            const size_t  remain   = jsonLen - offset;
            const uint8_t chunkLen = static_cast<uint8_t>(
                remain < CHUNK_PAYLOAD ? remain : CHUNK_PAYLOAD);

            // Build chunk: [msg_id][total][index][len][...payload...]
            packet[0] = thisMsgId;
            packet[1] = totalChunks;
            packet[2] = i;
            packet[3] = chunkLen;
            memcpy(&packet[4], jsonBuf + offset, chunkLen);

            const esp_err_t err = esp_now_send(
                peerMac_, packet, HEADER_SIZE + chunkLen);

            if (err != ESP_OK) {
                Serial.printf("[espnow] send chunk %u/%u failed (0x%x)\n",
                              static_cast<unsigned>(i + 1),
                              static_cast<unsigned>(totalChunks),
                              static_cast<unsigned>(err));
                ++failCount_;
            }

            // Yield between chunks so the WiFi TX queue can drain.
            if (i + 1 < totalChunks) {
                vTaskDelay(pdMS_TO_TICKS(INTER_CHUNK_DELAY_MS));
            }
        }
    }
}

// ─── Public API ────────────────────────────────────────────────────────────────

module::InitStatus init() {
    // ESP-NOW channel follows the STA association — WiFi must be up first.
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println(F("[espnow] WiFi not connected — skipping ESP-NOW init"));
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }

    if (esp_now_init() != ESP_OK) {
        Serial.println(F("[espnow] esp_now_init() failed"));
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }

    esp_now_register_send_cb(onSent);

    // Register peer.  channel = 0 means "follow current WiFi STA channel".
    esp_now_peer_info_t peer{};
    memcpy(peer.peer_addr, peerMac_, 6);
    peer.channel = 0;
    peer.encrypt = false;
    peer.ifidx   = WIFI_IF_STA;

    if (esp_now_add_peer(&peer) != ESP_OK) {
        Serial.println(F("[espnow] esp_now_add_peer() failed"));
        esp_now_deinit();
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }

    Serial.printf("[espnow] Peer: %02X:%02X:%02X:%02X:%02X:%02X  channel: %d (WiFi STA)\n",
                  peerMac_[0], peerMac_[1], peerMac_[2],
                  peerMac_[3], peerMac_[4], peerMac_[5],
                  WiFi.channel());

    // Pin the task to Core 0 so it runs alongside the WiFi/TCPIP stack and
    // vTaskDelay() yields do not stall the control loop on Core 1.
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
 * Kept so espnow::Module satisfies the ModuleBase interface and call sites
 * in loop() compile without change.
 */
module::ServiceStatus service() {
    return module::MODULE_SERVICE_SKIPPED;
}

uint32_t getSentCount() { return sentCount_; }
uint32_t getFailCount() { return failCount_; }
bool     isReady()      { return ready_; }

} // namespace espnow

#endif // ENABLE_ESPNOW
