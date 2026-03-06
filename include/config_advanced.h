/**
 * @file config_advanced.h
 * @brief Advanced / implementation-level parameters.
 *
 * This file is included automatically by config.h — do not include it
 * directly.  All symbols defined here are available to any translation
 * unit that includes config.h.
 *
 * These parameters govern internal algorithmic behaviour (ramp tuning,
 * ADC internals, loop timing, tracking-monitor thresholds, FSM diagnostics,
 * etc.).  They have been calibrated for the reference hardware and should
 * not need adjustment during normal operation.  Change them only if you
 * are modifying the underlying hardware or retuning the control algorithms.
 */

#ifndef CONFIG_ADVANCED_H
#define CONFIG_ADVANCED_H

#include <stdint.h>

// =============================================================================
// ADC / DAC internals
// =============================================================================

// ADC read resolution in bits (9–12 on ESP32).
#define ADC_RESOLUTION    static_cast<uint8_t>(12)

// ADC readings below this raw count are treated as 0 (noise floor / off).
#define ADC_MIN_VOLTAGE   static_cast<uint8_t>(15)

// 12-bit DAC full scale (0–4095).  Fixed by the MCP4725 hardware.
#define AMPLIFIER_RESOLUTION  static_cast<uint16_t>(4095)

// I2C address of the MCP4725 DAC.
// Default: 0x60 (A2=A1=A0 tied to GND on most breakout modules).
// The Adafruit breakout board uses 0x62; adjust to match your A0 pin wiring.
#define MCP4725_I2C_ADDRESS  static_cast<uint8_t>(0x60)

// =============================================================================
// Amplifier ramp rates (DAC counts per LOOP_INTERVAL_MS tick)
// =============================================================================

// Maximum DAC increment per main-loop tick (soft ramp-rate cap).
// At LOOP_INTERVAL_MS = 200 ms a step of 5 → full-scale ramp in ~164 s.
#define AMPLIFIER_MAX_STEP_PER_INTERVAL       static_cast<uint16_t>(5)

#define AMPLIFIER_RAMP_RATE_VERY_FAST         static_cast<uint16_t>(1)
#define AMPLIFIER_RAMP_RATE_FAST              static_cast<uint16_t>(5)
#define AMPLIFIER_RAMP_RATE_MEDIUM            static_cast<uint16_t>(10)
#define AMPLIFIER_RAMP_RATE_SLOW              static_cast<uint16_t>(20)
#define AMPLIFIER_RAMP_RATE_VERY_SLOW         static_cast<uint16_t>(50)

// DAC step size during the shutdown ramp (ramps down much faster than up).
// At LOOP_INTERVAL_MS = 200 ms a step of 200 → full-scale ramp in ~4 s.
#define AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL  static_cast<uint16_t>(200)

// =============================================================================
// ACS712 AC Current Sensor — internal ADC constants
// =============================================================================

// ADC supply voltage on the ESP32-S3 (3.3 V rail).
#define ACS712_ADC_VOLTS      3.3f

// Maximum ADC output value for ADC_RESOLUTION = 12 → (2^12) − 1 = 4095.
#define ACS712_ADC_MAX_VALUE  static_cast<uint16_t>((1u << ADC_RESOLUTION) - 1u)

// ESP32 ADC attenuation for ACS712_CURRENT_PIN.
// ADC_11db → 0–3.3 V (full 5 A range; default safe choice).
#ifdef ARDUINO
#  define ACS712_ADC_ATTENUATION  ADC_11db
#endif

// =============================================================================
// Overstroke (back-EMF spike) detection — algorithm internals
// =============================================================================

// EMA smoothing factor for the current baseline (0 < α ≤ 1).
// Smaller values track more slowly so brief spikes stand out more clearly.
#define OVERSTROKE_EMA_ALPHA          0.08f

// Number of readCurrent() calls to prime the EMA before detection is armed.
// At LOOP_INTERVAL_MS = 200 ms this is ~4 seconds.
#define OVERSTROKE_PRIME_READINGS     static_cast<uint8_t>(20)

// Minimum time between consecutive overstroke detections (milliseconds).
// Prevents a single physical event from generating many consecutive flags.
#define OVERSTROKE_DEBOUNCE_MS        static_cast<uint32_t>(200)

// DAC counts subtracted from the target per confirmed backoff event.
// At AMPLIFIER_RESOLUTION = 4095, each step is ~4.9 % of full scale.
#define BACKOFF_DAC_STEP              static_cast<uint16_t>(200)

// =============================================================================
// Indicator LED timing
// =============================================================================

// Brightness for the on-board WS2812 status LED (0–255).
#define WAVE_STATUS_LED_BRIGHTNESS        static_cast<uint8_t>(10)

// Flash period for "fast" flashing (2 Hz → 500 ms full cycle).
#define INDICATOR_FLASH_FAST_PERIOD_MS    static_cast<uint32_t>(500)

