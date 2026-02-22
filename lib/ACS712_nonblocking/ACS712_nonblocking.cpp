//
//  ACS712_nonblocking.cpp
//

#include "ACS712_nonblocking.h"


ACS712_nonblocking::ACS712_nonblocking(uint8_t analogPin, float volts, uint16_t maxADC, float mVperAmpere)
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


void ACS712_nonblocking::setADC(uint16_t (*readFn)(uint8_t), float volts, uint16_t maxADC)
{
  readADC_ = readFn;

  maxADC_ = (maxADC == 0) ? 1 : maxADC;
  mVperStep_ = 1000.0f * volts / maxADC_;
  mAPerStep_ = 1000.0f * mVperStep_ / mVperAmpere_;
  midPoint_  = (int)(maxADC_ / 2);
}


void ACS712_nonblocking::suppressNoise(bool flag)
{
  suppressNoise_ = flag;
}


uint16_t ACS712_nonblocking::setMidPoint(uint16_t midPoint)
{
  if (midPoint <= maxADC_) midPoint_ = (int)midPoint;
  return (uint16_t)midPoint_;
}


uint16_t ACS712_nonblocking::getMidPoint() const
{
  return (uint16_t)midPoint_;
}


uint16_t ACS712_nonblocking::resetMidPoint()
{
  midPoint_ = (int)(maxADC_ / 2);
  return (uint16_t)midPoint_;
}


void ACS712_nonblocking::setmVperAmp(float mVperAmpere)
{
  if (mVperAmpere <= 0) return;
  mVperAmpere_ = mVperAmpere;
  mAPerStep_   = 1000.0f * mVperStep_ / mVperAmpere_;
}


float ACS712_nonblocking::getmVperAmp() const
{
  return mVperAmpere_;
}


float ACS712_nonblocking::getmAPerStep() const
{
  return mAPerStep_;
}


void ACS712_nonblocking::setOffsetmA(float offsetmA)
{
  offsetmA_ = offsetmA;
}


float ACS712_nonblocking::getOffsetmA() const
{
  return offsetmA_;
}


void ACS712_nonblocking::setClampZero(bool clampToZero)
{
  clampZero_ = clampToZero;
}


bool ACS712_nonblocking::getClampZero() const
{
  return clampZero_;
}


uint16_t ACS712_nonblocking::readRaw()
{
  return analogRead16_(pin_);
}


void ACS712_nonblocking::beginMidPointCalibration(uint16_t samples)
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


bool ACS712_nonblocking::updateMidPointCalibration()
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


bool ACS712_nonblocking::midPointCalibrationBusy() const
{
  return midCal_.active;
}


bool ACS712_nonblocking::midPointCalibrationAvailable() const
{
  return midCal_.available;
}


uint16_t ACS712_nonblocking::midPointCalibrationResult() const
{
  return midCal_.result;
}


void ACS712_nonblocking::beginACSampling(float frequencyHz, uint16_t cycles)
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
  acSampling_.sumSquared      = 0;
  acSampling_.sumRms          = 0;
}


bool ACS712_nonblocking::updateACSampling()
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
    const float currentSteps = (float)((int)reading - midPoint_);
    acSampling_.sumSquared += (currentSteps * currentSteps);
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
    const float currentSteps = (float)((int)reading - midPoint_);
    acSampling_.sumSquared = (currentSteps * currentSteps);
  }

  acSampling_.sumRms += sqrt(acSampling_.sumSquared / acSampling_.samples);
  acSampling_.completedCycles++;

  if (acSampling_.completedCycles >= acSampling_.targetCycles)
  {
    float mA = acSampling_.sumRms * mAPerStep_;
    if (acSampling_.targetCycles > 1) mA /= acSampling_.targetCycles;

    acSampling_.resultmAUncorrected = mA;
    mA -= offsetmA_;
    if (clampZero_ && (mA < 0.0f)) mA = 0.0f;

    acSampling_.resultmA  = mA;
    acSampling_.active    = false;
    acSampling_.available = true;
    return true;
  }

  acSampling_.cycleStartUs = now;
  acSampling_.samples      = 0;
  acSampling_.sumSquared   = 0;
  return false;
}


bool ACS712_nonblocking::busy() const
{
  return acSampling_.active;
}


bool ACS712_nonblocking::available() const
{
  return acSampling_.available;
}


float ACS712_nonblocking::resultmA() const
{
  return acSampling_.resultmA;
}


float ACS712_nonblocking::resultmAUncorrected() const
{
  return acSampling_.resultmAUncorrected;
}


void ACS712_nonblocking::cancel()
{
  acSampling_.active    = false;
  acSampling_.available = false;
}


uint16_t ACS712_nonblocking::analogRead16_(uint8_t pin)
{
  if (readADC_ != nullptr) return readADC_(pin);
  return (uint16_t)analogRead(pin);
}

