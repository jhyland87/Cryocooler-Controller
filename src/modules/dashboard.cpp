/**
 * @file dashboard.cpp
 * @brief Serial Studio async TCP dashboard — integration layer.
 *
 * Architecture
 * ────────────
 * A dedicated FreeRTOS task (Core 0, taskPriority) owns all TCP I/O.
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
 * Serial Studio frame format (TCP port 8080, for Serial Studio):
 *   / *{...JSON...}* /\r\n
 *
 * WebSocket (HTTP port 80, path /ws, for the web dashboard SPA):
 *   Protobuf binary telemetry frame pushed at 1 Hz.  The schema is defined
 *   in proto/telemetry.proto (shared with the JS decoder).  Encoded using
 *   Nanopb on the ESP32, decoded by protobufjs in the browser.
 *   Connect at:  ws://<hostname>/ws
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
#include "telemetry_pb.h"
#include "ss_dashboard.h"
#include "commands.h"
#include "ota.h"
#include "logger.h"
#include "state_machine.h"

static LogStream _Log = Log.createChildLogger("dashboard");
// AsyncWebSocket is included via ESPAsyncWebServer.h

// ─── WebSocket toggle ─────────────────────────────────────────────────────────
// Set to 1 to enable the /ws WebSocket endpoint used by the Preact SPA.
// Set to 0 to disable it entirely (no handler registered, no broadcast, no
// Serial.printf calls from the TCPIP task) — useful for isolating whether
// the WebSocket is interfering with serial input.
#define DASHBOARD_WEBSOCKET_ENABLED 1

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
        if (bufLen_ >= bufSize) flush();
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

    static constexpr size_t bufSize = 128;
    AsyncClient* client_;
    char         buf_[bufSize];
    size_t       bufLen_;
};

// ─── Constants ───────────────────────────────────────────────────────────────

static constexpr uint32_t   broadcastIntervalMs = 1000;
// Transmit buffer for Serial Studio TCP frames.  Must be larger than the
// compact serialised dashboard JSON (use estimateSize() to measure).
// Budget: ~50 datasets × ~350 B each ≈ 17.5 KB; add group wrappers → ~24 KB.
// 32 KB gives comfortable headroom for future config growth.
static constexpr size_t     txBufSize           = 32768;
static constexpr uint8_t    maxClients          = 4;

#if DASHBOARD_WEBSOCKET_ENABLED
// Protobuf binary buffer for WebSocket frames.  The Protobuf-encoded
// telemetry payload is typically ~600-700 bytes; 2 KB gives comfortable
// headroom for future field growth.
static constexpr size_t     pbBufSize           = 2048;
#endif

// FreeRTOS task parameters.
// NOTE: on ESP-IDF the usStackDepth argument to xTaskCreatePinnedToCore is
// in BYTES (unlike vanilla FreeRTOS where it is in words).
// wsBuf and jsonBuf are static (BSS), not stack-allocated, so they don't
// affect this value.  12288 gives comfortable headroom for local variables.
static constexpr uint32_t   taskStackBytes      = 12288; // bytes
static constexpr UBaseType_t taskPriority       = 1;     // low; yields freely

// Inter-chunk pause — gives lwIP time to ACK and refill the send window.
static constexpr uint32_t   chunkPauseMs        = 5;

#if DASHBOARD_WEBSOCKET_ENABLED
// Cleanup WebSocket clients every N broadcast ticks (~5 s).
static constexpr uint8_t    wsCleanupEveryN     = 5;
#endif

// ─── Module state ─────────────────────────────────────────────────────────────

static volatile bool    enabled_ = true;
static ss::Dashboard    ssDashboard(dashboard_config::dashboardCfg);
static AsyncServer      tcpServer(WS_PORT);
static AsyncWebServer   httpServer(HTTP_API_PORT);
#if DASHBOARD_WEBSOCKET_ENABLED
static AsyncWebSocket   wsServer_("/ws");   // WebSocket endpoint for SPA
#endif
static char             txBuf[txBufSize];
#if DASHBOARD_WEBSOCKET_ENABLED
static uint8_t          pbBuf[pbBufSize];
#endif

// Client slot array.  Slots are nulled inside disconnect/error callbacks
// (which run in the TCPIP task) before AsyncTCP releases the object.
static AsyncClient* clients_[maxClients] = {};

// ─── Client list helpers ──────────────────────────────────────────────────────

static void removeClient(AsyncClient* c) {
    for (auto& slot : clients_) {
        if (slot == c) { slot = nullptr; return; }
    }
}

// ─── AsyncTCP event callbacks ─────────────────────────────────────────────────

static void onClientDisconnect(void* /*arg*/, AsyncClient* c) {
    _Log.printf("Client %s disconnected\n",
                  c->remoteIP().toString().c_str());
    removeClient(c);
}

