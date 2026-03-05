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
 * ── Card Detect ─────────────────────────────────────────────────────────────
 *
 * SD_CD_PIN (pin_config.h) must be connected to the socket's CD switch, which
 * shorts to GND when a card is fully seated.  The internal pull-up keeps the
 * pin HIGH when the slot is empty (card absent = HIGH, card present = LOW).
 *
 * service() polls the CD pin on every call and drives a simple state machine:
 *
 *   ABSENT  →  PRESENT  →  SD.begin() attempted (with cooldown)  →  READY
 *   READY   →  ABSENT   →  SD.end(), flags cleared                →  ABSENT
 *
 * Write failures (SD.open() returning invalid File) are also counted as a
 * belt-and-suspenders ejection signal — three consecutive failures trigger the
 * same SD.end() + flag-clear path even if the CD pin has not transitioned.
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
#include "config.h"



namespace logger {

static constexpr char TAG[] = "logger";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Maximum formatted message length including NUL terminator. */
static constexpr uint16_t LOG_BUF_SIZE = 256;

/**
 * How many consecutive write failures before the card is declared ejected.
 * Provides a software fallback if the CD pin wiring is unreliable.
 */
static constexpr uint8_t MAX_WRITE_FAILURES = 3;

/** Minimum time (ms) between successive SD.begin() reinit attempts. */
static constexpr uint32_t REINIT_COOLDOWN_MS = 2000;

/**
 * CD pin must hold a new state for this many milliseconds before the logger
 * acts on it, to filter mechanical switch bounce.
 */
static constexpr uint32_t DEBOUNCE_MS = 100;

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

static bool     sdReady       = false; ///< True once SD.begin() has succeeded.
static bool     headerWritten = false; ///< True once the CSV header has been written.
static uint8_t  writeFailures = 0;    ///< Consecutive file-open failures.

/// Last stable CD pin reading (true = card present / pin LOW).
static bool     lastCdPresent = false;
/// millis() when the CD pin last changed state (debounce anchor).
static uint32_t cdChangeMs    = 0;
/// millis() of the most recent SD.begin() attempt (rate-limits reinit).
static uint32_t lastReinitMs  = 0;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Populate @p buf with the current local time in "[YYYY-MM-DD HH:MM:SS] "
 * format.  @p buf must be at least 22 bytes.
 */
static void fillTimestamp(char* buf, size_t bufLen) {
    const time_t now = time(nullptr);
    strftime(buf, bufLen, "[%Y-%m-%d %H:%M:%S] ", localtime(&now));
}

/**
 * Declare the SD card ejected: release the bus, clear all flags.
 * Safe to call when already not ready.
 */
static void handleEject() {
    if (sdReady) {
        Serial.printf("[%s] SD card ejected — logging paused\n", TAG);
    }
    SD.end();
    sdReady       = false;
    headerWritten = false;
    writeFailures = 0;
}

/**
 * Record one write failure.  After MAX_WRITE_FAILURES consecutive failures the
 * card is treated as ejected (belt-and-suspenders in case the CD pin is noisy
 * or the card is removed faster than the debounce window).
 */
static void handleWriteFailure() {
    if (++writeFailures >= MAX_WRITE_FAILURES) {
        Serial.printf("[%s] %u consecutive write failures — assuming card ejected\n",
                      TAG, static_cast<unsigned>(MAX_WRITE_FAILURES));
        handleEject();
    }
}

/**
 * Attempt to (re-)initialise the SD card.
 *
 * @return true if the card is now mounted and accessible.
 */
static bool tryInit() {
    if (SD.begin(SD_CS_PIN, hardware::spi()) && SD.cardType() != CARD_NONE) {
        sdReady       = true;
        headerWritten = false;
        writeFailures = 0;

        const uint8_t  ct   = SD.cardType();
        const char*    name = (ct == CARD_MMC)  ? "MMC"  :
                              (ct == CARD_SD)   ? "SDSC" :
                              (ct == CARD_SDHC) ? "SDHC" : "UNKNOWN";
        Serial.printf("[%s] SD card ready: type=%s  size=%.1f MB  free=%.1f MB\n",
                      TAG,
                      name,
                      static_cast<double>(SD.cardSize())                      / (1024.0 * 1024.0),
                      static_cast<double>(SD.totalBytes() - SD.usedBytes())   / (1024.0 * 1024.0));
        return true;
    }

    SD.end();   // Clean up a failed SPI negotiation before the next attempt.
    return false;
}

// ---------------------------------------------------------------------------
// init
// ---------------------------------------------------------------------------

module::InitStatus init() {
    if (!ENABLE_LOGGER) {
        Serial.printf("[%s] Logger disabled in config.h\n", TAG);
        return module::MODULE_INIT_SUCCESS;
    }

    // Configure the Card Detect pin with the internal pull-up so it reads HIGH
    // (absent) when nothing is connected, and LOW (present) when the socket's
    // mechanical switch closes to GND.
    pinMode(SD_CD_PIN, INPUT_PULLDOWN);

    // Capture the initial CD state so service() has a baseline to diff against.
    // If the CD wire is not yet connected the pull-up holds the pin HIGH, which
    // would make the logger silently skip init.  To avoid that, attempt SD.begin()
    // regardless of the CD reading at startup; service() will use the pin for
    // hot-swap detection once the wire is in place.
    lastCdPresent = (digitalRead(SD_CD_PIN) == HIGH);
    cdChangeMs    = millis();

    if (tryInit()) {
        return module::MODULE_INIT_SUCCESS;
    }

    if (!lastCdPresent) {
        // CD reads HIGH — card absent or CD wire not yet connected.
        Serial.printf("[%s] SD.begin() failed and CD pin %d reads HIGH "
                      "(no card, or CD not wired yet)\n", TAG, SD_CD_PIN);
        return module::MODULE_INIT_SUCCESS;  // non-fatal; service() will retry on insertion
    }

    Serial.printf("[%s] SD.begin() failed — check wiring and CS pin (%d)\n",
                  TAG, SD_CS_PIN);
    return module::MODULE_INIT_HARDWARE_ERROR;
}

// ---------------------------------------------------------------------------
// service — CD pin state machine
// ---------------------------------------------------------------------------

module::ServiceStatus service() {
    if (!ENABLE_LOGGER) {
        return module::MODULE_SERVICE_NOT_STARTED;
    }

    const bool     cdNow = (digitalRead(SD_CD_PIN) == HIGH); // HIGH = card present
    const uint32_t now   = millis();

    // ── Debounce ──────────────────────────────────────────────────────────
    if (cdNow != lastCdPresent) {
        // Pin changed — restart the debounce window and do nothing else.
        lastCdPresent = cdNow;
        cdChangeMs    = now;
        return module::MODULE_SERVICE_SKIPPED;
    }

    // The pin has been stable since cdChangeMs.  Only act once the debounce
    // window has elapsed.
    if (now - cdChangeMs < DEBOUNCE_MS) {
        return module::MODULE_SERVICE_SKIPPED;
    }

    // ── Card absent ───────────────────────────────────────────────────────
    if (!cdNow && sdReady) {
        handleEject();
        return module::MODULE_SERVICE_OK;
    }

    // ── Card present but not yet ready ────────────────────────────────────
    if (cdNow && !sdReady) {
        if (now - lastReinitMs < REINIT_COOLDOWN_MS) {
            return module::MODULE_SERVICE_SKIPPED;
        }
        lastReinitMs = now;

        if (tryInit()) {
            Serial.printf("[%s] SD card inserted — logging resumed\n", TAG);
            return module::MODULE_SERVICE_OK;
        }
        // tryInit already called SD.end(); we'll retry next cooldown period.
    }

    return module::MODULE_SERVICE_SKIPPED;
}

// ---------------------------------------------------------------------------
// log / logf
// ---------------------------------------------------------------------------

void log(const char* msg) {
    if (!ENABLE_LOGGER) {
        return;
    }

    // Always write to Serial regardless of SD state.
    Serial.print(msg);

    if (!sdReady) return;

    char timestamp[22];
    fillTimestamp(timestamp, sizeof(timestamp));

    File file = SD.open(SERIAL_LOG_PATH, FILE_APPEND);
    if (!file) {
        handleWriteFailure();
        return;
    }
    file.print(timestamp);
    file.print(msg);
    file.close();
    writeFailures = 0; // successful write resets the failure counter
}

void logf(const char* fmt, ...) {
    if (!ENABLE_LOGGER) {
        return;
    }

    char buf[LOG_BUF_SIZE];
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
    if (!ENABLE_LOGGER) {
        return;
    }

    if (!sdReady) return;

    const uint8_t n = frame.fieldCount();
    if (n == 0) return;

    // Capture the local timestamp once for both the header check and data row.
    const time_t now = time(nullptr);
    char localTimestamp[20];
    strftime(localTimestamp, sizeof(localTimestamp), "%Y-%m-%d %H:%M:%S", localtime(&now));

    // Write the CSV header row the first time, or if the file was deleted /
    // a new card was inserted (headerWritten is cleared by handleEject()).
    if (!headerWritten || !SD.exists(TELEMETRY_PATH)) {
        File file = SD.open(TELEMETRY_PATH, FILE_WRITE);
        if (!file) {
            handleWriteFailure();
            return;
        }
        file.print("log_timestamp");
        for (uint8_t i = 0; i < n; ++i) {
            file.print(',');
            file.print(frame.getField(i).name);
        }
        file.println();
        file.close();
        headerWritten = true;
        writeFailures = 0;
    }

    // Append one CSV data row.
    File file = SD.open(TELEMETRY_PATH, FILE_APPEND);
    if (!file) {
        handleWriteFailure();
        return;
    }

    file.print(localTimestamp);
    for (uint8_t i = 0; i < n; ++i) {
        file.print(',');

        const char* val = frame.getField(i).str;

        // Wrap in double-quotes if the value contains a comma or double-quote
        // to produce valid RFC 4180 CSV.
        const bool needsQuote = (strchr(val, ',') != nullptr ||
                                 strchr(val, '"') != nullptr);
        if (needsQuote) {
            file.print('"');
            for (const char* p = val; *p != '\0'; ++p) {
                if (*p == '"') file.print('"'); // RFC 4180: double embedded quotes
                file.print(*p);
            }
            file.print('"');
        } else {
            file.print(val);
        }
    }

    file.println();
    file.close();
    writeFailures = 0;
}

} // namespace logger
