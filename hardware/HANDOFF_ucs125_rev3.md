# Rev 3 on the UCS 125-87 board — status

Branch `ucs-125-87-rev3`, from `ucs-145-125-rev3` (085961d). The same rev 3 circuit
moved onto the smaller Phoenix UCS 125-87 board. Routed board committed as 4cab2b9; fab files carry board ID `rev 4cab2b9`. Not pushed, not ordered.
Firmware: same pins; one change for the AD9837's 16 MHz clock (`AMPLIFIER_DDS_MCLK_HZ` in `config.h`, passed to `setClk()` in `amplifier.cpp`).

## Board

- **Outline:** 100 x 62 mm (drawing `dev/pxc_2203445_01_00_UCS-125-87-H-CCD-7035_PCB2D_UCS-PCB-125-87.pdf`).
  - **Mounting holes:** 4x M3 at 4.2 mm from each edge.
  - **Restricted corners:** a 4.45 mm square plus a Ø6 ring at each corner, with no parts, copper or mask.
  - **Height:** the housing allows 31 mm above the board and 10 mm below.
- **ESP32 antenna:** U1 is centred on the top edge over a routed notch (x 40.5-59.5, 6 mm deep), with 14.5 mm copper/part keep-outs on each side.
- **Layers:** 4.
  - In1: GND plane (ISO_GND in the island).
  - In2: signals, then a +3V3 pour.
  - F/B: signals with GND pours.
- **Vias:** smallest is 0.45 / 0.2 mm, as on rev 3.
- **Labels:** 0.8 mm / 0.1 mm silk (order with JLCPCB high-precision silkscreen) wherever one fits, on the part's own side. Footprint reference fields stay hidden; there are no section boxes or mask labels.
  - `ucs125_board.py labels` places them (a `part labels` group, replaced on each run) above or below the part, then beside it, then vertical, never nearer another part than its own.
  - Test points show their net (`+15V`, `DDS`, `U5 OUT`, ...); connectors, jumpers and switches show reference and function (`J9 SINE OUT`, `SW1 RESET`). LEDs use `LED_LABELS`, also 0.8 mm.
  - A through-hole connector with no room on its own side is labelled on the far side, under its body (J3, J4 on the back; J6, J13 on the front).
  - 87 parts (mostly 0402 passives, a few ICs) have no room and stay unlabelled; the run prints the list.
  - The board's DRC text minimum is 0.8 mm / 0.1 mm (`SILK_DRC_MIN_*` in `gen_pcb.py`).
- **Board ID:** `cryocooler` / `BETA rev <hash>` on the back silk, centred at (80, 23.2); now `rev 4cab2b9`. Keep it there on later revisions and restamp with `ucs125_board.py boardid <board> 80.0 23.2` after each board commit.
- **Script:** `kicad/tools/ucs125_board.py`. It runs `place` → `route` → `finish` → `boardid` → `labels` from the routed 145-125 rev 3 board. Run it with KiCad's python. The last connections were closed by hand (see Routing), so a rerun doesn't reproduce the routed board: edit the board itself from here on.

## What changed from the 145-125 rev 3 board

- **Test points:** only the waveform and rail points remain:
  - TP37 DDS_SINE, TP38 SIG_SINE, TP47 (U5 output, the AD5453 VREF node);
  - TP9 +15V, TP10 -15V, TP11 +16V5, TP12 -16V5;
  - TP14 GND.

  The other 26 retired. Their numbers stay retired, and `KEPT_TEST_POINTS` in `gen_schematic.py` selects them.
