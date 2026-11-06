/**
 * @file sensor_mock.cpp
 * @brief Runtime sensor override layer — implementation.
 */

#include "sensor_mock.h"
#include "tick.h"

namespace sensor_mock {

static bool      sActive    = false;
static Overrides sOverrides = {};   // value-initialised to safe defaults

// One RampSpec per rampable field.
static RampSpec sRamps[static_cast<uint8_t>(RampField::Count)] = {};

// ── Core API ─────────────────────────────────────────────────────────────────

void enable()  { sActive = true;  }
void disable() { sActive = false; }
bool isActive(){ return sActive;  }

Overrides& get() { return sOverrides; }

// ── Ramp API ──────────────────────────────────────────────────────────────────

void startRamp(RampField field,
               float startVal, float endVal, float ratePerMin)
{
    const uint32_t nowMs = tick::nowMs();
    const auto idx = static_cast<uint8_t>(field);
    RampSpec& ramp = sRamps[idx];
    ramp.active     = true;
    ramp.startVal   = startVal;
    ramp.endVal     = endVal;
    ramp.ratePerMin = ratePerMin;
    ramp.startMs    = nowMs;

    // Snap the override to the start value immediately so the FSM doesn't
    // see a stale value on the very first tick.
    switch (field) {
        case RampField::Temp:    sOverrides.tempC      = startVal; break;
        case RampField::Rms:     sOverrides.rmsVoltageV = startVal; break;
        case RampField::Voltage: sOverrides.voltage   = startVal; break;
        default: break;
    }
}

void stopRamp(RampField field)
{
    sRamps[static_cast<uint8_t>(field)].active = false;
}

void stopAllRamps()
{
    for (auto& ramp : sRamps) { ramp.active = false; }
}

const RampSpec& getRamp(RampField field)
{
    return sRamps[static_cast<uint8_t>(field)];
}

// ── service() ─────────────────────────────────────────────────────────────────

/**
 * Apply one active ramp, writing the interpolated value to @p current.
 * Returns true if the ramp is still running, false if it completed.
 *
 * @param ramp        The ramp spec (modified in place when completed).
 * @param current  [out] Updated value for this tick.
 */
static bool applyRamp(RampSpec& ramp, float& current)
{
    if (!ramp.active) return false;

    const float elapsedMin = static_cast<float>(tick::nowMs() - ramp.startMs) / 6e4f;
    const float direction  = (ramp.endVal >= ramp.startVal) ? 1.0f : -1.0f;
    const float projected  = ramp.startVal + direction * ramp.ratePerMin * elapsedMin;

    // Check whether the ramp has reached (or overshot) the end value.
    const bool done = (direction > 0.0f) ? (projected >= ramp.endVal)
                                         : (projected <= ramp.endVal);
    if (done) {
        current  = ramp.endVal;
        ramp.active = false;
        return false;  // ramp completed
    }

    current = projected;
    return true;  // ramp still running
}

void service()
{
    if (!sActive) return;

    // ── Temp ramp ────────────────────────────────────────────────────────────
    {
        RampSpec& ramp = sRamps[static_cast<uint8_t>(RampField::Temp)];
        if (ramp.active) {
            const float direction  = (ramp.endVal >= ramp.startVal) ? 1.0f : -1.0f;
            applyRamp(ramp, sOverrides.tempC);
            // Auto-derive coolingRate: positive = temperature dropping.
            // A downward ramp (direction == -1) means the stage is cooling;
            // by convention coolingRate > 0 when temperature is falling.
            sOverrides.coolingRate = -direction * ramp.ratePerMin;
        }
    }

    // ── RMS voltage ramp ─────────────────────────────────────────────────────
    {
        RampSpec& ramp = sRamps[static_cast<uint8_t>(RampField::Rms)];
        if (ramp.active) {
            applyRamp(ramp, sOverrides.rmsVoltageV);
        }
    }

    // ── Supply voltage ramp ───────────────────────────────────────────────────
    {
        RampSpec& ramp = sRamps[static_cast<uint8_t>(RampField::Voltage)];
        if (ramp.active) {
            applyRamp(ramp, sOverrides.voltage);
        }
    }
}

} // namespace sensor_mock
