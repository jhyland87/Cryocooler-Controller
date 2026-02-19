/**
 * @file waveform.h
 * @brief AD9833 DDS waveform generator interface
 */

#ifndef WAVEFORM_H
#define WAVEFORM_H

namespace waveform {
/**
 * Initialize the AD9833 and begin generating the configured sine wave.
 */
void init();

/**
 * Status LED helpers (on-board WS2812).
 */
void statusError();
void statusOk();
void statusOff();
} // namespace waveform

#endif // WAVEFORM_H
