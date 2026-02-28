/**
 * @file hardware.h
 * @brief Shared hardware bus registry.
 *
 * Wraps the global Wire and SPI singletons so modules can access buses via
 * hardware::i2c() / hardware::spi() without coupling to the globals directly.
 *
 * Rationale:
 *   ESP-IDF 5.x creates a new I2C driver handle for every TwoWire instance.
 *   Instantiating a second TwoWire(0) alongside the framework-owned global
 *   Wire causes two handles to fight over port 0, resulting in
 *   ESP_ERR_INVALID_STATE on every transaction.  The correct approach is to
 *   use the global Wire exclusively and ensure no library re-calls begin().
 *
 *   The QMI8658 library is vendored in lib/QMI8658 with its internal
 *   Wire.begin() call removed; see lib/QMI8658/src/QMI8658.cpp for details.
 *
 * Usage:
 *   // In main.cpp setup(), before any module init:
 *   hardware::init();
 *
 *   // In any module that needs I2C:
 *   imu.begin(hardware::i2c());
 */

#pragma once

#include <Wire.h>
#include <SPI.h>
#include "module.h"

namespace hardware {

    /**
     * Initialise all shared hardware buses (I2C and SPI).
     * Must be called exactly once, before any module that uses a bus.
     *
     * @return MODULE_INIT_SUCCESS always (Wire.begin has no failure path on
     *         ESP32 with valid pins; SPI.begin is void).
     */
    module::InitStatus init();

    /**
     * Returns a reference to the shared I2C bus (the global Wire instance).
     * Valid after hardware::init() has been called.
     */
    TwoWire& i2c();

    /**
     * Returns a reference to the shared SPI bus (the global SPI instance).
     * Valid after hardware::init() has been called.
     */
    SPIClass& spi();

    /**
     * Scan the I2C bus by probing every 7-bit address via i2c_master_probe()
     * (bypasses the Wire layer entirely).  Logs each responding address and a
     * warning if nothing is found.  Useful for diagnosing wiring or driver
     * issues independent of any sensor library.
     *
     * @param timeoutMs  Per-address probe timeout in ms (default 10).
     * @return           Number of devices that responded.
     */
    uint8_t scanI2c(uint32_t timeoutMs = 10);

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
