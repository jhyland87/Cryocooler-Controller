/**
 * @file tick.cpp
 * @brief Implementation of the shared monotonic tick clock (see tick.h).
 *
 * Holds the current-tick timestamp and delta in file-static state so every
 * module can read a consistent time for the loop() iteration without passing
 * it around. On native (host) test builds where millis() is unavailable, the
 * clock only advances via setNowMs().
 */
#include "tick.h"
#ifdef ARDUINO
#include <Arduino.h>
#endif

namespace tick {

/// Timestamp (ms) snapshotted at the start of the current tick.
static uint32_t sNowMs   = 0;
/// Elapsed time (ms) between the previous tick and the current one.
static uint32_t sDeltaMs = 0;

void update() {
#ifdef ARDUINO
    uint32_t prev = sNowMs;
    sNowMs = millis();
    sDeltaMs = sNowMs - prev;
#endif
}

uint32_t nowMs()   { return sNowMs; }
uint32_t deltaMs() { return sDeltaMs; }

void setNowMs(uint32_t ms) {
    sDeltaMs = ms - sNowMs;
    sNowMs = ms;
}

} // namespace tick
