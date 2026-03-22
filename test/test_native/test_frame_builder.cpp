/**
 * @file test_frame_builder.cpp
 * @brief Native unit tests for FrameBuilder.
 *
 * Verifies field accumulation, type detection, serial output format, and JSON
 * output correctness without any hardware dependencies.
 *
 * This file has no main().  It exposes run_frame_builder_tests() which is
 * called from test_state_machine.cpp::main() so that all native tests share
 * a single test binary.
 *
 * Run with:  pio test -e native
 */

#include <unity.h>
#include <cstring>
#include <ArduinoJson.h>
#include "Print.h"           // native stub — provides the Print class
#include "frame_builder.h"

// ---------------------------------------------------------------------------
// Construction and reset
// ---------------------------------------------------------------------------

void test_fb_starts_empty(void) {
    FrameBuilder fb;
    TEST_ASSERT_EQUAL_UINT8(0, fb.fieldCount());
}

void test_fb_field_increments_count(void) {
    FrameBuilder fb;
    fb.field("a", "%d", static_cast<int>(1));
    TEST_ASSERT_EQUAL_UINT8(1, fb.fieldCount());
    fb.field("b", "%d", static_cast<int>(2));
    TEST_ASSERT_EQUAL_UINT8(2, fb.fieldCount());
}

void test_fb_reset_clears_count(void) {
    FrameBuilder fb;
    fb.field("a", "%d", static_cast<int>(42))
      .field("b", "%d", static_cast<int>(7));
    fb.reset();
    TEST_ASSERT_EQUAL_UINT8(0, fb.fieldCount());
}

void test_fb_max_fields_not_exceeded(void) {
    FrameBuilder fb;
    // Add more fields than MAX_FIELDS — count must not exceed MAX_FIELDS.
    for (uint8_t i = 0; i < FrameBuilder::MAX_FIELDS + 5u; ++i) {
        fb.field("x", "%d", static_cast<int>(i));
    }
    TEST_ASSERT_EQUAL_UINT8(FrameBuilder::MAX_FIELDS, fb.fieldCount());
}

// ---------------------------------------------------------------------------
// Field name storage
// ---------------------------------------------------------------------------

void test_fb_field_name_stored(void) {
    FrameBuilder fb;
    fb.field("temperature", "%.2f", 23.5f);
    TEST_ASSERT_EQUAL_STRING("temperature", fb.getField(0).name);
}

void test_fb_multiple_names_stored(void) {
    FrameBuilder fb;
    fb.field("alpha", "%d", static_cast<int>(1))
      .field("beta",  "%d", static_cast<int>(2))
      .field("gamma", "%d", static_cast<int>(3));
    TEST_ASSERT_EQUAL_STRING("alpha", fb.getField(0).name);
    TEST_ASSERT_EQUAL_STRING("beta",  fb.getField(1).name);
    TEST_ASSERT_EQUAL_STRING("gamma", fb.getField(2).name);
}

// ---------------------------------------------------------------------------
// Type detection
// ---------------------------------------------------------------------------

void test_fb_float_type(void) {
    FrameBuilder fb;
    fb.field("val", "%.1f", 3.14f);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Float),
                      static_cast<uint8_t>(fb.getField(0).type));
}

void test_fb_double_type(void) {
    FrameBuilder fb;
    fb.field("val", "%.1f", 3.14);   // double literal
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Float),
                      static_cast<uint8_t>(fb.getField(0).type));
}

void test_fb_signed_int_type(void) {
    FrameBuilder fb;
    fb.field("val", "%d", static_cast<int>(-5));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Signed),
                      static_cast<uint8_t>(fb.getField(0).type));
}

void test_fb_int8_type(void) {
    FrameBuilder fb;
    fb.field("val", "%d", static_cast<int8_t>(-100));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Signed),
                      static_cast<uint8_t>(fb.getField(0).type));
}

void test_fb_unsigned_int_type(void) {
    FrameBuilder fb;
    fb.field("val", "%u", static_cast<uint32_t>(42u));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Unsigned),
                      static_cast<uint8_t>(fb.getField(0).type));
}

void test_fb_uint8_type(void) {
    FrameBuilder fb;
    fb.field("val", "%u", static_cast<uint8_t>(255u));
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Unsigned),
                      static_cast<uint8_t>(fb.getField(0).type));
}

