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
 *   The Adafruit LSM6DS library manages I2C via Adafruit_BusIO, which
 *   accepts an external TwoWire reference and does not call Wire.begin().
 *
 * Usage:
 *   // In main.cpp setup(), before any module init:
 *   hardware::init();
 *
 *   // In any module that needs I2C:
 *   sensor.begin(hardware::i2c());
 */

#pragma once

#include <Wire.h>
#include <SPI.h>
#include "module.h"

namespace hardware {

    module::InitStatus initSPI();
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
     * Reset the I2C bus to a clean idle state.
     *
     * On Core 3.x (IDF 5.x) uses i2c_master_bus_reset(); falls back to
     * Wire.end()/Wire.begin() if that fails or on Core 2.x.  All sensor
     * objects that hold a TwoWire* remain valid because they reference the
     * global Wire object, which Wire.begin() updates in place.
     */
    void recoverI2c();

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
