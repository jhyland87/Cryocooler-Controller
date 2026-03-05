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

#include "pin_config.h"
#include "arduino_secrets.h"

#define HOSTNAME "cryocooler"

#define ENABLE_LOGGER false

// =============================================================================
// Serial
// =============================================================================
#define SERIAL_BAUD       static_cast<uint32_t>(115200)

// =============================================================================
// RTD Sensor (MAX31865)
// =============================================================================


#define ANALOG_RESOLUTION 12

#define DS18B20_VREF      3.3f

// Reference resistor on the MAX31865 breakout.
// Use 430.0 for PT100, 4300.0 for PT1000 (adjust to measured value).
#define RTD_RREF          435.3f

// Nominal 0 °C resistance of the RTD element.
// Use 100.0 for PT100, 1000.0 for PT1000.
#define RTD_RNOMINAL      100.0f

// Wire configuration: MAX31865_2WIRE, MAX31865_3WIRE, or MAX31865_4WIRE
#define RTD_WIRE_CONFIG   MAX31865_3WIRE

// =============================================================================
// AD9833 Waveform Generator
// =============================================================================

// Output frequency in Hz.
#define AMPLIFIER_FREQ_HZ    static_cast<uint16_t>(60)

// 12-bit full scale (0–4095).
#define AMPLIFIER_RESOLUTION  static_cast<uint16_t>(4095)

// SPI clock speed for the MCP4921.
#define AMPLIFIER_DAC_SPI_SPEED  static_cast<uint32_t>(20000000)

// Maximum DAC increment allowed per main-loop interval.
// At LOOP_INTERVAL_MS = 200 ms, a step of 5 gives a full-scale ramp in ~164 s.
#define AMPLIFIER_MAX_STEP_PER_INTERVAL  static_cast<uint16_t>(5)

#define AMPLIFIER_RAMP_RATE_VERY_FAST  static_cast<uint16_t>(1)
#define AMPLIFIER_RAMP_RATE_FAST  static_cast<uint16_t>(5)
#define AMPLIFIER_RAMP_RATE_MEDIUM  static_cast<uint16_t>(10)
#define AMPLIFIER_RAMP_RATE_SLOW  static_cast<uint16_t>(20)
#define AMPLIFIER_RAMP_RATE_VERY_SLOW  static_cast<uint16_t>(50)

// DAC step size during shutdown sequence (ramp down much faster than ramp up).
// At LOOP_INTERVAL_MS = 200 ms, a step of 200 gives a full-scale ramp in ~4 s.
#define AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL  static_cast<uint16_t>(200)

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
#define AMPLIFIER_MAX_VOLTAGE  120.0f

// =============================================================================
// System Voltage Safety
// =============================================================================

// Minimum allowable DC system supply voltage (V).
// Dropping below this threshold from any state immediately transitions the
// system to Fault (LowSystemVoltage).  Pass 0.0f to update() when no
// measurement is available — a value of 0.0f is treated as "not monitored"
// and will never trigger this fault.
#define MIN_SYSTEM_VOLTAGE_VDC  11.5f

// =============================================================================
// Temperature Thresholds (Kelvin)
// =============================================================================

// Target cold-stage temperature.  The system aims to reach and hold this.
#define SETPOINT_K                   78.0f

// Temperature boundary between Coarse Cool-down (state 2) and
// Fine Cool-down (state 3).
#define COARSE_FINE_THRESHOLD_K      85.0f

// Assumed ambient / start temperature — top of the DAC ramp range.
// DAC output = 0 at AMBIENT_START_K and AMPLIFIER_RESOLUTION at SETPOINT_K.
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
// Shutdown Sequence
// =============================================================================

// Duration of the Shutdown (9) state during which the DAC ramps to 0
// before returning to Idle. Prevents motor stress from abrupt stops.
#define SHUTDOWN_DURATION_MS static_cast<uint32_t>(5000)     // 5 s

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
#define OVERSTROKE_DEBOUNCE_MS        static_cast<uint32_t>(200)

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
// At AMPLIFIER_RESOLUTION = 4095, each step is ~4.9 % of full scale.
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

// =============================================================================
// HTTP API
// =============================================================================

#define HTTP_API_PORT static_cast<uint16_t>(80)

#define WS_PORT static_cast<uint16_t>(8080)

// =============================================================================
// Cooling
// =============================================================================

// The frequency at which the cooling system will check the coolant temperature.
#define COOLING_CHECK_CYCLE_MS static_cast<uint32_t>(1000)

#define COOLING_AUTOSTART_ENABLED true

// Max speed in percent
#define COOLING_FAN_MAX_SPEED 20

// If the cryocooler is in an OFF state, and the coolant temperature dips below
// this value then just turn off the cooling fans and pump.
// This is the temp of the coolant
#define COOLING_OFF_BELOW_COOLANT_TEMP 30.0f

// =============================================================================
// FSM History
// =============================================================================

// Number of state-transition records retained in the FSM history ring buffer.
// Older entries are silently overwritten once the buffer is full.
// Accessible via the 'fsm history' serial command.
#define FSM_HISTORY_LIMIT  static_cast<uint8_t>(20)

// =============================================================================
// FSM Oscillation Detection
// =============================================================================

