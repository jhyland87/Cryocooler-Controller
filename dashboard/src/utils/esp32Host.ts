/**
 * @file esp32Host.ts
 * @brief Where the dashboard reaches the ESP32.
 *
 * A page served by the ESP32 talks back to the address it was loaded from, so
 * the browser's login for that address covers every request. Opened from a file
 * or run on the Vite dev server, it uses the device's mDNS name, which comes
 * from HOSTNAME in include/config/config.h (both injected by vite.config.ts).
 * That second case can't log in, so it only works with no dashboard password.
 *
 * With a password set the board answers a logged-out request with 401;
 * deviceFetch() then sends the browser to the board's login page.
 */

declare const __ESP32_HOSTNAME__: string;
declare const __DEV_SERVER__: boolean;

/** True when this page was loaded from the ESP32 itself. */
const SERVED_BY_DEVICE = !__DEV_SERVER__ && window.location.host !== '';

/** Host (and port) the ESP32 is reached at. */
const ESP32_HOST = SERVED_BY_DEVICE ? window.location.host : `${__ESP32_HOSTNAME__}.local`;

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

/**
 * fetch() for a device endpoint. From a page served by the board it marks the
 * request as the dashboard's own, and a 401 reply sends the browser to the
 * login page.
 *
 * @param path  Absolute path, e.g. '/api/fault-history'.
 * @param init  Usual fetch options.
 * @returns The response, including a 401 one.
 */
export async function deviceFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!SERVED_BY_DEVICE) {
    // A custom header would force a cross-origin preflight the board doesn't answer.
    return fetch(deviceHttpUrl(path), init);
  }
  const headers = new Headers(init.headers);
  headers.set('X-Dashboard', '1');
  const response = await fetch(deviceHttpUrl(path), { ...init, headers });
  if (response.status === 401) {
    window.location.replace('/login');
  }
  return response;
}
