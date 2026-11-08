---
paths:
  - "src/**"
  - "include/**"
  - "dashboard/**"
  - "proto/**"
  - "scripts/**"
  - "test/**"
  - "data/**"
  - "platformio.ini"
  - "Doxyfile"
  - "docs/*.md"
  - "docs/agents/firmware.md"
---

# Firmware and dashboard rules

Before changing firmware, dashboard, proto, build-script or test code, read
`docs/agents/firmware.md` if it is not already in context. Language style
guides load from `style-cpp.md` / `style-typescript.md`.

@../../docs/agents/firmware.md

## Claude Code specifics

- **Dev server:** the dashboard dev server is preconfigured in
  `.claude/launch.json` as `dashboard-dev` (`npm run dev`, port 5173, cwd
  `dashboard/`). Use the preview tools to run it rather than a raw shell.
- **Skills:** `firmware-build` (build / flash / monitor / test), `add-module`
  (scaffold a ModuleBase module), `add-telemetry-field` (telemetry field
  end-to-end), `generate-docs` (Doxygen).
- **Fast firmware iteration:** prefer
  `SKIP_DASHBOARD_BUILD=1 SKIP_PROTO_BUILD=1 pio run` when a change doesn't touch
  the dashboard or `proto/telemetry.proto`.
- **Do not edit generated files** — see the list in `docs/agents/firmware.md`.
