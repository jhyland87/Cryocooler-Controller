/**
 * @file cold_head.cpp
 * @brief ADS1220 RTD cold_head sensor implementation
 *
 * Maintains a ring buffer of (timestamp, tempC) samples for cooling-rate
 * calculation and cold_head-stall detection.
 *
 * Hardware:
 *   - ADS1220 on the shared SPI bus (mode 1), chip select ADS1220_CS
 *   - PT1000 RTD in 4-wire configuration
 *   - R_ref = 3854 ohm 0.1% reference resistor
 *   - IDAC1 routed to AIN3, sense on AIN1(+)/AIN0(-)
 *   - External REFP0/REFN0 (ratiometric measurement)
 *   - DRDY is not wired to the MCU: conversions are timed instead
 */

#include <Arduino.h>
#include <ADS1220_WE.h>
#include <RunningAverage.h>
#include <optional>

#include "pin_config.h"
#include "config.h"
#include "cold_head.h"
#include "conversions.h"
#include "module.h"
#include "imu.h"
#include "amplifier.h"
#include "esp_log.h"
#include "sensor_mock.h"
#include "hardware.h"
#include "tracking.h"
#include "tick.h"
#include "logger.h"

static LogStream _Log = Log.createChildLogger("cold_head");
// ---------------------------------------------------------------------------
// Module-private types and state
// ---------------------------------------------------------------------------


struct TempSample {
    uint32_t timestampMs;
    float    tempC;
    float    ambientTempC;
    float    rmsVoltageV;
    float    rmsCurrentA;
};

// Shares the main SPI bus (already started by hardware::init); no DRDY pin.
static ADS1220_WE ads1220(&hardware::spi(), ADS1220_CS, -1, false, true);

// Single-shot conversion at 20 SPS takes 204850 / 4.096 MHz = 50 ms.
static constexpr uint32_t ADS1220_CONVERSION_MS = 60;

// Ring buffer - fixed size determined by TEMP_HISTORY_SIZE
static TempSample  sHistory[TEMP_HISTORY_SIZE];
static uint8_t     sHead         = 0;   // index of next write position
static uint8_t     sCount        = 0;   // number of valid samples stored
static float       sLastTempK    = 0.0f;
static float       sLastTempC    = 0.0f;
static float       sLastAmbientTempC = 0.0f;
static float        sLastRmsVoltageV = 0.0f;
static float        sLastRmsCurrentA = 0.0f;
// Mock injection state — set by setLastReadings(), cleared by read().
// When active, getCoolingRateCPerMin() and isStalled() return these values
// directly instead of computing from the ring buffer.
static bool  sMockInjected    = false;
static float sMockCoolingRate = 0.0f;
static bool  sMockStalled     = false;

// Module-local RTD mock — bypasses ADS1220 hardware without enabling the
// global sensor_mock layer.  Allows the rest of the system to run on real
// hardware while the temperature probe is absent or not yet wired up.
static bool  sLocalMockEnabled = false;
static float sLocalMockTempC   = 26.85f;

// Set to true when the most recent read() detected an ADS1220 communication
// failure or a temperature reading outside [MIN_PLAUSIBLE_COLDHEAD_TEMP_C,
// MAX_PLAUSIBLE_COLDHEAD_TEMP_C].
// Self-clears on the next clean read.  Exposed via hasSensorFault().
static bool sRtdFaultActive = false;
// Per-key fault rate-limiter.
// Each distinct fault type gets its own slot so that two simultaneously
// oscillating faults don't reset each other's timers and cause spam.
// Keys:
//   1      → ADS1220 communication fault (all-zero / all-one frame)
//   256    → plausibility fault, reading too low
//   257    → plausibility fault, reading too high
//   0      → unused slot
static constexpr uint32_t FAULT_LOG_INTERVAL_MS  = 10'000;
static constexpr uint16_t FAULT_KEY_NONE         = 0;
static constexpr uint16_t FAULT_KEY_PLAUS_LOW    = 256;
static constexpr uint16_t FAULT_KEY_PLAUS_HIGH   = 257;

struct FaultRateLimit {
    uint16_t key          = FAULT_KEY_NONE;
    uint32_t lastLogMs    = 0;
    uint32_t suppressedCt = 0;
};

// 4 slots: hw-fault (up to 2 distinct codes), plaus-low, plaus-high.
static constexpr uint8_t MAX_TRACKED_FAULTS = 4;
static FaultRateLimit    sFaultLimits[MAX_TRACKED_FAULTS];

