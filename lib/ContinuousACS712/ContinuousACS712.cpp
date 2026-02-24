//
//  ContinuousACS712.cpp
//

#include "ContinuousACS712.h"


ContinuousACS712::ContinuousACS712(uint8_t analogPin, float volts, uint16_t maxADC, float mVperAmpere)
  : pin_(analogPin),
    maxADC_(maxADC),
    mVperAmpere_(mVperAmpere)
{
  if (maxADC_ == 0) maxADC_ = 1;
  if (mVperAmpere_ <= 0) mVperAmpere_ = 100.0f;

  mVperStep_ = 1000.0f * volts / maxADC_;         // V -> mV
  mAPerStep_ = 1000.0f * mVperStep_ / mVperAmpere_;
  midPoint_  = (int)(maxADC_ / 2);
}


void ContinuousACS712::setADC(uint16_t (*readFn)(uint8_t), float volts, uint16_t maxADC)
{
  readADC_ = readFn;

  maxADC_ = (maxADC == 0) ? 1 : maxADC;
  mVperStep_ = 1000.0f * volts / maxADC_;
  mAPerStep_ = 1000.0f * mVperStep_ / mVperAmpere_;
  midPoint_  = (int)(maxADC_ / 2);
}


void ContinuousACS712::suppressNoise(bool flag)
{
  suppressNoise_ = flag;
}


uint16_t ContinuousACS712::setMidPoint(uint16_t midPoint)
{
  if (midPoint <= maxADC_) midPoint_ = (int)midPoint;
  return (uint16_t)midPoint_;
}


uint16_t ContinuousACS712::getMidPoint() const
{
  return (uint16_t)midPoint_;
}


uint16_t ContinuousACS712::resetMidPoint()
{
  midPoint_ = (int)(maxADC_ / 2);
  return (uint16_t)midPoint_;
}


void ContinuousACS712::setmVperAmp(float mVperAmpere)
{
  if (mVperAmpere <= 0) return;
  mVperAmpere_ = mVperAmpere;
  mAPerStep_   = 1000.0f * mVperStep_ / mVperAmpere_;
}


float ContinuousACS712::getmVperAmp() const
{
  return mVperAmpere_;
}


float ContinuousACS712::getmAPerStep() const
{
  return mAPerStep_;
}


void ContinuousACS712::setOffsetmA(float offsetmA)
{
  offsetmA_ = offsetmA;
}


float ContinuousACS712::getOffsetmA() const
{
  return offsetmA_;
}


void ContinuousACS712::setClampZero(bool clampToZero)
{
  clampZero_ = clampToZero;
}


bool ContinuousACS712::getClampZero() const
{
  return clampZero_;
}


void ContinuousACS712::setUseMeanCenter(bool useMeanCenter)
{
  useMeanCenter_ = useMeanCenter;
}


bool ContinuousACS712::getUseMeanCenter() const
{
  return useMeanCenter_;
}


void ContinuousACS712::setNoiseFloormA(float noiseFloormA)
{
  noiseFloormA_ = noiseFloormA;
}


float ContinuousACS712::getNoiseFloormA() const
{
  return noiseFloormA_;
}


uint16_t ContinuousACS712::readRaw()
{
  return analogRead16_(pin_);
}


void ContinuousACS712::beginSpikeTracking(uint16_t windowSize)
{
  if (windowSize == 0) windowSize = 1;
  if (windowSize > kMaxSpikeWindow) windowSize = kMaxSpikeWindow;

  spike_.enabled    = true;
  spike_.windowSize = windowSize;
  spike_.count      = 0;
  spike_.index      = 0;
  spike_.sum        = 0.0f;
  spike_.sumSquares = 0.0f;
  spike_.lastMean   = 0.0f;
  spike_.lastStdDev = 0.0f;
  spike_.lastDelta  = 0.0f;
  spike_.lastZ      = 0.0f;
  spike_.active     = false;
  for (uint16_t i = 0; i < windowSize; ++i)
  {
    spike_.buffer[i] = 0.0f;
  }
}


void ContinuousACS712::stopSpikeTracking()
{
  spike_.enabled = false;
}


bool ContinuousACS712::spikeTrackingEnabled() const
{
  return spike_.enabled;
}


bool ContinuousACS712::spikeTrackingReady() const
{
  return spike_.enabled && (spike_.count >= spike_.windowSize);
}


float ContinuousACS712::spikeBaselineMean() const
{
  return spike_.lastMean;
}


