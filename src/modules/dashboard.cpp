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

// A failed authentication leaves WiFi.status() unchanged, so attempts need their own timeout.
static constexpr uint32_t   wifiAttemptTimeoutMs = 8000;
static constexpr uint32_t   wifiRetryMinDelayMs  = 5000;
static constexpr uint32_t   wifiRetryMaxDelayMs  = 60000;
static constexpr uint32_t   wifiScanDwellMs      = 100;  // per channel; about 1.3 s for a full scan

// ─── Module state ─────────────────────────────────────────────────────────────

static bool             runtimeStarted_ = false;  // HTTP server and task are running

// Written by other tasks; consumed by serviceWifiLink().
static volatile uint8_t wifiDisconnectReason_ = 0;
static volatile bool    wifiRetryRequested_   = false;
static volatile int8_t  wifiPendingTxPower_   = 0;  // wifi_power_t value; 0 = none pending

// Owned by whichever task runs the connection: init(), then the dashboard task.
static bool             wifiLinkUp_          = false;
static bool             wifiAttemptActive_   = false;
static bool             networkServicesUp_   = false;
static uint32_t         wifiAttemptCount_    = 0;
static uint32_t         wifiAttemptStartMs_  = 0;
static uint32_t         wifiNextAttemptMs_   = 0;
static uint32_t         wifiRetryDelayMs_    = wifiRetryMinDelayMs;

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
            // On a slow link, drop frames for this client instead of closing
            // it when its queue fills (the SPA would just reconnect and refill).
            client->setCloseClientOnQueueFull(false);
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

// ─── WiFi link management ─────────────────────────────────────────────────────

static const char* wifiReasonName(uint8_t reason) {
    switch (reason) {
        case 0:                                 return "none yet";
        case WIFI_REASON_AUTH_EXPIRE:           return "AUTH_EXPIRE";
        case WIFI_REASON_ASSOC_TOOMANY:         return "ASSOC_TOOMANY";
        case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT: return "4WAY_HANDSHAKE_TIMEOUT";
        case WIFI_REASON_BEACON_TIMEOUT:        return "BEACON_TIMEOUT";
        case WIFI_REASON_NO_AP_FOUND:           return "NO_AP_FOUND";
        case WIFI_REASON_AUTH_FAIL:             return "AUTH_FAIL";
        case WIFI_REASON_ASSOC_FAIL:            return "ASSOC_FAIL";
        case WIFI_REASON_HANDSHAKE_TIMEOUT:     return "HANDSHAKE_TIMEOUT";
        case WIFI_REASON_CONNECTION_FAIL:       return "CONNECTION_FAIL";
        default:                                return "other";
    }
}

static const char* wifiSecurityName(wifi_auth_mode_t mode) {
    switch (mode) {
        case WIFI_AUTH_OPEN:            return "open";
        case WIFI_AUTH_WEP:             return "WEP";
        case WIFI_AUTH_WPA_PSK:         return "WPA";
        case WIFI_AUTH_WPA2_PSK:        return "WPA2";
        case WIFI_AUTH_WPA_WPA2_PSK:    return "WPA/WPA2";
        case WIFI_AUTH_WPA2_ENTERPRISE: return "WPA2-Enterprise";
        case WIFI_AUTH_WPA3_PSK:        return "WPA3";
        case WIFI_AUTH_WPA2_WPA3_PSK:   return "WPA2/WPA3";
        default:                        return "other";
    }
}

/** Log every access point advertising the configured network. The name itself stays out of the log. */
static void logWifiScan() {
    const int16_t foundCount = WiFi.scanNetworks(false, false, false, wifiScanDwellMs, 0, WIFI_SSID);
    if (foundCount < 0) {
        _Log.printf("WiFi scan failed (%d)\n", foundCount);
        return;
    }
    if (foundCount == 0) {
        _Log.println(F("WiFi scan: configured network not visible"));
    }
    for (int16_t index = 0; index < foundCount; ++index) {
        _Log.printf("  AP %s  RSSI %d dBm  channel %d  security %s\n",
                    WiFi.BSSIDstr(index).c_str(), WiFi.RSSI(index), WiFi.channel(index),
                    wifiSecurityName(WiFi.encryptionType(index)));
    }
    WiFi.scanDelete();
}

