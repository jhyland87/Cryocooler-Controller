/**
 * @file logger.cpp
 * @brief SD-backed serial and telemetry logger implementation.
 *
 * SD card wiring reference (SPI mode):
 *
 * +--------------+---------+-------+----------+----------+----------+
 * | SPI Pin Name | ESP8266 | ESP32 | ESP32‑S2 | ESP32‑S3 | ESP32‑C3 |
 * +==============+=========+=======+==========+==========+==========+
 * | CS (SS)      | GPIO15  | GPIO5 | GPIO34   | GPIO10   | GPIO7    |
 * +--------------+---------+-------+----------+----------+----------+
 * | DI (MOSI)    | GPIO13  | GPIO23| GPIO35   | GPIO11   | GPIO6    |
 * +--------------+---------+-------+----------+----------+----------+
 * | DO (MISO)    | GPIO12  | GPIO19| GPIO37   | GPIO13   | GPIO5    |
 * +--------------+---------+-------+----------+----------+----------+
 * | SCK (SCLK)   | GPIO14  | GPIO18| GPIO36   | GPIO12   | GPIO4    |
 * +--------------+---------+-------+----------+----------+----------+
 *
 * This project uses the shared SPI bus (SPI_CLK/SPI_MISO/SPI_MOSI from
 * pin_config.h) that hardware::Module::init() starts via SPI.begin().
 * SD_CS_PIN (pin_config.h) selects the card; all other CS lines are kept
 * HIGH by their respective drivers during SD transactions.
 *
 * For more info see:
 * https://github.com/espressif/arduino-esp32/tree/master/libraries/SD
 */

#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <stdarg.h>
#include <time.h>
#include "logger.h"
#include "pin_config.h"
#include "hardware.h"

namespace logger {

static constexpr char TAG[] = "logger";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Maximum formatted message length, including the NUL terminator. */
static constexpr uint16_t kLogBufSize = 256;

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static bool sdReady_       = false; ///< True once SD.begin() has succeeded.
static bool headerWritten_ = false; ///< True once the CSV header has been written.

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Append @p data to @p path, opening and closing the file each call.
 *
 * Open-write-close on every append is slower than keeping a file handle open,
 * but it ensures the FAT directory entry is updated after every write so that
 * a power loss never corrupts the file beyond the most recent entry.
 *
 * @return true on success, false if the file could not be opened.
 */
static bool appendToFile(const char* path, const char* data) {
    File file = SD.open(path, FILE_APPEND);
    if (!file) return false;
    file.print(data);
    file.close();
    return true;
}

// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------

module::InitStatus init() {
    // SD.begin() uses the SPI singleton already started by hardware::Module::init().
    if (!SD.begin(SD_CS_PIN, hardware::spi())) {
        Serial.printf("[%s] SD.begin() failed — check wiring and CS pin (%d)\n",
                      TAG, SD_CS_PIN);
        return module::MODULE_INIT_HARDWARE_ERROR;
    }

    const uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE) {
        Serial.printf("[%s] No SD card detected on CS pin %d\n", TAG, SD_CS_PIN);
        return module::MODULE_INIT_HARDWARE_ERROR;
    }

    sdReady_ = true;

    const char* typeName =
        (cardType == CARD_MMC)  ? "MMC"     :
        (cardType == CARD_SD)   ? "SDSC"    :
        (cardType == CARD_SDHC) ? "SDHC"    : "UNKNOWN";

    const uint64_t cardBytes = SD.cardSize();
    Serial.printf("[%s] SD card ready: type=%s  size=%.1f MB  free=%.1f MB\n",
                  TAG,
                  typeName,
                  static_cast<double>(cardBytes)         / (1024.0 * 1024.0),
                  static_cast<double>(SD.totalBytes() - SD.usedBytes()) / (1024.0 * 1024.0));

    return module::MODULE_INIT_SUCCESS;
}

// ---------------------------------------------------------------------------
// service
// ---------------------------------------------------------------------------

module::ServiceStatus service() {
    // All I/O is demand-driven; nothing to do here.
    return module::MODULE_SERVICE_SKIPPED;
}

// ---------------------------------------------------------------------------
// log / logf
// ---------------------------------------------------------------------------

void log(const char* msg) {
    // Always write to Serial regardless of SD state.
    Serial.print(msg);

    if (!sdReady_) return;

    // Build a timestamped prefix for the file entry.
    const time_t now = time(nullptr);
    char tsBuf[22];
    strftime(tsBuf, sizeof(tsBuf), "[%Y-%m-%d %H:%M:%S] ", localtime(&now));

    // Open, write (prefix + message), close — safe against power loss.
    File file = SD.open(kSerialLogPath, FILE_APPEND);
    if (!file) {
        Serial.printf("[%s] Failed to open %s for append\n", TAG, kSerialLogPath);
        return;
    }
    file.print(tsBuf);
    file.print(msg);
    file.close();
}

void logf(const char* fmt, ...) {
    char buf[kLogBufSize];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    log(buf);
}

// ---------------------------------------------------------------------------
// logTelemetry
// ---------------------------------------------------------------------------

void logTelemetry(const FrameBuilder& frame) {
    if (!sdReady_) return;

    const uint8_t n = frame.fieldCount();
    if (n == 0) return;

    // Capture the local timestamp once for both the header check and data row.
    const time_t now = time(nullptr);
    char localTs[20];
    strftime(localTs, sizeof(localTs), "%Y-%m-%d %H:%M:%S", localtime(&now));

    // Write the CSV header row the first time, or if the file was deleted.
    if (!headerWritten_ || !SD.exists(kTelemetryPath)) {
        File file = SD.open(kTelemetryPath, FILE_WRITE);
        if (!file) {
            Serial.printf("[%s] Failed to create %s\n", TAG, kTelemetryPath);
            return;
        }
        file.print("log_timestamp");  // first column header
        for (uint8_t i = 0; i < n; ++i) {
            file.print(',');
            file.print(frame.getField(i).name);
        }
        file.println();
        file.close();
        headerWritten_ = true;
    }

    // Append one CSV data row.
    File file = SD.open(kTelemetryPath, FILE_APPEND);
    if (!file) {
        Serial.printf("[%s] Failed to open %s for append\n", TAG, kTelemetryPath);
        return;
    }

    file.print(localTs);  // first column value
    for (uint8_t i = 0; i < n; ++i) {
        file.print(',');

        const char* val = frame.getField(i).str;

        // Wrap in double-quotes if the value contains a comma or double-quote
        // so the output is always valid RFC 4180 CSV.
        const bool needsQuote = (strchr(val, ',') != nullptr ||
                                 strchr(val, '"') != nullptr);
        if (needsQuote) {
            file.print('"');
            // Escape any embedded double-quotes per RFC 4180 ("" → literal ").
            for (const char* p = val; *p != '\0'; ++p) {
                if (*p == '"') file.print('"'); // double it
                file.print(*p);
            }
            file.print('"');
        } else {
            file.print(val);
        }
    }

    file.println();
    file.close();
}

} // namespace logger
