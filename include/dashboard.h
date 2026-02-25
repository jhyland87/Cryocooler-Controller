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

namespace dashboard {

/**
 * Initialise WiFi, build the dashboard JSON, start the TCP server, and
 * launch the background FreeRTOS task that handles all broadcasting.
 * Call once from setup().
 */
void init();

/**
 * No-op compatibility stub — the dashboard task is self-scheduling.
 * Safe (and harmless) to call from loop() on every tick.
 */
void service();

/** Enable dashboard broadcasts (default: enabled). */
void enable();

/** Disable dashboard broadcasts. */
void disable();

/** @return true if dashboard broadcasts are enabled. */
bool isEnabled();

// Internal — called from init(); defined in dashboard.cpp.
void setupWifi();
void setupServer();

} // namespace dashboard

#endif // DASHBOARD_H
