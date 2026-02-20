/**
 * @file relay.cpp
 * @brief Bypass and alarm relay implementation
 */

#include <Arduino.h>

#include "pin_config.h"
#include "relay.h"

namespace relay {

void init() {
    pinMode(BYPASS_RELAY_PIN, OUTPUT);
    pinMode(ALARM_RELAY_PIN,  OUTPUT);
    digitalWrite(BYPASS_RELAY_PIN, LOW);   // start in Bypass
    digitalWrite(ALARM_RELAY_PIN,  LOW);   // alarm off
}

void setBypass(bool normal) {
    digitalWrite(BYPASS_RELAY_PIN, normal ? HIGH : LOW);
}

void setAlarm(bool active) {
    digitalWrite(ALARM_RELAY_PIN, active ? HIGH : LOW);
}

} // namespace relay
