/**
 * @file run_recorder.cpp
 * @brief PSRAM run recorder and the GET /api/history endpoint.
 *
 * service() runs on loop() (Core 1) and pushes one sample a second. The HTTP
 * filler runs in the async TCP task and reads samples by sequence number. A
 * spinlock guards each push and copy; a sample overwritten while a response is
 * streaming is skipped. No ISR touches the PSRAM buffer.
 */

#include <Arduino.h>
#include <ESPAsyncWebServer.h>
#include <esp_heap_caps.h>
#include <esp_random.h>
#include <freertos/FreeRTOS.h>
#include <pb_encode.h>
#include <algorithm>
#include <memory>

#include "run_recorder.h"
#include "config.h"
#include "logger.h"
#include "run_history_ring.h"
#include "telemetry_pb.h"
#include "tick.h"

static LogStream _Log = Log.createChildLogger("run_recorder");

namespace run_recorder {

// ─── Channel table ────────────────────────────────────────────────────────────
// Keys match the dashboard's HISTORY_KEYS; the dashboard maps values by key.

using FrameReader = float (*)(const cryocooler_TelemetryFrame& frame);

struct Channel {
    const char* key;
    FrameReader read;
};

static const Channel CHANNELS[] = {
    {"cold_head.temp_c",           [](const cryocooler_TelemetryFrame& frame) { return frame.cold_head.temp_c; }},
    {"cold_head.ambient_temp_c",   [](const cryocooler_TelemetryFrame& frame) { return frame.cold_head.ambient_temp_c; }},
    {"cold_head.target_temp_c",    [](const cryocooler_TelemetryFrame& frame) { return frame.cold_head.target_temp_c; }},
    {"cold_head.voltage_v",        [](const cryocooler_TelemetryFrame& frame) { return frame.cold_head.voltage_v; }},
    {"cold_head.current_a",        [](const cryocooler_TelemetryFrame& frame) { return frame.cold_head.current_a; }},
    {"amplifier.power_w",          [](const cryocooler_TelemetryFrame& frame) { return frame.amplifier.power_w; }},
    {"system.voltage_v",           [](const cryocooler_TelemetryFrame& frame) { return frame.system.voltage_v; }},
    {"system.current_a",           [](const cryocooler_TelemetryFrame& frame) { return frame.system.current_a; }},
    {"cooling.fan_speed",          [](const cryocooler_TelemetryFrame& frame) { return frame.cooling.fan_speed; }},
    {"cooling.temp_c",             [](const cryocooler_TelemetryFrame& frame) { return frame.cooling.temp_c; }},
    {"cooling.flow_rate_lpm",      [](const cryocooler_TelemetryFrame& frame) { return frame.cooling.flow_rate_lpm; }},
    {"imu.x",                      [](const cryocooler_TelemetryFrame& frame) { return frame.imu.x; }},
    {"imu.y",                      [](const cryocooler_TelemetryFrame& frame) { return frame.imu.y; }},
    {"imu.z",                      [](const cryocooler_TelemetryFrame& frame) { return frame.imu.z; }},
    {"imu.accel_mag",              [](const cryocooler_TelemetryFrame& frame) { return frame.imu.accel_mag; }},
    {"imu.freq_hz",                [](const cryocooler_TelemetryFrame& frame) { return frame.imu.freq_hz; }},
    {"system.cpu_usage_percent",   [](const cryocooler_TelemetryFrame& frame) { return frame.system.cpu_usage_percent; }},
    {"system.heap_usage_percent",  [](const cryocooler_TelemetryFrame& frame) { return frame.system.heap_usage_percent; }},
    {"system.psram_usage_percent", [](const cryocooler_TelemetryFrame& frame) { return frame.system.psram_usage_percent; }},
};

static_assert(sizeof(CHANNELS) / sizeof(CHANNELS[0]) == run_history::CHANNEL_COUNT,
              "CHANNELS must have run_history::CHANNEL_COUNT entries");
static_assert(run_history::CHANNEL_COUNT <= sizeof(cryocooler_HistorySample{}.values) / sizeof(float),
              "raise HistorySample.values max_count in telemetry.options");
static_assert(run_history::CHANNEL_COUNT <= sizeof(cryocooler_RunHistoryHeader{}.channels)
                                            / sizeof(cryocooler_RunHistoryHeader{}.channels[0]),
              "raise RunHistoryHeader.channels max_count in telemetry.options");

// ─── State ────────────────────────────────────────────────────────────────────

static run_history::Ring          sRing;
static portMUX_TYPE               sRingLock      = portMUX_INITIALIZER_UNLOCKED;
static uint32_t                   sBootId        = 0;
static uint32_t                   sLastSampleMs  = 0;
static bool                       sHasSampled    = false;
static cryocooler_TelemetryFrame  sFrame;   // fillFrame() scratch, loop() only

// ─── Lifecycle ────────────────────────────────────────────────────────────────

module::InitStatus init() {
    const size_t bytes = static_cast<size_t>(RUN_RECORDER_CAPACITY) * sizeof(run_history::Sample);
    auto* storage = static_cast<run_history::Sample*>(heap_caps_malloc(bytes, MALLOC_CAP_SPIRAM));
    if (storage == nullptr) {
        _Log.printf("PSRAM allocation of %u bytes failed, recorder off\n",
                    static_cast<unsigned>(bytes));
        return module::MODULE_INIT_HARDWARE_ERROR;
    }
    sRing.attach(storage, RUN_RECORDER_CAPACITY);
    sBootId = esp_random();
    _Log.printf("Recording %u samples every %u ms in %u KB of PSRAM\n",
                static_cast<unsigned>(RUN_RECORDER_CAPACITY),
                static_cast<unsigned>(RUN_RECORDER_PERIOD_MS),
                static_cast<unsigned>(bytes / 1024u));
    return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    if (!Module::isInitialized()) return module::MODULE_SERVICE_SKIPPED;

    const uint32_t nowMs = tick::nowMs();
    if (sHasSampled && nowMs - sLastSampleMs < RUN_RECORDER_PERIOD_MS) {
        return module::MODULE_SERVICE_SKIPPED;
    }
    sLastSampleMs = nowMs;
    sHasSampled   = true;

    telemetry::fillFrame(sFrame);
    float values[run_history::CHANNEL_COUNT];
    for (size_t index = 0; index < run_history::CHANNEL_COUNT; ++index) {
        values[index] = CHANNELS[index].read(sFrame);
    }
    const auto stateId = static_cast<int8_t>(sFrame.state.id);

    portENTER_CRITICAL(&sRingLock);
    sRing.push(nowMs, stateId, values);
    portEXIT_CRITICAL(&sRingLock);
    return module::MODULE_SERVICE_OK;
}

// ─── /api/history streaming ───────────────────────────────────────────────────

/// Per-request cursor. Encodes one message at a time and hands it out in chunks.
class HistoryStream {
public:
    explicit HistoryStream(uint32_t fromSeq) {
        portENTER_CRITICAL(&sRingLock);
        const uint32_t oldestSeq = sRing.oldestSeq();
        endSeq_ = sRing.endSeq();
        portEXIT_CRITICAL(&sRingLock);
        nextSeq_ = fromSeq < oldestSeq ? oldestSeq : fromSeq;
        if (nextSeq_ > endSeq_) nextSeq_ = endSeq_;
        encodeHeader();
    }

