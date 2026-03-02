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
 *   sensor.begin(hardware::i2c());
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
     * Recover the I2C bus by tearing down and re-creating the IDF master
     * driver (Wire.end() then Wire.begin()).
     *
     * IDF 5.x's new-gen I2C driver can leave the bus in ESP_ERR_INVALID_STATE
     * after a failed probe transaction even when the transaction itself was an
     * expected "device not at this address" probe.  The QMI8658 library is the
     * known trigger: it first probes QMI8658_ADDRESS_LOW; if that fails the bus
     * gets stuck, making every subsequent I2C call (including the ACS37800
     * init) also fail with INVALID_STATE.
     *
     * Call this after imu::init() (or any other module whose init is known to
     * leave the bus stuck) so that the next module starts with a clean driver.
     *
     * Wire.end() deletes the IDF bus handle; Wire.begin() creates a fresh one.
     * All sensor objects that hold a TwoWire* continue to work because they
     * reference the global Wire object, which Wire.begin() updates in place.
     */
    void recoverI2c();

    /**
     * Scan the I2C bus by probing every 7-bit address using the Arduino Wire
     * API (beginTransmission / endTransmission).  Logs each responding address
     * and a warning if nothing is found.
     *
     * The Wire API is used rather than i2c_master_probe() to avoid a crash
     * caused by Adafruit_I2CDevice::begin() leaving the IDF bus handle in an
     * inconsistent state (see hardware.cpp for full explanation).
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
