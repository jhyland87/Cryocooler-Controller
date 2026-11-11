/**
 * @file historyStore.ts
 * @brief Columnar chart history keyed by device uptime, with min/max decimation.
 *
 * One Float64Array time column (device uptime, ms) and one Float32Array per
 * channel (NaN = no valid reading). Holds up to a day at 1 Hz in about 7 MB,
 * where an array of {t, v} objects per channel would take ~75 MB.
 *
 * Times are stored as device uptime so samples recorded before NTP sync stay in
 * place; DataPoint.t adds the device's boot epoch (`clockOffsetMs`) when read.
 */

import type { DataPoint, TelemetryData } from '../types/telemetry';
import { getField } from '../types/telemetry';

// ─── Types ────────────────────────────────────────────────────────────────────

/** A block of samples, sorted by uptime, to merge into the store. */
export interface HistoryBatch {
  /** Device uptime (ms) of each sample, ascending. */
  uptimeMs: Float64Array;
  /** One column per channel key, same length as `uptimeMs`; NaN = no reading. */
  columns: Record<string, Float32Array>;
}

// ─── Configuration ────────────────────────────────────────────────────────────

/** Samples kept: 24 h at 1 Hz, matching the firmware's RUN_RECORDER_CAPACITY. */
export const HISTORY_CAPACITY = 86_400;

/** Extra slots so trimming happens once per SLACK pushes, not every push. */
const SLACK = 4_096;

/** A live frame's boot-epoch estimate must move this far to count as a clock step (NTP sync). */
const CLOCK_STEP_MS = 2_000;

// ─── Store ────────────────────────────────────────────────────────────────────

/**
 * Fixed-capacity history for a set of telemetry keys.
 *
 * @example
 * const store = new HistoryStore(['cold_head.temp_c']);
 * store.push(frame, Date.now());
 * store.getSeries('cold_head.temp_c', 120_000, 600);  // last 2 min, ≤ 1200 points
 */
export class HistoryStore {
  /** Wall-clock ms of device boot (wall time = uptime + offset); undefined until the first frame. */
  clockOffsetMs: number | undefined = undefined;

  private times: Float64Array;
  private readonly columns = new Map<string, Float32Array>();
  private length = 0;
  /** Samples dropped from the front so far; keeps bucket boundaries fixed as the store trims. */
  private dropped = 0;

  constructor(readonly keys: readonly string[], readonly capacity = HISTORY_CAPACITY) {
    this.times = new Float64Array(capacity + SLACK);
    for (const key of keys) {
      this.columns.set(key, new Float32Array(capacity + SLACK));
    }
  }

  /** Number of samples held. */
  get size(): number {
    return this.length;
  }

  /** Time from the oldest to the newest sample (ms). */
  get spanMs(): number {
    return this.length > 1 ? this.times[this.length - 1] - this.times[0] : 0;
  }

  /** Device uptime (ms) of the newest sample, or undefined when empty. */
  get latestUptimeMs(): number | undefined {
    return this.length > 0 ? this.times[this.length - 1] : undefined;
  }

  /** Drop every sample (e.g. after the device rebooted). */
  reset(): void {
    this.length = 0;
    this.dropped = 0;
  }

  /**
   * Append a live telemetry frame.
   *
   * Frames without `system.uptime_ms` are ignored. An uptime that goes
   * backwards means the device rebooted, so the store is cleared first.
   *
   * @param data    Decoded telemetry frame.
   * @param wallMs  Frame timestamp (ms since epoch), used to track the boot epoch.
   */
  push(data: TelemetryData, wallMs: number): void {
    const uptimeMs = data.system?.uptime_ms;
    if (typeof uptimeMs !== 'number') return;

    const offset = wallMs - uptimeMs;
    if (this.clockOffsetMs === undefined || Math.abs(offset - this.clockOffsetMs) > CLOCK_STEP_MS) {
      this.clockOffsetMs = offset;
    }

    const latest = this.latestUptimeMs;
    if (latest !== undefined && uptimeMs < latest) this.reset();
    if (latest !== undefined && uptimeMs === latest) return;

    if (this.length === this.times.length) this.trim();
    const index = this.length;
    this.times[index] = uptimeMs;
    for (const [key, column] of this.columns) {
      const value = getField(data, key);
      column[index] = typeof value === 'number' ? value : NaN;
    }
    this.length = index + 1;
  }

