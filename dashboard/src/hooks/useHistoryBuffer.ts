import { useRef, useCallback } from 'preact/hooks';
import type { DataPoint, HistoryMap, TelemetryData } from '../types/telemetry';

/** Number of samples to retain per channel (60 s at 1 Hz). */
const HISTORY_LENGTH = 60;

/**
 * Maintains a fixed-length rolling history buffer for a set of numeric
 * telemetry keys.
 *
 * Returns a stable `push` function that appends the latest telemetry snapshot
 * and a stable `getHistory` function that returns the current buffer for a
 * given key.
 */
export function useHistoryBuffer(keys: ReadonlyArray<string>) {
  const buffers = useRef<HistoryMap>(
    Object.fromEntries(keys.map((k) => [k, [] as DataPoint[]]))
  );

  const push = useCallback(
    (data: TelemetryData, timestamp: number) => {
      for (const key of keys) {
        const raw = data[key];
        if (typeof raw !== 'number') continue;

        const buf = buffers.current[key];
        buf.push({ t: timestamp, v: raw });
        if (buf.length > HISTORY_LENGTH) buf.shift();
      }
    },
    // keys array identity is fixed at mount time — no need to re-run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const getHistory = useCallback((key: string): DataPoint[] => {
    return buffers.current[key] ?? [];
  }, []);

  return { push, getHistory };
}
