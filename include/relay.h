/**
 * @file relay.h
 * @brief Bypass and alarm relay control
 *
 * Two relays are managed:
 *
 *   BYPASS_RELAY_PIN  - LOW = Bypass mode (default / safe),
 *                       HIGH = Normal mode (states 5, 6, 7 only).
 *
 *   ALARM_RELAY_PIN   - LOW = idle, HIGH = alarm (state 8 / Fault only).
 */

#ifndef RELAY_H
#define RELAY_H

namespace relay {

/**
 * Initialize relay GPIO pins (outputs, defaulting to Bypass / alarm-off).
 */
void init();

/**
 * Switch the bypass relay.
 * @param normal  true = Normal mode (HIGH), false = Bypass mode (LOW).
 */
void setBypass(bool normal);

/**
 * Drive the alarm relay.
 * @param active  true = alarm on (HIGH), false = alarm off (LOW).
 */
void setAlarm(bool active);

} // namespace relay

#endif // RELAY_H