void test_fb_bool_true_is_unsigned_one(void) {
    FrameBuilder fb;
    fb.field("flag", "%d", true);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Unsigned),
                      static_cast<uint8_t>(fb.getField(0).type));
    TEST_ASSERT_EQUAL_UINT64(1u, fb.getField(0).num.u);
}

void test_fb_bool_false_is_unsigned_zero(void) {
    FrameBuilder fb;
    fb.field("flag", "%d", false);
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::Unsigned),
                      static_cast<uint8_t>(fb.getField(0).type));
    TEST_ASSERT_EQUAL_UINT64(0u, fb.getField(0).num.u);
}

void test_fb_const_char_ptr_is_string(void) {
    FrameBuilder fb;
    fb.field("label", "%s", "Running");
    TEST_ASSERT_EQUAL(static_cast<uint8_t>(FrameBuilder::Field::Type::String),
                      static_cast<uint8_t>(fb.getField(0).type));
}

// ---------------------------------------------------------------------------
// Numeric value storage
// ---------------------------------------------------------------------------

void test_fb_float_value_stored(void) {
    FrameBuilder fb;
    fb.field("v", "%f", 1.5f);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.5f, fb.getField(0).num.f);
}

void test_fb_negative_float_stored(void) {
    FrameBuilder fb;
    fb.field("v", "%f", -273.15f);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, -273.15f, fb.getField(0).num.f);
}

void test_fb_signed_value_stored(void) {
    FrameBuilder fb;
    fb.field("v", "%d", static_cast<int>(-42));
    TEST_ASSERT_EQUAL_INT64(-42, fb.getField(0).num.i);
}

void test_fb_unsigned_value_stored(void) {
    FrameBuilder fb;
    fb.field("v", "%u", static_cast<uint32_t>(4095u));
    TEST_ASSERT_EQUAL_UINT64(4095u, fb.getField(0).num.u);
}

// ---------------------------------------------------------------------------
// Formatted string (str[] in Field, consumed by sendSerial)
// ---------------------------------------------------------------------------

void test_fb_format_string_applied_float(void) {
    FrameBuilder fb;
    fb.field("temp", "%.2f", 23.456f);
    TEST_ASSERT_EQUAL_STRING("23.46", fb.getField(0).str);
}

void test_fb_format_string_applied_padded_int(void) {
    FrameBuilder fb;
    fb.field("count", "%05d", static_cast<int>(7));
    TEST_ASSERT_EQUAL_STRING("00007", fb.getField(0).str);
}

void test_fb_format_string_applied_string(void) {
    FrameBuilder fb;
    fb.field("label", "%s", "Hello");
    TEST_ASSERT_EQUAL_STRING("Hello", fb.getField(0).str);
}

// ---------------------------------------------------------------------------
// sendSerial
// ---------------------------------------------------------------------------

void test_fb_serial_empty_frame(void) {
    FrameBuilder fb;
    Print p;
    fb.sendSerial(p);
    TEST_ASSERT_EQUAL_STRING("\r\n", p.str());
}

void test_fb_serial_single_field(void) {
    FrameBuilder fb;
    Print p;
    fb.field("n", "%d", static_cast<int>(42));
    fb.sendSerial(p);
    TEST_ASSERT_EQUAL_STRING("42\r\n", p.str());
}

void test_fb_serial_multiple_fields_tab_separated(void) {
    FrameBuilder fb;
    Print p;
    fb.field("a", "%d", static_cast<int>(1))
      .field("b", "%d", static_cast<int>(2))
      .field("c", "%d", static_cast<int>(3));
    fb.sendSerial(p);
    TEST_ASSERT_EQUAL_STRING("1\t2\t3\r\n", p.str());
}

void test_fb_serial_ends_with_crlf(void) {
    FrameBuilder fb;
    Print p;
    fb.field("x", "%d", static_cast<int>(99));
    fb.sendSerial(p);
    TEST_ASSERT_TRUE(p.contains("\r\n"));
}

void test_fb_serial_no_leading_tab(void) {
    // First field must not be preceded by a tab
    FrameBuilder fb;
    Print p;
    fb.field("x", "%d", static_cast<int>(5));
    fb.sendSerial(p);
    TEST_ASSERT_EQUAL('5', p.str()[0]);
}

