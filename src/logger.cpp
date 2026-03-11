/**
 * @file logger.cpp
 * @brief In-RAM ring buffer log implementation.
 */

#include "logger.h"

#ifdef ARDUINO
#  include <Arduino.h>   // millis(), Serial
#  include <time.h>      // time()
#else
#  include <cstring>
#  include <cstdint>
#  include <ctime>
// millis() stub provided by test/test_native/stubs/arduino_stub.cpp
extern "C" uint32_t millis();
#endif

// ── Ring buffer state ─────────────────────────────────────────────────────────

namespace logger {

static_assert((CAPACITY & (CAPACITY - 1u)) == 0,
              "CAPACITY must be a power of two for efficient modulo");

static Entry   buf_[CAPACITY];
static uint8_t head_  = 0;   ///< Index of the next write slot
static uint8_t count_ = 0;   ///< Number of valid entries (≤ CAPACITY)

// ── push ─────────────────────────────────────────────────────────────────────

void push(const char* text) {
    push(text, strlen(text));
}

void push(const char* text, size_t len) {
    Entry& e  = buf_[head_];
    e.ms      = millis();
    e.epoch   = static_cast<int64_t>(time(nullptr));

    const size_t copy_len = (len < static_cast<size_t>(MAX_MSG_LEN - 1))
                            ? len
                            : static_cast<size_t>(MAX_MSG_LEN - 1);
    memcpy(e.text, text, copy_len);
    e.text[copy_len] = '\0';

    head_  = static_cast<uint8_t>((head_ + 1u) & (CAPACITY - 1u));
    if (count_ < CAPACITY) { ++count_; }
}

// ── count / get / clear ───────────────────────────────────────────────────────

uint8_t count() { return count_; }

const Entry& get(uint8_t idx) {
    // idx 0 = oldest entry.
    // When the buffer is not yet full the oldest entry is at slot 0.
    // Once full the oldest entry is at head_ (the slot about to be overwritten).
    const uint8_t slot = (count_ < CAPACITY)
                         ? idx
                         : static_cast<uint8_t>((head_ + idx) & (CAPACITY - 1u));
    return buf_[slot];
}

void clear() {
    head_  = 0;
    count_ = 0;
}

// ── fillJson ─────────────────────────────────────────────────────────────────

void fillJson(JsonArray arr, uint8_t maxEntries) {
    const uint8_t n = count_;
    if (n == 0) return;

    // Emit only the most-recent `total` entries.
    const uint8_t total = (maxEntries > 0 && n > maxEntries) ? maxEntries : n;
    const uint8_t start = n - total;

    for (uint8_t i = start; i < n; ++i) {
        const Entry& e   = get(i);
        JsonObject   obj = arr.add<JsonObject>();
        obj["ms"]        = e.ms;
        obj["epoch"]     = e.epoch;
        obj["text"]      = e.text;
    }
}

// ── Module ────────────────────────────────────────────────────────────────────

module::InitStatus init() {
    // Pure in-memory — nothing to set up.
    return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    // Nothing to poll or flush.
    return module::MODULE_SERVICE_SKIPPED;
}

} // namespace logger

// ── LogStream ─────────────────────────────────────────────────────────────────

LogStream Log;

LogStream LogStream::createChildLogger(const char* name) const {
    return LogStream(name);
}

size_t LogStream::write(uint8_t c) {
#ifdef ARDUINO
    // Prefixed streams defer their Serial output to flushLine() so that the
    // "[name] " prefix can be prepended to the complete line in one write.
    // Un-prefixed streams mirror each byte immediately for minimal latency.
    if (prefix_ == nullptr) {
        Serial.write(c);
    }
#endif

    if (pos_ < static_cast<uint8_t>(sizeof(line_) - 1u)) {
        line_[pos_++] = static_cast<char>(c);
    }

    if (c == '\n') {
        flushLine();
    }

    return 1;
}

size_t LogStream::write(const uint8_t* buf, size_t size) {
    for (size_t i = 0; i < size; ++i) {
        write(buf[i]);
    }
    return size;
}

void LogStream::flushLine() {
    line_[pos_] = '\0';

    if (prefix_ != nullptr) {
        // Build the prefixed line once, then send it to both Serial and the
        // ring buffer.  snprintf truncates gracefully if the combined string
        // exceeds MAX_MSG_LEN.
        char prefixed[logger::MAX_MSG_LEN];
        const int n = snprintf(prefixed, sizeof(prefixed), "[%s] %s", prefix_, line_);
        const size_t len = (n > 0 && n < static_cast<int>(logger::MAX_MSG_LEN))
                           ? static_cast<size_t>(n)
                           : static_cast<size_t>(logger::MAX_MSG_LEN - 1u);
#ifdef ARDUINO
        // prefixed already contains the trailing '\n' (stored in line_ before
        // flushLine() was called), so no extra write is needed.
        Serial.print(prefixed);
#endif
        logger::push(prefixed, len);
    } else {
        logger::push(line_, pos_);
    }

    pos_ = 0;
}
