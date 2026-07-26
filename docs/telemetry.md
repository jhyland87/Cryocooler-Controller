# Adding a New Telemetry Field

This document walks through every file that must be touched to add a new
telemetry value end-to-end.  The system has **two independent output paths**
that both need updating:

| Path | Transport | Encoder | Decoder |
|---|---|---|---|
| **Serial Studio / HTTP JSON** | Serial (CSV) + TCP + HTTP GET | `FrameBuilder` in `telemetry.cpp` | Serial Studio project / browser `JSON.parse()` |
| **WebSocket binary** | WebSocket | Nanopb in `telemetry_pb.cpp` | protobufjs in `decodeTelemetry.ts` |

Both paths share the same dot-notation key convention (`group.field_name`).

---

## Worked Example

We'll add a hypothetical field `cooling.pump_pressure_bar` (a float read from
`cooling::getPumpPressure()`).

---

## Step 1 — src/telemetry.cpp: emit() and buildStartupFrame()

`emit()` is called once per control tick (1 Hz) and populates `lastFrame_`.
`buildStartupFrame()` is the startup slow-path that is used before the first
`emit()` completes.  Both must be kept in sync.

### 1a — emit()

Find the `cooling.*` block and add your field:

```cpp
// src/telemetry.cpp  ~line 600
lastFrame_
    ...
    .field("cooling.pump_rpm",       "%u",   cooling::getPumpRPM())
    .field("cooling.pump_pressure_bar", "%.2f", cooling::getPumpPressure())  // ← add
    ...
```

`FrameBuilder::field(name, fmt, value)` accepts any numeric or string type.
The format string controls both the Serial Studio output and how the value is
stored internally (float/int/string determines the JSON type).

### 1b — buildStartupFrame()

The same field must appear in `buildStartupFrame()` so the HTTP dashboard gets
a valid structure even during startup.  If the module might not be ready yet,
guard it:

```cpp
// src/telemetry.cpp  ~line 298 (inside the coolingReady block)
if (coolingReady) {
    frame
        ...
        .field("cooling.pump_rpm",          "%u",   cooling::getPumpRPM())
        .field("cooling.pump_pressure_bar", "%.2f", cooling::getPumpPressure())  // ← add
        ...
} else {
    frame
        ...
        .field("cooling.pump_rpm",          "%s", "")
        .field("cooling.pump_pressure_bar", "%s", "")  // ← add (empty sentinel)
        ...
}
```

### 1c — (Optional) Delta-mode passive list

If the field changes every tick and should **not** trigger a Serial Studio line
on its own (e.g. a slowly-drifting value), add it to `kPassiveFields[]` near
the top of `telemetry.cpp`:

```cpp
static const char* const kPassiveFields[] = {
    ...
    "cooling.pump_pressure_bar",   // ← add if it's noisy/continuous
};
```

### 1d — Check FrameBuilder::MAX_FIELDS

If the build produces a compile-time assertion failure about field count, bump
the limit in `include/frame_builder.h`:

```cpp
static constexpr uint8_t MAX_FIELDS = 130;  // increase if needed
```

Count fields by searching for `.field(` calls across both `emit()` and
`buildStartupFrame()`.

---

## Step 2 — proto/telemetry.proto: Schema definition

The `.proto` file is the single source of truth for the WebSocket binary
format.  Every field must live inside a **message** that maps to a dot-notation
prefix.

### Adding to an existing message

```protobuf
// proto/telemetry.proto
message Cooling {
  int32  status        = 1;
  int32  pump_on       = 2;
  float  temp_c        = 3;
  float  flow_rate_lpm = 4;
  uint32 fan_speed     = 5;
  uint32 fan_rpm       = 6;
  uint32 pump_speed    = 7;
  uint32 pump_rpm      = 8;
  float  pump_pressure_bar = 9;   // ← add; next available field number
}
```

> **Field numbers are permanent.**  Never renumber or reuse a field number
> after the firmware has been deployed — doing so silently corrupts decoding
> on old clients.  Always append using the next available number.

### Adding to a new message / group

If you need a brand-new group prefix (e.g. `vacuum.*`):

