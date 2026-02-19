/**
 * @file waveform.cpp
 * @brief AD9833 DDS waveform generator implementation
 */

#include <Arduino.h>
#include <MD_AD9833.h>
#include <FastLED.h>

#include "pin_config.h"
#include "config.h"
#include "waveform.h"

// Module-private generator instance
static MD_AD9833 ad9833(AD9833_CS);

namespace waveform {

static constexpr uint8_t kStatusLedCount = 1;
static constexpr uint8_t kStatusLedDataPin = 48; // Common for onboard RGB on ESP32-S3
static CRGB statusLeds[kStatusLedCount];

void init() {
  FastLED.addLeds<WS2812, kStatusLedDataPin, GRB>(statusLeds, kStatusLedCount);
  FastLED.setBrightness(0);
  FastLED.show();

  ad9833.begin();
  ad9833.setMode(MD_AD9833::MODE_SINE);
  ad9833.setFrequency(MD_AD9833::CHAN_0, AD9833_FREQ_HZ);

  Serial.print("AD9833 initialized - Generating ");
  Serial.print(AD9833_FREQ_HZ);
  Serial.println(" Hz sine wave");
}

void statusError() {
  statusLeds[0] = CRGB::Red4;
  Serial.println("Showing RED");
  FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
  FastLED.show();
}

void statusOk() {
  statusLeds[0] = CRGB::Green4;
  Serial.println("Showing GREEN");
  FastLED.setBrightness(WAVE_STATUS_LED_BRIGHTNESS);
  FastLED.show();
}

void statusOff() {
  FastLED.setBrightness(0);
  FastLED.show();
}

} // namespace waveform
