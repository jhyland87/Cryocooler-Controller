# AGENTS.md

Guidance for AI coding agents and human contributors working in this repo. This
file holds only what applies everywhere. The detail lives in two area guides;
read the one for the area you are working in before changing anything there:

| Working on | Read |
|------------|------|
| ESP32 firmware, dashboard, telemetry schema, build scripts, tests (`src/`, `include/`, `dashboard/`, `proto/`, `scripts/`, `test/`, `data/`, `platformio.ini`) | [`docs/agents/firmware.md`](docs/agents/firmware.md) and [`STYLEGUIDE.md`](STYLEGUIDE.md) |
| Schematic, PCB, 3D models, KiCad tooling, fab files (`hardware/`) | [`hardware/AGENTS.md`](hardware/AGENTS.md) |

New rules go in the guide for their area; add one here only if it applies to
the whole repo.

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

## Repository layout

| Path | Contents |
|------|----------|
| `src/` | Firmware source. `src/modules/` holds the subsystem modules. |
| `include/` | Headers. `include/config/` (build/pin config), `include/modules/` (module APIs). |
| `dashboard/` | Preact/TypeScript SPA (its own `package.json`). |
| `hardware/` | KiCad schematic, PCB, generators and fab output (see [`hardware/AGENTS.md`](hardware/AGENTS.md)). |
| `proto/` | `telemetry.proto` (+ `.options`) — single source of truth for telemetry wire format. |
| `scripts/` | PlatformIO pre-build steps + helper shell scripts. |
| `docs/` | Subsystem guides, the firmware agent guide (`docs/agents/`) + generated Doxygen output (`docs/doxygen/`, gitignored). |
| `data/` | Vite build output + OTA static files, embedded into firmware. |
| `test/` | Unity tests (`test_embedded`, `test_native`). |

## Repo-wide rules

- **Secrets** — `include/config/arduino_secrets.h` holds WiFi credentials in
  plaintext and is gitignored; never commit it or paste its contents.
