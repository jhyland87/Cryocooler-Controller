/**
 * @file sysinfo.h
 * @brief INA260 power monitoring and ESP32 resource utilisation.
 *
 * Exposes supply-rail voltage/current/power from the INA260 as well as
 * runtime resource metrics (CPU load, heap, PSRAM, chip info).
 *
 * CPU usage is estimated via FreeRTOS idle-task hooks registered during
 * init().  The first second of data is used to establish an adaptive
 * "fully-idle" baseline, so the reading converges quickly after boot.
 */

#ifndef DEVICE_H
#define DEVICE_H

#include <stdint.h>
#include "module.h"

namespace sysinfo {

/**
 * Initialise INA260 ADC and register FreeRTOS idle hooks for CPU tracking.
 * @return MODULE_INIT_SUCCESS if INA260 responds, HARDWARE_ERROR otherwise.
 */
module::InitStatus init();

/**
 * Sample INA260 and update CPU usage estimate.
 * @return SERVICE_OK always.
 */
module::ServiceStatus service();

// ── INA260 power rail ─────────────────────────────────────────────────────────

float getVoltage();
float getCurrent();
float getPower();
float getAmbientTemperature();

/**
 * Inject cached readings directly, bypassing the INA260 hardware read.
 * Used in mock mode so that telemetry and the dashboard reflect the values
 * set via `mock voltage` and `mock current` without touching the I2C bus.
 * Power is derived as voltage * current.
 */
void setLastReadings(float voltage, float current, float power);

// ── CPU ───────────────────────────────────────────────────────────────────────

float    getCpuUsagePercent();
uint32_t getCpuFreqMHz();

// ── Heap (internal SRAM) ──────────────────────────────────────────────────────

uint32_t getTotalHeapBytes();
uint32_t getFreeHeapBytes();
uint32_t getMinFreeHeapBytes();
uint32_t getMaxAllocBytes();
float    getHeapUsagePercent();

// ── PSRAM (external SPI RAM) ──────────────────────────────────────────────────

uint32_t getTotalPsramBytes();
uint32_t getFreePsramBytes();
float    getPsramUsagePercent();

// ── System info ───────────────────────────────────────────────────────────────

uint32_t    getUptimeMs();
uint8_t     getNumCores();
const char* getChipModel();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus    = sysinfo::init(); }
    static module::ServiceStatus service() { return _serviceStatus = sysinfo::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace sysinfo

#endif // DEVICE_H
