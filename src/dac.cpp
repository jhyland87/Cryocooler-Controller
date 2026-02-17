/**
 * @file dac.cpp
 * @brief DAC output control driven by ADC feedback
 */

#include <Arduino.h>
#include <stdint.h>

#include "pin_config.h"
#include "dac.h"

void dac_update() {
  const uint16_t dacVal = static_cast<uint16_t>(analogRead(DAC_VOLTAGE_PIN));
  Serial.printf("DAC_VOLTAGE_PIN: %u\n", dacVal);

  if (dacVal == 0) {
    dacDisable(DAC_PIN);
    pinMode(DAC_PIN, OUTPUT);
    digitalWrite(DAC_PIN, LOW);
  } else {
    dacWrite(DAC_PIN, static_cast<uint8_t>(dacVal));
  }
}
