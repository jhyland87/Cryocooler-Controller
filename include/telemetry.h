/**
 * @file telemetry.h
 * @brief Serial Studio CSV telemetry emitter
 *
 * Emits one telemetry frame per call to emit() using the Serial Studio
 * "Quick Plot" frame format:
 *
 *   /*<csv_fields>*\/\r\n
 *
 * Fields (in column order, pipe-delimited):
 *   1  state_no         numeric state index -1 to 8
 *   2  state_name       ASCII state label (e.g. "CoarseCooldown")
 *   3  status_text      human-readable status description
 *   4  temp_k           cold-stage temperature in Kelvin   (2 dp)
 *   5  temp_c           cold-stage temperature in Celsius  (2 dp)
 *   6  cooling_rate     K/min; positive = cooling          (3 dp)
 *   7  dac_target       desired DAC count from state machine (0-4095)
 *   8  dac_actual       current DAC output count            (0-4095)
 *   9  rms_v            RMS voltage VDC                     (2 dp)
 *  10  relay_normal     0 = Bypass, 1 = Normal
 *  11  alarm_relay      0 = off,    1 = active
 *  12  red_led          1 = FAULT LED lit, 0 = off
 *  13  green_led        1 = READY LED lit, 0 = off
 *  14  on_duration_ms   total on-state duration in milliseconds
 *  15  on_duration      total on-state duration as HH:MM:SS
 *  16  cooldown_pct     cooldown progress 0–100 %           (2 dp)
 *  17  time_in_state    time spent in the current state as HH:MM:SS
 *  18  current_a        ACS712 AC RMS current in amps             (2 dp)
 *  19  backoff_count    cumulative back-EMF backoff events this run
 *
 * To visualise in Serial Studio:
 *   - Open Serial Studio, connect at SERIAL_BAUD.
 *   - Enable "Frame detection" with start seq "\/*" and end seq "*\/".
 *   - Load the Cryocooler.ssproj project file.
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include "state_machine.h"

namespace telemetry {

/**
 * Emit one Serial Studio CSV frame to Serial.
 *
 * @param out          State-machine output for this tick
 */
void emit(const state_machine::Output& out);

void disable();
void enable();
bool isEnabled();
} // namespace telemetry

#endif // TELEMETRY_H