float ContinuousACS712::spikeBaselineStdDev() const
{
  return spike_.lastStdDev;
}


float ContinuousACS712::spikeDelta() const
{
  return spike_.lastDelta;
}


float ContinuousACS712::spikeZScore() const
{
  return spike_.lastZ;
}


bool ContinuousACS712::spikeActive() const
{
  return spike_.enabled && spike_.active;
}


void ContinuousACS712::setSpikeThresholdZ(float z)
{
  spike_.thresholdZ = z;
}


void ContinuousACS712::setSpikeThresholdDelta(float delta_mA)
{
  spike_.thresholdDelta = delta_mA;
}


void ContinuousACS712::setSpikeDetectNegative(bool detectNegative)
{
  spike_.detectNegative = detectNegative;
}


void ContinuousACS712::spikeUpdate_(float currentmA)
{
  if (!spike_.enabled || spike_.windowSize == 0) return;

  // Baseline uses previous samples only (exclude currentmA).
  const uint16_t n = spike_.count;
  bool active = false;
  if (n >= 2)
  {
    const float invN = 1.0f / (float)n;
    const float mean = spike_.sum * invN;
    const float meanSq = spike_.sumSquares * invN;
    float var = meanSq - (mean * mean);
    if (var < 0.0f) var = 0.0f;
    const float stddev = sqrt(var);

    spike_.lastMean   = mean;
    spike_.lastStdDev = stddev;
    spike_.lastDelta  = currentmA - mean;
    spike_.lastZ      = (stddev > 0.0f) ? (spike_.lastDelta / stddev) : 0.0f;

    const float deltaCheck = spike_.detectNegative ? fabsf(spike_.lastDelta) : spike_.lastDelta;
    const float zCheck     = spike_.detectNegative ? fabsf(spike_.lastZ)     : spike_.lastZ;

    const bool zEnabled = (spike_.thresholdZ > 0.0f);
    const bool dEnabled = (spike_.thresholdDelta > 0.0f);

    if (zEnabled && (zCheck >= spike_.thresholdZ)) active = true;
    if (dEnabled && (deltaCheck >= spike_.thresholdDelta)) active = true;
  }
  else if (n == 1)
  {
    const float mean = spike_.sum;
    spike_.lastMean   = mean;
    spike_.lastStdDev = 0.0f;
    spike_.lastDelta  = currentmA - mean;
    spike_.lastZ      = 0.0f;

    const float deltaCheck = spike_.detectNegative ? fabsf(spike_.lastDelta) : spike_.lastDelta;
    const bool dEnabled = (spike_.thresholdDelta > 0.0f);
    if (dEnabled && (deltaCheck >= spike_.thresholdDelta)) active = true;
  }
  else
  {
    spike_.lastMean   = 0.0f;
    spike_.lastStdDev = 0.0f;
    spike_.lastDelta  = 0.0f;
    spike_.lastZ      = 0.0f;
  }

  // Becomes true while the condition holds; returns to false automatically.
  // Only arm once we have a full baseline window.
  if (spikeTrackingReady())
  {
    spike_.active = active;
  }
  else
  {
    spike_.active = false;
  }

  // Push current sample into ring buffer.
  if (spike_.count < spike_.windowSize)
  {
    spike_.buffer[spike_.index] = currentmA;
    spike_.sum += currentmA;
    spike_.sumSquares += currentmA * currentmA;
    spike_.count++;
    spike_.index++;
    if (spike_.index >= spike_.windowSize) spike_.index = 0;
    return;
  }

  const float old = spike_.buffer[spike_.index];
  spike_.buffer[spike_.index] = currentmA;
  spike_.sum += currentmA - old;
  spike_.sumSquares += (currentmA * currentmA) - (old * old);

  spike_.index++;
  if (spike_.index >= spike_.windowSize) spike_.index = 0;
}


void ContinuousACS712::beginContinuousRMS(float timeConstantMs, uint32_t minSampleIntervalUs)
{
  if (timeConstantMs <= 0) timeConstantMs = 1.0f;
  if (minSampleIntervalUs == 0) minSampleIntervalUs = 1;

  cont_.enabled       = true;
  cont_.tauUs         = timeConstantMs * 1000.0f;
  cont_.minIntervalUs = minSampleIntervalUs;
  cont_.lastSampleUs  = micros();
  cont_.initialized   = false;
  cont_.mean          = 0.0f;
  cont_.meanSquare    = 0.0f;
  cont_.resultmA      = 0.0f;
  cont_.resultmAUncorrected = 0.0f;
  cont_.minRaw        = 0xFFFF;
  cont_.maxRaw        = 0;
}


