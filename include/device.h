/**
 * @file waveform.h
 * @brief AD9833 DDS waveform generator interface
 *
 * Manages the AD9833 sine-wave output only.
 * LED / indicator control has moved to indicator.h.
 */

#ifndef DEVICE_H
#define DEVICE_H

namespace device {

/**
 * Initialize the AD9833 and begin generating the configured sine wave.
 */
void init();

void service();

float getVoltage();

int16_t getVoltageRaw();
} // namespace device

#endif // DEVICE_H
