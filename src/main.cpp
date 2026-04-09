/**
 * @file main.cpp
 * @brief ESP32-S3 cryocooler controller -- application entry point
 *
 * Orchestrates all subsystem modules through the state machine and emits
 * one Serial Studio telemetry frame each loop tick.  See telemetry.h for
 * the full Serial Studio frame format and column definitions.
 *
 * Required Libraries (platformio.ini lib_deps):
 *   - SparkFun ADS122C04 ADC Arduino Library
 *   - MD_AD9833
 */

#include <Arduino.h>
#include <esp_system.h>   // esp_register_shutdown_handler()

#include "config.h"
#include "hardware.h"
#include "pin_config.h"
#include "cold_head.h"
#include "indicator.h"
#include "state_machine.h"
#include "telemetry.h"
#include "commands.h"
#include "sysinfo.h"
#include "cooling.h"
#include "dashboard.h"
#include "imu.h"
#include "sensor_mock.h"
#include "amplifier.h"
#include "compressor.h"
#include "logger.h"
#include "esp_log.h"
#include "ota.h"
#include "espnow.h"
#include "tick.h"
// =============================================================================
// Logging
// =============================================================================

static constexpr char TAG[] = "main";
static LogStream _Log = Log.createChildLogger("main");

// Printf-style function used by module::initGroup / serviceWithLog / reportStatus.
__attribute__((format(printf, 1, 2)))
static void logPrintf(const char* fmt, ...) {
    char buf[192];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    _Log.print(buf);
}

// =============================================================================
// Module registry — init & service arrays
//
// Order within each array encodes dependency constraints:
//   - OTA before dashboard (registerRoutes must exist before setupServer)
//   - dashboard before espnow (WiFi must be up)
//   - compressor first in control group (de-energise relay ASAP)
//
// Special-cased modules that don't appear here:
//   - hardware    — fatal init, must succeed before anything else
//   - indicator   — init before WiFi to avoid neopixelWrite deadlock
//   - state_machine — non-standard update() signature
//   - telemetry   — emit(out) takes state_machine output
//   - cold_head   — in gated section, before state_machine
//   - sensor_mock — no Module struct
// =============================================================================

/// Modules initialized once at boot (never re-initialized on reinit).
static const module::ModuleEntry persistentModules[] = {
    MODULE_ENTRY(imu,       false),
    MODULE_ENTRY(ota,       false),
    MODULE_ENTRY(dashboard, false),
#if ENABLE_ESPNOW
    MODULE_ENTRY(espnow,    false),
#endif
    MODULE_ENTRY(telemetry, false),
    MODULE_ENTRY(sysinfo,   false),
};
static constexpr size_t NUM_PERSISTENT = sizeof(persistentModules) / sizeof(persistentModules[0]);

/// Control hardware modules — re-initialized on every FSM reinit().
static const module::ModuleEntry controlModules[] = {
#if ENABLE_COMPRESSOR
    MODULE_ENTRY(compressor, false),
#endif
    MODULE_ENTRY(cooling,    false),
    MODULE_ENTRY(amplifier,  false),
    MODULE_ENTRY(cold_head,  false),
};
static constexpr size_t NUM_CONTROL = sizeof(controlModules) / sizeof(controlModules[0]);

/// Modules serviced every loop() tick with health-transition logging.
static const module::ModuleEntry tickServiceModules[] = {
    MODULE_ENTRY(sysinfo,   false),
    MODULE_ENTRY(imu,       false),
    MODULE_ENTRY(amplifier, false),
    MODULE_ENTRY(cooling,   false),
};
static constexpr size_t NUM_TICK_SERVICE = sizeof(tickServiceModules) / sizeof(tickServiceModules[0]);

/// Combined list for the one-time boot status banner.
static const module::ModuleEntry allModulesForBanner[] = {
    MODULE_ENTRY(hardware,      true),
    MODULE_ENTRY(indicator,     false),
    MODULE_ENTRY(imu,           false),
    MODULE_ENTRY(ota,           false),
    MODULE_ENTRY(dashboard,     false),
    MODULE_ENTRY(sysinfo,       false),
    MODULE_ENTRY(cooling,       false),
    MODULE_ENTRY(amplifier,     false),
    MODULE_ENTRY(cold_head,     false),
    MODULE_ENTRY(state_machine, false),
#if ENABLE_COMPRESSOR
    MODULE_ENTRY(compressor,    false),
#endif
};
static constexpr size_t NUM_ALL_BANNER = sizeof(allModulesForBanner) / sizeof(allModulesForBanner[0]);

// =============================================================================
// Timing state
// =============================================================================

static uint32_t previousLoopMs = 0;
static uint32_t previousIndicatorUpdateMs = 0;

