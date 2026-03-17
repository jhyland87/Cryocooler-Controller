import { useState, useEffect, useRef, useCallback } from 'preact/hooks';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface LogEntry {
  /** Device uptime in milliseconds when the line was flushed (from millis()). */
  ms: number;
  /** Unix epoch seconds (UTC).  0 until SNTP syncs. */
  epoch: number;
  /** Log message text (may include a trailing newline). */
  text: string;
}

// ─── Configuration ────────────────────────────────────────────────────────────

/** Maximum number of log entries retained in the browser. */
const MAX_ENTRIES = 500;

/**
 * Target ESP32 hostname — must match HOSTNAME in include/config.h.
 * The hook always connects to the ESP32 directly so it works whether the
 * page is served from the device, a file:// URL, or the Vite dev server.
 */
const ESP32_HOST = 'cryocooler.local';

function apiUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${proto}//${ESP32_HOST}/api/telemetry`;
}

/** Stable fingerprint for deduplication: ms + first 60 chars of text. */
function fingerprint(e: LogEntry): string {
  return `${e.ms}:${e.text.slice(0, 60)}`;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * useConsoleLogs
 *
 * Event-driven console log fetcher.  Watches the `logEpoch` value from the
 * Protobuf WebSocket stream.  When `logEpoch` increases (meaning the server
 * has new log entries), it fetches /api/telemetry once to retrieve the latest
 * `logs` array.  No polling — HTTP is only called when the WebSocket signals
 * new logs are available.
 *
 * @param logEpoch  The `log_epoch` field from the latest telemetry WS frame.
 */
export function useConsoleLogs(logEpoch: number | undefined): { entries: LogEntry[]; clear: () => void } {
  const [entries, setEntries] = useState<LogEntry[]>([]);

  const mountedRef       = useRef(true);
  const lastFetchedEpoch = useRef<number>(0);
  /** Fingerprints of every entry returned by the most-recent successful fetch. */
  const prevBatchRef     = useRef<Set<string>>(new Set());

  const fetchLogs = useCallback(async () => {
    if (!mountedRef.current) return;
    try {
      const res = await fetch(apiUrl());
      if (!res.ok) return;

      const raw = await res.json() as Record<string, unknown>;
      const logsRaw = raw['logs'];
      if (!Array.isArray(logsRaw) || logsRaw.length === 0) return;

      // Parse and validate each entry.
      const batch: LogEntry[] = logsRaw.flatMap((item: unknown) => {
        if (typeof item !== 'object' || item === null) return [];
        const e = item as Record<string, unknown>;
        const ms    = typeof e['ms']    === 'number' ? e['ms']    : 0;
        const epoch = typeof e['epoch'] === 'number' ? e['epoch'] : 0;
        const text  = typeof e['text']  === 'string' ? e['text']  : '';
        return [{ ms, epoch, text }];
      });

      // Diff: keep only entries absent from the previous batch.
      const currentBatchPrints = new Set(batch.map(fingerprint));
      const newEntries = batch.filter(e => !prevBatchRef.current.has(fingerprint(e)));

      // Always advance the window — even if nothing is new this tick.
      prevBatchRef.current = currentBatchPrints;

      if (newEntries.length === 0) return;

      setEntries(prev => {
        const combined = [...prev, ...newEntries];
        return combined.length > MAX_ENTRIES
          ? combined.slice(combined.length - MAX_ENTRIES)
          : combined;
      });
    } catch {
      // Silently swallow network / parse errors — the panel just stops updating.
    }
  }, []);

  // Only fetch when logEpoch increases (WS signals new logs are available)
  useEffect(() => {
    if (logEpoch === undefined || logEpoch === 0) return;
    if (logEpoch <= lastFetchedEpoch.current) return;
    lastFetchedEpoch.current = logEpoch;
    fetchLogs();
  }, [logEpoch, fetchLogs]);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const clear = useCallback(() => {
    setEntries([]);
    prevBatchRef.current = new Set();
  }, []);

  return { entries, clear };
}
