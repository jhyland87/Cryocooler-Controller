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
#include <cstring>
#include "frame_builder.h"

// ---------------------------------------------------------------------------
// Serial line format:  v1\tv2\t...\tvN\r\n
//
// The entire frame is assembled into a single stack buffer before calling
// out.write() once.  This is important on ESP32: the Arduino HWCDC Serial
// implementation flushes its internal ring buffer asynchronously, so making
// ~50 individual print() calls lets the FreeRTOS scheduler preempt between
// them and interleave output from other tasks (WiFi, TCP/IP stack, etc.).
// A single write() keeps the complete frame contiguous in the USB FIFO.
// ---------------------------------------------------------------------------

void FrameBuilder::sendSerial(Print& out) const {
    // Worst-case frame size:
    //   2  ("/*") + MAX_FIELDS * (VALUE_BUF_SIZE + 1) ("val|") + 4 ("*/\r\n") + 1 (NUL)
    constexpr size_t BUF_SIZE =
        2u + static_cast<size_t>(MAX_FIELDS) * (VALUE_BUF_SIZE + 1u) + 4u + 1u;

    char   buf[BUF_SIZE];
    size_t pos = 0u;

    auto append = [&](const char* text, size_t length) {
        if (pos + length >= BUF_SIZE) { return; }   // truncate rather than overflow
        memcpy(buf + pos, text, length);
        pos += length;
    };

    //append("/*", 2u);
    for (uint8_t fieldIndex = 0u; fieldIndex < count_; ++fieldIndex) {
        if (fieldIndex > 0u) { append("\t", 1u); }
        append(fields_[fieldIndex].str, strlen(fields_[fieldIndex].str));
    }
    append("\r\n", 2u);


    out.write(reinterpret_cast<const uint8_t*>(buf), pos);
}

// ---------------------------------------------------------------------------
// Delta serial output — only changed fields, "name=value  name=value\r\n"
//
// A static BSS buffer is used (rather than a stack allocation) because the
// worst-case size — MAX_FIELDS × (field-name + "=" + VALUE_BUF_SIZE + "  ")
// plus "\r\n\0" — exceeds what is safe to allocate on the ESP32 task stack.
// emit() is called from a single FreeRTOS task so there is no reentrancy risk.
// ---------------------------------------------------------------------------

void FrameBuilder::sendSerialDelta(Print& out, const FrameBuilder& prev,
                                   const char* const* passiveFields,
                                   uint8_t            passiveCount) const {
    // Helper: true if field name appears in the passive list.
    auto isPassive = [&](const char* name) -> bool {
        for (uint8_t passiveIndex = 0u; passiveIndex < passiveCount; ++passiveIndex) {
            if (passiveFields[passiveIndex] && strcmp(name, passiveFields[passiveIndex]) == 0) {
                return true;
            }
        }
        return false;
    };

    // ── Phase 1: decide whether to emit anything ────────────────────────────
    // At least one *non-passive* field must have changed; otherwise the entire
    // output is suppressed (even changed passive fields are silent on their own).
    bool anyActiveChange = false;
    for (uint8_t fieldIndex = 0u; fieldIndex < count_; ++fieldIndex) {
        const bool changed = (fieldIndex >= prev.count_) ||
                             (strcmp(fields_[fieldIndex].str, prev.fields_[fieldIndex].str) != 0);
        if (changed && !isPassive(fields_[fieldIndex].name)) {
            anyActiveChange = true;
            break;
        }
    }
    if (!anyActiveChange) { return; }

    // ── Phase 2: assemble and write all changed fields (passive included) ───
    // Worst-case: every field changed.
    // Per field: name (≤ VALUE_BUF_SIZE) + "=" + str (≤ VALUE_BUF_SIZE) + "  "
    static char buf[static_cast<size_t>(MAX_FIELDS) * (2u * VALUE_BUF_SIZE + 3u) + 3u];

    size_t pos        = 0u;
    bool   firstToken = true;

    auto append = [&](const char* text, size_t length) {
        if (pos + length >= sizeof(buf)) { return; }
        memcpy(buf + pos, text, length);
        pos += length;
    };

    for (uint8_t fieldIndex = 0u; fieldIndex < count_; ++fieldIndex) {
        const bool changed = (fieldIndex >= prev.count_) ||
                             (strcmp(fields_[fieldIndex].str, prev.fields_[fieldIndex].str) != 0);
        if (!changed) { continue; }

        if (!firstToken) { append("  ", 2u); }
        firstToken = false;

        append(fields_[fieldIndex].name, strlen(fields_[fieldIndex].name));
        append("=", 1u);
        append(fields_[fieldIndex].str,  strlen(fields_[fieldIndex].str));
    }

    append("\r\n", 2u);
    out.write(reinterpret_cast<const uint8_t*>(buf), pos);
}

// ---------------------------------------------------------------------------
// JSON helpers
// ---------------------------------------------------------------------------

/**
 * Navigate the dot-separated key path, creating intermediate JsonObject nodes
 * as needed, then assign the field value directly to the final leaf slot.
 *
 * Assigning via obj[seg] = value rather than through a returned JsonVariant
 * is required because ArduinoJson v7's JsonVariant proxy does not propagate
 * mutations back to the document when returned by value.
 *
 *   "foo"     → root["foo"]         = value
 *   "foo.bar" → root["foo"]["bar"]  = value  (root["foo"] created if absent)
 *   "a.b.c"   → root["a"]["b"]["c"] = value
 *
 * @note The field name is copied into a stack buffer capped at
 *       VALUE_BUF_SIZE - 1 characters.
 */
static void setNestedField(JsonObject root, const FrameBuilder::Field& field)
{
    char  buf[FrameBuilder::VALUE_BUF_SIZE];
    strncpy(buf, field.name, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    JsonObject obj = root;
    char*      seg = buf;
    char*      dot;

    while ((dot = strchr(seg, '.')) != nullptr) {
        *dot = '\0';
        if (!obj[seg].is<JsonObject>()) {
            obj[seg].to<JsonObject>();
        }
        obj = obj[seg].as<JsonObject>();
        seg = dot + 1;
    }

    switch (field.type) {
        case FrameBuilder::Field::Type::Signed:   obj[seg] = field.num.signedValue; break;
        case FrameBuilder::Field::Type::Unsigned: obj[seg] = field.num.unsignedValue; break;
        case FrameBuilder::Field::Type::Float:    obj[seg] = field.num.floatValue; break;
        case FrameBuilder::Field::Type::String:   obj[seg] = field.str;   break;
    }
}

// ---------------------------------------------------------------------------
// JSON object — dotted field names produce nested objects.
//
//   field("foo",     ...) → { "foo": value }
//   field("foo.bar", ...) → { "foo": { "bar": value } }
//
// sendSerial() is unaffected; it always emits the pre-formatted str value.
// ---------------------------------------------------------------------------

void FrameBuilder::fillJson(JsonDocument& doc) const {
    // to<JsonObject>() clears the document and roots it as an object so that
    // setNestedField() can safely navigate and create intermediate nodes.
    JsonObject root = doc.to<JsonObject>();
    for (uint8_t fieldIndex = 0; fieldIndex < count_; ++fieldIndex) {
        setNestedField(root, fields_[fieldIndex]);
    }
}
