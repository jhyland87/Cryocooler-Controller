/**
 * @file cold_head.cpp
 * @brief MAX31865 RTD cold_head sensor implementation
 *
 * Maintains a ring buffer of (timestamp, tempK) samples for cooling-rate
 * calculation and cold_head-stall detection.
 */

#include <Arduino.h>
#include <Adafruit_MAX31865.h>
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
#include "logger.h"

static LogStream _Log = Log.createChildLogger("cold_head");
// ---------------------------------------------------------------------------
// Module-private types and state
// ---------------------------------------------------------------------------


struct TempSample {
    uint32_t timestampMs;
    float    tempK;
    float    ambientTempC;
    float    rmsVoltageV;
    float    rmsCurrentA;
};

static Adafruit_MAX31865 max31865(MAX31865_CS);

// Ring buffer - fixed size determined by TEMP_HISTORY_SIZE
static TempSample  history[TEMP_HISTORY_SIZE];
static uint8_t     head         = 0;   // index of next write position
static uint8_t     count        = 0;   // number of valid samples stored
static float       lastTempK    = 0.0f;
static float       lastTempC    = 0.0f;
static float       lastAmbientTempC = 0.0f;
static float        lastRmsVoltageV = 0.0f;
static float        lastRmsCurrentA = 0.0f;
// Mock injection state — set by setLastReadings(), cleared by read().
// When active, getCoolingRateKPerMin() and isStalled() return these values
// directly instead of computing from the ring buffer.
static bool  mockInjected    = false;
static float mockCoolingRate = 0.0f;
static bool  mockStalled     = false;

// Module-local RTD mock — bypasses MAX31865 hardware without enabling the
// global sensor_mock layer.  Allows the rest of the system to run on real
// hardware while the temperature probe is absent or not yet wired up.
static bool  sLocalMockEnabled = false;
static float sLocalMockTempK   = 300.0f;

// Set to true when the most recent read() detected a MAX31865 hardware fault
// or a temperature reading outside [MIN_PLAUSIBLE_TEMP_K, MAX_PLAUSIBLE_TEMP_K].
// Self-clears on the next clean read.  Exposed via hasSensorFault().
static bool rtdFaultActive = false;

// Per-key fault rate-limiter.
// Each distinct fault type gets its own slot so that two simultaneously
// oscillating faults don't reset each other's timers and cause spam.
// Keys:
//   1–255  → MAX31865 hw fault register value (bitmask)
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

// Target temperature set by the state machine via setTargetTempK().
// Defaults to the system setpoint; updated whenever the state machine
// changes its cooling target.
static float targetTempK_ = SETPOINT_K;

// Tracks how closely the measured cold-stage temperature follows targetTempK_.
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

static void pushSample(uint32_t nowMs, float tempK, float ambientTempC, float rmsVoltageV, float rmsCurrentA) {
    history[head].timestampMs = nowMs;
    history[head].tempK       = tempK;
    history[head].ambientTempC = ambientTempC;
    history[head].rmsVoltageV = rmsVoltageV;
    history[head].rmsCurrentA = rmsCurrentA;
    head = static_cast<uint8_t>((head + 1) % TEMP_HISTORY_SIZE);
    if (count < TEMP_HISTORY_SIZE) {
        ++count;
    }
}

/**
 * Return a reference to the sample at logical index @p i
 * (0 = oldest, count-1 = newest).
 */
