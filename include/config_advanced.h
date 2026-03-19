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
// Relays
// =============================================================================
// Each relay is an independent SparkFun Qwiic Single Relay on its own I2C address.
// Addresses are defined in pin_config.h:
//   Compressor relay: COMPRESSOR_RELAY_ADDR (0x18)
//   Amplifier relay:  AMPLIFIER_RELAY_ADDR  (0x19)

// =============================================================================
// ADC / DAC internals
// =============================================================================

// ADC read resolution in bits (9–12 on ESP32).
#define ADC_RESOLUTION    static_cast<uint8_t>(12)

// ADC readings below this raw count are treated as 0 (noise floor / off).
#define ADC_MIN_VOLTAGE   static_cast<uint8_t>(15)

// 16-bit DAC full scale (0–65535).  Fixed by the AD5693R hardware.
#define AMPLIFIER_RESOLUTION  static_cast<uint16_t>(65535)


// I2C address of the AD5693R DAC.
// A0 = GND → 0x4C.
// A0 = VDD → 0x4E.
#define AD5693_DAC_I2C_ADDRESS  static_cast<uint8_t>(0x4E)

// =============================================================================
// Amplifier ramp rates (DAC counts per LOOP_INTERVAL_MS tick)
// =============================================================================
//
// Scaled ×16 from 12-bit values to preserve the same wall-clock ramp speed
// at 16-bit resolution.

// Maximum DAC increment per main-loop tick (soft ramp-rate cap).
// At LOOP_INTERVAL_MS = 200 ms a step of 80 → full-scale ramp in ~164 s.
#define AMPLIFIER_MAX_STEP_PER_INTERVAL       static_cast<uint16_t>(80)

#define AMPLIFIER_RAMP_RATE_VERY_FAST         static_cast<uint16_t>(16)
#define AMPLIFIER_RAMP_RATE_FAST              static_cast<uint16_t>(80)
#define AMPLIFIER_RAMP_RATE_MEDIUM            static_cast<uint16_t>(160)
#define AMPLIFIER_RAMP_RATE_SLOW              static_cast<uint16_t>(320)
#define AMPLIFIER_RAMP_RATE_VERY_SLOW         static_cast<uint16_t>(800)

// DAC step size during the shutdown ramp (ramps down much faster than up).
// At LOOP_INTERVAL_MS = 200 ms a step of 3200 → full-scale ramp in ~4 s.
#define AMPLIFIER_DAC_SHUTDOWN_STEP_PER_INTERVAL  static_cast<uint16_t>(3200)

// The DAC output should only output 0-10vdc. This is the multiplier voltage
// that gets passed to the AD633 voltage
#define AMPLIFIER_DAC_MAX_OUTPUT_VOLTAGE_V   static_cast<float>(10.0f)

// =============================================================================
// ACS712 AC Current Sensor — internal ADC constants
// =============================================================================

// ADC supply voltage on the ESP32-S3 (3.3 V rail).
#define ACS712_ADC_VOLTS      static_cast<float>(3.3f)

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
#define OVERSTROKE_EMA_ALPHA          static_cast<float>(0.08f)

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

// How often the indicator updates (milliseconds).
#define INDICATOR_UPDATE_INTERVAL_MS  static_cast<uint32_t>(100)

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
#define COOLING_TEMP_ADC_RESOLUTION   static_cast<float>(4095.0f)

// ADC reference voltage (V) — matches the ESP32-S3 supply rail.
#define COOLING_TEMP_ADC_VREF         static_cast<float>(3.3f)

// ADC oversampling factor for the NTC temperature read (16 samples averaged).
#define COOLING_TEMP_OVERSAMPLE       static_cast<uint8_t>(16)


// =============================================================================
// EMC2302 I2C Address & Configuration
// =============================================================================
//
// A single EMC2302-2 dual PWM fan controller drives both the fan (channel 0)
// and the pump (channel 1).  No I2C mux or address translator is needed.

#define EMC2302_2_I2C_ADDRESS  static_cast<uint8_t>(0x2F)

// =============================================================================
// Pump — duty-cycle normalisation & software LUT configuration
// =============================================================================

// Maximum hardware PWM duty (0–255 raw) sent to the pump channel.
// The old EMC2101 used a 0–100 % scale mapped to 0–63 hardware steps.
// setDutyCycle(16) on EMC2101 → 16*63/100 = hw 10 → 10/63 ≈ 16 % duty.
// On the EMC2302 (0–255 raw), equivalent = ~41.  Bumped to 51 (~20 %)
// to give extra headroom — adjust down if pump stalls.
// All user-facing pump speeds are expressed in a normalised 0–100 % range
// that maps linearly to 0–COOLING_PUMP_MAX_DUTY_PCT at the hardware level.
//   user 0 %   → hardware 0      user 50 % → hardware ~26
//   user 100 % → hardware 51
#define COOLING_PUMP_MAX_DUTY_PCT  static_cast<uint8_t>(51)

// Initial safe pump duty (normalised 0–100 %) applied at startup before
// the software LUT evaluates its first temperature update.
// 30 % normalised → ~5 hw duty → ~2360 RPM (steady).
#define COOLING_PUMP_INITIAL_DUTY_PCT  static_cast<uint8_t>(30)

