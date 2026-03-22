#include "tick.h"
#ifdef ARDUINO
#include <Arduino.h>
#endif

namespace tick {

static uint32_t sNowMs   = 0;
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
