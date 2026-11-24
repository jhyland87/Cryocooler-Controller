---
paths:
  - "hardware/**"
---

# PCB layout

Standing rules for every board in `hardware/kicad/`. The "Board profile" in
`hardware/kicad/README.md` names this project's board script, handoff, check config
and baselines; counts and exceptions live there, not here. Part
verification and selection rules are in `hardware-schematic.md`.

## Before editing the board

- Use the skills: `kicad-pcb-autoroute` (routing a new placement with Freerouting),
  `kicad-pcb-edit` (board edits, DRC with schematic parity),
  `kicad-part-labels` (mask / silk labels), `kicad-fab-export` (Gerbers, renders,
  board ID stamp).
- The board file (~5 MB) is read-blocked in `.claude/settings.json`. Query it with
  pcbnew scripts or `grep`, never by reading it whole.
- Check for a KiCad lock file (`~*.kicad_pcb.lck`). If the board is open in KiCad,
  ask before writing to it.
- If the user has hand-edited the board, re-read the saved file first and keep their
  placements.

## Placement

- **Every part on the board.** An unplaced part (at the origin or off the edge) is a
  layout failure, not a warning.
- **Group by schematic sheet where routing allows.** Keep each sheet's components
  together, but this may be bent: when a circuit is too dense to route, spread it into
  quieter areas so pad density is even across the board. Section outlines go on
  silkscreen only if the board profile says so; where they are drawn, adjacent
  sections may share a border line and parts stay inside their outline.
- **Repeated circuits get the same layout.** Identical channels or blocks (I/O
  channels, LED drivers, matched rails) use the same relative placement, orientation
  and routing, stepped or mirrored as a group. Lay one out, then repeat it; a block
  that has to differ (board edge, a keep-out) differs as little as possible.
- **Dense placement.** Leave empty space only where a datasheet requires it
  (keep-outs, thermal, isolation clearance) or no other arrangement works. When a
  label won't fit beside its part, spread parts within their section, or grow the
  section a little, rather than adding an arrow.
- **Placement approval.** After placing, run `placement_gate.py`, render a placement
  preview and get the user's approval **before any routing** (pre-route, plane ties,
  autorouter). Never route an unapproved placement.
- **Power button and 12 V connector.** The power button is easy to reach and is the
  topmost part on whichever side of the board it is on. The 12 V power cable connector
  is the bottommost part on whichever side it is on (seen from the front). Both are
  listed in `board_checks.json` (`placement.topmost_on_edge`, `bottommost_on_edge`) so
  the gate checks them.
- **Test points.** Every IC gets at least supply, ground, and its key signals/buses.
  Each test point sits on the same side as the part it tests, as close as possible.
  Name test points by function (`-16V5`), not TP number.
- **ESP32 antenna.** Don't just void copper. Cut the board out beneath the antenna
  (routed notch, keep-out on all layers), or let the antenna overhang the edge if the
  footprint allows. **Confirm with the user before choosing the overhang.**
- **Traces** at 0°, 45°, and 90° unless absolutely necessary.
- **STEP 3D models only.** Every footprint's 3D model is a `.step` / `.stp` file.
  Never use VRML (`.wrl`) on the PCB.

## Silkscreen and labels

- **Readable:** no text may overlap other text, pads, part bodies, section lines,
  open holes, or the board edge. Silk may cross a via when the board is ordered with
  filled and capped vias. Reserve room for fixed text (board ID, labels) before
  placing parts. Fail the check rather than ship overlapping text.
- **Labels are data:** `hardware/kicad/tools/mask_labels.json` is the source, applied
  and checked by `mask_labels.py` (the `kicad-part-labels` skill). Don't re-run
  `mask_label_plan.py`, which follows an older parallel-to-edge rule.
- **Label placement:** horizontal, centred just above or below the part (about
  0.3-0.6 mm away). Next choice is horizontal beside it, then vertical beside it.
  Reject a spot closer to another part than to its own, or across a section line.
  Any arrow must actually point at its part.
- **Mask text first:** 0.5 mm solder-mask text on solid pour, 0.7 mm on large parts.
  Use 0.7 mm silk only where mask won't fit. DRC doesn't check mask text against mask
  text, so check that by script. Mask text stays on solid pour and may not cross vias.
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
  below them. A switch's function and reference share one row. Where the profile says so, a
  connector's function also sits beside its pins near the edge (a vertical 1.0 mm
  "Label" field), so it stays visible with the cable unplugged.
- **Board ID block** on every board: the board name (KiCad project or repo name,
  e.g. `Cryocooler-Controller`) and `rev <short commit>` from
  `git rev-parse --short HEAD` of the commit the fab files come from. Keep it in the
  same place and format on every board. It is stamped after review
  (`git-workflow.md`).

## After any board change

- Regenerate the renders, `fabrication/circuit-board-render-{front,back,angle}.png`
  and the main board's four `-edge-{top,bottom,left,right}.png`, with
  `python3 hardware/kicad/tools/export_fab.py` (it also writes the Gerbers and the
  JLCPCB zip; see the `kicad-fab-export` skill). Commit them with the board
  change, and check the front render. A new or removed `J` connector needs its
  callout text in `PORTS` in `tools/render_callouts.py`.
- Run DRC with schematic parity and fix anything new before reporting the layout done.
- Run `board_checks.py` on the routed board. It must pass, or each exception is a
  `suppress` entry with a reason the user accepted. Baselines only go down.
- Run the `pcb-reviewer` agent once over the finished change (once at the end, not
  per edit) before calling it done.

## Layout rules of thumb

The thresholds the tools enforce (`placement_gate.py`, `board_checks.py`):

- Decoupling cap pad within 5 mm of its power pin; aim for 3 mm. Measure to the
  module's power pins, not its centre.
- Switcher hot loop under 25 mm².
- Fast nets only (`fast_signals` in `board_checks.json`: classes SPI and Usb, plus named
  clock, CAN, RS-485 and UART nets; slow and DC nets have no requirement): no track over
  a 3 mm or longer gap in its reference plane, and a ground via or ground through-hole
  pad within 3 mm of each via that moves the net to or from B.Cu. F.Cu to In2.Cu keeps
  In1 as the reference on both sides and needs no ground via. (`finish_route.py --stitch`
  still adds ground vias within 1 mm where they fit; the check is the looser rule.)
- Size trace width by IPC-2221 for the net's current (`net_currents` in
  `board_checks.json`).
- Thermal pads get their via count.

## When to re-render

Re-render (the `kicad-fab-export` skill, "Renders only") and commit the images with
the change whenever it alters what a render shows, not only after a board edit:

- A 3D model added, swapped or re-posed, or a stackup or solder-mask colour change.
- Camera, size or lighting settings in `RENDERS` in `tools/export_fab.py`.
- Callout text or the parts listed in `PORTS` / `GROUPS` in
  `tools/render_callouts.py`, or the drawing code there.
- A labelled part (connector, button, ESP32, status LED) moved, added or removed:
  check its callout still points at it, and that the edge views still fit a taller
  part.

A change that leaves every render identical (docs, BOM, schematic text) needs none.
Look at the renders you regenerated before reporting them done.