- **J14 filter:** one NUF6401MNT1G (U36, 6 channels, DFN12 case 506AD) replaces the two NUF4001MU (U36, U37). U37 is retired. See `kicad/DESIGN_REVIEW.md`. The 3D model is a plain 3.0 x 1.35 x 1.0 mm envelope.
- **SW1, SW2:** Panasonic EVP-AA802Q (3.5 x 2.9 mm, J-lead, 5.0 N) replaces the EVQ-P2F02K.
- **LEDs:** every indicator but D13 is a Kingbright APGB0607G22R23C green/red LED (0.65 x 0.65 mm). D7 is now one STATUS LED (green on, red standby, both = +3V3 missing) in place of D7, D8 and D9. D2/D3 show green on and red off; D11/D12 green good and red bad (Q51, Q52 added). Details in `kicad/DESIGN_REVIEW.md`.
  - **Placement:** STATE (D13), PWR, +15V, −15V, AMP, COMP and ALERT form one labelled column at the bottom right of the front (`LED_BLOCK_SPOT`, clear of U25 and J8's pegs); D10 (ISO 5V) is labelled in the isolated island. `LED_LABELS` / `place_leds` in `ucs125_board.py`.
- **U4 DDS:** AD9837BCPZ-RL7 (3 x 3 mm LFCSP-10, exposed pad to GND) replaces the AD9833BRMZ (MSOP-10): same pin numbers and register set, but 16 MHz MCLK max, so U3 is now the 16 MHz ECS-2520MV-160-BN-TR.
- **U33, U35 ESD clamps:** Littelfuse SP3422-04UTG (DFN-5, 1.0 x 0.6 mm) replaces the TPD4E05U06DQAR (USON-10). See `kicad/DESIGN_REVIEW.md` for the leakage trade-off.
- **U2 USB ESD clamp:** MCC SRL05P7-TP (DFN1510-6, 1.5 x 1.0 mm) replaces the USBLC6-2SC6 (SOT-23-6); same pin functions and pass-through pairs.
- **U24 level shifter:** Nexperia 74AHCT1G125GM (XSON6 SOT886, 1.0 x 1.45 mm) replaces the SN74AHCT1G125 (SOT-23-5); pin 6 is VCC, pin 5 n.c.
- **U31 display buffer:** Nexperia 74LV1T34GXH (X2SON5, 0.8 x 0.8 mm) replaces the SN74LV1T34 (SOT-23-5). Pin 1 (n.c.) is grounded so a footprint bridge can escape the centre GND land. The lands run out past the left and right body edges (datasheet Fig. 5), and the 3D model is the SamacSys STEP (its top dot is at the wrong corner).
- **The INA239 stays in VSSOP-10 (user's call, 2026-11-08).** TI makes its SPI power monitors (INA239, INA229) only in that package. The only leadless SPI monitor found, the ADI LTC2947 (QFN 4 x 6 mm), is larger and not register-compatible.
- **U15 stays the AP63205WU-7 (user's call, 2026-11-08).** The leadless options (TI TPSM33620S5QRDNRQ1 module, LMR604205RAKR, ADI MAX17632BATE+) cost 5-10x as much and are thinly stocked.
- **C78 (U15 input):** 10 uF/50 V X5R 1206 (Samsung CL31A106KBHNNNE, JLCPCB C13585) replaces the 10 uF/25 V, which was rated below the SMBJ16A clamp (about 26 V). Same footprint.
- **U5 + U9 → one OPA2991IDSGR** (WSON-8, 2 x 2 mm): A is the DDS gain stage, B the AD5453 output stage; U9 and its two decoupling caps are retired. C86 (AD5453 C1) is 22 pF for stability with the faster amp. See `kicad/DESIGN_REVIEW.md`.
- **J14 (IMU cable):** Molex Micro-Lock Plus 505448-0891 (2x4, 1.25 mm, right angle, latching) replaces the RJSSE-5380 RJ45, to free the right edge; same pin numbers. See `kicad/DESIGN_REVIEW.md`.
- **U32 (CS decoder) and U25 (GPIO expander) stay.** Dropping U32 needs 8 direct CS pins and only 7 are free.

## Wall connectors

Only the USB stays on the top edge. Connectors that couldn't fit on the walls moved to the back of the board at the wall.

| Edge | Front | Back |
|---|---|---|
| Top | J1 USB-C | |
| Left | J12 amp out (TE 643228-1) | |
| Right | J14 IMU (Micro-Lock Plus 2x4), SW3 power button, J9 sine out (3.5 mm) | |
| Bottom | J11 amp current, J2 12 V, J3/J4 fans | J5, J6, J7, J13, J10 PT1000 (JST-PH), J8 amp remote |

- **J9 and J10:** J9 was planned for the left wall, but it would sit inside the isolated island. J10 moved to the back bottom wall because J9's locating pegs can't sit under it.
- **Housing:** the housing walls need new cut-outs for every connector position (open item).

## Isolated island

- **Location:** bottom-left: J12 pins 1-2, J11, U18 (ACS37800) and U17's isolated half (U17 is on the back, rot 270, barrier across its body).
- **Outline:** `ISO_RECTS` / `ISO_OUTLINE` in `ucs125_board.py`. ISO_GND fills it on all four layers.
- **Moat:** a 1.5 mm no-copper rule area (`ISO moat`) separates it from everything else.
- **Amp current (up to 5 A):** locked 2 mm copper.
  - **IP−:** F.Cu from J12 pin 1 to U18 pins 5-8.
  - **IP+:** B.Cu from J11 pin 1 (4 vias, 0.6/0.3) to a bar of 4 vias beside U18 pins 1-4.

## Routing

- **Flow:**
  1. `place`, then `route`: Freerouting takes about 25 min, and its window shows unless `FREEROUTING_HIDE=1`.
  2. `finish`, then repair with `prune_flagged`, `gridroute` and `plane_ties`.
  3. `reroute`: one more Freerouting round that keeps the existing copper.
- **Placement for routing:**
  - Moving the LED column off U25 cut Freerouting's unrouted count from 125 to 83.
  - SW2 sits beside SW3, U32 under U1, and the ±15 V group moved over.
  - `reserve_current_path` keeps the IP+ B.Cu corridor (J11 → U18) free of other parts.
- **Closed by hand:** the last signal links and about 37 GND pads and pour fragments, by scripted board edits that `ucs125_board.py` doesn't repeat. Notable ones:
  - C23 is rotated 180°. Its GND pad now faces left, with a via at (45.8, 46.48), which gives Q7-G its lane between J6 and J7.
  - DISP_RST reaches R14.1 with one F.Cu stub. R14.2 and C36.2 tie to GND through their own vias.
  - C86 pad 2 reaches its In2 route through a via at (51.95, 33.01).
- **Totals:** 586 vias.
  - Every segment is at 0/45/90° except five: four are under 1° off, and one is a 0.16 mm jog on STATUS_RGB.
  - `octilinear.py` straightened the other 83.
- **Long routes (slow signals, worth a look before fab):**
  - DISP_RST: 78 mm, 13 vias.
  - Q7-G: 79 mm, 7 vias.
  - ACS_SCK: 72 mm.
  - ACS_MOSI: 64 mm, 9 vias.
  - TOUCH_CS: 10 vias.
  - DISP_CS: 8 vias.
- **Tool fixes:**
  - `gen_pcb.add_escape_via` no longer drops a via onto another net's track or onto a pad on the other side (`other_side_pad_near`).
  - `gridroute` reads the antenna notch from the board outline.

## Checks

- **Schematic:** ERC 0, `datasheet_rules` 353/353, `verify_netlist` no mismatches (280 parts, 208 nets), `check_symbols` 0 in all four checks.
- **Board:** DRC with schematic parity gives 0 errors, 0 unconnected and 0 parity.
  - The warnings are the accepted baseline: 4 `lib_footprint_mismatch` (U1, U18, C53, C74) and 2 `silk_edge_clearance` (J11's silk at the bottom edge).
  - A 0.34 mm² B.Cu GND sliver at (65, 42.5) hangs off U33 pin 2's GND track. It is connected; it isn't an island.

## Still open

- Wall cut-outs in the housing for the new connector positions; J15 (display FPC) against the lid display window.
- J14's plug sticks out past the right edge: the wall needs a slot for it (about 10 x 9 mm) or a cable gland. The 505432 housing and crimps aren't in the BOM; stock not checked.
- The long, via-heavy routes listed under Routing.
- APGB0607G22R23C (7 LEDs) is a DigiKey part (22561020); JLCPCB stock not checked.
- 74LV1T34GXH (U31): DigiKey and JLCPCB stock not checked.
- NUF6401MNT1G (U36) is bought from DigiKey (1484990), not JLCPCB stock: supply it for assembly. One DigiKey listing quoted a 40-week lead time, so check stock before ordering.
