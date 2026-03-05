/**
 * @file tracking.h
 * @brief Generic setpoint-tracking monitor for module output values.
 *
 * TrackingMonitor<T> compares a measured value against a setpoint and:
 *
 *   - Computes a score (1.0 = perfect match, 0.0 = deviation >= fullScale).
 *   - Enters WARNING after the value stays outside the hysteresis band for
 *     warningDelayMs milliseconds.
 *   - Escalates to FAULT after faultDelayMs milliseconds.
 *   - Returns to IN_RANGE immediately when the value re-enters the band.
 *   - Logs once per state transition (ESP_LOGI on recovery, ESP_LOGW for
 *     WARNING, ESP_LOGE for FAULT).
 *
 * ── Usage ────────────────────────────────────────────────────────────────────
 *
 *   // In your module .cpp, at file scope:
 *   static TrackingMonitor<float> myTracker_(TrackingMonitor<float>::Config{
 *       MY_HYSTERESIS,
 *       MY_FULL_SCALE,
 *       MY_WARNING_MS,
 *       MY_FAULT_MS,
 *       "my_module",    // ESP_LOG tag
 *       "temperature",  // value label for log messages
 *   });
 *
 *   // In service() or read():
 *   myTracker_.update(setpoint, measured, nowMs);
 *
 *   // In getters:
 *   float score = myTracker_.getScore();   // 0.0–1.0
 *   bool  ok    = myTracker_.isInRange();
 *
 * ── State machine ─────────────────────────────────────────────────────────────
 *
 *   setpoint ± hysteresis = deadband.
 *
 *   IN_RANGE ──(leaves band)──► WARNING ──(faultDelayMs)──► FAULT
 *      ▲                           │
 *      └─────────(re-enters band)──┘
 *
 *   State resets to IN_RANGE immediately when the value returns to the band.
 *   Call reset() explicitly when the setpoint changes significantly so the
 *   timer does not inherit stale elapsed time from the previous target.
 */

#pragma once

#include <stdint.h>
#include <math.h>
#include <inttypes.h>
#include "esp_log.h"

template<typename T>
class TrackingMonitor {
public:
    /** Tracking state — normal, deviating, or faulted. */
    enum class State : uint8_t {
        IN_RANGE,  ///< |error| <= hysteresis — value is on target
        WARNING,   ///< |error| > hysteresis for >= warningDelayMs
        FAULT,     ///< |error| > hysteresis for >= faultDelayMs
    };

    /** Per-instance configuration. All fields must be set. */
    struct Config {
        T           hysteresis;      ///< Acceptable deviation from setpoint (deadband half-width)
        T           fullScale;       ///< Deviation at which the score reaches 0.0
        uint32_t    warningDelayMs;  ///< Continuous out-of-band time (ms) before WARNING
        uint32_t    faultDelayMs;    ///< Continuous out-of-band time (ms) before FAULT
        const char* tag;             ///< ESP_LOG tag (must be a static string literal)
        const char* label;           ///< Value label used in log messages (e.g. "temperature")
    };

    explicit TrackingMonitor(Config cfg) : cfg_(cfg) {}

    /**
     * Advance the monitor with new measurement data.
     * Call once per service() / read() tick.
     *
     * @param setpoint  Target value.
     * @param measured  Current measured value.
     * @param nowMs     Current millis() timestamp.
     */
    void update(T setpoint, T measured, uint32_t nowMs) {
        const float error  = fabsf(static_cast<float>(measured)
                                  - static_cast<float>(setpoint));
        lastError_         = error;
        const bool  inBand = (error <= static_cast<float>(cfg_.hysteresis));

        if (inBand) {
            if (outOfBand_) {
                ESP_LOGI(cfg_.tag,
                         "[track] %s back within tolerance "
                         "(error=%.3f, hysteresis=%.3f)",
                         cfg_.label, error,
                         static_cast<float>(cfg_.hysteresis));
            }
            outOfBand_        = false;
            outOfBandSinceMs_ = 0u;
            state_            = State::IN_RANGE;
            return;
        }

        // First tick out of band — start the timer.
        if (!outOfBand_) {
            outOfBand_        = true;
            outOfBandSinceMs_ = nowMs;
        }

        const uint32_t elapsed = nowMs - outOfBandSinceMs_;
        const State    prev    = state_;

        if (elapsed >= cfg_.faultDelayMs) {
            state_ = State::FAULT;
        } else if (elapsed >= cfg_.warningDelayMs) {
            state_ = State::WARNING;
        }

        // Log once per upward state transition.
        if (state_ != prev) {
            if (state_ == State::FAULT) {
                ESP_LOGE(cfg_.tag,
                         "[track] %s FAULT — out of band for %" PRIu32 " ms "
                         "(error=%.3f, setpoint=%.3f, measured=%.3f)",
                         cfg_.label, elapsed, error,
                         static_cast<float>(setpoint),
                         static_cast<float>(measured));
            } else if (state_ == State::WARNING) {
                ESP_LOGW(cfg_.tag,
                         "[track] %s WARNING — deviating for %" PRIu32 " ms "
                         "(error=%.3f, setpoint=%.3f, measured=%.3f)",
                         cfg_.label, elapsed, error,
                         static_cast<float>(setpoint),
                         static_cast<float>(measured));
            }
        }
    }

    /**
     * Reset to IN_RANGE and clear the out-of-band timer.
     *
     * Call whenever the setpoint changes significantly so the elapsed time
     * does not carry over from the previous target, or when the module is
     * in a state where tracking is not meaningful (e.g. LUT-controlled fan).
     */
    void reset() {
        state_            = State::IN_RANGE;
        outOfBand_        = false;
        outOfBandSinceMs_ = 0u;
        lastError_        = 0.0f;
    }

    /**
     * Tracking score: 1.0 = perfectly on target, 0.0 = error >= fullScale.
     * Clamped to [0.0, 1.0].
     */
    float getScore() const {
        const float norm = lastError_ / static_cast<float>(cfg_.fullScale);
        return (norm >= 1.0f) ? 0.0f : (1.0f - norm);
    }

    State getState()  const { return state_;                    }
    bool  isInRange() const { return state_ == State::IN_RANGE; }
    bool  isWarning() const { return state_ == State::WARNING;  }
    bool  isFault()   const { return state_ == State::FAULT;    }

    /** Absolute deviation from setpoint on the most recent update() call. */
    float getError()  const { return lastError_;                }

private:
    Config   cfg_;
    State    state_            = State::IN_RANGE;
    bool     outOfBand_        = false;
    uint32_t outOfBandSinceMs_ = 0u;
    float    lastError_        = 0.0f;
};
