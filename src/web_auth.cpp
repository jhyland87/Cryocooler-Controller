/**
 * @file web_auth.cpp
 * @brief Dashboard and OTA passwords: NVS storage, HTTP digest checks, WebSocket tickets.
 */

#include "web_auth.h"

#ifdef ARDUINO
#include <Arduino.h>
#include <ESPAsyncWebServer.h>
#include <esp_random.h>
#include <freertos/FreeRTOS.h>
#include <nvs.h>
#include "config.h"

namespace web_auth {

static constexpr char NVS_NAMESPACE[] = "web_auth";
static constexpr char DASHBOARD_KEY[] = "dashboard";
static constexpr char OTA_KEY[]       = "ota";
static constexpr char REALM[]         = "cryocooler";

static constexpr uint32_t ticketLifetimeMs = 30000;
static constexpr size_t   ticketSlots      = 4;

struct Ticket {
    char     value[TICKET_CHARS + 1];
    uint32_t issuedMs;
    bool     live;
};

// Written by the loop task (serial commands), read by the web server task.
static portMUX_TYPE sLock = portMUX_INITIALIZER_UNLOCKED;
static char   sDashboardPassword[PASSWORD_MAX_CHARS + 1] = "";
static char   sOtaPassword[PASSWORD_MAX_CHARS + 1]       = OTA_DEFAULT_PASSWORD;
static Ticket sTickets[ticketSlots]                      = {};
static size_t sNextTicketSlot                            = 0;

// ─── Storage ──────────────────────────────────────────────────────────────────

/** Read @p key into @p password; leaves it untouched when missing or invalid. */
static void loadPassword(nvs_handle_t handle, const char* key, char* password) {
    char   stored[PASSWORD_MAX_CHARS + 1];
    size_t storedSize = sizeof(stored);
    if (nvs_get_str(handle, key, stored, &storedSize) == ESP_OK && isValidPassword(stored)) {
        strcpy(password, stored);
    }
}

/** Save @p password under @p key, or erase the key when it is empty. */
static bool storePassword(const char* key, const char* password) {
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) {
        return false;
    }
    esp_err_t result;
    if (password[0] == '\0') {
        result = nvs_erase_key(handle, key);
        if (result == ESP_ERR_NVS_NOT_FOUND) {
            result = ESP_OK;
        }
    } else {
        result = nvs_set_str(handle, key, password);
    }
    const bool stored = (result == ESP_OK) && nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    return stored;
}

static void copyLocked(char* destination, const char* source) {
    portENTER_CRITICAL(&sLock);
    strcpy(destination, source);
    portEXIT_CRITICAL(&sLock);
}

void init() {
    // Fails with NOT_FOUND until the first save creates the namespace.
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle) != ESP_OK) {
        return;
    }
    loadPassword(handle, DASHBOARD_KEY, sDashboardPassword);
    loadPassword(handle, OTA_KEY, sOtaPassword);
    nvs_close(handle);
}

bool setDashboardPassword(const char* password) {
    if (password[0] != '\0' && !isValidPassword(password)) {
        return false;
    }
    if (!storePassword(DASHBOARD_KEY, password)) {
        return false;
    }
    copyLocked(sDashboardPassword, password);
    return true;
}

bool setOtaPassword(const char* password) {
    if (password[0] != '\0' && !isValidPassword(password)) {
        return false;
    }
    if (!storePassword(OTA_KEY, password)) {
        return false;
    }
    copyLocked(sOtaPassword, password[0] != '\0' ? password : OTA_DEFAULT_PASSWORD);
    return true;
}

bool hasDashboardPassword() {
    return sDashboardPassword[0] != '\0';
}

bool isOtaPasswordDefault() {
    char password[PASSWORD_MAX_CHARS + 1];
    copyLocked(password, sOtaPassword);
    return strcmp(password, OTA_DEFAULT_PASSWORD) == 0;
}

// ─── HTTP checks ──────────────────────────────────────────────────────────────

static bool hasLogin(AsyncWebServerRequest* request, const char* storedPassword) {
    // Digest only: a Basic login would put the password on the network in the clear.
    const AsyncWebHeader* authorization = request->getHeader("Authorization");
    if (authorization == nullptr || !authorization->value().startsWith("Digest ")) {
        return false;
    }
    char password[PASSWORD_MAX_CHARS + 1];
    copyLocked(password, storedPassword);
    return request->authenticate(WEB_AUTH_USERNAME, password, REALM);
}

bool allowDashboard(AsyncWebServerRequest* request) {
    if (!hasDashboardPassword() || hasLogin(request, sDashboardPassword)) {
        return true;
    }
    request->requestAuthentication(REALM, true);
    return false;
}

bool isOtaAuthorized(AsyncWebServerRequest* request) {
    return hasLogin(request, sOtaPassword);
}

bool allowOta(AsyncWebServerRequest* request) {
    if (isOtaAuthorized(request)) {
        return true;
    }
    request->requestAuthentication(REALM, true);
    return false;
}

// ─── WebSocket tickets ────────────────────────────────────────────────────────

void issueTicket(char* ticket) {
    snprintf(ticket, TICKET_CHARS + 1, "%08lx%08lx",
             static_cast<unsigned long>(esp_random()), static_cast<unsigned long>(esp_random()));

    portENTER_CRITICAL(&sLock);
    Ticket& slot = sTickets[sNextTicketSlot];
    sNextTicketSlot = (sNextTicketSlot + 1) % ticketSlots;
    strcpy(slot.value, ticket);
    slot.issuedMs = millis();
    slot.live     = true;
    portEXIT_CRITICAL(&sLock);
}

bool redeemTicket(const char* ticket) {
    if (strlen(ticket) != TICKET_CHARS) {
        return false;
    }
    const uint32_t nowMs = millis();
    bool redeemed = false;

    portENTER_CRITICAL(&sLock);
    for (Ticket& slot : sTickets) {
        if (!slot.live || strcmp(slot.value, ticket) != 0) {
            continue;
        }
        slot.live = false;
        redeemed  = (nowMs - slot.issuedMs) < ticketLifetimeMs;
        break;
    }
    portEXIT_CRITICAL(&sLock);
    return redeemed;
}

} // namespace web_auth

#endif // ARDUINO
