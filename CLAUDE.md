# CLAUDE.md

Project guidance for Claude Code. The contributor overview lives in the shared
file below — read it first:

@AGENTS.md

## Rules

Rules live in `.claude/rules/` and load automatically: `general.md` and
`git-workflow.md` every session, the rest when you work on matching paths (see
the index in `AGENTS.md`). Edit the rule file, not this one, when a convention
changes.

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
- **Do not edit generated files** — see the list in `.claude/rules/general.md`.
- **Secrets:** `include/config/arduino_secrets.h` holds plaintext WiFi
  credentials and is gitignored; never commit or echo its contents.
