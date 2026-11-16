/**
 * @file sysinfo.cpp
 * @brief Device voltage monitoring and ESP32 resource utilisation.
 *
 * CPU usage is estimated via FreeRTOS idle-task hooks.  Each core's idle
 * task increments a dedicated counter; once per second the delta is compared
 * to the highest delta ever observed (adaptive "fully-idle" baseline) to
 * derive an approximate load percentage.
 *
 * Heap / PSRAM metrics are thin wrappers around the ESP-IDF heap_caps API.
 */

#include <Arduino.h>
#include <INA239.h>
#include <esp_timer.h>
#include <esp_heap_caps.h>
#include <esp_system.h>
#include <esp_freertos_hooks.h>

#include "config.h"
#include "tick.h"
#include "sysinfo.h"
#include "hardware.h"
#include "imu.h"
#include "sensor_mock.h"

// ── INA239 readings ─────────────────────────────────────────────────────────
static float voltage = 0.0f;
static float current = 0.0f;
static float power   = 0.0f;

// ── CPU usage tracking ──────────────────────────────────────────────────────
static float              cpuUsage            = 0.0f;
static volatile uint32_t  idleCountCore0      = 0;
static volatile uint32_t  idleCountCore1      = 0;
static uint32_t           prevIdleTotal       = 0;
static uint32_t           maxIdleDeltaPerSec  = 0;
static int64_t            lastCpuSampleUs     = 0;

static constexpr int64_t kCpuSampleIntervalUs = 1000000;  // 1 second

static bool IRAM_ATTR onIdleCore0() { ++idleCountCore0; return false; }
static bool IRAM_ATTR onIdleCore1() { ++idleCountCore1; return false; }

static void updateCpuUsage() {
    int64_t nowUs   = esp_timer_get_time();
    int64_t elapsed = nowUs - lastCpuSampleUs;
    if (elapsed < kCpuSampleIntervalUs) return;
    lastCpuSampleUs = nowUs;

    uint32_t total = idleCountCore0 + idleCountCore1;
    uint32_t delta = total - prevIdleTotal;
    prevIdleTotal  = total;

    if (elapsed > 0) {
        delta = static_cast<uint32_t>(
            static_cast<int64_t>(delta) * kCpuSampleIntervalUs / elapsed);
    }

    if (delta > maxIdleDeltaPerSec) {
        maxIdleDeltaPerSec = delta;
    }

    if (maxIdleDeltaPerSec > 0) {
        float idleFrac = static_cast<float>(delta)
                       / static_cast<float>(maxIdleDeltaPerSec);
        cpuUsage = 100.0f * (1.0f - idleFrac);
        if (cpuUsage < 0.0f)   cpuUsage = 0.0f;
        if (cpuUsage > 100.0f) cpuUsage = 100.0f;
    }
}


