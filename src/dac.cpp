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

/**
 * Rate-limited ramp toward target using the specified step size.
 *
 * @param target    Desired 12-bit output value (0-4095)
 * @param maxStep   Maximum step size per call (e.g., DAC_MAX_STEP_PER_INTERVAL)
 */
static void rampTowardInternal(uint16_t target, uint16_t maxStep) {
    if (target > MCP4921_MAX_VALUE) {
        target = MCP4921_MAX_VALUE;
    }

    uint16_t next = currentDacVal;

    if (next < target) {
        const uint16_t step = target - next;
        next += (step > maxStep) ? maxStep : step;
    } else if (next > target) {
        const uint16_t step = next - target;
        next -= (step > maxStep) ? maxStep : step;
    }

    writeSpi(next);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace dac {

module::InitStatus init() {
    pinMode(MCP4921_CS, OUTPUT);
    digitalWrite(MCP4921_CS, HIGH);
    writeSpi(0);
    return module::MODULE_INIT_SUCCESS;
}

void update(uint16_t dacVal) {
    writeSpi(dacVal);
}

void rampToward(uint16_t target) {
    rampTowardInternal(target, DAC_MAX_STEP_PER_INTERVAL);
}

void rampTowardShutdown(uint16_t target) {
    rampTowardInternal(target, DAC_SHUTDOWN_STEP_PER_INTERVAL);
}

uint16_t getCurrent() {
    return currentDacVal;
}

} // namespace dac
