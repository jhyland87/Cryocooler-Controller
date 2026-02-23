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
#include "waveform.h"
#include "device.h"

// ---------------------------------------------------------------------------
// FrameBuilder — incremental Serial Studio frame assembler
//
// Builds a /*field1|field2|...*/\r\n frame into a fixed stack buffer.
// Each call to field() appends one value with its printf format, inserting
// the pipe delimiter automatically.  send() closes and transmits the frame.
//
// Usage:
//   FrameBuilder frame;
//   frame.field("%d",   myInt)        // field 1
//        .field("%.2f", myFloat)      // field 2
//        ...;
//   frame.send(Serial);
// ---------------------------------------------------------------------------

class FrameBuilder {
public:
    static constexpr size_t CAPACITY = 512;

    FrameBuilder() : pos_(2) {
        buf_[0] = '/';
        buf_[1] = '*';
    }

    template<typename... Args>
    FrameBuilder& field(const char* fmt, Args&&... args) {
        if (pos_ > 2) {
            if (pos_ < CAPACITY - 1) buf_[pos_++] = '|';
        }
        int n = snprintf(buf_ + pos_, CAPACITY - pos_, fmt,
                         std::forward<Args>(args)...);
        if (n > 0) pos_ += static_cast<size_t>(n);
        return *this;
    }

    void send(Print& out) {
        snprintf(buf_ + pos_, CAPACITY - pos_, "*/\r\n");
        out.print(buf_);
    }

private:
    char   buf_[CAPACITY];
    size_t pos_;
};

// ---------------------------------------------------------------------------

namespace telemetry {

static bool enabled = true;

void disable()   { enabled = false; }
void enable()    { enabled = true; }
bool isEnabled() { return enabled; }

void emit(const state_machine::Output& out)
{
#ifdef ARDUINO
    if (!enabled) return;

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

    // Build and send the Serial Studio Quick-Plot frame: /*field1|field2|...*/\r\n
    // To add a field: append one .field(fmt, value) call and update telemetry.h.
    FrameBuilder frame;
    frame
        .field("%d",   static_cast<int8_t>(out.state))             //  1 state_no
        .field("%s",   state_machine::stateName(out.state))        //  2 state_name
        .field("%s",   state_machine::getStatusText())             //  3 status_text
        .field("%.2f", temperature::getLastTempK())                //  4 temp_k
        .field("%.2f", temperature::getLastTempC())                //  5 temp_c
        .field("%.2f", temperature::getLastAmbientTempC())         //  6 ambient_temp_c
        .field("%.3f", temperature::getCoolingRateKPerMin())       //  7 cooling_rate
        .field("%u",   static_cast<unsigned>(out.dacTarget))       //  8 dac_target
        .field("%u",   static_cast<unsigned>(dacActual))           //  9 dac_actual
        .field("%.2f", rms::getVoltage())                          // 10 rms_v
        .field("%u",   static_cast<uint8_t>(!out.bypassRelay))     // 11 relay_normal (1=Normal)
        .field("%u",   static_cast<uint8_t>(out.alarmRelay))       // 12 alarm_relay
        .field("%d",   indicator::isFaultOn())                     // 13 red_led
        .field("%d",   indicator::isReadyOn())                     // 14 green_led
        .field("%lu",  static_cast<unsigned long>(durationMs))     // 15 on_duration_ms
        .field("%s",   hmsBuf)                                     // 16 on_duration HH:MM:SS
        .field("%.2f", temperature::getTemperatureToPercent())     // 17 cooldown_pct
        .field("%s",   tisHmsBuf)                                  // 18 time_in_state HH:MM:SS
        .field("%.2f", rms::getCurrentA())                         // 19 current_a
        .field("%u",   static_cast<unsigned>(out.backoffCount))    // 20 backoff_count
        .field("%.2f", temperature::getLastTempCBelowAmbient())    // 21 delta_below_ambient_c
        .field("%.2f", device::getVoltage())                       // 22 voltage_v
        .field("%.2f", device::getVoltageRaw())                    // 23 voltage_raw
        .field("%u",   waveform::getStatus())                      // 24 waveform_status
        .field("%.2f", waveform::getFrequency());                  // 25 frequency_hz
    frame.send(Serial);
#else
    (void)out;
#endif
}

} // namespace telemetry