void test_fb_serial_after_reset(void) {
    // After reset(), a new frame should emit the correct output.
    FrameBuilder fb;
    Print p;
    fb.field("old", "%d", static_cast<int>(9));
    fb.reset();
    fb.field("new_", "%d", static_cast<int>(7));
    fb.sendSerial(p);
    TEST_ASSERT_EQUAL_STRING("7\r\n", p.str());
}

// ---------------------------------------------------------------------------
// fillJson
// ---------------------------------------------------------------------------

void test_fb_json_empty_frame_is_empty_object(void) {
    FrameBuilder fb;
    JsonDocument doc;
    doc["old"] = 1;   // pre-populate to verify clear()
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL(0, doc.size());
}

void test_fb_json_float_field_stored_as_number(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("temp_c", "%.2f", 25.0f);
    fb.fillJson(doc);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 25.0f, doc["temp_c"].as<float>());
}

void test_fb_json_signed_field_stored_as_number(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("state", "%d", static_cast<int>(-3));
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL_INT(-3, doc["state"].as<int>());
}

void test_fb_json_unsigned_field_stored_as_number(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("dac", "%u", static_cast<uint16_t>(4095u));
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL_UINT32(4095u, doc["dac"].as<uint32_t>());
}

void test_fb_json_string_field_stored_as_string(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("label", "%s", "Running");
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL_STRING("Running", doc["label"].as<const char*>());
}

void test_fb_json_all_fields_present(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("int_v",   "%d",   static_cast<int>(1))
      .field("float_v", "%.1f", 2.0f)
      .field("str_v",   "%s",   "hi");
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL(3, doc.size());
    TEST_ASSERT_EQUAL_INT(1, doc["int_v"].as<int>());
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 2.0f, doc["float_v"].as<float>());
    TEST_ASSERT_EQUAL_STRING("hi", doc["str_v"].as<const char*>());
}

void test_fb_json_clears_previous_content(void) {
    FrameBuilder fb;
    JsonDocument doc;
    doc["stale"] = 999;
    TEST_ASSERT_EQUAL(1, doc.size());   // sanity check
    fb.field("fresh", "%d", static_cast<int>(1));
    fb.fillJson(doc);
    // Only "fresh" should remain — "stale" must be gone.
    TEST_ASSERT_EQUAL(1, doc.size());
    TEST_ASSERT_EQUAL_INT(1, doc["fresh"].as<int>());
}

void test_fb_json_bool_stored_as_zero_or_one(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("on",  "%d", true);
    fb.field("off", "%d", false);
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL_UINT32(1u, doc["on"].as<uint32_t>());
    TEST_ASSERT_EQUAL_UINT32(0u, doc["off"].as<uint32_t>());
}

// ---------------------------------------------------------------------------
// Fluent chaining
// ---------------------------------------------------------------------------

void test_fb_chaining_returns_same_object(void) {
    FrameBuilder fb;
    FrameBuilder& ref = fb.field("a", "%d", static_cast<int>(1))
                           .field("b", "%d", static_cast<int>(2));
    TEST_ASSERT_EQUAL_PTR(&fb, &ref);
    TEST_ASSERT_EQUAL_UINT8(2, fb.fieldCount());
}

// ---------------------------------------------------------------------------
// fillJson — dotted key names produce nested objects
// ---------------------------------------------------------------------------

void test_fb_json_dotted_two_levels(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("foo.bar", "%d", static_cast<int>(42));
    fb.fillJson(doc);
    TEST_ASSERT_TRUE(doc["foo"].is<JsonObject>());
    TEST_ASSERT_EQUAL_INT(42, doc["foo"]["bar"].as<int>());
}

void test_fb_json_dotted_three_levels(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("a.b.c", "%.1f", 1.5f);
    fb.fillJson(doc);
    TEST_ASSERT_TRUE(doc["a"].is<JsonObject>());
    TEST_ASSERT_TRUE(doc["a"]["b"].is<JsonObject>());
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 1.5f, doc["a"]["b"]["c"].as<float>());
}

void test_fb_json_dotted_shared_parent_reused(void) {
    // "foo.bar" and "foo.baz" must share one "foo" object, not create two.
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("foo.bar", "%d", static_cast<int>(1))
      .field("foo.baz", "%d", static_cast<int>(2));
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL(1, doc.size());   // one top-level key: "foo"
    TEST_ASSERT_EQUAL_INT(1, doc["foo"]["bar"].as<int>());
    TEST_ASSERT_EQUAL_INT(2, doc["foo"]["baz"].as<int>());
}

