# AGENTS.md

Guidance for AI coding agents and human contributors working in this repo. This
file holds only what applies everywhere. The rules live in
[`.claude/rules/`](.claude/rules/), indexed [below](#rules). Read the ones for the
area you are working in before changing anything there.

## Project overview

ESP32-S3 firmware that automates the cooldown sequence of a cryogenic cooler. A
ten-state machine drives a compressor-based cold stage from room temperature
(~295 K) down to a 78 K setpoint, enforcing thermal/current safety limits,
streaming Protobuf telemetry over WebSocket, and serving a real-time Preact
dashboard over WiFi.

- **Firmware:** C++17, Arduino framework on PlatformIO (`espressif32@5.3.0`).
- **Dashboard:** Preact + MUI + Vite + TypeScript in `dashboard/`, bundled into
  the firmware at build time.
- **Units:** Celsius throughout the firmware (not Kelvin), despite the K figures
  above being how the process is described.
- **No I2C:** every peripheral is on SPI or a GPIO. The fan and pump use LEDC PWM through a BSS138 and PCNT tach counting.

See [`README.md`](README.md) for the hardware table and wiring.

## Rules

Claude Code loads these automatically: `general.md` and `git-workflow.md` every
session, the rest when you work on matching files. Other tools: read the ones for
your area. New rules go in the file for their area.

| Rule file | Applies to | Covers |
|-----------|------------|--------|
| [`general.md`](.claude/rules/general.md) | everything | Verify, never assume; respect earlier decisions; no dead code; honest reporting; generated files; secrets; docs in sync |
| [`git-workflow.md`](.claude/rules/git-workflow.md) | everything | Review before commit, new branch per push, never push `main` |
| [`firmware-overview.md`](.claude/rules/firmware-overview.md) | firmware, dashboard, proto, scripts, tests | Key docs, architecture, build pipeline and commands, Doxygen, skills |
| [`firmware-cpp.md`](.claude/rules/firmware-cpp.md) | `src/`, `include/`, `test/`, `lib/` | No blocking in `loop()`, timing, naming and units, numeric literals, Doxygen style, build and test before done |
| [`firmware-modules.md`](.claude/rules/firmware-modules.md) | `src/modules/`, `include/modules/`, `main.cpp` | ModuleBase CRTP pattern, registration, SPI device helpers |
| [`telemetry.md`](.claude/rules/telemetry.md) | `proto/`, telemetry encoders, TS decoder | Two output paths, never renumber proto fields |
| [`safety-limits.md`](.claude/rules/safety-limits.md) | state machine, cold head / compressor / amplifier / cooling, `include/config/` | Never loosen a limit or interlock silently; fail safe |
| [`dashboard.md`](.claude/rules/dashboard.md) | `dashboard/` | Preact/TS conventions, preview server, type-check and build |
| [`hardware-overview.md`](.claude/rules/hardware-overview.md) | `hardware/` | Where things are, how to read the long handoffs, read-blocked board |
| [`hardware-schematic.md`](.claude/rules/hardware-schematic.md) | `hardware/`, `pin_config.h` | Generated schematic, datasheet verification, part selection, drawing conventions |
| [`hardware-pcb.md`](.claude/rules/hardware-pcb.md) | `hardware/` | PCB layout directives, STEP models, silkscreen and labels, board ID, renders |

## Repository layout

| Path | Contents |
|------|----------|
| `src/` | Firmware source. `src/modules/` holds the subsystem modules. |
| `include/` | Headers. `include/config/` (build/pin config), `include/modules/` (module APIs). |
| `lib/` | Project-private libraries (the ACS37800 driver). |
| `dashboard/` | Preact/TypeScript SPA (its own `package.json`). |
| `hardware/` | KiCad schematic, PCB, generators and fab output (see `hardware-overview.md`). |
| `proto/` | `telemetry.proto` (+ `.options`) — single source of truth for telemetry wire format. |
| `scripts/` | PlatformIO pre-build steps + helper shell scripts. |
| `docs/` | Subsystem guides + generated Doxygen output (`docs/doxygen/`, gitignored). |
| `data/` | Vite build output + OTA static files, embedded into firmware. |
| `test/` | Unity tests (`test_embedded`, `test_native`). |
