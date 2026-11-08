# UCS 145-125 board — status

Branch `pcb-ucs-145-125`. This branch carries the rev 2 work (`HANDOFF_rev2.md`): the LT8582 /
LT3097 rails, the display, the RJ45 IMU jack, 0402 parts and named test points. Here that work
is on the 120 x 100 mm PCB for the Phoenix UCS 145-125 housing. All items in `TODO.md` are
done.

## Reference renumbering (2026-11-05)

R, C and D references are renumbered so parts with the same MPN are consecutive, which keeps order customer references short (`C6-C42`). No part, position, track or connection changed.

- **Map:** `tools/ref_map.py` has old to new. `gen_schematic.py` still allocates its old numbers internally and applies the map when it writes the sheets, so its comments use old numbers. New parts keep their allocated number, above the mapped range.
- **Board:** `tools/renumber_refs.py board` renamed the footprints and auto-named nets; `tools/renumber_silk.py` moved the references of R45, R44 and C41 off part outlines.
- **Tools and docs:** board scripts and this file use the new numbers. Old R, C and D numbers remain in `HANDOFF_rev2.md`, the `gen_schematic.py` comments and any commit before this change.
- **BOM:** `gen_bom.py` now has one line per MPN, and Customer Reference shortens runs of three or more to a range. The JLCPCB files still list every designator.
- **Rev 1 boards:** a built board keeps its old silk, so use the map when reading one.

## State (2026-11-04)

- **Schematic:** ERC 0, all datasheet rules pass, BOM regenerated.
- **PCB:** 4 layers, blue mask, parts on both sides.
  - KiCad DRC with schematic parity: 0 errors, 0 unconnected, 0 parity, 0 silk overlaps.
  - 7 warnings remain:
    - 6 `silk_edge_clearance`: the J11, J12 and J14 body outlines run past the board edge,
      and the fab clips them there;
    - 1 `lib_footprint_mismatch` on U1, from the generator's local edits to the WROOM footprint.
- **Fab files and renders:** in `kicad/fabrication/`.
- **Firmware:** builds. `pio test -e native` passes test_conversions; test_native stops on
  the known `commands.cpp` stub errors.

## Connector choices

| Ref | Part | Notes |
|-----|------|-------|
| J10 PT1000 | Adafruit 4392, JST PH 4-pin horizontal SMD (CW2001-04T) | replaces the M12; footprint from the maker's drawing |
| J11 amp out | TE 2305908-2, right-angle SMT, 5 mm | + / − to U18 (ACS37800); 15 A; SMT pads only |
| J12 cryocooler | TE 2305908-3, right-angle SMT, 5 mm | + / − from U18; pin 3 on board GND, outside the ISO island; 15 A; SMT pads only |
| J14 IMU | Amphenol RJSSE-5380 | plain 8P8C; the three parts in the TODO have magnetics. Signal pads centred between the holes (fixed 0.28 mm offset) |
| J15 display | Hirose FH12-14S-0.5SH | top edge at (53.2, 4), top side, opening faces into the board |
| J6 / J7 / J13 | Sullins SWR25X-NRTC-S02-RB-BA, right-angle 2-pin, 2.54 mm | 3 A; mates with SWH25X housings, so JST PH pigtails no longer fit. Catalog drawing shows 6-20 positions; the 2-pin plate width is an estimate |
| J2 12 V in | Tensility 54-00164, 5.5 x 2.1 mm right-angle SMT jack | centre pin positive; sleeve and switch contacts both on GND. 5.5 A up to 40 C, derating to 0 at 70 C; not rated for mating under load |
| J8 amp REM | Phoenix 1821698, MC 0,5/ 2-G-2,54 SMD R24 | left wall; 6 A; drawing 00783144 rev 02; two 1.2 mm peg holes |
| J9 amp signal | Same Sky MJ-3523-SMT-TR, 3.5 mm mono right-angle SMT jack | tip SIG_SINE, sleeve GND, tip switch unconnected |
| J3 fan / J4 pump | MODDIY CO975 (FC-3+1P-MA) right-angle 3+1 fan header | takes PC fan plugs; footprint from `fan_header_90deg.step`, no maker drawing |
| J5 flow | Wurth 61900311021, right-angle 3-pin locking, 2.54 mm | 3 A; footprint from datasheet rev 002.000; check the locking plate clears the sensor plug. The 3D view uses `SWR25X-NRTC-S03-RB-BA.step` (Sullins, your own model), so it does not show the BOM part |

