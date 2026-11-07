# Rev 3 — status

Branch `ucs-145-125-rev3`, from `spi-cs-decoder`. Rev 3 and the label rework are committed and pushed. The schematic, PCB, fab files and CPL all describe rev 3.

## Stages

- **Stage 1 (done):** schematic, footprints, rules, simulation, firmware, BOM, docs.
- **Stage 2 (done, awaiting your review):** references renumbered, parts placed, board routed, fab files, CPL and renders exported.

## State

- **Schematic:** see "Checks" below for the latest results. Datasheet findings are in `kicad/DESIGN_REVIEW.md`, "Rev 3".
- **PCB:** see "PCB" below. Board ID reads `rev f85d84d`, the commit the fab files were generated from.
- **Firmware:** builds, native tests pass. Nothing has run on hardware.

## Reference numbers

Renumbered on 2026-11-06 so parts with the same MPN are consecutive. Only R, C and D changed; U, Q, L, J and TP kept their numbers. `tools/ref_map_rev3.py` maps old to new. `tools/rev3_board.py` and `tools/rev3_placement.json` keep the old numbers, because they ran before the renumber.

## Pins kept spare

| Pin | Notes |
|---|---|
| GPIO5, GPIO7 | 3.3 V, ADC1 |
| GPIO47 | 1.8 V only |
| Expander GP2, GP3, GP5 | Weak pull-ups on in firmware |

U25 (MCP23S08), U27 (TSC2046E), U31 and U32 (decoder) all stay.

## Firmware changes

- `AD5453_SYNC` replaces `MCP4921_CS`, on the same decoder output. Frames are 2 control bits + 14 data bits, SPI mode 1. Never send C1,C0 = 11.
- `AMPLIFIER_RESOLUTION` is 16383. Ramp rates, shutdown step, backoff step and the `rampTo()` dead-band are scaled by 4, so wall-clock behaviour is unchanged.
- New `power_button` module: INT# on GPIO1 latches through an interrupt, then `state_machine::stop()`, wait for DAC = 0 (5 s limit), then KILL# low.
- `indicator.cpp`: sends the WS2812B-2020 through its own RMT frame instead of `neopixelWrite()`, and only when the colour changes (see `DESIGN_REVIEW.md`).
- `RailFlags` has only the two LT3097 flags. The LT8582 flags and READY / FAULT writes are gone. The WS2812 still shows state.
- `gpio_expander::lastPins()` / `pinLow()` read a cached port byte. `sysinfo` logs INA239 ALERT changes, and `display::touchPressed()` reports PENIRQ.
- ACS37800 scale comes from `setBoardParameters(15, 4 MΩ, 4.02 kΩ)`. `AMPLIFIER_MAX_CURRENT_A` (5 A) is inside the new ±15 A range.
- **No proto field changed**, because none of the removed flags were in telemetry.
- **I2C:** no firmware code calls `Wire`. `lib/ACS37800` keeps Pololu's unused I2C branch, Adafruit BusIO includes `Wire.h`, and `lib/PCAL9535A` is an I2C driver nothing includes.
- **PSRAM ECC is not available.** The framework's prebuilt `opi_opi` libraries have no `CONFIG_SPIRAM_ECC_ENABLE`, and turning it on needs a custom library build. The module's 65 °C ambient limit stands, so measure the enclosure temperature.

## PCB

UCS 145-125 board, 120 x 100 mm, 4 layers.

**Pipeline, in order:** `tools/rev3_board.py` on the rev 2 board, `gen_pcb.py link`, `gridroute.py`, `plane_ties.py`, `prune_flagged.py`, the hand copper below, `renumber_refs.py board`, `rev3_silk.py`, `silk_fix.py`, `mask_label_plan.py`, `mask_labels.py`, `export_fab.py`.

