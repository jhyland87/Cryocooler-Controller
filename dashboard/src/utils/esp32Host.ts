/**
 * @file esp32Host.ts
 * @brief Where the dashboard reaches the ESP32.
 *
 * Always the device's mDNS hostname, so the dashboard works whether it's served
 * from the ESP32, opened from a file, or run on the Vite dev server. The name
 * comes from HOSTNAME in include/config/config.h (injected by vite.config.ts).
 */

declare const __ESP32_HOSTNAME__: string;

/** ESP32 mDNS hostname. */
export const ESP32_HOST = `${__ESP32_HOSTNAME__}.local`;
