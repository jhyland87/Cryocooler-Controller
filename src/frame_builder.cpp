/**
 * @file frame_builder.cpp
 * @brief FrameBuilder output method implementations.
 */

#ifdef ARDUINO
#  include <Arduino.h>
#else
#  include "Arduino.h"   // native stub — provides Print
#endif

#include <ArduinoJson.h>
#include "frame_builder.h"

// ---------------------------------------------------------------------------
// Serial Studio wire format:  /*v1|v2|...|vN*/\r\n
// ---------------------------------------------------------------------------

void FrameBuilder::sendSerial(Print& out) const {
    out.print("/*");
    for (uint8_t i = 0; i < count_; ++i) {
        if (i > 0) out.print("|");
        out.print(fields_[i].str);
    }
    out.print("*/\r\n");
}

// ---------------------------------------------------------------------------
// JSON object:  {"name": typed_value, ...}
// ---------------------------------------------------------------------------

void FrameBuilder::fillJson(JsonDocument& doc) const {
    doc.clear();
    for (uint8_t i = 0; i < count_; ++i) {
        const Field& f = fields_[i];
        switch (f.type) {
            case Field::Type::Signed:   doc[f.name] = f.num.i; break;
            case Field::Type::Unsigned: doc[f.name] = f.num.u; break;
            case Field::Type::Float:    doc[f.name] = f.num.f; break;
            case Field::Type::String:   doc[f.name] = f.str;   break;
        }
    }
}
