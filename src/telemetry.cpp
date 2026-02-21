/**
 * @file telemetry.cpp
 * @brief Serial Studio CSV telemetry implementation
 */

// emit() depends on Serial and hardware modules — target only.
// enable()/disable()/isEnabled() are plain flag operations and compile everywhere.
#include <Arduino.h>
#include "temperature.h"
#include "telemetry.h"
#include "state_machine.h"
#include "rms.h"
#include "dac.h"
#include "conversions.h"

namespace telemetry {

static bool sEnabled = true;

void disable()   { sEnabled = false; }
void enable()    { sEnabled = true; }
bool isEnabled() { return sEnabled; }

void emit(const state_machine::Output& out)
{
#ifdef ARDUINO
    if (!sEnabled) return;

    const uint16_t dacActual  = dac::getCurrent();

    // On-state duration (total time running since start())
    const uint32_t durationMs = state_machine::getOnStateDuration();
    const uint32_t durSec     = durationMs / 1000u;
    char hmsBuf[12];
    snprintf(hmsBuf, sizeof(hmsBuf), "%02lu:%02lu:%02lu",
             static_cast<unsigned long>(durSec / 3600u),
             static_cast<unsigned long>((durSec % 3600u) / 60u),
             static_cast<unsigned long>(durSec % 60u));

    // Time in current state (resets on every state transition)
    const uint32_t stateMs  = state_machine::getTimeInState();
    const uint32_t stateSec = stateMs / 1000u;
    char tisHmsBuf[12];
    snprintf(tisHmsBuf, sizeof(tisHmsBuf), "%02lu:%02lu:%02lu",
             static_cast<unsigned long>(stateSec / 3600u),
             static_cast<unsigned long>((stateSec % 3600u) / 60u),
             static_cast<unsigned long>(stateSec % 60u));

    // Serial Studio Quick-Plot frame: /*...*/\r\n
    // 17 pipe-delimited fields matching Cryocooler.ssproj parser
    Serial.printf("/*%d|%s|%s|%.2f|%.2f|%.3f|%u|%u|%.2f|%u|%u|%d|%d|%lu|%s|%.2f|%s*/\r\n",
                  static_cast<int8_t>(out.state),           //  1 state_no
                  state_machine::stateName(out.state),       //  2 state_name
                  state_machine::getStatusText(),            //  3 status_text
                  temperature::getLastTempK(),               //  4 temp_k
                  temperature::getLastTempC(),               //  5 temp_c
                  temperature::getCoolingRateKPerMin(),      //  6 cooling_rate
                  static_cast<unsigned>(out.dacTarget),      //  7 dac_target
                  static_cast<unsigned>(dacActual),          //  8 dac_actual
                  rms::getVoltage(),                         //  9 rms_v
                  static_cast<uint8_t>(!out.bypassRelay),   // 10 relay_normal (1=Normal)
                  static_cast<uint8_t>(out.alarmRelay),     // 11 alarm_relay
                  indicator::isFaultOn(),                    // 12 red_led
                  indicator::isReadyOn(),                    // 13 green_led
                  static_cast<unsigned long>(durationMs),   // 14 on_duration_ms
                  hmsBuf,                                    // 15 on_duration HH:MM:SS
                  temperature::getTemperatureToPercent(),   // 16 cooldown_percent
                  tisHmsBuf);                                // 17 time_in_state HH:MM:SS
#else
    (void)out;
#endif
}

} // namespace telemetry
