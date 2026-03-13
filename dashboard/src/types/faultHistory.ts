/** A single fault history record from the ESP32 ring buffer. */
export interface FaultRecord {
  reason:        string;
  reason_mask:   number;
  entered_epoch: number;
  entered_ms:    number;
  cleared_epoch: number;
  cleared_ms:    number;
  cleared_by:    string;
  active:        boolean;
}

/** Shape of the fault_history JSON message (HTTP response & WS text frame). */
export interface FaultHistoryMessage {
  type:    'fault_history';
  version: number;
  records: FaultRecord[];
}

/** Type guard for incoming WS text frames. */
export function isFaultHistoryMessage(msg: unknown): msg is FaultHistoryMessage {
  return (
    typeof msg === 'object' &&
    msg !== null &&
    (msg as Record<string, unknown>).type === 'fault_history' &&
    Array.isArray((msg as Record<string, unknown>).records)
  );
}
