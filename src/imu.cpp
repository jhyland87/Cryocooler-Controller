/**
 * @file imu.cpp
 * @brief LSM6DSOX IMU implementation (via Adafruit LSM6DS library — FIFO mode).
 *
 * Reads 6-DOF IMU data from the hardware FIFO, applies offset calibration
 * and a first-order low-pass filter, computes roll/pitch/yaw orientation,
 * and exposes motion/overstroke detection via hasOverstroke().
 *
 * FIFO mode:
 *   The LSM6DSOX FIFO is configured in continuous mode at 833 Hz for both
 *   accelerometer and gyroscope.  service() drains the FIFO each tick,
 *   processing all available samples.
 *
 * Frequency detection:
 *   Z-axis accelerometer samples are accumulated from the FIFO into an FFT
 *   buffer.  When FFT_N samples have been collected and FFT_INTERVAL_MS has
 *   elapsed, an FFT with Hann windowing and quadratic peak interpolation is
 *   run.  This is entirely non-blocking — no busy-wait collection loop.
 *
 * Calibration:
 *   performCalibration() is called once from init().  It reads
 *   ACCEL_CAL_SAMPLES accelerometer and gyroscope samples from the FIFO,
 *   computes mean offsets (gravity vector for accel, bias for gyro).
 *   Blocking at setup()-time is acceptable.
 */

#include <Adafruit_LSM6DSOX.h>
#include <arduinoFFT.h>
#include <math.h>
#include <SPI.h>
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

// Raw-to-engineering-unit scale factors for the configured ranges.
// 8 g accel: sensitivity = 0.244 mg/LSB → 0.000244 g/LSB
// 500 dps gyro: sensitivity = 17.50 mdps/LSB
static constexpr float ACCEL_SCALE_MPS2 = 0.000244f * 9.80665f;  // raw int16 → m/s²
static constexpr float ACCEL_SCALE_G    = 0.000244f;              // raw int16 → g

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static Adafruit_LSM6DSOX sensor;

/// Set true by init() only when sensor.begin_SPI() confirms the LSM6DSOX is
/// present and responding.  Guards service() and calculateFrequency() so
/// they silently skip when the hardware is absent.
static bool sImuAvailable = false;

// Calibration offsets — accel in m/s² (gravity preserved), gyro in raw int16
static float accelOffsetX_ = 0.0f, accelOffsetY_ = 0.0f, accelOffsetZ_ = 0.0f;
static float gyroBiasX_    = 0.0f, gyroBiasY_    = 0.0f, gyroBiasZ_    = 0.0f;

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

// Temperature is read from output registers (not FIFO) at a lower cadence.
static uint32_t lastTempMs_ = 0u;
static constexpr uint32_t TEMP_READ_INTERVAL_MS = 1000u;

static LogStream _Log = Log.createChildLogger("imu");
// ---------------------------------------------------------------------------
// FFT frequency detection state
// ---------------------------------------------------------------------------

// Number of samples per FFT window.
static constexpr uint16_t FFT_N            = 256u;
// Effective sampling rate — matches the FIFO batch rate.
static constexpr float    FFT_FS_HZ        = 833.0f;
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
static constexpr uint32_t FFT_INTERVAL_MS  = 1000u;

static float fftVReal_[FFT_N];
static float fftVImag_[FFT_N];
static float fftZBuf_[FFT_N];
// ArduinoFFT v2 — template on sample type.
static ArduinoFFT<float> fft_(fftVReal_, fftVImag_, FFT_N, FFT_FS_HZ);

static float    fftFiltered_ = NAN;   // IIR-smoothed frequency estimate
static uint32_t lastFftMs_   = 0u;    // millis() of last FFT run
static uint16_t fftBufIdx_   = 0u;    // accumulation index into fftZBuf_

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

/**
 * FIFO-based calibration.  Reads ACCEL_CAL_SAMPLES of accelerometer and
 * gyroscope data from the FIFO, computes mean offsets for gravity removal
 * and gyro bias.  The sensor must be stationary during this process.
 */
