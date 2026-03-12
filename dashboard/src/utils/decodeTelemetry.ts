/**
 * @file decodeTelemetry.ts
 * @brief Decode Protobuf binary telemetry frames into flat TelemetryData.
 *
 * Converts a Protobuf-encoded TelemetryFrame (received as a binary WebSocket
 * message) into the same flat dot-notation TelemetryData object that the
 * dashboard already uses.  Drop-in replacement for JSON.parse() + flatten().
 */

import { cryocooler } from '../generated/telemetry';
import type { TelemetryData } from '../types/telemetry';

type Frame = cryocooler.ITelemetryFrame;

/**
 * Helper: set a key in the flat object only if the value is meaningful.
 * Proto3 defaults (0, "") are kept since they can be legitimate values
 * (e.g. 0°C temperature).  Only undefined/null are skipped.
 */
function set(
  out: Record<string, number | string | undefined>,
  key: string,
  value: number | string | Long | null | undefined,
): void {
  if (value === null || value === undefined) return;
  // protobufjs uses Long for int64/sint64; convert to number
  if (typeof value === 'object' && 'toNumber' in value) {
    out[key] = (value as { toNumber(): number }).toNumber();
  } else {
    out[key] = value as number | string;
  }
}

// Long type from protobufjs (int64 fields)
interface Long {
  toNumber(): number;
}

/**
 * Decode a Protobuf binary frame and flatten to dot-notation TelemetryData.
 * Produces the exact same shape as the old JSON.parse() + flatten() pipeline.
 */
