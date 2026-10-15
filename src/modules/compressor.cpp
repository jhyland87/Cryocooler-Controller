/**
 * @file compressor.cpp
 * @brief Air compressor relay control implementation.
 *
 * The relay is driven from COMPRESSOR_RELAY_PIN (GPIO16) through a BSS138 /
 * BSS84 high-side switch: HIGH puts +12 V on the compressor relay terminal.
 *
 * Only timed runs are supported.  startRun() enables the relay and records a
 * deadline; service() polls that deadline each tick and disables the relay
 * when it expires.  The maximum run duration is capped by COMPRESSOR_MAX_RUN_MS.
 */

#include <Arduino.h>

#include "pin_config.h"
#include "config.h"
#include "compressor.h"
#include "tick.h"
#include "esp_log.h"

namespace compressor {

static constexpr char TAG[] = "compressor";

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

/// True while the relay output is energised.
static bool     sRelayOn       = false;

/// millis() value when the current timed run started; 0 when idle.
static uint32_t sRunStartMs    = 0;

/// Duration of the current timed run in ms; 0 when idle.
static uint32_t sRunDurationMs = 0;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static void setRelay(bool on) {
    if (on == sRelayOn) return;
    sRelayOn = on;
    digitalWrite(COMPRESSOR_RELAY_PIN, on ? HIGH : LOW);
    ESP_LOGD(TAG, "Relay → %s", on ? "ON" : "OFF");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init() {
    ESP_LOGI(TAG, "Initialising compressor relay (GPIO %d)", COMPRESSOR_RELAY_PIN);

    pinMode(COMPRESSOR_RELAY_PIN, OUTPUT);
    // Force the guard inside setRelay() to fire so the pin is driven low.
    sRelayOn = true;
    setRelay(false);
    sRunStartMs    = 0;
    sRunDurationMs = 0;

    ESP_LOGI(TAG, "Compressor initialised — relay OFF");
    return module::MODULE_INIT_SUCCESS;
}

void startRun(uint32_t durationMs) {
    const uint32_t nowMs = tick::nowMs();
    // Clamp to the configured safety limit (0 = no limit).
    const uint32_t limit = static_cast<uint32_t>(COMPRESSOR_MAX_RUN_MS);
    if (limit > 0u && durationMs > limit) {
        ESP_LOGW(TAG, "Requested duration %lu ms exceeds limit %lu ms — clamping",
                 static_cast<unsigned long>(durationMs),
                 static_cast<unsigned long>(limit));
        durationMs = limit;
    }

    ESP_LOGI(TAG, "Starting compressor run for %lu ms",
             static_cast<unsigned long>(durationMs));
    sRunStartMs    = nowMs;
    sRunDurationMs = durationMs;
    setRelay(true);
}

void stopRun() {
    if (!sRelayOn && sRunStartMs == 0u) return;   // already stopped
    ESP_LOGI(TAG, "Stopping compressor run");
    setRelay(false);
    sRunStartMs    = 0u;
    sRunDurationMs = 0u;
}

void service() {
    if (sRunStartMs == 0u || sRunDurationMs == 0u) return;
    const uint32_t nowMs = tick::nowMs();
    if ((nowMs - sRunStartMs) >= sRunDurationMs) {
        ESP_LOGI(TAG, "Compressor run duration elapsed — stopping");
        stopRun();
    }
}

bool getStatus() {
    return sRelayOn;
}

void setRelayState(bool on) {
    setRelay(on);
}

bool isTimedRunActive() {
    return sRelayOn && sRunStartMs != 0u;
}

uint32_t getElapsedMs() {
    if (!isTimedRunActive()) return 0u;
    return tick::nowMs() - sRunStartMs;
}

uint32_t getRemainingMs() {
    if (!isTimedRunActive()) return 0u;
    const uint32_t elapsed = tick::nowMs() - sRunStartMs;
    return (elapsed >= sRunDurationMs) ? 0u : (sRunDurationMs - elapsed);
}

}  // namespace compressor
