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
// Shared SPI bus chip selects: SN74LVC138A decoder (U32)
// =============================================================================
// A/B/C pick the output and G2A enables it (10 kOhm pull-up holds it off at boot).
// GPIO3 and GPIO45 are strapping pins: 10 kOhm resistors hold GPIO3 high (default
// USB-JTAG) and GPIO45 low at reset. GPIO44 is U0RXD; the console is native USB
// CDC, so UART0 is unused. GPIO5 and GPIO7 (3.3 V, ADC1) and GPIO47 (1.8 V only) are free.
#define CS_ADDR_A_PIN      3
#define CS_ADDR_B_PIN      44
#define CS_ADDR_C_PIN      45
#define CS_ENABLE_PIN      8

// *_CS values below are not GPIOs: src/spi_select.cpp catches these IDs in
// pinMode() and digitalWrite() and drives the decoder. ID - CS_ID_BASE is the
// output number. They must stay above RGB_BUILTIN (97) and fit an int8_t, which
// is how Adafruit BusIO stores CS.
#define CS_ID_BASE         100
#define CS_OUTPUT_COUNT    8

// MCP23S08 SPI GPIO expander — SPI mode 0 on the shared SPI bus. See the
// EXPANDER_PIN_* map below. RESET is tied high; INT is not wired to the MCU.
#define EXPANDER_CS_PIN    (CS_ID_BASE + 3)

// AD5453 14-bit multiplying DAC — amplitude control. SPI mode 1, writes only.
#define AD5453_SYNC        (CS_ID_BASE + 1)

// INA239 power monitor — SPI mode 1 on the shared SPI bus (MISO is Hi-Z when CS is high).
#define INA239_CS          (CS_ID_BASE + 2)

// ADS1220 RTD ADC — SPI mode 1 on the shared SPI bus (DOUT is Hi-Z when CS is high).
// DRDY is not wired to the MCU.
#define ADS1220_CS         (CS_ID_BASE + 6)

// LSM6DSOX IMU — Adafruit breakout (product 4438) mounted on the cryocooler and
// cabled to header J14; SPI on the shared bus (AD9833, AD5453, ...).
#define LSM6DSOX_CS        (CS_ID_BASE + 7)    // J14 pin 6
#define LSM6DSOX_INT1_PIN  2    // J14 pin 7
#define LSM6DSOX_INT2_PIN  39   // J14 pin 8

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================
#define AD9833_CS          (CS_ID_BASE + 0)    // Chip Select for AD9833

// Compressor relay driver (active HIGH): BSS138 + BSS84 high-side switch puts
// +12 V on the compressor relay terminal (130 mA max).
#define COMPRESSOR_RELAY_PIN 16

// LTC2954 power button handshake. INT# pulses low (32 ms minimum, 10 kOhm
// pull-up R8) when the button asks for power-off; driving KILL# low releases
// the supply. The LTC2954 cuts power by itself if the button is held 6.4 s.
#define PWR_INT_PIN       1
#define PWR_KILL_PIN      10

// =============================================================================
// SPI Bus (AD9833, AD5453, LSM6DSOX, INA239, ADS1220, MCP23S08, ST7789V, TSC2046)
// =============================================================================
// Why am I not using values from /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32s3/pins_arduino.h?
// or /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32_s3r8n16/pins_arduino.h
#define SPI_MISO          40    // Master In Slave Out  (read by the LSM6DSOX, INA239 and ADS1220)
#define SPI_MOSI          41    // Master Out Slave In  (AD5453 SDIN + AD9833 SDATA + LSM6DSOX SDI + INA239 MOSI)
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
// to 3.3 V at the connector, with a 4.7 kΩ series resistor and a clamp to the GPIO.
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
// GPIO46 is a strapping pin; a 10 kOhm pull-down holds its default (low) level at
// reset, so the display stays in reset until the firmware releases it.
#define DISP_CS_PIN                  (CS_ID_BASE + 4)
#define DISP_DC_PIN                  48
#define DISP_RST_PIN                 46
#define TOUCH_CS_PIN                 (CS_ID_BASE + 5)

// =============================================================================
// MCP23S08 expander pins (read / written over SPI, see gpio_expander.h)
// =============================================================================
#define EXPANDER_PIN_PGP_15V         0   // input: LT3097 +15 V power good
#define EXPANDER_PIN_PGN_15V         1   // input: LT3097 -15 V power good
#define EXPANDER_PIN_SPARE_2         2   // input with weak pull-up, not wired
#define EXPANDER_PIN_SPARE_3         3   // input with weak pull-up, not wired
#define EXPANDER_PIN_DISP_BL         4   // output: display backlight enable
#define EXPANDER_PIN_SPARE_5         5   // input with weak pull-up, not wired
#define EXPANDER_PIN_INA239_ALERT    6   // input: INA239 ALERT (active LOW, R9 pull-up)
#define EXPANDER_PIN_TOUCH_IRQ       7   // input: TSC2046 PENIRQ (active LOW, internal pull-up)

// =============================================================================




#endif // PIN_CONFIG_H
