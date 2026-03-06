/**
 * @file config.h
 * @brief User-facing application configuration.
 *
 * This file contains the parameters most likely to need adjustment when
 * setting up, calibrating, or operating the cryocooler:
 *   - Hardware calibration (RTD type, sensor coefficients)
 *   - Operating setpoints (target temperature, safety limits)
 *   - Timing thresholds (settle duration, stall window)
 *   - Feature flags (telemetry, autostart)
 *
 * Pin assignments live in pin_config.h.
 * Internal algorithm parameters live in config_advanced.h, which is
 * included at the bottom of this file — no need to include it separately.
 *
 * NOTE: RTD_WIRE_CONFIG references an enum value from the Adafruit MAX31865
 * header; that header must be included before using it.
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

#include "pin_config.h"
#include "arduino_secrets.h"

// =============================================================================
// System
// =============================================================================

#define HOSTNAME      "cryocooler"

#define ENABLE_LOGGER false

// Enable HTTP OTA firmware updates (GET /ota — upload form, POST /ota — flash).
// Requires an OTA-capable partition table (partitions.csv) and WiFi connectivity.
// Set false to compile out the OTA endpoint entirely.
#define ENABLE_OTA true

#define SERIAL_BAUD   static_cast<uint32_t>(115200)

// =============================================================================
// Network / HTTP API
// =============================================================================

#define HTTP_API_PORT static_cast<uint16_t>(80)
#define WS_PORT       static_cast<uint16_t>(8080)

// =============================================================================
// ESP-NOW — peer-to-peer telemetry bridge
// =============================================================================
//
// ESP-NOW coexists with WiFi (STA mode) on the same radio.  The transmit
// channel is determined automatically by the AP association — the peer device
// must be configured to listen on the same channel.
//
// Fragmentation: ESP-NOW frames are limited to 250 bytes.  Telemetry JSON is
// split into 246-byte chunks, each prefixed with a 4-byte header:
//   [msg_id][total_chunks][chunk_index][payload_len][...JSON fragment...]
// The peer reassembles chunks that share the same msg_id (wraps at 255).

// Enable ESP-NOW telemetry forwarding.  WiFi, HTTP dashboard, and OTA all
// remain fully operational when this is true.
#define ENABLE_ESPNOW  false

// MAC address of the receiving ESP32.
// Find it by running `Serial.println(WiFi.macAddress())` on the peer.
// Format: {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF}
// IMPORTANT: replace the placeholder below before enabling ESP-NOW.
#define ESPNOW_PEER_MAC  { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF }

// Telemetry burst interval sent to the peer (milliseconds).
// 1000 ms matches the dashboard broadcast cadence.
#define ESPNOW_SEND_INTERVAL_MS  static_cast<uint32_t>(1000)

// =============================================================================
// Telemetry
// =============================================================================

#define TELEMETRY_ENABLED        true

// Emit telemetry frames even while the cryocooler is in the Idle state.
// Requires TELEMETRY_ENABLED true.
#define EMIT_TELEMETRY_WHEN_IDLE true

// =============================================================================
// RTD Sensor (MAX31865)
// =============================================================================

#define ANALOG_RESOLUTION 12

// Reference resistor on the MAX31865 breakout.
// Use 430.0 for PT100, 4300.0 for PT1000 (adjust to your measured value).
#define RTD_RREF        435.3f

// Nominal 0 °C resistance of the RTD element.
// Use 100.0 for PT100, 1000.0 for PT1000.
#define RTD_RNOMINAL    100.0f

// Wire configuration: MAX31865_2WIRE, MAX31865_3WIRE, or MAX31865_4WIRE
#define RTD_WIRE_CONFIG MAX31865_3WIRE

// =============================================================================
// Amplifier (AD9833 waveform generator)
// =============================================================================

// Output frequency in Hz.
#define AMPLIFIER_FREQ_HZ  static_cast<uint16_t>(60)

// Maximum allowable RMS output voltage (VDC).
// Exceeding this immediately transitions the system to Fault.
#define AMPLIFIER_MAX_VOLTAGE  120.0f

// Maximum allowable continuous RMS output current (A).
// Exceeding this while running immediately transitions to Fault (SensorFault).
// Set to 0.0f to disable current fault detection.
// Calibrate to your cryocooler's rated maximum current draw.
#define AMPLIFIER_MAX_CURRENT_A  5.0f

// =============================================================================
// Safety — system supply voltage
// =============================================================================

// Minimum allowable DC system supply voltage (V).
// Dropping below this from any state immediately transitions to Fault.
// Set to 0.0f to disable (treated as "not monitored").
#define MIN_SYSTEM_VOLTAGE_VDC  11.5f

// =============================================================================
// ACS712 AC Current Sensor — calibration
// =============================================================================

// Sensitivity of the ACS712-05B module in mV per amp.
// Nominal 185 mV/A; adjust to the measured value of your specific module.
#define ACS712_SENSITIVITY_MV_PER_A   185.0f

// =============================================================================
// Safety — overstroke / back-EMF detection
// =============================================================================

// A current reading is flagged as a spike when it exceeds the EMA baseline
// by more than this many amps.
#define OVERSTROKE_CURRENT_THRESHOLD_A  2.0f

// Maximum number of backoff events before the state machine enters Fault.
// Cumulative DAC reduction at this point = BACKOFF_MAX_COUNT × BACKOFF_DAC_STEP.
#define BACKOFF_MAX_COUNT  static_cast<uint8_t>(10)

// =============================================================================
// Temperature Thresholds (Kelvin)
// =============================================================================

// Plausibility bounds for the cold-stage temperature sensor (Kelvin).
// Readings outside this range — including the 0 K default before first read —
// indicate a sensor hardware fault (open/short circuit or no data yet).
// Checked only while the system is running to avoid false faults on startup.
// MIN is set well below liquid-nitrogen temperature (77 K); MAX is set above
// any ambient temperature a cryocooler environment could legitimately reach.
#define MIN_PLAUSIBLE_TEMP_K   20.0f
#define MAX_PLAUSIBLE_TEMP_K  400.0f

// Target cold-stage temperature.  The system aims to reach and hold this.
#define SETPOINT_K              78.0f

// Temperature boundary between Coarse Cool-down (state 2) and
// Fine Cool-down (state 3).
#define COARSE_FINE_THRESHOLD_K 85.0f

// Assumed ambient / start temperature — top of the DAC ramp range.
// DAC output = 0 at AMBIENT_START_K and AMPLIFIER_RESOLUTION at SETPOINT_K.
#define AMBIENT_START_K         295.0f

// Cold-stage is considered "at setpoint" when within this many Kelvin of
// SETPOINT_K (used for overshoot / settle transitions).
#define SETPOINT_TOLERANCE_K    2.0f

// =============================================================================
// Cooldown Rate Limiting
// =============================================================================

// Maximum allowable cooling rate (K/min).
// If the measured rate exceeds this the DAC is held (not incremented).
#define MAX_COOLDOWN_RATE_K_PER_MIN  1.0f

// =============================================================================
// Temperature Stall Detection
// =============================================================================

// Observation window for stall detection (milliseconds).
// If the cold stage has not dropped by STALL_MIN_DROP_K within this window
// while in a cool-down state, the system transitions to Fault.
#define STALL_DETECT_WINDOW_MS  static_cast<uint32_t>(600000)  // 10 minutes

// Minimum temperature drop required within STALL_DETECT_WINDOW_MS.
#define STALL_MIN_DROP_K        2.0f

// =============================================================================
// Settling / Baseline Timing
// =============================================================================

// Temperature must remain within SETPOINT_TOLERANCE_K for this duration
// before the state machine advances from Settle (5) → Baseline (6).
#define SETTLE_DURATION_MS    static_cast<uint32_t>(60000)   // 60 s

// Duration of the Baseline (6) data-collection state before advancing to
// Operating (7).
#define BASELINE_DURATION_MS  static_cast<uint32_t>(300000)  // 5 minutes

// =============================================================================
// Shutdown Sequence
// =============================================================================

// Duration of the Shutdown (9) state during which the DAC ramps to 0
// before returning to Idle.  Prevents motor stress from abrupt stops.
#define SHUTDOWN_DURATION_MS  static_cast<uint32_t>(5000)    // 5 s

// =============================================================================
// Cooling — behaviour
// =============================================================================

// Start the cooling pump and fan automatically on system initialisation.
#define COOLING_AUTOSTART_ENABLED  true

// Maximum fan speed allowed (percent).
#define COOLING_FAN_MAX_SPEED  20

// If the cryocooler is in an OFF state and the coolant temperature drops
// below this value, turn off the fans and pump to save power.
#define COOLING_OFF_BELOW_COOLANT_TEMP  30.0f

// =============================================================================
// Coolant sensor — hardware calibration (Alphacool ES)
// =============================================================================

// ── NTC thermistor ────────────────────────────────────────────────────────
// Source: https://download.alphacool.com/legacy/kOhm_Sensor_Table_Alphacool.pdf

// Supply voltage for the thermistor voltage divider (V).
#define COOLING_TEMP_SUPPLY_V      3.3f

// Series reference resistor in the voltage divider (Ω).
// Match to the actual resistor fitted on your board.
#define COOLING_TEMP_REF_RESISTOR  10000.0f

// NTC nominal resistance at the reference temperature T0 (Ω).
#define COOLING_TEMP_R0            10000.0f

// Reference temperature for the Beta equation (K).  25 °C = 298.15 K.
#define COOLING_TEMP_T0            298.15f

// Beta coefficient of the NTC element (K).
#define COOLING_TEMP_BETA          3435.0f

// ── Flow sensor ───────────────────────────────────────────────────────────
// Hall-effect pulses emitted per impeller revolution.
#define COOLING_FLOW_PULSES_PER_REV  static_cast<uint8_t>(1)

// =============================================================================
// Coolant tracking setpoints
// =============================================================================

// Nominal coolant operating temperature (°C) — centre of the in-range band.
#define COOLING_COOLANT_NOMINAL_TEMP_C  25.0f

// Expected coolant flow rate when the pump is running (L/min).
#define COOLING_FLOW_NOMINAL_LPM        1.0f

// =============================================================================
// Advanced parameters
// =============================================================================
// Internal algorithm constants, ADC/DAC tuning, loop timing, tracking-monitor
// thresholds, and FSM diagnostics.  Calibrated for the reference hardware;
// edit only when modifying hardware or retuning control algorithms.

#include "config_advanced.h"

#endif // CONFIG_H
