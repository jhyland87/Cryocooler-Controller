import { useState, useEffect, useCallback } from 'preact/hooks';
import type { FaultRecord, FaultHistoryMessage } from '../types/faultHistory';
import type { FaultHistoryState } from '../types/hooks';

// Re-export for existing consumers
export type { FaultHistoryState } from '../types/hooks';

const ESP32_HOST = 'cryocooler.local';

function faultHistoryUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${proto}//${ESP32_HOST}/api/fault-history`;
}

/**
 * useFaultHistory
 *
 * Fetches the initial fault history snapshot from /api/fault-history on mount.
 * Exposes a `pushUpdate` callback that the WS message router can call whenever
 * a fault_history text frame arrives — this replaces the entire list with the
 * latest server-side snapshot.
 */
export function useFaultHistory(): FaultHistoryState & { pushUpdate: (msg: FaultHistoryMessage) => void } {
  const [faults, setFaults]   = useState<FaultRecord[]>([]);
  const [loading, setLoading] = useState(true);

  // Initial HTTP fetch
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(faultHistoryUrl());
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json() as FaultHistoryMessage;
        if (!cancelled) setFaults(json.records ?? []);
      } catch {
        // Silently ignore — WS pushes will populate the list when available.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // WS push handler — replaces the full list (server sends all records)
  const pushUpdate = useCallback((msg: FaultHistoryMessage) => {
    setFaults(msg.records ?? []);
    setLoading(false);
  }, []);

  return { faults, loading, pushUpdate };
}
