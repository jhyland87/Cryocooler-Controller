/**
 * @file indicator.cpp
 * @brief FAULT and READY indicator implementation
 *
 * Uses the on-board WS2812 LED (STATUS_LED_PIN) to display a combined
 * FAULT + READY colour, and optional discrete digital outputs on
 * FAULT_IND_PIN / READY_IND_PIN.
 *
 * Flash timing is non-blocking (state-machine style).
 */

#include <Arduino.h>
#include <FastLED.h>

#include "pin_config.h"
#include "config.h"
#include "indicator.h"

// ---------------------------------------------------------------------------
// Module constants
// ---------------------------------------------------------------------------

static constexpr uint8_t kLedCount = 1;

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static CRGB sLeds[kLedCount];

static indicator::Mode sFaultMode = indicator::Mode::Off;
static indicator::Mode sReadyMode = indicator::Mode::Off;

// Per-indicator flash state
static bool     sFaultLedOn   = false;
static bool     sReadyLedOn   = false;
static uint32_t sFaultLastMs  = 0;
static uint32_t sReadyLastMs  = 0;

// Cached result of last update() — used by isFaultOn() / isReadyOn()
static bool     sFaultOnCached = false;
static bool     sReadyOnCached = false;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Evaluate one indicator's state and return whether the LED should be on
 * for this tick.  Updates the toggle state when the period elapses.
 */
static bool evalMode(indicator::Mode    mode,
                     bool&              ledOn,
                     uint32_t&          lastMs,
                     uint32_t           nowMs)
{
    using Mode = indicator::Mode;
    switch (mode) {
        case Mode::Off:
            return false;

        case Mode::SolidRed:
        case Mode::SolidGreen:
        case Mode::SolidAmber:
            return true;

        case Mode::FlashFastRed:
        case Mode::FlashFastGreen: {
            const uint32_t half = INDICATOR_FLASH_FAST_PERIOD_MS / 2;
            if ((nowMs - lastMs) >= half) {
                lastMs = nowMs;
                ledOn = !ledOn;
            }
            return ledOn;
        }

        case Mode::FlashSlowRed:
        case Mode::FlashSlowGreen: {
            const uint32_t half = INDICATOR_FLASH_SLOW_PERIOD_MS / 2;
            if ((nowMs - lastMs) >= half) {
                lastMs = nowMs;
                ledOn = !ledOn;
            }
            return ledOn;
        }
    }
    return false;
}

/**
 * Return the colour component of a mode (ignoring flash/solid).
 */
static CRGB modeToColour(indicator::Mode mode) {
    using Mode = indicator::Mode;
    switch (mode) {
        case Mode::SolidRed:
        case Mode::FlashFastRed:
        case Mode::FlashSlowRed:
            return CRGB::Red;

        case Mode::SolidGreen:
        case Mode::FlashFastGreen:
        case Mode::FlashSlowGreen:
            return CRGB::Green;

        case Mode::SolidAmber:
            return CRGB(255, 80, 0);   // Orange-amber

        default:
            return CRGB::Black;
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace indicator {

void init() {
    FastLED.addLeds<WS2812, STATUS_LED_PIN, GRB>(sLeds, kLedCount);
    FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
    sLeds[0] = CRGB::Black;
    FastLED.show();

    // Discrete indicator pins
    pinMode(FAULT_IND_PIN, OUTPUT);
    pinMode(READY_IND_PIN, OUTPUT);
    digitalWrite(FAULT_IND_PIN, LOW);
    digitalWrite(READY_IND_PIN, LOW);
}

void setFaultMode(Mode mode) {
    if (mode != sFaultMode) {
        sFaultMode  = mode;
        sFaultLedOn = false;
        sFaultLastMs = 0;
    }
}

void setReadyMode(Mode mode) {
    if (mode != sReadyMode) {
        sReadyMode  = mode;
        sReadyLedOn = false;
        sReadyLastMs = 0;
    }
}

void update(uint32_t nowMs) {
    const bool faultOn = evalMode(sFaultMode, sFaultLedOn, sFaultLastMs, nowMs);
    const bool readyOn = evalMode(sReadyMode, sReadyLedOn, sReadyLastMs, nowMs);

    // Cache for isFaultOn() / isReadyOn()
    sFaultOnCached = faultOn;
    sReadyOnCached = readyOn;

    // Discrete LEDs (active HIGH)
    digitalWrite(FAULT_IND_PIN, faultOn ? HIGH : LOW);
    digitalWrite(READY_IND_PIN, readyOn ? HIGH : LOW);

    // WS2812 — blend fault and ready colours
    CRGB colour = CRGB::Black;
    if (faultOn && readyOn) {
        // Both active simultaneously: show amber
        colour = CRGB(255, 80, 0);
    } else if (faultOn) {
        colour = modeToColour(sFaultMode);
    } else if (readyOn) {
        colour = modeToColour(sReadyMode);
    }

    sLeds[0] = colour;
    FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
    FastLED.show();
}

bool isFaultOn() {
    return sFaultOnCached;
}

bool isReadyOn() {
    return sReadyOnCached;
}

} // namespace indicator
