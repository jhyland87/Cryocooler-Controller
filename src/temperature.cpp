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

namespace temperature {

void init() {
  if (!max31865.begin(RTD_WIRE_CONFIG)) {
    Serial.println("Could not initialize MAX31865! Check wiring.");
    while (true) delay(10);
  }

  // begin() doesn't verify SPI communication — read back the config
  // register to confirm the chip is actually responding.
  // After begin(MAX31865_2WIRE), config register should read 0x80 or 0x00
  // (not 0xFF which indicates a disconnected MISO line).
  const uint16_t rtd = max31865.readRTD();
  const uint8_t  fault = max31865.readFault();
  Serial.printf("MAX31865 comms check — RTD raw: %u  Fault: 0x%02X\n", rtd, fault);

  if (rtd == 0 && fault == 0) {
    Serial.println("WARNING: MAX31865 may not be communicating (RTD=0, Fault=0).");
    Serial.println("Check CS, CLK, SDI, SDO wiring and 3.3V supply.");
  } else {
    Serial.println("MAX31865 initialized successfully!");
  }
}

void read() {
  const uint16_t rtd        = max31865.readRTD();
  const float    resistance = conversions::rtdRawToResistance(rtd, RTD_RREF);
  const float    tempC      = max31865.temperature(RTD_RNOMINAL, RTD_RREF);
  const float    tempF      = conversions::celsiusToFahrenheit(tempC);

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

void checkFaults() {
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

} // namespace temperature