    /// AwsResponseFiller body: returns bytes written, 0 when done.
    size_t fill(uint8_t* buffer, size_t maxLen) {
        size_t written = 0;
        while (written < maxLen) {
            if (pendingPos_ == pendingLen_ && !encodeNextSample()) break;
            const size_t chunk = std::min(pendingLen_ - pendingPos_, maxLen - written);
            memcpy(buffer + written, pending_ + pendingPos_, chunk);
            pendingPos_ += chunk;
            written     += chunk;
        }
        return written;
    }

private:
    void encodeHeader() {
        cryocooler_RunHistoryHeader header = cryocooler_RunHistoryHeader_init_zero;
        header.boot_id        = sBootId;
        header.first_seq      = nextSeq_;
        header.end_seq        = endSeq_;
        header.channels_count = run_history::CHANNEL_COUNT;
        for (size_t index = 0; index < run_history::CHANNEL_COUNT; ++index) {
            strlcpy(header.channels[index], CHANNELS[index].key, sizeof(header.channels[index]));
        }
        encode(cryocooler_RunHistoryHeader_fields, &header);
    }

    /// Encode the next sample still in the ring. Returns false when none are left.
    bool encodeNextSample() {
        run_history::Sample sample{};
        while (nextSeq_ < endSeq_) {
            portENTER_CRITICAL(&sRingLock);
            const bool     found  = sRing.copyAt(nextSeq_, sample);
            const uint32_t oldest = sRing.oldestSeq();
            portEXIT_CRITICAL(&sRingLock);
            if (found) break;
            // Overwritten while streaming: jump to the oldest sample still held.
            nextSeq_ = oldest > nextSeq_ ? oldest : nextSeq_ + 1;
        }
        if (nextSeq_ >= endSeq_) return false;
        ++nextSeq_;

        cryocooler_HistorySample message = cryocooler_HistorySample_init_zero;
        message.seq          = sample.seq;
        message.uptime_ms    = sample.uptimeMs;
        message.state_id     = sample.stateId;
        message.values_count = run_history::CHANNEL_COUNT;
        memcpy(message.values, sample.values, sizeof(sample.values));
        return encode(cryocooler_HistorySample_fields, &message);
    }

    bool encode(const pb_msgdesc_t* fields, const void* message) {
        pb_ostream_t stream = pb_ostream_from_buffer(pending_, sizeof(pending_));
        pendingPos_ = 0;
        pendingLen_ = pb_encode_ex(&stream, fields, message, PB_ENCODE_DELIMITED)
                    ? stream.bytes_written : 0;
        return pendingLen_ > 0;
    }

    uint8_t  pending_[640];   // header with all channel keys is the largest message
    size_t   pendingLen_ = 0;
    size_t   pendingPos_ = 0;
    uint32_t nextSeq_    = 0;
    uint32_t endSeq_     = 0;
};

void registerRoutes(AsyncWebServer& server) {
    server.on("/api/history", HTTP_GET, [](AsyncWebServerRequest* request) {
        if (!Module::isInitialized()) {
            request->send(503, "application/json", "{\"error\":\"run recorder unavailable\"}");
            return;
        }
        uint32_t fromSeq = 0;
        if (request->hasParam("from")) {
            fromSeq = strtoul(request->getParam("from")->value().c_str(), nullptr, 10);
        }
        auto stream = std::make_shared<HistoryStream>(fromSeq);
        AsyncWebServerResponse* response = request->beginChunkedResponse(
            "application/x-protobuf",
            [stream](uint8_t* buffer, size_t maxLen, size_t) { return stream->fill(buffer, maxLen); });
        response->addHeader("Cache-Control", "no-store");
        // Lets the Vite dev server read it; the WebSocket already serves this data to any origin.
        response->addHeader("Access-Control-Allow-Origin", "*");
        request->send(response);
    });
}

} // namespace run_recorder