static uint32_t sSerialConnectionEstablishedMs = 0;
static uint32_t sSerialLastDetectedMs = 0;
static bool sSerialWelcomeMessageSent = false;

/**
 * Initialise modules required for the operator console and remote viewer to
 * function.  Called once in setup() before control hardware is initialised.
 *
 * These modules are intentionally never re-initialised by reinit() because
 * they provide the communication path through which the operator issues
 * commands — including the reinit command itself.
 *
 * Array order encodes dependencies (OTA before dashboard, dashboard before
 * espnow).  telemetry::emitSafe() is called after each step so the dashboard
 * shows real-time progress.
 */
static void initPersistentModules() {
    module::initGroup(persistentModules, NUM_PERSISTENT,
                      telemetry::emitSafe, logPrintf, yield);
}

/**
 * Initialise control hardware modules.
 *
 * This function is registered as the FSM's onInitialize callback and is
 * therefore called synchronously every time the machine enters the
 * Initialize state — both at startup and on any subsequent reinit() call.
 * That means hardware peripherals are re-initialised on a logical system
 * reset without requiring a full MCU reboot.
 *
 * Failures are non-fatal and do not halt startup.  Module init statuses are
 * persisted in each Module's static _initStatus; state_machine::start() reads
 * those statuses and blocks entry into any cooling state until all required
 * modules report MODULE_INIT_SUCCESS.  telemetry::emitSafe() is called after
 * each step so the dashboard shows real-time progress.
 *
 * indicator is intentionally omitted — it is initialised once in setup()
 * before WiFi starts to avoid a neopixelWrite() deadlock on ESP32-S3 with
 * Arduino 2.x.  It does not need re-initialisation on reinit().
 */
static void initControlModules() {
    module::initGroup(controlModules, NUM_CONTROL,
                      telemetry::emitSafe, logPrintf, yield);
}
// =============================================================================
// Setup
// =============================================================================

void setup() {
    Serial.setRxBufferSize(1024);
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    //while (!Serial.available()) delay(100);

    _Log.println(F("Starting up"));
    _Log.println(F("Cryocooler Controller -- starting up"));
    _Log.println(F("====================================="));

    // Initialise shared buses before any module that needs them.
    // hardware::init() owns the single GuardedWire and SPIClass instances;
    // modules access them via hardware::i2c() / hardware::spi() rather than
    // the global Wire / SPI singletons.
    // hardware is fatal — halt if it fails (marked fatal in its ModuleEntry).
    {
        static const module::ModuleEntry hwEntry = MODULE_ENTRY(hardware, true);
        if (!module::initGroup(&hwEntry, 1, nullptr, logPrintf)) {
            _Log.println(F("Hardware bus init failed. Halting."));
            return;
        }
    }

    // Initialise the indicator LED before WiFi starts.  On ESP32-S3 with
    // Arduino 2.x, neopixelWrite() uses rmt_wait_tx_done() internally which
    // deadlocks if the WiFi stack is already up — WiFi interrupt priorities
    // can block the RMT "done" interrupt, hanging the main task indefinitely.
    // The indicator only needs GPIO + RMT (no I2C/SPI), so it is safe to run
    // here immediately after the hardware buses are ready.
    {
        static const module::ModuleEntry indEntry = MODULE_ENTRY(indicator, false);
        module::initGroup(&indEntry, 1, nullptr, logPrintf);
    }

    // Initialise the command line buffer before any modules — the serial
    // console must be ready so the operator can observe progress and send
    // commands even if control hardware fails to initialise.
    commands::init();

    // Bring up the console and viewer so the operator can observe progress
    // and send commands even if control hardware fails to initialise.
    initPersistentModules();

    // Initialise the FSM infrastructure (pure in-memory, always succeeds).
    state_machine::Module::init();

    // Register initControlModules as the onInitialize callback, then call
    // reinit() to enter the Initialize state.  This runs initControlModules()
    // synchronously — the same path taken on every subsequent reinit().
    state_machine::setOnInitializeCallback(initControlModules);
    state_machine::reinit();

    // Zero the DAC before any software-triggered reset (esp_restart(), IDF
    // watchdog recovery, etc.).  Hard resets (reset button, power cut) cannot
    // be caught here; initDac() handles those by force-writing 0 on every boot.
    esp_register_shutdown_handler([]() { amplifier::hardStop(); });

    _Log.println(F("[setup] Setup complete. System is initializing."));
    _Log.println(F("Type 'help' for available commands."));
}

// =============================================================================
// Main Loop
// =============================================================================

int serialAvailable = 0;

