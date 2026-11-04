# UCS 145-125 board — status

Branch `pcb-ucs-145-125`. This branch carries the rev 2 work (`HANDOFF_rev2.md`): the LT8582 /
LT3097 rails, the display, the RJ45 IMU jack, 0402 parts and named test points. Here that work
is on the 120 x 100 mm PCB for the Phoenix UCS 145-125 housing. All items in `TODO.md` are
done.

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
| J15 display | Hirose FH12-14S-0.5SH | top edge, top side |
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
  is a ~1 mm strip from pin 13 to L3 plus a B.Cu pour to C59. Pin 12's link under the
  exposed pad stays narrow (~0.28 mm): the pad and a +5V_PS15 track bound it.
- **U20 exposed pad:** 15 GND vias now (was 1), capped via-in-pad.
- **J14 mouth past the edge:** the jack face is 4.37 mm in front of its locating holes, so as
  placed (x 116.65) it sits ~1.0 mm past the 120 mm board edge. Amphenol's drawing shows a
  1.65 mm overhang for panel mounting; check it against the UCS 145-125 wall cutout.
- **J14 3D model:** Amphenol's STEP (via SnapMagic, `dev/RJSSE5380`) is licensed for design
  use only, so `lib/cryocooler.3dshapes/RJSSE5380.step` is gitignored. Copy it there to render
  the real jack; without it `pcbmodels.py` falls back to a box envelope.
- **Board ID:** the silk prints `3939aa8`, the commit holding this design. The stamp and the
  fab files re-exported with it are in the next commit, because a commit can't contain its own hash.
  Restamp it after any later board change.
- **Labels left out (no room):**
  - silk labels for J9, D4, D7 and D17;
  - some ESP32 pin names;
  - the reference designators that silk_fix hid.

## Sine gain feedback (2026-11-03)

R6 (47k) + R170 (2.4k) in series replace the 22k, both 0402 on B.Cu beside U5; C121 (1 nF) stays across both. Done on the routed board with `tools/split_r6.py`, so re-running `gen_pcb.py route` needs that edit redone. Reference text for both is hidden (no silk room): R170 is the vertical one west of R6.

## Silk text width (2026-11-03)

All silk text is 0.9 mm wide by 1.0 mm high with unchanged stroke widths (`tools/narrow_silk.py`, and `SILK_WIDTH_RATIO` in `gen_pcb.py` for new boards). Height stays at JLCPCB's standard 1.0 mm minimum. Width stops at 0.9 because narrower text loses letter gap: pairs under JLCPCB's 0.15 mm gap go from 54 at full width to 63 at 0.9, 201 at 0.85 and 246 at 0.8. Some of those 63 are tight already (the "LA" in RELAY is 0.024 mm, and was 0.043 mm at full width).

The script also showed the hidden references that now fit beside their parts: D18, D21, J3, J4, J5, J6, J13 and R6. 40 others stay hidden (plus U1, which the script skips), and test points still print net names instead.

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
- **J7 / J13 spacing:** bodies are 0.68 mm apart (moved west to clear D12 and Q7), so check two plugs fit side by side.
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

USB VBUS can now run the logic side with no 12 V. U28 / U29 (LM66100, SLVSEZ8A Fig. 17) feed a new rail, `+5V_OR`, from `+5V` or `USB_VBUS`; U28's ST with R171 holds U29 off while `+5V` feeds it, and the inputs cannot back-feed each other.

- **On `+5V_OR`:** U16 (so all of +3V3), the DDS (U3, U4), the display backlight (R166) and JP3 (isolated supply).
- **Stays off on USB alone:** `+5V` and what hangs on it: the +-15 V stage (JP2), U24 / D11 (status LED), R39, R80, R86.
- **Why the DDS moved:** U4 shares SPI with +3V3 parts, so it would otherwise be driven while unpowered.
- **C41 / C42:** C41 (22 uF) is now U16's input cap. C42 grew from 10 uF 0805 to 22 uF 1206 to stay the buck's second output cap.
- **Parts:** U28, U29, R171, C126, TP43 (VBUS), TP44 (5V_OR), all on the bottom below U16. R171's and some other references are hidden.

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

- **J1 USB:** top edge at x 54.3, mouth up, between J15 and the antenna keep-out. USB4105 stays,
  because the USB4205 in `dev/USB4205_GF_A` is not needed for the fit. U2 sits on the bottom side
  behind the connector; the D+/D- fan-out is the old one turned 90 degrees. `USB_VBUS` gets shorter.
- **J2 12 V in:** bottom of the left wall, axis y 85.5. Raw 12 V runs up the wall on F.Cu at 2 mm
  (x 9.5) to F1, which did not move.
- **J9 / J8:** J9 up 3.3 mm to y 63.0; J8 between J9 and J2 at y 72.4 / 74.94. Q21 moved 2 mm east.
- **J3 / J4:** side by side on the bottom wall, pin 1 at x 80.5 and x 92.2. U10 moved up 2.5 mm so
  J4's pins clear it, with R14, C24 and TP30; D2 is now above J4, and R20, R21, C27 are behind it.
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
