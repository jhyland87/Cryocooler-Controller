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
#define SPI_MOSI          23    // Master Out Slave In
#define SPI_MISO          19    // Master In Slave Out
#define SPI_CLK           18    // SPI Clock

// =============================================================================
// MAX31865 RTD Sensor
// =============================================================================
#define MAX31865_CS        5    // Chip Select for MAX31865

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================
#define AD9833_CS         15    // Chip Select for AD9833

// =============================================================================
// DAC Output
// =============================================================================
#define DAC_PIN           25    // DAC output pin (GPIO25 = DAC1)
#define DAC_VOLTAGE_PIN   34    // ADC input to read back DAC-controlled voltage

// =============================================================================
// Reserved / Future Use (uncomment as needed)
// =============================================================================
// #define DAC12BIT_CS    XX    // MCP4921 12-bit DAC Chip Select

#endif // PIN_CONFIG_H
