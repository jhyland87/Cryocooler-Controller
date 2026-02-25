/**
 * @file dashboard.cpp
 * @brief Serial Studio async TCP dashboard — integration layer.
 *
 * Architecture
 * ────────────
 * A dedicated FreeRTOS task (Core 0, kTaskPriority) owns all TCP I/O.
 * The Arduino loop task (Core 1) only calls service(), which is a no-op;
 * the dashboard task manages its own 1 Hz schedule via vTaskDelayUntil().
 *
 * Why a separate task?
 * ────────────────────
 * AsyncTCP's add()/send() route through tcpip_api_call(), which is a
 * blocking cross-task IPC call: the calling task suspends until the lwIP
 * TCPIP task has processed the request.  For a ~10 KB frame this can mean
 * many round-trips (one per chunk that fits in tcp_sndbuf, typically 5–6 KB).
 * Doing this on Core 1 (Arduino loop) would stall every other subsystem.
 *
 * Chunked send
 * ────────────
 * tcp_sndbuf() is usually ≤ 5744 bytes by default.  sendChunked() loops
 * with vTaskDelay(5 ms) between chunks so the TCPIP task can drain the
 * window before we push more.  This keeps the dashboard task responsive
 * and never drops the tail of the frame.
 *
 * Serial Studio frame format:
 *   / *{...JSON...}* /\r\n
 */

#include <Arduino.h>
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ArduinoJson.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "dashboard.h"
#include "dashboard_config.h"
#include "config.h"
#include "telemetry.h"
#include "ss_dashboard.h"
#include "commands.h"

namespace dashboard {

// ─── AsyncClientPrint ─────────────────────────────────────────────────────────

/**
 * Print adapter that buffers output and flushes it to an AsyncClient.
 * Allows commands::processLine() to send its text responses back over TCP.
 *
 * Bytes are accumulated in an internal buffer and flushed via add()+send()
 * whenever the buffer fills or the object is destroyed (end of scope).
 * This keeps the number of tcpip_api_call() round-trips minimal.
 *
 * NOTE: Must only be used from the AsyncTCP service task (Core 0), which is
 * the same context as the onClientData callback.
 */
class AsyncClientPrint : public Print {
public:
    explicit AsyncClientPrint(AsyncClient* c) : client_(c), bufLen_(0) {}

    ~AsyncClientPrint() { flush(); }

    size_t write(uint8_t b) override {
        buf_[bufLen_++] = static_cast<char>(b);
        if (bufLen_ >= kBufSize) flush();
        return 1;
    }

    size_t write(const uint8_t* src, size_t size) override {
        for (size_t i = 0; i < size; ++i) write(src[i]);
        return size;
    }

private:
    void flush() {
        if (bufLen_ == 0 || !client_ || !client_->connected()) {
            bufLen_ = 0;
            return;
        }
        client_->add(buf_, bufLen_);
        client_->send();
        bufLen_ = 0;
    }

