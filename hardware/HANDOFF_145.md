# UCS 145-125 board — status

Branch `pcb-ucs-145-125`. This branch carries the rev 2 work (`HANDOFF_rev2.md`): the LT8582 /
LT3097 rails, the display, the RJ45 IMU jack, 0402 parts and named test points. Here that work
is on the 120 x 100 mm PCB for the Phoenix UCS 145-125 housing. All items in `TODO.md` are
done.

## State (2026-11-03)

- **Schematic:** ERC 0, all datasheet rules pass, BOM regenerated.
- **PCB:** 4 layers, blue mask, parts on both sides.
  - KiCad DRC with schematic parity: 0 errors, 0 unconnected, 0 parity, 0 silk overlaps.
  - 45 warnings remain:
    - 44 `silk_edge_clearance`: the wall connectors' body outlines run past the board edge,
      and the fab clips them there;
    - 1 `lib_footprint_mismatch` on U1, from the generator's local edits to the WROOM footprint.
- **Fab files and renders:** in `kicad/fabrication/`.
- **Firmware:** builds. `pio test -e native` passes test_conversions; test_native stops on
  the known `commands.cpp` stub errors.

## Connector choices

| Ref | Part | Notes |
|-----|------|-------|
| J10 PT1000 | Adafruit 4392, JST PH 4-pin horizontal SMD (CW2001-04T) | replaces the M12; footprint from the maker's drawing |
| J11 amp out | Phoenix MSTBA 2,5 2-pin | + / − to U18 (ACS37800) |
| J12 cryocooler | Phoenix MSTBA 2,5 3-pin (1757255) | + / − from U18; pin 3 on board GND, outside the ISO island |
| J14 IMU | Amphenol RJSSE-5380 | plain 8P8C; the three parts in the TODO have magnetics. Signal pads centred between the holes (fixed 0.28 mm offset) |
| J15 display | Hirose FH12-14S-0.5SH | top edge, top side |
| J6 / J7 / J13 | Adafruit 1769 JST PH 2-pin SMD | unchanged |
| J8 / J9 | Phoenix MC 1,5 | moved to the left wall |

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
- **Board ID:** the board ID prints the commit the board was generated from (`7f4c0ac`), not
  the commit that holds the files.
- **Labels left out (no room):**
  - silk labels for J9, J13, D4, D7 and D17;
  - some ESP32 pin names;
  - the reference designators that silk_fix hid.
