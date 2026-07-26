# CLAUDE.md

Project guidance for Claude Code. The full contributor guide and coding
conventions live in the shared files below — read them first:

@AGENTS.md
@STYLEGUIDE.md

## Claude Code specifics

- **Dev server:** the dashboard dev server is preconfigured in
  `.claude/launch.json` as `dashboard-dev` (`npm run dev`, port 5173, cwd
  `dashboard/`). Use the preview tools to run it rather than a raw shell.
- **Skills** (`.claude/skills/`) cover the common workflows:
  - `firmware-build` — build / flash / monitor / test the firmware.
  - `add-module` — scaffold a new subsystem module (ModuleBase pattern).
  - `add-telemetry-field` — add a telemetry field end-to-end.
  - `generate-docs` — regenerate the Doxygen API docs.
- **Fast firmware iteration:** prefer
  `SKIP_DASHBOARD_BUILD=1 SKIP_PROTO_BUILD=1 pio run` when a change doesn't touch
  the dashboard or `proto/telemetry.proto`.
- **Do not edit generated files** — see the list in `AGENTS.md`.
- **Secrets:** `include/config/arduino_secrets.h` holds plaintext WiFi
  credentials and is gitignored; never commit or echo its contents.
