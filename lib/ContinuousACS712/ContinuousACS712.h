#pragma once
//
//  ContinuousACS712.h
//
//  Non-blocking ACS712 sampling helper.
//  Designed to be driven from Arduino's loop() without busy-waiting.
//

#include <Arduino.h>


class ContinuousACS712
{
public:
  //  TYPE   mV per Ampere
  //  5A        185.0
  //  20A       100.0
  //  30A        66.0
  ContinuousACS712(uint8_t analogPin, float volts = 5.0f, uint16_t maxADC = 1023, float mVperAmpere = 100.0f);

  // If you use an external ADC, provide a read function here.
  void setADC(uint16_t (*readFn)(uint8_t), float volts, uint16_t maxADC);

  void suppressNoise(bool flag);

  // Midpoint functions (raw ADC reference).
  uint16_t setMidPoint(uint16_t midPoint);
  uint16_t getMidPoint() const;
  uint16_t resetMidPoint();

  // Calibration.
  void  setmVperAmp(float mVperAmpere);
  float getmVperAmp() const;
  float getmAPerStep() const;

  // Output correction.
  // For sensors / analog front-ends with a residual baseline at "zero current".
  // Offset is subtracted from the computed RMS current.
  void  setOffsetmA(float offsetmA);
  float getOffsetmA() const;
  void  setClampZero(bool clampToZero);
  bool  getClampZero() const;

  // Centering mode for RMS calculation.
  // - Fixed midpoint: uses midPoint_ as the center (ACS712-style).
  // - Mean centered: uses the measured mean as the center (robust for CT modules / drifting offsets).
  void  setUseMeanCenter(bool useMeanCenter);
  bool  getUseMeanCenter() const;

  // Optional deadband after correction (offset/clamp).
  // If corrected RMS is below this threshold, output is forced to 0.
  void  setNoiseFloormA(float noiseFloormA);
  float getNoiseFloormA() const;

  // Quick non-blocking helpers for debugging/calibration.
  uint16_t readRaw();

  // Non-blocking midpoint calibration (assumes zero current).
  // Call beginMidPointCalibration(), then call updateMidPointCalibration() from loop().
  // When it returns true, midpoint is updated and midPointCalibrationResult() returns it.
  void     beginMidPointCalibration(uint16_t samples = 2000);
  bool     updateMidPointCalibration();  // returns true once when finished
  bool     midPointCalibrationBusy() const;
  bool     midPointCalibrationAvailable() const;
  uint16_t midPointCalibrationResult() const;

  // Continuous RMS mode (plotter-friendly).
  // Updates an RMS estimate continuously using an exponential moving average (EMA) of sample^2.
  // Call beginContinuousRMS(), then call updateContinuousRMS() from loop() as often as possible.
  void     beginContinuousRMS(float timeConstantMs = 250.0f, uint32_t minSampleIntervalUs = 200);
  void     stopContinuousRMS();
  bool     continuousEnabled() const;
  bool     updateContinuousRMS();        // returns true when a new sample was processed
  float    continuousmA() const;         // corrected (offset/clamped)
  float    continuousmAUncorrected() const;
  uint16_t continuousMinRaw() const;     // min raw since beginContinuousRMS()
  uint16_t continuousMaxRaw() const;     // max raw since beginContinuousRMS()
  uint16_t continuousLastRaw() const;    // last raw sample used by updateContinuousRMS()
  float    continuousMeanRaw() const;    // EMA mean of raw ADC steps
  float    continuousRmsSteps() const;   // RMS in ADC steps around selected center

