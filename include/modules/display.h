/**
 * @file display.h
 * @brief Status screen on the Phoenix 2.4" touch display (ST7789V, 320 x 240).
 *
 * The display sits in the lid of the UCS 125-87-F-GD-D2,4 housing and hangs
 * off the shared SPI bus (CS from the decoder, D/C GPIO48, RESET GPIO46; 4-wire SPI
 * half duplex, so it never drives MISO). Its backlight is switched by the
 * MCP23S08 expander pin GP4. This first version only prints a few status lines;
 * touch positions are not read from the TSC2046 yet, only its pen-down flag.
 */

#ifndef DISPLAY_H
#define DISPLAY_H

#include "module.h"

namespace display {

/**
 * Reset and initialise the ST7789V with the Phoenix panel settings (datasheet
 * 109921, section 7), turn the backlight on and draw the static layout.
 * Blocking (reset delays); called from setup() only.
 * @return MODULE_INIT_SUCCESS always (the panel cannot be read back).
 */
module::InitStatus init();

/**
 * Redraw the status lines whose text changed, at most once per
 * DISPLAY_REFRESH_MS. Returns quickly when nothing is due.
 * @return MODULE_SERVICE_OK after a refresh, MODULE_SERVICE_SKIPPED otherwise.
 */
module::ServiceStatus service();

/**
 * Switch the backlight (expander pin GP4) on or off.
 * @param on True to light the panel.
 */
void setBacklight(bool on);

/**
 * True while the panel is touched: TSC2046 PENIRQ low, read through the
 * expander every 250 ms.  PENIRQ is disabled during a conversion, so ignore this
 * around touch reads, and end the last control byte with PD0 = 0 to keep it armed.
 * @return true if the latest expander read saw PENIRQ low.
 * @code
 * if (display::touchPressed()) { ... }
 * @endcode
 */
bool touchPressed();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = display::init(); }
    static module::ServiceStatus service() { return _serviceStatus = display::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace display

#endif // DISPLAY_H