## How the board was made

1. Place: `gen_pcb.py place`. Re-runs with the same inputs give the same placement, because
   the generator pins `PYTHONHASHSEED`.
2. Route: `gen_pcb.py route <freerouting jar>`.
3. Hand routes: `tools/hand_route.py` adds U4 pin 5 and U20 pins 2, 17 and 22, the
   LT8582 switch-node pours (`sw_nodes`) and the U20 exposed-pad GND vias (`u20_ep_vias`).
   - Its coordinates fit the committed route only.
   - A new autoroute needs new hand routes, checked with DRC.
4. Silk: `tools/silk_fix.py` clears the DRC silk overlaps.
   - It cuts section lines under text, hides colliding reference designators, and nudges labels.
   - It drops the `MCU & USB` and `INDICATORS` section names; those outlines stay.
5. Fab files and renders: `tools/export_fab.py`.

## Open points

- **Via-in-pad:** U20 has via-in-pad on its signal pads (`SIGNAL_VIA_PADS`). Order filled /
  capped vias; see `kicad/fabrication/README.md`.
- **Switch nodes:** SW1, SW2 and the inverting node X are priority-3 copper pours
  (`hand_route.py sw_nodes`). SW1 is one solid pour from U20 pins 1 / 24 to D5 and L2; SW2
  is a ~1 mm strip from pin 13 to L3 plus a B.Cu pour to C76. Pin 12's link under the
  exposed pad stays narrow (~0.28 mm): the pad and a +5V_PS15 track bound it.
- **U20 exposed pad:** 15 GND vias now (was 1), capped via-in-pad.
- **J14 mouth past the edge:** the jack face is 4.37 mm in front of its locating holes, so as
  placed (x 116.65) it sits ~1.0 mm past the 120 mm board edge. Amphenol's drawing shows a
  1.65 mm overhang for panel mounting; check it against the UCS 145-125 wall cutout.
- **J14 3D model:** Amphenol's STEP (via SnapMagic, `dev/RJSSE5380`) is licensed for design
  use only, so `lib/cryocooler.3dshapes/RJSSE5380.step` is gitignored. Copy it there to render
  the real jack; without it `pcbmodels.py` falls back to a box envelope.
- **Board ID:** the silk prints `5e8fc30`, the commit holding this design. The stamp and the
  fab files re-exported with it are in the next commit, because a commit can't contain its own hash.
  Restamp it after any later board change.
- **Labels left out (no room):**
  - silk labels for J9, D3, D7 and D14;
  - some ESP32 pin names;
  - the reference designators that silk_fix hid.

## Sine gain feedback (2026-11-03)

R45 (47k) + R122 (2.4k) in series replace the 22k, both 0402 on B.Cu beside U5; C84 (1 nF) stays across both. Done on the routed board with `tools/split_r6.py`, so re-running `gen_pcb.py route` needs that edit redone. Reference text for both is hidden (no silk room): R122 is the vertical one west of R45.

## Silk text width (2026-11-03)

All silk text is 0.9 mm wide by 1.0 mm high with unchanged stroke widths (`tools/narrow_silk.py`, and `SILK_WIDTH_RATIO` in `gen_pcb.py` for new boards). Height stays at JLCPCB's standard 1.0 mm minimum. Width stops at 0.9 because narrower text loses letter gap: pairs under JLCPCB's 0.15 mm gap go from 54 at full width to 63 at 0.9, 201 at 0.85 and 246 at 0.8. Some of those 63 are tight already (the "LA" in RELAY is 0.024 mm, and was 0.043 mm at full width).

The script also showed the hidden references that now fit beside their parts: D15, D18, J3, J4, J5, J6, J13 and R45. 40 others stay hidden (plus U1, which the script skips), and test points still print net names instead.

## Label placement (2026-11-03)

`tools/label_owners.py` moves any reference, test point name or LED / jumper name whose nearest part is another part, so its own part is clearly the nearest. The +15V and -15V LED names are gone: the test point beside each LED prints the same name, for both. Where a reference has no such spot it is hidden, and a test point or LED name may take a reference's place. Its printed lists give the current result. It runs after `narrow_silk.py` and before `silk_fix.py`.

