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
`pcbnew`); don't hand-edit it and expect the edits to survive a regeneration.

* **Board:** 130 x 110 mm (was 130 x 100; the extra 10 mm at the bottom edge makes room for a label beside every part), 4 layers: F.Cu signal / In1 solid GND (ISO_GND island) / In2 signal + 3V3 pour / B.Cu signal,
  GND pours and stitching vias on the outer layers. Net classes (Power 0.3 mm, Power12V 0.8 mm, Usb) live in `cryocooler.kicad_pro`.
* **Floor plan:** every schematic module has its own outlined, labelled box on the front silkscreen
  (`MODULE_REGIONS` in `tools/pcbfloorplan.py`): signal generator and amp control top left, indicators top
  middle, MCU & USB top right (antenna overhanging the right edge over a copper keep-out), the isolated amp
  current block middle left (ISO_GND island with 1.5 mm keep-out bands), +-15 V rails in the middle, compressor
  relay and the IMU cable header (J14) down the right, 12 V input / button / 5 V and 3.3 V rails / system current
  bottom left, and bottom right the WATER COOLING box (EMC2303, I2C bridge, flow sensor, NTC; fan/pump/flow/NTC
  headers on the bottom edge) and the COLD HEAD TEMP box (ADS1220 + PT1000 header on the right edge). Parts and
  their passives are placed only inside their own box, debug test points join the box of the part they sit beside
  (the cooling-section ones overflow into free spots of the power box, since those two boxes are full), and `gen_pcb.py` fails if a part leaves its box or two boxes are closer than 1.8 mm.
  Lines stop short of the mounting holes; labels sit on a box border.
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

* **IMU cable (J14, JST XH 8-pin):** the LSM6DSOX is the Adafruit breakout (product 4438) mounted on the
  cryocooler. J14 pins 1-8 run top to bottom on the board as VIN, GND, SCL, SDA, DO, CS, I1, I2, the same order
  as the breakout's SPI-side pads (minus its 3Vo pad), so an 8-wire cable maps pin for pin. Power the breakout's
  `Vin` from 3V3 so its logic stays 3.3 V, and leave its `3Vo` pad open. Keep the cable short (it hangs on the
  shared SPI bus; each signal has a 100 Ω series resistor at J14). The pin names are printed beside the connector.

  | J14 (top to bottom) | Board signal | Breakout pad |
  |---|---|---|
  | 1 | +3V3 | Vin |
  | 2 | GND | GND |
  | 3 | SPI_SCK | SCL |
  | 4 | SPI_MOSI | SDA |
  | 5 | SPI_MISO | DO |
  | 6 | IMU_CS (GPIO 1, 10 k pull-up on the board) | CS |
  | 7 | IMU_INT1 (GPIO 2) | I1 |
  | 8 | IMU_INT2 (GPIO 39) | I2 |

* **Connector pin labels:** every terminal and header has its pin functions printed beside the pads on the side
  facing the board interior (`PIN_LABELS` in `tools/gen_pcb.py`): J2 +12V/GND, J3/J4 GND/+12V/TACH/PWM, J5
  GND/+12V/TACH, J6 NTC/GND, J7 BTN/GND, J8 REM/GND, J9 SIG/GND, J10 F+/S+/S-/F- (4-wire PT1000: force, sense),
  J11/J12 +/-, J13 +12V/GND, J14 as above (VIN, GND, SCL, SDA, DO, CS, I1, I2). Pin 1 is the first label in each list.
* **Current path:** J11 -> ACS37800 pins 1-4 / 5-8 -> J12 is pre-routed with locked 2 mm traces.
* **Flow:** `gen_pcb.py place` (placement only) or `gen_pcb.py route freerouting.jar` (placement, Freerouting
  autoroute in two rounds on F.Cu/In2/B.Cu, pours, stitching vias, island vias). `finish` re-opens the routed board
  and redoes the pours and stitching. Freerouting 2.4.1 needs Java 25.