// Software LUT hysteresis for the fan (°C).
// Temperature must drop this many degrees below a threshold before the
// duty cycle steps back down (prevents rapid hunting / sawtooth RPM).
#define COOLING_FAN_LUT_HYSTERESIS_C   static_cast<uint8_t>(2)

// Software LUT hysteresis for the pump (°C).
// Temperature must drop this many degrees below a threshold before the
// duty cycle steps back down (prevents rapid hunting).
#define COOLING_PUMP_LUT_HYSTERESIS_C  static_cast<uint8_t>(3)


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
#define COLD_HEAD_TRACK_HYSTERESIS_C        static_cast<float>(1.0f)

// Deviation at which the tracking score reaches 0%.
#define COLD_HEAD_TRACK_FULL_SCALE_C       static_cast<float>(10.0f)

// Time (ms) continuously outside the band before a WARNING is logged.
#define COLD_HEAD_TRACK_WARNING_MS         static_cast<uint32_t>(60000)   // 60 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COLD_HEAD_TRACK_FAULT_MS           static_cast<uint32_t>(300000)  // 5 min

// =============================================================================
// Tracking Monitor — amplifier output frequency
// =============================================================================

// Acceptable error (Hz) between IMU-measured and AD9833 set-point.
#define AMPLIFIER_FREQ_TRACK_HYSTERESIS_HZ  static_cast<float>(0.5f)

// Frequency error (Hz) at which the score reaches 0%.
#define AMPLIFIER_FREQ_TRACK_FULL_SCALE_HZ  static_cast<float>(5.0f)

// Time (ms) continuously outside the band before a WARNING is logged.
#define AMPLIFIER_FREQ_TRACK_WARNING_MS    static_cast<uint32_t>(10000)   // 10 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define AMPLIFIER_FREQ_TRACK_FAULT_MS      static_cast<uint32_t>(30000)   // 30 s

// =============================================================================
// Tracking Monitor — amplifier output voltage
// =============================================================================

// Acceptable RMS voltage error (V) around the target.
#define AMPLIFIER_VOLT_TRACK_HYSTERESIS_V   static_cast<float>(0.05f)

// Voltage error (V) at which the score reaches 0%.
#define AMPLIFIER_VOLT_TRACK_FULL_SCALE_V   static_cast<float>(2.0f)

// Time (ms) continuously outside the band before a WARNING is logged.
#define AMPLIFIER_VOLT_TRACK_WARNING_MS    static_cast<uint32_t>(15000)   // 15 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define AMPLIFIER_VOLT_TRACK_FAULT_MS      static_cast<uint32_t>(60000)   // 60 s

// =============================================================================
// Tracking Monitor — cooling fan duty cycle (forced/manual mode only)
// =============================================================================

// Acceptable duty-cycle error (%) between requested and actual fan speed.
#define COOLING_FAN_TRACK_HYSTERESIS_PCT    static_cast<float>(5.0f)

// Duty-cycle error (%) at which the score reaches 0%.
#define COOLING_FAN_TRACK_FULL_SCALE_PCT   static_cast<float>(30.0f)

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_FAN_TRACK_WARNING_MS       static_cast<uint32_t>(10000)   // 10 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_FAN_TRACK_FAULT_MS         static_cast<uint32_t>(30000)   // 30 s

// =============================================================================
// Tracking Monitor — coolant temperature (deviation from nominal)
// =============================================================================

// Acceptable deviation around COOLING_COOLANT_NOMINAL_TEMP_C (°C).
#define COOLING_COOLANT_TRACK_HYSTERESIS_C  static_cast<float>(15.0f)

// Deviation (°C) at which the score reaches 0%.
#define COOLING_COOLANT_TRACK_FULL_SCALE_C  static_cast<float>(30.0f)

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_COOLANT_TRACK_WARNING_MS    static_cast<uint32_t>(30000)   // 30 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_COOLANT_TRACK_FAULT_MS      static_cast<uint32_t>(120000)  // 2 min

// =============================================================================
// Tracking Monitor — coolant flow rate (deviation from nominal)
// =============================================================================

// Acceptable deviation around the dynamic flow setpoint (L/min).
// The setpoint is proportional to pump speed, so this is an absolute
// tolerance around the speed-scaled expected flow.
#define COOLING_FLOW_TRACK_HYSTERESIS_LPM   static_cast<float>(3.0f)

// Flow deviation (L/min) at which the score reaches 0%.
#define COOLING_FLOW_TRACK_FULL_SCALE_LPM   static_cast<float>(10.0f)

// Time (ms) continuously outside the band before a WARNING is logged.
#define COOLING_FLOW_TRACK_WARNING_MS       static_cast<uint32_t>(10000)   // 10 s

// Time (ms) continuously outside the band before a FAULT is raised.
#define COOLING_FLOW_TRACK_FAULT_MS         static_cast<uint32_t>(30000)   // 30 s


// ====
// IMU
// =============================================================================
#define LSM6DSOX_IMU_IC2_ADDRESS static_cast<uint8_t>(0x6A) // 0x6B is alternative, if SA0 is tied high.

#define ADS122C04_RTD_SENSOR_I2C_ADDRESS static_cast<uint8_t>(0x45)

// =============================================================================
// Misc stuff
// =============================================================================
#define ON true
#define OFF false

#endif // CONFIG_ADVANCED_H
