/**
 * @file test_run_history_ring.cpp
 * @brief Native unit tests for the run recorder's sample ring.
 *
 * Run with:  pio test -e native
 */

#include <unity.h>
#include "run_history_ring.h"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static constexpr uint32_t TEST_CAPACITY = 4;
static run_history::Sample sStorage[TEST_CAPACITY];

/** Values whose first channel encodes @p marker so samples can be told apart. */
static void fillValues(float* values, float marker) {
    for (size_t index = 0; index < run_history::CHANNEL_COUNT; ++index) {
        values[index] = marker + static_cast<float>(index) * 0.5f;
    }
}

/** Push @p count samples with uptime seq*1000 and first value seq. */
static void pushSamples(run_history::Ring& ring, uint32_t count) {
    float values[run_history::CHANNEL_COUNT];
    for (uint32_t index = 0; index < count; ++index) {
        const uint32_t seq = ring.endSeq();
        fillValues(values, static_cast<float>(seq));
        ring.push(seq * 1000u, static_cast<int8_t>(seq % 3), values);
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void test_rhr_unattached_has_nothing(void) {
    run_history::Ring ring;
    run_history::Sample sample{};
    TEST_ASSERT_FALSE(ring.isAttached());
    TEST_ASSERT_FALSE(ring.copyAt(0, sample));
}

void test_rhr_starts_empty(void) {
    run_history::Ring ring;
    ring.attach(sStorage, TEST_CAPACITY);
    run_history::Sample sample{};
    TEST_ASSERT_TRUE(ring.isAttached());
    TEST_ASSERT_EQUAL_UINT32(0, ring.oldestSeq());
    TEST_ASSERT_EQUAL_UINT32(0, ring.endSeq());
    TEST_ASSERT_FALSE(ring.copyAt(0, sample));
}

void test_rhr_push_returns_sequential_seq(void) {
    run_history::Ring ring;
    ring.attach(sStorage, TEST_CAPACITY);
    float values[run_history::CHANNEL_COUNT];
    fillValues(values, 0.0f);
    TEST_ASSERT_EQUAL_UINT32(0, ring.push(10, 1, values));
    TEST_ASSERT_EQUAL_UINT32(1, ring.push(20, 1, values));
    TEST_ASSERT_EQUAL_UINT32(2, ring.endSeq());
}

void test_rhr_copy_returns_stored_fields(void) {
    run_history::Ring ring;
    ring.attach(sStorage, TEST_CAPACITY);
    pushSamples(ring, 3);
    run_history::Sample sample{};
    TEST_ASSERT_TRUE(ring.copyAt(2, sample));
    TEST_ASSERT_EQUAL_UINT32(2, sample.seq);
    TEST_ASSERT_EQUAL_UINT32(2000, sample.uptimeMs);
    TEST_ASSERT_EQUAL_INT8(2, sample.stateId);
    TEST_ASSERT_EQUAL_FLOAT(2.0f, sample.values[0]);
    TEST_ASSERT_EQUAL_FLOAT(2.0f + 18 * 0.5f, sample.values[run_history::CHANNEL_COUNT - 1]);
}

void test_rhr_copy_past_end_fails(void) {
    run_history::Ring ring;
    ring.attach(sStorage, TEST_CAPACITY);
    pushSamples(ring, 2);
    run_history::Sample sample{};
    TEST_ASSERT_FALSE(ring.copyAt(2, sample));
    TEST_ASSERT_FALSE(ring.copyAt(100, sample));
}

void test_rhr_wrap_drops_oldest(void) {
    run_history::Ring ring;
    ring.attach(sStorage, TEST_CAPACITY);
    pushSamples(ring, TEST_CAPACITY + 2);
    run_history::Sample sample{};
    TEST_ASSERT_EQUAL_UINT32(2, ring.oldestSeq());
    TEST_ASSERT_EQUAL_UINT32(TEST_CAPACITY + 2, ring.endSeq());
    TEST_ASSERT_FALSE(ring.copyAt(1, sample));   // overwritten
    TEST_ASSERT_TRUE(ring.copyAt(2, sample));
    TEST_ASSERT_EQUAL_UINT32(2, sample.seq);
    TEST_ASSERT_EQUAL_FLOAT(2.0f, sample.values[0]);
    TEST_ASSERT_TRUE(ring.copyAt(TEST_CAPACITY + 1, sample));
    TEST_ASSERT_EQUAL_UINT32(TEST_CAPACITY + 1, sample.seq);
    TEST_ASSERT_EQUAL_UINT32((TEST_CAPACITY + 1) * 1000u, sample.uptimeMs);
}

void test_rhr_attach_clears(void) {
    run_history::Ring ring;
    ring.attach(sStorage, TEST_CAPACITY);
    pushSamples(ring, 3);
    ring.attach(sStorage, TEST_CAPACITY);
    run_history::Sample sample{};
    TEST_ASSERT_EQUAL_UINT32(0, ring.endSeq());
    TEST_ASSERT_FALSE(ring.copyAt(0, sample));
}

void run_run_history_ring_tests() {
    RUN_TEST(test_rhr_unattached_has_nothing);
    RUN_TEST(test_rhr_starts_empty);
    RUN_TEST(test_rhr_push_returns_sequential_seq);
    RUN_TEST(test_rhr_copy_returns_stored_fields);
    RUN_TEST(test_rhr_copy_past_end_fails);
    RUN_TEST(test_rhr_wrap_drops_oldest);
    RUN_TEST(test_rhr_attach_clears);
}
