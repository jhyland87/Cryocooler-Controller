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
| `rails_15v` | ADP5071AREZ ±16.4 V (datasheet Fig. 47 values) → ADP7142 (+15 V), ADP7182 (−15 V) |
| `signal_gen` | 25 MHz osc, AD9833, OPA1656, MCP4921 + LM4040-2.5 + OPA188, AD633 |
| `amp_control` | GPIO6 → BSS138 → BSS84 high-side 12 V to amplifier REM, red/green LED |
| `amp_current` | ACS37800 (SPI) + ISO7741 + MIE1W0505 (VSEL→GND2 = 3.3 V output), 4×1 MΩ + 4.02 kΩ divider |
| `system_current` | INA239 (SPI mode 1, CS on GPIO3) + 15 mΩ shunt in the switched 12 V rail, 49.9 Ω / 470 nF input filter, ALERT and 3V3 power LEDs |
| `i2c_bridge` | SC18IS604 SPI-to-I2C bridge (SPI mode 3, CS GPIO8, RESET GPIO9) with 4.7 kΩ I2C pull-ups, 74LVC1G125 MISO gate, INT# pull-up + test point |
| `cooling` | EMC2303 (0x4D via 33 kΩ ADDR_SEL pull-up; fan + pump), Alphacool ES flow tach and NTC |
| `cold_head` | ADS1220 (SPI mode 1, CS on GPIO44), 4-wire PT1000, 3.9 kΩ Rref, DRDY pull-up + test point |
| `imu` | LSM6DSOX in SPI mode with INT1/INT2 |
| `compressor_relay` | GPIO16 → BSS138 → BSS84 high-side +12 V switch, flyback diode, red/green state LED, 2-pin JST XH output |
| `indicators` | READY / FAULT LEDs, WS2812B status LED behind a 74AHCT1G125 level shifter |
| `debug` | Test points on rails, grounds, buses, chip selects and control lines; LEDs on +5V, ±15V and ISO 3V3 |

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

GPIO3 is a strapping pin (JTAG source); the 10 kΩ pull-up on INA239_CS keeps it high at reset, which selects the default USB-JTAG. The INA239 ALERT pin drives only its LED. GPIO43 (TXD0) is left unconnected because it toggles with ROM boot messages; ACS37800 chip-select is on GPIO17. GPIO26–37 are reserved
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

`tools/verify_netlist.py` checks the GPIO map against `pin_config.h`, missing footprints and
single-pin nets on a `kicad-cli sch export netlist` output; `tools/compare_netlists.py` compares the
connectivity of two netlists (useful after changing layout, which must not change connections; two-pin
passives may be flipped), and `tools/datasheet_rules.py` checks datasheet-critical connections.

## Review status

Every IC was audited against its datasheet; see [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) for the
errors found and fixed, what was verified, and the open issues that need a decision (notably:
the 12 V → 5 V stage is now an AP63205 buck instead of the over-limit LD1117S50).
`tools/datasheet_rules.py` re-checks 162 datasheet-derived connections on every change.

## PCB layout

`cryocooler.kicad_pcb` is generated by `tools/gen_pcb.py` (run with KiCad's bundled python, which provides
`pcbnew`); don't hand-edit it and expect the edits to survive a regeneration.

* **Board:** 130 x 100 mm, 4 layers: F.Cu signal / In1 solid GND (ISO_GND island) / In2 signal + 3V3 pour / B.Cu signal,
  GND pours and stitching vias on the outer layers. Net classes (Power 0.3 mm, Power12V 0.8 mm, Usb) live in `cryocooler.kicad_pro`.
* **Floor plan:** 12 V input and screw terminals on the left edge, signal generator top left, the isolated ACS37800 /
  ISO7741 / MIE1W0505 block middle left (ISO_GND island with 1.5 mm keep-out bands, nothing but the isolators crosses
  the barrier), +-15 V rails in the middle, ESP32 top right with the antenna overhanging the right edge and a copper
  keep-out beneath it, USB-C on the top edge, fan/pump/flow/NTC headers on the bottom edge, RTD on the right edge.
* **Current path:** J11 -> ACS37800 pins 1-4 / 5-8 -> J12 is pre-routed with locked 2 mm traces.
* **Flow:** `gen_pcb.py place` (placement only) or `gen_pcb.py route freerouting.jar` (placement, Freerouting
  autoroute in two rounds on F.Cu/In2/B.Cu, pours, stitching vias, island vias). `finish` re-opens the routed board
  and redoes the pours and stitching. Freerouting 2.4.1 needs Java 25.
* **Checks (2026-10-14):** `kicad-cli pcb drc` reports 0 errors and 0 unconnected items (only silkscreen warnings: 22 overlaps, 4 over copper, 1 edge); all 807 pad nets match the schematic netlist; schematic ERC is 0. 284 footprints, including about 40 test points and the SC18IS604 / compressor relay / debug additions.
* **After `route`:** run `python3 tools/link_usb_vbus.py` (KiCad's python). Freerouting leaves the A4/B9 pair of the USB-C VBUS pads unconnected; the script adds a stub, two vias and a short B.Cu link, trying positions until DRC is clean.
* **Fine-pitch ground pads:** the LSM6DSOX (U19 pads 2, 3, 6, 7), INA239 (U23 pad 7) and AD9833 (U4 pads 4, 9) ground pads get locked 0.35 mm / 0.2 mm via-in-pad before routing; `cryocooler.kicad_pro` allows 0.35 mm vias and a 0.075 mm annular ring for them (order filled/capped vias, check the fab's minimums).
* **Silkscreen:** small labels (`SILK_LABELS` in `gen_pcb.py`) sit beside the RESET / BOOT / POWER buttons, the panel button connector and every indicator LED, on the first side with room. The back silkscreen carries a black-and-white trace of the cryocooler (`artwork/`, vectorized with potrace, stickers removed, mirrored so it reads from the back) with "STI Hybrid-98 Cryocooler Control Unit" and "ALPHA DEV UNIT" under it; a large "ALPHA" is on the front. To retrace, see `artwork/trace_cooler.py`.
* **Test points:** every `TP` and the `Debug` sheet LEDs are placed beside a pad on their net by `gen_pcb.py` (ground loops use fixed anchors).
