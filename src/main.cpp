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
#include <SmoothADC.h>

#include "config.h"
#include "hardware.h"
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
#include "sysinfo.h"
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
    Serial.printf("[%s] Initialising ... \n", name);

    module::InitStatus status = initFn();
    while (status == module::MODULE_INIT_IN_PROGRESS) {
        status = initFn();
    }

    if (status == module::MODULE_INIT_SUCCESS) {
        Serial.printf("[%s] Initialisation complete\n", name);
    } else {
        Serial.printf("[%s] FAILED (status %d)\n", name, static_cast<int>(status));
    }
    return status;
}

// =============================================================================
// Timing state
// =============================================================================

static uint32_t previousLoopMs = 0;
static bool     setupComplete  = false;

void setupModules(){
    // ── Module initialisation ────────────────────────────────────────────────
    // Each call blocks until the module is no longer IN_PROGRESS, then logs
    // OK or FAILED.  Failures are non-fatal here; the state machine will
    // detect missing sensor data and transition to Fault as appropriate.

    auto sysinfoStatus =  initModule("sysinfo",        [] { return sysinfo::Module::init(); });
    if (sysinfoStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Sysinfo initialization failed (status %d). Halting startup.\n", static_cast<int>(sysinfoStatus));
        return;
    }

    auto accelerometerStatus = initModule("accelerometer", [] { return accelerometer::Module::init(); });
    if (accelerometerStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Accelerometer initialization failed (status %d) — continuing without IMU.\n", static_cast<int>(accelerometerStatus));
    }

    auto coolingStatus = initModule("cooling",       [] { return cooling::Module::init(); });
    if (coolingStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Cooling initialization failed (status %d). Halting startup.\n", static_cast<int>(coolingStatus));
        return;
    }

    auto dashboardStatus = initModule("dashboard",     [] { return dashboard::Module::init(); });
    if (dashboardStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Dashboard initialization failed (status %d) — continuing without dashboard.\n", static_cast<int>(dashboardStatus));
    }

    // Smooth DAC voltage readback ADC (not a module — inline init)
    dacVoltageAdc.init(DAC_VOLTAGE_PIN, TB_MS, DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);
    dacVoltageAdc.enable();
    dacVoltageAdc.setPeriod(0);
    for (uint8_t i = 0; i < DAC_VOLTAGE_ADC_SMOOTH_PRIME_SAMPLES; ++i) {
        dacVoltageAdc.serviceADCPin();
    }

    dacVoltageAdc.setPeriod(DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);

    auto waveformStatus = initModule("waveform",      [] { return waveform::Module::init(); });
    if (waveformStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Waveform initialization failed (status %d). Halting startup.\n", static_cast<int>(waveformStatus));
        return;
    }

    auto cold_headStatus = initModule("cold_head",   [] { return cold_head::Module::init(); });
    if (cold_headStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Cold head initialization failed (status %d). Halting startup.\n", static_cast<int>(cold_headStatus));
        return;
    }

    auto dacStatus = initModule("dac",           [] { return dac::Module::init(); });
    if (dacStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] DAC initialization failed (status %d). Halting startup.\n", static_cast<int>(dacStatus));
        return;
    }

    auto rmsStatus = initModule("rms",           [] { return rms::Module::init(); });
    if (rmsStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] RMS initialization failed (status %d). Halting startup.\n", static_cast<int>(rmsStatus));
        return;
    }

    auto relayStatus = initModule("relay",         [] { return relay::Module::init(); });
    if (relayStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Relay initialization failed (status %d). Halting startup.\n", static_cast<int>(relayStatus));
        return;
    }

    auto indicatorStatus = initModule("indicator",     [] { return indicator::Module::init(); });
    if (indicatorStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Indicator initialization failed (status %d). Halting startup.\n", static_cast<int>(indicatorStatus));
        return;
    }
    //initModule("http_api",    [] { return http_api::init(); });

    auto stateMachineStatus = initModule("state_machine", [] { return state_machine::Module::init(); });
    if (stateMachineStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] State machine initialization failed (status %d). Halting startup.\n", static_cast<int>(stateMachineStatus));
        return;
    }

    auto commandsStatus = initModule("commands",      [] { return commands::Module::init(); });
    if (commandsStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Commands initialization failed (status %d). Continuing without commands.\n", static_cast<int>(commandsStatus));
    }

    // telemetry has no hardware setup but we call Module::init() to record a
    // valid InitStatus so the mod.telemetry.init field in the telemetry frame
    // reflects the actual state rather than NOT_STARTED.
    telemetry::Module::init();

    setupComplete = true;
}
// =============================================================================
// Setup
// =============================================================================

void setup() {
    Serial.begin(SERIAL_BAUD);

    // Wait for USB-CDC serial port (ESP32-S3 native USB).
    while (!Serial) delay(10);
    delay(3000);

    Serial.println(F("Cryocooler Controller -- starting up"));
    Serial.println(F("====================================="));

    // Initialise shared buses before any module that needs them.
    // hardware::init() owns the single GuardedWire and SPIClass instances;
    // modules access them via hardware::i2c() / hardware::spi() rather than
    // the global Wire / SPI singletons.
    if (initModule("hardware", [] { return hardware::Module::init(); })
            != module::MODULE_INIT_SUCCESS) {
        Serial.println(F("Hardware bus init failed. Halting."));
        return;
    }

    setupModules();

    if ( ! setupComplete ){
        Serial.println(F("Setup failed. Halting startup."));
        return;
    }


    Serial.printf("\nSetup complete. System is Off. (status %d)", static_cast<int>(sysinfo::Module::getInitStatus()));

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

    if (sysinfo::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] sysinfo service error"));
    }
    if (accelerometer::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] accelerometer service error"));
    }
    if (waveform::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] waveform service error"));
    }
    if (cooling::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] cooling service error"));
    }

    // Service smoothed ADC every iteration (non-blocking)
    dacVoltageAdc.serviceADCPin();

    const uint32_t nowMs = millis();

    // Process incoming serial commands (non-blocking)
    if (commands::Module::service() == module::MODULE_SERVICE_ERROR) {
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
    dashboard::Module::service();
}