  /**
   * Merge recorded history. The batch replaces any samples inside its time
   * range; samples before and after it are kept.
   *
   * @param batch  Samples sorted by uptime.
   */
  merge(batch: HistoryBatch): void {
    const batchLength = batch.uptimeMs.length;
    if (batchLength === 0) return;
    const firstMs = batch.uptimeMs[0];
    const lastMs  = batch.uptimeMs[batchLength - 1];

    const before = this.lowerBound(firstMs);
    const after  = this.upperBound(lastMs);
    const tail   = this.length - after;
    const total  = before + batchLength + tail;
    const skip   = Math.max(0, total - this.capacity);  // oldest samples that no longer fit

    const times = new Float64Array(this.times.length);
    const merged = new Map<string, Float32Array>();
    for (const key of this.keys) merged.set(key, new Float32Array(this.times.length));

    // Write the three ranges, dropping the first `skip` samples overall.
    let out = 0;
    let dropRemaining = skip;
    const append = (source: Float64Array, columnFor: (key: string) => Float32Array | undefined,
                    start: number, end: number): void => {
      for (let index = start; index < end; index += 1) {
        if (dropRemaining > 0) { dropRemaining -= 1; continue; }
        times[out] = source[index];
        for (const key of this.keys) {
          const column = columnFor(key);
          const target = merged.get(key);
          if (target !== undefined) target[out] = column !== undefined ? column[index] : NaN;
        }
        out += 1;
      }
    };
    append(this.times, (key) => this.columns.get(key), 0, before);
    append(batch.uptimeMs, (key) => batch.columns[key], 0, batchLength);
    append(this.times, (key) => this.columns.get(key), after, this.length);

    this.times = times;
    for (const [key, column] of merged) this.columns.set(key, column);
    this.dropped += skip;
    this.length = out;
  }

  /**
   * Points for one channel over the trailing window, decimated to at most
   * `2 * maxBuckets` points by keeping each bucket's min and max. Every key
   * gets the same timestamps for the same arguments, so series line up.
   *
   * @param key         Channel key, e.g. 'cold_head.temp_c'.
   * @param windowMs    Trailing window in ms; undefined = everything held.
   * @param maxBuckets  Bucket limit (about the chart's width in pixels / 2).
   * @returns Points with wall-clock `t` (ms since epoch); `v` null for gaps.
   */
  getSeries(key: string, windowMs: number | undefined, maxBuckets: number): DataPoint[] {
    const column = this.columns.get(key);
    if (column === undefined || this.length === 0) return [];
    const offset = this.clockOffsetMs ?? 0;
    const start = windowMs === undefined
      ? 0
      : this.lowerBound(this.times[this.length - 1] - windowMs);
    const count = this.length - start;

    const points: DataPoint[] = [];
    if (count <= 2 * maxBuckets) {
      for (let index = start; index < this.length; index += 1) {
        points.push({ t: this.times[index] + offset, v: toNullable(column[index]) });
      }
      return points;
    }

    // Bucket on absolute sample numbers so boundaries don't shift as the window slides.
    const bucketSize = Math.ceil(count / maxBuckets);
    let index = start;
    while (index < this.length) {
      const absolute = index + this.dropped;
      const bucketEnd = Math.min(this.length, index + bucketSize - (absolute % bucketSize));
      let minIndex = -1;
      let maxIndex = -1;
      for (let inner = index; inner < bucketEnd; inner += 1) {
        const value = column[inner];
        if (Number.isNaN(value)) continue;
        if (minIndex < 0 || value < column[minIndex]) minIndex = inner;
        if (maxIndex < 0 || value > column[maxIndex]) maxIndex = inner;
      }
      const firstT = this.times[index] + offset;
      const lastT  = this.times[bucketEnd - 1] + offset;
      if (minIndex < 0) {
        points.push({ t: firstT, v: null }, { t: lastT, v: null });
      } else {
        const [earlier, later] = minIndex <= maxIndex ? [minIndex, maxIndex] : [maxIndex, minIndex];
        points.push({ t: firstT, v: column[earlier] }, { t: lastT, v: column[later] });
      }
      index = bucketEnd;
    }
    return points;
  }

  /**
   * The newest `count` raw points for one channel (for sparklines).
   *
   * @param key    Channel key.
   * @param count  Number of points.
   * @returns Points with wall-clock `t`; `v` null for gaps.
   */
  getRecent(key: string, count: number): DataPoint[] {
    const column = this.columns.get(key);
    if (column === undefined) return [];
    const offset = this.clockOffsetMs ?? 0;
    const points: DataPoint[] = [];
    for (let index = Math.max(0, this.length - count); index < this.length; index += 1) {
      points.push({ t: this.times[index] + offset, v: toNullable(column[index]) });
    }
    return points;
  }

  /** Keep the newest `capacity` samples, moving them to the front. */
  private trim(): void {
    const drop = this.length - this.capacity;
    if (drop <= 0) return;
    this.times.copyWithin(0, drop, this.length);
    for (const column of this.columns.values()) column.copyWithin(0, drop, this.length);
    this.length -= drop;
    this.dropped += drop;
  }

  /** First index whose time is >= `uptimeMs`. */
  private lowerBound(uptimeMs: number): number {
    let low = 0;
    let high = this.length;
    while (low < high) {
      const mid = (low + high) >>> 1;
      if (this.times[mid] < uptimeMs) low = mid + 1;
      else high = mid;
    }
    return low;
  }

  /** First index whose time is > `uptimeMs`. */
  private upperBound(uptimeMs: number): number {
    let low = 0;
    let high = this.length;
    while (low < high) {
      const mid = (low + high) >>> 1;
      if (this.times[mid] <= uptimeMs) low = mid + 1;
      else high = mid;
    }
    return low;
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toNullable(value: number): number | null {
  return Number.isNaN(value) ? null : value;
}
