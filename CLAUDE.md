# CLAUDE.md

Project guidance for Claude Code. The shared overview loads here; each area's
guide loads on demand from `.claude/rules/` when you touch files in that area:

- `.claude/rules/firmware.md` — firmware, dashboard, proto, scripts, tests
  (loads `docs/agents/firmware.md`).
- `.claude/rules/style-cpp.md` — `src/`, `include/`, `test/` (loads
  `docs/style/cpp.md`).
- `.claude/rules/style-typescript.md` — `dashboard/` (loads
  `docs/style/typescript.md`).
- `.claude/rules/hardware.md` — anything under `hardware/` (loads
  `hardware/AGENTS.md`).

If a task spans both areas, read both guides.

@AGENTS.md

## Claude Code specifics

- **Huge files are read-blocked** in `.claude/settings.json` (the `.kicad_pcb`,
  STEP/WRL models, `web_content.h`, `data/`, Gerbers, Doxygen, `.pio/build`).
  Query them with `grep` or scripts instead.
