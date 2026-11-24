---
name: kicad-pcb-edit
description: Change the routed KiCad PCB (the board named in hardware/kicad/README.md, Board profile), such as moving or swapping a part, fixing copper or syncing it to a schematic change, and run DRC with schematic parity. Use for any board edit, after a schematic change that has to reach the PCB, or to check the board before fab export. Covers gen_pcb.py modes, the post-edit repair tools (gridroute, plane_ties, prune_flagged, board_edit, octilinear), finish_route.py --stitch, board_checks.py and the DRC baseline in the board profile.
---

# PCB: edit the routed board and check it

Layout rules (repeated circuits laid out alike, test points, silkscreen, trace
angles, STEP-only models, board ID) are in `.claude/rules/hardware-pcb.md`. Follow them, and confirm with the user where they
say to. Board script, current handoff, check config and baselines: the "Board profile" in
`hardware/kicad/README.md`. After an edit run the `pcb-reviewer` agent once on the
finished change.

```bash
cd hardware/kicad
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3  # has pcbnew
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
OUT=<session scratchpad>
```

Any script that does `import pcbnew` needs `$KPY`. System `python3` has no
pcbnew, and `$KPY` has no numpy.

## The board file is the source of truth

A routed board carries hand copper that exists only in the board file
(see "PCB" in the current handoff). So:

- **Never run `$KPY tools/gen_pcb.py`, `gen_pcb.py place` or `gen_pcb.py route`**. They
  rebuild the board from the netlist and lose all of it. Any mode name it doesn't
  recognise does the same full rebuild.
- `gen_pcb.py texts` deletes every F/B silkscreen drawing (U1 pin names, board ID,
  section boxes) before it redraws. `iclabels` redoes the IC body labels. Don't
  use either on a routed board.
- The `*_board.py` scripts in `tools/` were each written for one board or one change.
  Don't re-run one on a board it was not written for. The board profile names the
  current one. Use the others as templates for a new one-off script.
- Don't run `tools/silk_fix.py`. It hides U1 pin names it finds colliding.

**The IMU board (`imu/imu.kicad_pcb`) is the opposite:** `$KPY tools/imu_board.py`
rebuilds it from the tables in that script, so edit the script, never the board.
Then re-apply its labels (`kicad-part-labels`), export (`kicad-fab-export`) and run
DRC on it. Its baseline is in `README.md`, "IMU board".

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
   - A pour the signals have cut up (`+3V3` on In2): `LINKS=+3V3 $KPY tools/gridroute.py
     cryocooler.kicad_pcb - out.kicad_pcb` joins the separate copper islands of that net.
   - Last step only: `NECK=REF.PAD,... $KPY tools/gridroute.py ...` lets those pads (one low-current load each: an
     IC sense or supply pin, a bypass capacitor) leave at a 0.2 mm neck under 1 mm long, then class width again.
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
7. Run `make drc` and `board_checks.py` (below). After copper edits that add signal
   vias, `$KPY tools/finish_route.py --stitch` adds the missing ground vias; with `--reach MM` (and
   `--nets A,B`) it instead gives every unlocked signal via farther than MM from a ground via one at the nearest legal spot.
8. Record what changed in the current handoff.

## DRC with schematic parity

```bash
$KC pcb drc --schematic-parity --severity-all --format json -o $OUT/drc.json cryocooler.kicad_pcb
python3 -c "import json,collections,sys; d=json.load(open(sys.argv[1])); \
print('unconnected', len(d['unconnected_items']), 'parity', len(d.get('schematic_parity', []))); \
print(collections.Counter((v['severity'], v['type']) for v in d['violations']))" $OUT/drc.json
```

Don't add `--refill-zones --save-board` unless you mean to write the board.

`make drc` runs the same command and exits non-zero on any error, unconnected item
or parity issue.

**Baseline:** the accepted DRC counts and the reason for each accepted warning are in
the board profile (`hardware/kicad/README.md`) and the current handoff. Anything
above them needs a fix or the user's OK.

## Board checks

```bash
$KPY tools/board_checks.py --project cryocooler.kicad_pro --json $OUT/checks.json
```

`board_checks.py` checks return-path gaps of 3 mm or longer on fast nets (`fast_signals`
in `board_checks.json`; a via's own antipad is not a gap), reference-plane changes, fast-net
vias to or from B.Cu with no ground via or pad within 3 mm (F.Cu to In2.Cu is exempt; `--stitch`
adds vias within 1 mm, tighter than the check), trace width
against current (IPC-2221, from `net_currents`: a net's locked corridor copper carries
the full current, F.Cu and B.Cu tracks joined by vias add at an assumed 1 A per via,
other tracks only need their net class width), thermal-pad via count, open nets and mask-text overlap. Settings,
`suppress` entries (each needs a reason) and the baseline are in `board_checks.json`
beside the `.kicad_pro`. A count above its baseline fails; baselines only go down
(`--update-baseline` after a real improvement). `make checks` runs the schematic
checks, DRC and this.

DRC gaps you have to check yourself:
- Mask text against mask text isn't compared by DRC. `board_checks.py` reports it
  as `MASK_TEXT_OVERLAP`.
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
