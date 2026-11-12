# Rev 4 on the UCS 125-87 board — status

Branch `ucs-125-87-rev4`, from `ucs-125-87-rev3` (be0e7f9). Same 100 x 62 mm board and
circuit as rev 3 with the changes below. Not ordered, not built, not bench tested.
Read `HANDOFF_ucs125_rev3.md` for everything this note doesn't mention; the datasheet
checks for the new parts are in `kicad/DESIGN_REVIEW.md` under "Rev 4".

**Work in progress (paused 2026-11-12).** The schematic and firmware are done; the
board is placed and mostly routed but not finished. Start at "Where it stands".

## Where it stands

| Area | State |
|---|---|
| Schematic, symbols, footprints | Done. ERC 0, 396 / 396 datasheet rules, `verify_netlist.py` and `check_symbols.py` pass; 309 parts, 246 nets |
| Firmware | Done. Builds; 277 native tests pass. Not run on hardware |
| Board placement | Done. 313 footprints, none off the board, parity 0 |
| Board routing | **Not done.** DRC: 0 errors, 36 unconnected (below) |
| Labels | **Not applied.** `ucs125_rev4.py labels` is written and was tried on a copy (silk warnings back at the rev 3 figures) |
| BOM, CPL, renders, Gerbers, board ID | **Not regenerated.** `kicad/bom/` and `kicad/fabrication/` still hold rev 3 output |

**Open connections** on `kicad/cryocooler.kicad_pcb` (routing pass 9):

| Net | Between |
|---|---|
| `Net-(D84-GA)` | U43 pin 13 and D84 pin 1 |
| `IO5_SENSE` | RN4 pin 8 and U44 pin 11 |
| `ACS_MISO` | U17 pin 5 and U42 pin 2 |
| `SPI_SCK` | U41 pin 2 and the bus track at (33.9, 32.2) |
| `Net-(J3-Pin_4)` | Q61 pin 6 and the track at (65.2, 49.4) |
| `+5V` | R84 pin 1 to C33 pin 1 and to the track at (84.2, 60.1) |
| `+3V3` | R501 pin 1 and the track at (30.6, 23.7) |
| `GND` | 28 pads and pour islands, left for `plane_ties.py` and the finish step |

**Still to do, in order:**