export function decodeTelemetryFrame(buffer: Uint8Array): TelemetryData {
  const frame: Frame = cryocooler.TelemetryFrame.decode(buffer);
  const out: Record<string, number | string | undefined> = {};

  // ── Timestamp ──────────────────────────────────────────────────────────────
  if (frame.timestamp) {
    set(out, 'timestamp.epoch', frame.timestamp.epoch);
    set(out, 'timestamp.local', frame.timestamp.local);
  }

  // ── State ──────────────────────────────────────────────────────────────────
  if (frame.state) {
    set(out, 'state.id', frame.state.id);
    set(out, 'state.name', frame.state.name);
    set(out, 'state.status_text', frame.state.statusText);
  }

  // ── Status ─────────────────────────────────────────────────────────────────
  if (frame.status) {
    set(out, 'status.on_duration_ms', frame.status.onDurationMs);
    set(out, 'status.on_duration', frame.status.onDuration);
    set(out, 'status.time_in_state', frame.status.timeInState);
    set(out, 'status.backoff_count', frame.status.backoffCount);
  }

  // ── Cold head ──────────────────────────────────────────────────────────────
  if (frame.coldHead) {
    // Only include temp_c if the sensor is healthy (has_temp == true).
    // When the sensor faults, the firmware sets has_temp = false and the
    // dashboard should treat temp_c as absent (undefined).
    if (frame.coldHead.hasTemp) {
      set(out, 'cold_head.temp_c', frame.coldHead.tempC);
    }
    set(out, 'cold_head.cooling_rate', frame.coldHead.coolingRate);
    set(out, 'cold_head.cooldown_pct', frame.coldHead.cooldownPct);
    set(out, 'cold_head.delta_below_ambient_c', frame.coldHead.deltaBelowAmbientC);
    set(out, 'cold_head.ambient_temp_c', frame.coldHead.ambientTempC);
    set(out, 'cold_head.voltage_v', frame.coldHead.voltageV);
    set(out, 'cold_head.current_a', frame.coldHead.currentA);
  }

  // ── Amplifier ──────────────────────────────────────────────────────────────
  if (frame.amplifier) {
    set(out, 'amplifier.voltage_v', frame.amplifier.voltageV);
    set(out, 'amplifier.current_a', frame.amplifier.currentA);
  }

  // ── System ─────────────────────────────────────────────────────────────────
  if (frame.system) {
    set(out, 'system.voltage_v', frame.system.voltageV);
    set(out, 'system.current_a', frame.system.currentA);
    set(out, 'system.power_w', frame.system.powerW);
  }

  // ── IMU ────────────────────────────────────────────────────────────────────
  if (frame.imu) {
    set(out, 'imu.roll_deg', frame.imu.rollDeg);
    set(out, 'imu.pitch_deg', frame.imu.pitchDeg);
    set(out, 'imu.yaw_deg', frame.imu.yawDeg);
    set(out, 'imu.accel_mag', frame.imu.accelMag);
    set(out, 'imu.temp_c', frame.imu.tempC);
    set(out, 'imu.motion', frame.imu.motion);
    set(out, 'imu.x', frame.imu.x);
    set(out, 'imu.y', frame.imu.y);
    set(out, 'imu.z', frame.imu.z);
  }

  // ── Cooling ────────────────────────────────────────────────────────────────
  if (frame.cooling) {
    set(out, 'cooling.status', frame.cooling.status);
    set(out, 'cooling.pump_on', frame.cooling.pumpOn);
    set(out, 'cooling.temp_c', frame.cooling.tempC);
    set(out, 'cooling.flow_rate_lpm', frame.cooling.flowRateLpm);
    set(out, 'cooling.fan_speed', frame.cooling.fanSpeed);
    set(out, 'cooling.fan_rpm', frame.cooling.fanRpm);
    set(out, 'cooling.pump_speed', frame.cooling.pumpSpeed);
    set(out, 'cooling.pump_rpm', frame.cooling.pumpRpm);
  }

  // ── Compressor ─────────────────────────────────────────────────────────────
  if (frame.compressor) {
    set(out, 'compressor.status', frame.compressor.status);
  }

  // ── Relay ──────────────────────────────────────────────────────────────────
  if (frame.relay) {
    set(out, 'relay.compressor_state', frame.relay.compressorState);
    set(out, 'relay.amplifier_state', frame.relay.amplifierState);
  }

  // ── Indicator ──────────────────────────────────────────────────────────────
  if (frame.indicator) {
    set(out, 'indicator.fault', frame.indicator.fault);
    set(out, 'indicator.ready', frame.indicator.ready);
  }

  // ── Faults ─────────────────────────────────────────────────────────────────
  if (frame.faults) {
    set(out, 'faults.count_10m', frame.faults.count_10m);
    set(out, 'faults.count_30m', frame.faults.count_30m);
    set(out, 'faults.count_60m', frame.faults.count_60m);
  }

  // ── Firmware ───────────────────────────────────────────────────────────────
  if (frame.firmware) {
    set(out, 'firmware.version', frame.firmware.version);
    set(out, 'firmware.build_date', frame.firmware.buildDate);
    set(out, 'firmware.ota_flash_ts', frame.firmware.otaFlashTs);
    set(out, 'firmware.ota_flash_local', frame.firmware.otaFlashLocal);
  }

  // ── Scores ─────────────────────────────────────────────────────────────────
  if (frame.score?.cooling) {
    set(out, 'score.cooling.fan_speed', frame.score.cooling.fanSpeed);
    set(out, 'score.cooling.coolant_temp', frame.score.cooling.coolantTemp);
    set(out, 'score.cooling.coolant_flow', frame.score.cooling.coolantFlow);
    set(out, 'score.cooling.worst', frame.score.cooling.worst);
  }

  // ── Module status ──────────────────────────────────────────────────────────
  if (frame.modules) {
    const mods = frame.modules;
    const entries: [string, cryocooler.IModuleEntry | null | undefined][] = [
      ['hardware', mods.hardware],
      ['sysinfo', mods.sysinfo],
      ['imu', mods.imu],
      ['cooling', mods.cooling],
      ['dashboard', mods.dashboard],
      ['cold_head', mods.coldHead],
      ['indicator', mods.indicator],
      ['state_machine', mods.stateMachine],
      ['commands', mods.commands],
      ['telemetry', mods.telemetry],
    ];
    for (const [name, entry] of entries) {
      if (entry) {
        set(out, `mod.${name}.init`, entry.init);
        set(out, `mod.${name}.service`, entry.service);
      }
    }
  }

  if ( window.LOG_TELEMETRY == true) {
    console.log('decodeTelemetryFrame', out);
  }
  return out as TelemetryData;
}
