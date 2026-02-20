/**
 * @file telemetry.cpp
 * @brief Serial Studio CSV telemetry implementation
 */

#include <Arduino.h>
#include "telemetry.h"
#include "state_machine.h"

namespace telemetry {

void emit(const state_machine::Output& out,
          float    tempK,
          float    tempC,
          float    coolingRate,
          float    rmsV,
          uint16_t dacActual,
          bool     redLedOn,
          bool     greenLedOn)
{
    // Serial Studio Quick-Plot frame: /*...*/\r\n
    // 13 CSV fields matching Cryocooler.ssproj parser
    Serial.printf("/*%d,%s,%s,%.2f,%.2f,%.3f,%u,%u,%.2f,%u,%u,%s,%s*/\r\n",
                  static_cast<int8_t>(out.state),
                  state_machine::stateName(out.state),
                  out.statusText ? out.statusText : "",
                  tempK,
                  tempC,
                  coolingRate,
                  static_cast<unsigned>(out.dacTarget),
                  static_cast<unsigned>(dacActual),
                  rmsV,
                  static_cast<uint8_t>(!out.bypassRelay),  // 1 = Normal
                  static_cast<uint8_t>(out.alarmRelay),
                  redLedOn   ? "100" : "0",
                  greenLedOn ? "100" : "0");
}

} // namespace telemetry
