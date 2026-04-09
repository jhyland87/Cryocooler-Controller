/**
 * @file dashboard.h
 * @brief Serial Studio async TCP dashboard interface.
 *
 * A dedicated FreeRTOS task (Core 0) manages WiFi, the async TCP server,
 * JSON serialisation, and chunked delivery to connected clients at 1 Hz.
 * The Arduino loop task (Core 1) is never blocked.
 */

#ifndef DASHBOARD_H
#define DASHBOARD_H

#include "module.h"

namespace dashboard {

/**
 * Initialise WiFi, build the dashboard JSON, start the TCP server, and
 * launch the background FreeRTOS task that handles all broadcasting.
 * Call once from setup().
 * @return MODULE_INIT_SUCCESS on success, MODULE_INIT_HARDWARE_ERROR if WiFi fails.
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

// Internal — called from init(); defined in dashboard.cpp.
bool setupWifi();
bool setupServer();

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
