/**
 * @file mockTelemetry.ts
 * @brief Generated telemetry frames for running the dashboard with no board.
 *
 * Dev server only (`?mock`); useTelemetry loads it with a dynamic import so it
 * stays out of the firmware bundle.
 */

import type { TelemetryData } from '../types/telemetry';

// ─── Simulated run ────────────────────────────────────────────────────────────

const AMBIENT_C = 22;
const TARGET_C = -195;
/** Time constant of the simulated cooldown (ms); short so the charts move. */
const COOLDOWN_TAU_MS = 180_000;

/** The simulated amplifier reading drops out for this long (ms) ... */
const DROPOUT_MS = 6_000;
/** ... once every this long (ms), to show gaps in the charts. */
const DROPOUT_PERIOD_MS = 45_000;

/** Simulated overstroke: two hits at the start of each period, then hold and decay. */
const BACKOFF_PERIOD_MS = 100_000;
const BACKOFF_STEP_PCT = 4.9;
const BACKOFF_HOLD_MS = 30_000;
const BACKOFF_TAU_MS = 10_000;

/** Back-off (% of drive) and hit count, shaped like the firmware's step, hold and decay. */
function mockBackoff(elapsedMs: number): { pct: number; count: number } {
  const cycles = Math.floor(elapsedMs / BACKOFF_PERIOD_MS);
  const inCycleMs = elapsedMs % BACKOFF_PERIOD_MS;
  const hits = inCycleMs < 3_000 ? 1 : 2;
  const pastHoldMs = Math.max(0, inCycleMs - 3_000 - BACKOFF_HOLD_MS);
  const pct = hits * BACKOFF_STEP_PCT * Math.exp(-pastHoldMs / BACKOFF_TAU_MS);
  return { pct: pct < 0.05 ? 0 : pct, count: cycles * 2 + hits };
}

/** Slow sine with a period in seconds, in the range -1..1. */
function wave(elapsedMs: number, periodS: number): number {
  return Math.sin((elapsedMs / 1000) * ((2 * Math.PI) / periodS));
}

function formatDuration(elapsedMs: number): string {
  const totalS = Math.floor(elapsedMs / 1000);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(Math.floor(totalS / 3600))}:${pad(Math.floor(totalS / 60) % 60)}:${pad(totalS % 60)}`;
}

/**
 * Build one telemetry frame for a simulated cooldown.
 *
 * @param elapsedMs  Time since the mock started; used as the device uptime.
 * @returns A frame with every group the dashboard displays.
 * @example
 * mockFrame(0).cold_head?.temp_c; // 22 (ambient), falling toward -195
 */
export function mockFrame(elapsedMs: number): TelemetryData {
  const remaining = Math.exp(-elapsedMs / COOLDOWN_TAU_MS);
  const tempC = TARGET_C + (AMBIENT_C - TARGET_C) * remaining;
  const coolingRate = (-(AMBIENT_C - TARGET_C) * remaining * 60_000) / COOLDOWN_TAU_MS;

  const cryoVolts = 21 + 0.4 * wave(elapsedMs, 40);
  const cryoAmps = 3.2 + 0.8 * remaining + 0.1 * wave(elapsedMs, 13);
  const cryoPowerFactor = 0.8 + 0.05 * wave(elapsedMs, 29);
  const systemVolts = 12.05 + 0.03 * wave(elapsedMs, 25);
  const systemAmps = 1.4 + 0.15 * wave(elapsedMs, 17);
  const duration = formatDuration(elapsedMs);
  const backoff = mockBackoff(elapsedMs);
  const amplifierOnline = elapsedMs % DROPOUT_PERIOD_MS < DROPOUT_PERIOD_MS - DROPOUT_MS;

  return {
    state: { id: 3, name: 'MOCK COOLDOWN', status_text: 'Stubbed data, no board' },
    status: { on_duration_ms: elapsedMs, on_duration: duration, time_in_state: duration,
      backoff_count: backoff.count, backoff_pct: backoff.pct },
    cold_head: {
      temp_c: tempC,
      ambient_temp_c: AMBIENT_C + 0.3 * wave(elapsedMs, 90),
      cooling_rate: coolingRate,
      cooldown_pct: (1 - remaining) * 100,
      voltage_v: amplifierOnline ? cryoVolts : undefined,
      current_a: amplifierOnline ? cryoAmps : undefined,
      target_temp_c: TARGET_C,
    },
    amplifier: amplifierOnline
      ? {
          voltage_v: cryoVolts,
          current_a: cryoAmps,
          power_w: cryoVolts * cryoAmps,
          active_power_w: cryoVolts * cryoAmps * cryoPowerFactor,
          power_factor: cryoPowerFactor,
          back_emf_v: cryoVolts * 0.85,
          commanded_voltage_v: cryoVolts + 1.5,
        }
      : {},
    system: {
      voltage_v: systemVolts,
      current_a: systemAmps,
      power_w: systemVolts * systemAmps,
      cpu_usage_percent: 28 + 10 * wave(elapsedMs, 11),
      cpu_freq_mhz: 240,
      heap_usage_percent: 41 + 3 * wave(elapsedMs, 31),
      psram_usage_percent: 12 + 2 * wave(elapsedMs, 47),
      total_heap_bytes: 327_680,
      total_psram_bytes: 8_388_608,
      uptime_ms: elapsedMs,
      num_cores: 2,
    },
    imu: {
      roll_deg: 0.4,
      pitch_deg: -0.2,
      yaw_deg: 0,
      accel_mag: 1 + 0.05 * wave(elapsedMs, 3),
      motion: 0,
      temp_c: 31,
      x: 0.03 * wave(elapsedMs, 3),
      y: 0.02 * wave(elapsedMs, 5),
      z: 1 + 0.04 * wave(elapsedMs, 4),
      freq_hz: 60,
    },
    cooling: {
      status: 1,
      pump_on: 1,
      temp_c: 26 + 2 * wave(elapsedMs, 120),
      flow_rate_lpm: 1.8 + 0.1 * wave(elapsedMs, 19),
      fan_speed: 65 + 10 * wave(elapsedMs, 60),
      fan_rpm: 1800,
      pump_speed: 80,
      pump_rpm: 3200,
    },
    compressor: { status: 1 },
    relay: { compressor_state: 1, amplifier_state: 1 },
    indicator: { fault: 0, ready: 0 },
    faults: { count_10m: 0, count_30m: 0, count_60m: 0 },
    firmware: { version: 'mock', build_date: '' },
    network: { hostname: 'cryocooler', ip: '192.168.0.42', ssid: 'MockNet', rssi_dbm: -58, connected: true },
    log_epoch: 0,
  };
}
