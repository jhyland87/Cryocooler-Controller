---
paths:
  - "src/**"
  - "include/**"
  - "dashboard/**"
  - "proto/**"
  - "scripts/**"
  - "test/**"
  - "data/**"
  - "lib/**"
  - "platformio.ini"
  - "Doxyfile"
  - "docs/*.md"
---

# Firmware and dashboard overview

Where the firmware, dashboard, telemetry schema, build scripts, and tests fit
together. Conventions are in `firmware-cpp.md`, `firmware-modules.md`,
`telemetry.md`, `dashboard.md`, and `safety-limits.md`.

## Key docs

- `docs/modules.md`: module lifecycle, authoring a module, SPI ICs.
- `docs/telemetry.md`: add a telemetry field end-to-end.
- `docs/state_machine.md`: FSM states and transitions.
- `docs/acs37800.md`: ACS37800 SPI frame, probe, and bring-up gotchas.

## Architecture

Every subsystem is a C++ **namespace of free functions** plus a thin
`struct Module : ModuleBase<T>` (CRTP) that gives it a compiler-enforced lifecycle
(`init()` / `service()`, optional `enable` / `disable` / `isEnabled`). Modules are
registered in **declarative `ModuleEntry` arrays** in `src/main.cpp`, and generic
helpers (`initGroup`, `serviceWithLog`, `reportStatus`) drive the init and service
loops. The contract is in `include/module.h`.

## Build pipeline

`platformio.ini` runs three pre-build scripts **in this order** before compiling:

1. `scripts/compile_proto.py`: Nanopb → `src/generated/telemetry.pb.c` +
   `include/generated/telemetry.pb.h`.
2. `scripts/build_dashboard.py`: `npm ci` + `npm run build` (Vite) → `data/`.
3. `scripts/embed_web.py`: embeds the `data/` assets into `include/web_content.h`.

```bash
pio run                          # full build (default env: esp32s3)
pio run -t upload                # build + flash over USB
pio device monitor               # serial monitor (115200)
pio test -e native               # host-side unit tests
SKIP_DASHBOARD_BUILD=1 pio run   # skip the npm/Vite dashboard build
SKIP_PROTO_BUILD=1 pio run       # skip Nanopb regeneration
```

Prefer `SKIP_DASHBOARD_BUILD=1 SKIP_PROTO_BUILD=1 pio run` when a change touches
neither the dashboard nor `proto/telemetry.proto`. Environments: `esp32s3` (default),
`native` (host unit tests), `esp32s3_test` (on-device tests).

## API documentation (Doxygen)

`doxygen Doxyfile` writes HTML to `docs/doxygen/html` (needs
`brew install doxygen graphviz`; without `dot` the graphs are skipped). Generated
files and `dashboard/` are excluded. Merges to `main` run
`.github/workflows/docs.yml`, which publishes to GitHub Pages
(`https://jhyland87.github.io/Cryocooler-Controller/`).

## Claude Code specifics

- **Dev server:** `dashboard-dev` in `.claude/launch.json` (`npm run dev`, port 5173,
  cwd `dashboard/`). Run it with the preview tools, not a raw shell.
- **Skills:** `firmware-build` (build / flash / monitor / test), `add-module`
  (scaffold a ModuleBase module), `add-telemetry-field` (telemetry field
  end-to-end), `generate-docs` (Doxygen).