**The board file is the source of truth.** These edits exist only in `cryocooler.kicad_pcb`, so re-running the pipeline loses them:
- U36 fan-out (IMU_INT1, IMU_CS, SPI_MISO).
- TOUCH_IRQ: escape from U25 pad 16 and its legs across the board, made with `tools/route_legs.py`. Way-point vias must be added and routed in one process, or KiCad gives them the pour's net on reload.
- U20: 9 exposed-pad vias, `+5V_PS15` and SEQ rerouted around them, wider necks on the boost nodes.
- U16: SW neck, GND via and the `+5V_OR` link. Exposed-pad vias on U14, U6, U25, U36 and U37.
- C20 moved to the VIN diagonal.
- J11: TE 2305908-2 SMT header, replacing the MSTBA part `rev3_placement.json` still lists. Pins are now at (8.75, 11.42) and (8.75, 16.42), moved for J12.
- J12: TE 643228-1, also not in `rev3_placement.json`. See "J12: TE 643228-1" below.
- D13: WS2812B-2020 at the old LED's centre (68, 35), rotation 90, so VDD, DIN and GND face the same way as before. The GND diagonal that crossed the part and the via at (68, 36) are gone. Model `WS2812-2020.step` is the user's file from `dev/ws2812-2020-1.snapshot.4`.
- SW1 / SW2: EVQ-P2F02K at the PTS810's centres, rotation -90. Moved for it: the +3V3 F.Cu run at y 8.3 is gone and U1 pad 2 has its own via to the In2 plane; DISP_RST runs at y 10.425 between SW1's rows; DISP_DC is on In2 at y 15 past SW2's GND land; ESP_EN, ESP_BOOT and three GND vias shifted off the pads. Each GND land has a via to In1.

- Moved to fit a label beside every part, all inside their sections:
  - By x: C7, C53 and C54 -0.3, C74 +0.2, FB1 +0.09, C40 -0.1, C51 +0.6, C6 +0.3, C32 -0.15, R76 +0.1.
  - C87 from (23, 79.75) to (23, 80.83), R34 from (23, 80.8) to (23, 82.85), R82 from (29.65, 48.5) to (29.07, 48.9).
  - Vias: `U17-OUTB` from (21.85, 20.05) to (21.85, 19.1), `U21-PGFBP` from (75.2, 53.85) to (75.444, 54.95).
  - Tracks: ISO_5V from C54 to TP13 now runs at x 16.85, with C7's stubs extended to x 16.2. +3V3 and U16-FB follow C87 and R34, +3V3 follows C51, and the B.Cu D8-A and +3V3 stubs follow R82.
  - Silk cuts: C53's right tick, C74's left tick and x 19.6-21.95 of U18's bottom line.

- Moved so all 40 U1 pads can show a pin name (2026-11-06, uncommitted):
  - Test points: TP34 from (73.25, 17.65) to (70.9, 17.65), TP35 from (73.25, 20.34) to (70.9, 19.9), TP40 from (73.25, 24.69) to (70.9, 23.711), TP33 from (80.825, 27.75) to (75.35, 27.4).
  - SW2 from (66.5, 17.675) to (66.3, 17.675), so the test point courtyards clear it. SW1 stayed, so the two switches are 0.2 mm out of line.
  - Vias: `COMP_RELAY_EN` from (72.496, 18.649) to (72.496, 21.1), with F.Cu from pad 9 down x 72.4 and In2 shortened; `ACS_CS` from (74.025, 18.811) to (74.1, 19.1), 0.6 to 0.45 mm; `GND` from (84.6, 28.1) to (84.9, 28.5) and from (85.9, 27.85) to (87.81, 26.9).
  - Tracks: `AMP_REM_EN` now detours left of TP34 along x 70.0 to its unchanged via, and runs on down to TP35. TP40 and TP33 each have a new stub. USB_D+/D- didn't move.

`tools/board_edit.py` applies rip, track and via edits from JSON.

