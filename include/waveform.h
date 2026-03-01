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

/**
 * Adjust the DDS output mode based on supply voltage.
 * @return SERVICE_OK always.
 */
module::ServiceStatus service();

float getFrequency();

void enable();

void disable();

bool isEnabled();

mode_t getWaveformMode();

float getRMSVoltage();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = waveform::init(); }
    static module::ServiceStatus service() { return _serviceStatus = waveform::service(); }
    static void enable()                   { waveform::enable(); }
    static void disable()                  { waveform::disable(); }
    static bool isEnabled()                { return waveform::isEnabled(); }

};

ASSERT_MODULE_INTERFACE(Module);

} // namespace waveform

#endif // WAVEFORM_H
