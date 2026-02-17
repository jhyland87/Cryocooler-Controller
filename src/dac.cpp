/**
 * @file dac.cpp
 * @brief DAC output control driven by ADC feedback
 */

#include <Arduino.h>
#include <stdint.h>

#include "pin_config.h"
#include "dac.h"

uint16_t currentDacVal = 0;

void dac_update(uint16_t dacVal) {
  if ( currentDacVal == dacVal ) return;
  currentDacVal = dacVal;

  Serial.printf("Setting DAC to: %u\n", dacVal);

  if (dacVal == 0) {
    dacDisable(DAC_PIN);
    pinMode(DAC_PIN, OUTPUT);
    digitalWrite(DAC_PIN, LOW);
  } else {
    dacWrite(DAC_PIN, static_cast<uint8_t>(dacVal));
  }
}
