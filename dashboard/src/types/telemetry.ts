/**
 * Flat telemetry object received over WebSocket (/ws) or HTTP (/api/telemetry).
 * Keys use dot-notation matching the FrameBuilder / dashboard_config.h names.
 * All fields are optional — modules that have not yet initialised emit empty
 * strings, which the JSON parser will omit from the resulting object.
 */
export interface TelemetryData {
  // ── Timestamp ───────────────────────────────────────────────────────────────
  'timestamp.epoch'?: number;   // seconds since Unix epoch (from ESP32 RTC)
  'timestamp.local'?: string;   // human-readable local time string

  // ── State machine ───────────────────────────────────────────────────────────
  'state.id'?: number;
  'state.name'?: string;
  'state.status_text'?: string;

  // ── Status ──────────────────────────────────────────────────────────────────
  'status.on_duration'?: string;
  'status.time_in_state'?: string;
  'status.backoff_count'?: number;

  // ── Cold head temperatures & performance ────────────────────────────────────
  'cold_head.temp_k'?: number;
  'cold_head.temp_c'?: number;
  'cold_head.ambient_temp_c'?: number;
  'cold_head.cooling_rate'?: number;
  'cold_head.delta_below_ambient_c'?: number;
  'cold_head.cooldown_pct'?: number;

  // ── Cold head power ─────────────────────────────────────────────────────────
  'cold_head.voltage_v'?: number;
  'cold_head.current_a'?: number;

  // ── System power & resources ────────────────────────────────────────────────
  'system.voltage_v'?: number;   // alias — firmware actually emits voltage_vdc
  'system.voltage_vdc'?: number; // actual ESP32 key
  'system.current_a'?: number;
  'system.power_w'?: number;
  'system.cpu_usage_percent'?: number;
  'system.cpu_freq_mhz'?: number;
  'system.heap_usage_percent'?: number;
  'system.psram_usage_percent'?: number;
  'system.total_heap_bytes'?: number;
  'system.total_psram_bytes'?: number;
  'system.uptime_ms'?: number;
  'system.num_cores'?: number;

  // ── Cooling loop ────────────────────────────────────────────────────────────
  'cooling.fan_speed'?: number;
  'cooling.fan_rpm'?: number;
  'cooling.pump_on'?: number;
  'cooling.temp_c'?: number;
  'cooling.flow_rate_lpm'?: number;

  // ── IMU / accelerometer ─────────────────────────────────────────────────────
  'imu.x'?: number;         // alias — firmware actually emits roll_deg/pitch_deg/yaw_deg
  'imu.y'?: number;
  'imu.z'?: number;
  'imu.roll_deg'?: number;  // actual ESP32 key
  'imu.pitch_deg'?: number;
  'imu.yaw_deg'?: number;
  'imu.accel_mag'?: number;
  'imu.motion'?: number;

  // ── Amplifier ───────────────────────────────────────────────────────────────
  'amplifier.target_v'?: number;
  'amplifier.voltage_v'?: number;

  // ── Relay & indicators ──────────────────────────────────────────────────────
  'relay.normal'?: number;
  'relay.alarm'?: number;
  'indicator.fault'?: number;
  'indicator.ready'?: number;

  // ── Compressor ──────────────────────────────────────────────────────────────
  'compressor.status'?: number;

  // ── Fault counters ──────────────────────────────────────────────────────────
  'faults.count_10m'?: number;
  'faults.count_30m'?: number;
  'faults.count_60m'?: number;

  // ── Sysinfo (secondary INA power monitor) ───────────────────────────────────
  'sysinfo.voltage_v'?: number;

  // Allow accessing arbitrary string keys for forward-compatibility.
  [key: string]: number | string | undefined;
}

/** A timestamped snapshot appended to every rolling history buffer. */
export interface DataPoint {
  /** Wall-clock time at which the snapshot was taken (ms since epoch). */
  t: number;
  v: number;
}

export type HistoryMap = Record<string, DataPoint[]>;
