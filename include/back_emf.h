/**
 * @file back_emf.h
 * @brief Linear-motor back-EMF estimate and the electrical overstroke detector.
 *
 * Header-only and free of Arduino calls, so the same logic runs on the ESP32
 * and in the native unit tests.
 *
 * Motor model: V = I * (R + j*w*L) + E.  At a fixed drive frequency the
 * back-EMF magnitude |E| is proportional to piston stroke, so a limit on |E|
 * is a stroke limit.  A piston that hits its stop loses velocity, |E| falls
 * and the load impedance V / I drops suddenly, which is the second check.
 *
 * ── Usage ────────────────────────────────────────────────────────────────────
 *
 *   static back_emf::Detector detector(config);
 *
 *   const float emfV = back_emf::estimateVrms(reading, coil, 60.0f, 0.3f);
 *   const auto  trip = detector.update(emfV, voltageV / currentA, nowMs);
 *   if (trip != back_emf::Trip::None) { ... back off the drive ... }
 */

#pragma once

#include <math.h>
#include <stdint.h>

namespace back_emf {

/** Electrical constants of the motor coil. */
struct CoilModel {
    float resistanceOhm;  ///< DC coil resistance
    float inductanceH;    ///< Coil inductance
};

/** One set of power-monitor readings taken over the same line cycle. */
struct Reading {
    float voltageVrms;     ///< RMS drive voltage
    float currentArms;     ///< RMS coil current
    float activePowerW;    ///< Real power; the sign is ignored
    bool  currentLagging;  ///< true = current lags voltage (inductive load)
};

/**
 * Estimates the RMS back-EMF of the motor from one set of readings.
 *
 * With the current as phase reference the drive voltage is
 * (P / I) + j(Q / I); subtracting the coil drop I * (R + j*w*L) leaves E.
 *
 * @param reading       Voltage, current, real power and lead/lag sign.
 * @param coil          Coil resistance and inductance.
 * @param frequencyHz   Drive frequency.
 * @param minCurrentA   Below this current the readings are noise.
 * @return |E| in volts RMS, or NaN when a reading is missing, not finite, or
 *         the current is below @p minCurrentA.
 */
inline float estimateVrms(const Reading& reading, const CoilModel& coil,
                          float frequencyHz, float minCurrentA)
{
    const float voltageV = reading.voltageVrms;
    const float currentA = reading.currentArms;
    if (!isfinite(voltageV) || !isfinite(currentA) || !isfinite(reading.activePowerW) ||
        !isfinite(frequencyHz) || frequencyHz <= 0.0f) {
        return NAN;
    }
    if (currentA < minCurrentA || currentA <= 0.0f || voltageV < 0.0f) {
        return NAN;
    }

    const float apparentVa = voltageV * currentA;
    // Real power can read a step above V * I on single-cycle data; clamp it.
    const float activeW    = fminf(fabsf(reading.activePowerW), apparentVa);
    const float reactiveVar =
        sqrtf(apparentVa * apparentVa - activeW * activeW) * (reading.currentLagging ? 1.0f : -1.0f);

    const float reactanceOhm = 2.0f * static_cast<float>(M_PI) * frequencyHz * coil.inductanceH;
    const float inPhaseV     = activeW / currentA - currentA * coil.resistanceOhm;
    const float quadratureV  = reactiveVar / currentA - currentA * reactanceOhm;
    return sqrtf(inPhaseV * inPhaseV + quadratureV * quadratureV);
}

/** Why the detector tripped. */
enum class Trip : uint8_t {
    None = 0,
    BackEmfLimit,   ///< smoothed back-EMF above the limit
    ImpedanceDrop,  ///< load impedance fell suddenly below its baseline
};

/** @return A short name for @p trip, for log lines. */
inline const char* tripName(Trip trip)
{
    switch (trip) {
        case Trip::BackEmfLimit:  return "back-EMF limit";
        case Trip::ImpedanceDrop: return "impedance drop";
        case Trip::None:          break;
    }
    return "none";
}

/** Detector thresholds and timing.  A threshold of 0 disables that check. */
struct DetectorConfig {
    float    limitVrms;              ///< Trip when smoothed back-EMF exceeds this
    float    impedanceDropFraction;  ///< Trip when impedance falls this fraction below baseline
    uint32_t smoothingMs;            ///< Time constant of the reading filter
    uint32_t baselineMs;             ///< Time constant of the impedance baseline
    uint32_t baselineSettleMs;       ///< Valid readings needed before the impedance check arms
    uint32_t holdoffMs;              ///< Minimum time between two trips
};

/**
 * Smooths the back-EMF estimate and decides when it indicates an overstroke.
 *
 * A missing reading (NaN) resets the filters, so a stale value never stands
 * in for a current one.
 */
class Detector {
public:
    explicit Detector(const DetectorConfig& config) : config_(config) {}

