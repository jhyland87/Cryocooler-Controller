/**
 * @file esp32Host.ts
 * @brief Where the dashboard reaches the ESP32.
 *
 * Always the device's mDNS hostname, so the dashboard works whether it's served
 * from the ESP32, opened from a file, or run on the Vite dev server. Must match
 * HOSTNAME in include/config.h / include/arduino_secrets.h.
 */

/** ESP32 mDNS hostname. */
const ESP32_HOST = 'cryocooler.local';

/**
 * HTTP(S) URL for a device endpoint, matching the page's scheme.
 *
 * @param path  Absolute path, e.g. '/api/history?from=0'.
 * @returns Full URL, e.g. 'http://cryocooler.local/api/history?from=0'.
 */
export function deviceHttpUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${proto}//${ESP32_HOST}${path}`;
}

/**
 * WebSocket URL for a device endpoint, matching the page's scheme.
 *
 * @param path  Absolute path, e.g. '/ws'.
 * @returns Full URL, e.g. 'ws://cryocooler.local/ws'.
 */
export function deviceWsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${ESP32_HOST}${path}`;
}
