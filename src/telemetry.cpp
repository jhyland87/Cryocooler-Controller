/**
 * @file telemetry.cpp
 * @brief Serial Studio CSV telemetry implementation
 */

// emit() depends on Serial and temperature — hardware only.
// enable()/disable()/isEnabled() are plain flag operations and compile everywhere.
#ifdef ARDUINO
#  include <Arduino.h>
#  include "temperature.h"
#endif

#include "telemetry.h"
#include "state_machine.h"

namespace telemetry {

static bool sEnabled = true;

void disable()   { sEnabled = false; }
void enable()    { sEnabled = true; }
bool isEnabled() { return sEnabled; }

void emit(const state_machine::Output& out,
          float    tempK,
          float    tempC,
          float    coolingRate,
          float    rmsV,
          uint16_t dacActual,
          bool     redLedOn,
          bool     greenLedOn)
{
#ifdef ARDUINO
    if (!sEnabled) return;

    // Convert on-state duration from ms to seconds and HH:MM:SS
    const uint32_t durationMs  = state_machine::getOnStateDuration();
    const uint32_t totalSec    = durationMs / 1000u;
    const uint32_t hh          = totalSec / 3600u;
    const uint32_t mm          = (totalSec % 3600u) / 60u;
    const uint32_t ss          = totalSec % 60u;

    char hmsBuf[12];
    snprintf(hmsBuf, sizeof(hmsBuf), "%02lu:%02lu:%02lu",
             static_cast<unsigned long>(hh),
             static_cast<unsigned long>(mm),
             static_cast<unsigned long>(ss));

    // Serial Studio Quick-Plot frame: /*...*/\r\n
    // 15 CSV fields matching Cryocooler.ssproj parser
    Serial.printf("/*%d|%s|%s|%.2f|%.2f|%.3f|%u|%u|%.2f|%u|%u|%d|%d|%lu|%s|%.2f*/\r\n",
                  static_cast<int8_t>(out.state),
                  state_machine::stateName(out.state),
                  state_machine::getStatusText(),
                  tempK,
                  tempC,
                  coolingRate,
                  static_cast<unsigned>(out.dacTarget),
                  static_cast<unsigned>(dacActual),
                  rmsV,
                  static_cast<uint8_t>(!out.bypassRelay),  // 1 = Normal
                  static_cast<uint8_t>(out.alarmRelay),
                  redLedOn   ? 1 : 0,
                  greenLedOn ? 1 : 0,
                  static_cast<unsigned long>(totalSec),
                  hmsBuf,
                  temperature::getTemperatureToPercent());
#else
    // Suppress unused-parameter warnings in native builds.
    (void)out; (void)tempK; (void)tempC; (void)coolingRate;
    (void)rmsV; (void)dacActual; (void)redLedOn; (void)greenLedOn;
#endif
}

} // namespace telemetry
