/**
 * @file web_auth.h
 * @brief Passwords for the dashboard and for OTA updates, stored in NVS flash.
 *
 * Set from the serial console only (`dashboard password`, `ota password`) and
 * checked by the HTTP server with digest authentication, user WEB_AUTH_USERNAME.
 * The dashboard has no password until one is set; OTA always has one and starts
 * at OTA_DEFAULT_PASSWORD. NVS is not encrypted, so both are plaintext in flash.
 */

#ifndef WEB_AUTH_H
#define WEB_AUTH_H

#include <stddef.h>
#include <string.h>

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

/** Load both passwords from flash. Call once before the HTTP server starts. */
void init();

/**
 * Set the dashboard password, or remove it.
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

// ─── HTTP checks (device only) ────────────────────────────────────────────────

/**
 * Gate a dashboard or API request. Sends the login challenge when it fails.
 * @param request The incoming request.
 * @return true if the handler may go on; false if a 401 was already sent.
 */
bool allowDashboard(AsyncWebServerRequest* request);

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

// ─── WebSocket tickets ────────────────────────────────────────────────────────

static constexpr size_t TICKET_CHARS = 16;

/**
 * Issue a one-use ticket for opening the WebSocket; it expires after 30 s.
 * Browsers can't be relied on to send a login on a WebSocket handshake, so the
 * page fetches a ticket over an authenticated request and passes it instead.
 * @param ticket Receives the ticket; at least TICKET_CHARS + 1 bytes.
 */
void issueTicket(char* ticket);

/**
 * Use up a ticket.
 * @param ticket The value the client sent.
 * @return true if it was issued, unused and not expired.
 */
bool redeemTicket(const char* ticket);

} // namespace web_auth

#endif // WEB_AUTH_H
