# CLAUDE.md

Project guidance for Claude Code. The shared overview loads here:

@AGENTS.md

## Rules

Rules live in `.claude/rules/` and load automatically: `general.md` and
`git-workflow.md` every session, the rest when you work on matching paths (see the
index in `AGENTS.md`). If a task spans firmware and hardware, both sets load. Edit
the rule file, not this one, when a convention changes.

## Claude Code specifics

- **Huge files are read-blocked** in `.claude/settings.json` (the `.kicad_pcb`,
  STEP/WRL models, `web_content.h`, `data/`, Gerbers, Doxygen, `.pio/build`).
  Query them with `grep` or scripts instead.
