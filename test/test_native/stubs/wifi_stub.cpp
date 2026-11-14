/**
 * @file wifi_stub.cpp
 * @brief Native stand-ins for wifi_credentials (NVS) and the dashboard WiFi requests.
 */

#include <cstring>
#include "wifi_credentials.h"
#include "dashboard.h"
#include "wifi_stub.h"

static char s_ssid[wifi_credentials::SSID_MAX_CHARS + 1];
static char s_passphrase[wifi_credentials::PASSPHRASE_MAX_CHARS + 1];
static bool s_hasSaved        = false;
static bool s_onBoot          = true;
static bool s_saveFails       = false;
static bool s_wifiEnabled     = true;
static bool s_reloadRequested = false;
static bool s_scanRequested   = false;

namespace wifi_stub {

void reset() {
    s_ssid[0]         = '\0';
    s_passphrase[0]   = '\0';
    s_hasSaved        = false;
    s_onBoot          = true;
    s_saveFails       = false;
    s_wifiEnabled     = true;
    s_reloadRequested = false;
    s_scanRequested   = false;
}

const char* savedSsid()       { return s_ssid; }
const char* savedPassphrase() { return s_passphrase; }
bool hasSaved()               { return s_hasSaved; }
bool onBoot()                 { return s_onBoot; }
bool reloadRequested()        { return s_reloadRequested; }
bool scanRequested()          { return s_scanRequested; }
void setSaveFails(bool fails) { s_saveFails = fails; }

} // namespace wifi_stub

namespace wifi_credentials {

bool load(char* ssid, size_t ssidSize, char* passphrase, size_t passphraseSize) {
    ssid[0]       = '\0';
    passphrase[0] = '\0';
    if (!s_hasSaved) {
        return false;
    }
    strncpy(ssid, s_ssid, ssidSize - 1);
    ssid[ssidSize - 1] = '\0';
    strncpy(passphrase, s_passphrase, passphraseSize - 1);
    passphrase[passphraseSize - 1] = '\0';
    return true;
}

bool save(const char* ssid, const char* passphrase) {
    if (s_saveFails || !isValidSsid(ssid) || !isValidPassphrase(passphrase)) {
        return false;
    }
    strcpy(s_ssid, ssid);
    strcpy(s_passphrase, passphrase);
    s_hasSaved = true;
    return true;
}

bool clear() {
    s_ssid[0]       = '\0';
    s_passphrase[0] = '\0';
    s_hasSaved      = false;
    return true;
}

bool loadOnBoot() { return s_onBoot; }

bool saveOnBoot(bool onBoot) {
    if (s_saveFails) {
        return false;
    }
    s_onBoot = onBoot;
    return true;
}

} // namespace wifi_credentials

namespace dashboard {

void reloadWifiCredentials()      { s_reloadRequested = true; }
void requestWifiScan()            { s_scanRequested = true; }
void setWifiEnabled(bool enabled) { s_wifiEnabled = enabled; }
bool isWifiEnabled()              { return s_wifiEnabled; }

} // namespace dashboard