## SPI and clock test points removed (2026-11-03)

The SCK, MOSI, MISO, A_MISO and chip-select test points (TP18-TP28) and SCL (TP31) are gone from the schematic and board. Their numbers stay unused so the other test points keep theirs; SDA (TP30) stays. Done on the routed board with `tools/remove_test_points.py`. This departs from the AGENTS.md test point rule, so those signals now have to be probed on the part pins.

## Bottom and right wall headers (2026-11-03)

J3, J4, J5, J6, J7 and J13 are right-angle through-hole headers on the routed board, pulled in so their tabs stop at the board edge (J3, J5 holes at y 86.6; J6, J7, J13 at y 86.7; J4 at x 106.6). Applied in order to the routed board, so a full `gen_pcb.py route` needs them redone:

1. `tools/fan_headers.py`, `tools/two_pin_headers.py` (headers, bottom-side parts behind them, rip-up).
2. `gen_pcb.py link`, `reroute` (three rounds) and `finish`, after `tools/ripup.py` on the eight nets left open.
3. `tools/hand_route.py cryocooler.kicad_pcb bottom_wall_headers` (NTC_ADC, +5V, +3V3).
4. `tools/bottom_wall_silk.py`, `tools/silk_fix.py`.

Open points:

- **Plugs past the edge:** tabs stop at the edge, so the plug and wires sit outside the board. Check the openings in the housing wall.
- **J7 / J13 spacing:** bodies are 0.68 mm apart (moved west to clear D4 and Q7), so check two plugs fit side by side.
- **CO975 not verified:** no maker drawing, pin material or current rating; check a real part's hole fit and the fan and pump current before ordering boards. Pins 1-3 share the key tab and pin 4 (PWM) is the separate pin.
- **Plug fit:** J5's locking plate has not been tried with the Alphacool plug, and J6 / J7 / J13 need SWH25X housings on the cables.
- **Plate width:** the J5 and J6 / J7 / J13 drawings show other position counts, so these plates are estimated. PANEL sits beside J7's estimated plate but within its body width, so a full-width plate would cover it.
- **J4 GND label:** printed at y 88, below TP16's pad, instead of level with pin 1.
- **3D models:** `fan_header_90deg.step` (GrabCAD, licence not read) is gitignored and copied from `dev/`; without it the footprint gets a box envelope. J5, J6, J7 and J13 use your own Sullins models, `SWR25X-NRTC-S03-RB-BA.step` and `SWR25X-NRTC-S02-RB-BA.step`; these two are not gitignored.

## DC and 3.5 mm jacks (2026-11-04)

J2 and J9 are SMT jacks on the left wall, mouths level with the board edge (`tools/wall_jacks.py`); footprints follow the maker land patterns. Q5, Q6, TP36 and TP38 moved to clear J9. Applied to the routed board in this order, so a full `gen_pcb.py route` needs them redone:

1. `tools/wall_jacks.py`, `gen_pcb.py link`.
2. `tools/gridroute.py` on the DRC report (Freerouting closed none of the open links), `gen_pcb.py finish`.
3. `tools/hand_route.py cryocooler.kicad_pcb wall_jacks`, `tools/silk_fix.py`.

Open points:

- **Current:** the jack's 5.5 A falls with temperature (about 4.5 A at 50 C on the maker's curve) and is below the 7.5-10 A inline fuse in `DESIGN_REVIEW.md`. F1 (5 A) protects it; check the real 12 V load.
- **Assembly:** both jacks are left out of the JLCPCB placement files with the other connectors, so hand-solder them or add them.
- **3D models:** `54-00164.step` and `MJ-3523-SMT-TR.step` (from `dev/`, licences not read) are gitignored in `lib/cryocooler.3dshapes/`; without them the footprints get box envelopes. The MJ-3523 model renders white, though the part is black.

## USB-only power (2026-11-04)

USB VBUS can now run the logic side with no 12 V. U28 / U29 (LM66100, SLVSEZ8A Fig. 17) feed a new rail, `+5V_OR`, from `+5V` or `USB_VBUS`; U28's ST with R24 holds U29 off while `+5V` feeds it, and the inputs cannot back-feed each other.

