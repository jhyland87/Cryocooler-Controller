/**
 * @file web_auth.h
 * @brief Passwords for the dashboard and for OTA updates, stored in NVS flash.
 *
 * Set from the serial console only (`dashboard password`, `ota password`).
 * The dashboard has no password until one is set; OTA always has one and starts
 * at OTA_DEFAULT_PASSWORD. NVS is not encrypted, so both are plaintext in flash.
 *
 * Dashboard: a login page issues a session cookie. "Remember me" saves a hash of
 * the session in flash for DASHBOARD_REMEMBER_DAYS; otherwise it lasts until
 * reboot. Scripts may use HTTP digest instead (user WEB_AUTH_USERNAME).
 * OTA: HTTP digest only; a dashboard session never unlocks it.
 */

#ifndef WEB_AUTH_H
#define WEB_AUTH_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

class AsyncWebServer;
class AsyncWebServerRequest;

namespace web_auth {

static constexpr size_t PASSWORD_MIN_CHARS = 8;
static constexpr size_t PASSWORD_MAX_CHARS = 32;

/**
 * @param password Null-terminated candidate.
 * @return true if it is 8 to 32 printable ASCII characters with no spaces.
 */
inline bool isValidPassword(const char* password) {
    const size_t passwordLen = strlen(password);
    if (passwordLen < PASSWORD_MIN_CHARS || passwordLen > PASSWORD_MAX_CHARS) {
        return false;
    }
    for (size_t charIndex = 0; charIndex < passwordLen; ++charIndex) {
        if (password[charIndex] < 0x21 || password[charIndex] > 0x7E) {
            return false;
        }
    }
    return true;
}

// ─── Stored passwords ─────────────────────────────────────────────────────────

/** Load the passwords and remembered sessions from flash. Call once before the HTTP server starts. */
void init();

/**
 * Set the dashboard password, or remove it. Either way every session ends.
 * @param password A valid password, or "" to leave the dashboard open.
 * @return true if it was saved.
 */
bool setDashboardPassword(const char* password);

/**
 * Set the OTA password, or go back to the default.
 * @param password A valid password, or "" to restore OTA_DEFAULT_PASSWORD.
 * @return true if it was saved.
 */
bool setOtaPassword(const char* password);

/** @return true if the dashboard asks for a password. */
bool hasDashboardPassword();

/** @return true if the OTA password is still OTA_DEFAULT_PASSWORD. */
bool isOtaPasswordDefault();

/** End every dashboard session, remembered ones included. */
void clearSessions();

// ─── HTTP checks (device only) ────────────────────────────────────────────────

/** How a refused dashboard request is answered. */
enum class Route : uint8_t {
    Page,  ///< redirect the browser to the login page
    Api,   ///< 401; with a digest challenge unless the dashboard page itself asked
};

/**
 * Gate a dashboard request: open when no password is set, else it needs a
 * session cookie or a digest login. Answers the request itself when it fails.
 * @param request The incoming request.
 * @param route   How to answer a refusal.
 * @return true if the handler may go on; false if a reply was already sent.
 */
bool allowDashboard(AsyncWebServerRequest* request, Route route = Route::Api);

/**
 * Check a dashboard request without answering it (for the WebSocket handshake).
 * @param request The incoming request.
 * @return true if no password is set or the request carries a live session.
 */
bool hasDashboardAccess(AsyncWebServerRequest* request);

/**
 * Gate an OTA request. Sends the login challenge when it fails.
 * @param request The incoming request.
 * @return true if the handler may go on; false if a 401 was already sent.
 */
bool allowOta(AsyncWebServerRequest* request);

/**
 * Check an OTA request without answering it (for the upload chunk handler).
 * @param request The incoming request.
 * @return true if it carries the OTA login.
 */
bool isOtaAuthorized(AsyncWebServerRequest* request);

/**
 * Register the login page and the session endpoints:
 * GET /login, GET /api/login/challenge, POST /api/login, POST /api/logout,
 * GET /api/session.
 * @param server The dashboard's HTTP server.
 */
void registerRoutes(AsyncWebServer& server);

} // namespace web_auth

#endif // WEB_AUTH_H
