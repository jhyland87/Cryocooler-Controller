# Rev 4 on the UCS 125-87 board — status

Branch `ucs-125-87-rev4`, from `ucs-125-87-rev3` (be0e7f9). Same 100 x 62 mm board and
circuit as rev 3 with the changes below. Not ordered, not built, not bench tested.
Read `HANDOFF_ucs125_rev3.md` for everything this note doesn't mention; the datasheet
checks for the new parts are in `kicad/DESIGN_REVIEW.md` under "Rev 4".

**Finished, checked and approved by the user (2026-11-12).** The fab files and the
board ID are not done yet. Start at "Where it stands".

## Where it stands

| Area | State |
|---|---|
| Schematic, symbols, footprints | Done. ERC 0, 396 / 396 datasheet rules, `verify_netlist.py` and `check_symbols.py` pass; 309 parts, 246 nets |
| Firmware | Done, unchanged since the WIP checkpoint, where it built and 277 native tests passed. Not run on hardware |
| Board | Done. 313 footprints, none off the board. DRC: 0 errors, 0 unconnected, 0 parity, 23 warnings |
| Labels | Applied (`ucs125_rev4.py labels`) |
| BOM, CPL, renders | Regenerated from the finished board |
| Gerbers, JLCPCB zip, board ID | **Not done.** `kicad/fabrication/gerbers` is still rev 3 and the board ID reads rev 3's hash |

**DRC warnings:** the 22 of rev 3 (16 `silk_overlap`, 4 `lib_footprint_mismatch`, 2
`silk_edge_clearance`) plus one new `silk_overlap`: the pin-1 dots of U45 and U47
land on the same spot, because the two clamps face each other. It prints as one dot
between the two pin 1 pads. Accepted by the user (2026-11-12), so 23 is the baseline
for this board.

**Still to do, in order:**

1. Attach the USB4205's STEP model to J1 (`pcbmodels.attach_missing_models`; the file
   and its table entry are in place) and redo the renders. Held back because KiCad
   had the board open.
2. Stamp the board ID with the hash of the commit that holds the finished board, run
   `export_fab.py`, commit again.
3. Delete what rev 4 left unused, once confirmed (list under "Unused after rev 4").
4. Housing: every wall cut-out moved (open item, as on rev 3).

**Not verified:** the ACS37800 with SCLK running while CS is high (hence the SCK
gate), the keying of fan plugs in X2510H housings, the USB current budget. The
OPA4990 has an envelope 3D model only, and so does the USB4205 on the board until
step 1 above is done. GCT's STEP model of the USB4205 was checked against the
footprint: its feet land on the pads and its pegs in the holes. XKB's STEP model of
the X2510WRS
shows bare pins past the body, where the drawing has a friction wall; the labels
clear both. Nothing is bench tested.

**Weak spots of the routing.** Everything is connected and DRC clean, but the board
was closed with rip-up routing on top of rev 3 copper, and it shows:

| What | Rev 4 | Rev 3 |
|---|---|---|
| Vias | 761 | 586 |
| Segments off 0 / 45 / 90 that `octilinear.py` could not straighten | 21 | 10 |
| `NTC_ADC` | 163 mm, 23 vias | 92 mm, 7 vias |
| `INA239_ALERT` | 222 mm, 11 vias | 114 mm, 3 vias |
| `DISP_CS` | 202 mm, 19 vias | 74 mm, 8 vias |
| `SPI_SCK` | 201 mm, 21 vias | 164 mm, 15 vias |

- `NTC_ADC`: J6 reaches the clamp (U33) by way of the old header spot on the left of
  the board. A direct route from the new corner position was tried and has no path.
- `INA239_ALERT`: the alert LED branch (R9, D6) joins the rest round the bottom and
  left of the board.
- These are DC or slow signals apart from `SPI_SCK`. A clean-up pass on them is
  worth doing before ordering if there is time.

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
- **J6** sits back to back with J4, in the corner. Moving it was tried (the gap by
  the display connector, the top wall, a shared header with J13) and each spot
  blocks other nets.
- **J13** is unchanged: the switched +12 V relay output on GPIO16.
- **Housing:** every wall cut-out moves again (open item, as on rev 3).

## Board edits

The routed rev 3 board was edited in place; copper outside the changed areas stays.

