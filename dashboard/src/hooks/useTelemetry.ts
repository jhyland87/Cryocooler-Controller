import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import type { TelemetryData } from '../types/telemetry';
import type { ConnectionStatus, TelemetryState } from '../types/hooks';
import { decodeTelemetryFrame } from '../utils/decodeTelemetry';
import type { FaultHistoryMessage } from '../types/faultHistory';
import { isFaultHistoryMessage } from '../types/faultHistory';

// Re-export types so existing consumers don't break
export type { ConnectionStatus, TelemetryState } from '../types/hooks';

// ─── Configuration ────────────────────────────────────────────────────────────

/** WebSocket reconnect delay (ms) after an unexpected close. */
const WS_RECONNECT_MS = 3000;

/**
 * If no WS message arrives within this window, treat the connection as dead.
 * The ESP32 sends frames at 1 Hz, so 5 s of silence means the device is gone
 * (e.g. unplugged) even though the browser hasn't fired a 'close' event yet.
 */
const STALE_TIMEOUT_MS = 5000;

/** How often (ms) to check for staleness. */
const STALE_CHECK_MS = 2000;

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

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * useTelemetry
 *
 * Connects to the ESP32 WebSocket endpoint (ws://<host>/ws) and maintains a
 * live TelemetryData object.  WebSocket is the only transport — no HTTP
 * polling.  When the WebSocket disconnects, the hook shows 'disconnected'
 * status and attempts to reconnect automatically.
 */
export function useTelemetry(): TelemetryState & {
  onData: (cb: (d: TelemetryData, ts: number) => void) => void;
  onFaultHistory: (cb: (msg: FaultHistoryMessage) => void) => void;
} {
  const [data, setData]             = useState<TelemetryData>({});
  const [status, setStatus]         = useState<ConnectionStatus>('connecting');
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [frameCount, setFrameCount] = useState(0);

  const wsRef        = useRef<WebSocket | null>(null);
  const mountedRef   = useRef(true);
  const lastMsgRef   = useRef<number>(0);  // Date.now() of last WS message
  const statusRef    = useRef<ConnectionStatus>('connecting');
  const staleRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** True once we've been connected at least once — prevents reconnect
   *  attempts from briefly flashing 'connecting' and hiding the overlay. */
  const wasConnectedRef = useRef(false);
  const onDataCbRef         = useRef<((d: TelemetryData, ts: number) => void) | null>(null);
  const onFaultHistoryCbRef = useRef<((msg: FaultHistoryMessage) => void) | null>(null);

  /** Update both the ref (for use inside callbacks) and state (for render). */
  const updateStatus = useCallback((s: ConnectionStatus) => {
    statusRef.current = s;
    setStatus(s);
  }, []);

  /** Register a callback that fires on every new telemetry frame. */
  const onData = useCallback((cb: (d: TelemetryData, ts: number) => void) => {
    onDataCbRef.current = cb;
  }, []);

  /** Register a callback that fires on fault_history WS text frames. */
  const onFaultHistory = useCallback((cb: (msg: FaultHistoryMessage) => void) => {
    onFaultHistoryCbRef.current = cb;
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

  /** Handle a Protobuf binary frame (used by WebSocket). */
  const handleProtobufFrame = useCallback((buf: ArrayBuffer) => {
    try {
      const frame = decodeTelemetryFrame(new Uint8Array(buf));
      applyFrame(frame);
    } catch {
      // Silently drop malformed frames.
    }
  }, [applyFrame]);

  // ── WebSocket connection ───────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Clean up any previous socket that hasn't fully closed yet.
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Only show 'connecting' on the very first attempt.  After we've been
    // connected once, stay in 'disconnected' until a message actually arrives
    // so the overlay doesn't flicker away during failed reconnect attempts.
    if (!wasConnectedRef.current) {
      updateStatus('connecting');
    }

    const ws = new WebSocket(wsUrl());
    ws.binaryType = 'arraybuffer'; // Receive Protobuf binary frames
    wsRef.current = ws;

    ws.addEventListener('open', () => {
      if (!mountedRef.current) { ws.close(); return; }
      lastMsgRef.current = Date.now();
      // Don't set 'connected' here — wait for the first message so we know
      // the device is truly alive (open can succeed even if the device is
      // about to go away).
    });

    ws.addEventListener('message', (ev: MessageEvent) => {
      lastMsgRef.current = Date.now();

      // Transition to 'connected' on the first real message.
      if (statusRef.current !== 'connected') {
        wasConnectedRef.current = true;
        updateStatus('connected');

        // (Re)start the staleness watchdog.
        if (staleRef.current) clearInterval(staleRef.current);
        staleRef.current = setInterval(() => {
          if (!mountedRef.current) return;
          if (Date.now() - lastMsgRef.current > STALE_TIMEOUT_MS) {
            ws.close(); // force-close the zombie socket
          }
        }, STALE_CHECK_MS);
      }

      if (ev.data instanceof ArrayBuffer) {
        // Binary frame → Protobuf telemetry
        handleProtobufFrame(ev.data);
      } else {
        // Text frame → typed JSON dispatch (e.g. fault_history)
        const raw = typeof ev.data === 'string' ? ev.data : String(ev.data);
        try {
          const parsed = JSON.parse(raw);
          if (isFaultHistoryMessage(parsed)) {
            onFaultHistoryCbRef.current?.(parsed);
          }
        } catch {
          // Not valid JSON — ignore
        }
      }
    });

    ws.addEventListener('close', () => {
      if (staleRef.current) { clearInterval(staleRef.current); staleRef.current = null; }
      if (!mountedRef.current) return;
      updateStatus('disconnected');
      reconnectRef.current = setTimeout(connect, WS_RECONNECT_MS);
    });

    ws.addEventListener('error', () => {
      // 'close' fires after 'error', so the reconnect logic lives there.
    });
  }, [handleProtobufFrame, updateStatus]);

  useEffect(() => {
    mountedRef.current = true;

    connect();

    return () => {
      mountedRef.current = false;
      if (staleRef.current) { clearInterval(staleRef.current); staleRef.current = null; }
      if (reconnectRef.current) { clearTimeout(reconnectRef.current); reconnectRef.current = null; }
      wsRef.current?.close();
      wsRef.current = null;
    };
    // connect is a stable ref — exhaustive-deps warning is a false positive.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, status, lastUpdate, frameCount, onData, onFaultHistory };
}
