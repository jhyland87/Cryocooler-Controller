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

// MCP23S08 SPI GPIO expander — SPI mode 0 on the shared SPI bus. See the
// EXPANDER_PIN_* map below. RESET is tied high; INT is not wired to the MCU.
#define EXPANDER_CS_PIN    8

// MCP4921 SPI DAC — amplitude control (shares SPI bus with AD9833)
#define MCP4921_CS         5

// INA239 power monitor — SPI mode 1 on the shared SPI bus (MISO is Hi-Z when CS is high).
// GPIO3 is a strapping pin (JTAG source); the 10 kΩ CS pull-up keeps it high at reset,
// which selects the default USB-JTAG.
#define INA239_CS          3

// ADS1220 RTD ADC — SPI mode 1 on the shared SPI bus (DOUT is Hi-Z when CS is high).
// GPIO44 is U0RXD; the console is native USB CDC, so UART0 is unused.
// DRDY is not wired to the MCU.
#define ADS1220_CS         44

// LSM6DSOX IMU — Adafruit breakout (product 4438) mounted on the cryocooler and
// cabled to header J14; SPI on the shared bus (AD9833, MCP4921, ...).
#define LSM6DSOX_CS        1    // J14 pin 6
#define LSM6DSOX_INT1_PIN  2    // J14 pin 7
#define LSM6DSOX_INT2_PIN  39   // J14 pin 8

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================
#define AD9833_CS          7    // Chip Select for AD9833

// =============================================================================
// Discrete Indicator Outputs
// =============================================================================
// The FAULT and READY LEDs are on the GPIO expander (EXPANDER_PIN_FAULT_IND and
// EXPANDER_PIN_READY_IND, active HIGH).  The WS2812 (STATUS_LED_PIN) still
// works if the expander or SPI bus is down.

// Compressor relay driver (active HIGH): BSS138 + BSS84 high-side switch puts
// +12 V on the compressor relay terminal (130 mA max).  GPIO16 used to carry
// the optional LTC2954 INT# line, which is no longer wired to the MCU.
#define COMPRESSOR_RELAY_PIN 16

// Power kill switch (active LOW).
#define PWR_KILL_PIN      10

// =============================================================================
// SPI Bus (AD9833, MCP4921, LSM6DSOX, INA239, ADS1220, MCP23S08)
// =============================================================================
// Why am I not using values from /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32s3/pins_arduino.h?
// or /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32_s3r8n16/pins_arduino.h
#define SPI_MISO          40    // Master In Slave Out  (read by the LSM6DSOX, INA239 and ADS1220)
#define SPI_MOSI          41    // Master Out Slave In  (MCP4921 SDI + AD9833 SDATA + LSM6DSOX SDI + INA239 MOSI)
#define SPI_CLK           42    // SPI Clock


// ACS37800 Power Monitor — dedicated SPI3 bus (SPI3_HOST)
// Separate bus required: ACS37800 keeps MISO driven when CS is HIGH.
// CS is GPIO17, not GPIO43: GPIO43 is U0TXD and toggles with ROM boot messages at reset.
#define ACS37800_CS        17
#define ACS37800_SPI_CLK   11
#define ACS37800_SPI_MOSI  12
#define ACS37800_SPI_MISO  13
// =============================================================================
// Alphacool ES High Flow + Temperature Sensor
// =============================================================================

// Hall-effect flow pulse input (open-drain, active LOW).
// Requires a 10 kΩ pull-up to 3.3 V on the line; the internal INPUT_PULLUP
// is used as a backup but an external resistor is strongly recommended.
#define COOLING_FLOW_PIN         18

// Fan and pump 4-pin PWM outputs, each through a BSS138: GPIO high pulls the
// PWM line low (0 % drive).  The line can sit at up to 5.25 V, so it must not
// connect to a GPIO directly.  A 10 kΩ gate pull-up holds 0 % drive during boot.
#define COOLING_FAN_PWM_PIN      9
#define COOLING_PUMP_PWM_PIN     14

// Fan and pump tach inputs (open collector, 2 pulses per revolution), pulled up
// to 3.3 V at the connector, with a 1 kΩ series resistor to the GPIO.
#define COOLING_FAN_TACH_PIN     15
#define COOLING_PUMP_TACH_PIN    21

// ADC input for the NTC coolant temperature sensor.
// Wiring: 3.3 V → 10 kΩ (ref) → GPIO → NTC sensor → GND
// Use ADC1 channels only (GPIO 1–10 on ESP32-S3) to avoid ADC2 Wi-Fi conflicts.
#define COOLING_TEMP_ADC_PIN     4    // GPIO4 = ADC1-3

// =============================================================================
// On-board WS2812 RGB Status LED
// =============================================================================
#define STATUS_LED_PIN     RGB_LED_PIN   // Common for on-board RGB on ESP32-S3 DevKit


// =============================================================================
// Amplifier Relay — GPIO-driven (active HIGH closes relay)
// =============================================================================
#define AMPLIFIER_RELAY_PIN          6

// =============================================================================
// +-15 V power good (active LOW)
// =============================================================================
// Low when both LT3097 outputs are in regulation. The hardware already blocks
// AMP_REM while it is high; read it before starting the signal generator.
// GPIO43 is U0TXD (it toggles with ROM boot messages), behind a 1 kOhm series
// resistor; the console is native USB CDC, so UART0 is otherwise unused.
#define PG_15V_N_PIN                 43

// =============================================================================
// Display (Phoenix 2.4" touch display in the UCS 125-87 lid: ST7789V, 4-wire
// SPI half duplex on the shared bus) and its TSC2046 touch controller
// =============================================================================
// GPIO45 and GPIO46 are strapping pins; 10 kOhm pull-downs hold their default
// (low) levels at reset, so TOUCH_CS must be driven HIGH before any SPI
// traffic and the display stays in reset until the firmware releases it.
#define DISP_CS_PIN                  47
#define DISP_DC_PIN                  48
#define DISP_RST_PIN                 46
#define TOUCH_CS_PIN                 45

// =============================================================================
// MCP23S08 expander pins (read / written over SPI, see gpio_expander.h)
// =============================================================================
#define EXPANDER_PIN_PGP_15V         0   // input: LT3097 +15 V power good
#define EXPANDER_PIN_PGN_15V         1   // input: LT3097 -15 V power good
#define EXPANDER_PIN_PGP_16V5        2   // input: LT8582 +16.4 V power good (PG1)
#define EXPANDER_PIN_PGN_16V5        3   // input: LT8582 -16.5 V power good (PG2)
#define EXPANDER_PIN_DISP_BL         4   // output: display backlight enable
#define EXPANDER_PIN_READY_IND       5   // output: READY LED (active HIGH)
#define EXPANDER_PIN_FAULT_IND       6   // output: FAULT LED (active HIGH)
#define EXPANDER_PIN_SPARE           7   // input with weak pull-up, not wired

// =============================================================================




#endif // PIN_CONFIG_H