- **On `+5V_OR`:** U16 (so all of +3V3), the DDS (U3, U4), the display backlight (R121) and JP3 (isolated supply).
- **Stays off on USB alone:** `+5V` and what hangs on it: the +-15 V stage (JP2), U24 / D22 (status LED), R80, R81, R47.
- **Why the DDS moved:** U4 shares SPI with +3V3 parts, so it would otherwise be driven while unpowered.
- **C65 / C66:** C65 (22 uF) is now U16's input cap. C66 grew from 10 uF 0805 to 22 uF 1206 to stay the buck's second output cap.
- **Parts:** U28, U29, R24, C49, TP43 (VBUS), TP44 (5V_OR), all on the bottom below U16. R24's and some other references are hidden.

Applied to the routed board in this order, so a full `gen_pcb.py route` needs them redone:

1. `tools/usb_power_path.py`, `gen_pcb.py link`.
2. `tools/gridroute.py` on the DRC report (VBUS with `WIDTH=0.3 MAX_EXPAND=15000000 VIA_COST=8`).
3. `tools/hand_route.py cryocooler.kicad_pcb usb_power_path`, `gen_pcb.py finish`, `tools/silk_fix.py`.

Open points:

- **Not bench-tested:** the design passes ERC, datasheet rules and DRC only.
- **Current:** the USB port carries the ESP32 (WiFi peaks), the DDS, the isolated supply and the backlight. Pull JP3 and unplug the display if a port browns out.
- **Headroom:** the VBUS track is about 130 mm of 0.3 mm copper with 10 vias (roughly 0.25 ohm, estimated), about 0.13 V at 0.5 A. U16 needs about 1.2 V, so a weak port or thin cable can still brown out.
- **Firmware:** unchanged. `cooling` latches `MODULE_INIT_UNDERVOLTAGE`, so check it after booting on USB and adding 12 V later; it may need a reinit. Avoid `start` on USB alone: the DAC can drive OPA188 inputs with its rails off.

## Connector moves (2026-11-04)

`tools/connector_moves.py` and `tools/connector_silk.py`, on the routed board:

- **J1 USB:** top edge, mouth up; at x 54.3 here, since moved to x 32.5 (see Connector swap below). USB4105 stays,
  because the USB4205 in `dev/USB4205_GF_A` is not needed for the fit. U2 sits on the bottom side
  behind the connector; the D+/D- fan-out is the old one turned 90 degrees. `USB_VBUS` gets shorter.
- **J2 12 V in:** bottom of the left wall, axis y 85.5. Raw 12 V runs up the wall on F.Cu at 2 mm
  (x 9.5) to F1, which did not move.
- **J9 / J8:** J9 up 3.3 mm to y 63.0; J8 between J9 and J2 at y 72.4 / 74.94. Q21 moved 2 mm east.
- **J3 / J4:** side by side on the bottom wall, pin 1 at x 80.5 and x 92.2. U10 moved up 2.5 mm so
  J4's pins clear it, with TP30 and parts since removed (old R14, C24, D2), and R5, R61, C62 are behind it.
- **J11 / J12:** TE 2305908-2 at y 21 and 2305908-3 at y 33.5. The 5.5 mm pads would hit U18 pins
  5-8 at J11's old height, so J11 moved below U18. J11 + runs up the wall to pins 1-4; J12 + rises at
  x 15.4 to pins 5-8. J11 - and J12 - have a 2 mm F.Cu link at x 7, because SMT pads no longer tie the
  ISO_GND layers together; five vias stitch it.
- **3D models:** J8, J11 and J12 use the makers' STEP files from `dev/` (`194834544-19-1821698`,
  `ul_2305908-2`, `2305908_3`), gitignored as `lib/cryocooler.3dshapes/1821698.step`, `2305908-2.step` and
  `2305908-3.step`. Without those files they fall back to box envelopes.
- **J10 3D model:** still a box envelope. `4392 STEMMA QT Horizontal` in Adafruit_CAD_Parts is a 1 mm pitch,
  6 mm wide JST SH part, not the 2 mm pitch, 12 mm wide Adafruit 4392, and KiCad ships no SMT JST PH 4-pin model.
- **Housing:** every moved connector needs its wall cut-out moved: J1, J2, J3, J4, J8, J9, J11, J12.
- **Silk:** the front section label is shortened to `POWER & RAILS`, because the full name does not fit
  between J2 and SW3. The J8 reference stays hidden, because no free spot sits next to it; `AMP REM`, `REM` and
  `GND` mark the connector.
