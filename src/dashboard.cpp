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
#include <time.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include "web_content.h"
#include <ArduinoJson.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <ESPmDNS.h>
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
// Transmit buffer.  Must be larger than the compact serialised dashboard JSON
// (use estimateSize() to measure).  Pretty mode is NOT used for live streaming
// because pretty output is ~3–4× larger; 16 KB comfortably holds the compact
// frame (~10–11 KB for a typical cryocooler config).
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
static AsyncWebServer   httpServer(HTTP_API_PORT);
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
    Serial.printf(F("[dashboard] Client %s disconnected\n"),
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

    Serial.printf(F("[dashboard] Client %s cmd: %s\n"),
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
            Serial.printf(F("[dashboard] Client %s connected\n"),
                          c->remoteIP().toString().c_str());
            return;
        }
    }
    Serial.println(F("[dashboard] Max clients reached, rejecting connection"));
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
        for (auto* c : clients_) {
            if (c && c->connected()) { anyConnected = true; break; }
        }
        if (!anyConnected) continue;

        // Snapshot telemetry from Core 1.  Stale values are acceptable for
        // a monitoring display; a full mutex would add latency for no gain.
        // fillJsonSafe() is used so the dashboard is populated immediately on
        // connect, even while other modules are still initialising: fields from
        // unready modules are emitted as empty strings rather than blocking the
        // whole frame.
        JsonDocument telemetry;
        telemetry::fillJsonSafe(telemetry);
        ssDashboard.update(telemetry);

        const size_t len = ssDashboard.serialize(txBuf, kTxBufSize);
        if (len == 0) {
            Serial.println(F("[dashboard] serialize() returned 0 — frame dropped"));
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
module::ServiceStatus service() { return module::MODULE_SERVICE_SKIPPED; }

// ─── init() ──────────────────────────────────────────────────────────────────

module::InitStatus init() {
    if (!setupWifi()) {
        return module::MODULE_INIT_CONFIG_ERROR;
    }

    if (!ssDashboard.begin()) {
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }

    if (!setupServer()) {
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }
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
    return module::MODULE_INIT_SUCCESS;
}

// ─── WiFi setup ──────────────────────────────────────────────────────────────

bool setupWifi() {
    // Tear down any stale auth state from a previous session.
    // Without this the ESP32 can present an expired auth context to the AP,
    // which responds with deauth reason 2 (AUTH_EXPIRE) every ~1 s until
    // waitForConnectResult() times out.
    //WiFi.disconnectAsync(true, true);
    WiFi.setAutoReconnect(false);
    WiFi.mode(WIFI_OFF);
    delay(100);  // let the WiFi stack fully idle before re-arming

    WiFi.setHostname(HOSTNAME);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    if (WiFi.waitForConnectResult(10000) != WL_CONNECTED) {
        Serial.println(F("[dashboard] Failed to connect to WiFi"));

        return false;
    }

    Serial.printf("[dashboard] Connected — IP: %s\n", WiFi.localIP().toString().c_str());

    if (!MDNS.begin(HOSTNAME)) { // Set hostname
        Serial.println(F("[dashboard] Error setting up MDNS responder!"));
    } else {
        Serial.printf("[dashboard] mDNS responder started: %s.local\n", HOSTNAME);
    }

    MDNS.addService("http", "tcp", HTTP_API_PORT);
    MDNS.addService("ws", "tcp", WS_PORT);

    // Kick off SNTP sync in the background.  time(nullptr) returns 0 until
    // the first sync completes (typically a few seconds after WiFi connects),
    // then switches to the real Unix epoch — no explicit wait needed.
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
    Serial.println(F("[dashboard] SNTP sync started (UTC)"));

    return true;
}

// ─── TCP server setup ─────────────────────────────────────────────────────────

bool setupServer() {
    tcpServer.onClient(&onNewClient, nullptr);
    tcpServer.begin();
    Serial.printf("[dashboard] TCP server listening on port %u\n",
                  static_cast<unsigned>(WS_PORT));

    // Static files embedded at compile time by scripts/embed_web.py.
    // No LittleFS partition needed — files are served directly from flash.
    httpServer.on("/", HTTP_GET, [](AsyncWebServerRequest* r) {
        r->send(200, "text/html", k_index_html);
    });
    httpServer.on("/index.html", HTTP_GET, [](AsyncWebServerRequest* r) {
        r->send(200, "text/html", k_index_html);
    });
    httpServer.on("/style.css", HTTP_GET, [](AsyncWebServerRequest* r) {
        r->send(200, "text/css", k_style_css);
    });
    httpServer.on("/app.js", HTTP_GET, [](AsyncWebServerRequest* r) {
        r->send(200, "application/javascript", k_app_js);
    });

    // GET /api/telemetry — latest telemetry snapshot as flat JSON.
    // The buffer is static: ESPAsyncWebServer callbacks run serialised in the
    // lwIP TCPIP task, so there is no concurrent access risk for a single route.
    // fillJsonSafe() is used so the endpoint returns a fully-structured response
    // even during startup, with empty strings for modules not yet initialised.
    httpServer.on("/api/telemetry", HTTP_GET, [](AsyncWebServerRequest* request) {
        static char jsonBuf[8192];
        JsonDocument doc;
        telemetry::fillJsonSafe(doc);
        const size_t len = serializeJson(doc, jsonBuf, sizeof(jsonBuf));
        if (len == 0 || len >= sizeof(jsonBuf)) {
            request->send(500, "application/json", "{\"error\":\"serialization failed\"}");
            return;
        }
        request->send(200, "application/json", jsonBuf);
    });

    httpServer.begin();

    Serial.printf("[dashboard] HTTP server listening on port %u\n",
                  static_cast<unsigned>(HTTP_API_PORT));
    return true;
}

} // namespace dashboard