namespace sysinfo {

static constexpr uint16_t INA239_MANUFACTURER_ID = 0x5449;  // "TI"
static constexpr uint16_t INA239_DIE_ID         = 0x239;
// The shunt (R65) is 15 mΩ, but on this board the sense lines tap the 12 V
// copper away from its pads, so the INA239 also sees the drop in that copper.
// Effective value measured 2026-11-15: 8.90 mV at the chip for 0.21 A on a
// series meter, less the 0.6 mV VBUS offset below.  One load point only, and
// copper drifts about 0.4 %/°C.  Re-measure with `get ina` on another board.
static constexpr float    SHUNT_OHMS            = 0.0396f;
// The ±163.84 mV input range now ends near 4.1 A (163.84 mV / 39.6 mΩ).
static constexpr float    SHUNT_MAX_AMPS        = 10.0f;
// VBUS shares the filtered IN− line: its input current (ZVBUS 1 MΩ, INA239
// datasheet SLYS027 Electrical Characteristics) through the 49.9 Ω filter
// resistor adds a shunt-voltage offset proportional to the bus voltage.
static constexpr float    VBUS_INPUT_OHMS       = 1.0e6f;
static constexpr float    INPUT_FILTER_OHMS     = 49.9f;
static constexpr float    OFFSET_AMPS_PER_BUS_VOLT =
    INPUT_FILTER_OHMS / VBUS_INPUT_OHMS / SHUNT_OHMS;

// Shares the main SPI bus; the library applies SPI mode 1 per transaction.
static INA239 ina239(INA239_CS, &hardware::spi());

static constexpr uint8_t MAX_SPI_ERRORS = 3;
static uint8_t sIna239Errors = 0;
static bool    sIna239Disabled = false;

// SPI has no ACK, so presence is judged by reading the fixed ID registers.
static bool ina239Present() {
    return ina239.getManufacturer() == INA239_MANUFACTURER_ID
        && ina239.getDieID() == INA239_DIE_ID;
}

module::InitStatus init() {
    sIna239Errors   = 0;
    sIna239Disabled = false;

    Serial.println(F("[sysinfo] Registering CPU idle hooks..."));
    esp_register_freertos_idle_hook_for_cpu(onIdleCore0, 0);

    esp_chip_info_t chipInfo;
    esp_chip_info(&chipInfo);
    if (chipInfo.cores > 1) {
        esp_register_freertos_idle_hook_for_cpu(onIdleCore1, 1);
    }
    lastCpuSampleUs = esp_timer_get_time();

    Serial.println(F("[sysinfo] Looking for INA239 chip..."));

    for (uint8_t attempt = 0; attempt < 2; ++attempt) {
        ina239.begin();
        if (ina239Present()) {
            ina239.setMaxCurrentShunt(SHUNT_MAX_AMPS, SHUNT_OHMS);
            Serial.println(F("[sysinfo] INA239 chip found and initialized"));
            analogReadResolution(ADC_RESOLUTION);
            return module::MODULE_INIT_SUCCESS;
        }
        delay(100);
    }

    Serial.println(F("[sysinfo] INA239 chip not found after 2 attempts"));
    analogReadResolution(ADC_RESOLUTION);
    return module::MODULE_INIT_HARDWARE_ERROR;
}


module::ServiceStatus service() {
    updateCpuUsage();

    if (sensor_mock::isActive()) {
        const auto& mo = sensor_mock::get();
        setLastReadings(mo.voltage, mo.current, mo.voltage * mo.current);
        return module::MODULE_SERVICE_OK;
    }

    // Chip missing at boot or lost since: look for it again every so often
    // instead of reading all-zero or all-one frames every tick.
    if (Module::getInitStatus() != module::MODULE_INIT_SUCCESS || sIna239Disabled) {
        static uint32_t lastProbeMs = 0;
        const uint32_t nowMs = tick::nowMs();
        if (static_cast<uint32_t>(nowMs - lastProbeMs) < SYSINFO_INA239_REPROBE_INTERVAL_MS) {
            return module::MODULE_SERVICE_SKIPPED;
        }
        lastProbeMs = nowMs;
        if (!ina239Present()) {
            return module::MODULE_SERVICE_SKIPPED;
        }
        // A power-cycled chip has lost its shunt calibration.
        ina239.begin();
        ina239.setMaxCurrentShunt(SHUNT_MAX_AMPS, SHUNT_OHMS);
        sIna239Errors   = 0;
        sIna239Disabled = false;
        Module::overrideInitStatus(module::MODULE_INIT_SUCCESS);
        ESP_LOGI("sysinfo", "INA239 found — readings resumed");
    }

    // ID check: when 12 V drops, the INA239 loses its supply and MISO floats.
    // Require consecutive failures before reporting an error — one corrupted
    // frame should not flip the service status and spam the log.
    if (!ina239Present()) {
        ++sIna239Errors;
        if (sIna239Errors >= MAX_SPI_ERRORS) {
            sIna239Disabled = true;
            ESP_LOGW("sysinfo", "INA239 offline after %u consecutive errors — disabled until it answers again",
                     sIna239Errors);
            voltage = NAN;
            current = NAN;
            power   = NAN;
            return module::MODULE_SERVICE_ERROR;
        }
        // Transient failure — keep last-known-good values, don't report error
        return module::MODULE_SERVICE_OK;
    }

    sIna239Errors = 0;  // reset on successful ID read

    float rawV = ina239.getBusVoltage();

    // Sanity check: reject readings far outside the 12 V rail.  Send NaN so
    // the dashboard shows a gap in the chart for this tick.
    if (rawV > 60.0f || rawV < -1.0f) {
        voltage = NAN;
        current = NAN;
        power   = NAN;
        return module::MODULE_SERVICE_OK;
    }

    voltage = rawV;
    current = ina239.getCurrent() - voltage * OFFSET_AMPS_PER_BUS_VOLT;  // A
    // Library 0.4.0 getPower() scales wrongly: setMaxCurrentShunt() doesn't update its LSB.
    power   = voltage * current;    // W
    return module::MODULE_SERVICE_OK;
}

// ── INA239 getters ──────────────────────────────────────────────────────────

void printIna239Diagnostics(Print& out) {
    // Register addresses: INA239 datasheet (SLYS027), register map.
    const uint16_t config    = ina239.readRegister(0x00, 2);
    const uint16_t adcConfig = ina239.readRegister(0x01, 2);
    const uint16_t shuntCal  = ina239.readRegister(0x02, 2);
    const int16_t  shuntRaw  = static_cast<int16_t>(ina239.readRegister(0x04, 2));
    const uint16_t busRaw    = ina239.readRegister(0x05, 2);
    const int16_t  currentRaw = static_cast<int16_t>(ina239.readRegister(0x07, 2));
    const bool     narrowRange = (config & 0x0010u) != 0;  // ADCRANGE, bit 4
    const float    shuntLsbUv  = narrowRange ? 1.25f : 5.0f;

    char buf[128];
    snprintf(buf, sizeof(buf), "CONFIG 0x%04X (ADCRANGE=%d)  ADC_CONFIG 0x%04X  SHUNT_CAL %u",
             config, narrowRange ? 1 : 0, adcConfig, shuntCal);
    out.println(buf);
    snprintf(buf, sizeof(buf), "VSHUNT raw %d = %.3f mV   VBUS raw %u = %.3f V   CURRENT raw %d",
             shuntRaw, static_cast<float>(shuntRaw) * shuntLsbUv / 1000.0f,
             busRaw, static_cast<float>(busRaw) * 3.125e-3f, currentRaw);
    out.println(buf);
    snprintf(buf, sizeof(buf), "library: current LSB %.1f uA, shunt %.4f ohm, current %.4f A",
             ina239.getCurrentLSB_uA(), ina239.getShunt(), ina239.getCurrent());
    out.println(buf);
}

float getVoltage() {
    return voltage;
}

float getCurrent() {
    return current;
}

float getPower() {
    return power;
}

// "Ambient" is the IMU die temperature, i.e. the cooler body it is mounted on.
float getAmbientTemperature() {
    return imu::getTemperature();
}

void setLastReadings(float v, float a, float w) {
    voltage = v;
    current = a;
    power   = w;
}

// ── CPU ─────────────────────────────────────────────────────────────────────

float getCpuUsagePercent() {
    return cpuUsage;
}

uint32_t getCpuFreqMHz() {
    return ESP.getCpuFreqMHz();
}

// ── Heap (internal SRAM) ────────────────────────────────────────────────────

uint32_t getTotalHeapBytes() {
    return heap_caps_get_total_size(MALLOC_CAP_INTERNAL);
}

uint32_t getFreeHeapBytes() {
    return heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
}

uint32_t getMinFreeHeapBytes() {
    return heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL);
}

uint32_t getMaxAllocBytes() {
    return heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL);
}

float getHeapUsagePercent() {
    uint32_t total = heap_caps_get_total_size(MALLOC_CAP_INTERNAL);
    if (total == 0) return 0.0f;
    uint32_t free = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
    return 100.0f * static_cast<float>(total - free)
                   / static_cast<float>(total);
}

// ── PSRAM (external SPI RAM) ────────────────────────────────────────────────

uint32_t getTotalPsramBytes() {
    return heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
}

uint32_t getFreePsramBytes() {
    return heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
}

float getPsramUsagePercent() {
    uint32_t total = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
    if (total == 0) return 0.0f;
    uint32_t free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    return 100.0f * static_cast<float>(total - free)
                   / static_cast<float>(total);
}

// ── System info ─────────────────────────────────────────────────────────────

uint32_t getUptimeMs() {
    return static_cast<uint32_t>(esp_timer_get_time() / 1000);
}

uint8_t getNumCores() {
    esp_chip_info_t info;
    esp_chip_info(&info);
    return static_cast<uint8_t>(info.cores);
}

const char* getChipModel() {
    return ESP.getChipModel();
}

} // namespace sysinfo
