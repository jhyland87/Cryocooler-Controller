/**
 * @file web_auth_stub.cpp
 * @brief Native stand-in for the web_auth password store (no NVS, no HTTP).
 */

#include <cstring>
#include "config.h"
#include "web_auth.h"
#include "web_auth_stub.h"

static char s_dashboardPassword[web_auth::PASSWORD_MAX_CHARS + 1];
static char s_otaPassword[web_auth::PASSWORD_MAX_CHARS + 1] = OTA_DEFAULT_PASSWORD;
static bool s_saveFails = false;
static unsigned s_sessionClears = 0;

namespace web_auth_stub {

void reset() {
    s_dashboardPassword[0] = '\0';
    strcpy(s_otaPassword, OTA_DEFAULT_PASSWORD);
    s_saveFails = false;
    s_sessionClears = 0;
}

const char* dashboardPassword() { return s_dashboardPassword; }
const char* otaPassword()       { return s_otaPassword; }
void setSaveFails(bool fails)   { s_saveFails = fails; }
unsigned sessionClears()        { return s_sessionClears; }

} // namespace web_auth_stub

namespace web_auth {

void init() {}

void clearSessions() { ++s_sessionClears; }

bool setDashboardPassword(const char* password) {
    if (s_saveFails || (password[0] != '\0' && !isValidPassword(password))) {
        return false;
    }
    strcpy(s_dashboardPassword, password);
    clearSessions();
    return true;
}

bool setOtaPassword(const char* password) {
    if (s_saveFails || (password[0] != '\0' && !isValidPassword(password))) {
        return false;
    }
    strcpy(s_otaPassword, password[0] != '\0' ? password : OTA_DEFAULT_PASSWORD);
    return true;
}

bool hasDashboardPassword() { return s_dashboardPassword[0] != '\0'; }
bool isOtaPasswordDefault() { return strcmp(s_otaPassword, OTA_DEFAULT_PASSWORD) == 0; }

} // namespace web_auth
