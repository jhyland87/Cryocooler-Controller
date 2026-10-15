/**
 * @file dashboard.cpp
 * @brief WiFi, HTTP/OTA server and WebSocket telemetry broadcast for the SPA.
 *
 * Architecture
 * ────────────
 * A dedicated FreeRTOS task (Core 0, taskPriority) owns the periodic
 * WebSocket broadcast.  The Arduino loop task (Core 1) only calls service(),
 * which is a no-op; the dashboard task manages its own 1 Hz schedule via
 * vTaskDelayUntil() so network I/O never stalls other subsystems.
 *
 * WebSocket (HTTP port 80, path /ws, for the web dashboard SPA):
 *   Protobuf binary telemetry frame pushed at 1 Hz.  The schema is defined
 *   in proto/telemetry.proto (shared with the JS decoder).  Encoded using
 *   Nanopb on the ESP32, decoded by protobufjs in the browser.
 *   Connect at:  `ws://<hostname>/ws`
 */

#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include <ESPAsyncWebServer.h>
#include "web_content.h"
#include <ArduinoJson.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <ESPmDNS.h>
#include "dashboard.h"
#include "config.h"
#include "telemetry.h"
#include "telemetry_pb.h"
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

// ─── Constants ───────────────────────────────────────────────────────────────

static constexpr uint32_t   broadcastIntervalMs = 1000;

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

#if DASHBOARD_WEBSOCKET_ENABLED
// Cleanup WebSocket clients every N broadcast ticks (~5 s).
static constexpr uint8_t    wsCleanupEveryN     = 5;
#endif

// ─── Module state ─────────────────────────────────────────────────────────────

static volatile bool    enabled_ = true;
static AsyncWebServer   httpServer(HTTP_API_PORT);
#if DASHBOARD_WEBSOCKET_ENABLED
static AsyncWebSocket   wsServer_("/ws");   // WebSocket endpoint for SPA
#endif
#if DASHBOARD_WEBSOCKET_ENABLED
static uint8_t          pbBuf[pbBufSize];
#endif

// ─── WebSocket event handler ──────────────────────────────────────────────────

#if DASHBOARD_WEBSOCKET_ENABLED
/**
 * Minimal WebSocket event handler.
 *
 * The ESP32 SPA dashboard connects here (ws://hostname/ws) and receives
 * Protobuf telemetry pushes at 1 Hz.  Incoming data from the browser is
 * accepted but ignored — control goes through the USB serial command
 * interface or the HTTP /api/* endpoints.
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

#if DASHBOARD_WEBSOCKET_ENABLED
        // ── WebSocket: broadcast Protobuf binary to all SPA clients ───────
        if (wsServer_.count() > 0) {
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
    MDNS.addService("ws", "tcp", HTTP_API_PORT);

    // Kick off SNTP sync in the background.  time(nullptr) returns 0 until
    // the first sync completes (typically a few seconds after WiFi connects),
    // then switches to the real Unix epoch — no explicit wait needed.
    // "MST7" is the POSIX TZ string for Phoenix / Mountain Standard Time:
    // UTC−7, no daylight-saving transition (Arizona does not observe DST).
    configTzTime("MST7", "pool.ntp.org", "time.nist.gov");
    _Log.println(F("SNTP sync started (MST / Phoenix)"));

    return true;
}

// ─── HTTP server setup ────────────────────────────────────────────────────────

bool setupServer() {
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
