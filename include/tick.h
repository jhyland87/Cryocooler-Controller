/**
 * @file tick.h
 * @brief Shared monotonic tick clock — updated once per loop() iteration.
 *
 * Call tick::update() at the very top of loop().  Every module then reads
 * tick::nowMs() to get a consistent timestamp for the current tick — no
 * parameter passing required.
 */
#pragma once
#include <cstdint>

namespace tick {
    /// Call once at the top of loop() to snapshot millis().
    void update();

    /// Milliseconds at the start of the current tick.
    uint32_t nowMs();

    /// Elapsed milliseconds since the previous tick (0 on first call).
    uint32_t deltaMs();

    /// For tests: manually set the tick timestamp.
    void setNowMs(uint32_t ms);
}
