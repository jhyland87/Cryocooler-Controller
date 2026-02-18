/**
 * @file config.h
 * @brief Application configuration for sensor and peripheral settings
 *
 * Tunable parameters for the RTD sensor, waveform generator,
 * serial output, and timing. Pin assignments live in pin_config.h.
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

// =============================================================================
// Serial
// =============================================================================
#define SERIAL_BAUD       static_cast<uint32_t>(115200)

// =============================================================================
// RTD Sensor (MAX31865)
// =============================================================================

// Reference resistor on the MAX31865 breakout
// Use 430.0 for PT100, 4300.0 for PT1000 (adjust to measured value)
#define RTD_RREF          435.3f

// Nominal 0 °C resistance of the RTD element
// Use 100.0 for PT100, 1000.0 for PT1000
#define RTD_RNOMINAL      100.0f

// Wire configuration: MAX31865_2WIRE, MAX31865_3WIRE, or MAX31865_4WIRE
#define RTD_WIRE_CONFIG   MAX31865_2WIRE

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================
#define AD9833_FREQ_HZ    static_cast<uint16_t>(60)    // Output frequency in Hz

// =============================================================================
// MCP4921 12-bit DAC
// =============================================================================
#define MCP4921_MAX_VALUE  static_cast<uint16_t>(4095)  // 12-bit full scale
#define MCP4921_SPI_SPEED  static_cast<uint32_t>(20000000)  // 20 MHz SPI clock

// =============================================================================
// ADC
// =============================================================================
#define ADC_RESOLUTION    static_cast<uint8_t>(8)     // ADC read resolution in bits

// =============================================================================
// Timing
// =============================================================================
#define LOOP_INTERVAL_MS  static_cast<uint32_t>(1000)  // Main loop read interval (ms)

#endif // CONFIG_H