// Returns the existing slot for key, or claims an empty one.
// Returns nullptr only if the table is full (shouldn't happen in practice).
static FaultRateLimit* findFaultLimit(uint16_t key) {
    FaultRateLimit* empty = nullptr;
    for (auto& fl : sFaultLimits) {
        if (fl.key == key)                              return &fl;
        if (fl.key == FAULT_KEY_NONE && empty == nullptr) empty = &fl;
    }
    if (empty != nullptr) { empty->key = key; }
    return empty;
}

static constexpr char TAG[] = "cold_head";

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

// Target temperature set by the state machine via setTargetTempC().
// NAN while the system is idle/off/fault — only populated when the FSM
// enters a cooling state.  The dashboard treats NAN as "no target".
static float targetTempC_ = NAN;

// Tracks how closely the measured cold-stage temperature follows targetTempC_.
// Only active while the FSM is in the Operating state; nullopt otherwise.
// Constructed by startTemperatureTracking() (onEnterOperating) and destroyed
// by stopTemperatureTracking() (onExitOperating).
static std::optional<TrackingMonitor<float>> tempTracker_;

// Running average over computed cooling-rate values to smooth out sensor noise.
// Window of 15 samples @ 200 ms/sample ≈ 3 s of additional smoothing on top
// of the ring-buffer window, giving a much steadier readout.
static RunningAverage coolingRateAvg(15);
// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static void pushSample(uint32_t nowMs, float tempC, float ambientTempC, float rmsVoltageV, float rmsCurrentA) {
    sHistory[sHead].timestampMs = nowMs;
    sHistory[sHead].tempC       = tempC;
    sHistory[sHead].ambientTempC = ambientTempC;
    sHistory[sHead].rmsVoltageV = rmsVoltageV;
    sHistory[sHead].rmsCurrentA = rmsCurrentA;
    sHead = static_cast<uint8_t>((sHead + 1) % TEMP_HISTORY_SIZE);
    if (sCount < TEMP_HISTORY_SIZE) {
        ++sCount;
    }
}

/**
 * Return a reference to the sample at logical index @p i
 * (0 = oldest, count-1 = newest).
 */
