---
name: kicad-fab-export
description: Export the PCB fabrication files (Gerbers, drill files, JLCPCB zip) and the front, back and angled board renders, regenerate only the renders, and stamp the board ID with the git revision. Use after any change to hardware/kicad/cryocooler.kicad_pcb, when the renders in hardware/kicad/fabrication look stale, or when preparing a board order.
---

# Fab export, renders and board ID

Output goes to `hardware/kicad/fabrication/`. Its `README.md` has the order
settings to check (ENIG, filled and capped vias, high-precision silk, via-in-pad
list). Never hand-edit anything in `fabrication/`.

**Rule:** after any PCB change, regenerate the renders
(`circuit-board-render-front.png`, `-back.png`, `-angle.png`) and include them in
the same commit as the board.

`export_fab.py` only shells out to `kicad-cli`, so the system `python3` works.

## Full export (Gerbers, drills, zip, renders)

```bash
python3 hardware/kicad/tools/export_fab.py      # about 30 s
```

This writes `fabrication/gerbers/` (Gerbers with X2, Excellon PTH and NPTH in mm,
drill maps, `drill_report.txt`), `fabrication/cryocooler_jlcpcb.zip` and the three
renders.

- Every `gen_pcb.py` mode (including `link`) and `link_usb_vbus.py` already run it
  when they finish. `SKIP_FAB_EXPORT=1` skips it there and here.
- Zones must be filled first. The scripts that edit copper refill them. After a
  hand edit in KiCad, refill and save before exporting.
- Gerber headers carry a creation date, so every export shows a git diff even if
  the board didn't change.

## Renders only

```bash
cd hardware/kicad/tools && python3 -c "import export_fab; export_fab.render_board()"
```

This runs `kicad-cli pcb render` three times: top with perspective, bottom, and
angled. Sizes, camera and lighting are in `RENDERS` in `export_fab.py`. Change
them there, not on the command line.

- Look at the front render (`Read` the PNG) after a layout change.
- Vendor STEP models live in `lib/cryocooler.3dshapes/` and are tracked in git.
  A part with a missing model renders as bare pads, so a missing body in the render
  points to a model path problem. Models must be STEP, never `.wrl`
  (`hardware/AGENTS.md`).

## Board ID stamp

The back silkscreen carries `cryocooler` / `BETA rev <short hash>`, the commit the
fab files come from (`hardware/AGENTS.md`, "Board ID block"). On the routed rev 3
board no script restamps it (`gen_pcb.py` stamps only on a full rebuild, which
must not be run). The repo's pattern:

1. Commit the board change, after the user has reviewed it. Note its hash with
   `git rev-parse --short HEAD`.
2. Change the `gr_text "BETA rev <old>"` on `B.SilkS` to the new hash, either in
   KiCad or with a one-line pcbnew edit. Don't move it: the block stays in the same
   place on every revision.
3. Run the full export, update the `rev` mentions in `hardware/HANDOFF_rev3.md`, and
   commit as `UCS 145-125: stamp board ID with <hash>, re-export fab files`.

Commit only when the user asks.

## Before an order

- DRC at the accepted baseline (`kicad-pcb-edit` skill).
- `python3 hardware/kicad/tools/gen_bom.py` so `bom/cryocooler_cpl.csv` matches the
  board. Check JLCPCB's placement preview for rotations (`ROTATION_OFFSETS` in
  `gen_bom.py`). Through-hole parts (J12 and others) aren't in the CPL.
- Go through "Order settings to check" in `fabrication/README.md` and the "To
  confirm" / "Still open" lists in `hardware/HANDOFF_rev3.md`.
