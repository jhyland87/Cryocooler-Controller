/**
 * @file config.h
 * @brief Application configuration — ALL tunable parameters live here.
 *
 * Pin assignments live in pin_config.h.
 * No hardware includes required — safe for native unit tests.
 *
 * NOTE: RTD_WIRE_CONFIG references an enum value from the Adafruit MAX31865
 * header; that header must be included before using it.
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


#define ANALOG_RESOLUTION 12

#define DS18B20_VREF 3.3

// Reference resistor on the MAX31865 breakout.
// Use 430.0 for PT100, 4300.0 for PT1000 (adjust to measured value).
#define RTD_RREF          435.3f

// Nominal 0 °C resistance of the RTD element.
// Use 100.0 for PT100, 1000.0 for PT1000.
#define RTD_RNOMINAL      100.0f

// Wire configuration: MAX31865_2WIRE, MAX31865_3WIRE, or MAX31865_4WIRE
#define RTD_WIRE_CONFIG   MAX31865_2WIRE

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================

// Output frequency in Hz.
#define AD9833_FREQ_HZ    static_cast<uint16_t>(60)

// =============================================================================
// MCP4921 12-bit DAC
// =============================================================================

// 12-bit full scale (0–4095).
#define MCP4921_MAX_VALUE  static_cast<uint16_t>(4095)

// SPI clock speed for the MCP4921.
#define MCP4921_SPI_SPEED  static_cast<uint32_t>(20000000)

// Maximum DAC increment allowed per main-loop interval.
// At LOOP_INTERVAL_MS = 200 ms, a step of 5 gives a full-scale ramp in ~164 s.
#define DAC_MAX_STEP_PER_INTERVAL  static_cast<uint16_t>(5)

// =============================================================================
// ADC
// =============================================================================

// ADC read resolution in bits (9–12 on ESP32).
#define ADC_RESOLUTION    static_cast<uint8_t>(12)

// ADC readings below this value are treated as 0 (noise floor / off).
#define ADC_MIN_VOLTAGE   static_cast<uint8_t>(15)

// SmoothADC: sample the DAC voltage pin every this many milliseconds.
#define DAC_VOLTAGE_ADC_SMOOTH_PERIOD_MS  static_cast<uint32_t>(5)

// SmoothADC: number of priming samples at boot to seed the filter.
#define DAC_VOLTAGE_ADC_SMOOTH_PRIME_SAMPLES  static_cast<uint8_t>(8)

// DAC voltage ADC readings below this are treated as zero (output off).
#define DAC_MIN_VOLTAGE   static_cast<uint16_t>(15)

// =============================================================================
// RMS Voltage Safety
// =============================================================================

// Maximum allowable RMS voltage (VDC).
// Exceeding this threshold immediately transitions the system to Fault (8).
// The RMS module is currently stubbed; this value is reserved for when it
// is fully implemented.
#define RMS_MAX_VOLTAGE_VDC  120.0f

// =============================================================================
// Temperature Thresholds (Kelvin)
// =============================================================================

// Target cold-stage temperature.  The system aims to reach and hold this.
#define SETPOINT_K                   78.0f

// Temperature boundary between Coarse Cool-down (state 2) and
// Fine Cool-down (state 3).
#define COARSE_FINE_THRESHOLD_K      85.0f

// Assumed ambient / start temperature — top of the DAC ramp range.
// DAC output = 0 at AMBIENT_START_K and MCP4921_MAX_VALUE at SETPOINT_K.
#define AMBIENT_START_K             295.0f

// Cold-stage is considered "at setpoint" when within this many Kelvin of
// SETPOINT_K (used for overshoot / settle transitions).
#define SETPOINT_TOLERANCE_K          2.0f

// =============================================================================
// Cooldown Rate Limiting
// =============================================================================

// Maximum allowable cooling rate: 10 °C per 10 min → 1 K per minute.
// If the measured rate exceeds this value the DAC is held (not incremented).
#define MAX_COOLDOWN_RATE_K_PER_MIN   1.0f

// =============================================================================
// Temperature Stall Detection
// =============================================================================

// Observation window for stall detection (milliseconds).
// If the cold stage has not dropped by STALL_MIN_DROP_K within this window
// while in a cool-down state, the system transitions to Fault (8).
#define STALL_DETECT_WINDOW_MS     static_cast<uint32_t>(600000)  // 10 minutes

// Minimum temperature drop required within STALL_DETECT_WINDOW_MS.
#define STALL_MIN_DROP_K             2.0f

// Number of (timestamp, temperature) samples retained in the ring buffer
// used for cooling-rate and stall calculations.  Must be >= 2.
#define TEMP_HISTORY_SIZE            static_cast<uint8_t>(20)

// =============================================================================
// Settling / Baseline Timing
// =============================================================================

// Temperature must remain within SETPOINT_TOLERANCE_K for this duration
// before the state machine advances from Settle (5) → Baseline (6).
#define SETTLE_DURATION_MS   static_cast<uint32_t>(60000)    // 60 s

// Duration of the Baseline (6) data-collection state before advancing to
// Operating (7).
#define BASELINE_DURATION_MS static_cast<uint32_t>(300000)   // 5 minutes

// =============================================================================
// Timing
// =============================================================================

// Main loop read/update interval (milliseconds).
#define LOOP_INTERVAL_MS  static_cast<uint32_t>(200)

// =============================================================================
// ACS712 AC Current Sensor — Overstroke (Back-EMF Spike) Detection
// =============================================================================

// Sensitivity of the ACS712-05B module in mV per amp.
// Nominal 185 mV/A; adjust to the measured value of your specific module.
#define ACS712_SENSITIVITY_MV_PER_A   185.0f

// ADC supply voltage on the ESP32-S3 (3.3 V rail).
// Passed to the RobTillaart ACS712 constructor so it can convert ADC counts
// to millivolts correctly.
#define ACS712_ADC_VOLTS              3.3f

// Maximum ADC output value for the configured resolution.
// For ADC_RESOLUTION = 12 this is (2^12) − 1 = 4095.
#define ACS712_ADC_MAX_VALUE          static_cast<uint16_t>((1u << ADC_RESOLUTION) - 1u)

// EMA smoothing factor for the current baseline (0 < α ≤ 1).
// Smaller values track more slowly so brief spikes stand out more.
#define OVERSTROKE_EMA_ALPHA          0.08f

// Number of readCurrent() calls used to prime the EMA before spike
// detection is armed.  At LOOP_INTERVAL_MS = 200 ms this is ~4 seconds.
#define OVERSTROKE_PRIME_READINGS     static_cast<uint8_t>(20)

// A reading is flagged as a spike when the instantaneous current exceeds
// the running EMA baseline by more than this many amps.
#define OVERSTROKE_CURRENT_THRESHOLD_A  2.0f

// Minimum time between consecutive overstroke detections (milliseconds).
// Prevents a single physical event from generating many consecutive flags.
#define OVERSTROKE_DEBOUNCE_MS        static_cast<uint32_t>(2000)

// ESP32 ADC attenuation for ACS712_CURRENT_PIN.
// MUST match the supply voltage / voltage-divider configuration (see rms.cpp).
// This constant is applied via analogSetPinAttenuation() before sSensor.begin()
// so that calibration and live readings always use the same ADC full-scale range.
//
//   ADC_0db  → 0 – 1.1 V  (not usable; ACS712 output always exceeds this)
//   ADC_6db  → 0 – 2.2 V  (best resolution; clips at ~4.5 A on 3.3 V supply
//                           or ~4.1 A on 5 V supply + 3.3 kΩ / 6.8 kΩ divider)
//   ADC_11db → 0 – 3.3 V  (full 5 A range; default safe choice)
#ifdef ARDUINO
#  define ACS712_ADC_ATTENUATION  ADC_11db
#endif

// =============================================================================
// DAC Backoff (response to overstroke events)
// =============================================================================

// DAC counts to subtract from the target for each confirmed backoff event.
// At MCP4921_MAX_VALUE = 4095, each step is ~4.9 % of full scale.
#define BACKOFF_DAC_STEP              static_cast<uint16_t>(200)

// Total number of backoff events allowed before the state machine enters a
// dedicated Fault state.  The cumulative DAC reduction at this point is
// BACKOFF_MAX_COUNT × BACKOFF_DAC_STEP counts.
#define BACKOFF_MAX_COUNT             static_cast<uint8_t>(10)

// =============================================================================
// Indicator LED
// =============================================================================

// Brightness for the on-board WS2812 status LED (0–255).
#define WAVE_STATUS_LED_BRIGHTNESS  static_cast<uint8_t>(10)

// Flash period for "fast" flashing (2 Hz → 500 ms full cycle).
#define INDICATOR_FLASH_FAST_PERIOD_MS  static_cast<uint32_t>(500)

// Flash period for "slow" flashing (1 Hz → 1000 ms full cycle).
#define INDICATOR_FLASH_SLOW_PERIOD_MS  static_cast<uint32_t>(1000)

// Duration of the AMBER power-on flash during Initialize (state 0).
#define INDICATOR_INIT_AMBER_MS     static_cast<uint32_t>(1500)

#endif // CONFIG_H
