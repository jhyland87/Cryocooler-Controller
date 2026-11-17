---
name: kicad-pcb-autoroute
description: Autoroute a newly placed KiCad board with Freerouting from the board scripts (hardware/kicad/tools/rev5_board.py, ucs125_board.py), and get a stalled run to converge. Use when routing a new placement, when Freerouting's open-connection count stops falling, when choosing what to pre-route and lock, or when deciding whether a board that won't close needs a placement change. Covers the pre-route steps (plane ties, locked current paths), Freerouting 2.5 settings, how to read its log, diagnosis of a stall, and the 4-layer limit.
---

# PCB: autoroute a placed board

For edits to an already routed board use `kicad-pcb-edit`. Layout rules are in
`.claude/rules/hardware-pcb.md`. The user approves placement before any routing.

**4 layers only.** The user ruled out 6 layers on cost (2026-11-16). If a board will
not close, change the placement or the routing strategy.

```bash
cd hardware/kicad/tools
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
OUT=<session scratchpad>          # route scratch copies, never cryocooler.kicad_pcb
```

## Pipeline (`rev5_board.py`)

| Mode | Does |
|---|---|
| `place in out` | Places every part from the section floorplan (about 4 min) |
| `preroute in out` | Planes, locked current paths, vias-in-pad and plane ties; no autorouter (15 s) |
| `route in out [rounds]` | `preroute`, then Freerouting, then the pours |
| `reroute in out drc.json` | One more Freerouting round on a routed board |
| `finish board` | Pours, stitching, refill |

Run `route` in the background with `PYTHONHASHSEED=0` and the log redirected to a
file. Run `preroute` and DRC it first: a fault in the locked copper costs 15 s to find
there and an hour to find after a route.

## Before the autorouter: take work away from it

Freerouting stalls when it has to route everything. On the rev 5 board (615 parts,
457 nets) it hovered at 830-940 open connections for 20 passes until these were done
first.

1. **Tie every GND and +3V3 pad to its plane by script** (`tie_plane_pads` in
   `rev5_board.py`, built on `tie_pad_to_ground`). Left alone, Freerouting drew
   364 GND and 350 +3V3 track segments on the signal layers. The ties share a via
   within 3.5 mm, stay out of rule areas and 0.6 mm off the edge.
2. **Put the tied nets in a class the router skips** (`patch_dsn` moves them to
   `PlaneTied`; `--router.autorouter.ignore_net_classes=PlaneTied`).
3. **Lock the high-current copper** (`current_paths`) so the router cannot choose it.
4. **Vias-in-pad for exposed IC ground pads**, skipped where a part sits behind them.
5. **Copy repeated circuits.** Identical cells (the I/O channels) are placed as copies
   so one cell's routing can be copied too.

## Freerouting 2.5 facts (checked against the jar, 2026-11-16)

- Needs Java 25 (`temurin-25`). System `java` is too old.
- The autorouter pass is single-threaded. Several runs can share the machine.
- Any setting can be passed as `--router.<group>.<name>=value` or as an environment
  variable `FREEROUTING__ROUTER__<GROUP>__<NAME>`. Names are in
  `app/freerouting/settings/*.class` inside the jar (`javap -p`).
- `--router.fanout.enabled=false` turns off the fanout stage. It gave every SMD pin a
  via (341 extra) and did not help this board.
- The script only gets a result when Freerouting exits by itself. If the time limit
  (`gen_pcb.FREEROUTING_TIMEOUT`) kills it, nothing is saved, so size `MAX_PASSES`
  to fit: a pass took 4-6 min on this board.
- The optimiser only runs on a fully routed board.
- The Freerouting window has a cancel button; a click there ends the run in seconds
  with "Auto-routing stage interrupted" in the log. Set `FREEROUTING_HIDE=1` for
  unattended runs.
- "Power-plane validation failed ... overlap" appears because the GND plane covers the
  ISO_GND island. Harmless once the ground nets are skipped.
- Nets route in DSN file order and the result depends on it.

## Reading the log

```bash
grep "pass #" route.log | sed -E 's/.*(pass #[0-9]+).*in ([0-9.]+) seconds.*\(([0-9]+ unrouted).*/\1 \2s \3/'
```

Freerouting's "unrouted" is not KiCad's unconnected count (it counted 713 where KiCad
found 445). Compare passes with each other, and judge the board with KiCad DRC. The
count should fall pass by pass. Flat or rising after pass 3 means it has stalled:
stop, diagnose, change something. More passes will not fix it.

## Diagnosing a stall

Get a board to look at: one pass (`gen_pcb.MAX_PASSES = '1'`), then DRC to JSON with
copies of `cryocooler.kicad_pro` **and** `cryocooler.kicad_dru` beside the scratch
board, renamed to its basename. Without the `.kicad_pro` KiCad uses default rules;
without the `.kicad_dru` every via-in-pad and repair-tool via shows as a clearance
error (169 false errors on rev 5). KiCad's report stops at 499 unconnected items, so
499 means "at least 499". Then tally:

- **Open connections by net.** Power nets at the top mean the plane ties are missing.
- **Track segments by net.** Hundreds on GND or a supply means the router is drawing a
  plane net as wiring.
- **Open connections on a 20 mm grid.** One hot cell is a placement problem there;
  an even spread is a strategy problem.

## If it still will not close

In this order:

1. Route in groups: short local nets, then buses, then long nets, locking each.
2. Rotate parts so connected pins face each other; swap MCU or expander pins that
   cross (update `pin_config.h` and the schematic generator with it).
3. Shuffle the net order in the DSN and run several copies in parallel; keep the best.
4. Move parts. This changes the approved placement, so show the user first.

A net whose two ends cannot reach each other at all is a placement problem. Do not
tune the router for it.

## After the autorouter

The repair tools add copper without refilling the pours, so run DRC with
`--refill-zones --save-board` on the scratch board before reading the result.

Use the repair loop in `kicad-pcb-edit` (`gridroute.py`, `plane_ties.py`,
`prune_flagged.py`, `octilinear.py`), then `finish`, then DRC with schematic parity to
0 errors, 0 unconnected, 0 parity. Only then copy the board over
`cryocooler.kicad_pcb` (check for a KiCad lock first) and run `gen_pcb.py link`.

## Not tried here

DeepPCB (cloud, paid credits, uploads the design) and older Freerouting versions were
considered and not tested.
