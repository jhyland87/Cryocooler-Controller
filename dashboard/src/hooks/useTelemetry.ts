import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import type { TelemetryData } from '../types/telemetry';
import { decodeTelemetryFrame } from '../utils/decodeTelemetry';

// ─── Connection state ─────────────────────────────────────────────────────────

export type ConnectionStatus = 'connecting' | 'connected' | 'polling' | 'error';

export interface TelemetryState {
  data: TelemetryData;
  status: ConnectionStatus;
  lastUpdate: number | null;
  /** Frames received since last mount */
  frameCount: number;
}

// ─── Configuration ────────────────────────────────────────────────────────────

/** How often (ms) to poll /api/telemetry when WebSocket is unavailable. */
const POLL_INTERVAL_MS = 1000;

/** WebSocket reconnect delay (ms) after an unexpected close. */
const WS_RECONNECT_MS = 3000;

/**
 * Target ESP32 hostname.
 *
 * Always connect to the ESP32's mDNS hostname so the dashboard works
 * correctly whether it's being served from the ESP32 itself, opened from a
 * local file, or run via the Vite dev server (`npm run dev`).
 *
 * Change this if your ESP32 uses a different hostname (see HOSTNAME in
 * include/config.h / include/arduino_secrets.h).
 */
const ESP32_HOST = 'cryocooler.local';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${ESP32_HOST}/ws`;
}

function apiUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${proto}//${ESP32_HOST}/api/telemetry`;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * useTelemetry
 *
 * Connects to the ESP32 WebSocket endpoint (ws://<host>/ws) and maintains a
 * live TelemetryData object.  If WebSocket is unavailable (firmware without
 * WebSocket support, or network issue), the hook transparently falls back to
 * polling GET /api/telemetry every second.
 *
 * The hook cleans up the WebSocket and polling timer on unmount.
 */
export function useTelemetry(): TelemetryState & { onData: (cb: (d: TelemetryData, ts: number) => void) => void } {
  const [data, setData]             = useState<TelemetryData>({});
  const [status, setStatus]         = useState<ConnectionStatus>('connecting');
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [frameCount, setFrameCount] = useState(0);

  const wsRef       = useRef<WebSocket | null>(null);
  const pollRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef  = useRef(true);
  const onDataCbRef = useRef<((d: TelemetryData, ts: number) => void) | null>(null);

  /** Register a callback that fires on every new telemetry frame. */
  const onData = useCallback((cb: (d: TelemetryData, ts: number) => void) => {
    onDataCbRef.current = cb;
  }, []);

  /** Apply a decoded TelemetryData frame to React state. */
  const applyFrame = useCallback((frame: TelemetryData) => {
    if (!mountedRef.current) return;
    const epochSec = frame.timestamp?.epoch;
    const now = typeof epochSec === 'number' ? epochSec * 1000 : Date.now();
    setData(frame);
    setLastUpdate(now);
    setFrameCount((c) => c + 1);
    onDataCbRef.current?.(frame, now);
  }, []);

  /** Handle a JSON text frame (used by HTTP polling fallback). */
  const handleFrame = useCallback((raw: string) => {
    try {
      // /api/telemetry already returns a nested JSON object matching TelemetryData.
      const frame = JSON.parse(raw) as TelemetryData;
      applyFrame(frame);
    } catch {
      // Silently drop malformed frames.
    }
  }, [applyFrame]);

  /** Handle a Protobuf binary frame (used by WebSocket). */
  const handleProtobufFrame = useCallback((buf: ArrayBuffer) => {
    try {
      const frame = decodeTelemetryFrame(new Uint8Array(buf));
      applyFrame(frame);
    } catch {
      // Silently drop malformed frames.
    }
  }, [applyFrame]);

  // ── Polling fallback ───────────────────────────────────────────────────────

  const startPolling = useCallback(() => {
    if (pollRef.current) return; // already polling
    if (!mountedRef.current) return;
    setStatus('polling');

    const tick = async () => {
      if (!mountedRef.current) return;
      try {
        const res = await fetch(apiUrl());
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        handleFrame(await res.text());
        if (status !== 'polling') setStatus('polling');
      } catch {
        if (mountedRef.current) setStatus('error');
      }
    };

    tick();
    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
  }, [handleFrame, status]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // ── WebSocket connection ───────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');

    const ws = new WebSocket(wsUrl());
    ws.binaryType = 'arraybuffer'; // Receive Protobuf binary frames
    wsRef.current = ws;

    ws.addEventListener('open', () => {
      if (!mountedRef.current) { ws.close(); return; }
      setStatus('connected');
      stopPolling(); // WebSocket is working — stop polling
    });

    ws.addEventListener('message', (ev: MessageEvent) => {
      if (ev.data instanceof ArrayBuffer) {
        // Binary frame → Protobuf
        handleProtobufFrame(ev.data);
      } else {
        // Text frame → JSON (backward compatibility)
        handleFrame(typeof ev.data === 'string' ? ev.data : String(ev.data));
      }
    });

    ws.addEventListener('close', () => {
      if (!mountedRef.current) return;
      setStatus('polling');
      // Fall back to polling while we wait to reconnect.
      startPolling();
      // Schedule a reconnect attempt.
      setTimeout(connect, WS_RECONNECT_MS);
    });

    ws.addEventListener('error', () => {
      // 'close' fires after 'error', so the reconnect logic lives there.
      // Start polling immediately so the dashboard stays live.
      startPolling();
    });
  }, [handleFrame, handleProtobufFrame, startPolling, stopPolling]);

  useEffect(() => {
    mountedRef.current = true;

    // Try WebSocket first; polling is the fallback.
    connect();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
      wsRef.current = null;
      stopPolling();
    };
    // connect / stopPolling are stable refs — exhaustive-deps warning is a
    // false positive here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, status, lastUpdate, frameCount, onData };
}
