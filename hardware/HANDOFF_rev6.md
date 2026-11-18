# Rev 6 handoff (branch `rev6-schematic`)

Rev 6 is rev 5's circuit on a larger board in the Phoenix UCS 237-195 housing
(drawings in `dev/pxc_2203457_...pdf` and `dev/pxc_1104781_...pdf`). **The board in
`hardware/kicad/cryocooler.kicad_pcb` is placed, routed and passes DRC.** Not bench
tested, not ordered. Details and reasons: `kicad/DESIGN_REVIEW.md`, "Rev 6".

## Checks (2026-11-18)

- Schematic: ERC 0, `datasheet_rules` 609 of 609, `verify_netlist` 497 parts / 379
  nets with no mismatches, `check_symbols` 0.
- Board: DRC with schematic parity 0 errors, 0 unconnected, 0 parity. 12 warnings:
  6 `silk_edge_clearance` (J2, J11), 4 `silk_over_copper` (U32),
  2 `lib_footprint_mismatch` (U1, U18).

## What changed from rev 5

- **Board:** 212 x 84 mm (max PCB in this housing is 212 x 170). The connector wall
  is the bottom edge; the top edge is free and carries the antenna notch. Bottom
  corners use the housing mounts, top corners glue domes.
- **All wall connectors on the front**, none back to back. Left wall, top to
  bottom: J12 cryocooler, J11 amp out, J2 12 V in. Right wall: SW3 power, J8, J9,
  J31, J30. Bottom wall: J5, J3, J4, J6, J13, J10, J14, J1, J36-J39, J32, J33.
- **In-board top-entry JST PH headers:** J15 display (6-pin, replaces J15 + J21),
  J34 RS-485 (4), J35 SPI expansion (10), J40 AUX (5).
- **J40 AUX (new):** 5 V, 3V3, GPIO11, GPIO13, GND. UART, I2C, 1-Wire, touch or GPIO.
- **LT3045EDD** (3 x 3 mm DFN) replaces the LT3045HMSE (MSOP).
- **Rules:** 0.15 mm track and clearance for signals, 0.45 / 0.2 mm vias, no 0.1 mm
  exceptions, `Power12V` 0.5 mm for the router, new `iso_barrier` rule (1.5 mm).

## Deviations to know about

- **`IMU_CS` runs 2 mm on In1**, the GND plane, at (119.8, 27.5-29.55): the only
  way through the chip-select lines round the decoder U32.
- **U51 and C13 sit 3.6 mm right of where the approved placement had them**
  (`rev6_board.py place` would put them back over U32's pads).
- Via in U36 pad 4, ground via in U32 pad 19, and the In2 `Net-(J14-Pin_3)` track
  jogged round the U36 via.

## Tools

- `tools/rev6_board.py`: placement, pre-route and routing for this outline (modes
  as `rev5_board.py`, plus `rules`). **Do not re-run `place` or `route` on the
  routed board:** the hand work above exists only in `cryocooler.kicad_pcb`.
- `tools/placement_view.py`: draws a placed board with its sections (SVG).
- `tools/gridroute.py`: `VIA_TRACK_CLEAR` sets a new via's clearance to tracks
  apart from the 0.1 mm it keeps to pads. Rev 6 ran it with
  `FINE=1 CLEAR=0.15 VIA_TRACK_CLEAR=0.15`.
- `kicad/backup_rev6_routing_wip/`: routed snapshots (`rev6_2_open`, and
  `rev6_routed_clean`, the finished board before labels) and the one-off repair helpers
  (`unstick2.py`, `rip.py`, `box.py`, `near.py`, `drc.sh`).
- Running the KiCad tools steals window focus on the Mac; run long jobs when the
  user is away from it.

## How it was routed

Freerouting round 1 (20 passes, 58 min): 96 unconnected in KiCad, 7 of them
signals. Round 2 with neck-down off was worse and was stopped. On round 1's board:
thin segments widened to 0.15 mm, tie-via drills set back to 0.2 mm, clearance
faults ripped, `gridroute.py` (113 to 8), a rip-up loop (8 to 5), hand links and
the U51 move (to 1), then `route_legs.py` with way-points, a hand-drawn escape at
U32 pad 8 and the In1 hop. `rev6_board.py finish`, `gen_pcb.py link`,
`prune_flagged.py` until clean.

## Not done

- 73 parts have no label; 9 connectors have no pin names (J3, J5, J9, J35,
  J36-J39, J40).
- Ten parts sit outside their section: C33 C34 D13 D15 Q22 R13 R52 R83 R84 R88.
- Board ID block (the back carries `REV6`); `pcb-layer-stack.gif` is rev 5's.
- No vendor STEP for the JST PH headers (envelopes) or J2.
- Glue-dome screw size against the 3.2 mm top holes.
- JLCPCB stock for the 5-pin and 10-pin PH headers; a price for this outline.
- ISOW7841AQDWERQ1: Mouser had 41 on 2026-11-18, Digi-Key none.

## Open with the user

- What goes in the housing lid window, and which side walls (flat or Pi-cut).
- Whether `Power12V` may stay at 0.5 mm, and whether the 2 mm In1 hop is accepted.
- A standards-based spacing for the 120 VAC nets (the board enforces 1.5 mm).
