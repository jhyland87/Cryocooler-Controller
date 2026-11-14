/**
 * @file wifi_credentials.h
 * @brief WiFi network name, passphrase and on-boot setting, stored in NVS flash.
 *
 * Set from the serial console (`wifi set`, `wifi onboot`) and read by the dashboard module.
 * NVS is not encrypted on this board, so the passphrase is plaintext in flash.
 */

#ifndef WIFI_CREDENTIALS_H
#define WIFI_CREDENTIALS_H

#include <stddef.h>
#include <string.h>

namespace wifi_credentials {

// Not MAX_SSID_LEN / MAX_PASSPHRASE_LEN: esp_wifi_types.h defines those as macros.
static constexpr size_t SSID_MAX_CHARS       = 32;  ///< IEEE 802.11 SSID limit
static constexpr size_t PASSPHRASE_MIN_CHARS = 8;   ///< WPA passphrase minimum
static constexpr size_t PASSPHRASE_MAX_CHARS = 64;  ///< 63-char passphrase or 64 hex digits

/**
 * @param ssid Null-terminated network name.
 * @return true if @p ssid is 1 to 32 characters.
 */
inline bool isValidSsid(const char* ssid) {
    const size_t ssidLen = strlen(ssid);
    return ssidLen >= 1 && ssidLen <= SSID_MAX_CHARS;
}

/**
 * @param passphrase Null-terminated passphrase; empty means an open network.
 * @return true if @p passphrase is empty or 8 to 64 characters.
 */
inline bool isValidPassphrase(const char* passphrase) {
    const size_t passphraseLen = strlen(passphrase);
    return passphraseLen == 0 ||
           (passphraseLen >= PASSPHRASE_MIN_CHARS && passphraseLen <= PASSPHRASE_MAX_CHARS);
}

/**
 * Read the saved credentials. Both buffers are left empty when nothing is saved.
 * @param ssid           Receives the network name.
 * @param ssidSize       Size of @p ssid; at least SSID_MAX_CHARS + 1.
 * @param passphrase     Receives the passphrase (empty for an open network).
 * @param passphraseSize Size of @p passphrase; at least PASSPHRASE_MAX_CHARS + 1.
 * @return true if valid credentials were loaded.
 */
bool load(char* ssid, size_t ssidSize, char* passphrase, size_t passphraseSize);

/**
 * Save credentials, replacing any previous ones.
 * @param ssid       Network name; must pass isValidSsid().
 * @param passphrase Passphrase; must pass isValidPassphrase().
 * @return true if they were written and committed.
 */
bool save(const char* ssid, const char* passphrase);

/**
 * Erase the saved credentials. The on-boot setting is kept.
 * @return true if the erase was committed.
 */
bool clear();

/** @return whether WiFi starts at boot; true when no setting is saved. */
bool loadOnBoot();

/**
 * Save whether WiFi starts at boot.
 * @param onBoot true to start WiFi at boot.
 * @return true if it was written and committed.
 */
bool saveOnBoot(bool onBoot);

} // namespace wifi_credentials

#endif // WIFI_CREDENTIALS_H
