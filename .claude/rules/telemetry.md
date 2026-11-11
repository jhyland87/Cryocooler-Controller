---
paths:
  - "proto/**"
  - "src/modules/telemetry*.cpp"
  - "include/modules/telemetry*.h"
  - "src/frame_builder.cpp"
  - "dashboard/src/utils/decodeTelemetry.ts"
---

# Telemetry

Two independent output paths, both driven from the same module getters and sharing
the `group.field_name` key convention:

1. **HTTP JSON:** `FrameBuilder` in `src/modules/telemetry.cpp`.
2. **WebSocket binary (Protobuf):** the Nanopb encoder in
   `src/modules/telemetry_pb.cpp`, decoded by `dashboard/src/utils/decodeTelemetry.ts`.

Rules:

- `proto/telemetry.proto` is the single source of truth for the C++ and TS stubs.
- **Never renumber or reuse a proto field number.** It silently corrupts old clients.
  Retire a field with `reserved`.
- Proto message `ColdHead` maps to the telemetry prefix `cold_head`. protobufjs turns
  snake_case fields into camelCase on the JS side.
- After editing the `.proto`, delete the stale generated stubs so the next build
  regenerates them (`docs/telemetry.md` Step 3).
- Adding a field touches about 8 places. Follow `docs/telemetry.md` exactly, or use
  the `add-telemetry-field` skill.
- Update both output paths together. A field present in one path and missing from
  the other is a bug.
- The run recorder (`GET /api/history`) samples chart channels from
  `telemetry::fillFrame()`. Its `CHANNELS` keys in `src/modules/run_recorder.cpp`
  must match the dashboard's `HISTORY_KEYS`; the dashboard maps them by key.