static void onClientError(void* /*arg*/, AsyncClient* c, int8_t err) {
    _Log.printf("Client %s error %d\n",
                  c->remoteIP().toString().c_str(), err);
    removeClient(c);
}

static void onClientData(void* /*arg*/, AsyncClient* c, void* data, size_t len) {
    // Copy into a null-terminated buffer; data from AsyncTCP is NOT null-terminated.
    static constexpr size_t maxCmd = 80;
    char buf[maxCmd + 1];
    const size_t copyLen = (len < maxCmd) ? len : maxCmd;
    memcpy(buf, data, copyLen);
    buf[copyLen] = '\0';

    // Strip trailing CR / LF (Serial Studio sends "stop\n").
    size_t end = copyLen;
    while (end > 0 && (buf[end - 1] == '\r' || buf[end - 1] == '\n')) { --end; }
    buf[end] = '\0';

    if (end == 0) return;

    _Log.printf("Client %s cmd: %s\n",
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
            _Log.printf("Client %s connected\n",
                          c->remoteIP().toString().c_str());
            return;
        }
    }
    _Log.println(F("Max clients reached, rejecting connection"));
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
            vTaskDelay(pdMS_TO_TICKS(chunkPauseMs));
            continue;
        }

        const size_t written = c->add(data + offset, len - offset);
        if (written == 0) {
            // add() returned 0 — buffer might be momentarily full.
            vTaskDelay(pdMS_TO_TICKS(chunkPauseMs));
            continue;
        }

        c->send();          // flush queued bytes to the wire
        offset += written;

        if (offset < len) {
            // Yield so the TCPIP task can drain the TCP window before next chunk.
            vTaskDelay(pdMS_TO_TICKS(chunkPauseMs));
        }
    }
}

// ─── WebSocket event handler ──────────────────────────────────────────────────

#if DASHBOARD_WEBSOCKET_ENABLED
/**
 * Minimal WebSocket event handler.
 *
 * The ESP32 SPA dashboard connects here (ws://hostname/ws) and receives flat
 * JSON telemetry pushes at 1 Hz.  Incoming data from the browser is accepted
 * but ignored — all control goes through the TCP command interface on port
 * WS_PORT (Serial Studio) or via the HTTP /api/* endpoints.
 */
static void onWsEvent(AsyncWebSocket* /*srv*/, AsyncWebSocketClient* client,
                      AwsEventType type, void* /*arg*/, uint8_t* /*data*/, size_t /*len*/) {
    switch (type) {
        case WS_EVT_CONNECT:
            _Log.printf("WS client %u connected from %s\n",
                          client->id(), client->remoteIP().toString().c_str());
            break;
        case WS_EVT_DISCONNECT:
            _Log.printf("WS client %u disconnected\n", client->id());
            break;
        case WS_EVT_ERROR:
            _Log.printf("WS client %u error\n", client->id());
            break;
        default:
            break;
    }
}
#endif // DASHBOARD_WEBSOCKET_ENABLED

// ─── Fault history JSON helper ────────────────────────────────────────────────

/**
 * Populate @p doc with the fault_history JSON payload.
 * Uses the public API from state_machine.h — no internal access needed.
 */
