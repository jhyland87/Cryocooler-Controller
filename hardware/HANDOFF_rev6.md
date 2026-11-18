# Rev 6 handoff (branch `rev6-schematic`, work in progress)

Rev 6 is rev 5's circuit on a larger board in the Phoenix UCS 237-195 housing
(drawings in `dev/pxc_2203457_...pdf` and `dev/pxc_1104781_...pdf`). **The board in
`hardware/kicad/cryocooler.kicad_pcb` is placed and not routed.** Placement was
approved by the user on 2026-11-18; routing was under way on scratch copies.

## What changed from rev 5

- **Board:** 212 x 84 mm (max PCB in this housing is 212 x 170). The connector wall
  is the bottom edge; the top edge is free and carries the antenna notch. Bottom
  corners use the housing mounts, top corners glue domes (hole size for the
  glue-dome screw not checked).
- **All wall connectors on the front**, none back to back. Left wall, top to
  bottom: J12 cryocooler, J11 amp out, J2 12 V in. Right wall: SW3 power, J8, J9,
  J31, J30. Bottom wall: J5, J3, J4, J6, J13, J10, J14, J1, J36-J39, J32, J33.
- **In-board top-entry JST PH headers** (B*B-PH-SM4-TB, JST ePH.pdf): J15 display
  (6-pin, replaces J15 + J21), J34 RS-485 (4), J35 SPI expansion (10), J40 AUX (5).
  Envelope 3D models only; no vendor STEP.
- **J40 AUX header (new):** 5 V, 3V3, GPIO11, GPIO13, GND. 100 R and a TPD1E05U06 on
  each line, 4.7 k pull-ups not fitted. UART, I2C, 1-Wire, touch (T11, T13) or GPIO.
  ADC2 on these pins does not work with WiFi on.
- **LT3045EDD** (3 x 3 mm DFN) replaces the LT3045HMSE (MSOP). Same datasheet.
- **J14 IMU stays** a Molex Micro-Lock Plus on the wall. **J2 stays** the 2 x 2
  Mini-Fit Jr (the user considered the 2-pin 39-30-0020 and kept the 4-pin).
- **Rules:** signal classes 0.15 mm track / 0.15 mm clearance / 0.45-0.2 via;
  Power12V router width 0.5 mm (was 0.8; user told, not yet confirmed); the four
  `tight_*` 0.1 mm rules are gone; `via_in_pad_clearance` applies against pads only;
  new `iso_barrier` rule, 1.5 mm between the isolated nets and everything else (the
  keep-out width, not a certified creepage figure).

## Checks (2026-11-18)

ERC 0, `datasheet_rules` 609 of 609, `verify_netlist` 497 parts / 379 nets, no
mismatches, `check_symbols` 0. Pre-route board (planes, plane ties, locked copper):
DRC 0 errors.

## Where routing stands

Everything below is on scratch copies; rerun it, the scratch folder does not persist.

```bash
cd hardware/kicad/tools
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
OUT=<scratch dir>; cp ../cryocooler.kicad_pcb $OUT/rev6.kicad_pcb
cp ../cryocooler.kicad_pro $OUT/rev6.kicad_pro; cp ../cryocooler.kicad_dru $OUT/rev6.kicad_dru
FREEROUTING_HIDE=1 PYTHONHASHSEED=0 $KPY rev6_board.py route $OUT/rev6.kicad_pcb $OUT/rev6_routed.kicad_pcb 1 > $OUT/route.log 2>&1
```

- **Round 1 (about 58 min, 20 passes):** KiCad DRC found 96 unconnected (rev 5 had
  128 after its first round): +3V3 40, +12V 23, VIN 11, +3V3_SG 6, +5V_IO 5, GND 4,
  and 7 signals (Net-(U15-SW), EXP_SCK, EXP_CSA, SPI_SCK, RS485_RTS_N, CS_ADDR_A,
  IMU_CS). Faults: 199 segments necked to 0.11 mm, 58 tie vias with a 0.3 mm drill.
