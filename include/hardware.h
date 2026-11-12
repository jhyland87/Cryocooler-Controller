/**
 * @file hardware.h
 * @brief Shared hardware bus registry.
 *
 * Wraps the global SPI singleton so modules can access it via hardware::spi()
 * without coupling to the global directly.  The firmware uses no I2C.
 *
 * Usage:
 *   // In main.cpp setup(), before any module init:
 *   hardware::init();
 */

#pragma once

#include <SPI.h>
#include "module.h"

namespace hardware {

    /**
     * Deselects every device on the shared SPI bus (the decoder outputs and
     * the ACS37800 CS GPIO), then starts the bus. Safe to call again.
     *
     * @return MODULE_INIT_SUCCESS always (SPI.begin is void).
     */
    module::InitStatus initSPI();

    /**
     * Initialise the shared SPI bus and the GPIO expander on it.
     * Must be called exactly once, before any module that uses the bus.
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
     * Leaves the shared SPI clock idling low (CPOL 0) by clocking one byte
     * with every CS high. Call after any SPI_MODE2/3 transaction (AD9833; the
     * ACS37800 driver calls it after each of its own): the ESP32-S3 only
     * applies a new idle level when the next transfer starts, so the next
     * mode-1 device (ADS1220, INA239) would otherwise see an extra falling
     * edge after its CS goes low and shift by a bit.
     */
    void idleSpiClockLow();

// ── Module interface ──────────────────────────────────────────────────────────
//
// hardware provides the shared SPI bus; all other modules depend on it.
// No periodic service work is needed — the bus handle remains valid indefinitely.

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = hardware::init(); }
    // service() — inherited no-op; the bus handle requires no periodic maintenance.
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace hardware
