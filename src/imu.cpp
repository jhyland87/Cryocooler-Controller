/**
 * @file imu.cpp
 * @brief LSM6DSOX IMU implementation (via Adafruit LSM6DS library).
 *
 * Reads 6-DOF IMU data, applies offset calibration and a first-order
 * low-pass filter, computes roll/pitch/yaw orientation, and exposes
 * motion/overstroke detection via hasOverstroke().
 *
 * Frequency detection:
 *   checkFrequency() collects FFT_N samples at FFT_FS_HZ using a
 *   micros()-paced busy-wait loop (no delay() calls), then runs an
 *   FFT with Hann windowing and quadratic peak interpolation.
 *   The LSM6DSOX ODR is 833 Hz (≈1.2 ms per sample), so each read in the
 *   2500 us-spaced loop returns genuinely fresh data.  The collection
 *   window is ~640 ms and is triggered once every FFT_INTERVAL_MS.
 *
 * Calibration:
 *   performCalibration() is called once from init().  It reads
 *   ACCEL_CAL_SAMPLES samples with a brief delay between reads to
 *   allow the sensor to produce new data.  At 833 Hz ODR this takes ~1.2 s.
 *   Blocking at setup()-time is acceptable.
 */

#include <Adafruit_LSM6DSOX.h>
#include <arduinoFFT.h>
#include <math.h>
#include <Wire.h>
#include "imu.h"
#include "config.h"
#include "hardware.h"
#include "pin_config.h"
#include "logger.h"

