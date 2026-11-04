/**
 * @file hardware.h
 * @brief Shared hardware bus registry.
 *
 * Wraps the global SPI singleton and the ACS37800 bus so modules can access
 * them via hardware::spi() / hardware::acsSpi() without coupling to the
 * globals directly.  The firmware uses no I2C.
 *
 * Usage:
 *   // In main.cpp setup(), before any module init:
 *   hardware::init();
 */

#pragma once

#include <SPI.h>
#include "module.h"

namespace hardware {

    module::InitStatus initSPI();
    module::InitStatus initAcsSPI();
    /**
     * Initialise all shared SPI buses.
     * Must be called exactly once, before any module that uses a bus.
     *
     * @return MODULE_INIT_SUCCESS always (SPI.begin is void).
     */
    module::InitStatus init();

    /**
     * Returns a reference to the shared SPI bus (the global SPI instance).
     * Valid after hardware::init() has been called.
     */
    SPIClass& spi();

    /**
     * Returns a reference to the ACS37800 dedicated SPI bus (SPI3_HOST).
     * Separate from the main SPI bus because the ACS37800 keeps MISO driven
     * when CS is high, which would corrupt the shared bus.
     */
    SPIClass& acsSpi();

// ── Module interface ──────────────────────────────────────────────────────────
//
// hardware provides the shared SPI buses; all other modules depend on it.
// No periodic service work is needed — bus handles remain valid indefinitely.

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = hardware::init(); }
    // service() — inherited no-op; bus handles require no periodic maintenance.
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace hardware
