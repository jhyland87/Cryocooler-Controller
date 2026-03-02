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

#include "pin_config.h"
#include "config.h"
#include "cold_head.h"
#include "conversions.h"
#include "module.h"
#include "imu.h"
#include "amplifier.h"
#include "sensor_mock.h"
#include "hardware.h"
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
static module::InitStatus initStatus = module::MODULE_INIT_NOT_STARTED;

// Mock injection state — set by setLastReadings(), cleared by read().
// When active, getCoolingRateKPerMin() and isStalled() return these values
// directly instead of computing from the ring buffer.
static bool  mockInjected    = false;
static float mockCoolingRate = 0.0f;
static bool  mockStalled     = false;

// Running average over computed cooling-rate values to smooth out sensor noise.
// Window of 15 samples @ 200 ms/sample ≈ 3 s of additional smoothing on top
// of the ring-buffer window, giving a much steadier readout.
static RunningAverage coolingRateAvg(15);


//OneWire oneWire(ONE_WIRE_BUS);
//DallasTemperature sensors(&oneWire);
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
    if (!checkDependencies() && !sensor_mock::isActive()) {
        initStatus = module::MODULE_INIT_DEPENDENCY_ERROR;
        return initStatus;
    }

    // ACS37800 voltage/current readings are owned by the amplifier module.
    // cold_head::read() pulls from amplifier::getLastRmsVoltageV/CurrentA().

    Serial.println(F("[cold_head] Initializing MAX31865..."));
    module::InitStatus rtdStatus = initRTD();
    if (rtdStatus != module::MODULE_INIT_SUCCESS) {
        Serial.printf("[cold_head] MAX31865 initialization failed! Status: %s\n", module::initStatusName(rtdStatus));
        initStatus = rtdStatus;
        return initStatus;
    }
    Serial.println(F("[cold_head] MAX31865 initialization successful!"));
    initStatus = module::MODULE_INIT_SUCCESS;
    return initStatus;
}

module::InitStatus initACS() {
    // ACS37800 is owned by the amplifier module.
    // cold_head pulls voltage/current readings from amplifier::getLastRmsVoltageV()
    // and amplifier::getLastRmsCurrentA() instead of accessing the sensor directly.
    return module::MODULE_INIT_SUCCESS;
}

module::InitStatus initRTD() {
    if (!max31865.begin(RTD_WIRE_CONFIG) && !sensor_mock::isActive()) {
        Serial.println(F("[cold_head] Could not initialize MAX31865! Check wiring."));
        // State machine will see tempK == 0 and fault if appropriate.
        return module::MODULE_INIT_HARDWARE_ERROR;
    }

    const uint16_t rtd   = max31865.readRTD();
    const uint8_t  fault = max31865.readFault();
    Serial.printf("[cold_head] MAX31865 comms check - RTD raw: %u  Fault: 0x%02X\n", rtd, fault);

    if (rtd == 0 && fault == 0) {
        Serial.println(F("[cold_head] WARNING: MAX31865 may not be communicating (RTD=0, Fault=0)."));
        Serial.println(F("[cold_head] Check CS, CLK, SDI, SDO wiring and 3.3V supply."));
    } else {
        Serial.println(F("[cold_head] MAX31865 initialized successfully!"));
    }

    return module::MODULE_INIT_SUCCESS;
}

void read(uint32_t nowMs) {
    if (sensor_mock::isActive()) {
        const auto& mo = sensor_mock::get();
        setLastReadings(nowMs, mo.tempK, mo.coolingRate, mo.stalled, mo.rmsVoltageV, mo.rmsCurrentA);
        return;
    }
    mockInjected = false;   // real read supersedes any prior mock injection
    // Voltage/current are owned by the amplifier module; pull the latest reading.
    lastRmsVoltageV = amplifier::getLastRmsVoltageV();
    lastRmsCurrentA = amplifier::getLastRmsCurrentA();

    const uint16_t rtd          = max31865.readRTD();
    const float    resistance   = conversions::rtdRawToResistance(rtd, RTD_RREF);
    const float    tempC        = max31865.temperature(RTD_RNOMINAL, RTD_RREF);
    const float    tempK        = conversions::celsiusToKelvin(tempC);
    const float    tempF        = conversions::celsiusToFahrenheit(tempC);
    const float    ambientTempC = imu::getTemperature();

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

bool checkDependencies() {
    if (!imu::isInitialized() && !sensor_mock::isActive()) {
        Serial.println(F("[cold_head] Dependency check failed - Accelerometer not initialized!"));
        return false;
    }
    return true;
}

void checkFaults() {
    if (sensor_mock::isActive()) return;
    const uint8_t fault = max31865.readFault();
    if (fault == 0) return;

    Serial.printf("[cold_head] Fault detected! Code: 0x%02X\n", fault);

    if (fault & MAX31865_FAULT_HIGHTHRESH)  Serial.println(F("[cold_head]  - RTD High Threshold"));
    if (fault & MAX31865_FAULT_LOWTHRESH)   Serial.println(F("[cold_head]  - RTD Low Threshold"));
    if (fault & MAX31865_FAULT_REFINLOW)    Serial.println(F("[cold_head]  - REFIN- > 0.85 x Bias"));
    if (fault & MAX31865_FAULT_REFINHIGH)   Serial.println(F("[cold_head]  - REFIN- < 0.85 x Bias - FORCE- open"));
    if (fault & MAX31865_FAULT_RTDINLOW)    Serial.println(F("[cold_head]  - RTDIN- < 0.85 x Bias - FORCE- open"));
    if (fault & MAX31865_FAULT_OVUV)        Serial.println(F("[cold_head]  - Under/Over voltage"));

    max31865.clearFault();
}

float getLastTempK() {
    return lastTempK;
}

float getLastTempC() {
    return lastTempC;
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

float getTemperatureToPercent()
{
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

float getLastRmsVoltageV() {
    return lastRmsVoltageV;
}

float getLastRmsCurrentA() {
    return lastRmsCurrentA;
}

} // namespace cold_head
