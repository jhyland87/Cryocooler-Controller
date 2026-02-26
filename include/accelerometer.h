#ifndef ACCELEROMETER_H
#define ACCELEROMETER_H

#include <stdint.h>
#include "module.h"

namespace accelerometer {

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

/**
 * Initialise the QMI8658, configure ranges/ODR, and perform calibration.
 * Safe to call if hardware is absent — isInitialized() will return false
 * and all getters will return 0 / false.
 */
module::InitStatus init();

/**
 * Read one sensor sample, update filter / orientation / motion state.
 * Must be called every main-loop tick.  No-op if isInitialized() == false.
 */
void service();

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

/** True if init() succeeded and the sensor is running. */
bool isInitialized();

/** True while checkMotion() detects significant acceleration or rotation. */
bool isMotionDetected();

/**
 * True when an overstroke (excessive motion) condition is active.
 * Backed by the same motionDetected state as isMotionDetected().
 */
bool hasOverstroke();


// ---------------------------------------------------------------------------
// Latest readings  (valid after the first successful service() call)
// ---------------------------------------------------------------------------

float getRoll();         ///< Roll  angle in degrees
float getPitch();        ///< Pitch angle in degrees
float getYaw();          ///< Yaw   angle in degrees (open-loop gyro integration)
float getAccelX();       ///< Filtered acceleration on X axis in m/s² (calibrated)
float getAccelY();       ///< Filtered acceleration on Y axis in m/s² (calibrated)
float getAccelZ();       ///< Filtered acceleration on Z axis in m/s² (calibrated)
float getAccelMag();     ///< Acceleration magnitude in m/s² (calibrated, unfiltered)
float getGyroMag();      ///< Gyroscope magnitude in deg/s   (calibrated, unfiltered)
float getTemperature();  ///< IMU die temperature in °C

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return accelerometer::init(); }
    static void service()            { accelerometer::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace accelerometer

#endif // ACCELEROMETER_H
