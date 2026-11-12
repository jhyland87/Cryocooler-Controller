---
name: kicad-pcb-edit
description: Change the routed KiCad PCB (hardware/kicad/cryocooler.kicad_pcb), such as moving or swapping a part, fixing copper or syncing it to a schematic change, and run DRC with schematic parity. Use for any board edit, after a schematic change that has to reach the PCB, or to check the board before fab export. Covers gen_pcb.py modes, the post-edit repair tools (gridroute, plane_ties, prune_flagged, board_edit, octilinear) and the accepted DRC baseline.
---

# PCB: edit the routed board and check it

Layout rules (test points, silkscreen, trace angles, STEP-only models, board ID)
are in `.claude/rules/hardware-pcb.md`. Follow them, and confirm with the user where they
say to. Current board state and its hand edits: `hardware/HANDOFF_rev3.md`.

```bash
cd hardware/kicad
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3  # has pcbnew
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
OUT=<session scratchpad>
```

Any script that does `import pcbnew` needs `$KPY`. System `python3` has no
pcbnew, and `$KPY` has no numpy.

## The board file is the source of truth

The rev 3 board carries hand copper that exists only in `cryocooler.kicad_pcb`
(see "PCB" in the handoff). So:

- **Never run `$KPY tools/gen_pcb.py`, `gen_pcb.py place` or `gen_pcb.py route`**. They
  rebuild the board from the netlist and lose all of it. Any mode name it doesn't
  recognise does the same full rebuild.
- `gen_pcb.py texts` deletes every F/B silkscreen drawing (U1 pin names, board ID,
  section boxes) before it redraws. `iclabels` redoes the IC body labels. Don't
  use either on rev 3.
- One-off board scripts (`rev3_board.py`, `j12_643228_board.py`,
  `sw3_1571300_board.py`, `trim_lands_board.py` and the other `*_board.py`) were
  run once on an earlier board. Don't re-run them. Use them as templates for a
  new one-off script.
- Don't run `tools/silk_fix.py`. It hides U1 pin names it finds colliding.

**The IMU board (`imu/imu.kicad_pcb`) is the opposite:** `$KPY tools/imu_board.py`
rebuilds it from the tables in that script, so edit the script, never the board.
Then re-apply its labels (`kicad-part-labels`), export (`kicad-fab-export`) and run
DRC on it. Its baseline is 0 errors, 0 unconnected, 0 parity and 22 `text_height`
warnings (`README.md`, "IMU board").

## Safe `gen_pcb.py` modes on the routed board

| Mode | Does |
|---|---|
| `link` | Re-links every footprint to its schematic symbol (run after any part add, swap or renumber) |
| `finish` | Redoes the pours, GND stitching, island and escape vias, and refills |
| `reroute <freerouting.jar>` | One more Freerouting round; existing copper stays (needs Java 25) |

Every mode, `link` included, finishes by running `tools/export_fab.py`, which
rewrites the Gerbers, zip and renders. Put `SKIP_FAB_EXPORT=1` in front while
iterating, then export once at the end (`kicad-fab-export` skill).

## Typical edit loop

1. Make the edit, either in KiCad (save the board, then re-read it before
   scripting on top) or in a one-off pcbnew script. `$KPY tools/board_edit.py
   cryocooler.kicad_pcb edits.json` applies `rip`, `track` and `via` edits from JSON.
2. `SKIP_FAB_EXPORT=1 $KPY tools/gen_pcb.py link`
3. DRC to JSON (see below), then close the open ends:
   - `$KPY tools/gridroute.py cryocooler.kicad_pcb $OUT/drc.json` routes each
     unconnected pair (optional `out.kicad_pcb NET,...`). Env knobs: `FIRST=U20,U21`,
     `FINE=1`, `IN1=1`, `VIA_COST`, `WIDTH`, `SKIP` (default `GND`).
   - `$KPY tools/plane_ties.py cryocooler.kicad_pcb $OUT/drc.json GND,+3V3` ties
     unconnected pads to their plane.
   - `$KPY tools/prune_flagged.py cryocooler.kicad_pcb $OUT/drc.json` deletes
     dangling tracks and vias. Re-run DRC and this until nothing is pruned.
   - `$KPY tools/octilinear.py cryocooler.kicad_pcb` straightens off-angle
     segments to 0/45/90.
   - A long net: `$KPY tools/route_legs.py cryocooler.kicad_pcb NET x,y x,y ...`.
     Way-point vias have to be added and routed in one process, or KiCad gives
     them the pour's net on reload.
4. Labels don't follow a moved part: see the `kicad-part-labels` skill.
5. If placement changed, re-run `python3 tools/gen_bom.py` (CPL).
6. DRC again, then fab export and renders (`kicad-fab-export` skill).
7. Record what changed in `hardware/HANDOFF_rev3.md`.

## DRC with schematic parity

```bash
$KC pcb drc --schematic-parity --severity-all --format json -o $OUT/drc.json cryocooler.kicad_pcb
python3 -c "import json,collections,sys; d=json.load(open(sys.argv[1])); \
print('unconnected', len(d['unconnected_items']), 'parity', len(d.get('schematic_parity', []))); \
print(collections.Counter((v['severity'], v['type']) for v in d['violations']))" $OUT/drc.json
```

Don't add `--refill-zones --save-board` unless you mean to write the board.

**Accepted baseline (rev 3, 2026-11-07):** 0 errors, 0 unconnected, 0 parity. The
215 accepted warnings are 4 `silk_edge_clearance` (J11 and J14 body lines), 3
`silk_overlap` (outline ticks at U16/C3, R70/R71, R49/R50), 4
`lib_footprint_mismatch` (U1, U18, C53, C74), and 102 each of `text_thickness` and
`text_height` (the 0.7 mm silk class). Anything new needs a fix or the user's OK.

DRC gaps you have to check yourself:
- Mask text against mask text isn't compared. Check it by script against the
  stroke outlines (there's no committed checker).
- `copper_sliver` has no location. Search the filled copper for sharp corners.
- Courtyard overlap is an error here, which limits how far parts can be nudged.

## pcbnew scripting gotchas

- pcbnew loads one board per process. Use a subprocess per board (as `silk_fix.py`
  does).
- SWIG frees removed or added items when their Python wrapper dies. Keep
  references in a list until `board.Save()`.
- Board `PCB_TEXT` can't be hidden. Delete it instead.
- `gen_pcb.py` pins `PYTHONHASHSEED=0` so placement is repeatable.
- Renders exaggerate tall bodies over nearby silk (perspective). Check against the
  body coordinates, not the picture.
