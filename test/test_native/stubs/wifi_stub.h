/**
 * @file wifi_stub.h
 * @brief Test access to the in-RAM WiFi credential store and dashboard WiFi requests.
 */

#ifndef WIFI_STUB_H
#define WIFI_STUB_H

namespace wifi_stub {

/** Forget everything: no credentials, on-boot on, WiFi on, no requests, saves succeed. */
void reset();

const char* savedSsid();        ///< "" when nothing is saved
const char* savedPassphrase();  ///< "" when nothing is saved or the network is open
bool hasSaved();
bool onBoot();
bool reloadRequested();
bool scanRequested();
void setSaveFails(bool fails);  ///< make save() / saveOnBoot() report a flash failure

} // namespace wifi_stub

#endif // WIFI_STUB_H
