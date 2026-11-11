/**
 * @file useRunHistory.ts
 * @brief Load the device's recorded run history into the chart store on every (re)connect.
 */

import { useEffect, useRef } from 'preact/hooks';
import { decodeRunHistory } from '../utils/decodeRunHistory';
import { deviceHttpUrl } from '../utils/esp32Host';
import type { HistoryStore } from '../utils/historyStore';

/**
 * Fetch GET /api/history whenever `connectionCount` changes and merge it into
 * `store`. After the first load only the gap since the last fetch is
 * requested (`?from=`). A new boot id means the device rebooted, so the store
 * is cleared and the whole history fetched again.
 *
 * @param store            Chart history store to fill.
 * @param connectionCount  From useTelemetry; bumps on each (re)connect.
 * @param onMerged         Called after new history lands, to trigger a render.
 */
export function useRunHistory(store: HistoryStore, connectionCount: number, onMerged: () => void): void {
  const bootIdRef   = useRef<number | undefined>(undefined);
  const nextSeqRef  = useRef(0);

  useEffect(() => {
    if (connectionCount === 0) return;
    // A newer connection aborts this fetch; refs only advance on success, so it re-asks for the same gap.
    const controller = new AbortController();

    const fetchFrom = async (fromSeq: number) => {
      const response = await fetch(deviceHttpUrl(`/api/history?from=${fromSeq}`), {
        cache: 'no-store',
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return decodeRunHistory(new Uint8Array(await response.arrayBuffer()), store.keys);
    };

    const load = async () => {
      try {
        const knownBoot = bootIdRef.current;
        let history = await fetchFrom(knownBoot === undefined ? 0 : nextSeqRef.current);
        if (knownBoot !== undefined && history.bootId !== knownBoot) {
          store.reset();
          history = await fetchFrom(0);
        }
        bootIdRef.current  = history.bootId;
        nextSeqRef.current = history.endSeq;
        store.merge(history.batch);
        onMerged();
      } catch {
        // Recorder off, request aborted or device unreachable: charts keep live data only.
      }
    };
    void load();

    return () => controller.abort();
  }, [connectionCount, store, onMerged]);
}
