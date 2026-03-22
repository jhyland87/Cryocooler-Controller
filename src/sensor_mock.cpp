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
    RampSpec& r = sRamps[idx];
    r.active     = true;
    r.startVal   = startVal;
    r.endVal     = endVal;
    r.ratePerMin = ratePerMin;
    r.startMs    = nowMs;

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
    for (auto& r : sRamps) { r.active = false; }
}

const RampSpec& getRamp(RampField field)
{
    return sRamps[static_cast<uint8_t>(field)];
}

// ── service() ─────────────────────────────────────────────────────────────────

/**
 * Apply one active ramp at index @p idx, writing to @p current.
 * Returns true if the ramp is still running, false if it completed.
 *
 * @param r        The ramp spec (modified in place when completed).
 * @param nowMs    Current millis().
 * @param current  [out] Updated value for this tick.
 */
static bool applyRamp(RampSpec& r, float& current)
{
    if (!r.active) return false;

    const float elapsedMin = static_cast<float>(tick::nowMs() - r.startMs) / 60000.0f;
    const float direction  = (r.endVal >= r.startVal) ? 1.0f : -1.0f;
    const float projected  = r.startVal + direction * r.ratePerMin * elapsedMin;

    // Check whether the ramp has reached (or overshot) the end value.
    const bool done = (direction > 0.0f) ? (projected >= r.endVal)
                                         : (projected <= r.endVal);
    if (done) {
        current  = r.endVal;
        r.active = false;
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
        RampSpec& r = sRamps[static_cast<uint8_t>(RampField::Temp)];
        if (r.active) {
            const float direction  = (r.endVal >= r.startVal) ? 1.0f : -1.0f;
            applyRamp(r, sOverrides.tempC);
            // Auto-derive coolingRate: positive = temperature dropping.
            // A downward ramp (direction == -1) means the stage is cooling;
            // by convention coolingRate > 0 when temperature is falling.
            sOverrides.coolingRate = -direction * r.ratePerMin;
        }
    }

    // ── RMS voltage ramp ─────────────────────────────────────────────────────
    {
        RampSpec& r = sRamps[static_cast<uint8_t>(RampField::Rms)];
        if (r.active) {
            applyRamp(r, sOverrides.rmsVoltageV);
        }
    }

    // ── Supply voltage ramp ───────────────────────────────────────────────────
    {
        RampSpec& r = sRamps[static_cast<uint8_t>(RampField::Voltage)];
        if (r.active) {
            applyRamp(r, sOverrides.voltage);
        }
    }
}

} // namespace sensor_mock
