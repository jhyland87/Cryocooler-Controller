/**
 * @file useHistoryBuffer.ts
 * @brief Holds one HistoryStore for the lifetime of the component.
 */

import { useRef } from 'preact/hooks';
import { HistoryStore } from '../utils/historyStore';

/**
 * Create the chart history store once, for a fixed set of telemetry keys.
 *
 * The store mutates in place and never triggers a render; callers re-render
 * after `push` / `merge` (App bumps a tick counter).
 *
 * @param keys  Telemetry keys to keep, e.g. ['cold_head.temp_c']. Read once at mount.
 * @returns The same HistoryStore on every render.
 */
export function useHistoryBuffer(keys: readonly string[]): HistoryStore {
  const storeRef = useRef<HistoryStore | null>(null);
  if (storeRef.current === null) storeRef.current = new HistoryStore(keys);
  return storeRef.current;
}