void loop() {
    tick::update();

    if ( Serial.available() != serialAvailable) {
        serialAvailable = Serial.available();
        ESP_LOGD(TAG, "Serial available: %d", static_cast<int>(serialAvailable));
    }
    //while (Serial.available()) { Serial.print("Serial:"); Serial.println(Serial.read()); }
    //while (Serial.available()) { Serial.read(); }
    //return;
    // One-time banner on the very first loop() iteration.
    // Lets the user know the loop has started and the console is ready —
    // i.e. this is the right moment to start typing commands.
    // @todo - This doesnt work unless the user is connected when the first loop is triggered
    static bool sLoopStarted = false;
    if (!sLoopStarted) {
        sLoopStarted = true;
        // Drain any characters that arrived in the USB RX buffer during setup
        // so they don't accidentally dispatch stale commands.
        //while (Serial.available()) { Serial.print("Serial:"); Serial.println(Serial.read()); }
        _Log.println();
        _Log.println(F(">>> Serial console active. Type 'help' for commands. <<<"));

        // Scan all modules for init failures and list them explicitly.
        module::reportStatus(allModulesForBanner, NUM_ALL_BANNER, logPrintf);
        Log.println();
    }

    // Serial command processing runs unconditionally so the console is always
    // reachable even when control hardware failed to initialise.
    // (The TCP/Serial-Studio path calls processLine() directly.)
    commands::service();

    // ── Per-tick module service ───────────────────────────────────────────
    // Each call returns a ServiceStatus.  SERVICE_ERROR is logged; all
    // modules are still serviced regardless so the control loop keeps running.
    // Only health-status transitions are logged (not every tick).
    //
    // Mock mode is handled inside each module: when sensor_mock::isActive(),
    // read() / service() pull values from sensor_mock::get() and skip hardware
    // access entirely.  No conditional logic is needed here.
    {
        static module::ServiceStatus prevStatus[NUM_TICK_SERVICE] = {};
        for (size_t i = 0; i < NUM_TICK_SERVICE; ++i) {
            module::serviceWithLog(tickServiceModules[i], prevStatus[i], logPrintf);
        }
    }

    const uint32_t nowMs = tick::nowMs();

    // I2C health monitor — Wire ESP_LOGE messages are suppressed; we count
    // errors via module service return codes and log periodic summaries.
    hardware::serviceI2c();

    if ((nowMs - previousIndicatorUpdateMs) < INDICATOR_UPDATE_INTERVAL_MS) {
        indicator::update();
        previousIndicatorUpdateMs = nowMs;
    }

    // Main control tick at LOOP_INTERVAL_MS cadence
    if ((nowMs - previousLoopMs) < LOOP_INTERVAL_MS) {
        return;
    }
    previousLoopMs = nowMs;
    indicator::update();

    // ---- 1. Read sensors ------------------------------------------------
    // Advance any active mock ramps before module reads, so that every module
    // sees the updated value on the same tick.
    sensor_mock::service();

    // Each module handles mock mode internally: when sensor_mock::isActive(),
    // read()/service() pulls from sensor_mock::get() instead of hardware.
    cold_head::service();  // includes fault checking internally

    // Read cached values.
    const float tempC       = cold_head::getLastTempC();
    //Serial.printf("tempC: %f\n", tempC);
    const float coolingRate = cold_head::getCoolingRateCPerMin();
    //Serial.printf("coolingRate: %f\n", coolingRate);
    const bool  stalled     = cold_head::isStalled();
    //Serial.printf("stalled: %d\n", stalled);

    const float rmsV        = amplifier::getLastRmsVoltage();

    const bool  overstroke  = imu::hasOverstroke();
    //Serial.printf("overstroke: %d\n", overstroke);
    const float sysVoltage  = sysinfo::getVoltage();
    //Serial.printf("sysVoltage: %f\n", sysVoltage);
    // ---- 2. Advance state machine ---------------------------------------
    const auto out = state_machine::update(tempC, coolingRate, rmsV, stalled, overstroke, sysVoltage);
    // Clear edge-triggered overstroke flag after the state machine has consumed
    // it.  In real mode the flag was set by readCurrent(); in mock mode it was
    // set by setLastReadings().  Either way, clear it so it fires only once.
    if (overstroke) { imu::clearOverstroke(); }

    // ---- 3. Drive actuators ---------------------------------------------
    indicator::setFaultMode(out.faultIndMode);
    indicator::setReadyMode(out.readyIndMode);

    // DAC ramping is driven by state_machine::update() directly — either on
    // state entry (via on_enter callbacks) or per-tick for states with a
    // dynamic target (CoarseCooldown, FineCooldown, Shutdown).

    // ---- 4. Compressor timer -------------------------------------------
#if ENABLE_COMPRESSOR
    compressor::Module::service();
#endif

    // ---- 5. HTTP API ---------------------------------------------------
    //http_api::service();

    // ---- 6. Telemetry ---------------------------------------------------
    telemetry::emit(out);
    dashboard::Module::service();
}