static void performCalibration() {
    _Log.println("Calibrating — keep sensor still...");

    // Flush any stale FIFO data
    sensor.resetFIFO();
    delay(50);

    float    accelSumX = 0.0f, accelSumY = 0.0f, accelSumZ = 0.0f;
    float    gyroSumX  = 0.0f, gyroSumY  = 0.0f, gyroSumZ  = 0.0f;
    uint16_t accelCollected = 0u, gyroCollected = 0u;

    while (accelCollected < ACCEL_CAL_SAMPLES || gyroCollected < ACCEL_CAL_SAMPLES) {
        uint16_t count = sensor.getFIFOCount();
        if (count == 0) {
            delay(5);
            continue;
        }

        lsm6ds_fifo_tag_t tag;
        int16_t rx, ry, rz;

        while (sensor.readFIFOWord(tag, rx, ry, rz)) {
            if (tag == LSM6DS_FIFO_TAG_ACCEL_NC && accelCollected < ACCEL_CAL_SAMPLES) {
                accelSumX += static_cast<float>(rx) * ACCEL_SCALE_MPS2;
                accelSumY += static_cast<float>(ry) * ACCEL_SCALE_MPS2;
                accelSumZ += static_cast<float>(rz) * ACCEL_SCALE_MPS2;
                ++accelCollected;
            } else if (tag == LSM6DS_FIFO_TAG_GYRO_NC && gyroCollected < ACCEL_CAL_SAMPLES) {
                gyroSumX += static_cast<float>(rx);
                gyroSumY += static_cast<float>(ry);
                gyroSumZ += static_cast<float>(rz);
                ++gyroCollected;
            }
        }

        // Yield every 100 accel samples to feed the FreeRTOS task watchdog.
        if ((accelCollected % 100u) == 0u) { yield(); }
    }

    const float na = static_cast<float>(accelCollected);
    accelOffsetX_ = accelSumX / na;
    accelOffsetY_ = accelSumY / na;
    accelOffsetZ_ = (accelSumZ / na) - 9.81f;  // preserve gravity component

    const float ng = static_cast<float>(gyroCollected);
    gyroBiasX_ = gyroSumX / ng;
    gyroBiasY_ = gyroSumY / ng;
    gyroBiasZ_ = gyroSumZ / ng;

    // Seed filter state with expected stationary values so there is no ramp-up.
    filtAccelX_ = 0.0f;
    filtAccelY_ = 0.0f;
    filtAccelZ_ = 9.81f;

    _Log.println("Calibration done — accel offsets: " +
                 String(accelOffsetX_, 3) + ", " +
                 String(accelOffsetY_, 3) + ", " +
                 String(accelOffsetZ_, 3));
    _Log.println("  gyro bias (raw): " +
                 String(gyroBiasX_, 1) + ", " +
                 String(gyroBiasY_, 1) + ", " +
                 String(gyroBiasZ_, 1));

    // Flush FIFO so service() starts with fresh data.
    sensor.resetFIFO();
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

/**
 * Run FFT on the accumulated fftZBuf_ samples and update the internal
 * frequency estimate with an IIR-smoothed result.
 */
static void runFft() {
    // Compute min/max for amplitude check
    float zMin =  999.0f, zMax = -999.0f;
    for (uint16_t i = 0u; i < FFT_N; ++i) {
        if (fftZBuf_[i] < zMin) zMin = fftZBuf_[i];
        if (fftZBuf_[i] > zMax) zMax = fftZBuf_[i];
    }

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
        frequency_   = NAN;   // clear stale reading when vibration stops
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

module::InitStatus init() {
    // Restore SPI pins after AD9833 library's begin() may have reset them.
    SPI.end();
    SPI.begin(SPI_CLK, SPI_MISO, SPI_MOSI, -1);

    if (!sensor.begin_SPI(LSM6DSOX_CS, &SPI)) {
        _Log.println("LSM6DSOX not found on SPI — check wiring (CS=GPIO" + String(LSM6DSOX_CS) + ")");
        sImuAvailable = false;
        return module::InitStatus::MODULE_INIT_SUCCESS;   // non-fatal
    }
    _Log.println("LSM6DSOX found on SPI — continuing");
    sImuAvailable = true;

    sensor.setAccelRange(LSM6DS_ACCEL_RANGE_8_G);
    sensor.setAccelDataRate(LSM6DS_RATE_833_HZ);
    sensor.setGyroRange(LSM6DS_GYRO_RANGE_500_DPS);
    sensor.setGyroDataRate(LSM6DS_RATE_833_HZ);

    // Enable FIFO in continuous mode at the same rate as the ODR.
    sensor.setFIFOAccelBatchRate(LSM6DS_FIFO_RATE_833_HZ);
    sensor.setFIFOGyroBatchRate(LSM6DS_FIFO_RATE_833_HZ);
    sensor.setFIFOMode(LSM6DS_FIFO_CONTINUOUS);

    performCalibration();
    return module::InitStatus::MODULE_INIT_SUCCESS;
}

static void clearReadings() {
    filtAccelX_      = NAN;
    filtAccelY_      = NAN;
    filtAccelZ_      = NAN;
    accelMag_        = NAN;
    imuTemp_         = NAN;
    imuTempPlausible_ = false;
    roll_            = NAN;
    pitch_           = NAN;
    yaw_             = NAN;
    frequency_       = NAN;
    fftFiltered_     = NAN;
    fftBufIdx_       = 0u;
    motionDetected_  = false;
}

module::ServiceStatus service() {
    if (!sImuAvailable) { return module::MODULE_SERVICE_SKIPPED; }

    // Drain all available FIFO samples.
    uint16_t count = sensor.getFIFOCount();
    if (count == 0) { return module::MODULE_SERVICE_OK; }

    lsm6ds_fifo_tag_t tag;
    int16_t rx, ry, rz;
    bool hadAccel = false;

    while (sensor.readFIFOWord(tag, rx, ry, rz)) {
        if (tag == LSM6DS_FIFO_TAG_ACCEL_NC) {
            // Convert raw → m/s² and apply calibration offsets.
            const float ax = (static_cast<float>(rx) * ACCEL_SCALE_MPS2) - accelOffsetX_;
            const float ay = (static_cast<float>(ry) * ACCEL_SCALE_MPS2) - accelOffsetY_;
            const float az = (static_cast<float>(rz) * ACCEL_SCALE_MPS2) - accelOffsetZ_;

            // First-order low-pass filter
            filtAccelX_ = FILTER_ALPHA * ax + (1.0f - FILTER_ALPHA) * filtAccelX_;
            filtAccelY_ = FILTER_ALPHA * ay + (1.0f - FILTER_ALPHA) * filtAccelY_;
            filtAccelZ_ = FILTER_ALPHA * az + (1.0f - FILTER_ALPHA) * filtAccelZ_;

            // Magnitude from unfiltered data for spike sensitivity
            accelMag_ = sqrtf(ax*ax + ay*ay + az*az);

            // Accumulate Z-axis for FFT (raw → g; DC-removed inside fftDetect)
            if (fftBufIdx_ < FFT_N) {
                fftZBuf_[fftBufIdx_++] = static_cast<float>(rz) * ACCEL_SCALE_G;
            }

            hadAccel = true;
        }
        // Gyro samples are read (draining FIFO) but not processed further.
        // gyroBias values are available for future gyro integration.
    }

    if (hadAccel) {
        // Orientation from filtered data
        calculateOrientation(filtAccelX_, filtAccelY_, filtAccelZ_,
                             roll_, pitch_, yaw_);

        checkMotion(accelMag_);
    }

    // Read temperature from output registers (independent of FIFO) at a
    // lower cadence — temperature changes slowly and getEvent() is a full
    // SPI read of accel+gyro+temp output registers.
    {
        const uint32_t now = millis();
        if ((now - lastTempMs_) >= TEMP_READ_INTERVAL_MS) {
            lastTempMs_ = now;
            sensors_event_t accelEvt, gyroEvt, tempEvt;
            sensor.getEvent(&accelEvt, &gyroEvt, &tempEvt);
            const float tempReading = tempEvt.temperature;
            if (tempReading >= MIN_PLAUSIBLE_AMBIENT_TEMP_C && tempReading <= MAX_PLAUSIBLE_AMBIENT_TEMP_C) {
                imuTemp_          = tempReading;
                imuTempPlausible_ = true;
            } else {
                imuTempPlausible_ = false;
            }
        }
    }

    // Run FFT when the accumulation buffer is full.
    if (fftBufIdx_ >= FFT_N) {
        if ((millis() - lastFftMs_) >= FFT_INTERVAL_MS) {
            lastFftMs_ = millis();
            runFft();
        }
        fftBufIdx_ = 0u;  // reset to accumulate fresh samples
    }

    return module::MODULE_SERVICE_OK;
}

float getFrequency() {
    return frequency_;
}

/**
 * Run FFT on the current accumulation buffer (if full) and return the
 * frequency estimate.  Non-blocking — samples are accumulated by service()
 * from the FIFO; this function just triggers the FFT computation.
 *
 * If the buffer is not yet full, returns the last valid frequency estimate.
 *
 * @return Detected frequency in Hz, or NAN when signal is absent / SNR is
 *         below threshold.
 */
float calculateFrequency() {
    if (!sImuAvailable) return NAN;

    // If the accumulation buffer is full, run FFT now.
    if (fftBufIdx_ >= FFT_N) {
        runFft();
        fftBufIdx_  = 0u;
        lastFftMs_  = millis();
    }

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
