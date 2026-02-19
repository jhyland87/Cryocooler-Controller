/*!\file SmoothADC.cpp
** \author SMFSW
** \date 2017/11/21
** \copyright GNU LESSER GENERAL PUBLIC LICENSE (c) 2017, SMFSW
** \brief Get ADC to return averaged values
**/

#include <Arduino.h>
#include <stdint.h>
#include <string.h>

#include "SmoothADC.h"

void SmoothADC::init(const uint16_t Pin, const tick_base Res, const unsigned long Period) {
  pinMode(Pin, INPUT);
  ADCPin = Pin;
  setResolution(Res);
  AcqPeriod = Period;
  ADCChannel.NumAcq = 0;
}

bool SmoothADC::TestAcqRate(void) {
  const unsigned long tempTime = get_tick();

  if (tempTime - MemTimeAcq >= AcqPeriod) {
    MemTimeAcq = tempTime;
    return true;
  }

  return false;
}

void SmoothADC::Filtering(void) {
  uint16_t temp[DEF_NB_ACQ], swap;

  memcpy(temp, ADCChannel.ADCTab, sizeof(temp)); // Tab copy before average calc

  // Retrieve max value on 0 idx tab
  for (unsigned int c = 1; c < DEF_NB_ACQ; c++) {
    if (temp[0] < temp[c]) {
      swap = temp[0];
      temp[0] = temp[c];
      temp[c] = swap;
    }
  }

  // Retrieve min value on last idx tab
  for (unsigned int c = 1; c < (DEF_NB_ACQ - 1); c++) {
    if (temp[DEF_NB_ACQ - 1] > temp[c]) {
      swap = temp[DEF_NB_ACQ - 1];
      temp[DEF_NB_ACQ - 1] = temp[c];
      temp[c] = swap;
    }
  }

  // Average calc
  ADCChannel.Average = static_cast<uint16_t>((temp[1] + temp[2]) / 2);
}

#define DEF_BIT_ACQ 0x80U                 //!< Bit used to specify all acquisitions ok (MSB)
#define DEF_MSQ_NumAcq (uint8_t)(~DEF_BIT_ACQ) //!< Other bits in NumAcq (7 LSBs)

void SmoothADC::serviceADCPin(void) {
  if (En == true) {
    if (TestAcqRate() == true) {
      ADCChannel.ADCTab[ADCChannel.NumAcq & DEF_MSQ_NumAcq] = analogRead(ADCPin);
      if ((ADCChannel.NumAcq++ & DEF_MSQ_NumAcq) >= DEF_NB_ACQ) {
        ADCChannel.NumAcq = DEF_BIT_ACQ;
      }
    }
  }
}

uint16_t SmoothADC::getADCVal(void) {
  if (ADCChannel.NumAcq & DEF_BIT_ACQ) {
    Filtering();
  }
  return ADCChannel.Average;
}

void SmoothADC::dbgInfo(void) {
#ifdef DEBUG
  Serial.printf("!> Pin %u, Rate: %lu%s\n",
                static_cast<unsigned int>(getPin()),
                getPeriod(),
                (getResolution() == TB_US) ? "us" : "ms");

  Serial.print("!> Tab:\t");
  for (unsigned int c = 0; c < DEF_NB_ACQ; c++) {
    Serial.print(ADCChannel.ADCTab[c]);
    Serial.print('\t');
  }
  Serial.println();
#endif
}

