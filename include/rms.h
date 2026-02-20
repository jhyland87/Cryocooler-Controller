/**
 * @file rms.h
 * @brief RMS-to-DC converter interface (STUBBED)
 *
 * The hardware RMS measurement is not yet implemented.
 * getVoltage() returns 0.0f so the state machine's over-voltage guard
 * remains dormant until the real driver is in place.
 */

#ifndef RMS_H
#define RMS_H

namespace rms {

/**
 * Initialize the RMS-to-DC converter.
 */
void init();

/**
 * Read and cache the latest RMS voltage measurement.
 * Must be called once per loop interval.
 */
void read();

/**
 * Return the most recently measured RMS voltage in VDC.
 * Returns 0.0f while the hardware driver is stubbed.
 */
float getVoltage();

} // namespace rms

#endif // RMS_H
