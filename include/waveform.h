/**
 * @file waveform.h
 * @brief AD9833 DDS waveform generator interface
 *
 * Manages the AD9833 sine-wave output only.
 * LED / indicator control has moved to indicator.h.
 */

#ifndef WAVEFORM_H
#define WAVEFORM_H

#include "module.h"

namespace waveform {

/**
 * Initialize the AD9833 and begin generating the configured sine wave.
 * @return MODULE_INIT_SUCCESS always (the AD9833 has no readable ID register
 *         to confirm presence; the waveform output is the implicit check).
 */
module::InitStatus init();

void service();

int16_t getStatus();

float getFrequency();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return waveform::init(); }
    static void service()            { waveform::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace waveform

#endif // WAVEFORM_H
