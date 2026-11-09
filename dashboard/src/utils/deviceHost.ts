/**
 * @file deviceHost.ts
 * @brief Resolves the host the dashboard talks to (WebSocket and HTTP API).
 */

/** mDNS name of the ESP32; must match HOSTNAME in include/config/config.h. */
const ESP32_MDNS_HOST = 'cryocooler.local';

/** Hostnames that mean the page is not being served by the ESP32 itself. */
const NON_DEVICE_HOSTNAMES = new Set(['localhost', '127.0.0.1', '[::1]', '']);

/**
 * Host (with port) of the ESP32. When the page is served by the device, reuse
 * the address the browser already reached it on (IP or mDNS name), so the
 * sockets never wait on a second mDNS lookup. Vite dev and file:// fall back
 * to the mDNS name.
 *
 * @returns The host to connect to, without protocol.
 * @example
 * // page opened at http://192.168.1.40/
 * deviceHost(); // '192.168.1.40'
 * // page opened from the Vite dev server at http://localhost:5173/
 * deviceHost(); // 'cryocooler.local'
 * @category Utilities
 * @group Network
 * @source
 */
export function deviceHost(): string {
  const { protocol, hostname, host } = window.location;
  const servedOverHttp = protocol === 'http:' || protocol === 'https:';
  if (!servedOverHttp || NON_DEVICE_HOSTNAMES.has(hostname)) {
    return ESP32_MDNS_HOST;
  }
  return host;
}

/**
 * Base URL for HTTP API requests to the ESP32, matching the page's protocol.
 *
 * @returns Protocol and host with no trailing slash.
 * @example
 * // page opened at http://cryocooler.local/
 * deviceHttpBase(); // 'http://cryocooler.local'
 * @category Utilities
 * @group Network
 * @source
 */
export function deviceHttpBase(): string {
  const proto = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${proto}//${deviceHost()}`;
}
