/**
 * @file indicator.h
 * @brief FAULT and READY indicator control
 *
 * Drives the on-board WS2812 RGB LED (and optionally discrete digital LEDs
 * on FAULT_IND_PIN / READY_IND_PIN) according to the system state table:
 *
 *   State  | FAULT IND          | READY IND
 *   -------|--------------------|-----------------------
 *   0 Init | AMBER (momentary)  | AMBER (momentary)
 *   1 Idle | ON RED             | OFF
 *   2 Crse | Flash fast RED     | OFF
 *   3 Fine | Flash fast RED     | Flash slow GREEN
 *   4 Over | Flash fast RED     | Flash fast GREEN
 *   5 Sett | Flash fast RED     | Flash fast GREEN
 *   6 Base | OFF                | ON GREEN
 *   7 Oper | OFF                | ON GREEN
 *   8 Flt  | ON RED             | OFF
 *
 * Flash fast = 2 Hz (INDICATOR_FLASH_FAST_PERIOD_MS)
 * Flash slow = 1 Hz (INDICATOR_FLASH_SLOW_PERIOD_MS)
 *
 * All timing is non-blocking; call update() every loop.
 */

#ifndef INDICATOR_H
#define INDICATOR_H

#include <stdint.h>

namespace indicator {

/** Single-indicator display modes. */
enum class Mode : uint8_t {
    Off,
    SolidRed,
    SolidGreen,
    SolidAmber,
    FlashFastRed,
    FlashSlowRed,
    FlashFastGreen,
    FlashSlowGreen,
};

/**
 * Initialize GPIO pins and the WS2812 driver.
 * Must be called once in setup().
 */
void init();

/**
 * Set the desired display mode for the FAULT indicator.
 */
void setFaultMode(Mode mode);

/**
 * Set the desired display mode for the READY indicator.
 */
void setReadyMode(Mode mode);

/**
 * Service the indicator state machine.
 * Must be called every loop iteration (non-blocking).
 *
 * @param nowMs  Current millis() value
 */
void update(uint32_t nowMs);

/**
 * Return true if the FAULT (red) LED is currently lit this tick.
 * Accounts for flash modes — returns the instantaneous on/off state.
 * Only valid after update() has been called for the current tick.
 */
bool isFaultOn();

/**
 * Return true if the READY (green) LED is currently lit this tick.
 * Accounts for flash modes — returns the instantaneous on/off state.
 * Only valid after update() has been called for the current tick.
 */
bool isReadyOn();

} // namespace indicator

#endif // INDICATOR_H
