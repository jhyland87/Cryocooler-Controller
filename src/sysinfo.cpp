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
#include <Adafruit_INA260.h>
#include <esp_timer.h>
#include <esp_heap_caps.h>
#include <esp_system.h>
#include <esp_freertos_hooks.h>

#include "config.h"
#include "sysinfo.h"
#include "hardware.h"
#include "imu.h"
#include "sensor_mock.h"

// ── INA260 readings ─────────────────────────────────────────────────────────
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

Adafruit_INA260 ina260 = Adafruit_INA260();


module::InitStatus init() {
    Serial.println(F("[sysinfo] Registering CPU idle hooks..."));
    esp_register_freertos_idle_hook_for_cpu(onIdleCore0, 0);

    esp_chip_info_t chipInfo;
    esp_chip_info(&chipInfo);
    if (chipInfo.cores > 1) {
        esp_register_freertos_idle_hook_for_cpu(onIdleCore1, 1);
    }
    lastCpuSampleUs = esp_timer_get_time();

    Serial.println(F("[sysinfo] Looking for INA260 chip..."));

    TwoWire& i2c = hardware::i2c();

    for (uint8_t attempt = 0; attempt < 2; ++attempt) {
        if (ina260.begin(INA260_I2CADDR_DEFAULT, &i2c)) {
            Serial.println(F("[sysinfo] INA260 chip found and initialized"));
            analogReadResolution(ADC_RESOLUTION);
            return module::MODULE_INIT_SUCCESS;
        }
        delay(100);
    }

    Serial.println(F("[sysinfo] INA260 chip not found after 2 attempts"));
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
    voltage = ina260.readBusVoltage();
    current = ina260.readCurrent();
    power   = ina260.readPower();
    return module::MODULE_SERVICE_OK;
}

// ── INA260 getters ──────────────────────────────────────────────────────────

float getVoltage() {
    return voltage;
}

float getCurrent() {
    return current;
}

float getPower() {
    return power;
}

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