static void fillFaultHistoryJson(JsonDocument& doc) {
    doc["type"]    = "fault_history";
    doc["version"] = state_machine::getFaultHistoryVersion();

    JsonArray records = doc["records"].to<JsonArray>();
    const uint8_t count = state_machine::getFaultHistoryCount();
    char reasonBuf[128];

    for (uint8_t i = 0; i < count; ++i) {
        const state_machine::FaultRecord rec = state_machine::getFaultRecord(i);
        JsonObject obj = records.add<JsonObject>();

        state_machine::formatFaultReasons(rec.reason, reasonBuf, sizeof(reasonBuf));
        obj["reason"]        = String(reasonBuf);
        obj["reason_mask"]   = static_cast<uint8_t>(rec.reason);
        obj["entered_epoch"] = static_cast<long long>(rec.enteredEpoch);
        obj["entered_ms"]    = rec.enteredMs;
        obj["cleared_epoch"] = static_cast<long long>(rec.clearedEpoch);
        obj["cleared_ms"]    = rec.clearedMs;
        obj["cleared_by"]    = rec.clearedBy ? rec.clearedBy : "";
        obj["active"]        = (rec.clearedBy == nullptr);
    }
}

// ─── Dashboard FreeRTOS task ──────────────────────────────────────────────────

