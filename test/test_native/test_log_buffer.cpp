/**
 * @file test_log_buffer.cpp
 * @brief Native unit tests for the log ring buffer and LogStream.
 *
 * Tests run on the host PC without any hardware dependencies.
 * millis() is provided by test/test_native/stubs/arduino_stub.cpp and can be
 * controlled via stub_setMillis().
 *
 * Run with:  pio test -e native
 */

#include <unity.h>
#include <cstring>
#include <ArduinoJson.h>
#include "logger.h"

// millis() stub control (provided by stubs/arduino_stub.cpp)
extern "C" void stub_setMillis(uint32_t ms);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Reset the ring buffer and millis() stub before each test. */
static void setUp_log() {
    logger::clear();
    stub_setMillis(0);
}

// ---------------------------------------------------------------------------
// logger::push / count
// ---------------------------------------------------------------------------

void test_lb_starts_empty(void) {
    setUp_log();
    TEST_ASSERT_EQUAL_UINT8(0, logger::count());
}

void test_lb_push_increments_count(void) {
    setUp_log();
    logger::push("hello\n");
    TEST_ASSERT_EQUAL_UINT8(1, logger::count());
    logger::push("world\n");
    TEST_ASSERT_EQUAL_UINT8(2, logger::count());
}

void test_lb_push_stores_text(void) {
    setUp_log();
    logger::push("hello\n");
    TEST_ASSERT_EQUAL_STRING("hello\n", logger::get(0).text);
}

void test_lb_push_stores_timestamp(void) {
    setUp_log();
    stub_setMillis(12345);
    logger::push("ts test\n");
    TEST_ASSERT_EQUAL_UINT32(12345, logger::get(0).ms);
}

void test_lb_push_stores_epoch(void) {
    setUp_log();
    logger::push("epoch test\n");
    // The native time() call returns the host clock (well past the Unix epoch).
    // We just verify it was captured and is a plausible positive value rather
    // than zero / uninitialized.
    TEST_ASSERT_GREATER_THAN(static_cast<int64_t>(0), logger::get(0).epoch);
}

void test_lb_push_with_len(void) {
    setUp_log();
    // Push 5 chars of "hello world" — should store only "hello"
    logger::push("hello world", 5);
    TEST_ASSERT_EQUAL_STRING("hello", logger::get(0).text);
}

// ---------------------------------------------------------------------------
// logger::get — oldest-first ordering
// ---------------------------------------------------------------------------

void test_lb_get_oldest_is_index_0(void) {
    setUp_log();
    logger::push("first\n");
    logger::push("second\n");
    TEST_ASSERT_EQUAL_STRING("first\n",  logger::get(0).text);
    TEST_ASSERT_EQUAL_STRING("second\n", logger::get(1).text);
}

// ---------------------------------------------------------------------------
// logger::clear
// ---------------------------------------------------------------------------

void test_lb_clear_resets_count(void) {
    setUp_log();
    logger::push("a\n");
    logger::push("b\n");
    logger::clear();
    TEST_ASSERT_EQUAL_UINT8(0, logger::count());
}

void test_lb_clear_then_push_works(void) {
    setUp_log();
    logger::push("old\n");
    logger::clear();
    logger::push("new\n");
    TEST_ASSERT_EQUAL_UINT8(1, logger::count());
    TEST_ASSERT_EQUAL_STRING("new\n", logger::get(0).text);
}

// ---------------------------------------------------------------------------
// Capacity / ring wrap-around
// ---------------------------------------------------------------------------

void test_lb_count_does_not_exceed_capacity(void) {
    setUp_log();
    // Push more than CAPACITY entries
    for (uint16_t i = 0; i < static_cast<uint16_t>(logger::CAPACITY) + 10u; ++i) {
        logger::push("x\n");
    }
    TEST_ASSERT_EQUAL_UINT8(logger::CAPACITY, logger::count());
}

