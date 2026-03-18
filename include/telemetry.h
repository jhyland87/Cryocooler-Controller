/**
 * @file telemetry.h
 * @brief Serial Studio CSV telemetry emitter and frame store.
 *
 * emit() snapshots all module state into a FrameBuilder, transmits it to
 * Serial in Serial Studio wire format, and retains the frame so that other
 * modules can read the same data in other formats via getLastFrame() /
 * fillJson().
 *
 * ── Serial Studio wire format ───────────────────────────────────────────────
 *   Frame:  /*<pipe-delimited values>*\/\r\n
 *   To visualise in Serial Studio:
 *     - Connect at SERIAL_BAUD.
 *     - Enable "Frame detection" with start seq "\/*" and end seq "*\/".
 *     - Load the Cryocooler.ssproj project file.
 *
 * ── Fields (pipe-delimited, in column order) ────────────────────────────────
 *   #   Key name                Type    Description
 *   1   state_no                int     numeric state index -1 to 8
 *   2   state_name              string  ASCII state label (e.g. "CoarseCooldown")
 *   3   status_text             string  human-readable status description
 *   4   temp_k                  float   cold-stage temperature in Kelvin        (2 dp)
 *   5   temp_c                  float   cold-stage temperature in Celsius       (2 dp)
 *   6   ambient_temp_c          float   room temperature from DS18S20 in °C    (2 dp)
 *   7   cooling_rate            float   K/min; positive = cooling              (3 dp)
 *   8   dac_target              uint    desired DAC count from state machine (0-4095)
 *   9   dac_actual              uint    current DAC output count             (0-4095)
 *  10   rms_v                   float   RMS voltage VDC                        (2 dp)
 *  11   relay_normal            uint    0 = Bypass, 1 = Normal
 *  12   alarm_relay             uint    0 = off,    1 = active
 *  13   red_led                 int     1 = FAULT LED lit, 0 = off
 *  14   green_led               int     1 = READY LED lit, 0 = off
 *  15   on_duration_ms          ulong   total on-state duration in milliseconds
 *  16   on_duration             string  total on-state duration as HH:MM:SS
 *  17   cooldown_pct            float   cooldown progress 0–100 %              (2 dp)
 *  18   time_in_state           string  time spent in the current state as HH:MM:SS
 *  19   rms.amps                 float   ACS712 AC RMS current in amps          (2 dp)
 *  20   backoff_count           uint    cumulative back-EMF backoff events this run
 *  22   voltage_v               float   sysinfo supply voltage in V              (2 dp)
 *  23   voltage_raw             float   raw ADC voltage reading                 (2 dp)
 *  24   waveform_status         uint    AD9833 waveform output status
 *  25   frequency_hz            float   AD9833 output frequency in Hz           (2 dp)
 *  26   accel.roll_deg          float   IMU roll  angle in degrees              (2 dp)
 *  27   accel.pitch_deg         float   IMU pitch angle in degrees              (2 dp)
 *  28   accel.yaw_deg           float   IMU yaw   angle in degrees (gyro integ) (2 dp)
 *  29   accel.accel_mag         float   Acceleration magnitude in m/s²          (2 dp)
 *  30   accel.gyro_mag          float   Gyroscope  magnitude in deg/s           (2 dp)
 *  31   accel.temp_c            float   IMU die temperature in °C               (1 dp)
 *  32   accel.motion            uint    1 = motion/overstroke detected, 0 = still
 *  33   accel.x                 float   Filtered X-axis acceleration in m/s²    (3 dp)
 *  34   accel.y                 float   Filtered Y-axis acceleration in m/s²    (3 dp)
 *  35   accel.z                 float   Filtered Z-axis acceleration in m/s²    (3 dp)
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include "frame_builder.h"
#include "state_machine.h"
#include "module.h"

namespace telemetry {
/**
 * Emit one telemetry frame to Serial in Serial Studio wire format and store
 * it as the last frame (accessible via getLastFrame() / fillJson()).
 *
 * @param out  State-machine output for this tick.
 */