static void beginWifiAttempt() {
    if (wifiAttemptCount_ > 0) {
        WiFi.disconnect();
        delay(100);
    }
    ++wifiAttemptCount_;
    _Log.printf("WiFi attempt %u  MAC %s  TX power %.1f dBm\n",
                static_cast<unsigned>(wifiAttemptCount_), WiFi.macAddress().c_str(),
                static_cast<float>(WiFi.getTxPower()) / 4.0f);
    logWifiScan();

    wifiDisconnectReason_ = 0;
    wifiAttemptStartMs_   = millis();
    wifiAttemptActive_    = true;
    WiFi.begin(WIFI_SSID, WIFI_PASS);
}

/** Start mDNS and SNTP. Both survive a reconnect, so this runs only once. */
static void startNetworkServices() {
    if (networkServicesUp_) {
        return;
    }
    networkServicesUp_ = true;

    if (!MDNS.begin(HOSTNAME)) {
        _Log.println(F("Error setting up MDNS responder!"));
    } else {
        _Log.printf("mDNS responder started: %s.local\n", HOSTNAME);
    }

    MDNS.addService("http", "tcp", HTTP_API_PORT);
    MDNS.addService("ws", "tcp", HTTP_API_PORT);

    // time(nullptr) returns 0 until the first sync completes, then the Unix epoch.
    // "MST7" is Phoenix: UTC−7, no daylight saving.
    configTzTime("MST7", "pool.ntp.org", "time.nist.gov");
    _Log.println(F("SNTP sync started (MST / Phoenix)"));
}