- **Hand edits not in a script:** D+ west of J1's peg, +3V3 around J2's hole, the FAN_ALERT trunk, GND vias
  (80.6, 82.05) and (85.45, 78.15), the SDA In2 reroute near J4, and the SW3 branch of `Net-(J7-Pin_1)`, which now
  starts at the pad to remove a copper sliver. These live only in the board file, so a full `route` would lose them.
- **Open before ordering:**
  - DigiKey and te.com block scripted access, so 2305908-3 stock is unconfirmed. Other sellers list it as last-time-buy or discontinued.
  - J11, J12 and J8 carry plugging force on their SMT joints; only J8 has pegs.
  - Mating plugs are not ordered or test-fitted: TE 2213934 / 2213935 / 2305909 series, Phoenix FMC 0,5/2-ST-2,54.

## MCP23S08 board (2026-11-04)

Brings the routed board to the MCP23S08 schematic. Design commit `5e8fc30`; the stamp and fab files are in `191cead`.

- **Parts:** EMC2303, SC18IS604 and their parts are gone. U25 is the MCP23S08 QFN. Q26, Q27 and their resistors drive the fan and pump from the ESP32.
- **Display level shift:** GPIO47/48 are 1.8 V on this module, so U30 / U31 (SN74LV1T34 on `+3V3`) buffer `DISP_CS` and `DISP_DC` up to the panel. Firmware pins don't change.
- **Connectors:** J15 moved 8 mm left to (34, 5). J1 stays on the top edge, now in the MCU box, with a section wall at x 47.5 between them. The housing cut-out for J15 must move too.
- **Inductors:** L1 SRP6050CA-4R7M, L2 SRP7050TA-4R7M. L3 stays MSD7342-103: a single winding on SEPIC/Cuk needs L >= about 5.5 uH per L1||L2 when uncoupled, so SRP7050TA-6R8M can't work. The SRP parts use carbonyl powder cores, unproven at 1.5 MHz: bench-check heat and ripple. L2 uses the 3R3M STEP (same package).
- **Ground test points:** TP14-17 are Keystone 5015, SMT on the top side, joined to ground through the pour. All four kept by the user's choice.
- **Trace angles:** `tools/octilinear.py` converts off-angle segments to 45 / 90 degree doglegs, and `gridroute.py` now routes octilinear. What remains is short pad tie-ins and part of the USB pair.
- **`gridroute.py`:** the stale `ISO` region was removed. It came from an old floorplan and blocked routes into the lower right; keep-outs fence the real ISO island.
- **Route:** `tools/spi_expander_board.py`, then `gridroute.py`, then one-off fan-out edits around J15 pins 4-10 and U25 pin 14 that aren't scripted, so the committed board is the source. U27 sits directly under J15: check both sides before adding vias there.
- **Checks:** DRC 0 errors, 0 unconnected, 0 parity; warnings left are 6 connector silk at the board edge and the U1 library mismatch, as before.

## Pre-order audit fixes (2026-11-04)

`tools/audit_fixes_board.py` on the routed board, then `gen_pcb.py link`, `narrow_silk.py`, `label_owners.py`, `silk_fix.py`. Design commit `caa5c7b`, stamped on the board in the commit after it.

- **PG_15V:** R120 is 470k. At 10k it lifted dead PGP / PGN nodes to about 2.2 V, so REM unblocked and GPIO43 read good with no rails. Not yet measured on a board. If the negative side alone dies and PGN floats, R76 still feeds that node from +15V, so the hardware interlock may pass.
- **USB_VBUS:** R44 (100k to GND) stops U28 CE floating with USB unplugged.
- **U15 switch node:** 0.4 mm on F.Cu, the existing 0.6 mm via, 1 mm on In2, two vias in L1 pad 1. The BST via and In2 USB_VBUS limit the width.
- **U16:** a 21 mm2 +3V3 pour east of the tab, six vias to the In2 pour.
- **Rail caps:** GRM32ER71E226KE15L (25 V X7R), since no 22 uF / 50 V X7R 1210 could be sourced. C73, C74, C75 double +15V, -15V and -16V5. +16V5 stays single (no nearby room; LT3097 INP needs 4.7 uF). DC bias not confirmed against the maker's curve; check the LT8582 loops on the bench.
- **R82:** RT0402BRD073K9L (0.1 %). `PT1000_REF_R` is still 3854; set it to the measured value.
- **Still open before ordering:** J15 contact side, J11 / J12 terminal block stock (distributors list 2305908-3 obsolete).