void emit(const state_machine::Output& out);

/**
 * Return a const reference to the most recently emitted frame.
 *
 * The returned reference is valid until the next call to emit().
 * Before the first emit() the frame is empty (fieldCount() == 0).
 */
const FrameBuilder& getLastFrame();

/**
 * Populate @p doc with the most recently emitted frame as a JSON object.
 *
 * Equivalent to getLastFrame().fillJson(doc).
 * Any existing content in @p doc is cleared first.
 *
 * @param includeLogs  When true (default) the in-RAM log ring buffer is
 *                     appended under the "logs" key.  Pass false for
 *                     bandwidth-sensitive paths (e.g. the 1 Hz WebSocket
 *                     push stream) to keep the payload compact.
 */
void fillJson(JsonDocument& doc, bool includeLogs = true);

/**
 * Populate @p doc with telemetry, safe to call at any time — including during
 * startup before emit() has been called.
 *
 * Fast path: if emit() has been called at least once, delegates to fillJson()
 * and returns the real frame.
 *
 * Slow path (startup / setup failed): builds a JSON snapshot directly from
 * each module's current state.  Modules whose init() has not yet succeeded
 * have their data fields emitted as empty strings so the dashboard structure
 * is always fully populated.  Module init/service status fields are always
 * present and always reflect the real current status.
 *
 * @param includeLogs  When true (default) the in-RAM log ring buffer is
 *                     appended under the "logs" key.  Pass false for
 *                     bandwidth-sensitive paths (e.g. the 1 Hz WebSocket
 *                     push stream) to keep the payload compact.
 */
void fillJsonSafe(JsonDocument& doc, bool includeLogs = true);

/**
 * Emit one startup-progress telemetry frame to Serial and update lastFrame_.
 *
 * Intended to be called from setupModules() immediately after each
 * initModule() completes so that Serial Studio / the serial monitor shows
 * each module coming online in real time, and the dashboard fast-path
 * (fillJsonSafe) serves fresh data on its next 1 Hz tick.
 *
 * Uses the same module-ready checks as fillJsonSafe(): initialized modules
 * contribute real sensor values; uninitialized modules emit empty strings.
 * Module init/service status fields are always real.
 *
 * prevFrame_ is updated so the first real emit() delta only reports
 * genuinely new changes from the final init step onward.
 *
 * No-op when telemetry is disabled.
 */
void emitSafe();

void disable();
void enable();
bool isEnabled();

/**
 * Enable delta mode: emit() writes only the fields whose value has changed
 * since the previous frame to Serial.  fillJson() / getLastFrame() are
 * unaffected — they always return the complete current frame.
 */
void enableDelta();

/**
 * Disable delta mode: emit() writes the full frame to Serial (default).
 */
void disableDelta();

/** Return true while delta mode is active. */
bool isDeltaEnabled();

// ── Module interface ──────────────────────────────────────────────────────────
//
// telemetry::emit() has a non-standard signature (requires the state-machine
// Output struct), so it cannot map directly to a standard service() call.
// Module::service() is therefore a no-op; emit() must be called explicitly
// from the main control tick after the state machine has been advanced.
//
// enable() / disable() / isEnabled() are forwarded so the Module struct can
// be used with the optional toggling interface.

struct Module : ModuleBase<Module> {
    /** Telemetry requires no hardware setup; always succeeds immediately. */
    static module::InitStatus init() { telemetry::disable();return module::MODULE_INIT_SUCCESS; }
    // service() — inherited no-op; emit() is called explicitly from loop().
    static void enable()     { telemetry::enable(); }
    static void disable()    { telemetry::disable(); }
    static bool isEnabled()  { return telemetry::isEnabled(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace telemetry

#endif // TELEMETRY_H
