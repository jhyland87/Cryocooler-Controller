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
#include <FastLED.h>
#include <SmoothADC.h>

#include "config.h"
#include "temperature.h"
#include "pin_config.h"
#include "waveform.h"
#include "dac.h"


#define NUM_LEDS 1
#define DATA_PIN 48 // Common for onboard RGB on ESP32-S3
CRGB leds[NUM_LEDS];

static SmoothADC dacVoltageAdc;

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

  analogReadResolution(ADC_RESOLUTION);

  // Shared SPI bus with custom pins
  SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

  // Smooth the DAC voltage readback ADC to reduce noise/spikes.
  // SmoothADC needs a few samples before it reports a filtered value,
  // so we "prime" it here to avoid a 0 reading on first loop pass.
  dacVoltageAdc.init(DAC_VOLTAGE_PIN, TB_MS, DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);
  dacVoltageAdc.enable();
  dacVoltageAdc.setPeriod(0);
  for (uint8_t i = 0; i < DAC_VOLTAGE_ADC_SMOOTH_PRIME_SAMPLES; i++) {
    dacVoltageAdc.serviceADCPin();
  }
  dacVoltageAdc.setPeriod(DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS);


  FastLED.addLeds<WS2812, DATA_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(0);
  //pinMode(VOLTAGE_12_TEST_PIN, INPUT);

  waveform_init();
  // Initialize subsystems
  temperature_init();
  dac_init();

  Serial.println();
  delay(500);
}

void wave_status_led_red() {
  leds[0] = CRGB::Red4; // Set color to Red
  Serial.println("Showing RED");
  FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
  FastLED.show();
}

void wave_status_led_green() {
  leds[0] = CRGB::Green4; // Set color to Red
  Serial.println("Showing GREEN");
  FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
  FastLED.show();
}

void wave_status_led_off(){
  FastLED.setBrightness(0);
  FastLED.show();
}

// =============================================================================
// Main Loop
// =============================================================================
void loop() {
  dacVoltageAdc.serviceADCPin();

  const uint32_t currentMillis = millis();

  if (currentMillis - previousMillis >= LOOP_INTERVAL_MS) {
    previousMillis = currentMillis;

    uint16_t pinValue = analogRead(VOLTAGE_12_TEST_PIN);
    uint16_t voltage12 = map(pinValue, 0, 2470, 0, 12); // Map the value to the new range (0-255
    Serial.printf("pinValue: %u (%dV)\n", pinValue, voltage12);

    const uint16_t dacVal = dacVoltageAdc.getADCVal();
    Serial.printf("DAC read voltage: %u\n", dacVal);
    if ( dacVal < ADC_MIN_VOLTAGE ){
      wave_status_led_off();
      return ;
    }

    if ( voltage12 < 11) {
      Serial.printf("Voltage too low to read temp. (%d)\n", voltage12);
      wave_status_led_red();
      return ;
    }

    wave_status_led_green();
    temperature_read();
    temperature_checkFaults();


    dac_update(dacVal);


    Serial.printf("DAC set voltage: %u\n", dacVoltageAdc.getADCVal());

    Serial.println();
  }

  // AD9833 runs autonomously — no per-loop action needed.
}

