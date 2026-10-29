# Cryocooler controller — KiCad schematic

KiCad 10 hierarchical schematic for the ESP32-S3 cryocooler controller. Open
`cryocooler.kicad_pro`. A PDF export is in `cryocooler-schematic.pdf`. The 4-layer board is `cryocooler.kicad_pcb` (see [PCB layout](#pcb-layout)).

GPIO assignments follow [`include/config/pin_config.h`](../../include/config/pin_config.h).
The top-level README hardware table was brought in line with these sheets and the firmware
on 2026-10-14; if the two ever disagree, the schematic and `pin_config.h` win.

## Sheets

| Sheet | Contents |
|---|---|
| `cryocooler.kicad_sch` (root) | ESP32-S3-WROOM-2-N32R16V, EN/BOOT, USB-C + ESD |
| `power_input` | 12 V screw terminal, 5 A fuse, SMBJ16A TVS, bulk caps |
| `power_button` | LTC2954CTS8-2, IRF4905S high-side P-FET, KILL# bias, CL25N8-G (SOT-89) + red/green LED |
| `rails_logic` | AP63205 buck (12→5 V) → LD1117S33 (5→3.3 V) |
| `rails_15v` | ADP5071AREZ ±16.4 V (datasheet Fig. 47 values) → one LT3097 dual LDO (±14.7 V, 147 kΩ SET resistors); its PGP / PGN pins go to the `PGP_15V` / `PGN_15V` nodes on the `power_good` sheet (see below) |
| `power_good` | One node and green LED per LT3097 PG pin (D24 = +15 V, D25 = −15 V), a BAT54AW AND of the two nodes into `PG_15V`, and the 3.3 V flag `PG_15V_N` on GPIO43 (low = both ±15 V rails good); 0402 resistors and SOT-323 FETs |
| `signal_gen` | 25 MHz osc, AD9833, OPA1656, MCP4921 + LM4040-2.5 + OPA188, AD633 |
| `amp_control` | GPIO6 → BSS138 → BSS84 high-side 12 V to amplifier REM, red/green LED; a second BSS138 (Q9) in series with the level shifter's source is gated by `PG_15V`, so REM cannot turn on unless both ±15 V rails are good |
| `amp_current` | ACS37800 (SPI) + ISO7741 + MIE1W0505 (VSEL→GND2 = 3.3 V output), 4×1 MΩ + 4.02 kΩ divider |
| `system_current` | INA239 (SPI mode 1, CS on GPIO3) + 15 mΩ shunt in the switched 12 V rail, 49.9 Ω / 470 nF input filter, ALERT and 3V3 power LEDs |
| `i2c_bridge` ("Water Cooling I2C Bridge") | SC18IS604 SPI-to-I2C bridge (SPI mode 3, CS GPIO8, RESET GPIO9) with 4.7 kΩ I2C pull-ups, 74LVC1G125 MISO gate, INT# pull-up + test point |
| `cooling` ("Water Cooling") | EMC2303 (0x4D via 33 kΩ ADDR_SEL pull-up; fan + pump), Alphacool ES flow tach and NTC; its pull-ups sit on the switched `+3V3_COOL` rail |
| `cold_head` ("Cold Head Temp") | ADS1220 (SPI mode 1, CS on GPIO44), 4-wire PT1000, 3.9 kΩ Rref, DRDY pull-up + test point; powered from the switched `+3V3_CH` rail |
| `imu` | Header J14 (JST XH 8-pin) for the off-board Adafruit LSM6DSOX module: SPI bus, CS, INT1/INT2, +3V3, GND, 100 Ω series resistors, 10 kΩ CS pull-up |
| `compressor_relay` | GPIO16 → BSS138 → BSS84 high-side +12 V switch, flyback diode, red/green state LED, 2-pin JST XH output |
| `indicators` | READY / FAULT LEDs, WS2812B status LED behind a 74AHCT1G125 level shifter |
| `debug` | Test points on rails, grounds, buses, chip selects and control lines; LEDs on +5V, ±15V and ISO 3V3 |
| `supply_switches` | 5 two-pin 1.27 mm header jumpers JP1-JP5, one per section, in series with that section's supply (see "Supply jumpers" below), each with a green LED + resistor that shows its switched rail is live |

## ±15 V rails and power good

The ADP5071 makes +16.4 V / −16.5 V, one LT3097 post-regulates them to **±14.7 V** (V = 100 µA × R_SET, 147 kΩ;
+15 V would sit at the top of the LT3097's 0–15 V positive range, so the nets keep their `+15V` / `-15V` names
but run about 0.3 V low). The two ADP5071 output capacitors (22 µF / 50 V, C62 / C63) also serve as the LT3097
input capacitors, and each output has a 22 µF / 50 V capacitor.

PGP and PGN are open-collector (low = bad). Each drives its own node (`PGP_15V`, `PGN_15V`): +15 V through
220 kΩ / 62 kΩ, about 3.2 V when its rail is good and 0 V when its pin pulls low or the rail is missing (thresholds
from the 432 kΩ / 10 kΩ PGFB dividers, about 13.3 V). Each node turns on a BSS138W that lights its green LED (D24
for +15 V, D25 for −15 V). A BAT54AW (common anode) with a 10 kΩ pull-up to +3V3 ANDs the nodes into `PG_15V`
(3.3 V only when both are good). `PG_15V` gates Q9 (a series BSS138 in the amplifier REM switch) and Q10 (the
`PG_15V_N` flag for GPIO43). The amplifier module logs every change of `PG_15V_N` (they show in the dashboard
console); the firmware should still check it before starting the signal generator.

## GPIO map (ESP32-S3-WROOM-2)

| Signal | GPIO | Signal | GPIO |
|---|---|---|---|
| Bridge CS / RESET | 8 / 9 | AD9833 FSYNC | 7 |
| SPI SCK / MOSI / MISO | 42 / 41 / 40 | MCP4921 CS | 5 |
| LSM6DSOX CS / INT1 / INT2 | 1 / 2 / 39 | ACS37800 SCK / MOSI / MISO / CS | 11 / 12 / 13 / 17 |
| Amp REM enable | 6 | PWR_KILL (LTC2954 KILL#) | 10 |
| FAULT / READY LED | 14 / 15 | Flow tach | 18 |
| EMC2303 ALERT# | 21 | NTC ADC | 4 |
| Status RGB (WS2812B) | 38 | Compressor relay enable | 16 |
| INA239 CS (shared SPI bus) | 3 | ADS1220 CS (shared SPI bus) | 44 (RXD0) |

GPIO3 is a strapping pin (JTAG source); the 10 kΩ pull-up on INA239_CS keeps it high at reset, which selects the default USB-JTAG. The INA239 ALERT pin drives only its LED. GPIO43 (TXD0) toggles with ROM boot messages, so it carries no chip select; it reads the active-low `PG_15V_N` power-good flag through a 1 kΩ series resistor (`PG_15V_N_PIN`). ACS37800 chip-select is on GPIO17. GPIO26–37 are reserved
by the octal flash/PSRAM and are left unconnected.

## Drawing conventions

Power symbols are always upright (supplies point up, grounds hang down) and resistors use the US zig-zag symbol
(`Device:R_US`). Every sheet is hand-laid in the same style: signal flow runs left to right, supplies are drawn as
shared rails with decoupling caps hanging off them, switching loops are kept compact, and nets are wired with
lines rather than net labels (labels are used only for global signals such as the GPIO nets, and for a few
local nets that would otherwise need long detours, for example the ISO7741 isolated-side SPI lines).

Bypass/decoupling capacitors for each IC are drawn together in a labelled block at the side of the sheet (supply rail, caps, ground bus) and connect to the IC through the shared power nets; regulator input/output and compensation capacitors stay in the circuit.

**No-overlap text rule.** Reference, value, net-label and note text may not overlap other text or a symbol body
(plus 1 mm for pin numbers). `tools/textlayout.py` places each field in the first free spot, hides a field only
if none exists, and `gen_schematic.py` exits non-zero if `text overlap check` reports any overlap. Pin names and
numbers drawn inside a library symbol, and labels that sit on their own wire, are outside the rule.

## Regenerating

The schematic files are generated; edit the Python and re-run, don't hand-edit the `.kicad_sch` files.
Each `build_*` function in `tools/gen_schematic.py` sets `sh.handwired = True` and draws its sheet in grid cells
(1 cell = 1.27 mm) with `place_ic`, `pose=at(column, row, rot)`, `wire`, `rail_symbol`, `rail_flag`, `spur` and
`net_label`; `tools/layout.py` (the auto-router) is still there for sheets that leave `handwired` off.
Wires are split at pins automatically, so a pin in the middle of a wire is connected.

```bash
python3 hardware/kicad/tools/make_lib.py        # lib/cryocooler.kicad_sym
python3 hardware/kicad/tools/gen_schematic.py   # root + sheets/
```

`tools/gen_bom.py` writes the Digi-Key BOM to `bom/` (see `bom/README.md`).

`tools/verify_netlist.py` checks the GPIO map against `pin_config.h`, missing footprints and
single-pin nets on a `kicad-cli sch export netlist` output; `tools/compare_netlists.py` compares the
connectivity of two netlists (useful after changing layout, which must not change connections; two-pin
passives may be flipped), and `tools/datasheet_rules.py` checks datasheet-critical connections.

## Review status

Every IC was audited against its datasheet; see [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) for the
errors found and fixed, what was verified, and the open issues that need a decision (notably:
the 12 V → 5 V stage is now an AP63205 buck instead of the over-limit LD1117S50).
`tools/datasheet_rules.py` re-checks 193 datasheet-derived connections on every change.

## PCB layout

`cryocooler.kicad_pcb` is generated by `tools/gen_pcb.py` (run with KiCad's bundled python, which provides
`pcbnew`); don't hand-edit it and expect the edits to survive a regeneration. Layout rules: the
[PCB layout directives](../../AGENTS.md#pcb-layout-directives).

* **Board and housing:** 120 x 100 mm, 1.6 mm, 4 layers, blue solder mask, for the Phoenix Contact UCS
  145-125-F-CCD 7035 housing (`hardware/housing/`, PCB outline drawing 2203447). Four Ø3.2 mm mounting holes
  (H1-H4) on a 111.6 x 91.6 mm pattern, centred: (4.2, 4.2), (115.8, 4.2), (4.2, 95.8), (115.8, 95.8). Each has
  a Ø6 mm ring and a 4.45 mm corner square that the housing drawing restricts (no parts, copper or solder mask;
  rule area `housing_corner` plus mask openings). The housing leaves 31 mm above the board and 10 mm below,
  so the underside takes low-profile SMD parts only. Connectors sit on the board edges facing the side walls,
  which are machined for them.
* **Stackup:** F.Cu signal / In1 solid GND (ISO_GND island) / In2 signal + power pours / B.Cu signal, GND
  pours and stitching vias on the outer layers. Net classes (Power 0.3 mm, Power12V 0.8 mm, Usb) and the
  0.15 mm minimum track live in `cryocooler.kicad_pro`; `cryocooler.kicad_dru` holds the custom rules.
* **ESP32 antenna:** U1 sits at the top edge with the antenna over a routed notch (74.5-93.5 x 0-6 mm); the
  strips beside it (`antenna_keepout`) carry no copper and no parts.
* **Floor plan:** one outlined, labelled box per schematic sheet (`MODULE_REGIONS` in `tools/pcbfloorplan.py`),
  neighbours sharing a border line. Top row: isolated amp current (left, ISO_GND island with 1.5 mm keep-out
  bands), amp control and signal generator, MCU & USB, IMU (right edge). Middle: 12 V input, indicators,
  power good, ±15 V rails, cold head. Bottom row: 5 V / 3.3 V rails, power button, system current, compressor
  relay, I2C bridge, water cooling (fan, pump, flow and NTC headers on the bottom and right edges). Almost every
  part is on the top; a few passives and transistors sit underneath in their section's box. `gen_pcb.py` fails
  if a part is left unplaced or outside its box.
* **Supply jumpers (JP1-JP5):** to debug one section at a time, pull the shunt from its jumper and that supply
  is cut. Each jumper sits in its own section next to the load, with a name printed beside it and a green LED
  (D18-D22, resistor R96-R100) that lights while the switched rail is present. Pin 1 is the main rail, pin 2 the
  switched rail. They are 1.27 mm headers, rated only about 1 A per pin, which is plenty for these logic rails.
  A part whose supply is pulled can still be fed through its signal pins (the ESD diodes), so disconnect its
  cable too when you need it fully dead.

  | Jumper | Label | Cuts | Section |
  |---|---|---|---|
  | JP1 | SG 3V3 | +3.3 V to the signal generator (AD9833 side, MCP4921) | Signal Generator |
  | JP2 | ±15V EN | +5 V into the ±15 V generator (ADP5071), the only source of both ±15 V rails: pull it to disable +15 V and -15 V | Rails ±15V |
  | JP3 | ISO PS | +5 V into the isolated supply (PS1), which powers the whole isolated side | Amp Current (Isolated) |
  | JP4 | WATER EN | switched +3.3 V net `+3V3_COOL`: EMC2303, I2C bridge (SC18IS604 + 74LVC1G125) and the NTC divider, plus their pull-ups | Water Cooling |
  | JP5 | HEAD EN | switched +3.3 V net `+3V3_CH`: the ADS1220 PT1000 ADC and its DRDY pull-up | Cold Head Temp |

  Pulling JP4 cuts only the 3.3 V logic: the 12 V fans, pump and flow sensor stay powered, and with the EMC2303 off
  their PWM lines float (many 4-pin fans then run at full speed). An unpowered ADS1220 can still clamp the shared
  SPI MISO line through its ESD diodes while other devices are being read, so leave JP5 fitted during normal operation.

* **IMU cable (J14, Molex Micro-Lock Plus 505448-0871, 2 x 4, 1.25 mm, right angle):** the LSM6DSOX is the
  Adafruit breakout (product 4438) mounted on the cryocooler. Odd pins are the row away from the board edge,
  even pins the row at the edge. The cable end is a Molex 5054320801 housing (Micro-Lock Plus dual-row, 8
  circuits) with 505431-series crimp terminals, or Molex's tin pre-crimped leads 797581148 (150 mm) / 797581149
  (300 mm), 26 AWG (tin, to match the header). Power the breakout's `Vin` from 3V3 so its logic stays 3.3 V, and leave its
  `3Vo` pad open. Keep the cable short (it hangs on the shared SPI bus; each signal has a 100 Ω series
  resistor at J14). The pin names are printed beside the connector in pairs (VIN/GND, SCL/SDA, DO/CS, I1/I2).

  | J14 pin | Row | Board signal | Breakout pad |
  |---|---|---|---|
  | 1 | inner | +3V3 | Vin |
  | 2 | edge | GND | GND |
  | 3 | inner | SPI_SCK | SCL |
  | 4 | edge | SPI_MOSI | SDA |
  | 5 | inner | SPI_MISO | DO |
  | 6 | edge | IMU_CS (GPIO 1, 10 k pull-up on the board) | CS |
  | 7 | inner | IMU_INT1 (GPIO 2) | I1 |
  | 8 | edge | IMU_INT2 (GPIO 39) | I2 |

* **Cold head PT1000 (J10, TE T4145035041-001):** M12 A-coded 4-pin female receptacle, right angle, shielded,
  4 A / 250 V, IP67. It mounts through the right side wall (wall 2.0-3.0 mm, Ø12.2 mm hole, nut torque 0.6 Nm)
  with its panel face 0.35 mm beyond the board edge; the axis is 8.5 mm above the board. Turn the inside nut so
  a flat faces the board. Its shield pin and four shell legs are the symbol's `SH` pin, tied to GND, so a
  shielded sensor cable is grounded at the board end. The sensor cable needs an A-coded male M12 plug wired 4-wire:

  | J10 pin | Board signal | PT1000 wire |
  |---|---|---|
  | 1 | F+ (excitation) | force + |
  | 2 | S+ (sense) | sense + |
  | 3 | S- (sense) | sense - |
  | 4 | F- (return) | force - |

* **2-pin headers (J6 NTC, J7 panel button, J13 relay 12 V out):** Adafruit 1769 (4UCON 17311), JST PH
  compatible, 2.0 mm, right angle SMT, 2 A; they take JST PHR-2 housings or PH 2-pin pigtails. The mating face
  sits 0.6 mm inside the bottom edge.
* **Connector labels:** every connector has its function (`SILK_LABELS`, e.g. `12V IN`, `TO CRYOCOOLER`) and
  its pin functions (`PIN_LABELS`) printed beside it: J2 +12V/GND, J3/J4 GND/+12V/TACH/PWM, J5 GND/+12V/TACH,
  J6 NTC/GND, J7 BTN/GND, J8 REM/GND, J9 SIG/GND, J10 1 F+ / 2 S+ / 3 S- / 4 F- (the M12's pins sit under its body, so these are on the back beside them), J11/J12 +/-,
  J13 +12V/GND, J14 as above. Pin 1 is the first label; on a pitch finer than the text, every second label
  steps out. Both are reserved before the passives are placed; when the top has no room they go beside the
  connector's pins on the back.
* **Current path:** J11 -> ACS37800 pins 1-4 / 5-8 -> J12 is pre-routed with locked 2 mm traces.
* **Silkscreen:** text is measured from its printed ink, and the run fails if any text overlaps other text, a
  pad, a part outline, a section line or a pin-1 dot, or leaves the board. Section titles sit on a box border
  (along it, or up a side), else inside the box. Pin 1 is marked on every IC and connector: by the footprint's
  own triangle or dot, else by an added dot. All 40 ESP32 pin names are printed at 0.8 mm beside their pads.
  The board ID (`Cryocooler-Controller`, `UCS 145-125 rev <git short hash>`) is on the back, behind the
  isolated section (top left seen from the front).
  References that have no readable spot beside their part are left off the silkscreen (they stay on the Fab
  layer); the run prints them (9 on this board: TP10, D19, R36, R41, TP44, TP51, C57, C64, C65).
* **Test points:** every IC has test points on its supply, ground and key signals, on the same side of the
  board as the IC and within 8 mm of the part they serve (`test_point_problems` fails the run otherwise; the
  through-hole ground loops TP22-TP25, Keystone 5001 black miniature PC test points, reach any ground and are
  exempt). The pad test points are bare copper and stay out of the BOM; the loops are in it.
* **Flow:** `gen_pcb.py place` (placement and silkscreen only) or `gen_pcb.py route freerouting.jar`
  (placement, Freerouting on F.Cu/In2/B.Cu, pours, stitching vias, island vias); then `tools/fix_route.py`
  (KiCad's python) on the routed board. It removes duplicate GND vias and ones that crowd a foreign track, sit in
  a keep-out or land on another net's pad, reconnects pour fragments that lost their via, removes dangling signal
  vias and GND vias whose hole crowds another hole, nudges a squeezed track clear of a neighbouring track or pad,
  and switches off starved thermals. (`tools/link_usb_vbus.py` matches an earlier board's routing and is not
  needed on this one.) Freerouting 2.x needs Java 25.
* **Ground fan-out:** before routing, every small SMD ground pad gets a locked 0.5 / 0.3 mm via beside it with a
  short track (`fanout_ground_pads`), so the router never fences a ground pad onto a pour island; exposed pads
  with their own thermal vias and big pads are left to the pour.
* **Fine-pitch ground pads:** U4, U11, U20, U21, U23 and U25 ground pads (and C30 / C74 pad 2 and U24 pin 3,
  which the router would otherwise box in) get locked 0.45 mm / 0.2 mm via-in-pad before routing (`FINE_PITCH_GROUND_PADS`,
  `LATE_GROUND_PADS`); `cryocooler.kicad_dru` allows them 0.1 mm copper and 0.2 mm hole clearance. Order
  filled / capped vias.
* **Checks (2026-10-29, UCS 145-125 board):** `kicad-cli pcb drc --schematic-parity` reports 0 errors, 0
  unconnected items and 0 parity issues; the only warnings are 25 "silkscreen clipped by board edge" for the
  connector outlines that overhang the edge on purpose. Schematic ERC is 0, all 193 datasheet rules pass, 326
  footprints plus the 4 mounting holes.
* **Fabrication export:** every `gen_pcb.py` run and `link_usb_vbus.py` ends by running `tools/export_fab.py`
  (Gerbers, drill files, the JLCPCB zip and the front / back renders in `fabrication/`); set
  `SKIP_FAB_EXPORT=1` to skip it, or run the script yourself after a manual board edit (e.g. after `fix_route.py`).
* **IC part numbers:** each U / PS part with room gets its part number on the top silkscreen inside its body
  (0.9 or 0.8 mm, two lines if needed; `add_ic_labels`, also runnable alone as `gen_pcb.py iclabels`).
* **3D models:** KiCad ships no model file for the SG-8002CA (U3), SRP7050TA (L2, L3), NANO2 fuse (F1) or the
  Molex J14, and PS1 is our own footprint, so `tools/pcbmodels.py` writes box envelope models
  (`lib/cryocooler.3dshapes/`, sized from the datasheets) and attaches them.