static void dashboardTask(void* /*arg*/) {
    TickType_t lastWakeTime  = xTaskGetTickCount();
#if DASHBOARD_WEBSOCKET_ENABLED
    uint8_t    cleanupTick   = 0;
    uint32_t   lastFaultVersion_ = state_machine::getFaultHistoryVersion();
#endif

    for (;;) {
        // Accurate 1 Hz period regardless of send duration.
        vTaskDelayUntil(&lastWakeTime, pdMS_TO_TICKS(broadcastIntervalMs));

        if (!enabled_) continue;

#if DASHBOARD_WEBSOCKET_ENABLED
        // Periodically prune stale AsyncWebSocket clients so the internal
        // slot table does not fill with zombie entries.
        if (++cleanupTick >= wsCleanupEveryN) {
            wsServer_.cleanupClients();
            cleanupTick = 0;
        }
#endif

        // Determine whether any consumers are connected before doing work.
        bool anyTcpClient = false;
        for (auto* c : clients_) {
            if (c && c->connected()) { anyTcpClient = true; break; }
        }
#if DASHBOARD_WEBSOCKET_ENABLED
        const bool anyWsClient = (wsServer_.count() > 0);
        if (!anyTcpClient && !anyWsClient) continue;
#else
        if (!anyTcpClient) continue;
#endif

#if DASHBOARD_WEBSOCKET_ENABLED
        // ── WebSocket: broadcast Protobuf binary to all SPA clients ───────
        if (anyWsClient) {
            const size_t pbLen = telemetry::encodeProtobuf(pbBuf, pbBufSize);
            if (pbLen > 0) {
                wsServer_.binaryAll(pbBuf, pbLen);
            }

            // ── Fault history: push JSON text frame on change ─────────────
            const uint32_t curFaultVersion = state_machine::getFaultHistoryVersion();
            if (curFaultVersion != lastFaultVersion_) {
                lastFaultVersion_ = curFaultVersion;
                JsonDocument faultDoc;
                fillFaultHistoryJson(faultDoc);
                static char faultJsonBuf[2048];
                const size_t fLen = serializeJson(faultDoc, faultJsonBuf, sizeof(faultJsonBuf));
                if (fLen > 0 && fLen < sizeof(faultJsonBuf)) {
                    wsServer_.textAll(faultJsonBuf, fLen);
                }
            }
        }
#endif // DASHBOARD_WEBSOCKET_ENABLED

        // ── TCP: broadcast Serial Studio frame to Serial Studio clients ───
        if (anyTcpClient) {
            // Build JSON only when TCP clients are connected (Serial Studio).
            JsonDocument telDoc;
            telemetry::fillJsonSafe(telDoc, /*includeLogs=*/false);
            ssDashboard.update(telDoc);
            const size_t len = ssDashboard.serialize(txBuf, txBufSize);
            if (len == 0) {
                _Log.println(F("serialize() returned 0 — frame dropped"));
            } else {
                for (auto* c : clients_) {
                    if (!c || !c->connected()) continue;
                    sendChunked(c, txBuf, len);
                }
            }
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
        taskStackBytes,
        nullptr,
        taskPriority,
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
        _Log.println(F("Failed to connect to WiFi"));

        return false;
    }

    _Log.printf("Connected — IP: %s\n", WiFi.localIP().toString().c_str());

    if (!MDNS.begin(HOSTNAME)) { // Set hostname
        _Log.println(F("Error setting up MDNS responder!"));
    } else {
        _Log.printf("mDNS responder started: %s.local\n", HOSTNAME);
    }

    MDNS.addService("http", "tcp", HTTP_API_PORT);
    MDNS.addService("ws", "tcp", WS_PORT);

    // Kick off SNTP sync in the background.  time(nullptr) returns 0 until
    // the first sync completes (typically a few seconds after WiFi connects),
    // then switches to the real Unix epoch — no explicit wait needed.
    // "MST7" is the POSIX TZ string for Phoenix / Mountain Standard Time:
    // UTC−7, no daylight-saving transition (Arizona does not observe DST).
    configTzTime("MST7", "pool.ntp.org", "time.nist.gov");
    _Log.println(F("SNTP sync started (MST / Phoenix)"));

    return true;
}

// ─── TCP server setup ─────────────────────────────────────────────────────────

bool setupServer() {
    tcpServer.onClient(&onNewClient, nullptr);
    tcpServer.begin();
    _Log.printf("TCP server listening on port %u\n",
                  static_cast<unsigned>(WS_PORT));

    // Static files embedded at compile time by scripts/embed_web.py.
    // No LittleFS partition needed — files are served directly from flash.
    httpServer.on("/", HTTP_GET, [](AsyncWebServerRequest* r) {
        r->send(200, "text/html", index_html);
    });
    httpServer.on("/index.html", HTTP_GET, [](AsyncWebServerRequest* r) {
        r->send(200, "text/html", index_html);
    });
    httpServer.on("/style.css", HTTP_GET, [](AsyncWebServerRequest* r) {
        r->send(200, "text/css", style_css);
    });
    httpServer.on("/app.js", HTTP_GET, [](AsyncWebServerRequest* r) {
        AsyncWebServerResponse* resp = r->beginResponse(
            200, "application/javascript", app_js_gz, app_js_gz_len);
        resp->addHeader("Content-Encoding", "gzip");
        resp->addHeader("Cache-Control", "no-cache");
        r->send(resp);
    });

    // GET /api/telemetry — latest telemetry snapshot as flat JSON.
    // The buffer is static: ESPAsyncWebServer callbacks run serialised in the
    // lwIP TCPIP task, so there is no concurrent access risk for a single route.
    // fillJsonSafe() is used so the endpoint returns a fully-structured response
    // even during startup, with empty strings for modules not yet initialised.
    httpServer.on("/api/telemetry", HTTP_GET, [](AsyncWebServerRequest* request) {
        static char jsonBuf[32768];
        JsonDocument doc;
        telemetry::fillJsonSafe(doc);
        const size_t len = serializeJson(doc, jsonBuf, sizeof(jsonBuf));
        if (len == 0 || len >= sizeof(jsonBuf)) {
            request->send(500, "application/json", "{\"error\":\"serialization failed\"}");
            return;
        }
        request->send(200, "application/json", jsonBuf);
    });

    // GET /api/fault-history — full fault history snapshot as JSON.
    httpServer.on("/api/fault-history", HTTP_GET, [](AsyncWebServerRequest* request) {
        static char faultBuf[2048];
        JsonDocument doc;
        fillFaultHistoryJson(doc);
        const size_t len = serializeJson(doc, faultBuf, sizeof(faultBuf));
        if (len == 0 || len >= sizeof(faultBuf)) {
            request->send(500, "application/json", "{\"error\":\"serialization failed\"}");
            return;
        }
        request->send(200, "application/json", faultBuf);
    });

    // OTA firmware-update endpoint (GET /ota — upload form, POST /ota — flash).
    // Registered here so it shares the same AsyncWebServer instance and port.
    ota::registerRoutes(httpServer);

#if DASHBOARD_WEBSOCKET_ENABLED
    // WebSocket endpoint for the Preact SPA dashboard.
    // Browsers connect to ws://<hostname>/ws and receive 1 Hz flat JSON pushes.
    wsServer_.onEvent(onWsEvent);
    httpServer.addHandler(&wsServer_);
#endif

    httpServer.begin();

    _Log.printf("HTTP server listening on port %u\n",
                  static_cast<unsigned>(HTTP_API_PORT));
    return true;
}

} // namespace dashboard
