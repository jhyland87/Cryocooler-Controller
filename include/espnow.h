/**
 * @file espnow.h
 * @brief ESP-NOW peer-to-peer telemetry bridge.
 *
 * Forwards the JSON telemetry snapshot to a single configured peer ESP32
 * over ESP-NOW while WiFi (STA mode), the HTTP dashboard, and OTA firmware
 * updates continue to operate normally.  Both transports share the same radio;
 * the ESP-NOW channel follows the AP channel automatically.
 *
 * ── Fragmentation protocol ───────────────────────────────────────────────────
 * ESP-NOW frames are limited to 250 bytes.  Each outbound JSON burst is split
 * into chunks of up to 246 bytes.  Every chunk carries a 4-byte header:
 *
 *   Byte 0  msg_id        Rolling counter (0–255) — groups chunks of one message.
 *   Byte 1  total_chunks  How many chunks make up this message.
 *   Byte 2  chunk_index   Zero-based position of this chunk (0 … total-1).
 *   Byte 3  payload_len   Bytes of JSON that follow in this frame (1–246).
 *   Bytes 4+              UTF-8 JSON fragment.
 *
 * The peer reassembles chunks that share the same msg_id in chunk_index order
 * to recover the original JSON string.
 *
 * ── Peer channel requirement ─────────────────────────────────────────────────
 * The peer ESP32 must operate on the same WiFi channel as this device's AP.
 * If the peer is not connected to the same AP, configure it explicitly with:
 *   esp_wifi_set_channel(<channel>, WIFI_SECOND_CHAN_NONE)
 * where <channel> is the value reported by WiFi.channel() on this device.
 *
 * ── Enable / configure ───────────────────────────────────────────────────────
 *   ENABLE_ESPNOW       true / false (default false — set peer MAC first)
 *   ESPNOW_PEER_MAC     6-byte MAC of the receiving device
 *   ESPNOW_SEND_INTERVAL_MS  Burst period in milliseconds (default 1000)
 *
 * All three are defined in config.h.
 */

#pragma once

#include "config.h"
#include "module.h"

#if ENABLE_ESPNOW

namespace espnow {

/**
 * Initialise ESP-NOW, register the send callback, and add the peer.
 *
 * Must be called after WiFi has connected (i.e. after dashboard::init()).
 * Pins a FreeRTOS task to Core 0 that serialises, fragments, and transmits
 * telemetry at ESPNOW_SEND_INTERVAL_MS.
 *
 * Returns:
 *   MODULE_INIT_SUCCESS          — ready to transmit.
 *   MODULE_INIT_DEPENDENCY_ERROR — WiFi not connected, or esp_now_init()/
 *                                  esp_now_add_peer() returned an error.
 */
module::InitStatus init();

/**
 * No-op stub — the ESP-NOW task self-schedules on Core 0.
 * Present so espnow::Module satisfies the ModuleBase interface.
 */
module::ServiceStatus service();

/** Total successful chunk deliveries (cumulative since boot). */
uint32_t getSentCount();

/** Total chunk delivery failures (cumulative since boot). */
uint32_t getFailCount();

/** True once init() has completed successfully. */
bool isReady();

// ── Module interface ──────────────────────────────────────────────────────────

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return espnow::init(); }
    static module::ServiceStatus service() { return espnow::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace espnow

#endif // ENABLE_ESPNOW
