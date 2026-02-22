/**
 * @file pin_config.h
 * @brief Pin assignments for ESP32-S3 peripherals
 *
 * Central location for all GPIO and SPI pin definitions.
 * Update this file when changing wiring or board layout.
 *
 * Relay and indicator pins marked TODO must be wired to the actual
 * hardware and assigned before deployment.
 */

#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

// =============================================================================
// SPI Bus (shared by MAX31865, AD9833, and MCP4921)
// =============================================================================
// Why am I not using values from /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32s3/pins_arduino.h?
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
#define AD9833_CS          7    // Chip Select for AD9833

// =============================================================================
// MCP4921 12-bit DAC (SPI)
// =============================================================================
#define MCP4921_CS         6    // Chip Select for MCP4921 DAC
#define DAC_VOLTAGE_PIN    9    // ADC input to read back DAC-controlled voltage

// =============================================================================
// 12 V Rail Monitor
// =============================================================================
#define VOLTAGE_12_TEST_PIN  13   // ADC input - voltage divider on 12 V rail

// =============================================================================
// Relays
// =============================================================================

// Bypass relay - driven HIGH to switch to Normal mode (states 5-7).
// Driven LOW (or not driven) = Bypass mode (default / safe state).
// TODO: assign to actual wired GPIO before deployment.
#define BYPASS_RELAY_PIN   10

// Alarm relay - driven HIGH in Fault state (8) to signal an external alarm.
// TODO: assign to actual wired GPIO before deployment.
#define ALARM_RELAY_PIN    11

// =============================================================================
// Discrete Indicator Outputs
// =============================================================================
// Optional digital outputs for separate FAULT and READY LEDs.
// If not wired, the on-board WS2812 (STATUS_LED_PIN) acts as the sole indicator.

// FAULT indicator (active HIGH).
// TODO: assign to actual wired GPIO before deployment.
#define FAULT_IND_PIN      12

// READY indicator (active HIGH).
// TODO: assign to actual wired GPIO before deployment.
// NOTE: previously 14; reassigned to ACS712_CURRENT_PIN — update wiring accordingly.
#define READY_IND_PIN      15

// =============================================================================
// ACS712 AC Current Sensor (back-EMF / overstroke detection)
// =============================================================================
// Analog output of the ACS712-05B 5 A module connected to the AC output line
// (post-amplifier, 0–120 V AC).  If the module is powered from 5 V, install
// a resistor divider (e.g. 3.3 kΩ / 6.8 kΩ) on the output so the signal
// stays within the ESP32-S3 ADC input range of 0–3.3 V.
#define ACS712_CURRENT_PIN 14

// =============================================================================
// On-board WS2812 RGB Status LED
// =============================================================================
#define STATUS_LED_PIN     48   // Common for on-board RGB on ESP32-S3 DevKit

#define ONE_WIRE_BUS  4



#endif // PIN_CONFIG_H
