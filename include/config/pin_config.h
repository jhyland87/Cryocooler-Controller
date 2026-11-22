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
// Shared SPI bus chip selects: 74HC154 4-to-16 decoder (U32)
// =============================================================================
// A/B/C/D pick the output and E0 enables it (10 kOhm pull-up holds it off at boot).
// GPIO3 and GPIO45 are strapping pins: 10 kOhm resistors hold GPIO3 high (default
// USB-JTAG) and GPIO45 low at reset. GPIO44 is U0RXD; the console is native USB
// CDC, so UART0 is unused. GPIO47 swings 1.8 V only, so address bit D reaches the
// decoder through a 74LV1T34 buffer whose input pull-down reads 0 while it floats.
#define CS_ADDR_A_PIN      3
#define CS_ADDR_B_PIN      44
#define CS_ADDR_C_PIN      45
#define CS_ADDR_D_PIN      47
#define CS_ENABLE_PIN      8

// *_CS values below are not GPIOs: src/spi_select.cpp catches these IDs in
// pinMode() and digitalWrite() and drives the decoder. ID - CS_ID_BASE is the
// output number. They must stay above RGB_BUILTIN (97) and fit an int8_t, which
// is how Adafruit BusIO stores CS.
#define CS_ID_BASE         100
#define CS_OUTPUT_COUNT    16

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
#define LSM6DSOX_CS        (CS_ID_BASE + 7)    // J14 pin 5

// ADT7320 ambient temperature sensor (U50) — SPI mode 3, MSB first, DOUT is released
// after CS rises. INT and CT (open drain, 10 kOhm pull-ups) go to expander GP2 and GP3.
#define AMBIENT_CS         (CS_ID_BASE + 8)
// IDs CS_ID_BASE + 9 to CS_ID_BASE + 15 are spare decoder outputs (Y9 to Y15).
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
// SPI Bus (AD9833, AD5453, LSM6DSOX, INA239, ADS1220, MCP23S08, ST7789V, TSC2046,
// ACS37800)
// =============================================================================
// Why am I not using values from /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32s3/pins_arduino.h?
// or /Users/justinhyland/.platformio/packages/framework-arduinoespressif32/variants/esp32_s3r8n16/pins_arduino.h
#define SPI_MISO          40    // Master In Slave Out  (read by the LSM6DSOX, INA239, ADS1220 and ACS37800)
#define SPI_MOSI          41    // Master Out Slave In  (AD5453 SDIN + AD9833 SDATA + LSM6DSOX SDI + INA239 MOSI)
#define SPI_CLK           42    // SPI Clock


// ACS37800 power monitor (U18, behind the U17 ISOW7741 isolator): SPI mode 3, LSB
// first, on the shared SPI bus. It keeps driving MISO while CS is high, so two
// SN74LVC1G125 gates with /OE on ACS_CS connect it only while CS is low: one passes
// SCK to the isolator, the other its MISO to the bus. A 10 kOhm pull-up holds CS
// high while the GPIO floats. CS is a plain GPIO, not a decoder ID.
// CS is GPIO17, not GPIO43: GPIO43 is U0TXD and toggles with ROM boot messages at reset.
#define ACS37800_CS        17

// =============================================================================
// General-purpose I/O headers (IO5, IO7, IO11, IO12, IO13)
// =============================================================================
// Each pin has a 100 Ohm series resistor, 200 kOhm to ground, an ESD clamp and an
// indicator LED whose brightness follows the pin voltage. Only GPIO5 and GPIO7 are
// ADC1 and can read analog with WiFi on; GPIO11 to GPIO13 are ADC2.
#define AUX_IO5_PIN        5
#define AUX_IO7_PIN        7
#define AUX_IO11_PIN       11
#define AUX_IO12_PIN       12
#define AUX_IO13_PIN       13

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
// Low when both +-15 V regulator outputs are in regulation. The hardware already blocks
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
#define EXPANDER_PIN_PGP_15V         0   // input: +15 V regulator power good
#define EXPANDER_PIN_PGN_15V         1   // input: -15 V regulator power good
#define EXPANDER_PIN_AMBIENT_INT     2   // input: ADT7320 INT (active LOW, R pull-up)
#define EXPANDER_PIN_AMBIENT_CT      3   // input: ADT7320 CT (active LOW, R pull-up)
#define EXPANDER_PIN_DISP_BL         4   // output: display backlight enable
#define EXPANDER_PIN_SPARE_5         5   // input with weak pull-up, not wired
#define EXPANDER_PIN_INA239_ALERT    6   // input: INA239 ALERT (active LOW, R9 pull-up)
#define EXPANDER_PIN_TOUCH_IRQ       7   // input: TSC2046 PENIRQ (active LOW, internal pull-up)

