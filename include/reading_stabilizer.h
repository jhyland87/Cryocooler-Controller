/**
 * @file reading_stabilizer.h
 * @brief Decides when a sensor's first readings have settled enough to report.
 *
 * Header-only and free of Arduino calls, so the same logic runs on the ESP32
 * and in the native unit tests.  A reading counts as stable once a run of
 * consecutive readings each sit within a band of the one before.  It then
 * stays stable until reset(), so a fast real change later is never hidden.
 *
 * ── Usage ────────────────────────────────────────────────────────────────────
 *
 *   static ReadingStabilizer settled(5, 0.5f);   // 5 readings within 0.5 units
 *
 *   // after each good reading:   settled.update(value);
 *   // after a bad or missing one: settled.reset();
 *   // before reporting:           if (settled.isStable()) { ... }
 */

#pragma once

#include <math.h>
#include <stdint.h>

class ReadingStabilizer {
public:
    /**
     * @param requiredReadings  Consecutive agreeing readings needed; at least 1.
     * @param band              Largest step between neighbours that still agrees.
     */
    ReadingStabilizer(uint8_t requiredReadings, float band)
        : requiredReadings_(requiredReadings < 1 ? 1 : requiredReadings), band_(band) {}

    /**
     * Feed one good reading.
     * @param value The reading.
     * @return true once the readings are stable.
     */
    bool update(float value) {
        if (stable_) {
            return true;
        }
        const bool agrees = runLength_ > 0 && fabsf(value - previous_) <= band_;
        runLength_ = agrees ? static_cast<uint8_t>(runLength_ + 1) : 1;
        previous_  = value;
        stable_    = runLength_ >= requiredReadings_;
        return stable_;
    }

    /** Forget everything; the next readings must settle again. */
    void reset() {
        stable_    = false;
        runLength_ = 0;
    }

    /** Declare the readings stable without waiting (for injected values). */
    void forceStable() {
        stable_ = true;
    }

    /** @return true once the readings have settled. */
    bool isStable() const { return stable_; }

private:
    uint8_t requiredReadings_;
    float   band_;
    float   previous_  = 0.0f;
    uint8_t runLength_ = 0;
    bool    stable_    = false;
};
