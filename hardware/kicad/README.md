# Cryocooler controller — KiCad schematic

KiCad 10 hierarchical schematic for the ESP32-S3 cryocooler controller. Open
`cryocooler.kicad_pro`. A PDF export is in `cryocooler-schematic.pdf`. No PCB layout yet.

GPIO assignments follow [`include/config/pin_config.h`](../../include/config/pin_config.h).
The hardware table in the top-level README is stale (wrong buses/pins for the IMU, DAC,
ACS37800 and EMC2303), so use this file instead.

## Sheets

| Sheet | Contents |
|---|---|
| `cryocooler.kicad_sch` (root) | ESP32-S3-WROOM-2-N32R16V, EN/BOOT, USB-C + ESD, I2C pull-ups |
| `power_input` | 12 V screw terminal, 5 A fuse, SMBJ16A TVS, bulk caps |
| `power_button` | LTC2954CTS8-2, IRF4905S high-side P-FET, KILL# bias, CL25N8-G (SOT-89) + red/green LED |
| `rails_logic` | AP63205 buck (12→5 V) → LD1117S33 (5→3.3 V) |
| `rails_15v` | ADP5071AREZ ±16.4 V (datasheet Fig. 47 values) → ADP7142 (+15 V), ADP7182 (−15 V) |
| `signal_gen` | 25 MHz osc, AD9833, OPA1656, MCP4921 + LM4040-2.5 + OPA188, AD633 |
| `amp_control` | GPIO6 → BSS138 → BSS84 high-side 12 V to amplifier REM, red/green LED |
| `amp_current` | ACS37800 (SPI) + ISO7741 + MIE1W0505 (VSEL→GND2 = 3.3 V output), 4×1 MΩ + 4.02 kΩ divider |
| `system_current` | INA237 (I2C 0x40) + 15 mΩ shunt in the switched 12 V rail |
| `cooling` | EMC2303 (0x4D via 33 kΩ ADDR_SEL pull-up; fan + pump), Alphacool ES flow tach and NTC |
| `cold_head` | ADS122C04 (I2C 0x45), 4-wire PT1000, 3.9 kΩ Rref |
| `imu` | LSM6DSOX in SPI mode with INT1/INT2 |
| `indicators` | READY / FAULT LEDs, WS2812B status LED behind a 74AHCT1G125 level shifter |

## GPIO map (ESP32-S3-WROOM-2)

| Signal | GPIO | Signal | GPIO |
|---|---|---|---|
| I2C SDA / SCL | 8 / 9 | AD9833 FSYNC | 7 |
| SPI SCK / MOSI / MISO | 42 / 41 / 40 | MCP4921 CS | 5 |
| LSM6DSOX CS / INT1 / INT2 | 1 / 2 / 39 | ACS37800 SCK / MOSI / MISO / CS | 11 / 12 / 13 / 17 |
| Amp REM enable | 6 | PWR_KILL (LTC2954 KILL#) | 10 |
| FAULT / READY LED | 14 / 15 | Flow tach | 18 |
| EMC2303 ALERT# | 21 | NTC ADC | 4 |
| Status RGB (WS2812B) | 38 | LTC2954 INT# (optional, unused by firmware) | 16 |

GPIO43 (TXD0) is left unconnected because it toggles with ROM boot messages; ACS37800 chip-select is on GPIO17. GPIO26–37 are reserved
by the octal flash/PSRAM and are left unconnected.

## Drawing conventions

Power symbols are always upright (supplies point up, grounds hang down) and resistors use the US zig-zag symbol
(`Device:R_US`). Every sheet is hand-laid in the same style: signal flow runs left to right, supplies are drawn as
shared rails with decoupling caps hanging off them, switching loops are kept compact, and nets are wired with
lines rather than net labels (labels are used only for global signals such as the GPIO nets, and for a few
local nets that would otherwise need long detours, for example the ISO7741 isolated-side SPI lines).

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
`tools/datasheet_rules.py` re-checks 117 datasheet-derived connections on every change.
