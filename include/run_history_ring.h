/**
 * @file run_history_ring.h
 * @brief Fixed-capacity ring of run recorder samples, addressed by sequence number.
 *
 * Pure logic with no Arduino or ESP-IDF calls, so the native tests can drive it
 * with a plain array. The run recorder owns the PSRAM storage and the lock.
 */

#ifndef RUN_HISTORY_RING_H
#define RUN_HISTORY_RING_H

#include <cstddef>
#include <cstdint>

namespace run_history {

/// Channels per sample; the run recorder's channel table must match.
static constexpr size_t CHANNEL_COUNT = 19;

/// One recorded sample. NaN in @c values marks a channel with no valid reading.
struct Sample {
    uint32_t seq;                     ///< Sample number since boot
    uint32_t uptimeMs;                ///< Device uptime when sampled
    int8_t   stateId;                 ///< FSM state id (Off is -1)
    float    values[CHANNEL_COUNT];   ///< Channel readings, recorder table order
};

/**
 * Ring buffer that keeps the newest @c capacity samples.
 *
 * Every push gets the next sequence number. Readers ask for a sample by
 * sequence number and get @c false once it has been overwritten.
 *
 * @code
 * run_history::Sample storage[4];
 * run_history::Ring ring;
 * ring.attach(storage, 4);
 * ring.push(1000, 1, values);   // seq 0
 * run_history::Sample sample;
 * ring.copyAt(0, sample);       // true
 * @endcode
 */
class Ring {
public:
    /**
     * Use @p storage for @p capacity samples and clear the ring.
     * @param storage   Caller-owned array of at least @p capacity samples.
     * @param capacity  Number of samples kept before the oldest is overwritten.
     */
    void attach(Sample* storage, uint32_t capacity);

    /** @return true once attach() has been given storage. */
    bool isAttached() const { return storage_ != nullptr && capacity_ > 0; }

    /**
     * Append a sample, overwriting the oldest when full.
     * @param uptimeMs  Device uptime when sampled.
     * @param stateId   FSM state id.
     * @param values    CHANNEL_COUNT readings.
     * @return The new sample's sequence number.
     */
    uint32_t push(uint32_t uptimeMs, int8_t stateId, const float* values);

    /** @return Sequence number of the oldest sample still held (== endSeq() when empty). */
    uint32_t oldestSeq() const;

    /** @return Sequence number the next push() will get. */
    uint32_t endSeq() const { return endSeq_; }

    /**
     * Copy the sample with sequence number @p seq.
     * @param seq  Sequence number to read.
     * @param out  Receives the sample.
     * @return false if @p seq was overwritten or hasn't been written yet.
     */
    bool copyAt(uint32_t seq, Sample& out) const;

private:
    Sample*  storage_  = nullptr;
    uint32_t capacity_ = 0;
    uint32_t endSeq_   = 0;
};

} // namespace run_history

#endif // RUN_HISTORY_RING_H
