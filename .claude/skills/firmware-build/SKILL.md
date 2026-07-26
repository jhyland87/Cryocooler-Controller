---
name: firmware-build
description: Build, flash, monitor, and test the ESP32-S3 cryocooler firmware with PlatformIO. Use when the user wants to compile, upload, run on device, watch serial output, run unit tests, or iterate quickly on firmware changes.
---

# Firmware build & flash

PlatformIO project (`platformio.ini`), framework Arduino, platform
`espressif32@5.3.0`, default env `esp32s3`.

## Build pipeline (runs automatically before compile)

Three pre-build scripts run **in order** (see `AGENTS.md`):
1. `scripts/compile_proto.py` — Nanopb C stubs from `proto/telemetry.proto`.
2. `scripts/build_dashboard.py` — `npm ci` + Vite build of `dashboard/` → `data/`.
3. `scripts/embed_web.py` — embeds `data/` into `include/web_content.h`.

The dashboard build is the slow step. Skip it when your change is firmware-only.

## Commands

```bash
pio run                                          # full build (env esp32s3)
pio run -t upload                                # build + flash over USB
pio device monitor                               # serial monitor @ 115200
pio run -t upload && pio device monitor          # flash then monitor
pio run -t clean                                 # clean build artifacts
```

### Fast iteration (skip slow pre-build steps)

```bash
SKIP_DASHBOARD_BUILD=1 pio run                   # skip npm/Vite dashboard build
SKIP_PROTO_BUILD=1 pio run                       # skip Nanopb regeneration
SKIP_DASHBOARD_BUILD=1 SKIP_PROTO_BUILD=1 pio run   # both — for comment/logic-only edits
```

Use both skips to verify a comment-only or pure-C++ change compiles fast.

## Environments

- `esp32s3` — default target board build/flash.
- `native` — host-side Unity unit tests (no hardware).
- `esp32s3_test` — on-device Unity tests.

```bash
pio test -e native                               # run host unit tests
pio test -e esp32s3_test                         # run on-device tests
pio run -e esp32s3                               # explicit env
```

## Notes

- Monitor/upload port and speeds are set in `platformio.ini`
  (`monitor_speed = 115200`, `upload_speed = 921600`). Adjust `monitor_port` if
  the device enumerates differently.
- Do not edit generated files (`web_content.h`, `*.pb.*`, `*/generated/*`).
- The dashboard has a live dev server too (`.claude/launch.json` → `dashboard-dev`);
  prefer that for pure UI iteration instead of a full firmware build.
