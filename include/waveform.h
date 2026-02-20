/**
 * @file waveform.h
 * @brief AD9833 DDS waveform generator interface
 *
 * Manages the AD9833 sine-wave output only.
 * LED / indicator control has moved to indicator.h.
 */

#ifndef WAVEFORM_H
#define WAVEFORM_H

namespace waveform {

/**
 * Initialize the AD9833 and begin generating the configured sine wave.
 */
void init();

} // namespace waveform

#endif // WAVEFORM_H
