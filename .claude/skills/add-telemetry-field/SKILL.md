---
name: add-telemetry-field
description: Add a telemetry field end-to-end across the firmware and dashboard — proto schema, both encoders, and the TypeScript decoder/UI. Use when exposing a new sensor value or computed metric to Serial Studio, the HTTP JSON API, or the Preact dashboard.
---

# Add a telemetry field

Telemetry has **two independent output paths** that both need updating, sharing
the `group.field_name` (snake_case) key convention:

| Path | Encoder | Decoder |
|------|---------|---------|
| Serial Studio / HTTP JSON | `FrameBuilder` in `src/modules/telemetry.cpp` | Serial Studio project / `JSON.parse()` |
| WebSocket binary (Protobuf) | Nanopb in `src/modules/telemetry_pb.cpp` | `dashboard/src/utils/decodeTelemetry.ts` |

The authoritative, worked walkthrough is
[`docs/telemetry.md`](../../../docs/telemetry.md) — follow it exactly. Summary:

## Steps

1. **`src/modules/telemetry.cpp`** — add `.field("group.key", "fmt", getter())`
   in **both** `emit()` and `buildStartupFrame()` (empty-string sentinel in the
   `else` branch). Add to `kPassiveFields[]` if the value is noisy/continuous.
   Bump `MAX_FIELDS` in `include/frame_builder.h` if the count assertion fires.

2. **`proto/telemetry.proto`** — add the field to the right message using the
   **next available field number**. **Never renumber or reuse a number.** For a
   new group, add a message and a field in `TelemetryFrame`. String fields also
   need a `max_size` entry in `proto/telemetry.options`.

3. **Delete stale generated stubs** so the build regenerates them:
   ```bash
   rm src/generated/telemetry.pb.c include/generated/telemetry.pb.h \
      dashboard/src/generated/telemetry.js dashboard/src/generated/telemetry.d.ts
   ```

4. **`src/modules/telemetry_pb.cpp`** — populate `frame_.<message>.<field>` from
   the getter (set `frame_.has_<message> = true` for a new message).

5. **`dashboard/src/types/telemetry.ts`** — add `field?: type` to the nested
   interface.

6. **`dashboard/src/utils/decodeTelemetry.ts`** — map the protobufjs camelCase
   property (`pump_pressure_bar` → `pumpPressureBar`) to the snake_case output
   field. Use the `toLong()` helper for `int64`/`uint64`.

7. **`include/config/dashboard_config.h`** — add a `DatasetCfg` entry (and a
   `GroupCfg` for a new group) so it appears in Serial Studio. `telemetryKey`
   must exactly match the key from step 1.

8. **(Optional) Preact dashboard** — `App.tsx` `HISTORY_KEYS` (chart history) and
   `TILES` (quick-read tile), then wire into a chart component.

## Verify

```bash
pio run                 # regenerates C stubs; full build incl. dashboard
```
Then confirm the value shows in the dashboard / HTTP `/api/telemetry`.

## Gotchas

- Key naming is always `group.field_name` snake_case; the group prefix is the
  proto message name in snake_case (`ColdHead` → `cold_head`).
- protobufjs converts every snake_case proto field to camelCase on the JS side.
- Proto field numbers are append-only and permanent once deployed.