static const TempSample& sampleAt(uint8_t i) {
    // oldest slot in the ring is (head - count + i) mod SIZE
    auto idx = static_cast<uint8_t>(
        (head + TEMP_HISTORY_SIZE - count + i) % TEMP_HISTORY_SIZE);
    return history[idx];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace cold_head {

module::InitStatus init() {
    // ACS37800 voltage/current readings are owned by the amplifier module.
    // cold_head::read() pulls from amplifier::getLastRmsVoltage/CurrentA().

    _Log.println("Initializing MAX31865...");
    const module::InitStatus rtdStatus = initRTD();
    if (rtdStatus != module::MODULE_INIT_SUCCESS) {
        ESP_LOGE(TAG, "MAX31865 initialization failed! Status: %s", module::initStatusName(rtdStatus));
        _Log.printf("MAX31865 initialization failed! Status: %s", module::initStatusName(rtdStatus));
        return rtdStatus;
    }
    _Log.println("MAX31865 initialization successful!");
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
        _Log.printf("Local RTD mock active (%.2f K) — skipping MAX31865 hardware init",
                 sLocalMockTempK);
        return module::MODULE_INIT_SUCCESS;
    }

    if (!max31865.begin(RTD_WIRE_CONFIG) && !sensor_mock::isActive()) {
        _Log.println("Could not initialize MAX31865! Check wiring.");
        // State machine will see tempK == 0 and fault if appropriate.
        return module::MODULE_INIT_HARDWARE_ERROR;
    }

    const uint16_t rtd   = max31865.readRTD();
    const uint8_t  fault = max31865.readFault();
    ESP_LOGD(TAG, "MAX31865 comms check - RTD raw: %u  Fault: 0x%02X", rtd, fault);

    if (rtd == 0 && fault == 0) {
        _Log.println("WARNING: MAX31865 may not be communicating (RTD=0, Fault=0).");
        ESP_LOGW(TAG, "Check CS, CLK, SDI, SDO wiring and 3.3V supply.");
    } else {
        ESP_LOGI(TAG, "MAX31865 initialized successfully!");
    }

    return module::MODULE_INIT_SUCCESS;
}

void read(uint32_t nowMs) {
    // Global sensor_mock takes precedence over the local RTD mock.
    if (sensor_mock::isActive()) {
        const auto& mo = sensor_mock::get();
        setLastReadings(nowMs, mo.tempK, mo.coolingRate, mo.stalled, mo.rmsVoltageV, mo.rmsCurrentA);
        // Check plausibility even for mock readings so tests can exercise the fault path.
        rtdFaultActive = (lastTempK < static_cast<float>(MIN_PLAUSIBLE_TEMP_K) ||
                          lastTempK > static_cast<float>(MAX_PLAUSIBLE_TEMP_K));
        return;
    }

    // Local RTD mock: return the configured temperature, everything else zeroed.
    // coolingRate and stalled stay at their defaults (0 / false) since we are
    // holding a fixed temperature — the state machine will not fault for stall
    // unless it is actively in a cooldown state and expects a drop.
    if (sLocalMockEnabled) {
        setLastReadings(nowMs, sLocalMockTempK, 0.0f, false, 0.0f, 0.0f);
        rtdFaultActive = false;
        return;
    }

    {
    mockInjected = false;   // real read supersedes any prior mock injection
    // Voltage/current are owned by the amplifier module; pull the latest reading.
    lastRmsVoltageV = amplifier::getLastRmsVoltage();
    lastRmsCurrentA = amplifier::getLastRmsCurrent();

    const uint16_t rtd          = max31865.readRTD();
    const float    resistance   = conversions::rtdRawToResistance(rtd, RTD_RREF);
    const float    tempC        = max31865.temperature(RTD_RNOMINAL, RTD_RREF);
    const float    tempK        = conversions::celsiusToKelvin(tempC);
    const float    tempF        = conversions::celsiusToFahrenheit(tempC);
    const float    ambientTempC = imu::getTemperature();

    // Check MAX31865 fault register and temperature plausibility.
    // The two checks are independent so each fault type can clear its own
    // rate-limit slot as soon as it resolves, without waiting for the other
    // to also clear.  rtdFaultActive is true if either fault is present.
    bool anyFault = false;

    // --- hw fault register ---
    const uint8_t hwFault = max31865.readFault();
    if (hwFault != 0) {
        anyFault = true;
        max31865.clearFault();
        const uint16_t  key  = static_cast<uint16_t>(hwFault);
        FaultRateLimit* fl   = findFaultLimit(key);
        const bool      emit = (fl == nullptr) ||
                               (nowMs - fl->lastLogMs >= FAULT_LOG_INTERVAL_MS);
        if (emit) {
            const uint32_t suppressed = fl ? fl->suppressedCt : 0;
            if (suppressed > 0) {
                _Log.printf("MAX31865 fault register 0x%02X — temperature reading unreliable"
                              " (+" PRIu32 " suppressed)", hwFault, suppressed);
            } else {
                _Log.printf("MAX31865 fault register 0x%02X — temperature reading unreliable", hwFault);
            }
            if (fl) { fl->lastLogMs = nowMs; fl->suppressedCt = 0; }
        } else {
            ++fl->suppressedCt;
        }
    } else {
        // hw fault cleared — reset its slot(s) so any recurrence emits immediately.
        for (auto& fl : sFaultLimits) {
            if (fl.key != FAULT_KEY_NONE &&
                fl.key != FAULT_KEY_PLAUS_LOW &&
                fl.key != FAULT_KEY_PLAUS_HIGH) {
                fl = {};
            }
        }
    }

    // --- plausibility check ---
    const bool plausLow  = tempK < static_cast<float>(MIN_PLAUSIBLE_TEMP_K);
    const bool plausHigh = tempK > static_cast<float>(MAX_PLAUSIBLE_TEMP_K);
    if (plausLow || plausHigh) {
        anyFault = true;
        const uint16_t  key  = plausLow ? FAULT_KEY_PLAUS_LOW : FAULT_KEY_PLAUS_HIGH;
        FaultRateLimit* fl   = findFaultLimit(key);
        const bool      emit = (fl == nullptr) ||
                               (nowMs - fl->lastLogMs >= FAULT_LOG_INTERVAL_MS);
        if (emit) {
            const uint32_t suppressed = fl ? fl->suppressedCt : 0;
            if (suppressed > 0) {
                _Log.printf("tempK %.2f outside plausible range [%.0f, %.0f] — sensor fault suspected"
                              " (+" PRIu32 " suppressed)",
                         tempK,
                         static_cast<float>(MIN_PLAUSIBLE_TEMP_K),
                         static_cast<float>(MAX_PLAUSIBLE_TEMP_K),
                         suppressed);
            } else {
                _Log.printf("tempK %.2f outside plausible range [%.0f, %.0f] — sensor fault suspected",
                         tempK,
                         static_cast<float>(MIN_PLAUSIBLE_TEMP_K),
                         static_cast<float>(MAX_PLAUSIBLE_TEMP_K));
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

    rtdFaultActive = anyFault;

    lastTempC = tempC;
    lastTempK = tempK;
    lastAmbientTempC = ambientTempC;
    pushSample(nowMs, tempK, ambientTempC, lastRmsVoltageV, lastRmsCurrentA);

    // Feed the freshly computed ring-buffer rate into the running average so
    // that getCoolingRateKPerMin() returns a smoothed value.
    if (count >= 2) {
        const auto& oldest = sampleAt(0);
        const auto& newest = sampleAt(static_cast<uint8_t>(count - 1));
        const uint32_t dtMs = newest.timestampMs - oldest.timestampMs;
        if (dtMs > 0) {
            const float dTempK    = oldest.tempK - newest.tempK;
            const float dtMinutes = static_cast<float>(dtMs) / 60000.0f;
            coolingRateAvg.addValue(dTempK / dtMinutes);
        }
    }

    //Serial.printf("RTD raw: %u  Resistance: %.2f Ohm  Temp: %.2f C / %.2f F / %.2f K\n",
    //              rtd, resistance, tempC, tempF, tempK);
    } // real hardware path

    // Update the tracking monitor if it is active (Operating state only).
    if (tempTracker_) {
        tempTracker_->update(targetTempK_, lastTempK, nowMs);
    }
}

void setLastReadings(uint32_t nowMs, float tempK,
                     float coolingRateKPerMin, bool stalled, float rmsVoltageV, float rmsCurrentA) {
    lastTempK         = tempK;
    lastTempC         = tempK - 273.15f;
    mockCoolingRate   = coolingRateKPerMin;
    mockStalled       = stalled;
    mockInjected      = true;
    lastRmsVoltageV   = rmsVoltageV;
    lastRmsCurrentA   = rmsCurrentA;
    // Push a timestamped sample so the ring buffer stays current;
    // this lets real stall / rate code pick up correctly if mock is disabled.
    pushSample(nowMs, tempK, lastAmbientTempC, rmsVoltageV, rmsCurrentA);
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
    const uint8_t fault = max31865.readFault();
    if (fault == 0) return;

    _Log.printf("Fault detected! Code: 0x%02X", fault);

    if (fault & MAX31865_FAULT_HIGHTHRESH)  _Log.println("  - RTD High Threshold");
    if (fault & MAX31865_FAULT_LOWTHRESH)   _Log.println("  - RTD Low Threshold");
    if (fault & MAX31865_FAULT_REFINLOW)    _Log.println("  - REFIN- > 0.85 x Bias");
    if (fault & MAX31865_FAULT_REFINHIGH)   _Log.println("  - REFIN- < 0.85 x Bias - FORCE- open");
    if (fault & MAX31865_FAULT_RTDINLOW)    _Log.println("  - RTDIN- < 0.85 x Bias - FORCE- open");
    if (fault & MAX31865_FAULT_OVUV)        _Log.println("  - Under/Over voltage");

    max31865.clearFault();
}

float getLastTempK() {
    return lastTempK;
}

float getLastTempC() {
    return lastTempC;
}

bool hasSensorFault() {
    return rtdFaultActive;
}

// float getLastAmbientTempC() {
//     return lastAmbientTempC;
// }

float getLastTempCBelowAmbient() {
    return lastAmbientTempC - lastTempC;
}

float getCoolingRateKPerMin() {
    if (mockInjected) return mockCoolingRate;
    // Return the running average of ring-buffer cooling rates for a smooth
    // readout.  Falls back to 0 until the first value has been added.
    if (coolingRateAvg.getCount() == 0) return 0.0f;
    return coolingRateAvg.getAverage();
}

bool isStalled() {
    if (mockInjected) return mockStalled;
    return false;
    if (count < 2) return false;

    const auto& newest = sampleAt(static_cast<uint8_t>(count - 1));
    const uint32_t windowStart = (newest.timestampMs >= STALL_DETECT_WINDOW_MS)
                                 ? newest.timestampMs - STALL_DETECT_WINDOW_MS
                                 : 0;

    // Find the oldest sample within the detection window
    float refTempK = newest.tempK;
    for (uint8_t i = 0; i < count; ++i) {
        const auto& s = sampleAt(i);
        if (s.timestampMs >= windowStart) {
            refTempK = s.tempK;
            break;
        }
    }

    // Stalled if the drop within the window is below the minimum threshold
    const float drop = refTempK - newest.tempK;
    return (drop < STALL_MIN_DROP_K);
}

float getLastAmbientTempC(){
    return lastAmbientTempC;
}

float getTemperatureToPercent(){
    const float tempK = getLastTempK();
    const float T_MAX = AMBIENT_START_K;
    const float T_MIN = SETPOINT_K;

    // Clamp temperature
    //if (tempK >= T_MAX) return 0.0;
    //if (tempK <= T_MIN) return 100.0;

    // Linear interpolation
    float percent = (T_MAX - tempK) / (T_MAX - T_MIN) * 100.0;

    return percent;
}

float getLastRmsVoltage() {
    return lastRmsVoltageV;
}

float getLastRmsCurrent() {
    return lastRmsCurrentA;
}

// ---------------------------------------------------------------------------
// Setpoint tracking
// ---------------------------------------------------------------------------

void setTargetTempK(float targetK) {
    // Reset the timer when the target changes significantly, so the monitor
    // does not inherit stale elapsed time from the previous setpoint.
    if (tempTracker_ && fabsf(targetK - targetTempK_) > COLD_HEAD_TRACK_HYSTERESIS_K) {
        tempTracker_->reset();
    }
    targetTempK_ = targetK;
}

void startTemperatureTracking() {
    tempTracker_.emplace(TrackingMonitor<float>::Config{
        /* hysteresis     */ COLD_HEAD_TRACK_HYSTERESIS_K,
        /* fullScale      */ COLD_HEAD_TRACK_FULL_SCALE_K,
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

void enableMock(float tempK) {
    sLocalMockEnabled = true;
    sLocalMockTempK   = tempK;
    _Log.printf("Local RTD mock enabled at %.2f K (%.2f C)", tempK, tempK - 273.15f);
#ifdef ARDUINO
    // If the module hasn't initialised successfully yet (e.g. MAX31865 absent),
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
    _Log.println("Local RTD mock disabled — will use real MAX31865 after next reinit");
}

bool isMockEnabled() {
    return sLocalMockEnabled;
}

} // namespace cold_head
