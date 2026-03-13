/**
 * @file logger.h
 * @brief In-RAM ring buffer log with a Serial-mirroring stream wrapper.
 *
 * Single module that provides lightweight in-memory logging.  Everything
 * lives in the `logger` namespace so call sites are consistent with every
 * other module in this project.
 *
 * ── What it does ─────────────────────────────────────────────────────────────
 *
 *   • Maintains a fixed-capacity ring buffer of recent log lines in RAM.
 *   • Provides `LogStream Log` — a Print-derived global that simultaneously
 *     forwards bytes to the hardware UART (ARDUINO builds) and stores each
 *     completed line ('\n'-terminated) in the ring buffer.
 *   • Exposes `logger::fillJson()` so the telemetry layer can embed the last N
 *     messages in every WebSocket/HTTP JSON push, giving the dashboard a live
 *     log panel with no SD card required.
 *
 * ── Usage ────────────────────────────────────────────────────────────────────
 *
 *   // Drop-in replacement for Serial.printf / Serial.print / Serial.println:
 *   Log.printf("[sensor] temp = %.2f K\n", t);
 *   Log.println("System started");
 *
 *   // Read the most-recent entries directly (oldest → newest, idx 0 = oldest):
 *   for (uint8_t i = 0; i < logger::count(); ++i) {
 *       const auto& e = logger::get(i);
 *       Serial.printf("%u  %s", e.ms, e.text);
 *   }
 *
 *   // Serialise into an ArduinoJson array for the dashboard:
 *   logger::fillJson(doc["logs"].to<JsonArray>());
 *
 * ── Memory budget ─────────────────────────────────────────────────────────────
 *
 *   CAPACITY × sizeof(Entry)  =  64 × (4 + 8 + 128)  =  8 960 bytes static RAM.
 *   Adjust CAPACITY / MAX_MSG_LEN below to taste.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include <Print.h>
#include <ArduinoJson.h>
#include "module.h"

namespace logger {

// ── Configuration ─────────────────────────────────────────────────────────────

/** Maximum number of log lines retained in RAM (oldest silently dropped). */
static constexpr uint8_t CAPACITY = 64;

/**
 * Maximum byte length of a stored log line, including the NUL terminator.
 * Lines longer than MAX_MSG_LEN – 1 characters are truncated.
 */
static constexpr uint8_t MAX_MSG_LEN = 128;

/**
 * Maximum number of entries included in the telemetry "logs" JSON array.
 * Limits the JSON payload size when the buffer is fully populated.
 * Pass 0 to fillJson() to include all entries (up to CAPACITY).
 */
static constexpr uint8_t TELEMETRY_MAX_ENTRIES = 32;

// ── Entry ─────────────────────────────────────────────────────────────────────

struct Entry {
    uint32_t ms;                ///< millis() when the line was flushed
    int64_t  epoch;             ///< Unix epoch seconds (UTC) from time(); 0 if clock not yet synced
    char     text[MAX_MSG_LEN]; ///< NUL-terminated message (may include '\n')
};

// ── Ring buffer operations ────────────────────────────────────────────────────

/**
 * Push a NUL-terminated string into the ring buffer.
 * Truncated silently to MAX_MSG_LEN – 1 characters.
 * If the buffer is full the oldest entry is overwritten.
 */
void push(const char* text);

/**
 * Push exactly @p len bytes (not necessarily NUL-terminated).
 * A NUL terminator is appended automatically.
 */
void push(const char* text, size_t len);

/** Return the number of valid entries currently held (0 … CAPACITY). */
uint8_t count();

/**
 * Return a const reference to the entry at logical index @p idx.
 * @p idx 0 is the oldest entry; count() – 1 is the newest.
 * Behaviour is undefined when @p idx >= count().
 */
const Entry& get(uint8_t idx);

/** Discard all entries. */
void clear();

/** Return the epoch (Unix seconds) of the most recent log entry, or 0 if empty. */
int64_t getLastLogEpoch();

/**
 * Append up to @p maxEntries of the most-recent log lines to @p arr.
 * Each element: {"ms": <uint32>, "epoch": <int64>, "text": "<string>"}
 * @param arr        Target ArduinoJson JsonArray (appended to, not cleared).
 * @param maxEntries Maximum entries to emit.  0 = include all (up to CAPACITY).
 */
void fillJson(JsonArray arr, uint8_t maxEntries = 0);

// ── Module interface ──────────────────────────────────────────────────────────

module::InitStatus    init();
module::ServiceStatus service();

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = logger::init(); }
    static module::ServiceStatus service() { return _serviceStatus = logger::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace logger

// ── LogStream ─────────────────────────────────────────────────────────────────

/**
 * A Print-derived stream that mirrors all output to hardware Serial AND stores
 * complete lines in the logger ring buffer.
 *
 * Overriding write() at the Print level means every method — print, println,
 * printf, write — routes through the same two-path logic automatically, so
 * changing `Serial.x(...)` to `Log.x(...)` at call sites is the only change
 * required to capture that output.
 *
 * Line flushing: characters are buffered internally until '\n' is received,
 * at which point the accumulated line is pushed into the ring buffer.
 *
 * In ARDUINO builds bytes are forwarded to the hardware UART via Serial.
 * In native (host) test builds the byte-write path is a no-op for Serial;
 * the ring buffer still receives everything through logger::push().
 *
 * ── Prefixed child loggers ───────────────────────────────────────────────────
 *
 * Call createChildLogger() to obtain an independent LogStream that
 * automatically prepends "[name] " to every flushed line in both the serial
 * output and the ring buffer:
 *
 *   static LogStream kLog = Log.createChildLogger("cold_head");
 *   kLog.println("Initialising ...");
 *   // serial + ring buffer receive: "[cold_head] Initialising ..."
 *
 * @p name must remain valid for the lifetime of the child instance; string
 * literals are ideal.  The child has its own independent line buffer so it
 * is safe to use concurrently with the parent and other children (subject to
 * the same single-writer-per-instance assumption as the parent).
 */
class LogStream : public Print {
public:
    /** Default constructor — no prefix.  Used for the global Log instance. */
    LogStream() = default;

    /**
     * Create an independent LogStream that prepends "[name] " to every
     * flushed line in both the Serial output and the ring buffer.
     *
     * @param name  Module label used as the prefix (e.g. "cold_head").
     *              Must be a string literal or otherwise outlive the child.
     */
    LogStream createChildLogger(const char* name) const;

    size_t write(uint8_t c) override;
    size_t write(const uint8_t* buf, size_t size) override;

private:
    /** Private constructor used by createChildLogger(). */
    explicit LogStream(const char* prefix) : prefix_(prefix) {}

    char        line_[logger::MAX_MSG_LEN]; ///< Accumulation buffer for the current line
    uint8_t     pos_    = 0;                ///< Next write position in line_
    const char* prefix_ = nullptr;          ///< Optional "[name] " prefix; null = no prefix

    void flushLine(); ///< Flush line_[0..pos_] to Serial + ring buffer, then reset pos_
};

/** Global LogStream — use in place of Serial for all logged output. */
extern LogStream Log;
