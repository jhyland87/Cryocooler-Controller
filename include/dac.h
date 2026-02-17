/**
 * @file dac.h
 * @brief DAC output control driven by ADC feedback
 */

#ifndef DAC_H
#define DAC_H

/**
 * Update the DAC output based on the ADC feedback value.
 * Drives DAC_PIN to absolute GND when the reading is zero.
 */
void dac_update(uint16_t dacVal);

#endif // DAC_H