void serviceWifiLink() {
    const int8_t pendingPower = wifiPendingTxPower_;
    if (pendingPower != 0) {
        wifiPendingTxPower_ = 0;
        const bool applied = WiFi.setTxPower(static_cast<wifi_power_t>(pendingPower));
        _Log.printf("WiFi TX power %s: %.1f dBm\n", applied ? "set" : "NOT set",
                    static_cast<float>(WiFi.getTxPower()) / 4.0f);
    }

    if (WiFi.status() == WL_CONNECTED) {
        wifiAttemptActive_ = false;
        if (wifiLinkUp_) {
            return;
        }
        wifiLinkUp_       = true;
        wifiRetryDelayMs_ = wifiRetryMinDelayMs;
        _Log.printf("Connected — IP: %s  RSSI %d dBm  channel %d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI(), WiFi.channel());
        startNetworkServices();
        Module::overrideInitStatus(module::MODULE_INIT_SUCCESS);
        return;
    }

    const uint32_t nowMs = millis();

    if (wifiLinkUp_) {
        wifiLinkUp_        = false;
        wifiAttemptActive_ = false;
        wifiNextAttemptMs_ = nowMs;
        _Log.printf("WiFi connection lost (reason %u, %s)\n",
                    wifiDisconnectReason_, wifiReasonName(wifiDisconnectReason_));
    }

    if (wifiAttemptActive_) {
        if (nowMs - wifiAttemptStartMs_ < wifiAttemptTimeoutMs && !wifiRetryRequested_) {
            return;
        }
        wifiAttemptActive_ = false;
        wifiNextAttemptMs_ = nowMs + wifiRetryDelayMs_;
        _Log.printf("WiFi attempt %u failed (reason %u, %s); next try in %u s\n",
                    static_cast<unsigned>(wifiAttemptCount_), wifiDisconnectReason_,
                    wifiReasonName(wifiDisconnectReason_),
                    static_cast<unsigned>(wifiRetryDelayMs_ / 1000));
        wifiRetryDelayMs_ = min(wifiRetryDelayMs_ * 2, wifiRetryMaxDelayMs);
    }

    if (wifiRetryRequested_) {
        wifiRetryRequested_ = false;
        wifiRetryDelayMs_   = wifiRetryMinDelayMs;
    } else if (static_cast<int32_t>(nowMs - wifiNextAttemptMs_) < 0) {
        return;
    }
    beginWifiAttempt();
}

void requestWifiRetry() {
    wifiRetryRequested_ = true;
}

bool setWifiTxPower(float powerDbm) {
    struct TxPowerLevel {
        float dbm;
        wifi_power_t level;
    };
    static constexpr TxPowerLevel levels[] = {
        {19.5f, WIFI_POWER_19_5dBm}, {19.0f, WIFI_POWER_19dBm}, {18.5f, WIFI_POWER_18_5dBm},
        {17.0f, WIFI_POWER_17dBm},   {15.0f, WIFI_POWER_15dBm}, {13.0f, WIFI_POWER_13dBm},
        {11.0f, WIFI_POWER_11dBm},   {8.5f, WIFI_POWER_8_5dBm}, {7.0f, WIFI_POWER_7dBm},
        {5.0f, WIFI_POWER_5dBm},     {2.0f, WIFI_POWER_2dBm},   {-1.0f, WIFI_POWER_MINUS_1dBm},
    };
    for (const TxPowerLevel& candidate : levels) {
        if (candidate.dbm != powerDbm) {
            continue;
        }
        wifiPendingTxPower_ = static_cast<int8_t>(candidate.level);
        // Retest straight away unless the link is already up.
        wifiRetryRequested_ = (WiFi.status() != WL_CONNECTED);
        return true;
    }
    return false;
}

void printWifiStatus(Print& out) {
    char line[96];
    const bool connected = (WiFi.status() == WL_CONNECTED);
    out.println(connected ? F("WiFi: connected") : F("WiFi: not connected"));
    if (connected) {
        snprintf(line, sizeof(line), "  IP %s  RSSI %d dBm  channel %d",
                 WiFi.localIP().toString().c_str(), WiFi.RSSI(), WiFi.channel());
        out.println(line);
    }
    snprintf(line, sizeof(line), "  MAC %s  TX power %.1f dBm",
             WiFi.macAddress().c_str(), static_cast<float>(WiFi.getTxPower()) / 4.0f);
    out.println(line);
    snprintf(line, sizeof(line), "  Attempts %u  last disconnect reason %u (%s)",
             static_cast<unsigned>(wifiAttemptCount_), wifiDisconnectReason_,
             wifiReasonName(wifiDisconnectReason_));
    out.println(line);
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

        // Runs even with broadcasts disabled, and may block here for a scan.
        serviceWifiLink();

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
        // Skip the tick while any client's queue is full: each frame is a
        // full snapshot, so the next one replaces it, and a pending fault
        // history push waits for the next tick instead of being dropped.
        if (wsServer_.count() > 0 && wsServer_.availableForWriteAll()) {
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
    // A repeat init (`reinit dashboard`) hands off to the task: it doesn't block
    // loop(), and the routes and task can't be registered twice.
    if (runtimeStarted_) {
        if (WiFi.status() == WL_CONNECTED) {
            return module::MODULE_INIT_SUCCESS;
        }
        requestWifiRetry();
        _Log.println(F("WiFi not connected; retrying in the background"));
        return module::MODULE_INIT_CONFIG_ERROR;
    }

    const bool wifiConnected = setupWifi();

    // Start these without WiFi too, so the task can keep retrying and the
    // server is ready as soon as the link comes up.
    if (!setupServer()) {
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }
    // Pin the dashboard task to Core 0 (the WiFi/TCPIP core) so that
    // tcpip_api_call() round-trips never block the Arduino loop on Core 1.
    const BaseType_t taskCreated = xTaskCreatePinnedToCore(
        dashboardTask,
        "dashboard",
        taskStackBytes,
        nullptr,
        taskPriority,
        nullptr,
        0  // Core 0
    );
    if (taskCreated != pdPASS) {
        _Log.println(F("Failed to start dashboard task"));
        return module::MODULE_INIT_DEPENDENCY_ERROR;
    }
    runtimeStarted_ = true;

    if (!wifiConnected) {
        _Log.println(F("WiFi not connected; retrying in the background"));
        return module::MODULE_INIT_CONFIG_ERROR;
    }
    return module::MODULE_INIT_SUCCESS;
}

// ─── WiFi setup ──────────────────────────────────────────────────────────────

bool setupWifi() {
    // serviceWifiLink() owns retries, so the core's tight 1 s auto-reconnect stays off.
    WiFi.setAutoReconnect(false);
    WiFi.mode(WIFI_OFF);
    delay(100);  // let the WiFi stack fully idle before re-arming

    WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) {
        // ASSOC_LEAVE is our own disconnect before a retry; keep the real cause.
        if (info.wifi_sta_disconnected.reason != WIFI_REASON_ASSOC_LEAVE) {
            wifiDisconnectReason_ = info.wifi_sta_disconnected.reason;
        }
    }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);

    WiFi.setHostname(HOSTNAME);
    WiFi.mode(WIFI_STA);
    // Modem sleep wakes the radio only at the AP's DTIM beacons, adding
    // 100-400 ms per packet. The board is mains powered, so keep it awake.
    WiFi.setSleep(false);

    // One bounded attempt: control hardware, including the relay safe state,
    // initialises after this, so further retries belong to the dashboard task.
    beginWifiAttempt();
    WiFi.waitForConnectResult(wifiAttemptTimeoutMs);
    serviceWifiLink();
    return WiFi.status() == WL_CONNECTED;
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
