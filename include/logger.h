/**
 * @file logger.h
 * @brief SD-backed serial and telemetry logger.
 *
 * Provides two independent logging channels, both backed by the SD card:
 *
 *   1. Serial log  — logf() / log() mirror every message sent to Serial into
 *      a plain-text file with a UTC epoch timestamp prefix on each line.
 *      File: LOG_SERIAL_PATH  (default "/serial.log")
 *
 *   2. Telemetry log — logTelemetry() appends one CSV row per call from a
 *      FrameBuilder snapshot.  The header row is written automatically on the
 *      first call (or whenever the file does not yet exist).
 *      File: LOG_TELEMETRY_PATH  (default "/telemetry.csv")
 *
 * Both functions are no-ops when the SD card is not available.
 *
 * ── Module lifecycle ────────────────────────────────────────────────────────
 *
 *   Call logger::Module::init() after hardware::Module::init() (the shared
 *   SPI bus must be running before SD.begin() is called).
 *   logger::Module::service() must be called regularly — it polls SD_CD_PIN
 *   and drives the card eject / re-insert state machine.
 *
 * ── Usage example ───────────────────────────────────────────────────────────
 *
 *   // In setup():
 *   logger::Module::init();
 *
 *   // Anywhere in the application:
 *   logger::logf("[sensor] temp = %.2f K\n", cold_head::getLastTempK());
 *   logger::logTelemetry(telemetry::getLastFrame());
 */

#pragma once

#include <stdarg.h>
#include "module.h"
#include "frame_builder.h"

namespace logger {

// ---------------------------------------------------------------------------
// File paths on the SD card
// ---------------------------------------------------------------------------

/** Plain-text log echoing Serial output. */
static constexpr char SERIAL_LOG_PATH[]  = "/serial.log";

/** CSV telemetry log — one row per logTelemetry() call. */
static constexpr char TELEMETRY_PATH[]   = "/telemetry.csv";

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

/**
 * Mount the SD card and verify it is accessible.
 *
 * Must be called after hardware::Module::init() so that the shared SPI bus
 * (SPI_CLK / SPI_MISO / SPI_MOSI) is already running.
 *
 * @return MODULE_INIT_SUCCESS      — SD card mounted and ready.
 *         MODULE_INIT_HARDWARE_ERROR — SD.begin() failed or no card inserted.
 */
module::InitStatus init();

/**
 * Poll the SD card CD (Card Detect) pin and drive the hot-swap state machine.
 *
 * Must be called regularly (e.g. from the main service loop).
 *
 * Behaviour:
 *   - CD pin HIGH (card present)  + not ready  →  attempt SD.begin() with a
 *     REINIT_COOLDOWN_MS back-off between tries.
 *   - CD pin LOW  (card absent)   + ready       →  SD.end(), flags cleared,
 *     Serial log paused until next insertion.
 *   - Three consecutive write failures also trigger the eject path as a
 *     belt-and-suspenders fallback if the CD pin is unreliable.
 *
 * @return MODULE_SERVICE_OK       if the card state changed this call.
 *         MODULE_SERVICE_SKIPPED  otherwise.
 */
module::ServiceStatus service();

// ---------------------------------------------------------------------------
// Serial log — plain-text file echo
// ---------------------------------------------------------------------------

/**
 * Write @p msg to Serial and, if the SD card is ready, append it to the
 * serial log file with a UTC epoch timestamp prefix.
 *
 * The message is written to Serial exactly as supplied (no extra newline).
 * The log file entry format is:
 *
 *   [<epoch_s>] <msg>
 *
 * where <epoch_s> is the current UNIX timestamp in seconds.  The timestamp
 * is 0 until SNTP has synced (normal for early-boot messages).
 *
 * @param msg  NUL-terminated string.  Must not be nullptr.
 */
void log(const char* msg);

/**
 * printf-style variant of log().
 *
 * Formats into a stack-local buffer (LOG_BUF_SIZE bytes) then delegates to
 * log().  Truncation is silent — increase kLogBufSize if messages are being
 * cut short.
 *
 * @param fmt  printf format string.
 */
void logf(const char* fmt, ...) __attribute__((format(printf, 1, 2)));

// ---------------------------------------------------------------------------
// Telemetry log — CSV file
// ---------------------------------------------------------------------------

/**
 * Append one CSV row from @p frame to the telemetry log file.
 *
 * Header row behaviour:
 *   - Written automatically on the first successful call.
 *   - Re-written if the file no longer exists (e.g. after it was deleted via
 *     a serial command).
 *
 * Values are taken from FrameBuilder::Field::str — the pre-formatted strings
 * produced by each field() call — so the CSV precisely mirrors what would be
 * transmitted to Serial Studio.  Values that contain a comma are wrapped in
 * double-quotes to produce valid CSV.
 *
 * No-op if the SD card is not ready or if @p frame contains no fields.
 *
 * @param frame  Telemetry frame to persist (typically telemetry::getLastFrame()).
 */
void logTelemetry(const FrameBuilder& frame);

// ---------------------------------------------------------------------------
// Module interface
// ---------------------------------------------------------------------------

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = logger::init(); }
    static module::ServiceStatus service() { return _serviceStatus = logger::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace logger
