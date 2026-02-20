/**
 * @file rms.cpp
 * @brief RMS-to-DC converter stub implementation
 *
 * TODO: Replace stub with real ADC read when hardware is available.
 */

#include "rms.h"

static float sVoltage = 0.0f;  // stubbed to 0 V

namespace rms {

void init() {
    // TODO: configure ADC channel / scaling for RMS-DC converter
    sVoltage = 0.0f;
}

void read() {
    // TODO: read ADC, convert raw counts to VDC, store in sVoltage
    sVoltage = 0.0f;
}

float getVoltage() {
    return sVoltage;
}

} // namespace rms
