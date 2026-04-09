/**
 * @file indicator.cpp
 * @brief FAULT and READY indicator implementation
 *
 * Uses the on-board WS2812 LED (STATUS_LED_PIN) to display a combined
 * FAULT + READY colour, and optional discrete digital outputs on
 * FAULT_IND_PIN / READY_IND_PIN.
 *
 * Flash timing is non-blocking (state-machine style).
 * LED output uses rgbLedWrite() from the ESP32 Arduino core — no external
 * library required.
 */

#include <Arduino.h>

#include "pin_config.h"
#include "config.h"
#include "indicator.h"
#include "tick.h"

// rgbLedWrite() was introduced in Arduino Core 3.x.  Core 2.x provides the
// identical function under the name neopixelWrite() (same signature, same
// RMT-based WS2812 implementation).
#if ESP_ARDUINO_VERSION_MAJOR < 3
#define rgbLedWrite neopixelWrite
#endif

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

struct RgbColor {
    uint8_t r;
    uint8_t g;
    uint8_t b;
};

// ---------------------------------------------------------------------------
// Module constants
// ---------------------------------------------------------------------------

static constexpr RgbColor COLOR_OFF     = {   0,   0,   0 };
static constexpr RgbColor COLOR_RED     = { 255,   0,   0 };
static constexpr RgbColor COLOR_GREEN   = {   0, 255,   0 };
static constexpr RgbColor COLOR_AMBER   = { 255,  80,   0 };
static constexpr RgbColor COLOR_YELLOW  = { 255,  255,  0 };
static constexpr RgbColor COLOR_BLUE    = {   0,   0, 255 };
static constexpr RgbColor COLOR_PURPLE  = { 128,   0, 128 };
static constexpr RgbColor COLOR_CYAN    = {   0, 255, 255 };
static constexpr RgbColor COLOR_MAGENTA = { 255,   0, 255 };
static constexpr RgbColor COLOR_WHITE   = { 255, 255, 255 };

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static indicator::Mode faultMode = indicator::Mode::Off;
static indicator::Mode readyMode = indicator::Mode::Off;

// Per-indicator flash state
static bool     faultLedOn  = false;
static bool     readyLedOn  = false;
static uint32_t faultLastMs = 0;
static uint32_t readyLastMs = 0;

// Cached result of last update() — used by isFaultOn() / isReadyOn()
static bool faultOnCached = false;
static bool readyOnCached = false;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static inline uint8_t applyBrightness(uint8_t channel)
{
    return static_cast<uint8_t>(
        (static_cast<uint16_t>(channel) * WAVE_STATUS_LED_BRIGHTNESS) / 255u
    );
}

static void writeLed(const RgbColor& color)
{
    rgbLedWrite(STATUS_LED_PIN,
                applyBrightness(color.r),
                applyBrightness(color.g),
                applyBrightness(color.b));
}

/**
 * Evaluate one indicator's state and return whether the LED should be on
 * for this tick.  Updates the toggle state when the period elapses.
 */
static bool evalMode(indicator::Mode mode,
                     bool&           ledOn,
                     uint32_t&       lastMs,
                     uint32_t        nowMs)
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
                ledOn  = !ledOn;
            }
            return ledOn;
        }

        case Mode::FlashSlowRed:
        case Mode::FlashSlowGreen: {
            const uint32_t half = INDICATOR_FLASH_SLOW_PERIOD_MS / 2;
            if ((nowMs - lastMs) >= half) {
                lastMs = nowMs;
                ledOn  = !ledOn;
            }
            return ledOn;
        }
    }
    return false;
}

/**
 * Return the colour associated with a mode (ignoring flash/solid distinction).
 */
static RgbColor modeToColour(indicator::Mode mode)
{
    using Mode = indicator::Mode;
    switch (mode) {
        case Mode::SolidRed:
        case Mode::FlashFastRed:
        case Mode::FlashSlowRed:
            return COLOR_RED;

        case Mode::SolidGreen:
        case Mode::FlashFastGreen:
        case Mode::FlashSlowGreen:
            return COLOR_GREEN;

        case Mode::SolidAmber:
            return COLOR_AMBER;

        default:
            return COLOR_OFF;
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace indicator {

module::InitStatus init()
{
    // rgbLedWrite() initialises the RMT channel on first call — no explicit
    // setup required beyond the call itself.
    writeLed(COLOR_OFF);

    pinMode(FAULT_IND_PIN, OUTPUT);
    pinMode(READY_IND_PIN, OUTPUT);
    digitalWrite(FAULT_IND_PIN, LOW);
    digitalWrite(READY_IND_PIN, LOW);
    return module::MODULE_INIT_SUCCESS;
}

void setFaultMode(Mode mode)
{
    if (mode != faultMode) {
        faultMode  = mode;
        faultLedOn = false;
        faultLastMs = 0;
    }
}

void setReadyMode(Mode mode)
{
    if (mode != readyMode) {
        readyMode  = mode;
        readyLedOn = false;
        readyLastMs = 0;
    }
}

void update()
{
    const uint32_t nowMs = tick::nowMs();
    const bool faultOn = evalMode(faultMode, faultLedOn, faultLastMs, nowMs);
    const bool readyOn = evalMode(readyMode, readyLedOn, readyLastMs, nowMs);

    faultOnCached = faultOn;
    readyOnCached = readyOn;

    // Discrete LEDs (active HIGH)
    digitalWrite(FAULT_IND_PIN, faultOn ? HIGH : LOW);
    digitalWrite(READY_IND_PIN, readyOn ? HIGH : LOW);

    // WS2812 — fault takes priority; both active simultaneously shows amber
    RgbColor colour = COLOR_OFF;
    if (faultOn && readyOn) {
        colour = COLOR_AMBER;
    } else if (faultOn) {
        colour = modeToColour(faultMode);
    } else if (readyOn) {
        colour = modeToColour(readyMode);
    }

    writeLed(colour);
}

bool isFaultOn()
{
    return faultOnCached;
}

bool isReadyOn()
{
    return readyOnCached;
}

} // namespace indicator
