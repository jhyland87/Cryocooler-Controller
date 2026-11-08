---
name: kicad-part-labels
description: Place, move or add the PCB part labels (solder-mask and silkscreen reference/function text beside each part) through hardware/kicad/tools/mask_labels.json and mask_labels.py, and check them. Use after a part is moved, added or swapped on the board, when a part has no label, when the user hand-edits labels in KiCad, or for any silkscreen or label-text work.
---

# Part labels (mask and silk)

Every referenced part has a label printed beside it. Most are solder-mask openings
over ground pour (exposed copper forms the letters, so the board is ENIG). Where
mask won't fit, the label is 0.7 mm silk. Silkscreen rules (no overlaps, board
I/O labels, pin 1, board ID) are in `hardware/AGENTS.md`. Board-specific notes are
under "Labels" and "U1 pin names" in `hardware/HANDOFF_rev3.md`.

```bash
cd hardware/kicad
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
```

## Source of truth: `tools/mask_labels.json`

This is a list of labels. Each one has `kind` (`ref`, `value` or `board`), `text`,
`side` (`F`/`B`), `x`, `y`, `angle`, `size` (0.5, or 0.7 on large parts and
connector pins), and optionally `ref`, `uuid` (the board text it replaces),
`silk: true` and `arrow`. As of 2026-11-08 it holds 342 labels: 287 mask, 55 silk,
0 arrows.

`$KPY tools/mask_labels.py cryocooler.kicad_pcb` turns the JSON into board text.
It removes its previous mask text and silk labels and hides the footprint
field or board text that each label replaces. It is safe to re-run.

**Labels don't follow a moved part.** After moving a part, edit its entries in the
JSON, then re-run `mask_labels.py`.

## Placement rule (from the user's hand edits of 2026-11-06)

1. Horizontal text, centred right above or below the part, about 0.3-0.6 mm away.
   Next best is horizontal beside the part, then vertical beside it.
2. Mask at 0.5 mm wherever it fits on solid pour (0.7 mm on inductors, connectors
   and large ICs). Use 0.7 mm silk only where mask won't fit.
3. Test points are named by function (for example `-16V5`), not by TP number.
4. On a switch, the reference and function share one row (`SW1` left, `RESET` right).
5. Connector pin names run vertically above their pins, with the connector name
   below them. **No arrows.** Spread parts within their section instead.

Reject a spot closer to another part than to its own, or one across a section
line. When the user has hand-edited labels in KiCad, re-read the saved board and
keep their placements.

## Don't run

- `tools/mask_label_plan.py` (with `mask_label_export.py`). It follows the older
  parallel-to-edge rule and would undo the current placements.
- `tools/silk_fix.py`. It hides colliding U1 pin names and nudges text.
- `gen_pcb.py texts`. It deletes all board silkscreen.

## Missing labels

`$KPY tools/silk_label_missing.py cryocooler.kicad_pcb` adds a 0.7 mm silk label to
the JSON for each part that has none, and shrinks visible footprint fields to 0.7 mm.
It takes about 7 minutes and edits the board and the JSON in place. It can still
add arrows: remove any it adds and place those labels by the rule. Then run
`mask_labels.py`.

## Text that isn't in the JSON

- **U1 pin names:** 40 F.Silkscreen texts at 0.7 mm / 0.1 mm stroke, outside the
  module body. Names follow Espressif's WROOM-2 datasheet v1.7 Table 3-1 (pads
  13/14 `IO19`/`IO20`, pads 28-30 `NC`). Edit them directly in the board.
- Section names, box lines, the board ID and part-body IC names. `mask_labels.py`
  leaves these alone.
- Footprint fields of TP5, TP7 and TP34.

## Check

1. DRC (`kicad-pcb-edit` skill). Text-size warnings stay at 102 `text_thickness`
   and 102 `text_height`, and no new `silk_overlap` should appear.
2. Mask text against mask text: DRC doesn't compare these. Check by script against
   the true stroke outlines. No checker is committed, so write one in the scratchpad.
3. Mask text has to sit on solid pour. Silk may cross vias only because the board
   is ordered with filled and capped vias.
4. Regenerate the renders and look at the area (`kicad-fab-export` skill).
