/**
 * @file sensor_mock.h
 * @brief Runtime sensor override layer for hardware-free FSM testing.
 *
 * When mock mode is active, every sensor read site pulls values from the
 * Overrides table instead of polling real hardware.  All override values can
 * be changed at runtime via serial commands (see mock_commands.cpp), so you
 * can drive the state machine through any scenario without physical sensors:
 *
 *   mock enable                          -- enter mock mode (safe defaults)
 *   mock disable                         -- return to real hardware
 *   mock status                          -- print current override values
 *   mock temp   <K>                      -- cold-stage temperature (Kelvin)
 *   mock rate   <K/min>                  -- cooling rate
 *   mock rms    <V>                      -- RMS voltage (compressor drive)
 *   mock current <A>                     -- INA260 current
 *   mock voltage <V>                     -- INA260 bus voltage
 *   mock stall  <0|1>                    -- temperature-stall flag
 *   mock stroke <0|1>                    -- back-EMF overstroke flag
 *
 * Dynamic / time-varying behaviour
 * ---------------------------------
 * Use ramps to simulate a continuously changing sensor value without sending
 * manual commands every loop tick:
 *
 *   mock ramp temp    <startK>  <endK>  <K/min>   -- e.g. mock ramp temp 300 77 3.5
 *   mock ramp rms     <startV>  <endV>  <V/min>   -- e.g. mock ramp rms 0 1.5 0.05
 *   mock ramp voltage <startV>  <endV>  <V/min>   -- e.g. mock ramp voltage 24 10 1.0
 *   mock ramp stop                                 -- cancel all active ramps
 *   mock ramp stop temp                            -- cancel temp ramp only
 *
 * While a temp ramp is active, sensor_mock::service() also auto-derives the
 * coolingRate field so the FSM sees a consistent dT/dt.
 *
 * Call sensor_mock::service(millis()) once per loop tick (before any module
 * reads) to advance active ramps.
 *
 * Notes:
 *  - Only compiled for the embedded target (guarded by #ifdef ARDUINO).
 *  - The Overrides struct is value-initialised to safe, benign defaults
 *    (room temperature, no faults) so enabling mock mode without setting
 *    any values is always safe.
 */

#ifndef SENSOR_MOCK_H
#define SENSOR_MOCK_H

#include <stdint.h>
#include <stdbool.h>

namespace sensor_mock {

/** All injectable sensor values in one flat struct. */
struct Overrides {
    // ── Cold head (PT100 / MAX31865) ────────────────────────────────────────
    float tempK       = 300.0f;   ///< Cold-stage temperature, Kelvin
    float coolingRate = 0.0f;     ///< Cooling rate, K/min (positive = cooling down)

    // ── Electrical ──────────────────────────────────────────────────────────
    float rmsVoltageV = 0.0f;     ///< Back-EMF RMS voltage (compressor drive)
    float rmsCurrentA = 0.0f;     ///< Back-EMF RMS current, Amperes
    float currentA    = 0.0f;     ///< INA260 current, Amperes
    float voltageV    = 0.0f;     ///< INA260 bus voltage, Volts

    // ── Flags ────────────────────────────────────────────────────────────────
    bool  stalled     = false;    ///< Temperature-stall detection output
    bool  overstroke  = false;    ///< Back-EMF overstroke flag
};

// =============================================================================
// Ramp subsystem
// =============================================================================

/**
 * Which field a RampSpec targets.
 * Indices are stable — used as array indices in sensor_mock.cpp.
 */
enum class RampField : uint8_t {
    Temp    = 0,  ///< Overrides::tempK  (also auto-updates coolingRate)
    Rms     = 1,  ///< Overrides::rmsVoltageV
    Voltage = 2,  ///< Overrides::voltageV
    Count   = 3   ///< sentinel — total number of rampable fields
};

/**
 * Parameters for one active ramp segment.
 * The ramp moves linearly from startVal to endVal at ratePerMin units/minute.
 * When the value reaches endVal the ramp deactivates automatically.
 */
struct RampSpec {
    bool     active     = false;
    float    startVal   = 0.0f;
    float    endVal     = 0.0f;
    float    ratePerMin = 0.0f;   ///< Always > 0; direction is derived from start/end
    uint32_t startMs    = 0;
};

// =============================================================================
// Core API
// =============================================================================

/**
 * Activate mock mode.
 * Override values retain whatever was set previously (or safe defaults on the
 * first call).
 */
void enable();

/** Deactivate mock mode. Next loop tick reads all values from real hardware. */
void disable();

/** Returns true while mock mode is active. */
bool isActive();

/**
 * Returns a mutable reference to the current override table.
 * Callers may read or write individual fields directly:
 *
 *   sensor_mock::get().tempK = 85.0f;
 */
Overrides& get();

// =============================================================================
// Ramp API
// =============================================================================

/**
 * Start a linear ramp for the given field.
 *
 * @param field      Which sensor field to ramp.
 * @param startVal   Value at t=0.
 * @param endVal     Target value; ramp stops when this is reached.
 * @param ratePerMin Speed in units per minute (must be > 0).
 * @param nowMs      Current millis() timestamp (ramp start time).
 *
 * The corresponding Overrides field is set to startVal immediately.
 * Calling this again for the same field replaces the previous ramp.
 */
void startRamp(RampField field,
               float startVal, float endVal, float ratePerMin,
               uint32_t nowMs);

/**
 * Cancel the ramp for the given field.
 * The current Overrides value is left as-is (frozen at the last computed
 * value), so the FSM won't see a sudden jump.
 */
void stopRamp(RampField field);

/** Cancel all active ramps. */
void stopAllRamps();

/**
 * Retrieve the RampSpec for inspection (e.g. for status output).
 * @param field  The field whose spec is requested.
 */
const RampSpec& getRamp(RampField field);

/**
 * Advance all active ramps by computing the new value for @p nowMs and
 * writing it into the Overrides table.  For Temp ramps, coolingRate is also
 * updated to match the ramp rate.
 *
 * Call once per loop tick, before any module reads.
 *
 * Has no effect when mock mode is inactive or when no ramp is active.
 *
 * @param nowMs  Current millis() timestamp.
 */
void service(uint32_t nowMs);

} // namespace sensor_mock

#endif // SENSOR_MOCK_H