1. Add the new message to `telemetry.proto`:

```protobuf
message Vacuum {
  float pressure_mbar = 1;
  float pump_speed    = 2;
}
```

2. Add a field for it in `TelemetryFrame`:

```protobuf
message TelemetryFrame {
  ...
  Vacuum vacuum = 16;   // next available field number in TelemetryFrame
}
```

### String fields

If the field is a string, add an entry to `proto/telemetry.options` to set a
fixed maximum size (required by Nanopb to avoid heap allocation):

```
cryocooler.Cooling.pump_label   max_size:24
```

---

## Step 3 — Delete stale generated files

After editing `.proto`, the generated C and JS stubs are stale.  Delete them
so the build pipeline regenerates them unconditionally:

```bash
rm src/generated/telemetry.pb.c
rm include/generated/telemetry.pb.h
rm dashboard/src/generated/telemetry.js
rm dashboard/src/generated/telemetry.d.ts
```

The next `pio run` will regenerate all four files automatically via
`scripts/compile_proto.py` (C stubs) and `npm run proto:build` (JS stubs).

---

## Step 4 — src/telemetry_pb.cpp: Nanopb encoder

This file populates the Nanopb struct that is encoded and sent over WebSocket.
It reads from the same module getters as `telemetry.cpp` but fills struct
fields rather than calling `FrameBuilder::field()`.

```cpp
// src/telemetry_pb.cpp  — inside the cooling section
frame_.has_cooling = true;
frame_.cooling.status        = cooling::isEnabled() ? 1 : 0;
...
frame_.cooling.pump_rpm      = cooling::getPumpRPM();
frame_.cooling.pump_pressure_bar = cooling::getPumpPressure();   // ← add
```

The struct field names are generated from the `.proto` field names in
snake_case (e.g. `pump_pressure_bar` → `frame_.cooling.pump_pressure_bar`).

> **For new top-level messages** you also need to set the `has_<message>` flag
> and initialise the nested struct, following the pattern used by
> `frame_.has_cooling`, `frame_.has_system`, etc.

---

## Step 5 — dashboard/src/types/telemetry.ts: TypeScript interface

Add the new field to the appropriate nested interface so TypeScript knows about
it:

```typescript
// dashboard/src/types/telemetry.ts
cooling?: {
  status?: number;
  pump_on?: number;
  temp_c?: number;
  flow_rate_lpm?: number;
  fan_speed?: number;
  fan_rpm?: number;
  pump_speed?: number;
  pump_rpm?: number;
  pump_pressure_bar?: number;   // ← add
};
```

For a new group, add an entirely new interface property:

```typescript
vacuum?: {
  pressure_mbar?: number;
  pump_speed?: number;
};
```

---

## Step 6 — dashboard/src/utils/decodeTelemetry.ts: Protobuf → TypeScript mapping

Map the protobufjs-generated camelCase property to the snake_case TypeScript
field.  protobufjs converts `pump_pressure_bar` → `pumpPressureBar`
automatically.

```typescript
// dashboard/src/utils/decodeTelemetry.ts
if (f.cooling) {
  out.cooling = {
    ...
    pump_rpm:           f.cooling.pumpRpm     ?? undefined,
    pump_pressure_bar:  f.cooling.pumpPressureBar ?? undefined,   // ← add
  };
}
```

For a new top-level message:

```typescript
if (f.vacuum) {
  out.vacuum = {
    pressure_mbar: f.vacuum.pressureMbar ?? undefined,
    pump_speed:    f.vacuum.pumpSpeed    ?? undefined,
  };
}
```

> **camelCase rule:** protobufjs converts every snake_case proto field name to
> camelCase on the JS side.  `pump_pressure_bar` → `pumpPressureBar`,
> `flow_rate_lpm` → `flowRateLpm`, etc.

---

## Step 7 — include/dashboard_config.h: Serial Studio layout

Add a `DatasetCfg` entry in the appropriate group array so the field appears
in the Serial Studio desktop dashboard:

```cpp
// include/dashboard_config.h  — inside coolingDatasets[]
{
    .title          = "Pump Pressure",
    .units          = "bar",
    .telemetryKey   = "cooling.pump_pressure_bar",
    .widget         = ss::WidgetType::Gauge,
    .widgetMin      = 0,
    .widgetMax      = 10,
    .alarmLow       = 0,
    .alarmHigh      = 8,
    .alarmEnabled   = true,
    .graph          = true,
    .log            = true,
    .overviewDisplay = true,
},
```

The `telemetryKey` must exactly match the dot-notation key used in
`FrameBuilder::field()` in `telemetry.cpp`.

For a new group, add a new `DatasetCfg` array and a new `GroupCfg` entry in
`dataGroups[]`.

---

## Step 8 — Web dashboard (optional)

These are only needed if you want the field visible in the Preact dashboard.

### 8a — History buffer (App.tsx)

To record a rolling 100-sample history for use in a chart, add the key to
`HISTORY_KEYS`:

```typescript
// dashboard/src/App.tsx
const HISTORY_KEYS = [
  ...
  'cooling.pump_pressure_bar',   // ← add
] as const;
```

### 8b — Quick-read tile (App.tsx)

To show the value as a large numeric tile in the top row:

```typescript
// dashboard/src/App.tsx
const TILES: TileConfig[] = [
  ...
  { label: 'Pump P', key: 'cooling.pump_pressure_bar', unit: 'bar', dp: 2, color: '#80cbc4' },
];
```

### 8c — Chart component

Pass the history buffer slice to whichever chart component is appropriate, or
create a new one.  Use `getHistory('cooling.pump_pressure_bar')` to retrieve
the data.

---

## Summary Checklist

| # | File | What to do |
|---|---|---|
| 1a | `src/telemetry.cpp` — `emit()` | Add `.field("group.key", "fmt", getter())` |
| 1b | `src/telemetry.cpp` — `buildStartupFrame()` | Same field, with empty-string sentinel in the `else` branch |
| 1c | `src/telemetry.cpp` — `kPassiveFields[]` | Add key if it should not trigger delta output on its own |
| 1d | `include/frame_builder.h` | Bump `MAX_FIELDS` if the assertion fires |
| 2  | `proto/telemetry.proto` | Add field to existing message (or new message + `TelemetryFrame` entry) |
| 2s | `proto/telemetry.options` | Add `max_size` entry for any new string field |
| 3  | Generated stubs | Delete `src/generated/telemetry.pb.c`, `include/generated/telemetry.pb.h`, `dashboard/src/generated/telemetry.{js,d.ts}` |
| 4  | `src/telemetry_pb.cpp` | Populate the new `frame_.<message>.<field>` from the getter |
| 5  | `dashboard/src/types/telemetry.ts` | Add `field?: type` to the appropriate nested interface |
| 6  | `dashboard/src/utils/decodeTelemetry.ts` | Map `f.<message>.<camelCaseField>` to `out.<group>.<snake_case_field>` |
| 7  | `include/dashboard_config.h` | Add `DatasetCfg` entry (and `GroupCfg` if new group) |
| 8a | `dashboard/src/App.tsx` — `HISTORY_KEYS` | Add key for chart history (optional) |
| 8b | `dashboard/src/App.tsx` — `TILES` | Add tile entry for quick-read display (optional) |
| 8c | Dashboard component | Wire `getHistory('group.key')` into a chart (optional) |

---

## Notes

- **Key naming convention:** always `group.field_name` in snake_case.  The
  group prefix must match the proto message name used in `TelemetryFrame`
  (converted to snake_case: `ColdHead` → `cold_head`).
- **Proto field numbers:** append-only, never reuse.  Check the highest
  existing number in the message before adding.
- **`int64`/`uint64` proto fields:** protobufjs returns these as `Long` objects.
  Use the `toLong()` helper in `decodeTelemetry.ts` when mapping them.
- **Build shortcut:** set `SKIP_DASHBOARD_BUILD=1` in your environment to skip
  the full npm/Vite build and iterate on firmware-only changes faster:
  ```bash
  SKIP_DASHBOARD_BUILD=1 pio run
  ```
