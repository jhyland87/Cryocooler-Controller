/**
 * @file main.cpp
 * @brief ESP32-S3 cryocooler controller -- application entry point
 *
 * Orchestrates all subsystem modules through the state machine and emits
 * one Serial Studio telemetry frame each loop tick.  See telemetry.h for
 * the full Serial Studio frame format and column definitions.
 *
 * Required Libraries (platformio.ini lib_deps):
 *   - Adafruit MAX31865
 *   - MD_AD9833
 *   - SmoothADC
 */

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <SmoothADC.h>

#include "config.h"
#include "pin_config.h"
#include "temperature.h"
#include "waveform.h"
#include "dac.h"
#include "rms.h"
#include "relay.h"
#include "indicator.h"
#include "state_machine.h"
#include "telemetry.h"
#include "commands.h"
#include "device.h"
#include "cooling.h"
#include "dashboard.h"
#include "accelerometer.h"

// =============================================================================
// Module-level objects
// =============================================================================

static SmoothADC dacVoltageAdc;

// =============================================================================
// Init helper
// =============================================================================

/**
 * Call initFn() until it stops returning MODULE_INIT_IN_PROGRESS, then log
 * the outcome.  Returns the final InitStatus.
 *
 * Example:
 *   initModule("accelerometer", [] { return accelerometer::init(); });
 */
template<typename Fn>
static module::InitStatus initModule(const char* name, Fn&& initFn) {
    Serial.printf("[init] %-20s ... ", name);

    module::InitStatus status = initFn();
    while (status == module::MODULE_INIT_IN_PROGRESS) {
        status = initFn();
    }

    if (status == module::MODULE_INIT_SUCCESS) {
        Serial.println(F("OK"));
    } else {
        Serial.printf("FAILED (status %d)\n", static_cast<int>(status));
    }
    return status;
}

// =============================================================================
// Timing state
// =============================================================================

static uint32_t previousLoopMs = 0;

// =============================================================================
// Setup
// =============================================================================

void setup() {
    Serial.begin(SERIAL_BAUD);

    // Wait for USB-CDC serial port (ESP32-S3 native USB).
    while (!Serial) delay(10);

    Serial.println(F("Cryocooler Controller -- starting up"));
    Serial.println(F("====================================="));

    // Shared buses — initialize once here, before any module that needs them.
    // The ESP32-S3 framework may call Wire.begin() silently in initVariant();
    // owning the call explicitly here prevents double-init surprises.
    SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);
    Wire.begin(SDA_PIN, SCL_PIN);

    // ── Module initialisation ────────────────────────────────────────────────
    // Each call blocks until the module is no longer IN_PROGRESS, then logs
    // OK or FAILED.  Failures are non-fatal here; the state machine will
    // detect missing sensor data and transition to Fault as appropriate.

    initModule("device",        [] { return device::init(); });
    initModule("accelerometer", [] { return accelerometer::init(); });
    initModule("cooling",       [] { return cooling::init(); });
    initModule("dashboard",     [] { return dashboard::init(); });

    // Smooth DAC voltage readback ADC (not a module — inline init)
    dacVoltageAdc.init(DAC_VOLTAGE_PIN, TB_MS, DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);
    dacVoltageAdc.enable();
    dacVoltageAdc.setPeriod(0);
    for (uint8_t i = 0; i < DAC_VOLTAGE_ADC_SMOOTH_PRIME_SAMPLES; ++i) {
        dacVoltageAdc.serviceADCPin();
    }
    dacVoltageAdc.setPeriod(DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);

    initModule("waveform",      [] { return waveform::init(); });
    initModule("temperature",   [] { return temperature::init(); });
    initModule("dac",           [] { return dac::init(); });
    initModule("rms",           [] { return rms::init(); });
    initModule("relay",         [] { return relay::init(); });
    initModule("indicator",     [] { return indicator::init(); });
    //initModule("http_api",    [] { return http_api::init(); });

    // state_machine::init() takes nowMs — wrap in a lambda
    initModule("state_machine", [] { return state_machine::init(millis()); });

    initModule("commands",      [] { return commands::init(); });

    Serial.println(F("\nSetup complete. System is Off."));
    Serial.println(F("Type 'help' for available commands."));
}

// =============================================================================
// Main Loop
// =============================================================================

void loop() {
    device::service();
    accelerometer::service();
    waveform::service();
    cooling::service();

    // Service smoothed ADC every iteration (non-blocking)
    dacVoltageAdc.serviceADCPin();

    const uint32_t nowMs = millis();

    // Process incoming serial commands (non-blocking)
    commands::service();

    // Indicator LEDs update every loop for accurate flash timing
    indicator::update(nowMs);

    // Main control tick at LOOP_INTERVAL_MS cadence
    if ((nowMs - previousLoopMs) < LOOP_INTERVAL_MS) {
        return;
    }
    previousLoopMs = nowMs;

    // ---- 1. Read sensors ------------------------------------------------
    temperature::read(nowMs);
    rms::read();
    rms::readCurrent();

    const float tempK       = temperature::getLastTempK();
    const float tempC       = temperature::getLastTempC();
    const float coolingRate = temperature::getCoolingRateKPerMin();
    const bool  stalled     = temperature::isStalled();
    const float rmsV        = rms::getVoltage();

    temperature::checkFaults();

    // ---- 2. Advance state machine ---------------------------------------
    const bool overstroke = rms::hasOverstroke();
    const auto out = state_machine::update(tempK, coolingRate, rmsV, stalled, nowMs, overstroke);
    if (overstroke) { rms::clearOverstroke(); }

    // ---- 3. Drive actuators ---------------------------------------------
    relay::setBypass(!out.bypassRelay);   // setBypass(true) = Normal
    relay::setAlarm(out.alarmRelay);

    indicator::setFaultMode(out.faultIndMode);
    indicator::setReadyMode(out.readyIndMode);

    // Ramp DAC toward the state-machine target (rate-limited in dac.cpp).
    // Use fast shutdown ramp during Shutdown state, normal ramp otherwise.
    if (out.state == state_machine::State::Shutdown) {
        dac::rampTowardShutdown(out.dacTarget);
    } else {
        dac::rampToward(out.dacTarget);
    }

    // ---- 4. HTTP API ---------------------------------------------------
    //http_api::service();

    // ---- 4. Telemetry ---------------------------------------------------
    telemetry::emit(out);
    dashboard::service();
}
