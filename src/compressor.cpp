/**
 * @file compressor.cpp
 * @brief Air compressor relay control implementation.
 *
 * The relay is driven through a PCAL9535A I2C GPIO expander.
 * The expander address and relay pin are configured in pin_config.h:
 *   COMPRESSOR_RELAY_PCAL_ADDR  — HardwareAddress enum value (A000–A111)
 *   COMPRESSOR_RELAY_PIN        — expander GPIO pin (0–15)
 *
 * Only timed runs are supported.  startRun() enables the relay and records a
 * deadline; service() polls that deadline each tick and disables the relay
 * when it expires.  The maximum run duration is capped by COMPRESSOR_MAX_RUN_MS.
 */

#include <Arduino.h>

#include "PCAL9535A.h"
#include "hardware.h"
#include "pin_config.h"
#include "config.h"
#include "compressor.h"
#include "esp_log.h"

namespace compressor {

static constexpr char TAG[] = "compressor";

// ---------------------------------------------------------------------------
// PCAL9535A instance — templated on TwoWire, shares the global I2C bus.
// Constructed once at file scope; begin() is called inside init().
// ---------------------------------------------------------------------------
static PCAL9535A::PCAL9535A<TwoWire> sGpio(hardware::i2c());

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
    sGpio.digitalWrite(COMPRESSOR_RELAY_PIN, on ? HIGH : LOW);
    ESP_LOGD(TAG, "Relay → %s", on ? "ON" : "OFF");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init() {
    ESP_LOGI(TAG, "Initialising compressor (PCAL9535A addr=%d pin=%d)",
             static_cast<int>(COMPRESSOR_RELAY_PCAL_ADDR),
             static_cast<int>(COMPRESSOR_RELAY_PIN));

    sGpio.begin(COMPRESSOR_RELAY_PCAL_ADDR);
    sGpio.pinMode(COMPRESSOR_RELAY_PIN, OUTPUT);

    // Force the guard inside setRelay() to fire by temporarily setting
    // sRelayOn to true, then drive LOW to ensure the pin starts off.
    sRelayOn       = true;
    setRelay(false);
    sRunStartMs    = 0;
    sRunDurationMs = 0;

    ESP_LOGI(TAG, "Compressor initialised — relay OFF");
    return module::MODULE_INIT_SUCCESS;
}

void startRun(uint32_t nowMs, uint32_t durationMs) {
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

void stopRun(uint32_t /*nowMs*/) {
    if (!sRelayOn && sRunStartMs == 0u) return;   // already stopped
    ESP_LOGI(TAG, "Stopping compressor run");
    setRelay(false);
    sRunStartMs    = 0u;
    sRunDurationMs = 0u;
}

void service(uint32_t nowMs) {
    if (sRunStartMs == 0u || sRunDurationMs == 0u) return;
    if ((nowMs - sRunStartMs) >= sRunDurationMs) {
        ESP_LOGI(TAG, "Compressor run duration elapsed — stopping");
        stopRun(nowMs);
    }
}

bool getStatus() {
    return sRelayOn;
}

bool isTimedRunActive() {
    return sRelayOn && sRunStartMs != 0u;
}

uint32_t getElapsedMs(uint32_t nowMs) {
    if (!isTimedRunActive()) return 0u;
    return nowMs - sRunStartMs;
}

uint32_t getRemainingMs(uint32_t nowMs) {
    if (!isTimedRunActive()) return 0u;
    const uint32_t elapsed = nowMs - sRunStartMs;
    return (elapsed >= sRunDurationMs) ? 0u : (sRunDurationMs - elapsed);
}

}  // namespace compressor
