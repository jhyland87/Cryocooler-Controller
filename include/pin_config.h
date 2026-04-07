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


#define RGB_LED_PIN 38

// I2C Bus 0 — shared bus for sensors, relays, power monitor
#define SDA_PIN            8
#define SCL_PIN            9

// MCP4921 SPI DAC — amplitude control (shares SPI bus with AD9833)
#define MCP4921_CS         5

// LSM6DSOX IMU — SPI (shares SPI bus with AD9833 and MCP4921)
#define LSM6DSOX_CS        1    // right header, physical pin 19
#define LSM6DSOX_INT1_PIN  2    // right header, physical pin 18
#define LSM6DSOX_INT2_PIN  39   // right header, physical pin 14

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================
#define AD9833_CS          7    // Chip Select for AD9833

// =============================================================================
// Discrete Indicator Outputs
// =============================================================================
// Optional digital outputs for separate FAULT and READY LEDs.
// If not wired, the on-board WS2812 (STATUS_LED_PIN) acts as the sole indicator.

// FAULT indicator (active HIGH).
// TODO: assign to actual wired GPIO before deployment.
#define FAULT_IND_PIN      13

// READY indicator (active HIGH).
// TODO: assign to actual wired GPIO before deployment.
// WARNING: do NOT use LED_BUILTIN here. On this board LED_BUILTIN resolves to
// RGB_BUILTIN (GPIO 48), and the ESP32 Arduino core's io_pin_remap.h silently
// redirects any digitalWrite() on RGB_BUILTIN to rgbLedWrite(), which fires
// the RMT peripheral and interferes with the real status LED on GPIO 38.
#define READY_IND_PIN      15



// =============================================================================
// SPI Bus (used by AD9833)
// =============================================================================
// Why am I not using values from /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32s3/pins_arduino.h?
// or /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32_s3r8n16/pins_arduino.h
#define SPI_MISO          40    // Master In Slave Out  (no SPI devices have SDO, but keep assigned)
#define SPI_MOSI          41    // Master Out Slave In  (MCP4921 SDI + AD9833 SDATA)
#define SPI_CLK           42    // SPI Clock

// =============================================================================
// Alphacool ES High Flow + Temperature Sensor
// =============================================================================

// Hall-effect flow pulse input (open-drain, active LOW).
// Requires a 10 kΩ pull-up to 3.3 V on the line; the internal INPUT_PULLUP
// is used as a backup but an external resistor is strongly recommended.
#define COOLING_FLOW_PIN         18

#define COOLING_FAN_FAULT_INDICATOR_PIN      14

// ADC input for the NTC coolant temperature sensor.
// Wiring: 3.3 V → 10 kΩ (ref) → GPIO → NTC sensor → GND
// Use ADC1 channels only (GPIO 1–10 on ESP32-S3) to avoid ADC2 Wi-Fi conflicts.
#define COOLING_TEMP_ADC_PIN     4    // moved from GPIO2 (now LSM6DSOX INT1); GPIO4 = ADC1-3

// =============================================================================
// On-board WS2812 RGB Status LED
// =============================================================================
#define STATUS_LED_PIN     RGB_LED_PIN   // Common for on-board RGB on ESP32-S3 DevKit

// =============================================================================
// SparkFun Qwiic Single Relay — compressor
// =============================================================================
// Default I2C address (0x18).  Jumper to 0x19 if address conflicts arise.
#define COMPRESSOR_RELAY_ADDR        0x19

// =============================================================================
// Amplifier Relay — GPIO-driven (active HIGH closes relay)
// =============================================================================
#define AMPLIFIER_RELAY_PIN          6

// =============================================================================




#endif // PIN_CONFIG_H
