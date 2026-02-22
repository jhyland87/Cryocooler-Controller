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
 * Hardware note (ACS712-05B supply voltage and ADC attenuation):
 *
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
 *   to ACS712_CURRENT_PIN before sensor.autoMidPoint() so the zero-offset
 *   calibration always uses the same range as the live readings.
 */

#ifdef ARDUINO
#  include <Arduino.h>
#  include <ACS712.h>
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
static float    currentA         = 0.0f;   // latest ACS712 reading
static float    currentEmaA      = 0.0f;   // EMA baseline of AC current
static uint8_t  primeCount       = 0;      // readings collected so far for priming
static bool     overstrokeFlag   = false;  // set on spike; cleared by caller
static uint32_t lastOverstrokeMs = 0;      // timestamp of most recent event

#ifdef ARDUINO
// RobTillaart ACS712 — 5 A sensor on ESP32-S3 (3.3 V supply, 12-bit ADC).
// Constructor: (analogPin, volts, maxADC, mVperAmpere)
static ACS712 sensor(ACS712_CURRENT_PIN,
                      ACS712_ADC_VOLTS,
                      ACS712_ADC_MAX_VALUE,
                      ACS712_SENSITIVITY_MV_PER_A);
#endif

namespace rms {

void init() {
    voltage          = 0.0f;
    currentA         = 0.0f;
    currentEmaA      = 0.0f;
    primeCount       = 0;
    overstrokeFlag   = false;
    lastOverstrokeMs = 0;

#ifdef ARDUINO
    // Set ADC input attenuation BEFORE autoMidPoint() so that calibration
    // samples are captured using the same full-scale range as live readings.
    // See config.h for available choices and voltage/resolution trade-offs.
    analogSetPinAttenuation(ACS712_CURRENT_PIN, ACS712_ADC_ATTENUATION);

    // Auto-calibrate the zero-current midpoint over one full AC cycle.
    // The AC output MUST be off (zero load current) when this is called.
    // Blocks ~2 cycles (~33 ms at AD9833_FREQ_HZ = 60 Hz) — acceptable
    // during initialisation; not an issue for the main loop.
    sensor.autoMidPoint(AD9833_FREQ_HZ, 1);
#endif
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
    // mA_AC_sampling computes true RMS via Σ(sample²) over one full cycle
    // (~16.7 ms at 60 Hz).  This is more robust than mA_AC() for compressor
    // loads whose current waveform may deviate from a pure sine.  The blocking
    // duration is bounded and predictable — not an arbitrary delay().
    // Result is in milliamps; divide by 1000 to convert to amps.
    const float current = sensor.mA_AC_sampling(AD9833_FREQ_HZ, 1) / 1000.0f;
    currentA = current;

    // Prime phase: seed the EMA with direct readings so the baseline
    // converges quickly and spike detection is not armed prematurely.
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
