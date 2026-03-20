import { useRef, useCallback } from 'preact/hooks';
import type { DataPoint, HistoryMap, TelemetryData } from '../types/telemetry';
import { getField } from '../types/telemetry';

/** Number of samples to retain per channel (60 s at 1 Hz). */
export const HISTORY_LENGTH = 100;

/** Total rolling window in milliseconds — used by charts to pin the x-axis domain. */
export const HISTORY_WINDOW_MS = HISTORY_LENGTH * 1_000;

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
        const raw = getField(data, key);
        const buf = buffers.current[key];
        // Always push — valid readings get a number, failed reads get null.
        // Null values render as gaps in the chart line while keeping the
        // x-axis advancing in sync with other series.
        buf.push({ t: timestamp, v: typeof raw === 'number' ? raw : null });
        if (buf.length > HISTORY_LENGTH) buf.shift();
      }
    },
    // keys array identity is fixed at mount time — no need to re-run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  /**
   * Returns a shallow copy of the buffer for `key`.
   *
   * A copy is returned (not the live reference) so that chart components
   * receive a new array identity on each re-render and can diff/animate
   * incrementally rather than treating every render as a "same data" no-op.
   */
  const getHistory = useCallback((key: string): DataPoint[] => {
    return [...(buffers.current[key] ?? [])];
  }, []);

  return { push, getHistory };
}
