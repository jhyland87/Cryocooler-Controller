/**
 * @file logger_stub.cpp
 * @brief Logger + LogStream implementation for native (host-PC) unit tests.
 *
 * Provides the ring-buffer API and the LogStream Print-derived class so that
 * modules which use Log.printf() / logger::push() compile and link natively.
 * Closely mirrors the real implementation so log-buffer unit tests pass.
 */

#include "logger.h"
#include <cstring>
#include <cstdio>
#include <time.h>

// millis() provided by stubs/arduino_stub.cpp
extern "C" uint32_t millis(void);

// ── Ring buffer implementation ───────────────────────────────────────────────

namespace logger {

static Entry sEntries[CAPACITY];
static uint8_t sCount = 0;
static uint8_t sHead  = 0;   // next write position

void push(const char* text) {
    push(text, strlen(text));
}

void push(const char* text, size_t len) {
    Entry& entry = sEntries[sHead];
    entry.ms    = millis();
    entry.epoch = static_cast<int64_t>(time(nullptr));
    if (len >= MAX_MSG_LEN - 1u) len = MAX_MSG_LEN - 2u;
    memcpy(entry.text, text, len);
    entry.text[len] = '\0';
    sHead = static_cast<uint8_t>((sHead + 1u) % CAPACITY);
    if (sCount < CAPACITY) ++sCount;
}

uint8_t count() { return sCount; }

const Entry& get(uint8_t idx) {
    // oldest-first: slot = (head - count + idx) mod CAPACITY
    uint8_t slot = static_cast<uint8_t>((sHead + CAPACITY - sCount + idx) % CAPACITY);
    return sEntries[slot];
}

void clear() {
    sCount = 0;
    sHead  = 0;
}

int64_t getLastLogEpoch() {
    if (sCount == 0) return 0;
    // Most recent entry is at (sHead - 1 + CAPACITY) % CAPACITY
    uint8_t last = static_cast<uint8_t>((sHead + CAPACITY - 1u) % CAPACITY);
    return sEntries[last].epoch;
}

void fillJson(JsonArray arr, uint8_t maxEntries) {
    const uint8_t total = sCount;
    if (total == 0) return;

    uint8_t entryCount = (maxEntries == 0u || maxEntries > total) ? total : maxEntries;
    // Start from (total - n) to get the most recent n entries.
    uint8_t startIdx = static_cast<uint8_t>(total - entryCount);
    for (uint8_t entryIndex = startIdx; entryIndex < total; ++entryIndex) {
        const Entry& entry = get(entryIndex);
        JsonObject obj = arr.add<JsonObject>();
        obj["ms"]    = entry.ms;
        obj["epoch"] = entry.epoch;
        obj["text"]  = entry.text;
    }
}

} // namespace logger

// ── LogStream implementation ─────────────────────────────────────────────────

LogStream Log;

LogStream LogStream::createChildLogger(const char* name) const {
    return LogStream(name);
}

size_t LogStream::write(uint8_t character) {
    if (pos_ < sizeof(line_) - 1u) {
        line_[pos_++] = static_cast<char>(character);
    }
    if (character == '\n') {
        flushLine();
    }
    return 1;
}

size_t LogStream::write(const uint8_t* buf, size_t size) {
    for (size_t byteIndex = 0; byteIndex < size; ++byteIndex) {
        write(buf[byteIndex]);
    }
    return size;
}

void LogStream::flushLine() {
    line_[pos_] = '\0';
    if (prefix_) {
        char prefixed[logger::MAX_MSG_LEN];
        snprintf(prefixed, sizeof(prefixed), "[%s] %s", prefix_, line_);
        logger::push(prefixed);
    } else {
        logger::push(line_, pos_);
    }
    pos_ = 0;
}
