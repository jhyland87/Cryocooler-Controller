/**
 * @file accelerometer.cpp
 * @brief QMI8658 accelerometer implementation.
 *
 * Reads 6-DOF IMU data, applies offset calibration and a first-order
 * low-pass filter, computes roll/pitch/yaw orientation, and exposes
 * motion/overstroke detection via hasOverstroke().
 *
 * All public getters return the values captured during the most recent
 * successful sensor read and are safe to call between service() ticks.
 *
 * Calibration:
 *   performCalibration() is called once from init().  It spins on
 *   imu.readSensorData() until ACCEL_CAL_SAMPLES valid readings have
 *   been collected — no delay() calls.  At 1000 Hz ODR this takes ~1 s.
 *   Blocking at setup()-time is acceptable; no delay() is used.
 */

#include <QMI8658.h>
#include <math.h>
#include "accelerometer.h"
#include "hardware.h"
#include "pin_config.h"

namespace accelerometer {

// ---------------------------------------------------------------------------
// Tuning constants
// ---------------------------------------------------------------------------

static constexpr float    ACCEL_THRESHOLD_MPS2 = 2.0f;   // m/s² deviation from 9.81 to flag motion
static constexpr float    GYRO_THRESHOLD_DPS   = 10.0f;  // deg/s magnitude to flag motion
static constexpr uint32_t MOTION_TIMEOUT_MS    = 2000u;  // clear motion flag after this ms of stillness
static constexpr uint16_t ACCEL_CAL_SAMPLES    = 1000u;  // number of valid samples for calibration
static constexpr float    FILTER_ALPHA         = 0.1f;   // low-pass filter coefficient (0–1)

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static QMI8658 imu;
static bool initialized_ = false;

// Calibration offsets (set by performCalibration)
static float accelOffsetX_ = 0.0f, accelOffsetY_ = 0.0f, accelOffsetZ_ = 0.0f;
static float gyroOffsetX_  = 0.0f, gyroOffsetY_  = 0.0f, gyroOffsetZ_  = 0.0f;

// Low-pass filter state
static float filtAccelX_ = 0.0f, filtAccelY_ = 0.0f, filtAccelZ_ = 0.0f;
static float filtGyroX_  = 0.0f, filtGyroY_  = 0.0f, filtGyroZ_  = 0.0f;

// Latest processed readings — updated each service() call
static float roll_     = 0.0f;
static float pitch_    = 0.0f;
static float yaw_      = 0.0f;
static float accelMag_ = 0.0f;
static float gyroMag_  = 0.0f;
static float imuTemp_  = 0.0f;

// Motion / overstroke detection
static bool     motionDetected_ = false;
static uint32_t lastMotionMs_   = 0u;

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

/**
 * Blocks until ACCEL_CAL_SAMPLES valid readings are collected; no delay()
 * used — the function spins on imu.readSensorData() which returns false
 * when no new sample is ready.
 */
static void performCalibration() {
    float    accelSumX = 0.0f, accelSumY = 0.0f, accelSumZ = 0.0f;
    float    gyroSumX  = 0.0f, gyroSumY  = 0.0f, gyroSumZ  = 0.0f;
    uint16_t collected = 0u;

    while (collected < ACCEL_CAL_SAMPLES) {
        QMI8658_Data data;
        if (imu.readSensorData(data)) {
            accelSumX += data.accelX;
            accelSumY += data.accelY;
            accelSumZ += data.accelZ;
            gyroSumX  += data.gyroX;
            gyroSumY  += data.gyroY;
            gyroSumZ  += data.gyroZ;
            ++collected;
        }
    }

    const float n = static_cast<float>(collected);
    accelOffsetX_ = accelSumX / n;
    accelOffsetY_ = accelSumY / n;
    accelOffsetZ_ = (accelSumZ / n) - 9.81f;  // remove gravity component
    gyroOffsetX_  = gyroSumX  / n;
    gyroOffsetY_  = gyroSumY  / n;
    gyroOffsetZ_  = gyroSumZ  / n;
}

static void calculateOrientation(float ax, float ay, float az,
                                 float gx, float gy, float gz,
                                 float& roll, float& pitch, float& yaw) {
    roll  = atan2f(ay, sqrtf(ax*ax + az*az)) * 180.0f / M_PI;
    pitch = atan2f(-ax, sqrtf(ay*ay + az*az)) * 180.0f / M_PI;

    // Open-loop yaw integration from gyroscope (drifts over time).
    static float    yawInteg_  = 0.0f;
    static uint32_t lastTimeMs = 0u;

    const uint32_t now = millis();
    if (lastTimeMs > 0u) {
        const float dt = static_cast<float>(now - lastTimeMs) / 1000.0f;
        yawInteg_ += gz * dt;
    }
    lastTimeMs = now;

    // Wrap to [−180, 180]
    while (yawInteg_ >  180.0f) { yawInteg_ -= 360.0f; }
    while (yawInteg_ < -180.0f) { yawInteg_ += 360.0f; }
    yaw = yawInteg_;
}

static void checkMotion(float accelMag, float gyroMag) {
    const float    accelDeviation = fabsf(accelMag - 9.81f);
    const uint32_t now            = millis();

    if (accelDeviation > ACCEL_THRESHOLD_MPS2 || gyroMag > GYRO_THRESHOLD_DPS) {
        motionDetected_ = true;
        lastMotionMs_   = now;
    } else if (motionDetected_ && (now - lastMotionMs_) > MOTION_TIMEOUT_MS) {
        motionDetected_ = false;
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init() {
    // Pass the shared bus from hardware::i2c().  The vendored QMI8658 library
    // (lib/QMI8658) has its internal Wire.begin() call removed, so the bus
    // is initialised exactly once by hardware::init() and never re-entered.
    if (!imu.begin(hardware::i2c())) {
        // Device did not respond.  Run a full bus scan so the serial log
        // shows exactly what (if anything) is present — distinguishes a
        // wiring/pull-up issue from a driver/address mismatch.
        log_e("[accelerometer] QMI8658 not found — scanning I2C bus:");
        hardware::scanI2c();
        initialized_ = false;
        return module::InitStatus::MODULE_INIT_HARDWARE_ERROR;
    }

    imu.setAccelRange(QMI8658_ACCEL_RANGE_8G);
    imu.setAccelODR(QMI8658_ACCEL_ODR_1000HZ);
    imu.setGyroRange(QMI8658_GYRO_RANGE_512DPS);
    imu.setGyroODR(QMI8658_GYRO_ODR_1000HZ);
    imu.setAccelUnit_mps2(true);   // m/s²
    imu.setGyroUnit_rads(false);   // degrees per second
    imu.enableSensors(QMI8658_ENABLE_ACCEL | QMI8658_ENABLE_GYRO);

    performCalibration();
    initialized_ = true;
    return module::InitStatus::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    if (!initialized_) { return module::MODULE_SERVICE_SKIPPED; }

    QMI8658_Data data;
    if (!imu.readSensorData(data)) { return module::MODULE_SERVICE_SKIPPED; }

    // Apply calibration offsets
    const float ax = data.accelX - accelOffsetX_;
    const float ay = data.accelY - accelOffsetY_;
    const float az = data.accelZ - accelOffsetZ_;
    const float gx = data.gyroX  - gyroOffsetX_;
    const float gy = data.gyroY  - gyroOffsetY_;
    const float gz = data.gyroZ  - gyroOffsetZ_;

    // First-order low-pass filter
    filtAccelX_ = FILTER_ALPHA * ax + (1.0f - FILTER_ALPHA) * filtAccelX_;
    filtAccelY_ = FILTER_ALPHA * ay + (1.0f - FILTER_ALPHA) * filtAccelY_;
    filtAccelZ_ = FILTER_ALPHA * az + (1.0f - FILTER_ALPHA) * filtAccelZ_;
    filtGyroX_  = FILTER_ALPHA * gx + (1.0f - FILTER_ALPHA) * filtGyroX_;
    filtGyroY_  = FILTER_ALPHA * gy + (1.0f - FILTER_ALPHA) * filtGyroY_;
    filtGyroZ_  = FILTER_ALPHA * gz + (1.0f - FILTER_ALPHA) * filtGyroZ_;

    // Orientation from filtered data
    calculateOrientation(filtAccelX_, filtAccelY_, filtAccelZ_,
                         filtGyroX_,  filtGyroY_,  filtGyroZ_,
                         roll_, pitch_, yaw_);

    // Magnitudes from unfiltered data for spike sensitivity
    accelMag_ = sqrtf(ax*ax + ay*ay + az*az);
    gyroMag_  = sqrtf(gx*gx + gy*gy + gz*gz);
    imuTemp_  = data.temperature;

    checkMotion(accelMag_, gyroMag_);
    return module::MODULE_SERVICE_OK;
}

bool  isInitialized()    { return initialized_;    }
bool  isMotionDetected() { return motionDetected_;  }
bool  hasOverstroke()    { return motionDetected_;  }
float getRoll()          { return roll_;            }
float getPitch()         { return pitch_;           }
float getYaw()           { return yaw_;             }
float getAccelX()        { return filtAccelX_;      }
float getAccelY()        { return filtAccelY_;      }
float getAccelZ()        { return filtAccelZ_;      }
float getAccelMag()      { return accelMag_;        }
float getGyroMag()       { return gyroMag_;         }
float getTemperature()   { return imuTemp_;         }

} // namespace accelerometer
