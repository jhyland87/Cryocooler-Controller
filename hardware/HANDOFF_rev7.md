# Rev 7 board: handoff

Evidence labels follow `.claude/rules/general.md`: **measured** = read from the installed board with pcbnew or
`kicad-cli` on 2026-11-23, **script-checked** = a named script, **inferred** = reasoned only.

## State (2026-11-23)

- Branch `rev7`, cut from `rev6-schematic`. Nothing is committed.
- Rev 7: Phoenix UCS 195-145, 170 x 120 mm, 4 layers. **Placed, fully routed and installed** at
  `hardware/kicad/cryocooler.kicad_pcb`. Not bench tested, not ordered.
- DRC with schematic parity, zones refilled: **0 errors, 0 unconnected, 0 parity.** Warnings: `silk_edge_clearance` 4
  (all J2, KiCad's stock Molex footprint, silk 0.135 mm from the edge) and `lib_footprint_mismatch` 2 (U1, U18).
- `board_checks.py` exit 0, every count 0, one suppression (the 0.2 mm +12V neck into U23 pad 8, user-accepted,
  with the reason in `board_checks.json`). `placement_gate.py` at its baseline (`TESTPOINT_MISSING` 53,
  `tools/board_checks_baseline.json`).
- `pcb-reviewer` run once. Its two high findings (120 VAC line-to-return spacing; ISO_GND 15 A return) were fixed in
  the last round (see Decisions).
- Fab files, renders, BOM / CPL, `cryocooler-schematic.pdf` and `fabrication/pcb-layer-stack.gif`
  (now from `tools/layer_stack_gif.py`) were regenerated from this board. Uncommitted, **no board ID stamp**:
  the stamp waits for the user's review and commit.
- Size (measured): 506 footprints, 193 on the back; 2,068 vias; CPL 485 placements (296 top, 189 bottom; J2 and J12
  are through-hole and not in it).
- **No section outlines.** `rev7_board.py` has no `sections` mode and no fixed rectangles; `placement_view.py`
  colours parts by sheet when a board script sets `PLACEMENT_VIEW_BY_SHEET`.
- Previews: `kicad/fabrication/preview/` (`rev7_placement_front|back.png`, `rev7_render_front|back.png`); these
  show the placement, not the routed board.

## Board outline

Phoenix UCS 195-145, drawings `dev/pxc_2203442_..._PCB2D_UCS-PCB-195-145.pdf` (PCB) and
`dev/pxc_2203441_..._2D.pdf` (housing). Read from the drawings (2026-11-23):

- **Size: 170 x 120 mm** (housing note: maximum PCB surface 170 x 120 mm; PCB thickness 0.8 to 3 mm). The outline
  was 120 x 100 mm until 2026-11-23: four placements on it failed to route on three signal layers with In1 a solid
  GND plane.
- **Mounting holes:** 4 x 3.2 mm, 6 mm land, on 161.6 x 111.6 mm: (4.2, 4.2), (165.8, 4.2), (4.2, 115.8),
  (165.8, 115.8).
- **Restricted corners:** 4.45 mm squares, no components and no solder mask (`CORNER_SQUARE`).
- **Edge.Cuts:** the rectangle with the antenna notch in the top edge, x 74.5 to 93.5, y 0 to 6 (rev 5's notch,
  not from the drawing).
- **Inside height** (housing drawing, section B-B): 31 mm and 10 mm either side of the PCB plane. Which side
  is the board's front is not checked.
- **Layers: 4.** F.Cu, In1.Cu (GND plane), In2.Cu (signal and `+3V3` pour), B.Cu, 1.6 mm.
- **Walls:** left = IMU / PT1000, cryocooler output, amplifier input, 12 V in; top = USB and antenna;
  right = power button, amplifier signal and REM, precision and pressure ports; bottom = flow, NTC, relay,
  fan, pump, I/O 1-4.

## Placement directives

- The placement preview must be approved by the user before any routing (done, 2026-11-23).
- The power button is easy to reach. It is the topmost part on whichever side
  it is on.
- The 12 V power cable connector is the bottommost part on whichever side it
  is on.
- Power button: **SW3** (only candidate). `tools/part_descriptions.py` line 162:
  `'SW3': 'Power button: tap for on, hold for off'`. SW1 and SW2 are RESET and
  BOOT. J15 pin 5 is the display's press line, not a board button.
- 12 V input: **J2** (only candidate). `part_descriptions.py` line 208:
  `'J2': '12 V input, Mini-Fit Jr 2 x 2 ...'`. `gen_schematic.py` ~line 1122
  places `'12V IN (ATX 4-PIN)'`. J8, J13 and J15 pin 2 are 12 V outputs.
- Refs come from `next_ref()`, so confirm them in the netlist after generation.

## How it was placed and routed

**The routed board is the source of truth. `rev7_board.py place` no longer reproduces it.** Re-running `place`
on the current schematic moves 33 parts the placed board does not have (the +5V block U15 / U16 / L1 / L4 / U28 and
small parts, 9-12 mm), with or without the `PINNED` entries: the planner reacts to the netlist. Hand copper
(the `+5V` trunk and its partner vias, island routes, three B.Cu re-routes, the ISO_GND return) lives only in
the board file. Edit the installed board; do not regenerate it. The scratch directory `route2/` and its helper
scripts (`g5.py`, `route_cov.py`, `island_fix*.py`) are not in the repo and do not survive a reboot.

**Placement** (`Plan` in `rev7_board.py`; sound as a description, not as a reproduction). After the wall connectors,
U1, the pinned 12 V block and U18 / U17 are down, every other IC is a cluster with the small parts that connect to
it. A cluster's size is its pads and courtyard area; its links are the nets it shares (weight 1 / (nodes - 1));
a 5 mm cell holds `TARGET` (0.09 pads/mm2) of its free area. Greedy, then 6 refinement passes, minimising link
length plus `PENALTY` (6 mm) per pad over capacity. The rev 5 placer then puts the small parts beside their ICs;
inductors, output capacitors, U28 (beside C4) and bulk capacitors are tied to their regulator / TVS
(`REGULATOR_PARTS`, `BOUND`). `NUDGES` (`{'C420': (1.0, 0.0)}`) is applied after placing.
- Pinned and reserved: F1, Q1, R78, D1, U11, U23 in one row above the fan and pump headers (y 93-99); F3 / F4
  (`PINNED`); U18 on the back between J11 and J12; the isolated island x 0-30, y 37.2-71 (`ISO_RECTS`, so U17's
  logic-side pads are outside the moat); `CORRIDORS` for the 12 V and amplifier copper. I/O pairs on the bottom
  edge start at x 105 with pitch 25 (`IO_PAIR_START`, `IO_PAIR_PITCH`).
- Fan-out ring (`Layout.fanout_ics`): every U with 5 or more pads whose pin pitch needs more than one staggered via
  row; the ring is 2.0 mm from the courtyard on both sides, sized from the 0.45 mm via pitch
  (`FANOUT_VIA_PITCH`). Decoupling caps may come 1.2 mm closer; pinned parts, wall connectors and the regulator
  parts are exempt. The "35 ICs" and "2.0 mm" figures are from the earlier handoff, not re-derived (inferred).
- Density when placed (script-checked, earlier handoff): 1,971 pads, no 20 mm cell above 0.22 pads/mm2, ratsnest
  8,284 mm. Results move a lot between neighbouring `TARGET` values.

**Routing sequence that worked** (KiCad's python for every step; `rev7_board.py` calls `rev5_board.main()`):

1. `rev7_board.py place`, then user approval of the placement.
2. `rev7_board.py route` (pre-route, then 14 Freerouting passes with `PYTHONHASHSEED=0`; ends near 220 unrouted).
   Pre-route draws the plane ties, the LED jumpers (`led_jumpers`: D2, D3), the thermal vias, and the locked
   current copper from `rev7_current.py`; `LOCKED_NETS` keeps Freerouting off those nets.
3. `gridroute.py` on the leftovers, then `LINKS=<net>` for `+3V3`, `+12V`, `+5V_IO`, `+3V3_COOL`, `+3V3`
   (joins separate copper islands of a net).
4. `octilinear.py`, then `finish_route.py --stitch` (about 1 min), then `rev7_board.py finish`, then
   `LINKS=+3V3 gridroute.py` once more with `MAX_EXPAND=12000000`.
5. `NECK=U23.8 gridroute.py`: the only neck on the board (`+12V`, 0.2 mm wide and long, into the INA239 VBUS
   sense pin; `NECK=REF.PAD,...` allows a 0.2 mm neck of at most 1 mm out of a pad, run last, never on the locked
   current nets).
6. Stragglers by local rip-up and re-route (`board_edit.py` rip, then `gridroute.py` for the target net first,
   then the ripped nets): U51 pad 5, IO1_DIRECT, C80 pad 2, R614 pad 2, C420 / U106 pad 11 (C420 moved 1.0 mm in
   +x; a +12V via at its pad 1; a via at pad 11 itself cannot fit).
7. Ground vias: `finish_route.py --stitch --reach 2` (65 vias), then `--reach 1 --nets
   /CS_ADDR_D,/Universal\ IO/IO1_DIRECT` (3 vias). `--reach` re-checks every unlocked signal via (of `--nets`, if
   given) against that distance.
8. **Island vias.** KiCad removes a pour island with no via, so In2 `+3V3` islands and bare GND islands are closed
   by one via inside the island plus a 0.3 mm outer-layer track to the nearest copper of the net (routed with
   `gridroute.route_between`; `finish_route.py` `stitch_islands` does it for GND pours). Run `LINKS=+3V3` and
   `--stitch` again after any edit that cuts a pour. Two In2 islands could not take a via (x 33-36, y 52-58,
   7.6 mm2; x 54, y 50-74, 0.7 mm wide).
9. Three B.Cu fast tracks that crossed In2 buses were re-routed with a limit on the uncovered run (SPI_SCK, SPI_MISO,
   SPI_MOSI); the longest uncovered stretch is 2.75 mm against the 3 mm limit.

**Locked current copper** (`tools/rev7_current.py`, drawn in pre-route from `CORRIDORS`). Wide round-ended tracks
on F.Cu and B.Cu, as wide as the corridor and the routed copper around them allow, joined by 0.7 / 0.35 mm vias
(about 1 A each by IPC-2221 inner-layer k, 25 um barrel, 10 C; 0.8 mm apart or more). `TRACKS` and `VIAS` are
fitted to the routed board, so they are the record of what is on it. A containment check confirms every locked
track lies inside its corridor. Nets: `Net-(F1-Pad1)`, `VIN`, `VSW`, `+12V` (10 A), `+12V_FAN`, `+12V_PUMP`
(below F3 / F4), `Net-(J12-Pin_1)`, `Net-(J11-Pin_1)` (15 A) and the `ISO_GND` return. `CORRIDORS` (IPC-2221, 1 oz,
10 C): 12 V bar B 7 mm (9.8 A), F row 3 mm (5.3 A); amplifier IP- 6.5 mm (9.3 A per layer), IP+ 10.5 mm (13.2 A per
layer); ISO_GND return in three entries with side `all`: spine x 0.3-6.75, y 37.2-70.9, and a link to J11 pin 2
and to J12 pin 2.

**The `+5V` trunk** (hand-routed after the autoroute; one loop-free tree from L1.2, 15 locked F.Cu tracks, 13 of
them 1.1 mm). Path: L1.2, round the +12V pads of C78 / U15 (x 45.6-52, y 64-71.5), C2.1, F.Cu y 61.1 to x 70,
pinch, y 61.14 to the `+5V` via (82.62, 61.14), J35.2 (a 1.1 mm track laid over its pad), diagonal to
(92.86, 46), J40.1. Branches carry only their loads and stay unlocked at class width or more.

## Checks and their current results

All on the installed board, 2026-11-23.

| Check | Result |
|---|---|
| DRC with schematic parity, refill | 0 errors, 0 unconnected, 0 parity; warnings `silk_edge_clearance` 4 (J2), `lib_footprint_mismatch` 2 (U1, U18) |
| `board_checks.py` | exit 0; RETURN_PATH_GAP 0, VIA_NO_GROUND_VIA 0, NET_OPEN 0, THERMAL_PAD_VIAS 0, MASK_TEXT_OVERLAP 0, REFERENCE_CHANGE 0; TRACE_CURRENT: the one suppressed neck |
| `placement_gate.py` | exit 0, `TESTPOINT_MISSING` 53 (baseline; a schematic-level gap, not addressed) |
| `pcb-reviewer` | run once; two high findings fixed (see Decisions) |

`board_checks.py` rule notes:
- **TRACE_CURRENT.** A net's locked tracks carry the full current (F.Cu + B.Cu tracks joined by vias add, assumed
  1 A per via); its unlocked tracks only need their net class width; a net with no locked copper is tested as a
  whole (narrowest track). The need is 1.25 x `net_currents`.
- **RETURN_PATH_GAP.** Fast nets only, gaps of 3 mm or longer. A sample inside the antipad of a via of the track's
  own net (radius + In1 zone clearance + 0.05 mm) is not a gap.
- **VIA_NO_GROUND_VIA.** Fast-net vias only, a ground via within 3 mm (`ground_via.reach_mm`); B.Cu layer changes only.
- Hot loops are in `board_checks.json` (`hot_loops`); the gate is clean on this placement.

## Decisions the user made on 2026-11-23

- **U18 rotation:** 0 instead of 180 (pins 1-4 face J11, 5-8 face J12; at 180 they faced away); 9 parts moved.
- **U105** moved off the back of U101.
- **Fan-out ring** round every fine-pitch IC (see Placement).
- **One 0.2 mm neck rule:** U23 pad 8 only, suppressed with a reason in `board_checks.json`.
- **C420 moved 1 mm** in +x (`NUDGES`) so a `+12V` via fits at its pad 1.
- **`net_currents`** (`board_checks.json`): `Net-(F1-Pad1)`, `VIN`, `VSW`, `+12V` 10 A (F1 10 A, J2 9 A per circuit);
  `Net-(J11-Pin_1)` and `Net-(J12-Pin_1)` 15 A (ACS37800 +-15 A, TE 2305908 15 A); `ISO_GND` 15 A (the amplifier
  return); `+12V_FAN` 0.5 A (3 x Noctua NF-F12 PWM at 0.05 A max = 0.15 A, rounded up); `+12V_PUMP` 2 A
  (FreezeMod D5 18 W / 12 V = 1.5 A, rounded up); `+5V` stays 2 A because J35 pin 2 and J40 pin 1 export 5 V
  unfused (defined loads sum to 1.36 A: U28 0.64, JP12 / 14 / 16 / 18 0.124 each, FB4 0.125, JP2 0.06, D13 0.04);
  `+16V5`, `-16V5`, `+15V`, `-15V` 0.5 A. `+3V3` has no figure.
- **TRACE_CURRENT tests locked main copper against the net current, branches against class width** (above).
- **Ground-via and return-path rules now fast nets only, 3 mm.** Earlier rules covered every signal and gave
  RETURN_PATH_GAP 89 and VIA_NO_GROUND_VIA 246.
- **F3 / F4 PTCs added** (MF-MSMF050/24X fan, MF-MSMF250/16X pump) on the back, rotation 90, pad 2 (`+12V`) up in
  the 12 V bar and pad 1 down to the header: F3 (42.2, 101.65), F4 (46.6, 101.65). `+12V_FAN` is F.Cu 0.8 mm
  with two vias in F3 pad 1; `+12V_PUMP` is B.Cu 1.8 mm, F4 pad 1 straight to J4.2. F3 vendor STEP; F4 uses
  `MF-MSMF250_envelope.step` (4.83 x 3.41 x 1.60 mm, maximum body, `mfmsmf.pdf` page 6).
- **Line-to-return rule `iso_line_to_return`** in `cryocooler.kicad_dru`: 1.25 mm, all layers, between `ISO_GND` and
  `Net-(J11-Pin_1)`, `Net-(J12-Pin_1)`, `Net-(R64-Pad2)`, `Net-(R65-Pad2)`, `Net-(R66-Pad2)`. **The 1.25 mm figure is
  from memory of IPC-2221 for 120 VAC; it was not checked against the standard (unverified).** `Net-(U18-VINP)`
  (about 0.1 V) is left out. J11 pin 1 and J12 pin 1 are the two ends of U18's current conductor, so no rule
  between them. Every pad-to-pad gap between rule nets and ISO_GND is 2.85 mm or more except footprint-fixed
  VINP gaps (R63 0.85 mm, U18 pins 15 / 16 0.67 mm). The pour clearance comes from the rule.
- **ISO_GND 15 A return** drawn as locked copper on all four layers: 12 tracks, 57 vias (12 in the J11 pin 2 pad,
  45 in the two corners); F.Cu stops at x 4.7 (the J11 pin 1 pad is F.Cu only), B.Cu and inner at x 6.7. Weakest
  locked track 22.4 A against 18.75 A needed; F.Cu 4.35 mm (6.9 A), B.Cu 6.35 mm (9.1 A), In1 and In2 6.35 mm (4.6 A each),
  so F.Cu + B.Cu alone reach 16.1 A and the inner layers are needed.

## Known weak spots

- **Two `+5V` pinches** could not reach 1.1 mm and have only partial B.Cu partners (the check credits 1 A per via):
  T2 (50.47, 69.82)-(46.37, 69.82), F.Cu 0.65 mm (1.75 A), boxed by L1.1 and GND / +12V vias, partner B.Cu 0.65 mm over
  1.8 mm of its 4.1 mm; pinch (70.0, 61.46)-(75.0, 61.46), F.Cu 0.70 mm (1.85 A), 0.77 mm between the C409 pads and the
  `IO2_GATE` track, partner B.Cu 0.70 mm (73.1, 61.48)-(74.6, 61.48). **Physically the F.Cu-only stretches carry 2 A at
  about 12-13 C rise, not 10 C** (inferred).
- **`+12V` row piece:** the F.Cu row piece (43.8-46.85, 98.88) is 2.24 mm wide (R78 pad 2 sits 0.15 mm above), so its B.Cu
  partner carries more; vias stay out of x 45-47.7, y 100.9-102.8 so the In2 `+3V3` island under C76 / the fan header
  stays connected. Weakest locked `+12V` track 13.29 A against 12.5 A needed.
- **RETURN_PATH_GAP is measured per track segment**, so a gap spanning several segments is reported shorter than it is
  (SPI_MISO read 4.2 mm for a 7 mm gap). The re-routed B.Cu runs still cross In2 buses (2.75 mm against 3 mm).
- **Fast nets are listed by auto-generated names** in `board_checks.json` (`Net-(U110-TX)`, `Net-(J14-SCK)` ...). A
  schematic change that renames them silently drops them from the return-path and ground-via checks.
- **Necks:** only U23 pad 8 has one (0.2 mm). Any other pad that cannot keep its class width is a routing failure.
- **J2** silk warnings: stock Molex footprint, left alone.
- 5 partly overlapping same-net track pairs remain (measured at r12, not re-counted).

## Open

- Part labels, pin names and the board ID block are not placed. The ID stamp waits for the user's review and commit,
  then the final `export_fab.py` run (`git-workflow.md`).
- Test points: `TESTPOINT_MISSING` 53 ICs have none (schematic-level gap).
- Housing fit: SW3, J2 and the other wall connectors, and the antenna notch (centre x 84), are not checked against the
  housing walls or its 31 / 10 mm inside heights.
- J2 silk warnings (4) remain.
- F4 uses an envelope STEP, not a vendor model.
- **Pump start-up current against F4 (MF-MSMF250/16X) is unmeasured**; **F4 stock is unconfirmed** (inferred, not
  checked with a distributor).
- **J5 flow-header 12 V is before the fuses**: it comes straight off `+12V`, not through F3 / F4.
- **J35 / J40 export 5 V unfused.**
- **System wiring diagram:** `tools/gen_wiring_diagram.py` is out of step with the rev 7 connector set.
- **Layer GIF:** `tools/layer_stack_gif.py` now writes `fabrication/pcb-layer-stack.gif`; `export_fab.py` does not run it.
- The isolated island (x 0-30, y 37-71) is mostly empty by construction.
