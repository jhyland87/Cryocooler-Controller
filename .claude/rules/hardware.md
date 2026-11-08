---
paths:
  - "hardware/**"
---

# Hardware rules

Before changing the schematic, PCB, 3D models, KiCad tooling or fab files, read
`hardware/AGENTS.md` if it is not already in context.

@../../hardware/AGENTS.md

## Claude Code specifics

- **Skills:** `kicad-schematic` (regenerate and check the schematic, BOM),
  `kicad-pcb-edit` (edit the routed board, DRC with parity), `kicad-part-labels`
  (mask / silk labels), `kicad-fab-export` (Gerbers, renders, board ID stamp).
- The board file is read-blocked; query it with pcbnew scripts or `grep`.
