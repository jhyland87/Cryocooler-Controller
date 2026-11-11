/**
 * @file run_history_ring.cpp
 * @brief Fixed-capacity ring of run recorder samples.
 */

#include "run_history_ring.h"

#include <cstring>

namespace run_history {

void Ring::attach(Sample* storage, uint32_t capacity) {
    storage_  = storage;
    capacity_ = capacity;
    endSeq_   = 0;
}

uint32_t Ring::push(uint32_t uptimeMs, int8_t stateId, const float* values) {
    const uint32_t seq = endSeq_;
    Sample& slot  = storage_[seq % capacity_];
    slot.seq      = seq;
    slot.uptimeMs = uptimeMs;
    slot.stateId  = stateId;
    memcpy(slot.values, values, sizeof(slot.values));
    ++endSeq_;
    return seq;
}

uint32_t Ring::oldestSeq() const {
    return endSeq_ > capacity_ ? endSeq_ - capacity_ : 0;
}

bool Ring::copyAt(uint32_t seq, Sample& out) const {
    if (!isAttached()) return false;
    if (seq < oldestSeq() || seq >= endSeq_) return false;
    out = storage_[seq % capacity_];
    return true;
}

} // namespace run_history
