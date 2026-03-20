import type { TelemetryData } from './telemetry';

// ─── useTelemetry ────────────────────────────────────────────────────────────

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

export interface TelemetryState {
  data: TelemetryData;
  status: ConnectionStatus;
  lastUpdate: number | null;
  /** Frames received since last mount */
  frameCount: number;
}

// ─── useConsoleLogs ──────────────────────────────────────────────────────────

export interface LogEntry {
  /** Device uptime in milliseconds when the line was flushed (from millis()). */
  ms: number;
  /** Unix epoch seconds (UTC).  0 until SNTP syncs. */
  epoch: number;
  /** Log message text (may include a trailing newline). */
  text: string;
}

// ─── useFaultHistory ─────────────────────────────────────────────────────────

import type { FaultRecord } from './faultHistory';

export interface FaultHistoryState {
  faults:  FaultRecord[];
  loading: boolean;
}