void ContinuousACS712::stopContinuousRMS()
{
  cont_.enabled = false;
}


bool ContinuousACS712::continuousEnabled() const
{
  return cont_.enabled;
}


bool ContinuousACS712::updateContinuousRMS()
{
  if (!cont_.enabled) return false;

  const uint32_t now = micros();
  const uint32_t dtUs = (uint32_t)(now - cont_.lastSampleUs);
  if (dtUs < cont_.minIntervalUs) return false;

  cont_.lastSampleUs = now;

  const uint16_t readingA = analogRead16_(pin_);
  uint16_t reading = readingA;
  if (suppressNoise_)
  {
    const uint16_t readingB = analogRead16_(pin_);
    reading = (uint16_t)((readingA + readingB) / 2);
  }

  cont_.lastRaw = reading;
  if (reading < cont_.minRaw) cont_.minRaw = reading;
  if (reading > cont_.maxRaw) cont_.maxRaw = reading;

  const float x = (float)reading;
  const float x2 = x * x;

  if (!cont_.initialized)
  {
    cont_.mean        = x;
    cont_.meanSquare  = x2;
    cont_.initialized = true;
  }
  else
  {
    const float dt = (float)dtUs;
    const float alpha = dt / (cont_.tauUs + dt);  // stable for variable dt
    cont_.mean       += alpha * (x - cont_.mean);
    cont_.meanSquare += alpha * (x2 - cont_.meanSquare);
  }

  const float center = useMeanCenter_ ? cont_.mean : (float)midPoint_;
  float rms2 = cont_.meanSquare - (2.0f * center * cont_.mean) + (center * center);
  if (rms2 < 0.0f) rms2 = 0.0f;

  const float rmsSteps = sqrt(rms2);
  cont_.lastRmsSteps = rmsSteps;
  float mA = rmsSteps * mAPerStep_;

  cont_.resultmAUncorrected = mA;
  mA -= offsetmA_;
  if (clampZero_ && (mA < 0.0f)) mA = 0.0f;
  if (noiseFloormA_ > 0.0f && (mA < noiseFloormA_)) mA = 0.0f;
  cont_.resultmA = mA;
  spikeUpdate_(mA);
  return true;
}


float ContinuousACS712::continuousmA() const
{
  return cont_.resultmA;
}


float ContinuousACS712::continuousmAUncorrected() const
{
  return cont_.resultmAUncorrected;
}


uint16_t ContinuousACS712::continuousMinRaw() const
{
  return cont_.minRaw;
}


uint16_t ContinuousACS712::continuousMaxRaw() const
{
  return cont_.maxRaw;
}


uint16_t ContinuousACS712::continuousLastRaw() const
{
  return cont_.lastRaw;
}


float ContinuousACS712::continuousMeanRaw() const
{
  return cont_.mean;
}


float ContinuousACS712::continuousRmsSteps() const
{
  return cont_.lastRmsSteps;
}


void ContinuousACS712::beginMidPointCalibration(uint16_t samples)
{
  if (samples == 0) samples = 1;

  // Cancel any ongoing AC measurement; midpoint calibration assumes a stable zero-current signal.
  acSampling_.active    = false;
  acSampling_.available = false;

  midCal_.active        = true;
  midCal_.available     = false;
  midCal_.targetSamples = samples;
  midCal_.collected     = 0;
  midCal_.total         = 0;
  midCal_.result        = (uint16_t)midPoint_;
}


bool ContinuousACS712::updateMidPointCalibration()
{
  if (!midCal_.active) return midCal_.available;

  const uint16_t readingA = analogRead16_(pin_);
  uint16_t reading = readingA;
  if (suppressNoise_)
  {
    const uint16_t readingB = analogRead16_(pin_);
    reading = (uint16_t)((readingA + readingB) / 2);
  }

  midCal_.total += reading;
  midCal_.collected++;

  if (midCal_.collected >= midCal_.targetSamples)
  {
    const uint32_t rounded = (uint32_t)((midCal_.total + (midCal_.targetSamples / 2)) / midCal_.targetSamples);
    const uint16_t newMid = (rounded > maxADC_) ? maxADC_ : (uint16_t)rounded;

    midPoint_ = (int)newMid;
    midCal_.result    = newMid;
    midCal_.active    = false;
    midCal_.available = true;
    return true;
  }

  return false;
}


