/**
 * @file compressor.cpp
 * @brief Air compressor relay control implementation.
 *
 * The relay is driven through a SparkFun Qwiic Single Relay at
 * COMPRESSOR_RELAY_ADDR (0x19) on the shared I2C bus.
 *
 * Only timed runs are supported.  startRun() enables the relay and records a
 * deadline; service() polls that deadline each tick and disables the relay
 * when it expires.  The maximum run duration is capped by COMPRESSOR_MAX_RUN_MS.
 */

#include <Arduino.h>
#include <SparkFun_Qwiic_Relay.h>

#include "hardware.h"
#include "pin_config.h"
#include "config.h"
#include "compressor.h"
#include "esp_log.h"

namespace compressor {

static constexpr char TAG[] = "compressor";

// SparkFun Qwiic Single Relay instance for this module.
static Qwiic_Relay sRelay(COMPRESSOR_RELAY_ADDR);

/// Set true by init() only when the relay device acknowledged on the I2C bus.
/// When false, setRelay() is a no-op so the module can be enabled in config
/// without crashing if the hardware is not yet fitted.
static bool sRelayAvailable = false;

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
    if (sRelayAvailable) {
        if (on) { sRelay.turnRelayOn(); } else { sRelay.turnRelayOff(); }
    }
    ESP_LOGD(TAG, "Relay → %s%s", on ? "ON" : "OFF", sRelayAvailable ? "" : " (no hw)");
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init() {
    ESP_LOGI(TAG, "Initialising compressor relay (Qwiic Single Relay @ 0x%02X)",
             static_cast<unsigned>(COMPRESSOR_RELAY_ADDR));

    if (!sRelay.begin(hardware::i2c())) {
        ESP_LOGW(TAG, "Qwiic Single Relay not found at 0x%02X — relay disabled",
                 static_cast<unsigned>(COMPRESSOR_RELAY_ADDR));
        sRelayAvailable = false;
    } else {
        sRelayAvailable = true;
        // Force the guard inside setRelay() to fire so sRelayOn tracks reality.
        sRelayOn = true;
        setRelay(false);
    }
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