// Flash period for "slow" flashing (1 Hz → 1000 ms full cycle).
#define INDICATOR_FLASH_SLOW_PERIOD_MS    static_cast<uint32_t>(1000)

// Duration of the AMBER power-on flash during Initialize (state 0).
#define INDICATOR_INIT_AMBER_MS           static_cast<uint32_t>(1500)

// =============================================================================
// Loop & service timing
// =============================================================================

// Main loop read/update interval (milliseconds).
#define LOOP_INTERVAL_MS  static_cast<uint32_t>(200)

// How often the cooling module updates its tracking monitors (milliseconds).
#define COOLING_CHECK_CYCLE_MS  static_cast<uint32_t>(1000)

// How often the cooling module snapshots the pulse counter and reads the ADC.
// Must be shorter than COOLING_CHECK_CYCLE_MS.
#define COOLING_SENSOR_SAMPLE_MS  static_cast<uint32_t>(100)

// Running-average window depth: 100 samples × 100 ms = 10 s smoothing.
#define COOLING_SENSOR_AVG_SAMPLES  static_cast<uint8_t>(100)

// =============================================================================
// Coolant sensor ADC internals
// =============================================================================

// 12-bit ADC full scale (fixed by hardware).
#define COOLING_TEMP_ADC_RESOLUTION   4095.0f

// ADC reference voltage (V) — matches the ESP32-S3 supply rail.
#define COOLING_TEMP_ADC_VREF         3.3f

// ADC oversampling factor for the NTC temperature read (16 samples averaged).
#define COOLING_TEMP_OVERSAMPLE       static_cast<uint8_t>(16)

// =============================================================================
// Temperature ring-buffer (cooling-rate and stall calculations)
// =============================================================================

// Number of (timestamp, temperature) samples retained in the ring buffer.
// Must be >= 2.
#define TEMP_HISTORY_SIZE  static_cast<uint8_t>(20)

// =============================================================================
// FSM history ring buffer
// =============================================================================

// Number of state-transition records retained.
// Older entries are silently overwritten once the buffer is full.
// Accessible via the 'fsm history' serial command.
#define FSM_HISTORY_LIMIT  static_cast<uint8_t>(20)

// =============================================================================
// Fault history ring buffer
// =============================================================================

// Number of fault records retained (one record per Fault-state entry).
// Older entries are silently overwritten once the buffer is full.
// Accessible via the 'fault history' serial command.
#define FAULT_HISTORY_LIMIT  static_cast<uint8_t>(8)

// =============================================================================
// FSM oscillation detection
// =============================================================================

// Number of consecutive same-pair bounces before declaring oscillation.
// The detector checks the last (FSM_OSCILLATION_MIN_CYCLES * 2) entries.
// Must satisfy: FSM_OSCILLATION_MIN_CYCLES * 2 <= FSM_HISTORY_LIMIT
//
// Example (FSM_OSCILLATION_MIN_CYCLES = 3):
//   History (newest→oldest): Fine, Coarse, Fine, Coarse, Fine, Coarse
//   → 3 full round-trips → oscillation fault on the next tick.
#define FSM_OSCILLATION_MIN_CYCLES  static_cast<uint8_t>(3)

// All cycles must have occurred within this duration.
// Protects against false positives from identical-state pairs separated by
// long periods of normal operation.
#define FSM_OSCILLATION_WINDOW_MS  static_cast<uint32_t>(300000)  // 5 minutes

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

// Acceptable error (Hz) between IMU-measured and AD9833 set-point.
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

// Acceptable RMS voltage error (V) around the target.
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
// Tracking Monitor — coolant temperature (deviation from nominal)
// =============================================================================

// Acceptable deviation around COOLING_COOLANT_NOMINAL_TEMP_C (°C).
#define COOLING_COOLANT_TRACK_HYSTERESIS_C  15.0f

// Deviation (°C) at which the score reaches 0%.
#define COOLING_COOLANT_TRACK_FULL_SCALE_C  30.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_COOLANT_TRACK_WARNING_MS    static_cast<uint32_t>(30000)   // 30 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_COOLANT_TRACK_FAULT_MS      static_cast<uint32_t>(120000)  // 2 min

// =============================================================================
// Tracking Monitor — coolant flow rate (deviation from nominal)
// =============================================================================

// Acceptable deviation around COOLING_FLOW_NOMINAL_LPM (L/min).
#define COOLING_FLOW_TRACK_HYSTERESIS_LPM   0.3f

// Flow deviation (L/min) at which the score reaches 0%.
#define COOLING_FLOW_TRACK_FULL_SCALE_LPM   1.0f

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_FLOW_TRACK_WARNING_MS       static_cast<uint32_t>(10000)   // 10 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_FLOW_TRACK_FAULT_MS         static_cast<uint32_t>(30000)   // 30 s

#endif // CONFIG_ADVANCED_H
