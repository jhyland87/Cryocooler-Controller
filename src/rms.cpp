/**
 * @file rms.cpp
 * @brief AC voltage and current monitoring — RMS stub + ACS712 implementation.
 *
 * ── Overstroke detection algorithm ──────────────────────────────────────────
 * An exponential moving average (EMA) tracks the "normal" AC RMS current.
 * A reading is classified as an overstroke spike when:
 *
 *   instantaneous_current > ema_baseline + OVERSTROKE_CURRENT_THRESHOLD_A
 *   AND (millis() - last_event_ms) >= OVERSTROKE_DEBOUNCE_MS
 *   AND the EMA has been primed for OVERSTROKE_PRIME_READINGS ticks.
 *
 * The small EMA alpha (OVERSTROKE_EMA_ALPHA) means the baseline tracks the
 * slowly-evolving steady-state current while brief spikes stand out clearly.
 *
 * ── ACS712 measurement ──────────────────────────────────────────────────────
 * The custom ContinuousZMCT103C library is used in continuous-RMS mode.
 * updateContinuousRMS() is called every loop tick; it samples the ADC,
 * updates an EMA of mean and mean-square, and returns in microseconds.
 * There is no blocking wait — sampling is spread across loop iterations.
 *
 * Mean-centering (useMeanCenter = true, the default) computes RMS relative
 * to the running mean, so no explicit midpoint calibration is required and
 * the result is robust against supply-voltage drift.
 *
 * ── Hardware note (ACS712-05B supply voltage and ADC attenuation) ────────────
 *   Option A — 3.3 V supply (recommended):
 *     Power the ACS712 from the ESP32's 3.3 V rail.  The output then spans
 *     ~0.33 V – 2.97 V (zero-current = 1.65 V, sensitivity ~122 mV/A).
 *     Use ADC_11db (0–3.3 V) for the full 5 A range, or ADC_6db (0–2.2 V)
 *     for ~45 % better resolution at the cost of clipping above ~4.5 A.
 *     Update ACS712_SENSITIVITY_MV_PER_A to 122 in config.h.
 *
 *   Option B — 5 V supply with voltage divider:
 *     Sensor output spans 0.5 V – 4.5 V.  A 3.3 kΩ / 6.8 kΩ divider
 *     (ratio ≈ 0.674) scales this to 0.34 V – 3.03 V → use ADC_11db.
 *     ADC_6db clips at 2.2 V (≈ 4.1 A) but gives better spike resolution.
 *
 *   The attenuation constant ACS712_ADC_ATTENUATION (config.h) is applied
 *   to ACS712_CURRENT_PIN in init() before the sensor is started.
 */

#ifdef ARDUINO
#  include <Arduino.h>
#  include "ContinuousZMCT103C.h"
#else
// Native (host-PC) build: Arduino.h stub provides millis().
#  include "Arduino.h"
#endif

#include "rms.h"
#include "config.h"
#include "pin_config.h"

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static float    voltage          = 0.0f;   // RMS voltage (stub, always 0)
static float    currentA         = 0.0f;   // latest ACS712 reading in amps
static float    currentEmaA      = 0.0f;   // slow-tracking EMA for overstroke baseline
static uint8_t  primeCount       = 0;      // readings collected for EMA priming
static bool     overstrokeFlag   = false;  // set on spike; cleared by caller
static uint32_t lastOverstrokeMs = 0;      // timestamp of most recent event

#ifdef ARDUINO
// ContinuousZMCT103C — 5 A sensor on ESP32-S3 (3.3 V supply, 12-bit ADC).
// Mean-centering is on by default: the running mean tracks the zero-current
// offset automatically, so no explicit midpoint calibration is required.
// Constructor: (analogPin, volts, maxADC, mVperAmpere)
static ContinuousZMCT103C sensor(ACS712_CURRENT_PIN,
                                  ACS712_ADC_VOLTS,
                                  ACS712_ADC_MAX_VALUE,
                                  ACS712_SENSITIVITY_MV_PER_A);
#endif

namespace rms {

module::InitStatus init() {
    voltage          = 0.0f;
    currentA         = 0.0f;
    currentEmaA      = 0.0f;
    primeCount       = 0;
    overstrokeFlag   = false;
    lastOverstrokeMs = 0;

#ifdef ARDUINO
    // ESP32 Arduino 3.x (ESP-IDF 5.x) uses lazy ADC unit initialisation —
    // the oneshot driver handle for an ADC unit is only created on the first
    // analogRead() for a pin in that unit.  analogSetPinAttenuation() requires
    // the unit to already be open, so we do a priming read here to open the
    // ADC2 handle before configuring attenuation.  The discarded value is fine
    // since the EMA in readCurrent() absorbs the first OVERSTROKE_PRIME_READINGS
    // samples regardless.
    (void)analogRead(ACS712_CURRENT_PIN);

    // Set ADC input attenuation so that all samples use the same full-scale
    // range as live readings.  See config.h for the available choices.
    analogSetPinAttenuation(ACS712_CURRENT_PIN, ACS712_ADC_ATTENUATION);

    // Start continuous non-blocking RMS mode.
    // Default tau = 250 ms, minSampleIntervalUs = 200 µs.
    // Mean-centering handles zero-current offset drift; no calibration needed.
    sensor.beginContinuousRMS();
#endif
    return module::MODULE_INIT_SUCCESS;
}

void read() {
    // TODO: implement RMS-to-DC converter ADC read.
    voltage = 0.0f;
}

float getVoltage() {
    return voltage;
}

void readCurrent() {
#ifdef ARDUINO
    // Tick the continuous EMA — returns immediately (< 50 µs) if the minimum
    // sample interval has not yet elapsed; no blocking wait.
    sensor.updateContinuousRMS();

    // continuousmA() returns milliamps; convert to amps.
    const float current = sensor.continuousmA() / 1000.0f;
    currentA = current;

    // Prime phase: seed the overstroke EMA baseline with the first few
    // readings so spike detection is not armed prematurely.
    if (primeCount < OVERSTROKE_PRIME_READINGS) {
        currentEmaA = current;
        ++primeCount;
        return;
    }

    // Update EMA baseline (slow-tracking, small alpha keeps transients visible).
    currentEmaA += OVERSTROKE_EMA_ALPHA * (current - currentEmaA);

    // Spike check: fire if delta exceeds threshold AND debounce has elapsed.
    const float    delta = current - currentEmaA;
    const uint32_t now   = millis();

    if (!overstrokeFlag &&
        delta   > OVERSTROKE_CURRENT_THRESHOLD_A &&
        (now - lastOverstrokeMs) >= OVERSTROKE_DEBOUNCE_MS) {
        overstrokeFlag   = true;
        lastOverstrokeMs = now;
    }
#endif
    // Native build: no-op — state remains 0 A, no spurious overstrokes.
}

float getCurrentA() {
    return currentA;
}

bool hasOverstroke() {
    return overstrokeFlag;
}

void clearOverstroke() {
    overstrokeFlag = false;
}

} // namespace rms
