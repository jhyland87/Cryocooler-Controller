/**
 * @file compressor.cpp
 * @brief Air compressor relay control implementation.
 *
 * The relay is driven through the shared relay_board driver (PCAL9535A at
 * COMPRESSOR_RELAY_PCAL_ADDR / 0x20).  relay_board owns the single library
 * instance and calls begin() exactly once, preventing the register-reset
 * problem that arises when two instances address the same chip.
 *
 * Only timed runs are supported.  startRun() enables the relay and records a
 * deadline; service() polls that deadline each tick and disables the relay
 * when it expires.  The maximum run duration is capped by COMPRESSOR_MAX_RUN_MS.
 */

#include <Arduino.h>

#include "hardware.h"
#include "pin_config.h"
#include "config.h"
#include "compressor.h"
#include "relay_board.h"
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
    relay_board::setPin(COMPRESSOR_RELAY_PIN, on);
    ESP_LOGD(TAG, "Relay → %s", on ? "ON" : "OFF");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init() {
    ESP_LOGI(TAG, "Initialising compressor relay (pin %d via relay_board)",
             static_cast<int>(COMPRESSOR_RELAY_PIN));

    // relay_board::init() is idempotent — whichever module calls it first
    // programmes the PCAL9535A and drives both relay pins LOW.
    relay_board::init();

    // Force the guard inside setRelay() to fire so sRelayOn tracks reality.
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

void setRelayState(bool on) {
    setRelay(on);
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
