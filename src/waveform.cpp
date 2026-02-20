/**
 * @file waveform.cpp
 * @brief AD9833 DDS waveform generator implementation
 */

#include <Arduino.h>
#include <MD_AD9833.h>

#include "pin_config.h"
#include "config.h"
#include "waveform.h"

static MD_AD9833 ad9833(AD9833_CS);

namespace waveform {

void init() {
    ad9833.begin();
    ad9833.setMode(MD_AD9833::MODE_SINE);
    ad9833.setFrequency(MD_AD9833::CHAN_0, AD9833_FREQ_HZ);

    Serial.printf("AD9833 initialized - Generating %u Hz sine wave\n",
                  static_cast<unsigned>(AD9833_FREQ_HZ));
}

} // namespace waveform
