/**
 * @file ota.h
 * @brief HTTP OTA firmware update module.
 *
 * Exposes a POST /ota endpoint via the shared AsyncWebServer (set up in
 * dashboard::setupServer()).  A GET /ota route serves a minimal HTML upload
 * form so the user can trigger an update from any browser on the LAN.
 *
 * ── Safety interlock ──────────────────────────────────────────────────────────
 * OTA updates are rejected while the cryocooler state machine is running.
 * A firmware update reboots the MCU immediately, which would de-energise the
 * motor driver and relays without a controlled shutdown ramp.  The operator
 * must bring the system to Idle or Off before flashing new firmware.
 *
 * ── Partition requirements ────────────────────────────────────────────────────
 * The project uses a custom partitions.csv with two OTA app slots (ota_0 /
 * ota_1) and an otadata partition.  init() verifies these exist at startup and
 * returns MODULE_INIT_CONFIG_ERROR if the running partition table is not OTA-
 * capable (e.g. if you forgot to set board_build.partitions in platformio.ini).
 *
 * ── Update flow ───────────────────────────────────────────────────────────────
 *   1. User POSTs a .bin firmware file to `http://<hostname>/ota`
 *   2. The upload callback streams the file through the Arduino Update library
 *      which internally calls esp_ota_write() into the inactive OTA slot.
 *   3. On completion, Update.end(true) calls esp_ota_set_boot_partition() to
 *      mark the new image as the boot target.
 *   4. A FreeRTOS reboot task fires 500 ms after the HTTP response is sent,
 *      giving the browser time to receive the "Rebooting…" message.
 *   5. On the next boot the new firmware runs from the previously-inactive slot.
 *
 * ── Usage ─────────────────────────────────────────────────────────────────────
 *   Call ota::Module::init() once in initPersistentModules() (before or after
 *   dashboard — init() only interrogates the partition table, no WiFi needed).
 *
 *   Call ota::registerRoutes(httpServer) from dashboard::setupServer() before
 *   httpServer.begin() so the /ota endpoint is live when the server starts.
 *
 *   Add ota::Module::service() to the main loop if you want the service-status
 *   telemetry field to update; the OTA process itself runs in HTTP callbacks
 *   and does not require a service() call.
 */

#pragma once

#ifdef ARDUINO

#include <stdint.h>
#include "module.h"

class AsyncWebServer;

namespace ota {

// ── Status ────────────────────────────────────────────────────────────────────

enum class Status : uint8_t {
    IDLE,        ///< No update in progress.
    IN_PROGRESS, ///< Upload underway; do not power-cycle.
    SUCCESS,     ///< Image written and boot partition set; awaiting reboot.
    FAILED,      ///< Update failed — call getLastError() for details.
};

// ── Lifecycle ─────────────────────────────────────────────────────────────────

/**
 * Verify that an OTA-capable partition table is present.
 *
 * Checks that esp_ota_get_next_update_partition() returns a non-null
 * partition, which is only true when both an otadata partition and at least
 * two OTA app slots exist.
 *
 * @return MODULE_INIT_SUCCESS    if the partition table supports OTA.
 * @return MODULE_INIT_CONFIG_ERROR if no OTA partition is available (wrong
 *                                   partition table flashed).
 */
module::InitStatus init();

/**
 * No-op — the OTA process runs entirely within HTTP upload callbacks.
 * Provided for module-interface compliance and telemetry reporting.
 * @return MODULE_SERVICE_SKIPPED always.
 */
module::ServiceStatus service();

// ── Route registration ────────────────────────────────────────────────────────

/**
 * Register the /ota GET (upload form) and /ota POST (firmware receive)
 * routes on the supplied web server.
 *
 * Must be called before AsyncWebServer::begin().  The server instance is
 * owned by dashboard; this function only adds handlers.
 */
void registerRoutes(AsyncWebServer& server);

// ── State accessors ───────────────────────────────────────────────────────────

/** @return Current OTA state. */
Status getStatus();

/** @return Human-readable label for the current state. */
const char* getStatusText();

/**
 * @return Null-terminated error string from the most recent failed update,
 *         or "" if no error has occurred.
 */
const char* getLastError();

/** @return true while an upload is in progress. */
bool isInProgress();

/** @return true once an upload has completed successfully. */
bool isSuccess();

// ── Firmware info accessors ───────────────────────────────────────────────────

/**
 * Unix epoch (seconds) of the last successful OTA flash stored in NVS.
 * Returns 0 if no OTA update has been performed yet, or if the clock was not
 * synced at the time of the last update.
 */
int64_t getLastFlashTime();

/**
 * @return Firmware version string from the running app description
 *         (populated by PROJECT_VER in platformio.ini / CMakeLists.txt).
 */
const char* getFirmwareVersion();

/**
 * @return Build date + time string for the running firmware image,
 *         e.g. "Mar  6 2026 14:32:01".  Sourced from __DATE__ / __TIME__
 *         baked in at compile time via esp_ota_get_app_description().
 */
const char* getFirmwareBuildDate();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = ota::init(); }
    static module::ServiceStatus service() { return _serviceStatus = ota::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace ota

#endif // ARDUINO
