import type { ComponentChildren } from 'preact';
import type { DataPoint, TelemetryData } from './telemetry';
import type { FaultRecord } from './faultHistory';
import type { ConnectionStatus } from './hooks';

// ─── App ─────────────────────────────────────────────────────────────────────

export interface TileConfig {
  label: string;
  key:   string;
  unit:  string;
  dp:    number;
  color: string;
}

// ─── Header ──────────────────────────────────────────────────────────────────

export interface HeaderProps {
  connectionStatus:  ConnectionStatus;
  stateName:         string;
  statusText:        string;
  onDuration:        string;
  timeInState:       string;
  cooldownPct:       number | undefined;
  frameCount:        number;
  loading?:          boolean;
}

// ─── StatusPanel ─────────────────────────────────────────────────────────────

export interface LedProps {
  label:   string;
  active:  boolean;
  color:   string;
  tooltip?: string;
}

export interface StatusPanelProps {
  data: TelemetryData;
  loading?: boolean;
}

// ─── CollapsiblePanel ────────────────────────────────────────────────────────

export interface CollapsiblePanelProps {
  title: string;
  defaultExpanded?: boolean;
  expanded?: boolean;
  children: ComponentChildren;
}

// ─── ErrorBoundary ───────────────────────────────────────────────────────────

export interface ErrorBoundaryProps {
  children: ComponentChildren;
}

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  componentStack: string;
}

// ─── SparkCard ───────────────────────────────────────────────────────────────

export interface SparkCardProps {
  label: string;
  data:  DataPoint[];
  color: string;
  unit:  string;
  dp?:   number;
  gauge?: {
    max?:       number;
    warnAbove?: number;
  };
}

// ─── MultiSparkCard ──────────────────────────────────────────────────────────

export interface SeriesConfig {
  label: string;
  data:  DataPoint[];
  color: string;
}

export interface MultiSparkCardProps {
  label:  string;
  series: SeriesConfig[];
  unit:   string;
  dp?:    number;
}

// ─── TelemetryLineChart ──────────────────────────────────────────────────────

export interface ChartSeries {
  label:   string;
  data:    DataPoint[];
  color:   string;
  dashed?: boolean;
}

/** A horizontal time range to highlight on a TelemetryLineChart. */
export interface ChartOverlay {
  /** Period start, epoch ms. */
  start:  number;
  /** Period end, epoch ms. `null` = ongoing (clipped to current xMax). */
  end:    number | null;
  /** Short label rendered at the top of the band. */
  label:  string;
  /** Optional band tint. Defaults to a neutral gray. */
  color?: string;
}

export interface TelemetryLineChartProps {
  title:     string;
  series:    ChartSeries[];
  yAxis?: {
    min?: number;
    max?: number;
  };
  overlays?: ChartOverlay[];
  /** Trailing window shown on the x-axis (ms); undefined = all the data given. */
  windowMs?: number;
}

// ─── HistoryRangeToggle ──────────────────────────────────────────────────────

/** Chart time range: trailing 2 min, 30 min, 4 h, or the whole history. */
export type HistoryRangeId = '2m' | '30m' | '4h' | 'all';

export interface HistoryRangeToggleProps {
  value:    HistoryRangeId;
  onChange: (next: HistoryRangeId) => void;
  /** Time covered by the history held (ms); 0 hides the caption. */
  spanMs:   number;
}

// ─── VibrationWave ───────────────────────────────────────────────────────────

export interface VibrationWaveProps {
  accelMag: DataPoint[];
  freqHz: DataPoint[];
}

// ─── Chart wrappers ──────────────────────────────────────────────────────────

export interface TemperatureChartProps {
  actualC:   DataPoint[];
  ambientC:  DataPoint[];
  targetC:   DataPoint[];
  overlays?: ChartOverlay[];
  windowMs?: number;
}

export interface CoolingChartProps {
  fanSpeed:    DataPoint[];
  coolantTemp: DataPoint[];
  flowRate:    DataPoint[];
  overlays?:   ChartOverlay[];
  windowMs?:   number;
}

export interface PowerChartProps {
  coldHeadVolts: DataPoint[];
  coldHeadAmps:  DataPoint[];
  coldHeadWatts: DataPoint[];
  systemVolts:   DataPoint[];
  systemAmps:    DataPoint[];
  overlays?:     ChartOverlay[];
  windowMs?:     number;
}

// ─── Sparkline panels ────────────────────────────────────────────────────────

export interface AccelSparklinesProps {
  accelX:   DataPoint[];
  accelY:   DataPoint[];
  accelZ:   DataPoint[];
  accelMag: DataPoint[];
  freqHz:   DataPoint[];
  motion:   number | undefined;
}

export interface SystemSparklinesProps {
  cpuUsage:   DataPoint[];
  heapUsage:  DataPoint[];
  psramUsage: DataPoint[];
}

// ─── ConsoleLog ──────────────────────────────────────────────────────────────

export interface ConsoleLogProps {
  logEpoch?: number;
  loading?: boolean;
}

// ─── FaultHistoryPanel ───────────────────────────────────────────────────────

export interface FaultHistoryPanelProps {
  faults:  FaultRecord[];
  loading: boolean;
}
