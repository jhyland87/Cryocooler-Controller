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
#include "cold_head.h"
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
static bool     setupComplete  = false;

// =============================================================================
// Setup
// =============================================================================

void setup() {
    Serial.begin(SERIAL_BAUD);

    // Wait for USB-CDC serial port (ESP32-S3 native USB).
    while (!Serial) delay(10);
    delay(2000);

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

    if ( initModule("device",        [] { return device::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Device initialization failed. Halting startup."));
        return;
    }
    if ( initModule("accelerometer", [] { return accelerometer::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Accelerometer initialization failed — continuing without IMU."));
    }
    if ( initModule("cooling",       [] { return cooling::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Cooling initialization failed. Halting startup."));
        return;
    }
    if ( initModule("dashboard",     [] { return dashboard::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Dashboard initialization failed — continuing without dashboard."));
    }

    // Smooth DAC voltage readback ADC (not a module — inline init)
    dacVoltageAdc.init(DAC_VOLTAGE_PIN, TB_MS, DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);
    dacVoltageAdc.enable();
    dacVoltageAdc.setPeriod(0);
    for (uint8_t i = 0; i < DAC_VOLTAGE_ADC_SMOOTH_PRIME_SAMPLES; ++i) {
        dacVoltageAdc.serviceADCPin();
    }
    dacVoltageAdc.setPeriod(DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);

    if ( initModule("waveform",      [] { return waveform::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Waveform initialization failed. Halting startup."));
        return;
    }
    if ( initModule("cold_head",   [] { return cold_head::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Temperature initialization failed. Halting startup."));
        return;
    }
    if ( initModule("dac",           [] { return dac::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("DAC initialization failed. Halting startup."));
        return;
    }
    if ( initModule("rms",           [] { return rms::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("RMS initialization failed. Halting startup."));
        return;
    }
    if ( initModule("relay",         [] { return relay::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Relay initialization failed. Halting startup."));
        return;
    }

    if ( initModule("indicator",     [] { return indicator::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Indicator initialization failed. Halting startup."));
        return;
    }
    //initModule("http_api",    [] { return http_api::init(); });

    // state_machine::init() takes nowMs — wrap in a lambda
    if ( initModule("state_machine", [] { return state_machine::init(millis()); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("State machine initialization failed. Halting startup."));
        return;
    }

    if ( initModule("commands",      [] { return commands::init(); }) != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Commands initialization failed. Halting startup."));
        return;
    }

    setupComplete = true;
    Serial.println(F("\nSetup complete. System is Off."));
    Serial.println(F("Type 'help' for available commands."));
}

// =============================================================================
// Main Loop
// =============================================================================

void loop() {
    if (!setupComplete) { return; }

    // ── Per-tick module service ───────────────────────────────────────────
    // Each call returns a ServiceStatus.  SERVICE_ERROR is logged; all
    // modules are still serviced regardless so the control loop keeps running.
    // Silence SERVICE_SKIPPED — it is the normal outcome for time-gated modules.

    if (device::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] device service error"));
    }
    if (accelerometer::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] accelerometer service error"));
    }
    if (waveform::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] waveform service error"));
    }
    if (cooling::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] cooling service error"));
    }

    // Service smoothed ADC every iteration (non-blocking)
    dacVoltageAdc.serviceADCPin();

    const uint32_t nowMs = millis();

    // Process incoming serial commands (non-blocking)
    if (commands::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] commands service error"));
    }

    // Indicator LEDs update every loop for accurate flash timing
    indicator::update(nowMs);

    // Main control tick at LOOP_INTERVAL_MS cadence
    if ((nowMs - previousLoopMs) < LOOP_INTERVAL_MS) {
        return;
    }
    previousLoopMs = nowMs;

    // ---- 1. Read sensors ------------------------------------------------
    cold_head::read(nowMs);
    rms::read();
    rms::readCurrent();

    const float tempK       = cold_head::getLastTempK();
    const float tempC       = cold_head::getLastTempC();
    const float coolingRate = cold_head::getCoolingRateKPerMin();
    const bool  stalled     = cold_head::isStalled();
    const float rmsV        = rms::getVoltage();

    cold_head::checkFaults();

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

    // ---- 5. Telemetry ---------------------------------------------------
    telemetry::emit(out);
    dashboard::service();
}
