#include "tick.h"

namespace tick {

static uint32_t sNowMs   = 0;
static uint32_t sDeltaMs = 0;

void update() {
    // no-op in tests — use setNowMs() to control time
}

uint32_t nowMs()   { return sNowMs; }
uint32_t deltaMs() { return sDeltaMs; }

void setNowMs(uint32_t ms) {
    sDeltaMs = ms - sNowMs;
    sNowMs = ms;
}

} // namespace tick