## SPI chip-select decoder (2026-11-05)

Branch `spi-cs-decoder`. U32 (SN74LVC138A) at (92, 33) replaces the eight CS GPIOs; design notes are in `kicad/DESIGN_REVIEW.md`. Not bench-tested.

- **Pipeline on the committed board:** `cs_decoder_board.py`, `gen_pcb.py link`, `gridroute.py`, `cs_decoder_finish.py` (no flag), `octilinear.py`, `cs_decoder_finish.py --ground` (ground ties, TP41 out), `gen_pcb.py link`, `narrow_silk.py`, `label_owners.py`, `silk_fix.py`, `cs_decoder_silk.py`. Later edits were small one-off moves whose final values are recorded in the scripts, so a replay may need touch-up.
- **Via-in-pad:** U32 exposed pad (RGY package) and D8 pad 1. Inner traces 0.9 mm apart leave no room beside D8.
- **+3V3 loop:** the feed to R28 and R27 runs out to x 99.6 so R29 pad 1 can reach a via at (98.71, 34.4).
- **Silk:** hand-placed around U32; re-running `silk_fix.py` may hide those labels, so run `cs_decoder_silk.py` again afterwards.
- **Part stock:** U32 is now SN74LVC138ARGYR, and its stock has not been checked (the earlier look at cached pages was for the TSSOP SN74LVC138APWR). Check live before ordering.
- **U32 / U27 3D models:** TI's `RGY0016A.stp` (`dev/SN74LVC138ARGYR`) and `RGV0016B.stp` (`dev/TSC2046EIRGVT`), no licence terms in the downloads, gitignored as `lib/cryocooler.3dshapes/RGY0016A.step` and `RGV0016B.step`. Copy them there to render; without them the parts have no 3D body. Neither needs an offset or rotation.

## Tact switches: TL6800 and PTS810 (2026-11-05)

SW3 is now the E-Switch TL6800AF260QJ; SW1 and SW2 are the C&K PTS810SJM250SMTR LFS. Pipeline: `tools/sw3_tl6800_board.py`, `tools/sw1_sw2_pts810_board.py`, `gen_pcb.py link`.

- **SW3:** same centre (27, 95.8). No track or via changed, because the new pads cover the old pad centres. `SW3` moved to (24.4, 91.7) and J7's `POWER` label to (32.45, 94.85).
- **SW1:** centre (66.5, 10.425), was y 11. DISP_RST (y 10.9) runs between the pad rows, under the body, with 0.175 mm to the bottom row. TOUCH_CS moved down to y 12.35, where the old GND track was. The bottom row reaches GND through a new via at (69.55, 11.6).
- **SW2:** centre (66.5, 17.675), was y 18.5. The top row sits on the ESP_BOOT track and the existing via is clear under the body; the bottom row drops to the GND track at y 20.4.
- **3D models:** gitignored in `lib/cryocooler.3dshapes/`, copied from `dev/`: `TL6800AFxxxQJ.step` and `PTS810SJM250SMTR-LFS.step`. Without them the parts have no 3D body. The PTS810 file is C&K's `PTS810SJS250` model: same shape per the datasheet, but it renders white and the SJM actuator is grey.
- **Force and height:** RESET and BOOT are 1.6 N, power is 260 gf (about 2.5 N). Check the PTS810's 2.5 mm height and the TL6800's 3.1 mm height against any panel or enclosure access; neither was checked.

## 12 V copper for 4 A (2026-11-05)

Planning load: 3 PWM fans 0.45-0.9 A, D5 pump 1.3-1.8 A (rarely 2 A), U15 up to about 0.9 A, so 4 A total and about 3 A east of U15. `tools/power_12v_rework.py` added:

- **VIN, F1 to Q1:** 1.2 mm on F.Cu / B.Cu with 3-via groups, in parallel with the old In2 run, which stays and feeds the VIN branches.
- **VSW, Q1 to R98:** 1.4 mm F.Cu strip from pin 2 to the tab, three 0.35 mm drill vias in R98 pad 1 (filled / capped).
- **+12V, R98 to the U15 junction:** 1.2 mm on B.Cu / F.Cu with a 3-via group. The old In2 run here is removed; it stayed at 0.8 mm and would have taken about half the current. R99's sense tap stays on In2 north of (40.16, 60.72).
- **U15 junction and (56.48, 85.52):** 3 vias each.
- **J5 to J3 to J4:** 1.0 mm on F.Cu in parallel with the In2 runs.