bool ContinuousACS712::midPointCalibrationBusy() const
{
  return midCal_.active;
}


bool ContinuousACS712::midPointCalibrationAvailable() const
{
  return midCal_.available;
}


uint16_t ContinuousACS712::midPointCalibrationResult() const
{
  return midCal_.result;
}


void ContinuousACS712::beginACSampling(float frequencyHz, uint16_t cycles)
{
  if (frequencyHz <= 0) frequencyHz = 60.0f;
  uint32_t periodUs = (uint32_t)round(1000000.0f / frequencyHz);
  if (periodUs == 0) periodUs = 1;

  if (cycles == 0) cycles = 1;

  acSampling_.active          = true;
  acSampling_.available       = false;
  acSampling_.targetCycles    = cycles;
  acSampling_.completedCycles = 0;
  acSampling_.periodUs        = periodUs;
  acSampling_.cycleStartUs    = micros();
  acSampling_.samples         = 0;
  acSampling_.sum             = 0;
  acSampling_.sumSquares      = 0;
  acSampling_.sumRms          = 0;
}


bool ContinuousACS712::updateACSampling()
{
  if (!acSampling_.active) return acSampling_.available;

  const uint32_t now = micros();
  const uint32_t elapsed = (uint32_t)(now - acSampling_.cycleStartUs);

  if (elapsed < acSampling_.periodUs)
  {
    const uint16_t readingA = analogRead16_(pin_);
    uint16_t reading = readingA;
    if (suppressNoise_)
    {
      const uint16_t readingB = analogRead16_(pin_);
      reading = (uint16_t)((readingA + readingB) / 2);
    }

    acSampling_.samples++;
    const float x = (float)reading;
    acSampling_.sum        += x;
    acSampling_.sumSquares += x * x;
    return false;
  }

  // If loop() is slow, we might get here with 0 samples. Take 1 sample so RMS is defined.
  if (acSampling_.samples == 0)
  {
    const uint16_t readingA = analogRead16_(pin_);
    uint16_t reading = readingA;
    if (suppressNoise_)
    {
      const uint16_t readingB = analogRead16_(pin_);
      reading = (uint16_t)((readingA + readingB) / 2);
    }

    acSampling_.samples = 1;
    const float x = (float)reading;
    acSampling_.sum        = x;
    acSampling_.sumSquares = x * x;
  }

  const float invN = 1.0f / (float)acSampling_.samples;
  const float mean = acSampling_.sum * invN;
  const float meanSq = acSampling_.sumSquares * invN;
  const float center = useMeanCenter_ ? mean : (float)midPoint_;
  float rms2 = meanSq - (2.0f * center * mean) + (center * center);
  if (rms2 < 0.0f) rms2 = 0.0f;

  acSampling_.sumRms += sqrt(rms2);
  acSampling_.completedCycles++;

  if (acSampling_.completedCycles >= acSampling_.targetCycles)
  {
    float mA = acSampling_.sumRms * mAPerStep_;
    if (acSampling_.targetCycles > 1) mA /= acSampling_.targetCycles;

    acSampling_.resultmAUncorrected = mA;
    mA -= offsetmA_;
    if (clampZero_ && (mA < 0.0f)) mA = 0.0f;
    if (noiseFloormA_ > 0.0f && (mA < noiseFloormA_)) mA = 0.0f;

    acSampling_.resultmA  = mA;
    spikeUpdate_(mA);
    acSampling_.active    = false;
    acSampling_.available = true;
    return true;
  }

  acSampling_.cycleStartUs = now;
  acSampling_.samples      = 0;
  acSampling_.sum          = 0;
  acSampling_.sumSquares   = 0;
  return false;
}


bool ContinuousACS712::busy() const
{
  return acSampling_.active;
}


bool ContinuousACS712::available() const
{
  return acSampling_.available;
}


float ContinuousACS712::resultmA() const
{
  return acSampling_.resultmA;
}


float ContinuousACS712::resultmAUncorrected() const
{
  return acSampling_.resultmAUncorrected;
}


void ContinuousACS712::cancel()
{
  acSampling_.active    = false;
  acSampling_.available = false;
}


uint16_t ContinuousACS712::analogRead16_(uint8_t pin)
{
  if (readADC_ != nullptr) return readADC_(pin);
  return (uint16_t)analogRead(pin);
}