    /**
     * Feed one reading.
     * @param backEmfVrms   Estimate from estimateVrms(), NaN when unavailable.
     * @param impedanceOhm  Load impedance V / I, NaN when unavailable.
     * @param nowMs         Current time in milliseconds.
     * @return The trip raised by this reading, or Trip::None.
     */
    Trip update(float backEmfVrms, float impedanceOhm, uint32_t nowMs)
    {
        if (!isfinite(backEmfVrms) || !isfinite(impedanceOhm)) {
            reset();
            return Trip::None;
        }
        if (!hasReading_) {
            hasReading_       = true;
            firstReadingMs_   = nowMs;
            lastUpdateMs_     = nowMs;
            smoothedVrms_     = backEmfVrms;
            smoothedOhm_      = impedanceOhm;
            baselineOhm_      = impedanceOhm;
            return checkTrip(nowMs);
        }

        const uint32_t elapsedMs = nowMs - lastUpdateMs_;
        if (elapsedMs == 0u) {
            return Trip::None;
        }
        lastUpdateMs_ = nowMs;

        const float smoothingGain = filterGain(elapsedMs, config_.smoothingMs);
        smoothedVrms_ += smoothingGain * (backEmfVrms - smoothedVrms_);
        smoothedOhm_  += smoothingGain * (impedanceOhm - smoothedOhm_);

        const Trip trip = checkTrip(nowMs);
        // The baseline follows after the check, so a sudden drop is compared
        // against the impedance from before it.
        baselineOhm_ += filterGain(elapsedMs, config_.baselineMs) * (smoothedOhm_ - baselineOhm_);
        return trip;
    }

    /** Forget all readings; the filters start again from the next one. */
    void reset()
    {
        hasReading_   = false;
        smoothedVrms_ = NAN;
        smoothedOhm_  = NAN;
        baselineOhm_  = NAN;
    }

    /**
     * Sets a temporary limit for testing.  It can only make the detector
     * stricter: the lower of this and the configured limit applies.
     * @param limitVrms Test limit in volts RMS; 0 or less removes it.
     */
    void setTestLimitVrms(float limitVrms)
    {
        testLimitVrms_ = (isfinite(limitVrms) && limitVrms > 0.0f) ? limitVrms : 0.0f;
    }

    /** @return The limit in force (0 = the back-EMF limit check is off). */
    float effectiveLimitVrms() const
    {
        if (testLimitVrms_ <= 0.0f)    { return config_.limitVrms; }
        if (config_.limitVrms <= 0.0f) { return testLimitVrms_; }
        return fminf(testLimitVrms_, config_.limitVrms);
    }

    /** @return Smoothed back-EMF in volts RMS, NaN when there is no reading. */
    float smoothedVrms() const { return smoothedVrms_; }

    /** @return Smoothed load impedance in ohms, NaN when there is no reading. */
    float smoothedImpedanceOhm() const { return smoothedOhm_; }

    /** @return Impedance baseline in ohms, NaN when there is no reading. */
    float baselineImpedanceOhm() const { return baselineOhm_; }

private:
    static float filterGain(uint32_t elapsedMs, uint32_t timeConstantMs)
    {
        const float elapsed = static_cast<float>(elapsedMs);
        return elapsed / (static_cast<float>(timeConstantMs) + elapsed);
    }

    Trip checkTrip(uint32_t nowMs)
    {
        if (hasTripped_ && (nowMs - lastTripMs_) < config_.holdoffMs) {
            return Trip::None;
        }

        Trip trip = Trip::None;
        const float limitVrms = effectiveLimitVrms();
        const bool  baselineArmed = (nowMs - firstReadingMs_) >= config_.baselineSettleMs;
        if (limitVrms > 0.0f && smoothedVrms_ > limitVrms) {
            trip = Trip::BackEmfLimit;
        } else if (config_.impedanceDropFraction > 0.0f && baselineArmed &&
                   smoothedOhm_ < baselineOhm_ * (1.0f - config_.impedanceDropFraction)) {
            trip = Trip::ImpedanceDrop;
        }

        if (trip != Trip::None) {
            hasTripped_ = true;
            lastTripMs_ = nowMs;
        }
        return trip;
    }

    DetectorConfig config_;
    float    testLimitVrms_  = 0.0f;
    bool     hasReading_     = false;
    bool     hasTripped_     = false;
    uint32_t firstReadingMs_ = 0u;
    uint32_t lastUpdateMs_   = 0u;
    uint32_t lastTripMs_     = 0u;
    float    smoothedVrms_   = NAN;
    float    smoothedOhm_    = NAN;
    float    baselineOhm_    = NAN;
};

} // namespace back_emf
