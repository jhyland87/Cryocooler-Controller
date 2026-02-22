/**
 * @file dac.cpp
 * @brief MCP4921 12-bit SPI DAC implementation
 *
 * MCP4921 16-bit SPI packet format:
 *   [15]    ~A/B   : 0 = DAC A (only channel on MCP4921)
 *   [14]    BUF    : 1 = Buffered Vref
 *   [13]    ~GA    : 1 = 1x gain
 *   [12]    ~SHDN  : 1 = Output active
 *   [11:0]  D11-D0 : 12-bit data
 *
 * Control nibble = 0b0111 -> top 4 bits = 0x3000
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdint.h>

#include "pin_config.h"
#include "config.h"
#include "dac.h"

static uint16_t currentDacVal = 0;

// MCP4921 control bits: Write to DAC A | Buffered | Gain 1x | Active
static constexpr uint16_t MCP4921_CTRL_BITS = 0x3000;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static void writeSpi(uint16_t dacVal) {
    if (dacVal > MCP4921_MAX_VALUE) {
        dacVal = MCP4921_MAX_VALUE;
    }
    if (currentDacVal == dacVal) return;

    currentDacVal = dacVal;

    const uint16_t packet = MCP4921_CTRL_BITS | dacVal;
    SPI.beginTransaction(SPISettings(MCP4921_SPI_SPEED, MSBFIRST, SPI_MODE0));
    digitalWrite(MCP4921_CS, LOW);
    SPI.transfer16(packet);
    digitalWrite(MCP4921_CS, HIGH);
    SPI.endTransaction();
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace dac {

void init() {
    pinMode(MCP4921_CS, OUTPUT);
    digitalWrite(MCP4921_CS, HIGH);
    writeSpi(0);
}

void update(uint16_t dacVal) {
    writeSpi(dacVal);
}

void rampToward(uint16_t target) {
    if (target > MCP4921_MAX_VALUE) {
        target = MCP4921_MAX_VALUE;
    }

    uint16_t next = currentDacVal;

    if (next < target) {
        const uint16_t step = target - next;
        next += (step > DAC_MAX_STEP_PER_INTERVAL) ? DAC_MAX_STEP_PER_INTERVAL : step;
    } else if (next > target) {
        const uint16_t step = next - target;
        next -= (step > DAC_MAX_STEP_PER_INTERVAL) ? DAC_MAX_STEP_PER_INTERVAL : step;
    }

    writeSpi(next);
}

uint16_t getCurrent() {
    return currentDacVal;
}

} // namespace dac
