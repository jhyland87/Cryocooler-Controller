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
#include "device.h"

static MD_AD9833 ad9833(AD9833_CS);


namespace waveform {

module::InitStatus init() {
    ad9833.begin();
    ad9833.setMode(MD_AD9833::MODE_SINE);
    ad9833.setFrequency(MD_AD9833::CHAN_0, AD9833_FREQ_HZ);

    Serial.printf("[waveform] AD9833 initialized - Generating %u Hz sine wave\n",
                  static_cast<unsigned>(AD9833_FREQ_HZ));
    return module::MODULE_INIT_SUCCESS;
}

void service() {
    float voltageV = device::getVoltage();
    mode_t mode = ad9833.getMode();

    if (voltageV < 11.5f) {
        if (mode != MD_AD9833::MODE_OFF) {
            Serial.println("Voltage too low for proper sine wave, turning off DDS");
            ad9833.setMode(MD_AD9833::MODE_OFF);
        }
    } else if (mode != MD_AD9833::MODE_SINE) {
        Serial.println("Voltage has returned to normal, turning on DDS");
        ad9833.setMode(MD_AD9833::MODE_SINE);
    }
}

int16_t getStatus(){
    return ad9833.getMode() == MD_AD9833::MODE_OFF ? 0 : 1;
}

float getFrequency(){
    return ad9833.getFrequency(MD_AD9833::CHAN_0);
}


} // namespace waveform
