/**
 * @file indicator.h
 * @brief FAULT and READY indicator control
 *
 * Drives the on-board WS2812 RGB LED (and optionally discrete digital LEDs
 * on FAULT_IND_PIN / READY_IND_PIN) according to the system state table:
 *
 *   State  | FAULT IND          | READY IND
 *   -------|--------------------|-----------------------
 *   0 Init | AMBER (momentary)  | AMBER (momentary)
 *   1 Idle | ON RED             | OFF
 *   2 Crse | Flash fast RED     | OFF
 *   3 Fine | Flash fast RED     | Flash slow GREEN
 *   4 Over | Flash fast RED     | Flash fast GREEN
 *   5 Sett | Flash fast RED     | Flash fast GREEN
 *   6 Base | OFF                | ON GREEN
 *   7 Oper | OFF                | ON GREEN
 *   8 Flt  | ON RED             | OFF
 *
 * Flash fast = 2 Hz (INDICATOR_FLASH_FAST_PERIOD_MS)
 * Flash slow = 1 Hz (INDICATOR_FLASH_SLOW_PERIOD_MS)
 *
 * All timing is non-blocking; call update() every loop.
 */

#ifndef INDICATOR_H
#define INDICATOR_H

#include <stdint.h>
#ifdef ARDUINO
#include <Arduino.h>
#endif
#include "module.h"

namespace indicator {

/** Single-indicator display modes. */
enum class Mode : uint8_t {
    Off,
    SolidRed,
    SolidGreen,
    SolidAmber,
    FlashFastRed,
    FlashSlowRed,
    FlashFastGreen,
    FlashSlowGreen,
};

/**
 * Initialize GPIO pins and the WS2812 driver.
 * Must be called once in setup().
 * @return MODULE_INIT_SUCCESS always.
 */
module::InitStatus init();

/**
 * Set the desired display mode for the FAULT indicator.
 */
void setFaultMode(Mode mode);

/**
 * Set the desired display mode for the READY indicator.
 */
void setReadyMode(Mode mode);

/**
 * Service the indicator state machine.
 * Must be called every loop iteration (non-blocking).
 *
 * @param nowMs  Current millis() value
 */
void update(uint32_t nowMs);

inline void update() { update(millis()); }

/**
 * Return true if the FAULT (red) LED is currently lit this tick.
 * Accounts for flash modes — returns the instantaneous on/off state.
 * Only valid after update() has been called for the current tick.
 */
bool isFaultOn();

/**
 * Return true if the READY (green) LED is currently lit this tick.
 * Accounts for flash modes — returns the instantaneous on/off state.
 * Only valid after update() has been called for the current tick.
 */
bool isReadyOn();

// ── Module interface ──────────────────────────────────────────────────────────
//
// update() requires a nowMs argument for accurate flash timing, so
// Module::service() samples millis() internally.
//
// Guarded by #ifdef ARDUINO because millis() is not available in native
// (host) unit-test builds.

#ifdef ARDUINO
struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = indicator::init(); }
    /** Calls indicator::update(millis()) — must be called every loop tick. */
    static module::ServiceStatus service() { indicator::update(millis()); return _serviceStatus = module::MODULE_SERVICE_OK; }
};

ASSERT_MODULE_INTERFACE(Module);
#endif // ARDUINO

} // namespace indicator

#endif // INDICATOR_H
