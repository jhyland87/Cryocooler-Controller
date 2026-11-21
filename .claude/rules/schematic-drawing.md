---
paths:
  - "**/*.kicad_sch"
  - "**/*.kicad_pro"
  - "**/kicad/**"
---

# Schematic drawing (every KiCad schematic in this repo)

These rules apply to every schematic project here: `hardware/kicad/` (the
cryocooler board and its IMU board), `docs/oem-controller/kicad/` (the patent
transcription) and any new one. The full guide is the `kicad-schematic-design`
skill; load it before drawing, moving or tidying anything on a sheet.

## Each project has a schematic profile

A project's `README.md` has a "Schematic profile" section. Read it first. It says:

- the root sheet and how the schematic is made (generator and command to
  regenerate; a generated `.kicad_sch` is never hand-edited)
- where part and label descriptions live
- its check config (`schematic_checks.json` beside the `.kicad_pro`: allowed
  global labels, part limit, baseline) and the checks to run, with their expected
  results
- the connectivity gate: what must stay identical when only the drawing changes
- whether a routed board depends on the net names
- the project's helpers and its deliberate exceptions to these rules

A project without a profile gets one before its sheets are redrawn. An exception
counts only if the profile lists it; anything else follows these rules.

## Rules that are never bent

- Supplies point up, grounds point down. Supply pins are on a symbol's top edge,
  ground pins on its bottom edge.
- Nothing overlaps: text, wires, buses, symbols. No 4-way junctions.
- A reference, value or label sits beside its own part or wire.
- Nothing touches a part it isn't connected to. A wire or bus reaches a part only at
  the end of one of its pins, and keeps 2.54 mm from any body it doesn't connect to.
- Every part has a description of its job in this circuit, and every net label,
  hierarchical label and global label has a description of what the net carries.
  Never state a guess as fact: when a part's role isn't known from the design
  (datasheet, design notes, the source document), the description says what it is
  inferred from, or "role unknown".
- An active-low net or pin is written with an overbar, `~{NAME}`, not a `_N`, `#`,
  `B` or `n` suffix (unless the profile says the source keeps printed names).

## Hierarchy and label scope

Use the narrowest connection that works:

| Connection | Use |
|------------|-----|
| Two points on one sheet, under 85 mm apart | Wire (a net label on it only to name the net) |
| Two points on one sheet, further apart | A net label on a short wire at each end; no wire across the sheet |
| Sheet to its parent | Hierarchical label on the sheet, sheet pin on its block; the parent joins the pins by wire when close, by a net label at each pin when far |
| Communication bus used project-wide | One global label on a bus, only if listed in the project's `allowed_globals` |

- One function per sheet. A sheet with a second function, or more parts than the
  profile's limit (30 by default, power symbols not counted), is split.
- A sheet holding several related functions can be a parent with child sheets, at
  any depth; keep it to two or three levels. A signal that crosses several levels
  goes through a hierarchical label and sheet pin at every level. Net labels never
  cross a sheet boundary, and depth is not a reason for a global label.
- A circuit used more than once is one sheet file placed several times. Never put a
  global label on such a sheet: it shorts every instance into one net.
- A bus is only for a communication bus (SPI, I2C). Chip selects, interrupts,
  address and control lines are single nets.
- A net label's name includes its sheet path (`/NAME`, `/Sheet/NAME`). Changing a
  label's type or moving a sheet renames the net. Where a board depends on the
  names, the profile says how to carry the rename to the board.

## No shortcuts

If the generator or helpers can't draw something the right way, extend them. Never
add a global label, a label pair or a bus to avoid drawing a wire, and never raise a
limit or a baseline to make a check pass; baselines only go down. A rule that seems
wrong for a case is a question for the user, not a reason to skip it.

## Done means checked

Run the project's checks from its profile, `check_sheet_structure.py` for the
project, and the connectivity gate. Then have the `schematic-reviewer` subagent
review every changed sheet, fix what it reports and run it again until it passes.
Say which checks ran and what the reviewer found.