Resistor-network solve of the copper with IPC-2221 rises at 4 A total (U15 0.9, J3 0.9, J4 2.05, Q8 0.1, J5 0.05 A): 1.2 mm outer routes about 24 C, VIN's In2 about 16 C (1.25 A), east 0.8 mm outer copper about 26 C (3.1 A), hottest via about 1.9 A. Before the rework the In2 runs were about 225 C on the same basis. Estimates only; check with a thermal camera at full load. J4's CO975 still has no current rating, and F1 (5 A) has little headroom at 4 A.

## USB / display connector swap (2026-11-04)

The panel's ribbon leaves its lower edge heading toward the top of the board, so J15's opening now faces into the board and J15 and J1 have swapped places.

- **J15:** (53.2, 4), rotation 0. Pin 1 is now on the west side. Cable width takes x 49-57 and has about 6.8 mm of runway before U7.
- **J1:** x 32.5 (was 54.3), with U2, R30, R31, C50. U27, C48, C40, R168, TP42 moved 20 mm east with J15. Display resistors and Q25 stayed at x 39-47.
- **Sections:** the wall moved from x 47.5 to x 38. `DISPLAY` is x 38-60; J1's box is a separate piece of `MCU & USB` (`pcbfloorplan.py`).
- **Route:** `tools/swap_usb_display.py`, `gridroute.py`, `swap_usb_display.py ... finish`, silk steps, `swap_usb_display.py ... silk`. An F.Cu +3V3 bridge at (49.9-52, 7.6-8.7) rejoins the In2 pour split by the new routes.
- **Housing:** J1's wall cut-out moves 21.8 mm left, and any J15 cable slot needs re-checking.
- **Still to confirm against the panel:** the ribbon's exposed contacts must face FH12's contact side (rotating J15 doesn't change this), and J15's x position must line up with the ribbon in the lid.


## Mask-opening labels (2026-11-06)

Silk can't go under JLCPCB's 1.0 mm, so 327 labels are now solder mask openings over the GND and ISO_GND pours, with the exposed copper forming the letters (`tools/mask_labels.py`, positions in `tools/mask_labels.json`). No copper changed. The stroke is 0.10 mm: R, C and D references are 0.5 mm tall and everything else is 0.7 mm. At 0.5 mm the "8" keeps 0.115 mm of mask against JLCPCB's 0.10 mm blue dam, and thinner strokes leave a sliver in the "9".

- **Placement rule (from the user's hand edits):** center a label on one edge of its part, parallel to that edge, on the open side and the same side as similar parts nearby. A slightly larger gap is fine. `tools/mask_label_plan.py` applies it, keeps the hand placements in `LOCKED`, and only moves a label to a better free spot, so coverage can't drop.
- **Arrows (29 labels):** 0.15 mm silk leaders at 0/45/90 degrees with at most one bend, the last resort for labels with no room beside their part. They cross traces, but not pads, vias or other silk.
- **1.0 mm silk:** 21 owned labels are silk centered on an edge (`silk: true` in the JSON), 12 of them mask labels before the rule, including R2, R25, R39, R70, R71, R72, R95 and R101. Another 11 stayed in their silk spots. The 19 ESP32 pin names are also silk.
- **Left alone on purpose:** section names, box lines, the board ID and part-body names.
- **Still hidden (13):** C21, C23, C33, C34, D13, R12, R90, R91, R94, R96, R97, R112, U15.
- **Copper text was rejected:** a 12-label trial gave 8 clearance errors and removed 41.6 mm² of GND pour.
- **Pipeline:** run after `silk_fix.py`, which could cut the arrows. To replan, run `tools/mask_label_export.py` under KiCad's Python, then `tools/mask_label_plan.py board.json tools/mask_labels.json previous_labels.json` under the system Python, then `tools/mask_labels.py`. Positions don't follow parts, so re-check after any move, reroute or refill.
- **Before ordering:** order ENIG and note the labels on the order. Readability at 0.5 mm isn't proven on a real board.
