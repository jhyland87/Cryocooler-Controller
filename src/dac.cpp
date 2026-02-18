/**
 * @file dac.cpp
 * @brief MCP4921 12-bit SPI DAC implementation
 *
 * MCP4921 16-bit SPI packet format:
 *   [15]    ~A/B   : 0 = DAC A (only channel on MCP4921)
 *   [14]    BUF    : 1 = Buffered Vref
 *   [13]    ~GA    : 1 = 1x gain
 *   [12]    ~SHDN  : 1 = Output active
 *   [11:0]  D11–D0 : 12-bit data
 *
 * Control nibble = 0b0111 = 0x3 → top 4 bits = 0x3000
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdint.h>

#include "pin_config.h"
#include "config.h"
#include "dac.h"

static uint16_t currentDacVal = 0;

// MCP4921 control bits: Write to DAC A | Buffered | Gain 1x | Active
static constexpr uint16_t MCP4921_CTRL = 0x3000;

void dac_init() {
  pinMode(MCP4921_CS, OUTPUT);
  digitalWrite(MCP4921_CS, HIGH);

  // Set output to 0 on startup
  dac_update(0);
}

void dac_update(uint16_t dacVal) {
  // Clamp to 12-bit range
  if (dacVal > MCP4921_MAX_VALUE) {
    dacVal = MCP4921_MAX_VALUE;
  }

  if (currentDacVal == dacVal) return;
  currentDacVal = dacVal;

  Serial.printf("Setting DAC to: %u\n", dacVal);

  const uint16_t packet = MCP4921_CTRL | dacVal;

  SPI.beginTransaction(SPISettings(MCP4921_SPI_SPEED, MSBFIRST, SPI_MODE0));
  digitalWrite(MCP4921_CS, LOW);
  SPI.transfer16(packet);
  digitalWrite(MCP4921_CS, HIGH);
  SPI.endTransaction();
}
