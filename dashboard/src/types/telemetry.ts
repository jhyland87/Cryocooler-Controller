declare global {
  interface Window {
    LOG_TELEMETRY?: boolean;
  }
}

// ─── Nested telemetry object ───────────────────────────────────────────────────

export interface TelemetryData {
  timestamp?: {
    epoch?: number;    // seconds since Unix epoch (from ESP32 RTC)
    local?: string;    // "YYYY-MM-DD HH:MM:SS"
  };

  state?: {
    id?: number;
    name?: string;
    status_text?: string;
  };

  status?: {
    on_duration_ms?: number;
    on_duration?: string;     // HH:MM:SS
    time_in_state?: string;   // HH:MM:SS
    backoff_count?: number;
  };

  cold_head?: {
    temp_c?: number;
    ambient_temp_c?: number;
    cooling_rate?: number;
    cooldown_pct?: number;
    voltage_v?: number;
    current_a?: number;
    target_temp_c?: number;
  };

  amplifier?: {
    voltage_v?: number;
    current_a?: number;
    power_w?:   number;
  };

  system?: {
    voltage_v?: number;
    current_a?: number;
    power_w?: number;
    cpu_usage_percent?: number;
    cpu_freq_mhz?: number;
    heap_usage_percent?: number;
    psram_usage_percent?: number;
    total_heap_bytes?: number;
    total_psram_bytes?: number;
    uptime_ms?: number;
    num_cores?: number;
  };

  imu?: {
    roll_deg?: number;
    pitch_deg?: number;
    yaw_deg?: number;
    accel_mag?: number;
    motion?: number;
    temp_c?: number;
    x?: number;
    y?: number;
    z?: number;
    freq_hz?: number;
  };

  cooling?: {
    status?: number;
    pump_on?: number;
    temp_c?: number;
    flow_rate_lpm?: number;
    fan_speed?: number;
    fan_rpm?: number;
    pump_speed?: number;
    pump_rpm?: number;
  };

  compressor?: {
    status?: number;
  };

  relay?: {
    compressor_state?: number;
    amplifier_state?: number;
    normal?: number;
    alarm?: number;
  };

  indicator?: {
    fault?: number;
    ready?: number;
  };

  faults?: {
    count_10m?: number;
    count_30m?: number;
    count_60m?: number;
  };

  firmware?: {
    version?: string;
    build_date?: string;
    ota_flash_ts?: number;
    ota_flash_local?: string;
  };

  score?: {
    cooling?: {
      fan_speed?: number;
      coolant_temp?: number;
      coolant_flow?: number;
      worst?: number;
    };
  };

  mod?: {
    [module: string]: {
      init?: string;
      service?: string;
    };
  };

  /** Epoch (Unix seconds) of the most recent log entry; 0 = none. */
  log_epoch?: number;
}

// ─── Path traversal helper ────────────────────────────────────────────────────

/**
 * Read a value from a nested TelemetryData object using a dot-notation path.
 *
 * Lets the history buffer and tile config reference fields by string path
 * (e.g. 'cold_head.temp_c') without caring about nesting depth.
 */
export function getField(data: TelemetryData, path: string): number | string | undefined {
  const parts = path.split('.');
  let current: unknown = data;
  for (const part of parts) {
    if (current === null || current === undefined || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  if (typeof current === 'number' || typeof current === 'string') return current;
  return undefined;
}

// ─── Supporting types ─────────────────────────────────────────────────────────

/** A timestamped snapshot appended to every rolling history buffer. */
export interface DataPoint {
  t: number;       // wall-clock ms since epoch
  v: number | null; // null = no valid reading (renders as a gap in charts)
}

export type HistoryMap = Record<string, DataPoint[]>;
