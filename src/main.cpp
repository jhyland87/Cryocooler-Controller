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
 */

#include <Arduino.h>
#include <esp_system.h>   // esp_register_shutdown_handler()

#include "config.h"
#include "hardware.h"
#include "pin_config.h"
#include "cold_head.h"
#include "relay.h"
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
#include "logger.h"
#include "ota.h"
#include "espnow.h"
// =============================================================================
// Module-level objects
// =============================================================================

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

/**
 * Initialise modules required for the operator console and remote viewer to
 * function.  Called once in setup() before control hardware is initialised.
 *
 * These modules are intentionally never re-initialised by reinit() because
 * they provide the communication path through which the operator issues
 * commands — including the reinit command itself.
 */
static void initPersistentModules() {

    auto loggerStatus = initModule("logger", [] { return logger::Module::init(); });
    if (loggerStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Logger initialization failed (status %d). Continuing without logger.\n",
                      static_cast<int>(loggerStatus));
    }

    auto imuStatus = initModule("imu", [] { return imu::Module::init(); });
    if (imuStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] IMU initialization failed (status %d) — continuing without IMU.\n",
                      static_cast<int>(imuStatus));
    }

    auto commandsStatus = initModule("commands", [] { return commands::Module::init(); });
    if (commandsStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Commands initialization failed (status %d). Continuing without commands.\n",
                      static_cast<int>(commandsStatus));
    }

    // OTA must init before dashboard so registerRoutes() is ready when
    // dashboard::setupServer() calls it during dashboard init.
    auto otaStatus = initModule("ota", [] { return ota::Module::init(); });
    if (otaStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] OTA initialization failed (status %d) — OTA endpoint unavailable.\n",
                      static_cast<int>(otaStatus));
    }

    auto dashboardStatus = initModule("dashboard", [] { return dashboard::Module::init(); });
    if (dashboardStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Dashboard initialization failed (status %d) — continuing without dashboard.\n",
                      static_cast<int>(dashboardStatus));
    }

    // ESP-NOW must be initialised after dashboard (which brings up WiFi).
    // The channel follows the STA association automatically; the peer must be
    // on the same channel.  Set ENABLE_ESPNOW=true and fill in ESPNOW_PEER_MAC
    // in config.h before enabling.
#if ENABLE_ESPNOW
    auto espnowStatus = initModule("espnow", [] { return espnow::Module::init(); });
    if (espnowStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] ESP-NOW initialization failed (status %d) — continuing without ESP-NOW.\n",
                      static_cast<int>(espnowStatus));
    }
#endif

    // telemetry has no hardware setup but we call Module::init() to record a
    // valid InitStatus so the mod.telemetry.init field in the telemetry frame
    // reflects the actual state rather than NOT_STARTED.
    telemetry::Module::init();
    telemetry::emitSafe();

    auto sysinfoStatus = initModule("sysinfo", [] { return sysinfo::Module::init(); });
    if (sysinfoStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Sysinfo initialization failed (status %d). Continuing.\n",
                      static_cast<int>(sysinfoStatus));
    }
    telemetry::emitSafe();
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
 */
static void initControlModules() {
    auto coolingStatus = initModule("cooling", [] { return cooling::Module::init(); });
    if (coolingStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Cooling initialization failed (status %d).\n",
                      static_cast<int>(coolingStatus));
    }
    telemetry::emitSafe();

    auto amplifierStatus = initModule("amplifier", [] { return amplifier::Module::init(); });
    if (amplifierStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Amplifier initialization failed (status %d).\n",
                      static_cast<int>(amplifierStatus));
    }
    telemetry::emitSafe();

    auto cold_headStatus = initModule("cold_head", [] { return cold_head::Module::init(); });
    if (cold_headStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Cold head initialization failed (status %d).\n",
                      static_cast<int>(cold_headStatus));
    }
    telemetry::emitSafe();

    auto relayStatus = initModule("relay", [] { return relay::Module::init(); });
    if (relayStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[init] Relay initialization failed (status %d).\n",
                      static_cast<int>(relayStatus));
    }
    telemetry::emitSafe();

    // indicator is intentionally omitted here — it is initialised once in
    // setup() before WiFi starts to avoid a neopixelWrite() deadlock on
    // ESP32-S3 with Arduino 2.x.  It does not need re-initialisation on reinit().
}
// =============================================================================
// Setup
// =============================================================================

