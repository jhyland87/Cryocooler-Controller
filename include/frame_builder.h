/**
 * @file frame_builder.h
 * @brief Multi-format telemetry frame builder.
 *
 * FrameBuilder accumulates named fields via a fluent field() API and renders
 * them in two formats:
 *
 *   sendSerial(Print&)     — Serial Studio wire format: `v1\tv2\t...\r\n`
 *   fillJson(JsonDocument&)— JSON object: {"name": typed_value, ...}
 *
 * Field types are detected automatically at compile time from the value
 * argument passed to field():
 *
 *   Floating-point args  → stored as float,    serialized as JSON number
 *   Signed integral args → stored as int64_t,  serialized as JSON number
 *   Unsigned integral    → stored as uint64_t, serialized as JSON number
 *   Pointer/string args  → stored as string,   serialized as JSON string
 *
 * The formatted string (via snprintf) is always stored regardless of type,
 * so sendSerial always outputs exactly what was specified by the format string.
 *
 * Usage:
 *   FrameBuilder frame;
 *   frame.field("temp_c",  "%.2f", temperature::getLastTempC())
 *        .field("state",   "%d",   static_cast<int>(currentState))
 *        .field("label",   "%s",   "Running");
 *   frame.sendSerial(Serial);
 *
 *   JsonDocument doc;
 *   frame.fillJson(doc);          // {"temp_c": 23.45, "state": 2, "label": "Running"}
 */

#ifndef FRAME_BUILDER_H
#define FRAME_BUILDER_H

#include <cstdio>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <ArduinoJson.h>

// Print is forward-declared here; the full header is only needed in
// frame_builder.cpp.  Including Arduino.h in this header would pull in the
// entire Arduino SDK for every translation unit that includes frame_builder.h.
class Print;

class FrameBuilder {
public:
    // Maximum number of fields per frame.  Increase if telemetry grows.
    static constexpr uint8_t MAX_FIELDS     = 130;
    // Maximum length of a formatted value string including the NUL terminator.
    static constexpr uint8_t VALUE_BUF_SIZE = 84;

    // ---------------------------------------------------------------------------
    // Field storage
    // ---------------------------------------------------------------------------

    struct Field {
        const char* name;               ///< Key name (string literal — not owned)
        char        str[VALUE_BUF_SIZE];///< Pre-formatted value string (for serial)
        enum class  Type : uint8_t { Signed, Unsigned, Float, String } type;
        union {
            int64_t  i;   ///< Signed integral value   (for JSON)
            uint64_t u;   ///< Unsigned integral value  (for JSON)
            float    f;   ///< Floating-point value     (for JSON)
        } num;
    };

    // ---------------------------------------------------------------------------
    // Construction / reset
    // ---------------------------------------------------------------------------

    FrameBuilder() : count_(0) {}

    /** Discard all fields so the builder can be reused. */
    void reset() { count_ = 0; }

    // ---------------------------------------------------------------------------
    // Field accumulation
    // ---------------------------------------------------------------------------

    /**
     * Append one named field.
     *
     * @param name  Key name (must outlive the FrameBuilder — use string literals).
     * @param fmt   printf-style format string for the value (e.g. "%.2f", "%d").
     * @param value The value to format.  Its C++ type determines how it is stored
     *              for JSON output; the format string controls serial output.
     */
    template<typename T>
    FrameBuilder& field(const char* name, const char* fmt, T value) {
        if (count_ >= MAX_FIELDS) return *this;

        Field& f = fields_[count_++];
        f.name   = name;
        snprintf(f.str, VALUE_BUF_SIZE, fmt, value);

        using DT = std::decay_t<T>;

        if constexpr (std::is_same_v<DT, bool>) {
            // bool before the general integral check to avoid ambiguity.
            f.type  = Field::Type::Unsigned;
            f.num.u = value ? 1u : 0u;
        } else if constexpr (std::is_floating_point_v<DT>) {
            f.type  = Field::Type::Float;
            f.num.f = static_cast<float>(value);
        } else if constexpr (std::is_signed_v<DT> && std::is_integral_v<DT>) {
            f.type  = Field::Type::Signed;
            f.num.i = static_cast<int64_t>(value);
        } else if constexpr (std::is_unsigned_v<DT> && std::is_integral_v<DT>) {
            f.type  = Field::Type::Unsigned;
            f.num.u = static_cast<uint64_t>(value);
        } else {
            // const char* and other pointer/reference types → string.
            f.type = Field::Type::String;
        }

        return *this;
    }

    // ---------------------------------------------------------------------------
    // Output
    // ---------------------------------------------------------------------------

    /**
     * Transmit the frame in Serial Studio wire format.
     *
     * Output: `v1\tv2\t...\tvN\r\n`
     * Values are the pre-formatted strings produced by the format argument to
     * each field() call — no additional rounding or conversion is applied.
     */
    void sendSerial(Print& out) const;

    /**
     * Transmit only the fields whose formatted value has changed since @p prev.
     *
     * Output format (when output is triggered):
     *   `name=value  name=value  ...\r\n`
     * If nothing is emitted, no bytes are written (not even a line ending).
     *
     * Fields are compared by position index using their pre-formatted strings.
     * Fields present in this frame but absent in @p prev are always treated as
     * changed (i.e. the first call when @p prev is an empty FrameBuilder emits
     * every field).
     *
     * ── Passive fields ──────────────────────────────────────────────────────
     * @p passiveFields is an optional list of field names that will NOT trigger
     * output on their own.  If the only changed fields are passive, nothing is
     * written.  Once a non-passive field has changed (triggering output), all
     * changed fields — passive or not — are included in that line.
     *
     * Typical use: high-churn counters like "status.time_in_state" that change
     * every tick and would otherwise produce noise when nothing meaningful has
     * changed.
     *
     * @param out            Output sink (Serial, TCP client, etc.).
     * @param prev           Previous frame to diff against for change detection.
     * @param passiveFields  Array of field-name C-strings to treat as passive.
     *                       Pass nullptr (default) to disable passive filtering.
     * @param passiveCount   Number of entries in @p passiveFields (default 0).
     *
     * @note Only the serial output path is affected.  fillJson() / getLastFrame()
     *       always return the full frame regardless of delta mode.
     */
    void sendSerialDelta(Print& out, const FrameBuilder& prev,
                         const char* const* passiveFields = nullptr,
                         uint8_t            passiveCount  = 0) const;

    /**
     * Populate @p doc with one key/value pair per field.
     *
     * Numeric fields (Signed, Unsigned, Float) are written as JSON numbers.
     * String fields are written as JSON strings.
     * Any existing content in @p doc is cleared first.
     */
    void fillJson(JsonDocument& doc) const;

    // ---------------------------------------------------------------------------
    // Inspection
    // ---------------------------------------------------------------------------

    uint8_t      fieldCount()           const { return count_; }
    const Field& getField(uint8_t idx)  const { return fields_[idx]; }

private:
    Field   fields_[MAX_FIELDS];
    uint8_t count_;
};

#endif // FRAME_BUILDER_H
