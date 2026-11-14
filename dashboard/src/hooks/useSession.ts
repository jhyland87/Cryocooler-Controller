/**
 * @file useSession.ts
 * @brief Whether the board has a dashboard password, and logging out.
 */

import { useCallback, useEffect, useState } from 'preact/hooks';
import { deviceFetch } from '../utils/esp32Host';

function isSessionReply(value: unknown): value is { passwordSet: boolean } {
  return typeof value === 'object' && value !== null && 'passwordSet' in value &&
    typeof value.passwordSet === 'boolean';
}

/**
 * Asks the board once whether a dashboard password is set.
 *
 * @returns `logout`, defined only when there is a session to end; calling it
 *          ends the session on the board and opens the login page.
 */
export function useSession(): { logout: (() => void) | undefined } {
  const [passwordSet, setPasswordSet] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await deviceFetch('/api/session', { cache: 'no-store' });
        const reply: unknown = response.ok ? await response.json() : undefined;
        if (!cancelled && isSessionReply(reply)) {
          setPasswordSet(reply.passwordSet);
        }
      } catch {
        // Unreachable, or older firmware: no log-out button is the right default.
      }
    };
    void load();
    return () => { cancelled = true; };
  }, []);

  const logout = useCallback(() => {
    const end = async () => {
      try {
        await deviceFetch('/api/logout', { method: 'POST' });
      } finally {
        window.location.replace('/login');
      }
    };
    void end();
  }, []);

  return { logout: passwordSet ? logout : undefined };
}
