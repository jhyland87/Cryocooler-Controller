/**
 * @file main.cpp
 * @brief ESP32 application entry point
 *
 * Initializes all peripherals and runs the main non-blocking loop.
 * Each subsystem is implemented in its own module — see the
 * corresponding header files for API details.
 *
 * Required Libraries:
 *   - Adafruit MAX31865  (PlatformIO / Arduino Library Manager)
 *   - MD_AD9833          (PlatformIO / Arduino Library Manager)
 */

#include <Arduino.h>
#include <SPI.h>

#include "config.h"
#include "temperature.h"
#include "pin_config.h"
#include "waveform.h"
#include "dac.h"

// =============================================================================
// Timing State
// =============================================================================
static uint32_t previousMillis = 0;

// =============================================================================
// Setup
// =============================================================================
void setup() {
  Serial.begin(SERIAL_BAUD);

  while (!Serial) delay(10);

  Serial.println("MAX31865 RTD + AD9833 Waveform Generator");
  Serial.println("=========================================");

  analogReadResolution(ADC_RESOLUTION);

  // Shared SPI bus
  SPI.begin();

  // Initialize subsystems
  temperature_init();
  waveform_init();

  Serial.println();
  delay(500);
}

// =============================================================================
// Main Loop
// =============================================================================
void loop() {
  const uint32_t currentMillis = millis();

  if (currentMillis - previousMillis >= LOOP_INTERVAL_MS) {
    previousMillis = currentMillis;

    temperature_read();
    temperature_checkFaults();

    const uint16_t dacVal = static_cast<uint16_t>(analogRead(DAC_VOLTAGE_PIN));
    dac_update(dacVal);

    Serial.println();
  }

  // AD9833 runs autonomously — no per-loop action needed.
}
