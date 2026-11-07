# Rev 3 — status

Branch `ucs-145-125-rev3`, from `spi-cs-decoder`. **Nothing is committed yet.** The schematic, PCB, fab files and CPL all describe rev 3.

## Stages

- **Stage 1 (done):** schematic, footprints, rules, simulation, firmware, BOM, docs.
- **Stage 2 (done, awaiting your review):** references renumbered, parts placed, board routed, fab files, CPL and renders exported.

## State

- **Schematic:** see "Checks" below for the latest results. Datasheet findings are in `kicad/DESIGN_REVIEW.md`, "Rev 3".
- **PCB:** see "PCB" below. Board ID reads `rev 436f6b4`, the commit the fab files were generated from.
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
- J11 / J12: back on the TE 2305908 SMT headers at their rev 2 spots (11.25, 21.0 and 11.25, 33.5), replacing the MSTBA parts `rev3_placement.json` still lists. J12+ can't take its rev 2 F.Cu path at x 15.4, because C7 sits there, so it runs on a 2 mm B.Cu track at x 13 between via groups: 6 at y 29.6-30.6 and 5 beside U18. The ISO_GND link at x 7 and its five vias match rev 2.
- D13: WS2812B-2020 at the old LED's centre (68, 35), rotation 90, so VDD, DIN and GND face the same way as before. The GND diagonal that crossed the part and the via at (68, 36) are gone. Model `WS2812-2020.step` is the user's file from `dev/ws2812-2020-1.snapshot.4`.
- SW1 / SW2: EVQ-P2F02K at the PTS810's centres, rotation -90. Moved for it: the +3V3 F.Cu run at y 8.3 is gone and U1 pad 2 has its own via to the In2 plane; DISP_RST runs at y 10.425 between SW1's rows; DISP_DC is on In2 at y 15 past SW2's GND land; ESP_EN, ESP_BOOT and three GND vias shifted off the pads. Each GND land has a via to In1.

`tools/board_edit.py` applies rip, track and via edits from JSON.

**DRC with schematic parity:** 0 errors, 0 unconnected, 0 parity. 11 accepted warnings:
- 6 `silk_edge_clearance`: J11, J12 and J14 body lines at the board edge.
- 4 `silk_overlap`: part outline ticks at R94/C87, U16/C3, R70/R71 and R49/R50.
- 1 `lib_footprint_mismatch`: U1, as in rev 2.

**Accepted compromises:**
- PWR_INT has 18 vias, TOUCH_IRQ 15 (both slow). SPI_SCK has 22 and SPI_MOSI 20.
- 38 short off-angle segments remain where `octilinear.py` found no clean path.
- U6's exposed pad has one via, because In2 and back traces block more.

**3D models:** the nine vendor STEP files for rev 3 parts are new in `lib/cryocooler.3dshapes` and listed in `LOCAL_STEP_MODELS` in `tools/pcbmodels.py`. Seating and pin 1 were checked by render and mesh bounds; U3, U14 and U34 show no pin 1 mark to compare. Q1 uses the AONR21305C file. The `SRP7050TA` model prints `2R2` on L2 and L3 whatever the real value is.

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
- U33 is one array for 4 lines spread over 35 mm.
- TPS62822 footprint pads are 0.8 x 0.25 mm against 0.6 x 0.25 mm in the datasheet: unresolved.
- J2 and F1 at 4 A.
- J3 / J4 have no rated right-angle part.
- J15 cable contact side.
- SW1 / SW2: no maker datasheet URL confirmed, no Mouser part number recorded (order EVQ-P2F02K by MPN). 5.0 N force. C42 and C14 discharge past the 20 mA rating for a moment on a press.
- **Trace angles:** 6 segments aren't 0/45/90: USB_D- (10 mm on In2, under SW1), EXPANDER_INT (5.4 mm), U3 OUT (1.2 mm), -15V (0.9 mm), +3V3 (0.8 mm), D16 K1 (0.3 mm).
- D13: Adafruit 4684 was listed out of stock on 2026-11-06 (100 pack: Adafruit 6428). Check the new RMT timing and colours on the bench.
- `src/main.cpp`: the indicator timer check uses `<`, so `indicator::update()` runs on every loop pass rather than every 100 ms. Harmless now that frames only go out on a colour change. Left as is.
- J12 (TE 2305908-3) stock: one listing shows Last Time Buy, another in production. Confirm before ordering.
- C55 stays at 25 V.
- Root sheet: the Supply Switches and Display sheet blocks overflow the bottom of the frame. This predates rev 3.