* **Checks (2026-10-17):** `kicad-cli pcb drc` reports 0 unconnected items and no copper violations; the only warnings are 6 silkscreen ones (reference text against reference text or a neighbour's outline, and the back-side logo over the JP2 / JP3 pads). Schematic ERC is 0 and all 175 datasheet rules pass. 302 footprints. After the water-cooling / cold-head split, Freerouting left four connections open (+12V to the amp REM section, a +15V link to C22, VIN at U11, the J12 net at R53) and two stitching vias too close to inner tracks; they were completed with a small grid router (clearance-aware, using the board's own copper as obstacles) and a 0.13 mm via nudge, then the zones were refilled.
* **Checks (2026-10-20, LT3097 revision):** `kicad-cli pcb drc --schematic-parity` reports 0 unconnected items, 0 parity issues and no copper violations; what remains is the TP24 / U1 courtyard overlap (also present on the previous board, the ESP32 courtyard includes its antenna keep-out), 43 silkscreen warnings (more reference texts share the ±15 V box). Schematic ERC is 0 and all 193 datasheet rules pass. 310 footprints.
* **Fabrication export:** every `gen_pcb.py` run and `link_usb_vbus.py` ends by running `tools/export_fab.py` (Gerbers, drill files, the JLCPCB zip and the front / back renders in `fabrication/`); set `SKIP_FAB_EXPORT=1` to skip it, or run the script yourself after a manual board edit.
* **After `route`:** run `python3 tools/link_usb_vbus.py` (KiCad's python). Freerouting leaves the A4/B9 pair of the USB-C VBUS pads unconnected; the script adds a stub, two vias and a short B.Cu link, trying positions until DRC is clean.
* **After `route` (LT3097 revision, Freerouting 2.5.0):** run `tools/fix_route.py` (KiCad's python) on the routed board. It removes GND vias that short or crowd a foreign-net track, gives pour fragments that lost their via a new one, removes signal vias that touch one layer only, links R53 pad 2 to the J12 current path and pulls the Q2 gate track away from Q4. Its two track edits match one routing result, so re-check them after any re-route. This run did not need `link_usb_vbus.py` (the VBUS pair routed). `gen_pcb.py` also joins the LT3097's same-net 0.5 mm-pitch pads with locked 0.2 mm stubs (`PAD_BRIDGES`) and pre-places its GND pad vias before routing, and it does not write the board stackup, so copy the `(stackup ...)` block from the previous board into `(setup` after a regeneration.
* **Fine-pitch ground pads:** the INA239 (U23 pad 7) and AD9833 (U4 pads 4, 9) ground pads get locked 0.35 mm / 0.2 mm via-in-pad before routing; `cryocooler.kicad_pro` allows 0.35 mm vias and a 0.075 mm annular ring for them (order filled/capped vias, check the fab's minimums).
* **Silkscreen labels:** the placer reserves a label pocket beside every part before the next one is placed (`reserve_pockets` in `gen_pcb.py`), so each reference designator and each small label (`SILK_LABELS`: the RESET / BOOT / POWER buttons, the panel button connector and every indicator LED) sits right next to its own part and inside its module box. The back silkscreen carries a black-and-white trace of the cryocooler (`artwork/`, vectorized with potrace, stickers removed, mirrored so it reads from the back) with "STI Hybrid-98 Cryocooler Control Unit" and "ALPHA DEV UNIT" under it; a large "ALPHA" is on the front. To retrace, see `artwork/trace_cooler.py`.
* **IC part numbers:** each U / PS part gets its part number on the top silkscreen inside its body (between the pads, largest font that fits, two lines if needed), so the soldered part covers it and it helps placement; `add_ic_labels` in `gen_pcb.py` runs with the silkscreen and as `iclabels`. Long values use shorter text (`IC_LABEL_TEXT`). Not labelled (no room under the body, or exposed pad): U2, U4, U8, U11, U12, U13, U15, U23, U24, U26 (SOT-23 / MSOP) and U10, U20, U21, PS1 (exposed pads / pad ring). The pin-1 arrows from the library footprints are unchanged.
* **3D models:** KiCad ships no model file for the SG-8002CA (U3), SRP7050TA (L2, L3) or NANO2 fuse (F1), and PS1 is our own footprint, so `tools/pcbmodels.py` writes box envelope models (`lib/cryocooler.3dshapes/`, sized from the datasheets; the PS1 height of 1.8 mm is an assumption) and attaches them. `gen_pcb.py texts` redoes the silkscreen (box lines, reference designators, part labels, logo) and adds the models on an already routed board without touching tracks. `gen_pcb.py iclabels` only adds the IC part numbers (below).
* **Test points:** every `TP` and the `Debug` sheet LEDs are placed beside a pad on their net by `gen_pcb.py` (ground loops use fixed anchors).