- **Script:** `kicad/tools/ucs125_rev4.py` (KiCad's python). Run once; don't re-run
  `place` on the finished board.
  - `plan`: dry run, prints each spot and any clash.
  - `place`: syncs footprints and pad nets to the netlist, sets the wall parts and
    fixed spots, finds free spots for the small parts, removes copper under new pads.
  - `labels`: hides the new parts' reference texts, prints each header's function and
    reference beside its friction wall, drops or moves stale labels.
- **Flow:** `place` → `gen_pcb.py link` → `plane_ties.py` → prune dangling copper
  along the bottom wall → `gridroute.py` in stages (cold head analog nets, +5V, the
  boxed-in nets, then the rest) → rip-up routing for what was left → the hand edits
  below → `ucs125_board.py finish` → ground ties → `octilinear.py` → `labels`.
- **`gridroute.py`** now keeps 0.25 mm from unplated holes (`jlc_npth_to_copper`).
- **Rev 3 parts that moved:**
  - SW3 and U34 to the top edge.
  - Q21 and Q6 to the old Q26 / Q27 spots; C14 clear of the divider arrays.
  - R84 and R404 to the front (beside D13, and beside R402).
  - R29 to the front at (76.7, 48.6), beside Q6 whose gate it pulls up.
  - C23 to the front at (69.1, 43.2), on the `NTC_ADC` run beside the clamp U33.
- **Rev 3 copper removed on purpose:** the +3V3 run on the front from (83.5, 36.2) to
  the via at (90.3, 32.2). It crossed the spot U43's vias and R508 need; the In2 pour
  carries +3V3 at both ends.

### Hand edits after routing

These exist only in the board file.

- **Q5 drain (Q6 gate):** R29 moved to Q6, so the +12V string that fed its old spot
  was freed. Its back run from the via at (78.55, 48.65) to Q5 now carries the Q5
  drain; the In2 run and two vias are gone.
- **U41, C301, C302 supply:** the In2 +3V3 pour under them is an island, cut off by
  the USB pair. R501 was turned (pin 1 up, at (29.7, 22.0)) and U41 pin 6 gets +3V3
  by a back track from the via at (29.05, 21.9). A front link and a via at
  (31.15, 25.0) join C301 and C302 to it.
- **U42 pin 3 (GND):** the +12V back run beside it moved 0.14 mm so a 0.15 mm ground
  track fits between it and the `SPI_MISO` via, into the pour north of U42.
- **C302** turned: its ground pad now sits beside the via at (32.3, 25.8).
- **C17 pad 2 (GND):** no via fits nearby (In2 is full there). A ground track runs
  from the pad along y 33.7 / 33.8 to a new via at (62.45, 33.85); `NTC_ADC` under
  C17 moved 0.15 mm down to make room. On rev 3 this pad returned through 7 mm of
  pour to one via, so the bypass is no worse than it was.
- **C24 pad 2 (GND):** `INA239_ALERT` was re-routed off the front around C24, and a
  ground track joins the pad to the pour west of the fuse.
- **SW2's lower ground pad:** joined to the ground via above it; D83's anode line
  was re-routed round it.
- **New ground vias:** U2 pin 2 (20.87, 9.58, under C4's ground pad), J6 pin 2
  (75.0, 51.25, with a track from Q61 pin 4 to J6 pin 2), D1 pin 2, C49, C40, Q21,
  R87. C18 and U17 pin 6 got a track to a via that was there.
- **Small:** R84 0.2 mm east, clear of D13's outline; the `RTD_2` track at J10 pin 2
  trimmed to end on the pad; labels STATE, R53, R402 and U35 moved off pads.

## Unused after rev 4

Nothing here is deleted yet; each needs the user's OK.

- `kicad/tools/rev4_wip/`: the routing helpers from the WIP checkpoint, older than
  the ones the board was finished with.
- `kicad/tools/softroute.py` no longer runs (it calls `gridroute.apply_iso`, which
  is gone); `rev4_wip/soft8.py` replaced it for this board.
- `kicad/tools/link_usb_vbus.py`: a post-Freerouting fix for the USB4105's VBUS pads.
- Footprints: `FanHeader_4P_P2.54mm_Horizontal`, `Sullins_SWR25X-NRTC-S02-RB-BA_…`,
  `Wurth_WR-WTB_61900311021_…`, with their entries in `make_footprints.py`,
  `gen_bom.py`, `part_links.py` and `pcbmodels.py`.
- Models: `SWR25X-NRTC-S02-RB-BA.step`, `SWR25X-NRTC-S03-RB-BA.step`,
  `fan_header_90deg.step` and the three matching `_envelope.step` files.
- The X2510WRS headers use XKB's STEP models (`lib/cryocooler.3dshapes/X2510WRS-0N-9TSN/`).
  Their envelope models, and the USB4205's, are only the fallback when the vendor
  files are missing.

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
