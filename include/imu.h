#ifndef IMU_H
#define IMU_H

#include <stdint.h>
#include "module.h"

namespace imu {

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

/**
 * Initialise the LSM6DSOX, configure ranges/ODR, and perform calibration.
 * Safe to call if hardware is absent — isInitialized() will return false
 * and all getters will return 0 / false.
 */
module::InitStatus init();

/**
 * Read one sensor sample, update filter / orientation / motion state.
 * Must be called every main-loop tick.
 * @return SERVICE_OK      — sample read and processed normally.
 *         SERVICE_SKIPPED — module not initialized, or no new sample ready this tick.
 */
module::ServiceStatus service();

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

/** True if init() succeeded and the sensor is running. */
bool isInitialized();

/** True if the LSM6DSOX was found and acknowledged on the I2C bus during init(). */
bool isAvailable();

/** True while checkMotion() detects significant acceleration or rotation. */
bool isMotionDetected();

/**
 * True when an overstroke (excessive motion) condition is active.
 * Backed by the same motionDetected state as isMotionDetected().
 */
bool hasOverstroke();

void clearOverstroke();


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
//float getGyroMag();      ///< Gyroscope magnitude in deg/s   (calibrated, unfiltered)
float getTemperature();         ///< IMU die temperature in °C
bool  isTemperaturePlausible(); ///< True when the last reading was within [MIN_PLAUSIBLE_AMBIENT_TEMP_C, MAX_PLAUSIBLE_AMBIENT_TEMP_C]
float getFrequency();  ///< Frequency of the linear motor in Hz (last valid FFT result)

/**
 * Collect FFT_N accelerometer-Z samples at FFT_FS_HZ, run an FFT, and
 * update the internal frequency estimate with an IIR-smoothed result.
 *
 * Blocks for approximately 640 ms (256 samples @ 400 Hz).  Should be called
 * infrequently — imu::service() gates this to once every FFT_INTERVAL_MS.
 * Amplifier code may call it directly when an on-demand frequency check is
 * needed, but should account for the blocking time.
 *
 * @return Detected frequency in Hz, or NAN when signal is absent / SNR is
 *         below threshold.  The internal frequency_ state is only updated on
 *         valid detections.
 */
float calculateFrequency();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = imu::init(); }
    static module::ServiceStatus service() { return _serviceStatus = imu::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace imu

#endif // IMU_H