void test_lb_oldest_overwritten_when_full(void) {
    setUp_log();

    // Fill the buffer completely.
    for (uint8_t i = 0; i < logger::CAPACITY; ++i) {
        char msg[8];
        snprintf(msg, sizeof(msg), "m%03u\n", static_cast<unsigned>(i));
        logger::push(msg);
    }
    // Verify index 0 (oldest) is "m000\n".
    TEST_ASSERT_EQUAL_STRING("m000\n", logger::get(0).text);

    // Push one more — this overwrites the oldest ("m000\n").
    logger::push("new\n");

    // Now the oldest should be "m001\n".
    TEST_ASSERT_EQUAL_STRING("m001\n", logger::get(0).text);

    // The newest (index count-1) should be "new\n".
    const uint8_t last = static_cast<uint8_t>(logger::count() - 1u);
    TEST_ASSERT_EQUAL_STRING("new\n", logger::get(last).text);
}

// ---------------------------------------------------------------------------
// Long-line truncation
// ---------------------------------------------------------------------------

void test_lb_long_line_truncated_to_max(void) {
    setUp_log();

    // Build a string longer than MAX_MSG_LEN.
    char long_msg[logger::MAX_MSG_LEN + 32];
    memset(long_msg, 'A', sizeof(long_msg) - 1);
    long_msg[sizeof(long_msg) - 1] = '\0';

    logger::push(long_msg);
    TEST_ASSERT_EQUAL_UINT8(1, logger::count());

    const char* stored = logger::get(0).text;
    // Stored length must be strictly less than MAX_MSG_LEN (room for '\0').
    TEST_ASSERT_LESS_THAN_UINT(logger::MAX_MSG_LEN,
                               static_cast<unsigned>(strlen(stored)) + 1u);
}

// ---------------------------------------------------------------------------
// fillJson
// ---------------------------------------------------------------------------

void test_lb_fillJson_empty(void) {
    setUp_log();

    JsonDocument doc;
    JsonArray arr = doc["log"].to<JsonArray>();
    logger::fillJson(arr);

    TEST_ASSERT_EQUAL(0, static_cast<int>(arr.size()));
}

void test_lb_fillJson_all_entries(void) {
    setUp_log();

    stub_setMillis(100);
    logger::push("line1\n");
    stub_setMillis(200);
    logger::push("line2\n");

    JsonDocument doc;
    JsonArray arr = doc["log"].to<JsonArray>();
    logger::fillJson(arr);   // maxEntries = 0 → include all

    TEST_ASSERT_EQUAL(2, static_cast<int>(arr.size()));

    TEST_ASSERT_EQUAL_UINT32(100, arr[0]["ms"].as<uint32_t>());
    TEST_ASSERT_EQUAL_STRING("line1\n", arr[0]["text"].as<const char*>());
    TEST_ASSERT_TRUE(arr[0]["epoch"].as<int64_t>() > 0); // epoch key present and plausible

    TEST_ASSERT_EQUAL_UINT32(200, arr[1]["ms"].as<uint32_t>());
    TEST_ASSERT_EQUAL_STRING("line2\n", arr[1]["text"].as<const char*>());
}

void test_lb_fillJson_respects_maxEntries(void) {
    setUp_log();

    logger::push("a\n");
    logger::push("b\n");
    logger::push("c\n");
    logger::push("d\n");

    JsonDocument doc;
    JsonArray arr = doc["log"].to<JsonArray>();
    logger::fillJson(arr, 2);   // keep only the 2 most-recent

    TEST_ASSERT_EQUAL(2, static_cast<int>(arr.size()));
    // Most recent 2 entries are "c\n" and "d\n".
    TEST_ASSERT_EQUAL_STRING("c\n", arr[0]["text"].as<const char*>());
    TEST_ASSERT_EQUAL_STRING("d\n", arr[1]["text"].as<const char*>());
}

// ---------------------------------------------------------------------------
// LogStream — line buffering
// ---------------------------------------------------------------------------