1. Close the seven nets with `softloop2.sh` (rip-up routing; it closed `Net-(D84-GA)`
   on an earlier pass by moving D84's cathode via).
   - **Freerouting does not help here.** Tried on a copy (2026-11-12, `fr_trial.py`):
     one round, 20 passes, 22 minutes, rev 3 copper locked. It closed none of the
     seven and left the board otherwise as it was (0 errors, parity 0).
   - With the rev 3 copper locked it has nowhere to go; unlocked, it would re-route
     the hand-finished board. It also reads about a dozen rev 3 nets that join
     through pours as open and spends its passes on those.
2. Ground: `plane_ties.py`, then `ucs125_board.py finish`, prune, `octilinear.py`.
3. `ucs125_rev4.py labels`, then DRC back to the rev 3 baseline: 0 errors, 0
   unconnected, 0 parity, 22 warnings.
4. `gen_bom.py`, renders, and after the commit the board ID stamp and `export_fab.py`.
5. Review the docs against the final board, then list what became unused (old
   header and USB4105 footprints and models, `link_usb_vbus.py`) for deletion.
6. Delete `kicad/tools/rev4_wip/`, or fold what is worth keeping into `tools/`.
   `softroute.py` there no longer runs: it calls `gridroute.apply_iso`, which is gone.

**To resume:** the routing runs on a copy, not on the repo board.

```bash
export SCRATCH=/tmp/rev4 && mkdir -p $SCRATCH/out
rsync -a --exclude __pycache__ --exclude fabrication hardware/kicad/ $SCRATCH/kicad/
cp hardware/kicad/tools/rev4_wip/* $SCRATCH/
$SCRATCH/softloop2.sh 'Net-(D84-GA)|/General Purpose IO/IO5_SENSE|ACS_MISO|SPI_SCK|Net-(J3-Pin_4)|+5V|+3V3'
```

Copy `$SCRATCH/kicad/cryocooler.kicad_pcb` back when a step is good (KiCad closed).
`pipeline9.sh` repeats the whole pass from the rev 3 board; it needs
`git show ucs-125-87-rev3:hardware/kicad/cryocooler.kicad_pcb > $SCRATCH/rev3_board_backup.kicad_pcb`
first and takes about 40 minutes.

**Not verified:** the ACS37800 with SCLK running while CS is high (hence the SCK
gate), the keying of fan plugs in X2510H housings, the USB current budget. Nothing
is bench tested.

## What changed from rev 3

- **ACS37800 on the shared SPI bus.** GPIO 11, 12 and 13 are free. CS stays on GPIO17
  (U32 has no spare output).
  - U41 gates SCK into the isolator and U42 gates the isolator's MISO onto the bus;
    both are SN74LVC1G125DRYR, enabled by `ACS_CS`.
  - R501 pulls the gated SCK high (the mode-3 idle level); R502 pulls `ACS_CS` high.
  - The SCK gate was not in `TODO.md`: the ACS37800 datasheet says nothing about SCLK
    with CS high.
- **J7 (panel button) removed.** SW3 is the only power button; U34 still clamps its
  line, now net `PWR_BTN`.
- **General-purpose I/O:** GPIO 5, 7, 11, 12, 13 on J16-J20 (pin 1 signal, pin 2 GND).
  - Each pin: ESD clamp, 100 Ω in series, 100 kΩ / 100 kΩ divider to GND.
  - Each pin has a green LED driven by one OPA4990 section from the divider tap:
    0.5 mA at 3.3 V, proportional below that.
  - U43 drives IO11 and IO12; U44 drives IO5, IO7 and IO13. Each LED's 3.3 kΩ
    (R506-R510) sits on the front beside it.
  - The op amps run from `+5V_OR`, so the LEDs also work on USB power.
  - Only GPIO5 and GPIO7 can read analog with WiFi on. All pins are 3.3 V only.
- **Headers:** every 2.54 mm header is an XKB X2510WRS (all-SMD, right angle), pin
  tips 3.0 mm past the board edge like J11 and J12.
  - J3 FAN, J4 PUMP, J5 FLOW: X2510WRS-04-9TSN (J5 pin 4 unused).
  - J6 NTC, J13 RELAY, J16-J20: X2510WRS-02-9TSN.
  - Fan, pump and flow leads have to be moved into X2510H housings.
- **USB-C:** GCT USB4205-GF-A (flag type, 12.5 mm high), mouth 3.0 mm past the top edge.
- **Multi-element parts:** Q61 (BSS138DW) replaces Q26 / Q27; RN1 (4.7 kΩ) and RN2
  (10 kΩ) replace R41, R42, R46, R47 and R3, R4, R5; RN3-RN5 serve the I/O block.

## USB-only power

Unchanged from rev 3, checked against the netlist and the TPS2116 truth table: with
no 12 V, U28 passes USB VBUS to `+5V_OR`, which feeds the 3.3 V buck.

| Powered from USB alone | Not powered |
|---|---|
| `+3V3` and its jumpered rails: ESP32, ADS1220, INA239, MCP23S08, IMU header, display and touch, NTC and tach pull-ups, DDS and DAC logic | `+5V`: WS2812 status LED, green status LED dies, the ±15 V stage |
| `+5V_OR`: display backlight, the ACS37800's isolated supply, the I/O LED op amps | 12 V: fans, pump, flow sensor supply, relay and amplifier REM outputs |

The USB current budget has not been measured.

## Wall connectors

| Edge | Front | Back |
|---|---|---|
| Top | J1 USB-C, SW3 power button (right of the antenna) | |
| Left | J12 cryocooler | |
| Right | J14 IMU, J16 IO5, J18 IO11, J9 sine out | J20 IO13, J17 IO7, J19 IO12 |
| Bottom | J11 amp current, J2 12 V, J15 display, J3 FAN, J4 PUMP | J5 FLOW, J13 RELAY, J10 PT1000, J6 NTC, J8 amp remote |

- **I/O block:** top to bottom on the right wall: IO13, IO5, IO7, IO11, IO12. Their
  LEDs (D85, D81, D82, D83, D84) sit in the same order in a column on the front,
  just inboard of the headers.
- **J6** sits back to back with J4.
- **Housing:** every wall cut-out moves again (open item, as on rev 3).

## Board edits

The routed rev 3 board was edited in place; copper outside the changed areas stays.

- **Script:** `kicad/tools/ucs125_rev4.py` (KiCad's python).
  - `plan`: dry run, prints each spot and any clash.
  - `place`: syncs footprints and pad nets to the netlist, sets the wall parts and
    fixed spots, finds free spots for the small parts, removes copper under new pads.
  - `labels`: hides the new parts' reference texts, prints each header's function and
    reference beside its friction wall, drops or moves stale labels.
- **Flow (`tools/rev4_wip/pipeline9.sh`):** `place` → `gen_pcb.py link` →
  `plane_ties.py` → prune dangling copper along the bottom wall → `gridroute.py` by
  `route_loop.py` (cut tracks first, then RTD and USB, the LED and header nets, the
  rest of the I/O block, the ACS bus, everything else) → prune → a wider search for
  what failed.
- **`gridroute.py`** now keeps 0.25 mm from unplated holes (`jlc_npth_to_copper`).
- **Parts that moved:** SW3 and U34 (top edge); Q21, Q6 and R404 (to the old Q26 / Q27
  spots, to make room for J6); R84 (beside D12); C14 (clear of the divider arrays).
- **Rev 3 copper removed on purpose:** the +3V3 run on the front from (83.5, 36.2) to
  the via at (90.3, 32.2). It crossed the spot U43's vias and R508 need; the In2 pour
  carries +3V3 at both ends.

## I/O block layout

- **Back, below the board ID:** RN5, RN4, RN3 in a row at y 27.4, facing each other
  pin for pin, then one clamp per header (U45, U47, U48, U49) in the strip between
  RN3 and the header pads. Only the outer rows of the arrays can be reached from
  outside; the inner rows come in through the gap between an array's pad columns.
- **LED drivers:** U44 at (85.4, 19.9) and U43 at (85.3, 33.3), both on the back
  where the front has no pads. U43 uses only the two sections that face the headers.
- **Front:** D85, D81, D82, D83, D84 in a column at x 87.7, each with its 3.3 kΩ
  just below it (R509, IO12's, sits beside J19 instead).
- **Two In2 tracks** (x 87.2 and 87.75) run the length of this block, so vias fit only
  at x 88.2 to 88.6 or left of 86.7.
