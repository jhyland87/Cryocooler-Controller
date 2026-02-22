#pragma once
//
//  ACS712_nonblocking.h
//
//  Non-blocking ACS712 sampling helper.
//  Designed to be driven from Arduino's loop() without busy-waiting.
//

#include <Arduino.h>


class ACS712_nonblocking
{
public:
  //  TYPE   mV per Ampere
  //  5A        185.0
  //  20A       100.0
  //  30A        66.0
  ACS712_nonblocking(uint8_t analogPin, float volts = 5.0f, uint16_t maxADC = 1023, float mVperAmpere = 100.0f);

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

  uint8_t  pin_;
  uint16_t maxADC_;
  float    mVperStep_;
  float    mVperAmpere_;
  float    mAPerStep_;
  int      midPoint_;
  bool     suppressNoise_ = false;
  float    offsetmA_ = 0.0f;
  bool     clampZero_ = true;

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
    float    sumSquared = 0;
    float    sumRms = 0;
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
};