// Number of consecutive same-pair bounces required before declaring
// oscillation.  The detector looks at the last (FSM_OSCILLATION_MIN_CYCLES * 2)
// history entries; all must alternate between exactly two non-trivial states.
//
// Example with FSM_OSCILLATION_MIN_CYCLES = 3:
//   History (newest→oldest): Fine, Coarse, Fine, Coarse, Fine, Coarse
//   → 3 full round trips → oscillation fault triggered on the next update() tick.
//
// Must satisfy: FSM_OSCILLATION_MIN_CYCLES * 2  <=  FSM_HISTORY_LIMIT
#define FSM_OSCILLATION_MIN_CYCLES  static_cast<uint8_t>(3)

// All cycles must have occurred within this duration (ms).
// Protects against false positives from identical-state pairs separated by long
// periods of normal operation.
#define FSM_OSCILLATION_WINDOW_MS  static_cast<uint32_t>(300000)  // 5 minutes

// =============================================================================
// Telemetry related config
// =============================================================================

#define TELEMETRY_ENABLED true

// If the telemetry is enabled, emit the telemetry when the cryocooler is in an IDLE state.
// (TELEMETRY_ENABLED must be true for this to work)
#define EMIT_TELEMETRY_WHEN_IDLE true

// =============================================================================
// Tracking Monitor — cold_head temperature
// =============================================================================

// Deadband: temperature must deviate beyond this to start the warning timer.
#define COLD_HEAD_TRACK_HYSTERESIS_K        1.0f

// Deviation at which the tracking score reaches 0%.
#define COLD_HEAD_TRACK_FULL_SCALE_K       10.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define COLD_HEAD_TRACK_WARNING_MS         static_cast<uint32_t>(60000)   // 60 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COLD_HEAD_TRACK_FAULT_MS           static_cast<uint32_t>(300000)  // 5 min

// =============================================================================
// Tracking Monitor — amplifier output frequency
// =============================================================================

// Acceptable error (Hz) between the IMU-measured frequency and the AD9833
// set-point before the warning timer starts.
#define AMPLIFIER_FREQ_TRACK_HYSTERESIS_HZ  0.5f

// Frequency error (Hz) at which the score reaches 0%.
#define AMPLIFIER_FREQ_TRACK_FULL_SCALE_HZ  5.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define AMPLIFIER_FREQ_TRACK_WARNING_MS    static_cast<uint32_t>(10000)   // 10 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define AMPLIFIER_FREQ_TRACK_FAULT_MS      static_cast<uint32_t>(30000)   // 30 s

// =============================================================================
// Tracking Monitor — amplifier output voltage
// =============================================================================

// Acceptable RMS voltage error (V) around the target before the timer starts.
#define AMPLIFIER_VOLT_TRACK_HYSTERESIS_V   0.05f

// Voltage error (V) at which the score reaches 0%.
#define AMPLIFIER_VOLT_TRACK_FULL_SCALE_V   2.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define AMPLIFIER_VOLT_TRACK_WARNING_MS    static_cast<uint32_t>(15000)   // 15 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define AMPLIFIER_VOLT_TRACK_FAULT_MS      static_cast<uint32_t>(60000)   // 60 s

// =============================================================================
// Tracking Monitor — cooling fan duty cycle (forced/manual mode only)
// =============================================================================

// Acceptable duty-cycle error (%) between requested and actual fan speed.
#define COOLING_FAN_TRACK_HYSTERESIS_PCT    5.0f

// Duty-cycle error (%) at which the score reaches 0%.
#define COOLING_FAN_TRACK_FULL_SCALE_PCT   30.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_FAN_TRACK_WARNING_MS       static_cast<uint32_t>(10000)   // 10 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_FAN_TRACK_FAULT_MS         static_cast<uint32_t>(30000)   // 30 s

// =============================================================================
// Tracking Monitor — coolant temperature
// =============================================================================

// Nominal coolant operating temperature (°C) — centre of the in-range band.
#define COOLING_COOLANT_NOMINAL_TEMP_C     25.0f

// Acceptable deviation around nominal (°C).  Band = nominal ± hysteresis.
#define COOLING_COOLANT_TRACK_HYSTERESIS_C 15.0f

// Deviation (°C) at which the score reaches 0%.
#define COOLING_COOLANT_TRACK_FULL_SCALE_C 30.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_COOLANT_TRACK_WARNING_MS   static_cast<uint32_t>(30000)   // 30 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_COOLANT_TRACK_FAULT_MS     static_cast<uint32_t>(120000)  // 2 min

// =============================================================================
// Tracking Monitor — coolant flow rate
// =============================================================================

// Expected flow rate (L/min) when the pump is running.
#define COOLING_FLOW_NOMINAL_LPM            1.0f

// Acceptable deviation around nominal (L/min).
#define COOLING_FLOW_TRACK_HYSTERESIS_LPM   0.3f

// Flow deviation (L/min) at which the score reaches 0%.
#define COOLING_FLOW_TRACK_FULL_SCALE_LPM   1.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_FLOW_TRACK_WARNING_MS      static_cast<uint32_t>(10000)   // 10 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_FLOW_TRACK_FAULT_MS        static_cast<uint32_t>(30000)   // 30 s

#endif // CONFIG_H
