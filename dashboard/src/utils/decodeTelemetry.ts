/**
 * @file decodeTelemetry.ts
 * @brief Decode Protobuf binary telemetry frames into nested TelemetryData.
 */

import { cryocooler } from '../generated/telemetry';
import type { TelemetryData } from '../types/telemetry';

type Frame = cryocooler.ITelemetryFrame;

// protobufjs represents int64/uint64 as Long objects; convert to JS number.
function toLong(v: number | Long | null | undefined): number | undefined {
  if (v === null || v === undefined) return undefined;
  if (typeof v === 'object' && 'toNumber' in v) return v.toNumber();
  return v as number;
}

interface Long { toNumber(): number; }

/**
 * Decode a Protobuf binary WebSocket frame into a nested TelemetryData object.
 */
export function decodeTelemetryFrame(buffer: Uint8Array): TelemetryData {
  const f: Frame = cryocooler.TelemetryFrame.decode(buffer);
  const out: TelemetryData = {};

  if (f.timestamp) {
    out.timestamp = {
      epoch: toLong(f.timestamp.epoch),
      local: f.timestamp.local ?? undefined,
    };
  }

  if (f.state) {
    out.state = {
      id:          f.state.id ?? undefined,
      name:        f.state.name ?? undefined,
      status_text: f.state.statusText ?? undefined,
    };
  }

  if (f.status) {
    out.status = {
      on_duration_ms: f.status.onDurationMs ?? undefined,
      on_duration:    f.status.onDuration ?? undefined,
      time_in_state:  f.status.timeInState ?? undefined,
      backoff_count:  f.status.backoffCount ?? undefined,
    };
  }

  if (f.coldHead) {
    out.cold_head = {
      // Only include temp_c when the sensor is healthy (has_temp flag).
      // A sensor fault sets has_temp=false so the dashboard shows no reading
      // rather than a spurious 0°C (proto3 default).
      temp_c:                f.coldHead.hasTemp ? (f.coldHead.tempC ?? undefined) : undefined,
      cooling_rate:          f.coldHead.coolingRate ?? undefined,
      cooldown_pct:          f.coldHead.cooldownPct ?? undefined,
      delta_below_ambient_c: f.coldHead.deltaBelowAmbientC ?? undefined,
      ambient_temp_c:        f.coldHead.ambientTempC ?? undefined,
      voltage_v:             f.coldHead.voltageV ?? undefined,
      current_a:             f.coldHead.currentA ?? undefined,
    };
  }

  if (f.amplifier) {
    out.amplifier = {
      voltage_v: f.amplifier.voltageV ?? undefined,
      current_a: f.amplifier.currentA ?? undefined,
    };
  }

  if (f.system) {
    out.system = {
      voltage_v:           f.system.voltageV ?? undefined,
      current_a:           f.system.currentA ?? undefined,
      power_w:             f.system.powerW ?? undefined,
      cpu_usage_percent:   f.system.cpuUsagePercent ?? undefined,
      cpu_freq_mhz:        f.system.cpuFreqMhz ?? undefined,
      heap_usage_percent:  f.system.heapUsagePercent ?? undefined,
      psram_usage_percent: f.system.psramUsagePercent ?? undefined,
      total_heap_bytes:    f.system.totalHeapBytes ?? undefined,
      total_psram_bytes:   f.system.totalPsramBytes ?? undefined,
      uptime_ms:           toLong(f.system.uptimeMs),
      num_cores:           f.system.numCores ?? undefined,
    };
  }

  if (f.imu) {
    out.imu = {
      roll_deg:  f.imu.rollDeg ?? undefined,
      pitch_deg: f.imu.pitchDeg ?? undefined,
      yaw_deg:   f.imu.yawDeg ?? undefined,
      accel_mag: f.imu.accelMag ?? undefined,
      motion:    f.imu.motion ?? undefined,
      temp_c:    f.imu.tempC ?? undefined,
      x:         f.imu.x ?? undefined,
      y:         f.imu.y ?? undefined,
      z:         f.imu.z ?? undefined,
    };
  }

  if (f.cooling) {
    out.cooling = {
      status:        f.cooling.status ?? undefined,
      pump_on:       f.cooling.pumpOn ?? undefined,
      temp_c:        f.cooling.tempC ?? undefined,
      flow_rate_lpm: f.cooling.flowRateLpm ?? undefined,
      fan_speed:     f.cooling.fanSpeed ?? undefined,
      fan_rpm:       f.cooling.fanRpm ?? undefined,
      pump_speed:    f.cooling.pumpSpeed ?? undefined,
      pump_rpm:      f.cooling.pumpRpm ?? undefined,
    };
  }

  if (f.compressor) {
    out.compressor = { status: f.compressor.status ?? undefined };
  }

  if (f.relay) {
    out.relay = {
      compressor_state: f.relay.compressorState ?? undefined,
      amplifier_state:  f.relay.amplifierState ?? undefined,
    };
  }

  if (f.indicator) {
    out.indicator = {
      fault: f.indicator.fault ?? undefined,
      ready: f.indicator.ready ?? undefined,
    };
  }

  if (f.faults) {
    out.faults = {
      count_10m: f.faults.count_10m ?? undefined,
      count_30m: f.faults.count_30m ?? undefined,
      count_60m: f.faults.count_60m ?? undefined,
    };
  }

  if (f.firmware) {
    out.firmware = {
      version:         f.firmware.version ?? undefined,
      build_date:      f.firmware.buildDate ?? undefined,
      ota_flash_ts:    toLong(f.firmware.otaFlashTs),
      ota_flash_local: f.firmware.otaFlashLocal ?? undefined,
    };
  }

  if (f.score?.cooling) {
    out.score = {
      cooling: {
        fan_speed:    f.score.cooling.fanSpeed ?? undefined,
        coolant_temp: f.score.cooling.coolantTemp ?? undefined,
        coolant_flow: f.score.cooling.coolantFlow ?? undefined,
        worst:        f.score.cooling.worst ?? undefined,
      },
    };
  }

  if (f.modules) {
    const entries: [string, cryocooler.IModuleEntry | null | undefined][] = [
      ['hardware',      f.modules.hardware],
      ['sysinfo',       f.modules.sysinfo],
      ['imu',           f.modules.imu],
      ['cooling',       f.modules.cooling],
      ['dashboard',     f.modules.dashboard],
      ['cold_head',     f.modules.coldHead],
      ['indicator',     f.modules.indicator],
      ['state_machine', f.modules.stateMachine],
      ['commands',      f.modules.commands],
      ['telemetry',     f.modules.telemetry],
    ];
    out.mod = {};
    for (const [name, entry] of entries) {
      if (entry) {
        out.mod[name] = {
          init:    entry.init    ?? undefined,
          service: entry.service ?? undefined,
        };
      }
    }
  }

  if (window.LOG_TELEMETRY === true) {
    console.log('decodeTelemetryFrame', out);
  }

  return out;
}
