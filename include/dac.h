/**
 * @file dac.h
 * @brief DAC output control driven by ADC feedback
 */

#ifndef DAC_H
#define DAC_H

/**
 * Read the ADC feedback pin and mirror the value to the DAC output.
 * Drives DAC_PIN to absolute GND when the reading is zero.
 */
void dac_update();

#endif // DAC_H
