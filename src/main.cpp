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

  // Wait for USB-CDC serial port to connect (ESP32-S3 native USB).
  // Without this, all setup() output is lost before the monitor opens.
  while (!Serial) delay(10);

  Serial.println("MAX31865 RTD + AD9833 Waveform Generator");
  Serial.println("=========================================");

  //analogReadResolution(ADC_RESOLUTION);

  // Shared SPI bus with custom pins
  SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);


  //pinMode(VOLTAGE_12_TEST_PIN, INPUT);

  waveform_init();
  // Initialize subsystems
  temperature_init();
  dac_init();

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
    Serial.println("Loop");
    int pinValue = analogRead(VOLTAGE_12_TEST_PIN);
    int voltage12 = map(pinValue, 0, 2470, 0, 12); // Map the value to the new range (0-255
    Serial.printf("pinValue: %u (%dV)\n", pinValue, voltage12);

    if ( voltage12 < 11) {
      Serial.printf("Voltage too low to read temp. (%d)\n", voltage12);
      return ;
    }
    temperature_read();
    temperature_checkFaults();

    const uint16_t dacVal = static_cast<uint16_t>(analogRead(DAC_VOLTAGE_PIN));
    Serial.printf("DAC read voltage: %u\n", dacVal);
    dac_update(dacVal);

    Serial.printf("DAC set voltage: %u\n", analogRead(11));

    Serial.println();
  }

  // AD9833 runs autonomously — no per-loop action needed.
}

