/**
 * @file hardware.h
 * @brief Shared hardware bus registry.
 *
 * Wraps the global SPI singleton and the SC18IS604 SPI-to-I2C bridge so
 * modules can access buses via hardware::spi() / hardware::i2c() without
 * coupling to the globals directly.
 *
 * The ESP32 has no I2C pins in use: the only I2C device (the EMC2303 fan
 * controller) sits behind the bridge, reached through an EMC230xBus.
 *
 * Usage:
 *   // In main.cpp setup(), before any module init:
 *   hardware::init();
 *
 *   // In a module that needs the I2C bus:
 *   controller.begin(addr, &hardware::i2c());
 */

#pragma once

#include <SPI.h>
#include <EMC230x.h>
#include "module.h"

namespace hardware {

    module::InitStatus initSPI();
    module::InitStatus initAcsSPI();
    module::InitStatus initI2C();
    /**
     * Initialise all shared hardware buses (I2C and SPI).
     * Must be called exactly once, before any module that uses a bus.
     *
     * @return MODULE_INIT_SUCCESS always (Wire.begin has no failure path on
     *         ESP32 with valid pins; SPI.begin is void).
     */
    module::InitStatus init();


    /**
     * Returns the I2C bus behind the SC18IS604 bridge.
     * Used by the EMC2303 fan controller.
     */
    EMC230xBus& i2c();

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

    /**
     * Reset the SC18IS604 bridge (and with it the I2C controller) to a clean
     * idle state: pulses its RESET pin and reconfigures the I2C clock.
     */
    void recoverI2c();

    // ── I2C error monitor ────────────────────────────────────────────────────
    //
    // The bridge driver reports failed transactions via reportI2cError();
    // serviceI2c() logs a periodic summary and resets the bridge when a
    // threshold is exceeded.

    /** Record a single I2C transaction error. */
    void reportI2cError();

    /**
     * Periodic I2C health check — call once per main-loop tick.
     * Logs a summary every 10 s if errors occurred and triggers
     * recoverI2c() when the per-window count exceeds the threshold.
     */
    void serviceI2c();

    /** Lifetime I2C error count since boot. */
    uint32_t getI2cErrorTotal();

    /** Number of automatic bus recovery attempts since boot. */
    uint32_t getI2cRecoveryCount();

// ── Module interface ──────────────────────────────────────────────────────────
//
// hardware provides shared I2C and SPI buses; all other modules depend on it.
// No periodic service work is needed — bus handles remain valid indefinitely.

struct Module : ModuleBase<Module> {
    static module::InitStatus init() { return _initStatus = hardware::init(); }
    // service() — inherited no-op; bus handles require no periodic maintenance.
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace hardware
