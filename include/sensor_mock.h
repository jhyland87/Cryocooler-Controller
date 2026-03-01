/**
 * @file sensor_mock.h
 * @brief Runtime sensor override layer for hardware-free FSM testing.
 *
 * When mock mode is active, every sensor read site in main.cpp returns a
 * value from the Overrides table instead of polling real hardware.  All
 * override values can be changed at runtime via serial commands (see
 * commands.cpp), so you can drive the state machine through any scenario
 * without physical sensors present:
 *
 *   mock enable            -- enter mock mode (safe defaults)
 *   mock disable           -- return to real hardware
 *   mock status            -- print current override values
 *   mock temp   <K>        -- cold-stage temperature (Kelvin)
 *   mock rate   <K/min>    -- cooling rate (negative = cooling down)
 *   mock rms    <V>        -- RMS voltage seen by the compressor drive
 *   mock current <A>       -- INA260 current
 *   mock voltage <V>       -- INA260 bus voltage
 *   mock stall  <0|1>      -- temperature-stall flag
 *   mock stroke <0|1>      -- back-EMF overstroke flag
 *
 * Usage in main.cpp sensor read block:
 *
 *   const float tempK = sensor_mock::isActive()
 *                           ? sensor_mock::get().tempK
 *                           : cold_head::getLastTempK();
 *
 * Notes:
 *  - Only compiled for the embedded target (guarded by #ifdef ARDUINO).
 *  - Has no native-test stub; the read sites in main.cpp are themselves
 *    Arduino-only code and are never compiled for native tests.
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
    float coolingRate = 0.0f;     ///< Cooling rate, K/min (negative = getting colder)

    // ── Electrical ──────────────────────────────────────────────────────────
    float rmsVoltage  = 0.0f;     ///< Back-EMF RMS voltage (compressor drive)
    float currentA    = 0.0f;     ///< INA260 current, Amperes
    float voltageV    = 0.0f;     ///< INA260 bus voltage, Volts

    // ── Flags ────────────────────────────────────────────────────────────────
    bool  stalled     = false;    ///< Temperature-stall detection output
    bool  overstroke  = false;    ///< Back-EMF overstroke flag
};

/**
 * Activate mock mode.
 * Override values retain whatever was set previously (or safe defaults on the
 * first call).  Real sensor reads continue to run in the background; they just
 * aren't used by the state machine while mock mode is on.
 */
void enable();

/**
 * Deactivate mock mode.
 * The next loop tick reads all values from real hardware again.
 */
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

} // namespace sensor_mock

#endif // SENSOR_MOCK_H
