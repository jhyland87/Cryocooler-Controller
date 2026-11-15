/**
 * @file decodeRunHistory.ts
 * @brief Decode a GET /api/history body into a HistoryBatch.
 *
 * The body is one length-delimited RunHistoryHeader, then length-delimited
 * HistorySample messages, oldest first (proto/telemetry.proto).
 */

import { Reader } from 'protobufjs/minimal';
import { cryocooler } from '../generated/telemetry';
import type { HistoryBatch } from './historyStore';

/** A decoded /api/history response. */
export interface RunHistory {
  /** Random per device boot; a change means the device restarted. */
  bootId: number;
  /** Sequence number to ask for next (`?from=`). */
  endSeq: number;
  /** Samples mapped onto the requested keys. */
  batch: HistoryBatch;
}

/**
 * Decode an /api/history body, keeping only `keys`. Channels the device didn't
 * send come back as NaN columns.
 *
 * @param body  Response bytes.
 * @param keys  Telemetry keys to extract, e.g. ['cold_head.temp_c'].
 * @returns Boot id, next sequence number and the samples.
 * @example
 * const history = decodeRunHistory(new Uint8Array(await response.arrayBuffer()), keys);
 * store.merge(history.batch);
 */
export function decodeRunHistory(body: Uint8Array, keys: readonly string[]): RunHistory {
  const reader = Reader.create(body);
  const header = cryocooler.RunHistoryHeader.decodeDelimited(reader);

  const samples: cryocooler.HistorySample[] = [];
  while (reader.pos < reader.len) {
    samples.push(cryocooler.HistorySample.decodeDelimited(reader));
  }

  const uptimeMs = new Float64Array(samples.length);
  const columns: Record<string, Float32Array> = {};
  for (const key of keys) columns[key] = new Float32Array(samples.length).fill(NaN);

  const channelIndex = new Map(header.channels.map((channel, index) => [channel, index]));
  samples.forEach((sample, row) => {
    uptimeMs[row] = sample.uptimeMs;
    for (const key of keys) {
      const index = channelIndex.get(key);
      const value = index === undefined ? undefined : sample.values[index];
      if (value !== undefined) columns[key][row] = value;
    }
  });

  return { bootId: header.bootId, endSeq: header.endSeq, batch: { uptimeMs, columns } };
}
