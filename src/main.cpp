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
 *   - FastLED
 *   - SmoothADC
 *   - ESP32SerialCtl
 */

#include <Arduino.h>
#include <SPI.h>
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
#include "serial_commands.h"

// =============================================================================
// Module-level objects
// =============================================================================

static SmoothADC dacVoltageAdc;

// =============================================================================
// Timing state
// =============================================================================

static uint32_t sPreviousLoopMs = 0;

// =============================================================================
// Setup
// =============================================================================

void setup() {
    Serial.begin(SERIAL_BAUD);

    // Wait for USB-CDC serial port (ESP32-S3 native USB).
    while (!Serial) delay(10);

    Serial.println("Cryocooler Controller -- starting up");
    Serial.println("=====================================");

    analogReadResolution(ADC_RESOLUTION);

    // Shared SPI bus
    SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

    // Smooth DAC voltage readback
    dacVoltageAdc.init(DAC_VOLTAGE_PIN, TB_MS, DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);
    dacVoltageAdc.enable();
    dacVoltageAdc.setPeriod(0);
    for (uint8_t i = 0; i < DAC_VOLTAGE_ADC_SMOOTH_PRIME_SAMPLES; ++i) {
        dacVoltageAdc.serviceADCPin();
    }
    dacVoltageAdc.setPeriod(DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);

    // Peripherals
    waveform::init();
    temperature::init();
    dac::init();
    rms::init();
    relay::init();
    indicator::init();

    // Kick off state machine in Off state
    state_machine::init(millis());

    // Initialise serial command handler (ESP32SerialCtl)
    serial_commands::init();

    Serial.println("Setup complete. System is Off.");
    Serial.println("Type 'help' for available commands.\n");
}

// =============================================================================
// Main Loop
// =============================================================================

void loop() {
    // Service smoothed ADC every iteration (non-blocking)
    dacVoltageAdc.serviceADCPin();

    const uint32_t nowMs = millis();

    // Process incoming serial commands (non-blocking)
    serial_commands::service();

    // Indicator LEDs update every loop for accurate flash timing
    indicator::update(nowMs);

    // Main control tick at LOOP_INTERVAL_MS cadence
    if ((nowMs - sPreviousLoopMs) < LOOP_INTERVAL_MS) {
        return;
    }
    sPreviousLoopMs = nowMs;

    // ---- 1. Read sensors ------------------------------------------------
    temperature::read(nowMs);
    rms::read();

    const float tempK       = temperature::getLastTempK();
    const float tempC       = temperature::getLastTempC();
    const float coolingRate = temperature::getCoolingRateKPerMin();
    const bool  stalled     = temperature::isStalled();
    const float rmsV        = rms::getVoltage();

    temperature::checkFaults();

    // ---- 2. Advance state machine ---------------------------------------
    const auto out = state_machine::update(tempK, coolingRate, rmsV, stalled, nowMs);

    // ---- 3. Drive actuators ---------------------------------------------
    relay::setBypass(!out.bypassRelay);   // setBypass(true) = Normal
    relay::setAlarm(out.alarmRelay);

    indicator::setFaultMode(out.faultIndMode);
    indicator::setReadyMode(out.readyIndMode);

    // Ramp DAC toward the state-machine target (rate-limited in dac.cpp)
    dac::rampToward(out.dacTarget);

    // ---- 4. Telemetry ---------------------------------------------------
    telemetry::emit(out, tempK, tempC, coolingRate, rmsV, dac::getCurrent(),
                    indicator::isFaultOn(), indicator::isReadyOn());
}
