/**
 * @file http_api.cpp
 * @brief HTTP API server — serves live telemetry as JSON.
 *
 * GET /   → JSON object with all current telemetry fields (see telemetry.h).
 *
 * The JSON body is built from the last frame stored by telemetry::emit().
 * Field names match the key names documented in telemetry.h, and values are
 * typed correctly (numbers as JSON numbers, strings as JSON strings).
 *
 * Example response:
 *   {
 *     "state_no": 2,
 *     "state_name": "CoarseCooldown",
 *     "temp_c": 18.72,
 *     "current_a": 1.34,
 *     ...
 *   }
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <ArduinoJson.h>

#include "http_api.h"
#include "telemetry.h"
#include "arduino_secrets.h"
#include "config.h"

WebServer server(HTTP_API_PORT);

namespace http_api {

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

void handleJsonResponse() {
    JsonDocument doc;
    telemetry::fillJson(doc);

    // Measure the serialized size so the correct Content-Length can be sent,
    // then serialize directly into the TCP client stream — no large buffer needed.
    const size_t len = measureJsonPretty(doc);
    server.setContentLength(static_cast<int>(len));
    server.send(200, "application/json", "");
    serializeJsonPretty(doc, server.client());
}

void handleNotFound() {
    server.send(404, "text/plain", "File Not Found");
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

void init() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(SECRET_SSID, SECRET_PASS);
    Serial.println("");

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println("");
    Serial.print("Connected to ");
    Serial.println(SECRET_SSID);
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());

    if (MDNS.begin("esp32")) {
        Serial.println("MDNS responder started");
    }

    server.on("/", handleJsonResponse);
    server.onNotFound(handleNotFound);
    server.begin();
    Serial.println("HTTP server started");
}

IPAddress getIPAddress() {
    return WiFi.localIP();
}

String getMacAddress() {
    uint8_t mac[6];
    WiFi.macAddress(mac);
    return String(mac[0], HEX) + ":" + String(mac[1], HEX) + ":" + String(mac[2], HEX) + ":" + String(mac[3], HEX) + ":" + String(mac[4], HEX) + ":" + String(mac[5], HEX);
}

String getSSID() {
    return WiFi.SSID();
}


void service() {
    server.handleClient();
}

} // namespace http_api