void setup() {
    Serial.begin(SERIAL_BAUD);

    //while (!Serial.available()) delay(100);
    delay(1000);

    logger::logf("[setup] Starting up\n");
    Serial.println(F("Cryocooler Controller -- starting up"));
    Serial.println(F("====================================="));

    // Initialise shared buses before any module that needs them.
    // hardware::init() owns the single GuardedWire and SPIClass instances;
    // modules access them via hardware::i2c() / hardware::spi() rather than
    // the global Wire / SPI singletons.
    if (initModule("hardware", [] { return hardware::Module::init(); })
            != module::MODULE_INIT_SUCCESS) {
        logger::logf("[setup] Hardware bus init failed. Halting.\n");
        Serial.println(F("Hardware bus init failed. Halting."));
        return;
    }

    // Initialise the indicator LED before WiFi starts.  On ESP32-S3 with
    // Arduino 2.x, neopixelWrite() uses rmt_wait_tx_done() internally which
    // deadlocks if the WiFi stack is already up — WiFi interrupt priorities
    // can block the RMT "done" interrupt, hanging the main task indefinitely.
    // The indicator only needs GPIO + RMT (no I2C/SPI), so it is safe to run
    // here immediately after the hardware buses are ready.
    initModule("indicator", [] { return indicator::Module::init(); });

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

    logger::logf("[setup] Setup complete. System is initializing.\n");
    Serial.println(F("\nSetup complete. System is initializing."));
    Serial.println(F("Type 'help' for available commands."));
}

// =============================================================================
// Main Loop
// =============================================================================

void loop() {
    // One-time banner on the very first loop() iteration.
    // Lets the user know the loop has started and the console is ready —
    // i.e. this is the right moment to start typing commands.
    static bool sLoopStarted = false;
    if (!sLoopStarted) {
        sLoopStarted = true;
        // Drain any characters that arrived in the USB RX buffer during setup
        // so they don't accidentally dispatch stale commands.
        while (Serial.available()) { Serial.read(); }
        Serial.println();
        Serial.println(F(">>> Serial console active. Type 'help' for commands. <<<"));
        Serial.println(F("    (setup may have partially failed — check status above)"));
        Serial.println();
    }

    // Serial command processing runs unconditionally so the console is always
    // reachable even when control hardware failed to initialise.
    // (The TCP/Serial-Studio path calls processLine() directly.)
    if (commands::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] commands service error"));
    }

    // ── Per-tick module service ───────────────────────────────────────────
    // Each call returns a ServiceStatus.  SERVICE_ERROR is logged; all
    // modules are still serviced regardless so the control loop keeps running.
    // Silence SERVICE_SKIPPED — it is the normal outcome for time-gated modules.
    //
    // Mock mode is handled inside each module: when sensor_mock::isActive(),
    // read() / service() pull values from sensor_mock::get() and skip hardware
    // access entirely.  No conditional logic is needed here.

    if (sysinfo::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] sysinfo service error"));
    }
    if (imu::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] imu service error"));
    }
    if (amplifier::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] amplifier service error"));
    }
    if (cooling::Module::service() == module::MODULE_SERVICE_ERROR) {
        Serial.println(F("[loop] cooling service error"));
    }

    const uint32_t nowMs = millis();

    // Indicator LEDs update every loop for accurate flash timing
    indicator::update(nowMs);

    // Main control tick at LOOP_INTERVAL_MS cadence
    if ((nowMs - previousLoopMs) < LOOP_INTERVAL_MS) {
        return;
    }
    previousLoopMs = nowMs;

    // ---- 1. Read sensors ------------------------------------------------
    // Advance any active mock ramps before module reads, so that every module
    // sees the updated value on the same tick.
    sensor_mock::service(nowMs);

    // Each module handles mock mode internally: when sensor_mock::isActive(),
    // read()/service() pulls from sensor_mock::get() instead of hardware.
    cold_head::read(nowMs);
    cold_head::checkFaults();

    // Read cached values.
    const float tempK       = cold_head::getLastTempK();
    const float tempC       = cold_head::getLastTempC();
    const float coolingRate = cold_head::getCoolingRateKPerMin();
    const bool  stalled     = cold_head::isStalled();
    const float rmsV        = amplifier::getLastRmsVoltage();
    const bool  overstroke  = imu::hasOverstroke();
    const float sysVoltage  = sysinfo::getVoltage();

    // ---- 2. Advance state machine ---------------------------------------
    const auto out = state_machine::update(tempK, coolingRate, rmsV, stalled, nowMs, overstroke, sysVoltage);
    // Clear edge-triggered overstroke flag after the state machine has consumed
    // it.  In real mode the flag was set by readCurrent(); in mock mode it was
    // set by setLastReadings().  Either way, clear it so it fires only once.
    if (overstroke) { imu::clearOverstroke(); }

    // ---- 3. Drive actuators ---------------------------------------------
    relay::setBypass(!out.bypassRelay);   // setBypass(true) = Normal
    relay::setAlarm(out.alarmRelay);

    indicator::setFaultMode(out.faultIndMode);
    indicator::setReadyMode(out.readyIndMode);

    // DAC ramping is driven by state_machine::update() directly — either on
    // state entry (via on_enter callbacks) or per-tick for states with a
    // dynamic target (CoarseCooldown, FineCooldown, Shutdown).

    // ---- 4. HTTP API ---------------------------------------------------
    //http_api::service();

    // ---- 5. Telemetry ---------------------------------------------------
    telemetry::emit(out);
    logger::logTelemetry(telemetry::getLastFrame());
    dashboard::Module::service();
}