// =============================================================================
// Rev 5 board additions (schematic only so far: no firmware uses these yet)
// =============================================================================
// Not yet applied above, because the display and ACS37800 firmware change with
// them: on rev 5 ACS37800_CS is CS_ID_BASE + 5, the on-board display is gone
// (DISP_*, TOUCH_CS_PIN, EXPANDER_PIN_DISP_BL, EXPANDER_PIN_TOUCH_IRQ) and
// AUX_IO12_PIN is CAN_RX. IO_DAC_CS reuses the old display ID.
#define CAN_TX_PIN                   17  // TCAN3414 TXD (10 kOhm pull-up)
#define CAN_RX_PIN                   12  // TCAN3414 RXD

// Universal I/O (four channels): DAC60508 (SPI mode 1), ADS124S08 (SPI mode 1), two
// MCP23S17 (hardware addresses 0 and 1, one chip select).
#define IO_DAC_CS                    (CS_ID_BASE + 4)
#define IO_ADC_CS                    (CS_ID_BASE + 9)
#define IO_EXPANDER_CS               (CS_ID_BASE + 10)
// SC16IS750 UART for the RS-485 port: SPI mode 0, 4 MHz max.
#define RS485_UART_CS                (CS_ID_BASE + 11)
// SPI expansion header chip selects A and B. IDs + 14 and + 15 are spare.
#define EXPANSION_CS_A               (CS_ID_BASE + 12)
#define EXPANSION_CS_B               (CS_ID_BASE + 13)

// Channels 1 and 2 keep a GPIO: high passes the DAC level to the output driver (PWM),
// and with IOn_BUF_OE_N low the pin reads back through a buffer (pulse input).
#define IO_CH1_FAST_PIN              5
#define IO_CH2_FAST_PIN              7
// GPIO11 and GPIO13 go to the AUX header J40 on rev 6 (spare on rev 5), and on
// rev 6.1 also to the Qwiic / STEMMA QT header J41 (I2C: SDA GPIO11, SCL GPIO13).

// MCP23S17 port bits, one port per channel (expander k: port A = channel 2k + 1,
// port B = channel 2k + 2). Every line has a pull resistor to its off level.
#define IO_BIT_OUT_EN                0   // output: HIGH closes the output switch
#define IO_BIT_DIRECT                1   // output: HIGH = 0-2.5 V range, LOW = 0-15 V
                                         // (channels 2-4; channel 1 uses the pin below)
#define IO_BIT_BURDEN                2   // output: HIGH adds the 120 Ohm loop burden
#define IO_BIT_PULLUP                3   // output: HIGH adds 10 kOhm to 3.3 V
#define IO_BIT_SENS_EN               4   // output: HIGH turns the sensor supply on
#define IO_BIT_OUT_FLT_N             5   // input, channel 1 only: output switch fault for
                                         // channels 1-4 (active LOW)
#define IO_BIT_SENS_FLT_N            6   // input: sensor supply fault (active LOW)
#define IO_BIT_BUF_OE_N              7   // output, channels 1 and 2: LOW enables the pulse buffer
// Bit 7 of channels 3 and 4 (expander 1) carries two interrupts instead.
#define IO_EXPANDER1_PIN_RS485_IRQ   7   // port A, input: SC16IS750 IRQ (active LOW)
#define IO_EXPANDER1_PIN_HEADER_INT  15  // port B bit 7, input: expansion header INT (active LOW)
// Precision sensor ports A and B (load cell, O2 cell): ADS124S08 AIN8 / AIN9 and
// AIN10 / AIN11. Pressure ports 1 (100 psi) and 2 (30 psi): AIN4 and AIN5 against
// AINCOM. All four use the switched 5 V excitation, which is also REFP0 / REFN0.
#define IO_ADC_AIN_PRESSURE_1        4
#define IO_ADC_AIN_PRESSURE_2        5
// Bit 5 of channel 2 (expander 0 port B) and channel 3 (expander 1 port A):
#define IO_EXPANDER0_PIN_PREC_EXC_EN 13  // port B bit 5, output: HIGH turns the excitation on
#define IO_EXPANDER1_PIN_PREC_EXC_FLT 5  // port A bit 5, input: excitation fault (active LOW)
// Channel 1 DIRECT moved for routing: expander 1 port B bit 5. Expander 0 port A
// bit 1 is spare.
#define IO_EXPANDER1_PIN_CH1_DIRECT  13  // port B bit 5, output: HIGH = 0-2.5 V range

// MCP23S08 inputs added on rev 5 (replace DISP_BL and SPARE_5 above).
#define EXPANDER_PIN_IO_EXP_INT      4   // input: MCP23S17 interrupts (open drain, active LOW)
#define EXPANDER_PIN_IO_ADC_DRDY     5   // input: ADS124S08 DRDY (active LOW)

// =============================================================================




#endif // PIN_CONFIG_H
