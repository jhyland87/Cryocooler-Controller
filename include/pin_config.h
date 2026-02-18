/**
 * @file pin_config.h
 * @brief Pin assignments for ESP32 peripherals
 *
 * Central location for all GPIO and SPI pin definitions.
 * Update this file when changing wiring or board layout.
 */

#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

// =============================================================================
// SPI Bus (VSPI - shared by MAX31865 and AD9833)
// =============================================================================
#define SPI_MOSI          42    // Master Out Slave In
#define SPI_MISO          41    // Master In Slave Out
#define SPI_CLK           40    // SPI Clock

// =============================================================================
// MAX31865 RTD Sensor
// =============================================================================
#define MAX31865_CS        1    // Chip Select for MAX31865 PT100

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================
#define AD9833_CS         7    // Chip Select for AD9833

// =============================================================================
// MCP4921 12-bit DAC (SPI)
// =============================================================================
#define MCP4921_CS         6    // Chip Select for MCP4921 dac
#define DAC_VOLTAGE_PIN   11    // ADC input to read back DAC-controlled voltage

#define VOLTAGE_12_TEST_PIN 13


#endif // PIN_CONFIG_H
