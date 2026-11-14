/**
 * @file dashboard.h
 * @brief WiFi, HTTP/OTA server and WebSocket telemetry broadcast interface.
 *
 * A dedicated FreeRTOS task (Core 0) manages WiFi, the HTTP/WebSocket server,
 * and Protobuf telemetry delivery to connected SPA clients at 1 Hz.
 * The Arduino loop task (Core 1) is never blocked.
 */

#ifndef DASHBOARD_H
#define DASHBOARD_H

#include "module.h"

class Print;

namespace dashboard {

/**
 * Initialise WiFi, start the HTTP/WebSocket server, and
 * launch the background FreeRTOS task that handles all broadcasting.
 * Call from setup(). Makes one bounded WiFi attempt, then the task keeps retrying
 * with backoff. A repeat call only requests a retry, without blocking.
 * @return MODULE_INIT_SUCCESS when connected (also set later if the task connects),
 *         MODULE_INIT_CONFIG_ERROR while WiFi is down, off, or has no saved credentials,
 *         MODULE_INIT_DEPENDENCY_ERROR if the server or task can't start.
 */
module::InitStatus init();

/**
 * No-op compatibility stub — the dashboard task is self-scheduling.
 * Safe (and harmless) to call from loop() on every tick.
 * @return SERVICE_SKIPPED always (work is done by the FreeRTOS task).
 */
module::ServiceStatus service();

/** Enable dashboard broadcasts (default: enabled). */
void enable();

/** Disable dashboard broadcasts. */
void disable();

/** @return true if dashboard broadcasts are enabled. */
bool isEnabled();

/** Ask the dashboard task to start a new WiFi attempt on its next tick (within 1 s). */
void requestWifiRetry();

/** Ask the dashboard task to re-read the saved credentials and reconnect with them. */
void reloadWifiCredentials();

/** Ask the dashboard task to scan and print every visible network to the serial port. */
void requestWifiScan();

/**
 * Turn the WiFi radio on or off, applied by the dashboard task. Not stored: the
 * state at boot comes from wifi_credentials::loadOnBoot().
 * @param enabled true to turn WiFi on.
 */
void setWifiEnabled(bool enabled);

/** @return true if WiFi is set to on (it may still be disconnected). */
bool isWifiEnabled();

/**
 * Request a maximum WiFi transmit power, applied by the dashboard task. Starts a
 * new attempt when not connected. Not stored: a reboot returns to the default.
 * @param powerDbm 19.5, 19, 18.5, 17, 15, 13, 11, 8.5, 7, 5, 2 or -1 dBm.
 * @return false if @p powerDbm isn't a supported level.
 */
bool setWifiTxPower(float powerDbm);

/**
 * Print on/off state, saved settings, link state, signal, MAC, transmit power and last disconnect reason.
 * @param out Stream to print to.
 */
void printWifiStatus(Print& out);

/** Snapshot of the WiFi link, for telemetry. */
struct WifiInfo {
    bool   connected;
    int8_t rssiDbm;   ///< 0 when not connected
    char   ip[16];    ///< dotted IPv4; empty when not connected
    char   ssid[33];  ///< joined network (32 characters + NUL); empty when not connected
};

/**
 * Read the current WiFi link details.
 * @param info Receives the snapshot.
 */
void getWifiInfo(WifiInfo& info);

// Internal — called from init() and the dashboard task; defined in dashboard.cpp.
bool setupWifi();
bool setupServer();
void serviceWifiLink();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = dashboard::init(); }
    /** No-op: the FreeRTOS task self-schedules.  Call from loop() harmlessly. */
    static module::ServiceStatus service() { return _serviceStatus = dashboard::service(); }
    static void enable()                   { dashboard::enable(); }
    static void disable()                  { dashboard::disable(); }
    static bool isEnabled()                { return dashboard::isEnabled(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace dashboard

#endif // DASHBOARD_H