**Labels:** every one of the 306 referenced parts has one: 283 mask openings (0.5 mm, or 0.7 mm on large parts and connector pins) and 55 silk at 0.7 mm / 0.1 mm stroke, in `tools/mask_labels.json`, plus the TP5, TP7 and TP34 footprint fields. There are no arrows. Labels follow the user's hand edits of 2026-11-06: horizontal, centred right above or below the part, in mask at 0.5 mm where there's solid ground pour, with silk only as the fallback. Test points are named by their function, not their TP number. Connector pin names sit vertically above their pins. Treat `mask_labels.json` as the source: `mask_label_plan.py` follows an older rule and would undo this. `tools/silk_label_missing.py` adds silk labels for parts that have none, but it can still add arrows, so check its output. J10's pin names are now 0.7 mm, and `S+` was missing and is back. Order high-precision silkscreen printing.

**U1 pin names:** all 40 side and bottom pads have a name on F.Silkscreen at 0.7 mm / 0.1 mm stroke, outside the module body. They are plain board text, not in `mask_labels.json`, so edit them in the board. Names follow Espressif's WROOM-2 datasheet v1.7, Table 3-1. Two groups differ from the project's U1 symbol: pads 13 and 14 read `IO19` and `IO20` (symbol: `USB_D-`, `USB_D+`), and pads 28-30 read `NC` (symbol: `IO35`-`IO37`). Every name sits on its pad's centreline and crosses vias where it has to, which relies on filled and capped vias. Don't run `silk_fix.py`.

**DRC with schematic parity:** 0 errors, 0 unconnected, 0 parity. 11 accepted warnings, plus the text size warnings below:
- 4 `silk_edge_clearance`: J11 and J14 body lines at the board edge. J12's silk stops inside the edge.
- 3 `silk_overlap`: part outline ticks at U16/C3, R70/R71 and R49/R50.
- 4 `lib_footprint_mismatch`: U1 as in rev 2, and U18, C53 and C74 from the silk cuts above.
- 102 `text_thickness` and 102 `text_height`: the 0.7 mm silk text class. The J12 swap didn't change these counts.

