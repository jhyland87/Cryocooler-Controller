/**
 * @file indicator.cpp
 * @brief FAULT and READY indicator implementation
 *
 * Uses the on-board WS2812B-2020 LED (STATUS_LED_PIN) to display a combined
 * FAULT + READY colour.  It needs no SPI, so it still works if the bus is down.
 *
 * Flash timing is non-blocking (state-machine style).
 * LED output uses the ESP32 Arduino core's RMT driver — no external library
 * required.
 */

#include <Arduino.h>

#include <string.h>

#include "pin_config.h"
#include "config.h"
#include "indicator.h"
#include "tick.h"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

struct RgbColor {
    uint8_t red;
    uint8_t green;
    uint8_t blue;
};

// ---------------------------------------------------------------------------
// Module constants
// ---------------------------------------------------------------------------

// WS2812B-2020 bit timing in 100 ns RMT ticks.
static constexpr float   RMT_TICK_NS = 100.0f;
static constexpr uint8_t T0H_TICKS   = 3;
static constexpr uint8_t T0L_TICKS   = 8;
static constexpr uint8_t T1H_TICKS   = 8;
static constexpr uint8_t T1L_TICKS   = 6;

static rmt_obj_t* sLedRmt = nullptr;
static uint8_t    sLastChannels[3] = {0, 0, 0};

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

/**
 * Send one colour to the WS2812B-2020 when it differs from the last one sent.
 *
 * The part needs T0H 220-380 ns and T1H/T0L/T1L 580-1000 ns (datasheet V1.3
 * p.4), which neopixelWrite()'s 400 ns T0H and T1L miss. It also latches only
 * after 280 us of low, so frames can't be sent on every loop pass.
 */
static void writeLed(const RgbColor& color)
{
    const uint8_t channels[] = {applyBrightness(color.green),
                                applyBrightness(color.red),
                                applyBrightness(color.blue)};
    if (sLedRmt != nullptr && memcmp(channels, sLastChannels, sizeof(channels)) == 0) {
        return;
    }
    if (sLedRmt == nullptr) {
        sLedRmt = rmtInit(STATUS_LED_PIN, RMT_TX_MODE, RMT_MEM_64);
        if (sLedRmt == nullptr) {
            return;
        }
        rmtSetTick(sLedRmt, RMT_TICK_NS);
    }

    rmt_data_t bits[sizeof(channels) * 8];
    size_t bitIndex = 0;
    for (const uint8_t channel : channels) {
        for (int bitNumber = 7; bitNumber >= 0; --bitNumber) {
            const bool isOne = (channel >> bitNumber) & 1u;
            bits[bitIndex].level0 = 1;
            bits[bitIndex].duration0 = isOne ? T1H_TICKS : T0H_TICKS;
            bits[bitIndex].level1 = 0;
            bits[bitIndex].duration1 = isOne ? T1L_TICKS : T0L_TICKS;
            ++bitIndex;
        }
    }
    if (rmtWrite(sLedRmt, bits, bitIndex)) {
        memcpy(sLastChannels, channels, sizeof(channels));
    }
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
