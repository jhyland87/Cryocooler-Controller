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

static constexpr uint8_t LED_COUNT = 1;

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static CRGB leds[LED_COUNT];

static indicator::Mode faultMode = indicator::Mode::Off;
static indicator::Mode readyMode = indicator::Mode::Off;

// Per-indicator flash state
static bool     faultLedOn   = false;
static bool     readyLedOn   = false;
static uint32_t faultLastMs  = 0;
static uint32_t readyLastMs  = 0;

// Cached result of last update() — used by isFaultOn() / isReadyOn()
static bool     faultOnCached = false;
static bool     readyOnCached = false;

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
    FastLED.addLeds<WS2812, STATUS_LED_PIN, GRB>(leds, LED_COUNT);
    FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
    leds[0] = CRGB::Black;
    FastLED.show();

    // Discrete indicator pins
    pinMode(FAULT_IND_PIN, OUTPUT);
    pinMode(READY_IND_PIN, OUTPUT);
    digitalWrite(FAULT_IND_PIN, LOW);
    digitalWrite(READY_IND_PIN, LOW);
}

void setFaultMode(Mode mode) {
    if (mode != faultMode) {
        faultMode  = mode;
        faultLedOn = false;
        faultLastMs = 0;
    }
}

void setReadyMode(Mode mode) {
    if (mode != readyMode) {
        readyMode  = mode;
        readyLedOn = false;
        readyLastMs = 0;
    }
}

void update(uint32_t nowMs) {
    const bool faultOn = evalMode(faultMode, faultLedOn, faultLastMs, nowMs);
    const bool readyOn = evalMode(readyMode, readyLedOn, readyLastMs, nowMs);

    // Cache for isFaultOn() / isReadyOn()
    faultOnCached = faultOn;
    readyOnCached = readyOn;

    // Discrete LEDs (active HIGH)
    digitalWrite(FAULT_IND_PIN, faultOn ? HIGH : LOW);
    digitalWrite(READY_IND_PIN, readyOn ? HIGH : LOW);

    // WS2812 — blend fault and ready colours
    CRGB colour = CRGB::Black;
    if (faultOn && readyOn) {
        // Both active simultaneously: show amber
        colour = CRGB(255, 80, 0);
    } else if (faultOn) {
        colour = modeToColour(faultMode);
    } else if (readyOn) {
        colour = modeToColour(readyMode);
    }

    leds[0] = colour;
    FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
    FastLED.show();
}

bool isFaultOn() {
    return faultOnCached;
}

bool isReadyOn() {
    return readyOnCached;
}

} // namespace indicator