void test_logstream_single_line_stored(void) {
    setUp_log();

    Log.print("hello\n");

    TEST_ASSERT_EQUAL_UINT8(1, logger::count());
    TEST_ASSERT_EQUAL_STRING("hello\n", logger::get(0).text);
}

void test_logstream_println_stored(void) {
    setUp_log();

    Log.println("world");   // println appends '\n'

    TEST_ASSERT_EQUAL_UINT8(1, logger::count());
    TEST_ASSERT_EQUAL_STRING("world\n", logger::get(0).text);
}

void test_logstream_two_lines_two_entries(void) {
    setUp_log();

    Log.print("line1\nline2\n");

    TEST_ASSERT_EQUAL_UINT8(2, logger::count());
    TEST_ASSERT_EQUAL_STRING("line1\n", logger::get(0).text);
    TEST_ASSERT_EQUAL_STRING("line2\n", logger::get(1).text);
}

void test_logstream_partial_line_not_flushed(void) {
    setUp_log();

    // No trailing '\n' — should not be stored yet.
    Log.print("partial");
    TEST_ASSERT_EQUAL_UINT8(0, logger::count());

    // Adding '\n' flushes it.
    Log.print("\n");
    TEST_ASSERT_EQUAL_UINT8(1, logger::count());
    TEST_ASSERT_EQUAL_STRING("partial\n", logger::get(0).text);
}

void test_logstream_multiple_partial_writes_coalesced(void) {
    setUp_log();

    Log.print("hel");
    Log.print("lo");
    Log.print("\n");

    TEST_ASSERT_EQUAL_UINT8(1, logger::count());
    TEST_ASSERT_EQUAL_STRING("hello\n", logger::get(0).text);
}

void test_logstream_long_line_truncated(void) {
    setUp_log();

    // Write a line that exceeds MAX_MSG_LEN without a '\n' until the end.
    for (uint16_t i = 0; i < static_cast<uint16_t>(logger::MAX_MSG_LEN) + 20u; ++i) {
        Log.write(static_cast<uint8_t>('B'));
    }
    // Force flush by sending '\n'.
    Log.print("\n");

    TEST_ASSERT_EQUAL_UINT8(1, logger::count());
    const char* stored = logger::get(0).text;
    TEST_ASSERT_LESS_THAN_UINT(logger::MAX_MSG_LEN,
                               static_cast<unsigned>(strlen(stored)) + 1u);
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

void run_log_tests() {
    // ring buffer — push / count
    RUN_TEST(test_lb_starts_empty);
    RUN_TEST(test_lb_push_increments_count);
    RUN_TEST(test_lb_push_stores_text);
    RUN_TEST(test_lb_push_stores_timestamp);
    RUN_TEST(test_lb_push_stores_epoch);
    RUN_TEST(test_lb_push_with_len);

    // ring buffer — get / ordering
    RUN_TEST(test_lb_get_oldest_is_index_0);

    // ring buffer — clear
    RUN_TEST(test_lb_clear_resets_count);
    RUN_TEST(test_lb_clear_then_push_works);

    // ring buffer — capacity / wrap-around
    RUN_TEST(test_lb_count_does_not_exceed_capacity);
    RUN_TEST(test_lb_oldest_overwritten_when_full);

    // ring buffer — truncation
    RUN_TEST(test_lb_long_line_truncated_to_max);

    // ring buffer — fillJson
    RUN_TEST(test_lb_fillJson_empty);
    RUN_TEST(test_lb_fillJson_all_entries);
    RUN_TEST(test_lb_fillJson_respects_maxEntries);

    // LogStream
    RUN_TEST(test_logstream_single_line_stored);
    RUN_TEST(test_logstream_println_stored);
    RUN_TEST(test_logstream_two_lines_two_entries);
    RUN_TEST(test_logstream_partial_line_not_flushed);
    RUN_TEST(test_logstream_multiple_partial_writes_coalesced);
    RUN_TEST(test_logstream_long_line_truncated);
}
