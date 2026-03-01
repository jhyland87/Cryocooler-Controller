/**
 * @file waveform.cpp
 * @brief AD9833 DDS waveform generator implementation
 */

#include <Arduino.h>
#include <MD_AD9833.h>

#include "pin_config.h"
#include "config.h"
#include "waveform.h"
#include "module.h"
#include "sysinfo.h"

static MD_AD9833 ad9833(AD9833_CS);


// System voltage in volts
static float     rmsVoltage     = 0.0f;
static mode_t    waveformMode   = MD_AD9833::MODE_OFF;
static float     frequency      = 0.0f;

namespace waveform {
module::InitStatus init() {
    ad9833.begin();
    ad9833.setMode(MD_AD9833::MODE_SINE);
    ad9833.setFrequency(MD_AD9833::CHAN_0, AD9833_FREQ_HZ);

    Serial.printf("[waveform] AD9833 initialized - Generating %u Hz sine wave\n",
                  static_cast<unsigned>(AD9833_FREQ_HZ));
    return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    rmsVoltage = sysinfo::getVoltage();
    waveformMode = ad9833.getMode();
    frequency = ad9833.getFrequency(MD_AD9833::CHAN_0);

   return module::MODULE_SERVICE_OK;
}

void disable(){
    ad9833.setMode(MD_AD9833::MODE_OFF);
}
bool isEnabled(){
    return waveformMode != MD_AD9833::MODE_OFF;
}
void enable(){
    ad9833.setMode(MD_AD9833::MODE_SINE);
}

float getFrequency(){
    return frequency;
}

mode_t getWaveformMode(){
    return waveformMode;
}

float getRMSVoltage(){
    return rmsVoltage;
}

} // namespace waveform