No two printed texts overlap (DRC doesn't compare mask text, so this was checked with a script against the true stroke outlines).

**Accepted compromises:**
- PWR_INT has 18 vias, TOUCH_IRQ 15 (both slow). SPI_SCK has 22 and SPI_MOSI 20.
- 38 short off-angle segments remain where `octilinear.py` found no clean path.
- U6's exposed pad has one via, because In2 and back traces block more.

**3D models:** the nine vendor STEP files for rev 3 parts are new in `lib/cryocooler.3dshapes` and listed in `LOCAL_STEP_MODELS` in `tools/pcbmodels.py`. Seating and pin 1 were checked by render and mesh bounds; U3, U14 and U34 show no pin 1 mark to compare. Q1 uses the AONR21305C file. The `SRP7050TA` model prints `2R2` on L2 and L3 whatever the real value is. L1 and L4 use `SRP4020TA-4R7M.step` and `SRP4020TA-R47M.step`, keyed by value because they share a footprint; Bourns' files are upside down, so both are flipped 180 degrees. `SRP4020TA.step` is no longer used.

## J12: TE 643228-1

**Status (2026-11-07):** committed in `f85d84d` and pushed on `ucs-145-125-rev3`, not merged or bench tested. The board ID reads `rev f85d84d`.

The user replaced the TE 2305908-3 SMT header with this through-hole Universal MATE-N-LOK part. Looking into the mating face with tails down, left to right is GND, -, +, which is molded cavities 3, 2, 1. Pin numbers and nets didn't change: pin 1 +, pin 2 - (ISO_GND), pin 3 GND.

**Footprint:** `TE_643228-1_1x03_P6.35mm_Horizontal` comes from drawing C-643228 rev D3 (`dev/ENG_CD_643228_D3.pdf`), not the vendor file. The vendor outline is 1.9 mm short at the rear of the ears and its drill is 1.60 mm; the drawing says 1.52 +/-0.08 mm. Pads are 3.0 mm for current and a real ring.

**Placement:** J12 is at (12.37, 45.8), rotation 90. Pin 1 is at y 45.8, pin 2 at y 39.45, pin 3 at y 33.1. Holes are at (9.83, 53.165) and (9.83, 25.735). The mating face is at x -3.0, 3 mm past the board edge, level with J11's face. J11 moved to clear the upper ear.

**Copper:**
- ISO_GND keeps its 1.5 mm barrier on all 4 layers. Pin 3 now sits north of pins 1 and 2, so a GND tab reaches it across the island. The scripted minimum gap is 1.499 mm.
- J12+ is B.Cu: 2 mm, narrowing to 1.6 mm past the GND tab.
- The ISO_GND F.Cu link from pin 2 to J11 pin 2 is 2 mm, narrowing to 1.2 mm in the same spot. The ISO_GND pours run alongside it. This replaces the x 7 link and its vias.
- Raw 12 V at x 9.5 jogs around the lower hole.
- A pour-only keep-out at (25.25, 40.5)-(26.75, 42) closes a 0.3 mm pour gap at that corner, which HEAD also had. The +3V3 and +5V_OR tracks still pass through that square.
- B.Cu has 7 mm keep-outs around both mounting holes for washers.

**How it was applied:** `tools/j12_643228_board.py` edits the pre-swap board once, then `tools/mask_labels.py` redoes the labels. Don't re-run it on the current board.

**To confirm:**
- 12 A / 600 V and mating plugs 350766-1 and 770018-1 come from distributor listings, not a TE document. The firmware limit is 5 A.
- The TE drawing link in `part_links.py` returned 403 to scripts, so it's unchecked.
- The STEP's tail tips sit 0.2 mm ahead of the drawing's pin line. The drawing sets the holes, so check the tails against a real part. At minimum drill tolerance the hole radius is 0.72 mm and the tail's corner radius is about 0.74 mm.
- Enclosure: the J11 and J12 wall cut-outs must move. J12 needs about 25.4 x 9.2 mm plus plug clearance, and the 3 mm overhang isn't checked against the real wall.
- Assembly: J12 needs hand or selective soldering and 2 screws, and it's no longer in the CPL. About 2.5 mm of tail sticks out below the board.
- Regenerating the schematic also changes D13's stale Product link in `sheets/indicators.kicad_sch`. That file was restored to keep it out of this change, so it comes back on the next regeneration.

## Q1: AONR21307

Swapped from the AONR21305C, which you couldn't get. Same -30 V and pinout, VGS rating is +-25 V. Max Rds(on) at -10 V is 11 mOhm against 6.5, so about 0.38 W against 0.25 W at 5 A hot. Its datasheet has no outline drawing. It names the package DFN 3x3 EP, so the footprint stays the AOS DFN3x3A_8L_EP1 pattern: **compare it against the part or an AOS drawing before ordering.**

## Checks

```bash
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
cd hardware/kicad
python3 tools/make_lib.py && python3 tools/gen_schematic.py
$KC sch erc --severity-all --format json -o /tmp/erc.json cryocooler.kicad_sch
$KC sch export netlist --format kicadsexpr -o /tmp/rev3.net cryocooler.kicad_sch
python3 tools/datasheet_rules.py /tmp/rev3.net
python3 tools/verify_netlist.py /tmp/rev3.net
python3 tools/check_symbols.py cryocooler.kicad_sch
python3 sim/run_ngspice.py sim/sine_chain_ideal.cir
```

Results on 2026-11-06, after the PCB:

| Check | Result |
|---|---|
| ERC | 0 violations |
| Generator: text overlaps, duplicate refs, 4-way junctions | 0 / 0 / 0 |
| `check_symbols.py` | 0 in all four checks |
| `datasheet_rules.py` | 319 of 319 pass |
| `verify_netlist.py` | no mismatches, 306 parts, 211 nets |
| Sine chain | 0, 2.49, 4.98, 7.47, 9.96 Vpp at codes 0, 4096, 8192, 12288, 16383; VREF 9.66 V peak in the over-drive case |
| `pio run` (with `SKIP_DASHBOARD_BUILD=1 SKIP_PROTO_BUILD=1`) | builds |
| `pio test -e native` | 277 of 277 pass (firmware unchanged by the J14 filter change) |

Links in `part_links.py`: every part has one. The analog.com links (AD5453, ADP5071, LTC2954) and the onsemi MMBZ link could not be confirmed by script (no response, or 403), so open them once in a browser. The other new links returned a PDF.

The simulation uses ideal op-amp and AD5453 stand-ins. The KiCad sim project in `sim/` has the same chain, with TI's op-amp models, and those don't converge headless. `sim/screenshots/input-v*.png` show the old AD633 chain.

## Bench list

1. ADP5071 loop stability with the LT3097 input capacitors. Rev 1 values, but the load capacitors differ.
2. 10 Vpp calibration at full code and 0 V at code 0 after power-up. Trim R92 if needed: the AD5453 VREF input is 7-11 kΩ, so R39 gives a part-dependent gain error.
3. Interlock with -15 V removed (Q42 guard).
4. Button press ramps down and powers off. Holding it 6.4 s forces power off.
5. Q1 inrush and SOA on a scope, with the slower gate network.
6. TPS2116 changeover between 12 V and USB.
7. Enclosure temperature against the module's 65 °C rating.
8. TPS62822 noise on the AD9833 and on the `+3V3_SG` rail.
9. ADS1220 IDAC compliance with R55 (1 kΩ) in series on AIN3.
10. ACS37800 readings against a meter, after the range change to ±15 A.

## Still open

- **Test points:** AGENTS.md asks for test points beside every IC. These new or changed ICs have none on their own nets on the same side nearby: U3, U6, U16 (only `+5V_OR`, on the far side), U20 (its rail outputs are at TP11 and TP12, 12-14 mm away, and nothing is on `+5V_PS15`), U34, U35, U36, U37. Some rev 2 ICs are also short (U5, U9, U12, U18, U23, U24).
- **Isolation gap:** the copper gap at the ISO boundary is 1.5 mm, though U17 has 8.1 mm package clearance. If you need the full rating, the pours and keep-out strips have to move.
- **Silk over vias:** allowed by the user on 2026-11-06, but only if the board is ordered with filled and capped vias. U1 pin names, the section names (DISPLAY, SIGNAL GENERATOR, WATER COOLING, RAILS ±15V, POWER GOOD, AMP CONTROL, POWER IN, FROM AMP), `SG 3V3` and the back board ID all cross vias. Confirm the order option covers every via and the 0.2 mm drills; not yet checked with JLCPCB.
- U33 is one array for 4 lines spread over 35 mm.
- TPS62822 footprint pads are 0.8 x 0.25 mm against 0.6 x 0.25 mm in the datasheet: unresolved.
- J2 and F1 at 4 A.
- J3 / J4 have no rated right-angle part.
- J15 cable contact side.
- SW1 / SW2: no maker datasheet URL confirmed, no Mouser part number recorded (order EVQ-P2F02K by MPN). 5.0 N force. C42 and C14 discharge past the 20 mA rating for a moment on a press.
- **Trace angles:** 6 segments aren't 0/45/90: USB_D- (10 mm on In2, under SW1), EXPANDER_INT (5.4 mm), U3 OUT (1.2 mm), -15V (0.9 mm), +3V3 (0.8 mm), D16 K1 (0.3 mm).
- D13: Adafruit 4684 was listed out of stock on 2026-11-06 (100 pack: Adafruit 6428). Check the new RMT timing and colours on the bench.
- `src/main.cpp`: the indicator timer check uses `<`, so `indicator::update()` runs on every loop pass rather than every 100 ms. Harmless now that frames only go out on a colour change. Left as is.
- J12 (TE 643228-1): rating, plugs, tail fit and wall cut-outs still need confirming. See "J12: TE 643228-1" above.
- C55 stays at 25 V.
- Root sheet: the Supply Switches and Display sheet blocks overflow the bottom of the frame. This predates rev 3.