    static constexpr size_t kBufSize = 128;
    AsyncClient* client_;
    char         buf_[kBufSize];
    size_t       bufLen_;
};

// ─── Constants ───────────────────────────────────────────────────────────────

static constexpr uint32_t   kBroadcastIntervalMs = 1000;
static constexpr size_t     kTxBufSize           = 16384;
static constexpr uint8_t    kMaxClients          = 4;

// FreeRTOS task parameters.
// NOTE: on ESP-IDF the usStackDepth argument to xTaskCreatePinnedToCore is
// in BYTES (unlike vanilla FreeRTOS where it is in words).
static constexpr uint32_t   kTaskStackBytes      = 8192;  // bytes
static constexpr UBaseType_t kTaskPriority       = 1;     // low; yields freely

// Inter-chunk pause — gives lwIP time to ACK and refill the send window.
static constexpr uint32_t   kChunkPauseMs        = 5;

// ─── Module state ─────────────────────────────────────────────────────────────

static volatile bool    enabled_ = true;
static ss::Dashboard    ssDashboard(dashboard_config::kDashboardCfg);
static AsyncServer      tcpServer(WS_PORT);
static char             txBuf[kTxBufSize];

// Client slot array.  Slots are nulled inside disconnect/error callbacks
// (which run in the TCPIP task) before AsyncTCP releases the object.
static AsyncClient* clients_[kMaxClients] = {};

// ─── Client list helpers ──────────────────────────────────────────────────────

static void removeClient(AsyncClient* c) {
    for (auto& slot : clients_) {
        if (slot == c) { slot = nullptr; return; }
    }
}

// ─── AsyncTCP event callbacks ─────────────────────────────────────────────────

static void onClientDisconnect(void* /*arg*/, AsyncClient* c) {
    Serial.printf("[dashboard] Client %s disconnected\n",
                  c->remoteIP().toString().c_str());
    removeClient(c);
}

static void onClientError(void* /*arg*/, AsyncClient* c, int8_t err) {
    Serial.printf("[dashboard] Client %s error %d\n",
                  c->remoteIP().toString().c_str(), err);
    removeClient(c);
}

static void onClientData(void* /*arg*/, AsyncClient* c, void* data, size_t len) {
    // Copy into a null-terminated buffer; data from AsyncTCP is NOT null-terminated.
    static constexpr size_t kMaxCmd = 80;
    char buf[kMaxCmd + 1];
    const size_t copyLen = (len < kMaxCmd) ? len : kMaxCmd;
    memcpy(buf, data, copyLen);
    buf[copyLen] = '\0';

    // Strip trailing CR / LF (Serial Studio sends "stop\n").
    size_t end = copyLen;
    while (end > 0 && (buf[end - 1] == '\r' || buf[end - 1] == '\n')) { --end; }
    buf[end] = '\0';

    if (end == 0) return;

    Serial.printf("[dashboard] Client %s cmd: %s\n",
                  c->remoteIP().toString().c_str(), buf);

    // Dispatch — response is sent back over the same TCP connection.
    // NOTE: processLine() runs here in the AsyncTCP service task (Core 0).
    // It modifies state that the Arduino loop (Core 1) also reads.  For this
    // application the race window is negligible; add a mutex if stricter
    // guarantees are needed.
    AsyncClientPrint printer(c);
    commands::processLine(buf, printer);
}

static void onNewClient(void* /*arg*/, AsyncClient* c) {
    for (auto& slot : clients_) {
        if (!slot) {
            slot = c;
            c->onDisconnect(&onClientDisconnect, nullptr);
            c->onError(&onClientError, nullptr);
            c->onData(&onClientData, nullptr);
            Serial.printf("[dashboard] Client %s connected\n",
                          c->remoteIP().toString().c_str());
            return;
        }
    }
    Serial.println("[dashboard] Max clients reached, rejecting connection");
    c->close();
}

// ─── Chunked TCP send ─────────────────────────────────────────────────────────

/**
 * Send @p len bytes from @p data to @p c, blocking the calling FreeRTOS task
 * (not the main loop) until all bytes are queued or the client disconnects.
 *
 * add() + send() are used in a loop so that frames larger than tcp_sndbuf()
 * (~5744 B default) are delivered in full rather than silently truncated.
 */
static void sendChunked(AsyncClient* c, const char* data, size_t len) {
    size_t offset = 0;
    while (offset < len) {
        if (!c || !c->connected()) return;

        if (!c->canSend()) {
            vTaskDelay(pdMS_TO_TICKS(kChunkPauseMs));
            continue;
        }

        const size_t written = c->add(data + offset, len - offset);
        if (written == 0) {
            // add() returned 0 — buffer might be momentarily full.
            vTaskDelay(pdMS_TO_TICKS(kChunkPauseMs));
            continue;
        }

        c->send();          // flush queued bytes to the wire
        offset += written;

        if (offset < len) {
            // Yield so the TCPIP task can drain the TCP window before next chunk.
            vTaskDelay(pdMS_TO_TICKS(kChunkPauseMs));
        }
    }
}

// ─── Dashboard FreeRTOS task ──────────────────────────────────────────────────

static void dashboardTask(void* /*arg*/) {
    TickType_t lastWakeTime = xTaskGetTickCount();

    for (;;) {
        // Accurate 1 Hz period regardless of send duration.
        vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(kBroadcastIntervalMs));

        if (!enabled_) continue;

        // Check for any connected client before doing expensive work.
        bool anyConnected = false;
        for (const auto* c : clients_) {
            if (c && c->connected()) { anyConnected = true; break; }
        }
        if (!anyConnected) continue;

        // Snapshot telemetry from Core 1.  Stale values are acceptable for
        // a monitoring display; a full mutex would add latency for no gain.
        JsonDocument telemetry;
        telemetry::fillJson(telemetry);
        ssDashboard.update(telemetry);

        const size_t len = ssDashboard.serialize(txBuf, kTxBufSize);
        if (len == 0) {
            Serial.println("[dashboard] serialize() returned 0 — frame dropped");
            continue;
        }

        for (auto* c : clients_) {
            if (!c || !c->connected()) continue;
            sendChunked(c, txBuf, len);
        }
    }
}

// ─── Public API ───────────────────────────────────────────────────────────────

void enable()    { enabled_ = true; }
void disable()   { enabled_ = false; }
bool isEnabled() { return enabled_; }

/**
 * No-op: the dashboard task manages its own schedule.
 * Kept so call sites in loop() compile without changes.
 */
void service() {}

// ─── init() ──────────────────────────────────────────────────────────────────

void init() {
    setupWifi();
    ssDashboard.begin();
    setupServer();

    // Pin the dashboard task to Core 0 (the WiFi/TCPIP core) so that
    // tcpip_api_call() round-trips never block the Arduino loop on Core 1.
    xTaskCreatePinnedToCore(
        dashboardTask,
        "dashboard",
        kTaskStackBytes,
        nullptr,
        kTaskPriority,
        nullptr,
        0  // Core 0
    );
}

// ─── WiFi setup ──────────────────────────────────────────────────────────────

void setupWifi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("[dashboard] Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();
    Serial.printf("[dashboard] Connected — IP: %s\n",
                  WiFi.localIP().toString().c_str());
}

// ─── TCP server setup ─────────────────────────────────────────────────────────

void setupServer() {
    tcpServer.onClient(&onNewClient, nullptr);
    tcpServer.begin();
    Serial.printf("[dashboard] TCP server listening on port %u\n",
                  static_cast<unsigned>(WS_PORT));
}

} // namespace dashboard
