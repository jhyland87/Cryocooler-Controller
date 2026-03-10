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

// =============================================================================
// MAX31865 RTD Sensor
// =============================================================================
#define MAX31865_CS        1    // Chip Select for MAX31865 PT100

// =============================================================================
// One-Wire Bus for DS18B20 temperature sensor
// =============================================================================
//#define ONE_WIRE_BUS      4


#define SDA_PIN            8
#define SCL_PIN            9


// MCP4921_CS (GPIO 6) removed — DAC is now MCP4725 on the shared I2C bus
// (SDA = GPIO 8, SCL = GPIO 9).  GPIO 6 is available for other use.

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================
#define AD9833_CS          7    // Chip Select for AD9833


#define SD_CS_PIN          48

// Card Detect switch on the SD socket (active HIGH — HIGH = card present).
// The switch drives this pin HIGH when a card is fully seated; the internal
// pull-down holds it LOW when the slot is empty.  Adjust if your socket routes
// CD to a different GPIO.
#define SD_CD_PIN          47


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
// SPI Bus (shared by MAX31865 and AD9833)
// =============================================================================
// Why am I not using values from /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32s3/pins_arduino.h?
// or /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32_s3r8n16/pins_arduino.h
#define SPI_CLK           42    // SPI Clock
#define SPI_MISO          41    // Master In Slave Out
#define SPI_MOSI          40    // Master Out Slave In

// =============================================================================
// Alphacool ES High Flow + Temperature Sensor
// =============================================================================

// Hall-effect flow pulse input (open-drain, active LOW).
// Requires a 10 kΩ pull-up to 3.3 V on the line; the internal INPUT_PULLUP
// is used as a backup but an external resistor is strongly recommended.
#define COOLING_FLOW_PIN         4

// ADC input for the NTC coolant temperature sensor.
// Wiring: 3.3 V → 10 kΩ (ref) → GPIO → NTC sensor → GND
// Use ADC1 channels only (GPIO 1–10 on ESP32-S3) to avoid ADC2 Wi-Fi conflicts.
#define COOLING_TEMP_ADC_PIN     3

// =============================================================================
// On-board WS2812 RGB Status LED
// =============================================================================
#define STATUS_LED_PIN     RGB_LED_PIN   // Common for on-board RGB on ESP32-S3 DevKit

// =============================================================================
// PCAL9535A I2C GPIO Expander — compressor relay
// =============================================================================
// I2C address is determined by the A0/A1/A2 hardware strapping pins on the
// PCAL9535A.  Adjust HardwareAddress to match your board wiring.
#define COMPRESSOR_RELAY_PCAL_ADDR   PCAL9535A::HardwareAddress::A000
// GPIO pin on the expander (0–15) wired to the relay coil.
#define COMPRESSOR_RELAY_PIN         static_cast<uint8_t>(0)

// =============================================================================
// PCAL9535A I2C GPIO Expander — amplifier relay
// =============================================================================
// Same PCAL9535A device as the compressor relay (both at A000 / 0x20).
// Compressor uses pin 0; amplifier uses pin 1.
#define AMPLIFIER_RELAY_PCAL_ADDR    PCAL9535A::HardwareAddress::A000
// GPIO pin on the expander (0–15) wired to the relay coil.
#define AMPLIFIER_RELAY_PIN          static_cast<uint8_t>(1)

// =============================================================================




#endif // PIN_CONFIG_H
