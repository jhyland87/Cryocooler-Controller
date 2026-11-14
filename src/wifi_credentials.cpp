/**
 * @file wifi_credentials.cpp
 * @brief NVS storage for the WiFi network name, passphrase and on-boot setting.
 */

#include "wifi_credentials.h"

#ifdef ARDUINO
#include <nvs.h>

namespace wifi_credentials {

static constexpr char NVS_NAMESPACE[]  = "wifi";
static constexpr char SSID_KEY[]       = "ssid";
static constexpr char PASSPHRASE_KEY[] = "pass";
static constexpr char ON_BOOT_KEY[]    = "onboot";

/** @return true if @p key was erased or was never there. */
static bool eraseKey(nvs_handle_t handle, const char* key) {
    const esp_err_t result = nvs_erase_key(handle, key);
    return result == ESP_OK || result == ESP_ERR_NVS_NOT_FOUND;
}

bool load(char* ssid, size_t ssidSize, char* passphrase, size_t passphraseSize) {
    ssid[0]       = '\0';
    passphrase[0] = '\0';

    // Fails with NOT_FOUND until the first save creates the namespace.
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle) != ESP_OK) {
        return false;
    }
    const bool found = nvs_get_str(handle, SSID_KEY, ssid, &ssidSize) == ESP_OK &&
                       nvs_get_str(handle, PASSPHRASE_KEY, passphrase, &passphraseSize) == ESP_OK;
    nvs_close(handle);

    if (found && isValidSsid(ssid) && isValidPassphrase(passphrase)) {
        return true;
    }
    ssid[0]       = '\0';
    passphrase[0] = '\0';
    return false;
}

bool save(const char* ssid, const char* passphrase) {
    if (!isValidSsid(ssid) || !isValidPassphrase(passphrase)) {
        return false;
    }
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) {
        return false;
    }
    const bool saved = nvs_set_str(handle, SSID_KEY, ssid) == ESP_OK &&
                       nvs_set_str(handle, PASSPHRASE_KEY, passphrase) == ESP_OK &&
                       nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    return saved;
}

bool clear() {
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) {
        return false;
    }
    const bool cleared = eraseKey(handle, SSID_KEY) && eraseKey(handle, PASSPHRASE_KEY) &&
                         nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    return cleared;
}

bool loadOnBoot() {
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READONLY, &handle) != ESP_OK) {
        return true;
    }
    uint8_t onBoot = 1;
    nvs_get_u8(handle, ON_BOOT_KEY, &onBoot);  // leaves the default when the key is missing
    nvs_close(handle);
    return onBoot != 0;
}

bool saveOnBoot(bool onBoot) {
    nvs_handle_t handle;
    if (nvs_open(NVS_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) {
        return false;
    }
    const bool saved = nvs_set_u8(handle, ON_BOOT_KEY, onBoot ? 1 : 0) == ESP_OK &&
                       nvs_commit(handle) == ESP_OK;
    nvs_close(handle);
    return saved;
}

} // namespace wifi_credentials

#endif // ARDUINO