void test_fb_json_dotted_and_flat_coexist(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("flat",    "%d",   static_cast<int>(10))
      .field("grp.val", "%.1f", 3.0f);
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL(2, doc.size());   // "flat" and "grp"
    TEST_ASSERT_EQUAL_INT(10, doc["flat"].as<int>());
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 3.0f, doc["grp"]["val"].as<float>());
}

void test_fb_json_dotted_string_value(void) {
    FrameBuilder fb;
    JsonDocument doc;
    fb.field("status.text", "%s", "Running");
    fb.fillJson(doc);
    TEST_ASSERT_EQUAL_STRING("Running", doc["status"]["text"].as<const char*>());
}

void test_fb_serial_dotted_name_unaffected(void) {
    // sendSerial emits only the formatted value; dots in the name are irrelevant.
    FrameBuilder fb;
    Print p;
    fb.field("foo.bar", "%d", static_cast<int>(7));
    fb.sendSerial(p);
    TEST_ASSERT_EQUAL_STRING("7\r\n", p.str());
}

// ---------------------------------------------------------------------------
// Entry point — called from test_state_machine.cpp::main()
// ---------------------------------------------------------------------------

void run_frame_builder_tests() {
    // Construction / reset
    RUN_TEST(test_fb_starts_empty);
    RUN_TEST(test_fb_field_increments_count);
    RUN_TEST(test_fb_reset_clears_count);
    RUN_TEST(test_fb_max_fields_not_exceeded);

    // Field name storage
    RUN_TEST(test_fb_field_name_stored);
    RUN_TEST(test_fb_multiple_names_stored);

    // Type detection
    RUN_TEST(test_fb_float_type);
    RUN_TEST(test_fb_double_type);
    RUN_TEST(test_fb_signed_int_type);
    RUN_TEST(test_fb_int8_type);
    RUN_TEST(test_fb_unsigned_int_type);
    RUN_TEST(test_fb_uint8_type);
    RUN_TEST(test_fb_bool_true_is_unsigned_one);
    RUN_TEST(test_fb_bool_false_is_unsigned_zero);
    RUN_TEST(test_fb_const_char_ptr_is_string);

    // Numeric value storage
    RUN_TEST(test_fb_float_value_stored);
    RUN_TEST(test_fb_negative_float_stored);
    RUN_TEST(test_fb_signed_value_stored);
    RUN_TEST(test_fb_unsigned_value_stored);

    // Formatted string
    RUN_TEST(test_fb_format_string_applied_float);
    RUN_TEST(test_fb_format_string_applied_padded_int);
    RUN_TEST(test_fb_format_string_applied_string);

    // sendSerial
    RUN_TEST(test_fb_serial_empty_frame);
    RUN_TEST(test_fb_serial_single_field);
    RUN_TEST(test_fb_serial_multiple_fields_tab_separated);
    RUN_TEST(test_fb_serial_ends_with_crlf);
    RUN_TEST(test_fb_serial_no_leading_tab);
    RUN_TEST(test_fb_serial_after_reset);

    // fillJson — flat keys
    RUN_TEST(test_fb_json_empty_frame_is_empty_object);
    RUN_TEST(test_fb_json_float_field_stored_as_number);
    RUN_TEST(test_fb_json_signed_field_stored_as_number);
    RUN_TEST(test_fb_json_unsigned_field_stored_as_number);
    RUN_TEST(test_fb_json_string_field_stored_as_string);
    RUN_TEST(test_fb_json_all_fields_present);
    RUN_TEST(test_fb_json_clears_previous_content);
    RUN_TEST(test_fb_json_bool_stored_as_zero_or_one);

    // fillJson — dotted key names (nested objects)
    RUN_TEST(test_fb_json_dotted_two_levels);
    RUN_TEST(test_fb_json_dotted_three_levels);
    RUN_TEST(test_fb_json_dotted_shared_parent_reused);
    RUN_TEST(test_fb_json_dotted_and_flat_coexist);
    RUN_TEST(test_fb_json_dotted_string_value);
    RUN_TEST(test_fb_serial_dotted_name_unaffected);

    // Chaining
    RUN_TEST(test_fb_chaining_returns_same_object);
}