- **Round 2 was started** with `--router.automatic_neckdown=false`, the tie-via drill
  restored after import, and Power12V at 0.5 mm. Its result was not read.
- **Next:** read round 2 (DRC with `--refill-zones --all-track-errors`, the project's
  `.kicad_pro` and `.kicad_dru` copied beside the scratch board under its basename),
  then the repair loop in the `kicad-pcb-edit` skill (gridroute, plane ties for the
  +3V3 pour islands), `finish`, DRC with schematic parity to 0 / 0 / 0, then copy
  over `cryocooler.kicad_pcb`. Pads the tie step could not reach: U11 pad 9, U41
  pad 6, U51 pads 3 and 5.

## Routing state when paused (2026-11-18, later the same day)

Best board: `kicad/backup_rev6_routing_wip/rev6_2_open.kicad_pcb` (with its
`.kicad_pro` / `.kicad_dru`). **2 unconnected, 0 DRC errors**, every track 0.15 mm
or wider, no 0.1 mm exceptions. `cryocooler.kicad_pcb` is still the placed board.

- Open: `IMU_CS` (via in U36 pad 4 at 97.29, 64.61 to U32 pad 8 at 120.31, 21.25)
  and one leg of `CS_ADDR_A` (B track end at 98.6, 24.85 to U32 pad 23). Both end
  at the chip-select decoder U32, the one crowded spot.
- How it got here: round 1 of Freerouting (round 2 with neck-down off was worse and
  was stopped), thin segments widened to 0.15 mm, tie-via drills set to 0.2 mm,
  clearance faults ripped, `gridroute.py` with `FINE=1 CLEAR=0.15
  VIA_TRACK_CLEAR=0.15`, `plane_ties.py`, then hand edits: an In2 link for
  `IO_EXP_INT_N`, a via-in-pad for `IMU_CS` with the In2 `Net-(J14-Pin_3)` track
  jogged round it, a ground via in U32 pad 19, and **U51 and C13 moved 3.6 mm right**
  (U51 sat on the front over U32's pads). The user allowed small part moves.
- `gridroute.py` now takes `VIA_TRACK_CLEAR` (new via to tracks) apart from the
  0.1 mm it keeps to pads.
- Next: `python3 backup_rev6_routing_wip/unstick2.py <stem> $PWD/tools IMU_CS
  119.5,21.3 2.2` and `... CS_ADDR_A 124.6,24.3 2.0` on a scratch copy (about 9 min
  each; it keeps a trial only if the open count falls). If they fail, re-place with
  wider part gaps round U32 rather than more trials. Then `finish`, DRC with
  schematic parity, copy over `cryocooler.kicad_pcb`.
- Running the KiCad tools steals window focus on the Mac; run them when the user
  is away from it.

## Not done

- Part labels, section outlines, pin names, REV6 mark, board ID.
- Render cameras: the angle view is off-centre and the four edge views are framed
  for the 120 mm board (`RENDERS` in `tools/export_fab.py`).
- Docs: `README.md` hardware table, `hardware/kicad/README.md`, `DESIGN_REVIEW.md`
  entry, `fabrication/README.md`, the rules index. `gen_bom.py` not re-run.
- Ten parts sit outside their section: C33 C34 D13 D15 Q22 R13 R52 R83 R84 R88.
- JLCPCB stock for the 5-pin and 10-pin PH headers, and a price for this outline.
- ISOW7841AQDWERQ1: Mouser had 41 on 2026-11-18, Digi-Key none.

## Open with the user

- What goes in the housing lid window, and which side walls (flat or Pi-cut).
- Whether Power12V may stay at 0.5 mm.
- A standards-based spacing for the 120 VAC nets.
- `tools/placement_view.py` draws a placed board with its sections (SVG), for a
  layout review before routing.