  // Spike tracking over previous N values.
  // Maintains a rolling baseline (mean/stddev) of the previous windowSize values and
  // reports how far the current value deviates from that baseline.
  //
  // Notes:
  // - Baseline excludes the current value (it uses "previous N").
  // - The tracked stream is the corrected mA output (after offset/clamp/noise floor).
  void     beginSpikeTracking(uint16_t windowSize = 50);
  void     stopSpikeTracking();
  bool     spikeTrackingEnabled() const;
  bool     spikeTrackingReady() const;     // true once we've collected at least windowSize samples
  float    spikeBaselineMean() const;      // mean of previous window (mA)
  float    spikeBaselineStdDev() const;    // stddev of previous window (mA)
  float    spikeDelta() const;             // current - baselineMean (mA)
  float    spikeZScore() const;            // delta / stddev (unitless); 0 if stddev is 0
  bool     spikeActive() const;            // true while spike condition is met
  void     setSpikeThresholdZ(float z);    // default 3.0; if <= 0, disables z-threshold
  void     setSpikeThresholdDelta(float delta_mA);  // default 0; if <= 0, disables delta-threshold
  void     setSpikeDetectNegative(bool detectNegative);  // default false (positive spikes only)

  // Non-blocking equivalent of ACS712::mA_AC_sampling().
  // Call beginACSampling(), then call updateACSampling() repeatedly from loop().
  // When updateACSampling() returns true (or available() is true), resultmA() holds the computed mA.
  void  beginACSampling(float frequencyHz = 60.0f, uint16_t cycles = 1);
  bool  updateACSampling();  // returns true once when finished
  bool  busy() const;
  bool  available() const;
  float resultmA() const;
  float resultmAUncorrected() const;
  void  cancel();

private:
  uint16_t analogRead16_(uint8_t pin);
  void     spikeUpdate_(float currentmA);

  uint8_t  pin_;
  uint16_t maxADC_;
  float    mVperStep_;
  float    mVperAmpere_;
  float    mAPerStep_;
  int      midPoint_;
  bool     suppressNoise_ = false;
  float    offsetmA_ = 0.0f;
  bool     clampZero_ = true;
  bool     useMeanCenter_ = true;
  float    noiseFloormA_ = 0.0f;

  uint16_t (*readADC_)(uint8_t) = nullptr;

  struct
  {
    bool     active = false;
    bool     available = false;
    uint16_t targetCycles = 1;
    uint16_t completedCycles = 0;
    uint32_t periodUs = 0;
    uint32_t cycleStartUs = 0;
    uint32_t samples = 0;
    float    sum = 0;          // sum of raw readings (ADC steps)
    float    sumSquares = 0;   // sum of raw^2 (ADC steps^2)
    float    sumRms = 0;       // sum of per-cycle RMS (ADC steps)
    float    resultmA = 0;
    float    resultmAUncorrected = 0;
  } acSampling_;

  struct
  {
    bool     active = false;
    bool     available = false;
    uint16_t targetSamples = 0;
    uint16_t collected = 0;
    uint64_t total = 0;
    uint16_t result = 0;
  } midCal_;

  struct
  {
    bool     enabled = false;
    float    tauUs = 250000.0f;
    uint32_t minIntervalUs = 200;
    uint32_t lastSampleUs = 0;
    bool     initialized = false;
    float    mean = 0.0f;        // EMA of raw (ADC steps)
    float    meanSquare = 0.0f;  // EMA of raw^2 (ADC steps^2)
    float    resultmA = 0.0f;
    float    resultmAUncorrected = 0.0f;
    uint16_t minRaw = 0xFFFF;
    uint16_t maxRaw = 0;
    uint16_t lastRaw = 0;
    float    lastRmsSteps = 0.0f;
  } cont_;

  static constexpr uint16_t kMaxSpikeWindow = 256;
  struct
  {
    bool     enabled = false;
    uint16_t windowSize = 0;
    uint16_t count = 0;
    uint16_t index = 0;
    float    sum = 0.0f;
    float    sumSquares = 0.0f;
    float    lastMean = 0.0f;
    float    lastStdDev = 0.0f;
    float    lastDelta = 0.0f;
    float    lastZ = 0.0f;
    bool     active = false;
    float    thresholdZ = 3.0f;
    float    thresholdDelta = 0.0f;
    bool     detectNegative = false;
    float    buffer[kMaxSpikeWindow] = {0};
  } spike_;
};

