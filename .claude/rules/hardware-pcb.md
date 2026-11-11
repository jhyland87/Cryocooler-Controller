---
paths:
  - "hardware/**"
---

# PCB layout

Standing rules for `hardware/kicad/cryocooler.kicad_pcb` and any new board. Part
verification and selection rules are in `hardware-schematic.md`.

## Before editing the board

- Check for a KiCad lock file (`~*.kicad_pcb.lck`). If the board is open in KiCad,
  ask before writing to it.
- If the user has hand-edited the board, re-read the saved file first and keep their
  placements.

## Placement

- **Every part on the board.** An unplaced part (at the origin or off the edge) is a
  layout failure, not a warning.
- **Sections mirror the schematic.** Group each sheet's components into its own
  region and outline it on silkscreen. Adjacent sections may share a border line.
  Parts stay inside their section.
- **Dense placement.** Leave empty space only where a datasheet requires it
  (keep-outs, thermal, isolation clearance) or no other arrangement works. When a
  label won't fit beside its part, spread parts within their section, or grow the
  section a little, rather than adding an arrow.
- **Test points.** Every IC gets at least supply, ground, and its key signals/buses.
  Each test point sits on the same side as the part it tests, as close as possible.
  Name test points by function (`-16V5`), not TP number.
- **ESP32 antenna.** Don't just void copper. Cut the board out beneath the antenna
  (routed notch, keep-out on all layers), or let the antenna overhang the edge if the
  footprint allows. **Confirm with the user before choosing the overhang.**
- **Traces** at 0°, 45°, and 90° unless absolutely necessary.

## Silkscreen and labels

- **Readable:** no text may overlap other text, pads, part bodies, section lines,
  holes, or the board edge. Reserve room for fixed text (board ID, labels) before
  placing parts. Fail the check rather than ship overlapping text.
- **Label placement:** horizontal, centred just above or below the part (about
  0.3-0.6 mm away). Next choice is horizontal beside it, then vertical beside it.
  Reject a spot closer to another part than to its own, or across a section line.
  Any arrow must actually point at its part.
- **Mask text first:** 0.5 mm solder-mask text on solid pour, 0.7 mm on large parts.
  Use 0.7 mm silk only where mask won't fit. DRC doesn't check mask text against mask
  text, so check that by script. Mask text may not cross vias.
- Where a part body has room, put its reference centred inside it (1.0 mm on large
  parts, else 0.8 mm) instead of outside.
- **Pin 1** marked on every IC, oscillator/crystal, connector, and polarized
  multi-pin part.
- **Part name on the footprint** when the body is large enough (e.g. `ACS37800`).
  Keep the reference designator too, just not directly under the part.
- **MCU pin names** (ATmega, ESP32) printed in or around the footprint (`GND`, `EN`,
  `IO1`, `TXD0`, …).
- **Board I/O labelled:** power input and its voltage, ground, and outputs.
  Connector pin names run vertically above their pins, with the connector's name just
  below them. A switch's function and reference share one row.
- **Board ID block** on every board: the board name (KiCad project or repo name,
  e.g. `Cryocooler-Controller`) and `rev <short commit>` from
  `git rev-parse --short HEAD` of the commit the fab files come from. Keep it in the
  same place and format across revisions. It is stamped after review
  (`git-workflow.md`).

## After any board change

- Regenerate both renders, `fabrication/circuit-board-render-{front,back}.png`, with
  `python3 hardware/kicad/tools/export_fab.py` (it also writes the Gerbers and the
  JLCPCB zip). Commit them with the board change, and check the front render.
- Run DRC and fix anything new before reporting the layout done.
