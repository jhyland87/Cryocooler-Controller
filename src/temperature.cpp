/**
 * @file temperature.cpp
 * @brief MAX31865 RTD temperature sensor implementation
 */

#include <Arduino.h>
#include <Adafruit_MAX31865.h>

#include "pin_config.h"
#include "config.h"
#include "temperature.h"
#include "conversions.h"

// Module-private sensor instance
static Adafruit_MAX31865 max31865(MAX31865_CS);

void temperature_init() {
  if (!max31865.begin(RTD_WIRE_CONFIG)) {
    Serial.println("Could not initialize MAX31865! Check wiring.");
    while (true) delay(10);
  }
  Serial.println("MAX31865 initialized successfully!");
}

void temperature_read() {
  const uint16_t rtd        = max31865.readRTD();
  const float    resistance = rtdRawToResistance(rtd, RTD_RREF);
  const float    tempC      = max31865.temperature(RTD_RNOMINAL, RTD_RREF);
  const float    tempF      = celsiusToFahrenheit(tempC);

  Serial.print("RTD Value: ");
  Serial.print(rtd);
  Serial.print("\t Resistance: ");
  Serial.print(resistance, 2);
  Serial.print(" Ω\t Temperature: ");
  Serial.print(tempC, 2);
  Serial.print(" °C / ");
  Serial.print(tempF, 2);
  Serial.println(" °F");
}

void temperature_checkFaults() {
  const uint8_t fault = max31865.readFault();
  if (fault == 0) return;

  Serial.print("Fault detected! Code: 0x");
  Serial.println(fault, HEX);

  if (fault & MAX31865_FAULT_HIGHTHRESH)  Serial.println("  - RTD High Threshold");
  if (fault & MAX31865_FAULT_LOWTHRESH)   Serial.println("  - RTD Low Threshold");
  if (fault & MAX31865_FAULT_REFINLOW)    Serial.println("  - REFIN- > 0.85 x Bias");
  if (fault & MAX31865_FAULT_REFINHIGH)   Serial.println("  - REFIN- < 0.85 x Bias - FORCE- open");
  if (fault & MAX31865_FAULT_RTDINLOW)    Serial.println("  - RTDIN- < 0.85 x Bias - FORCE- open");
  if (fault & MAX31865_FAULT_OVUV)        Serial.println("  - Under/Over voltage");

  max31865.clearFault();
}