namespace imu {

// ---------------------------------------------------------------------------
// Tuning constants
// ---------------------------------------------------------------------------

static constexpr float    ACCEL_THRESHOLD_MPS2 = 2.0f;   // m/s² deviation from 9.81 to flag motion
static constexpr uint32_t MOTION_TIMEOUT_MS    = 2000u;  // clear motion flag after this ms of stillness
static constexpr uint16_t ACCEL_CAL_SAMPLES    = 1000u;  // number of valid samples for calibration
static constexpr float    FILTER_ALPHA         = 0.1f;   // low-pass filter coefficient (0–1)

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static Adafruit_LSM6DSOX sensor;

/// Set true by init() only when sensor.begin_I2C() confirms the LSM6DSOX is
/// present and responding.  Guards service() and calculateFrequency() so
/// they silently skip rather than flood the log with I2C errors when the
/// hardware is absent.
static bool sImuAvailable = false;

// Calibration offsets (set by performCalibration)
static float accelOffsetX_ = 0.0f, accelOffsetY_ = 0.0f, accelOffsetZ_ = 0.0f;

// Low-pass filter state
static float filtAccelX_ = 0.0f, filtAccelY_ = 0.0f, filtAccelZ_ = 0.0f;

// Latest processed readings — updated each service() call
static float roll_     = 0.0f;
static float pitch_    = 0.0f;
static float yaw_      = 0.0f;
static float accelMag_ = 0.0f;
static float imuTemp_         = 0.0f;
static bool  imuTempPlausible_ = false;
static float frequency_ = 0.0f;
// Motion / overstroke detection
static bool     motionDetected_ = false;
static uint32_t lastMotionMs_   = 0u;

static LogStream _Log = Log.createChildLogger("imu");
// ---------------------------------------------------------------------------
// FFT frequency detection state
// ---------------------------------------------------------------------------

// Number of samples per FFT window.
static constexpr uint16_t FFT_N            = 256u;
// Sampling rate for the FFT collection loop (Hz).
// Must be > 2 × max expected frequency.  LSM6DSOX ODR (833 Hz) >> 400 Hz,
// so each read in the 2500 us-paced loop always returns fresh data.
static constexpr float    FFT_FS_HZ        = 400.0f;
// Inter-sample period in microseconds (1 000 000 / FFT_FS_HZ).
static constexpr uint32_t FFT_SAMPLE_US    = static_cast<uint32_t>(1000000.0f / FFT_FS_HZ); // 2500 us
// Search band for the peak bin (Hz).
static constexpr float    FFT_SEARCH_MIN   = 45.0f;
static constexpr float    FFT_SEARCH_MAX   = 75.0f;
// Minimum vibration amplitude (g) required to trust the result.
static constexpr float    FFT_AMP_ON_G     = 0.015f;
// Minimum peak-to-noise-floor ratio required to trust the result.
static constexpr float    FFT_MIN_SNR      = 5.0f;
// IIR smoothing weight applied to accepted measurements (0 < alpha <= 1).
static constexpr float    FFT_FREQ_ALPHA   = 0.15f;
// Minimum interval between FFT runs (ms).
// The ~640 ms collection window is included in this interval.
static constexpr uint32_t FFT_INTERVAL_MS  = 5000u;

static float fftVReal_[FFT_N];
static float fftVImag_[FFT_N];
static float fftZBuf_[FFT_N];
// ArduinoFFT v2 — template on sample type.
static ArduinoFFT<float> fft_(fftVReal_, fftVImag_, FFT_N, FFT_FS_HZ);

static float    fftFiltered_ = NAN;   // IIR-smoothed frequency estimate
static uint32_t lastFftMs_   = 0u;    // millis() of last FFT run

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

/**
 * Read ACCEL_CAL_SAMPLES from the sensor with brief delays between reads
 * to allow the sensor to produce fresh data at its configured ODR.
 */
static void performCalibration() {
    float    accelSumX = 0.0f, accelSumY = 0.0f, accelSumZ = 0.0f;
    uint16_t collected = 0u;

    sensors_event_t accel, gyro, temp;
    while (collected < ACCEL_CAL_SAMPLES) {
        sensor.getEvent(&accel, &gyro, &temp);
        accelSumX += accel.acceleration.x;
        accelSumY += accel.acceleration.y;
        accelSumZ += accel.acceleration.z;
        ++collected;
        delayMicroseconds(1200);  // ~833 Hz ODR → 1.2 ms per fresh sample
    }

    const float n = static_cast<float>(collected);
    accelOffsetX_ = accelSumX / n;
    accelOffsetY_ = accelSumY / n;
    accelOffsetZ_ = (accelSumZ / n) - 9.81f;  // remove gravity component
}

static void calculateOrientation(float ax, float ay, float az,
                                 float& roll, float& pitch, float& yaw) {
    roll  = atan2f(ay, sqrtf(ax*ax + az*az)) * 180.0f / M_PI;
    pitch = atan2f(-ax, sqrtf(ay*ay + az*az)) * 180.0f / M_PI;

    // Open-loop yaw integration from gyroscope (drifts over time).
    static float    yawInteg_  = 0.0f;
    static uint32_t lastTimeMs = 0u;

    const uint32_t now = millis();
    if (lastTimeMs > 0u) {
        const float dt = static_cast<float>(now - lastTimeMs) / 1000.0f;
        (void)dt;  // gyro yaw integration currently disabled
    }
    lastTimeMs = now;

    // Wrap to [−180, 180]
    while (yawInteg_ >  180.0f) { yawInteg_ -= 360.0f; }
    while (yawInteg_ < -180.0f) { yawInteg_ += 360.0f; }
    yaw = yawInteg_;
}

// Forward declaration — calculateFrequency() is defined after service() but called from it.
float calculateFrequency();

// ---------------------------------------------------------------------------
// FFT helpers (adapted from imu-fft-hz-test.cpp)
// ---------------------------------------------------------------------------

/** Hann window coefficient for sample index @p i. */
static inline float fftHann(uint16_t i) {
    return 0.5f * (1.0f - cosf((2.0f * static_cast<float>(M_PI) * i)
                               / static_cast<float>(FFT_N - 1u)));
}

/** In-place selection sort; returns median of @p arr[0..len-1]. */
static float fftMedian(float* arr, uint16_t len) {
    for (uint16_t i = 0u; i < len; ++i) {
        uint16_t m = i;
        for (uint16_t j = i + 1u; j < len; ++j) {
            if (arr[j] < arr[m]) m = j;
        }
        const float t = arr[i]; arr[i] = arr[m]; arr[m] = t;
    }
    return arr[len / 2u];
}

struct FftResult { float freq; float snr; };

/**
 * DC-remove, Hann-window, FFT, find peak in [FFT_SEARCH_MIN, FFT_SEARCH_MAX],
 * estimate noise via median, apply quadratic interpolation for sub-bin accuracy.
 */
static FftResult fftDetect(const float* data) {
    float mean = 0.0f;
    for (uint16_t i = 0u; i < FFT_N; ++i) mean += data[i];
    mean /= static_cast<float>(FFT_N);

    for (uint16_t i = 0u; i < FFT_N; ++i) {
        fftVReal_[i] = (data[i] - mean) * fftHann(i);
        fftVImag_[i] = 0.0f;
    }

    fft_.compute(FFTDirection::Forward);
    fft_.complexToMagnitude();

    const float    binHz = FFT_FS_HZ / static_cast<float>(FFT_N);
    const uint16_t kMin  = static_cast<uint16_t>(ceilf(FFT_SEARCH_MIN / binHz));
    uint16_t       kMax  = static_cast<uint16_t>(floorf(FFT_SEARCH_MAX / binHz));
    if (kMax > (FFT_N / 2u - 1u)) kMax = FFT_N / 2u - 1u;

    // Find peak bin
    uint16_t kPeak = kMin;
    float    peak  = fftVReal_[kMin];
    for (uint16_t k = kMin + 1u; k <= kMax; ++k) {
        if (fftVReal_[k] > peak) { peak = fftVReal_[k]; kPeak = k; }
    }

    // Noise floor via median of search-band magnitudes
    float    mags[64];
    uint16_t cnt = 0u;
    for (uint16_t k = kMin; k <= kMax && cnt < 64u; ++k) {
        mags[cnt++] = fftVReal_[k];
    }
    float noise = fftMedian(mags, cnt);
    if (noise < 1e-9f) noise = 1e-9f;

    // Coarse bin centre frequency
    float freq = static_cast<float>(kPeak) * binHz;

    // Quadratic interpolation for sub-bin precision
    if (kPeak > 1u && kPeak < FFT_N / 2u - 1u) {
        const float a     = fftVReal_[kPeak - 1u];
        const float b     = fftVReal_[kPeak];
        const float c     = fftVReal_[kPeak + 1u];
        const float denom = a - 2.0f * b + c;
        if (fabsf(denom) > 1e-9f) {
            freq = (static_cast<float>(kPeak) + 0.5f * (a - c) / denom) * binHz;
        }
    }

    return { freq, peak / noise };
}

static void checkMotion(float accelMag) {
    const float    accelDeviation = fabsf(accelMag - 9.81f);
    const uint32_t now            = millis();

    if (accelDeviation > ACCEL_THRESHOLD_MPS2) {
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
    if (!sensor.begin_I2C(LSM6DSOX_IMU_IC2_ADDRESS, &hardware::i2c())) {
        _Log.println("LSM6DSOX not found — check wiring and I2C address");
        sImuAvailable = false;
        return module::InitStatus::MODULE_INIT_SUCCESS;   // non-fatal
    }
    _Log.println("LSM6DSOX found — continuing");
    sImuAvailable = true;

    sensor.setAccelRange(LSM6DS_ACCEL_RANGE_8_G);
    sensor.setAccelDataRate(LSM6DS_RATE_833_HZ);
    sensor.setGyroRange(LSM6DS_GYRO_RANGE_500_DPS);
    sensor.setGyroDataRate(LSM6DS_RATE_833_HZ);

    performCalibration();
    return module::InitStatus::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    if (!sImuAvailable) { return module::MODULE_SERVICE_SKIPPED; }

    sensors_event_t accelEvt, gyroEvt, tempEvt;
    sensor.getEvent(&accelEvt, &gyroEvt, &tempEvt);

    // Apply calibration offsets (Adafruit unified sensor returns m/s²)
    const float ax = accelEvt.acceleration.x - accelOffsetX_;
    const float ay = accelEvt.acceleration.y - accelOffsetY_;
    const float az = accelEvt.acceleration.z - accelOffsetZ_;

    // First-order low-pass filter
    filtAccelX_ = FILTER_ALPHA * ax + (1.0f - FILTER_ALPHA) * filtAccelX_;
    filtAccelY_ = FILTER_ALPHA * ay + (1.0f - FILTER_ALPHA) * filtAccelY_;
    filtAccelZ_ = FILTER_ALPHA * az + (1.0f - FILTER_ALPHA) * filtAccelZ_;

    // Orientation from filtered data
    calculateOrientation(filtAccelX_, filtAccelY_, filtAccelZ_,
                         roll_, pitch_, yaw_);

    // Magnitudes from unfiltered data for spike sensitivity
    accelMag_ = sqrtf(ax*ax + ay*ay + az*az);

    // Temperature from the unified sensor event
    {
        const float tempReading = tempEvt.temperature;
        if (tempReading >= MIN_PLAUSIBLE_AMBIENT_TEMP_C && tempReading <= MAX_PLAUSIBLE_AMBIENT_TEMP_C) {
            imuTemp_          = tempReading;
            imuTempPlausible_ = true;
        } else {
            imuTempPlausible_ = false;
        }
    }

    checkMotion(accelMag_);

    // Periodically run FFT frequency detection.
    // checkFrequency() blocks for ~640 ms; the gate limits this to once every
    // FFT_INTERVAL_MS so the main loop is only briefly paused every few seconds.
    if ((millis() - lastFftMs_) >= FFT_INTERVAL_MS) {
        lastFftMs_ = millis();
        calculateFrequency();
    }

    return module::MODULE_SERVICE_OK;
}

float getFrequency() {
    return frequency_;
}

/**
 * Collect FFT_N accelerometer-Z samples at FFT_FS_HZ, run an FFT, and
 * update frequency_ with the IIR-smoothed result.
 *
 * Timing: uses a micros()-paced busy-wait loop (~640 ms total).  No delay()
 * is used.  The LSM6DSOX ODR is 833 Hz so each read in the 2500 us loop
 * always returns a genuinely fresh sample.  This function should be called
 * infrequently (every FFT_INTERVAL_MS) to limit its impact on the main loop.
 *
 * @return The detected frequency in Hz, or NAN when the signal is absent or
 *         the SNR is below threshold.  The internal frequency_ state is only
 *         updated on valid detections.
 */
float calculateFrequency() {
    if (!sImuAvailable) return NAN;

    // -- Collect FFT_N samples at FFT_FS_HZ using micros() timing ------------
    uint32_t tNext = micros();
    float    sumSq  = 0.0f;
    float    zMin   =  999.0f;
    float    zMax   = -999.0f;

    sensors_event_t accelEvt, gyroEvt, tempEvt;

    for (uint16_t i = 0u; i < FFT_N; ++i) {
        // Busy-wait for the next sample slot — no delay().
        while (static_cast<int32_t>(micros() - tNext) < 0) { /* spin */ }
        tNext += FFT_SAMPLE_US;

        sensor.getEvent(&accelEvt, &gyroEvt, &tempEvt);
        fftZBuf_[i] = accelEvt.acceleration.z / 9.80665f;   // convert m/s² → g

        const float z = fftZBuf_[i];
        sumSq += z * z;
        if (z < zMin) zMin = z;
        if (z > zMax) zMax = z;
    }

    // -- Run FFT and evaluate result ------------------------------------------
    const float     zPeak  = (zMax - zMin) * 0.5f;
    const FftResult result = fftDetect(fftZBuf_);
    const bool      valid  = (zPeak > FFT_AMP_ON_G) && (result.snr > FFT_MIN_SNR);

    if (valid) {
        if (!isfinite(fftFiltered_)) {
            fftFiltered_ = result.freq;
        } else {
            fftFiltered_ = (1.0f - FFT_FREQ_ALPHA) * fftFiltered_
                           + FFT_FREQ_ALPHA * result.freq;
        }
        frequency_ = fftFiltered_;
    } else {
        fftFiltered_ = NAN;
        // Keep the last valid frequency_ when signal is absent.
    }

    if (!isfinite(fftFiltered_)) return NAN;
    return frequency_;
}

bool  isInitialized()    { return Module::isInitialized(); }
bool  isAvailable()      { return sImuAvailable; }
bool  isMotionDetected() { return motionDetected_;  }
bool  hasOverstroke()    { return motionDetected_;  }
void  clearOverstroke()  { motionDetected_ = false; }
float getRoll()          { return roll_;            }
float getPitch()         { return pitch_;           }
float getYaw()           { return yaw_;             }
float getAccelX()        { return filtAccelX_;      }
float getAccelY()        { return filtAccelY_;      }
float getAccelZ()        { return filtAccelZ_;      }
float getAccelMag()      { return accelMag_;        }
float getTemperature()         { return imuTemp_;          }
bool  isTemperaturePlausible() { return imuTempPlausible_; }

} // namespace imu
