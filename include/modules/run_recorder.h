/**
 * @file run_recorder.h
 * @brief PSRAM run recorder: the dashboard's chart channels at 1 Hz for the last 24 h.
 *
 * Samples the 19 channels the dashboard charts, plus the FSM state id, once a
 * second into a ring buffer in PSRAM (RUN_RECORDER_CAPACITY samples). The ring
 * is served at GET /api/history so the dashboard can show the whole run after a
 * page reload or a WiFi drop-out.
 *
 * Response body: one length-delimited RunHistoryHeader, then length-delimited
 * HistorySample messages, oldest first (proto/telemetry.proto). The optional
 * `from` query parameter skips samples the client already has:
 * @code
 * GET /api/history?from=1200
 * @endcode
 */

#ifndef RUN_RECORDER_H
#define RUN_RECORDER_H

#include <stdint.h>
#include "module.h"

class AsyncWebServer;

namespace run_recorder {

/**
 * Allocate the ring buffer in PSRAM.
 * @return MODULE_INIT_SUCCESS, or MODULE_INIT_HARDWARE_ERROR if the PSRAM
 *         allocation fails (the recorder then stays off; nothing else depends on it).
 */
module::InitStatus init();

/**
 * Record one sample every RUN_RECORDER_PERIOD_MS.
 * @return MODULE_SERVICE_OK when a sample was recorded, SKIPPED between samples
 *         or when init() failed.
 */
module::ServiceStatus service();

/**
 * Register GET /api/history on @p server. Call from dashboard::setupServer()
 * before the server starts.
 * @param server  The dashboard's HTTP server.
 */
void registerRoutes(AsyncWebServer& server);

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = run_recorder::init(); }
    static module::ServiceStatus service() { return _serviceStatus = run_recorder::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace run_recorder

#endif // RUN_RECORDER_H
