/**
 * @file temperature.cpp
 * @brief MAX31865 RTD temperature sensor implementation
 *
 * Maintains a ring buffer of (timestamp, tempK) samples for cooling-rate
 * calculation and temperature-stall detection.
 */

#include <Arduino.h>
#include <Adafruit_MAX31865.h>

#include "pin_config.h"
#include "config.h"
#include "temperature.h"
#include "conversions.h"

// ---------------------------------------------------------------------------
// Module-private types and state
// ---------------------------------------------------------------------------

struct TempSample {
    uint32_t timestampMs;
    float    tempK;
};

static Adafruit_MAX31865 max31865(MAX31865_CS);

// Ring buffer - fixed size determined by TEMP_HISTORY_SIZE
static TempSample  sHistory[TEMP_HISTORY_SIZE];
static uint8_t     sHead         = 0;   // index of next write position
static uint8_t     sCount        = 0;   // number of valid samples stored
static float       sLastTempK    = 0.0f;
static float       sLastTempC    = 0.0f;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static void pushSample(uint32_t nowMs, float tempK) {
    sHistory[sHead].timestampMs = nowMs;
    sHistory[sHead].tempK       = tempK;
    sHead = static_cast<uint8_t>((sHead + 1) % TEMP_HISTORY_SIZE);
    if (sCount < TEMP_HISTORY_SIZE) {
        ++sCount;
    }
}

/**
 * Return a reference to the sample at logical index @p i
 * (0 = oldest, sCount-1 = newest).
 */
static const TempSample& sampleAt(uint8_t i) {
    // oldest slot in the ring is (sHead - sCount + i) mod SIZE
    auto idx = static_cast<uint8_t>(
        (sHead + TEMP_HISTORY_SIZE - sCount + i) % TEMP_HISTORY_SIZE);
    return sHistory[idx];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

namespace temperature {

void init() {
    if (!max31865.begin(RTD_WIRE_CONFIG)) {
        Serial.println("Could not initialize MAX31865! Check wiring.");
        // Non-blocking: continue anyway; the state machine will see tempK == 0
        // and should fault if appropriate.
        return;
    }

    const uint16_t rtd   = max31865.readRTD();
    const uint8_t  fault = max31865.readFault();
    Serial.printf("MAX31865 comms check - RTD raw: %u  Fault: 0x%02X\n", rtd, fault);

    if (rtd == 0 && fault == 0) {
        Serial.println("WARNING: MAX31865 may not be communicating (RTD=0, Fault=0).");
        Serial.println("Check CS, CLK, SDI, SDO wiring and 3.3V supply.");
    } else {
        Serial.println("MAX31865 initialized successfully!");
    }
}

void read(uint32_t nowMs) {
    const uint16_t rtd        = max31865.readRTD();
    const float    resistance = conversions::rtdRawToResistance(rtd, RTD_RREF);
    const float    tempC      = max31865.temperature(RTD_RNOMINAL, RTD_RREF);
    const float    tempK      = conversions::celsiusToKelvin(tempC);
    const float    tempF      = conversions::celsiusToFahrenheit(tempC);

    sLastTempC = tempC;
    sLastTempK = tempK;
    pushSample(nowMs, tempK);

    //Serial.printf("RTD raw: %u  Resistance: %.2f Ohm  Temp: %.2f C / %.2f F / %.2f K\n",
    //              rtd, resistance, tempC, tempF, tempK);
}

void checkFaults() {
    const uint8_t fault = max31865.readFault();
    if (fault == 0) return;

    Serial.printf("Fault detected! Code: 0x%02X\n", fault);

    if (fault & MAX31865_FAULT_HIGHTHRESH)  Serial.println("  - RTD High Threshold");
    if (fault & MAX31865_FAULT_LOWTHRESH)   Serial.println("  - RTD Low Threshold");
    if (fault & MAX31865_FAULT_REFINLOW)    Serial.println("  - REFIN- > 0.85 x Bias");
    if (fault & MAX31865_FAULT_REFINHIGH)   Serial.println("  - REFIN- < 0.85 x Bias - FORCE- open");
    if (fault & MAX31865_FAULT_RTDINLOW)    Serial.println("  - RTDIN- < 0.85 x Bias - FORCE- open");
    if (fault & MAX31865_FAULT_OVUV)        Serial.println("  - Under/Over voltage");

    max31865.clearFault();
}

float getLastTempK() {
    return sLastTempK;
}

float getLastTempC() {
    return sLastTempC;
}

float getCoolingRateKPerMin() {
    if (sCount < 2) return 0.0f;

    const auto& oldest = sampleAt(0);
    const auto& newest = sampleAt(static_cast<uint8_t>(sCount - 1));

    const uint32_t dtMs = newest.timestampMs - oldest.timestampMs;
    if (dtMs == 0) return 0.0f;

    // Positive result = temperature is decreasing (cooling)
    const float dTempK    = oldest.tempK - newest.tempK;
    const float dtMinutes = static_cast<float>(dtMs) / 60000.0f;
    return dTempK / dtMinutes;
}

bool isStalled() {
  return false;
    if (sCount < 2) return false;

    const auto& newest = sampleAt(static_cast<uint8_t>(sCount - 1));
    const uint32_t windowStart = (newest.timestampMs >= STALL_DETECT_WINDOW_MS)
                                 ? newest.timestampMs - STALL_DETECT_WINDOW_MS
                                 : 0;

    // Find the oldest sample within the detection window
    float refTempK = newest.tempK;
    for (uint8_t i = 0; i < sCount; ++i) {
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

} // namespace temperature