static const TempSample& sampleAt(uint8_t i) {
    // oldest slot in the ring is (head - count + i) mod SIZE
    auto idx = static_cast<uint8_t>(
        (sHead + TEMP_HISTORY_SIZE - sCount + i) % TEMP_HISTORY_SIZE);
    return sHistory[idx];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

// Configures the ADS1220 for PT1000 4-wire ratiometric measurement:
//   - MUX AIN1(+) / AIN0(-), gain 1 with the PGA bypassed (PT1000 gives
//     ~10x the PT100 signal, so gain 8 would overrange)
//   - external reference on REFP0/REFN0, IDAC1 (250 uA) routed to AIN3
//   - 20 SPS single-shot with simultaneous 50/60 Hz rejection
//   - non-blocking: conversions are started and read on a timer
static void configureAdc() {
    ads1220.setCompareChannels(ADS1220_MUX_1_0);
    ads1220.setGain(ADS1220_GAIN_1);
    ads1220.bypassPGA(true);
    ads1220.setDataRate(ADS1220_DR_LVL_0);
    ads1220.setConversionMode(ADS1220_SINGLE_SHOT);
    ads1220.setVRefSource(ADS1220_VREF_REFP0_REFN0);
    ads1220.setFIRFilter(ADS1220_50HZ_60HZ);
    ads1220.setIdacCurrent(ADS1220_IDAC_250_MU_A);
    ads1220.setIdac1Routing(ADS1220_IDAC_AIN3_REFN1);
    ads1220.setNonBlockingMode(true);
}

namespace cold_head {

module::InitStatus init() {
    // ACS37800 voltage/current readings are owned by the amplifier module.
    // cold_head::read() pulls from amplifier::getLastRmsVoltage/CurrentA().

    _Log.println(F("Initializing ADS1220..."));
    const module::InitStatus rtdStatus = initRTD();
    if (rtdStatus != module::MODULE_INIT_SUCCESS) {
        ESP_LOGE(TAG, "ADS1220 initialization failed! Status: %s", module::initStatusName(rtdStatus));
        _Log.printf("ADS1220 initialization failed! Status: %s", module::initStatusName(rtdStatus));
        return rtdStatus;
    }
    _Log.println(F("ADS1220 initialization successful!"));
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initACS() {
    // ACS37800 is owned by the amplifier module.
    // cold_head pulls voltage/current readings from amplifier::getLastRmsVoltage()
    // and amplifier::getLastRmsCurrent() instead of accessing the sensor directly.
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initRTD() {
    // Local mock: skip all hardware access entirely.
    if (sLocalMockEnabled) {
        _Log.printf("Local RTD mock active (%.2f C) — skipping ADS1220 hardware init",
                 sLocalMockTempC);
        return module::MODULE_INIT_SUCCESS;
    }

    if (!ads1220.init() && !sensor_mock::isActive()) {
        _Log.println(F("Could not initialize ADS1220! Check SPI wiring."));
        return module::MODULE_INIT_HARDWARE_ERROR;
    }
    configureAdc();

    ESP_LOGI(TAG, "ADS1220 configured for PT1000 4-wire measurement");
    return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    // If hardware init failed, don't touch the SPI bus — a missing ADS1220
    // would only return all-zero or all-one frames every tick.
    if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS
        && !sensor_mock::isActive() && !sLocalMockEnabled) {
        return module::MODULE_SERVICE_SKIPPED;
    }

    const uint32_t nowMs = tick::nowMs();
    // Global sensor_mock takes precedence over the local RTD mock.
    if (sensor_mock::isActive()) {
        const auto& mo = sensor_mock::get();
        setLastReadings(mo.tempC, mo.coolingRate, mo.stalled, mo.rmsVoltageV, mo.rmsCurrentA);
        // Check plausibility even for mock readings so tests can exercise the fault path.
        sRtdFaultActive = (sLastTempC < static_cast<float>(MIN_PLAUSIBLE_COLDHEAD_TEMP_C) ||
                          sLastTempC > static_cast<float>(MAX_PLAUSIBLE_COLDHEAD_TEMP_C));
        return module::MODULE_SERVICE_OK;
    }

    // Local RTD mock: return the configured temperature, everything else zeroed.
    // coolingRate and stalled stay at their defaults (0 / false) since we are
    // holding a fixed temperature — the state machine will not fault for stall
    // unless it is actively in a cooldown state and expects a drop.
    if (sLocalMockEnabled) {
        setLastReadings(sLocalMockTempC, 0.0f, false, 0.0f, 0.0f);
        sRtdFaultActive = false;
        return module::MODULE_SERVICE_OK;
    }

    {
    sMockInjected = false;   // real read supersedes any prior mock injection
    // Voltage/current are owned by the amplifier module; pull the latest reading.
    sLastRmsVoltageV = amplifier::getLastRmsVoltage();
    sLastRmsCurrentA = amplifier::getLastRmsCurrent();
    // Ambient temp is owned by the IMU module; pull every tick so the value
    // stays current even when the RTD read returns early (timeout / offline).
    sLastAmbientTempC = imu::getTemperature();

    // ── Non-blocking ADS1220 RTD measurement ────────────────────────────
    // Uses a two-phase state machine:
    //   Phase 0: Kick off a single-shot conversion via ads1220.start()
    //   Phase 1: After ADS1220_CONVERSION_MS (DRDY is not wired), read the
    //            24-bit result
    // Returns early each cycle that the conversion is still running, keeping
    // the main loop non-blocking.

    static uint32_t sRtdStartMs  = 0;
    static bool     sConvStarted = false;

    if (!sConvStarted) {
        // SPI has no ACK, so a dropped configuration (the chip may have been
        // power-cycled) shows up as the PGA bypass bit reading back clear.
        if (sRtdFaultActive || !ads1220.isPGABypassed()) {
            configureAdc();
        }
        ads1220.start();
        sConvStarted = true;
        sRtdStartMs  = nowMs;
        return module::MODULE_SERVICE_OK;  // conversion starting — nothing to read yet
    }

    // Return early while the conversion is still running.
    if ((nowMs - sRtdStartMs) < ADS1220_CONVERSION_MS) {
        return module::MODULE_SERVICE_OK;
    }

    // Measurement complete — read the 24-bit result (already sign-extended).
    sConvStarted = false;  // ready for next cycle

    const int32_t signed_raw = ads1220.getRawData();

    // All-zero or all-one frames mean no device is driving MISO.
    if (signed_raw == 0 || signed_raw == -1) {
        sRtdFaultActive = true;
        return module::MODULE_SERVICE_ERROR;
    }

    // Convert ADC counts to PT1000 resistance (ratiometric).
    // R_pt1000 = (ADC / 2^23) * R_ref / gain
    const float resistance = (static_cast<float>(signed_raw) / ADS1220_ADC_FULL_SCALE)
                             * PT1000_REF_R / PT1000_GAIN;
    const float tempC      = conversions::resistanceToTemperaturePT1000(resistance);

    // --- plausibility check ---
    bool anyFault = false;
    const bool plausLow  = tempC < static_cast<float>(MIN_PLAUSIBLE_COLDHEAD_TEMP_C);
    const bool plausHigh = tempC > static_cast<float>(MAX_PLAUSIBLE_COLDHEAD_TEMP_C);
    if (plausLow || plausHigh) {
        anyFault = true;
        const uint16_t  key  = plausLow ? FAULT_KEY_PLAUS_LOW : FAULT_KEY_PLAUS_HIGH;
        FaultRateLimit* fl   = findFaultLimit(key);
        const bool      emit = (fl == nullptr) ||
                               (nowMs - fl->lastLogMs >= FAULT_LOG_INTERVAL_MS);
        if (emit) {
            const uint32_t suppressed = fl ? fl->suppressedCt : 0;
            if (suppressed > 0) {
                _Log.printf("tempC %.2f outside plausible range [%.1f, %.1f] — sensor fault suspected"
                              " (%u suppressed)\n",
                         tempC,
                         static_cast<float>(MIN_PLAUSIBLE_COLDHEAD_TEMP_C),
                         static_cast<float>(MAX_PLAUSIBLE_COLDHEAD_TEMP_C),
                         suppressed);
            } else {
                _Log.printf("tempC %.2f outside plausible range [%.1f, %.1f] — sensor fault suspected\n",
                         tempC,
                         static_cast<float>(MIN_PLAUSIBLE_COLDHEAD_TEMP_C),
                         static_cast<float>(MAX_PLAUSIBLE_COLDHEAD_TEMP_C));
            }
            if (fl) { fl->lastLogMs = nowMs; fl->suppressedCt = 0; }
        } else {
            ++fl->suppressedCt;
        }
    } else {
        // Plausibility fault cleared — reset its slots so any recurrence emits immediately.
        for (auto& fl : sFaultLimits) {
            if (fl.key == FAULT_KEY_PLAUS_LOW || fl.key == FAULT_KEY_PLAUS_HIGH) {
                fl = {};
            }
        }
    }

    sRtdFaultActive = anyFault;

    sLastTempC = tempC;
    pushSample(nowMs, tempC, sLastAmbientTempC, sLastRmsVoltageV, sLastRmsCurrentA);

    // Feed the freshly computed ring-buffer rate into the running average so
    // that getCoolingRateCPerMin() returns a smoothed value.
    if (sCount >= 2) {
        const auto& oldest = sampleAt(0);
        const auto& newest = sampleAt(static_cast<uint8_t>(sCount - 1));
        const uint32_t dtMs = newest.timestampMs - oldest.timestampMs;
        if (dtMs > 0) {
            const float dTempC    = oldest.tempC - newest.tempC;
            const float dtMinutes = static_cast<float>(dtMs) / 60000.0f;
            coolingRateAvg.addValue(dTempC / dtMinutes);
        }
    }
    } // real hardware path

    // Update the tracking monitor if it is active (Operating state only).
    if (tempTracker_) {
        tempTracker_->update(targetTempC_, sLastTempC);
    }

    // Inline fault check — previously called separately from main.cpp.
    checkFaults();

    return module::MODULE_SERVICE_OK;
}

void setLastReadings(float tempC,
                     float coolingRateCPerMin, bool stalled, float rmsVoltageV, float rmsCurrentA) {
    sLastTempC         = tempC;
    sMockCoolingRate   = coolingRateCPerMin;
    sMockStalled       = stalled;
    sMockInjected      = true;
    sLastRmsVoltageV   = rmsVoltageV;
    sLastRmsCurrentA   = rmsCurrentA;
    // Push a timestamped sample so the ring buffer stays current;
    // this lets real stall / rate code pick up correctly if mock is disabled.
    pushSample(tick::nowMs(), tempC, sLastAmbientTempC, rmsVoltageV, rmsCurrentA);
}

// float readAmbientTemperature() {
//     sensors.requestTemperatures(); // Send the command to get temperatures
//     if (sensors.getDeviceCount() > 0) {
//         return sensors.getTempCByIndex(0);
//     }
//     return 0.0f;
// }

void checkFaults() {
    if (sensor_mock::isActive()) return;
    // ADS1220 has no dedicated fault register like the MAX31865.
    // Faults are detected during service() via empty SPI frames and plausibility
    // checks.  This function is retained for API compatibility.
    if (sRtdFaultActive) {
        _Log.println(F("ADS1220: sensor fault active (empty SPI frame or out-of-range reading)"));
    }
}

float getLastTempC() {
    return sLastTempC;
}

bool hasSensorFault() {
    return sRtdFaultActive;
}

// float getLastAmbientTempC() {
//     return lastAmbientTempC;
// }

float getLastTempCBelowAmbient() {
    return sLastAmbientTempC - sLastTempC;
}

float getCoolingRateCPerMin() {
    if (sMockInjected) return sMockCoolingRate;
    // Return the running average of ring-buffer cooling rates for a smooth
    // readout.  Falls back to 0 until the first value has been added.
    if (coolingRateAvg.getCount() == 0) return 0.0f;
    return coolingRateAvg.getAverage();
}

bool isStalled() {
    if (sMockInjected) return sMockStalled;
    return false;
    if (sCount < 2) return false;

    const auto& newest = sampleAt(static_cast<uint8_t>(sCount - 1));
    const uint32_t windowStart = (newest.timestampMs >= STALL_DETECT_WINDOW_MS)
                                 ? newest.timestampMs - STALL_DETECT_WINDOW_MS
                                 : 0;

    // Find the oldest sample within the detection window
    float refTempC = newest.tempC;
    for (uint8_t i = 0; i < sCount; ++i) {
        const auto& s = sampleAt(i);
        if (s.timestampMs >= windowStart) {
            refTempC = s.tempC;
            break;
        }
    }

    // Stalled if the drop within the window is below the minimum threshold
    const float drop = refTempC - newest.tempC;
    return (drop < STALL_MIN_DROP_C);
}

float getLastAmbientTempC(){
    return sLastAmbientTempC;
}

float getTemperatureToPercent(){
    const float tempC = getLastTempC();
    const float T_MAX = AMBIENT_START_C;
    const float T_MIN = SETPOINT_C;

    // Clamp temperature
    //if (tempC >= T_MAX) return 0.0;
    //if (tempC <= T_MIN) return 100.0;

    // Linear interpolation
    float percent = (T_MAX - tempC) / (T_MAX - T_MIN) * 100.0;

    return percent;
}

float getLastRmsVoltage() {
    return sLastRmsVoltageV;
}

float getLastRmsCurrent() {
    return sLastRmsCurrentA;
}

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

void setTargetTempC(float targetC) {
    // Reset the timer when the target changes significantly, so the monitor
    // does not inherit stale elapsed time from the previous setpoint.
    if (tempTracker_ && fabsf(targetC - targetTempC_) > COLD_HEAD_TRACK_HYSTERESIS_C) {
        tempTracker_->reset();
    }
    targetTempC_ = targetC;
}

float getTargetTempC() {
    return targetTempC_;
}

void startTemperatureTracking() {
    tempTracker_.emplace(TrackingMonitor<float>::Config{
        /* hysteresis     */ COLD_HEAD_TRACK_HYSTERESIS_C,
        /* fullScale      */ COLD_HEAD_TRACK_FULL_SCALE_C,
        /* warningDelayMs */ COLD_HEAD_TRACK_WARNING_MS,
        /* faultDelayMs   */ COLD_HEAD_TRACK_FAULT_MS,
        /* tag            */ TAG,
        /* label          */ "temperature",
    });
}

void stopTemperatureTracking() {
    tempTracker_.reset();
}

float getTemperatureScore() {
    return tempTracker_ ? tempTracker_->getScore() : 1.0f;
}

TrackingMonitor<float>::State getTemperatureTrackingState() {
    return tempTracker_ ? tempTracker_->getState() : TrackingMonitor<float>::State::IN_RANGE;
}

// ---------------------------------------------------------------------------
// Module-local RTD mock API
// ---------------------------------------------------------------------------

void enableMock(float tempC) {
    sLocalMockEnabled = true;
    sLocalMockTempC   = tempC;
    _Log.printf("Local RTD mock enabled at %.2f C", tempC);
#ifdef ARDUINO
    // If the module hasn't initialised successfully yet (e.g. ADS1220 absent),
    // run init() now — it will short-circuit through initRTD()'s mock branch and
    // set _initStatus = SUCCESS.  This means the caller never needs a separate
    // reinit command just to enable the cold-head mock.
    if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS) {
        Module::init();
    }
#endif
}

void disableMock() {
    sLocalMockEnabled = false;
    _Log.println(F("Local RTD mock disabled — will use real ADS1220 after next reinit"));
}

bool isMockEnabled() {
    return sLocalMockEnabled;
}

} // namespace cold_head
