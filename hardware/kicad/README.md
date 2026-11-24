# Cryocooler controller — KiCad schematic

KiCad 10 hierarchical schematic for the ESP32-S3 cryocooler controller. Open
`cryocooler.kicad_pro`. A PDF export is in `cryocooler-schematic.pdf`. The 4-layer board is `cryocooler.kicad_pcb` (see [PCB layout](#pcb-layout)).

GPIO assignments follow [`include/config/pin_config.h`](../../include/config/pin_config.h).
The top-level README hardware table was brought in line with these sheets and the firmware
on 2026-10-14; if the two ever disagree, the schematic and `pin_config.h` win.

## Sheets

| Sheet | Contents |
|---|---|
| `cryocooler.kicad_sch` (root) | ESP32-S3-WROOM-2-N32R16V, EN/BOOT, USB-C (GCT USB4205-GF-A, flag type) + ESD |
| `power_input` | 12 V DC jack (5.5 x 2.1 mm), 5 A fuse, SMBJ16A TVS, bulk caps Rev 5 (2026-11-16): sized for 10 A. J2 is a Molex Mini-Fit Jr 2 x 2 pinned as the ATX 12 V (CPU) connector (1, 2 ground; 3, 4 +12 V) and F1 is 10 A. |
| `power_button` | LTC2954CDDB-2 (INT# to GPIO1), AONR21307 high-side P-FET with slow-start gate network and 15 V clamp, KILL# bias, red standby LED through 13 kΩ and one BSS138, TPD1E05U06 on the button line `PWR_BTN` (the J7 panel header went in rev 4). Rev 5: `PWR_BTN` is a global label, so the display's digital output on the `display` sheet (J21) presses the same line as SW3 Rev 5: optional auto power-on (JP, 2.2 µF and a diode on `PWR_BTN`), jumper not fitted, not bench tested. |
| `rails_logic` | AP63205 buck with SRP4020TA-4R7M (12→5 V); TPS2116 selects +5V or USB VBUS into +5V_OR, priority to the 12 V side → TPS62822 buck with SRP4020TA-R47M (→3.3 V) |
| `rails_15v` | ADP5071ACPZ dual converter at 1.2 MHz with SRP7050TA-3R3M and -6R8M (rev 1 values) → one LT3097 dual LDO (±14.7 V, 147 kΩ SET resistors); the LT3097 PGP / PGN go to the `power_good` sheet Rev 5 (2026-11-16): the LT3097 (no stock) is replaced by an LT3045 (MSOP-12, U21) and an LT3094 (DFN-12, U22) with the same SET, PGFB and output parts. |
| `ldo_15v` ("Regulators +-15V") | The LT3045 (+15 V) and LT3094 (-15 V) post-regulators with their SET, PGFB and output parts. Split off `rails_15v` in the schematic redraw (that sheet was over 30 parts); the circuit and the references are unchanged. Its block carries the PGP_15V / PGN_15V pins. |
| `power_good` | One node and green LED per LT3097 PG pin (with a 470 k / 470 k guard and BSS138W so a missing -15 V pulls `PGN_15V` low), a BAT54AW AND of the two nodes into `PG_15V`, and the 3.3 V flag `PG_15V_N` on GPIO43 (low = both ±15 V rails good); both flags are also read by the MCP23S08 |
| `signal_gen` | ECS-2520MV 16 MHz oscillator, AD9837 (LFCSP-10), OPA2991 dual U5 (A: gain 16.3; B: AD5453 output stage, 22 pF C1), R39 + MMBZ9V1 clamp into AD5453 VREF, AD5453 (decoder Y1); all digital parts on `+3V3_SG` |
| `amp_control` | GPIO6 → BSS138 → BSS84 high-side 12 V to amplifier REM, red/green LED; a second BSS138 (Q9) in series with the level shifter's source is gated by `PG_15V`, so REM cannot turn on unless both ±15 V rails are good |
| `amp_current` | ACS37800-015B5 (SPI, ±15 A at 5 V) + ISOW7741 (isolated 5 V and SPI in one part) with FB1 / FB2, 4×1 MΩ + 4.02 kΩ divider, TE 2305908-2 SMT pluggable header J11, TE 643228-1 through-hole header J12. Rev 4: on the shared SPI bus through two SN74LVC1G125 gates enabled by `ACS_CS` (U41 passes SCK in, U42 passes MISO out), with 10 kΩ pull-ups on the gated SCK and on `ACS_CS` Rev 5 (2026-11-15): the ISOW7741 (no stock) is replaced by an ISOW7841AQDWERQ1 on `+3V3_ISO` (40 mA at 5 V out); FB1 / FB2 and the EN/FLT pull-up are gone. |
| `system_current` | INA239 (SPI mode 1, decoder Y2) + 15 mΩ shunt in the switched 12 V rail, 49.9 Ω / 470 nF input filter, ALERT to expander GP6, ALERT and 3V3 power LEDs Rev 5: the shunt is a 4-terminal part whose sense pads feed the filter, and VBUS sits on `+12V` directly. Later (2026-11-16): the shunt is a 10 mΩ Vishay WSK2512 (16.4 A full scale). |
| `gpio_expander` ("GPIO Expander") | MCP23S08 QFN-20 on the shared SPI bus (mode 0, decoder Y3), on unswitched `+3V3`: GP0-1 power-good flags, GP6 INA239 ALERT, GP2/GP3 ADT7320 INT/CT, GP4, GP5 and GP7 spare (rev 5; GP4 was the display backlight enable and GP7 the touch IRQ); RESET tied to +3V3, A0/A1 and exposed pad to GND, INT to a test point Rev 5 universal I/O: GP4 is `IO_EXP_INT_N` and GP5 `IO_ADC_DRDY_N`; only GP7 is spare. |
| `cooling` ("Water Cooling") | Fan and pump: LEDC PWM through the two halves of one BSS138DW (Q61) as open-drain drivers (gates held on by 10 kΩ to `+3V3`, so 0% drive at reset), tach through 4.7 kΩ to PCNT; Alphacool ES flow tach and NTC; connector-side pull-ups sit on the switched `+3V3_COOL` rail. 2026-11-23: the +12 V pin of J3 and J4 is fed through resettable fuses F3 (MF-MSMF050/24X, net `+12V_FAN`) and F4 (MF-MSMF250/16X, net `+12V_PUMP`), each with its 22 uF cap on the header side; on the rev 7 board both stand on the back above J4, with the pump fuse's pad 1 straight to J4 pin 2 and the fan fuse's through two vias to J3 pin 2. Rev 4: XKB X2510WRS headers (J5 is a 4-pin part with pin 4 unused), 4.7 kΩ and 10 kΩ resistors in arrays RN1 / RN2 |
| `cold_head` ("Cold Head Temp") | ADS1220 (SPI mode 1, CS on GPIO44), 4-wire PT1000, 3.9 kΩ Rref, DRDY pull-up + test point; powered from the switched `+3V3_CH` rail |
| `imu` | J14, a Molex Micro-Lock Plus 2x4 header (505448-0891, 1.25 mm, right angle, positive lock) for the off-board Adafruit LSM6DSOX module: SPI bus, CS, INT1/INT2, +3V3, GND; one NUF6401MN six-channel filter (100 Ω series, 17 pF and ESD clamp each side) |
| `compressor_relay` | GPIO16 → BSS138 → BSS84 high-side +12 V switch, flyback diode, red/green state LED, 2-pin right-angle XKB X2510WRS-02 output |
| `indicators` | WS2812B-2020 status LED behind a 74AHCT1G125 level shifter |
| `debug` | Test points on rails, grounds and control lines; LEDs on +5V and ISO 5V |
| `supply_switches` | 5 Keystone 5110 0603 zero-ohm jumpers JP1-JP5, one per section, in series with that section's supply (see "Supply jumpers" below); FB3 ahead of JP5 Rev 5: JP3 now feeds `+3V3_ISO`, and JP6 with FB4 feeds `+5V_IO` from `+5V` (universal I/O ADC, range switches and sensor excitation). |
| `display` | Rev 5: link to the off-board Waveshare ESP32-S3-Touch-LCD-4.3B, which runs its own firmware. TCAN3414 CAN transceiver (U52, `CAN_TX` GPIO17 with a 10 kΩ pull-up, `CAN_RX` GPIO12, 120 Ω termination R516) to J15 (X2510WRS-04: 1 GND, 2 unswitched 12 V `VIN`, 3 CAN_H, 4 CAN_L). J21 (X2510WRS-04: 1 GND, 2 power button, 3 reset, 4 unused) lets the display's two open-collector outputs press the global `PWR_BTN` like SW3 and pull `ESP_EN` low like the RESET button, each through 100 Ω with a TPD1E05U06 clamp. Rev 4 and earlier: FH12-14S FPC to the Phoenix 2.4" ST7789V display with a TSC2046 touch controller Later on 2026-11-15: J15 and J21 became one 6-pin connector J15 (1 GND, 2 fused 12 V, 3 CAN_H, 4 CAN_L, 5 power button, 6 reset), with a 0.5 A resettable fuse F2 and an ESD2CAN24 clamp; since 2026-11-16 the cable ends in two XKB headers back to back, as XKB makes no 6-pin part: J15 (X2510WRS-04: 1 CAN_H, 2 CAN_L, 3 power button, 4 reset) and J21 (X2510WRS-02: 1 GND, 2 fused 12 V). Rev 6 (2026-11-18): one 6-pin top-entry JST PH header J15 again (B6B-PH-SM4-TB: 1 GND, 2 fused 12 V, 3 CAN_H, 4 CAN_L, 5 power button, 6 reset); J21 is gone. |
| `io_core` ... `io_ch4` (10 sheets) | Rev 5 I/O, replacing `aux_io`: four universal channels on X2510WRS-04 headers J36-J39 (sensor supply, signal, GND, pin 4 unused), each usable as an analog input or a 0-12 V output. `io_core`: DAC60508Z (decoder Y4; outputs 4-7 unused) and ADS124S08 (Y9). `io_switches`: one TMUX1111 (divider legs) and one TMUX7412F (10 kΩ pull-ups). `io_expanders`: two MCP23S17 on Y10. `io_drivers`: two TSB582 duals (gain 4.83, 0-12 V, up to 100 mA) and one TMUX7412F output switch. `io_ch1`-`io_ch4`: 100 kΩ / 20 kΩ input divider, 120 Ω switched loop burden, TPS26625 sensor supply (5 V or 12 V by jumper), two TVS1800 clamps. Channels 1 and 2 also have an SN74LVC1G3157 gate and an SN74LVC1G125 buffer on GPIO5 / 7 for PWM and pulse input. `io_precision`: ports J30 / J31 (load cell, O2 cell). `io_pressure`: ports J32 / J33 for 0.5-4.5 V pressure transmitters on the 5 V excitation (ADC AIN4 / AIN5). See `DESIGN_REVIEW.md`, "Rev 5 schematic: universal I/O" and "Rev 5: I/O cut to four channels". |
| `io_precision` | Rev 5: two precision sensor ports J on the ADS124S08's spare inputs (AIN8-11) for bridges, RTDs, thermocouples and millivolt sensors: 2.2 kΩ / 10 nF per input, 100 nF across each pair, TVS1800 clamps, one TPS26625 switching 5 V excitation to both, and the excitation fed back to REFP0 / REFN0. The ADC analog supply is `+5V_IO`. |
| `expansion` | Rev 5: RS-485 port (SC16IS750 on Y11, 16 MHz clock, THVD2410, X2510WRS-04 header J34 with pin 4 unused, 120 Ω by jumper) and a surface-mount 2 x 5 SPI expansion header (two chip selects Y12 / Y13, interrupt, +3V3, +5V), MISO through two CS-gated buffers. Rev 6 (2026-11-18): J34 and J35 are top-entry JST PH headers inside the board (B4B and B10B-PH-SM4-TB; J35: 1 +3V3, 2 +5V, 3 SCK, 4 MOSI, 5 MISO, 6 INT, 7 CS A, 8 CS B, 9-10 GND), and the new 5-pin AUX header J40 (B5B: 1 +5V, 2 +3V3, 3 GPIO11, 4 GPIO13, 5 GND) brings out the two spare GPIOs through 100 Ω with TPD1E05U06 clamps and unfitted 4.7 kΩ pull-ups. Rev 6.1: the Qwiic / STEMMA QT header J41 (JST SH BM04B-SRSS-TB: 1 GND, 2 +3V3, 3 SDA = GPIO11, 4 SCL = GPIO13) on the same lines as J40. |
| `aux_header` ("AUX Header") | The 5-pin AUX header (GPIO11, GPIO13, both logic supplies) and the Qwiic / STEMMA QT header J41 (rev 6.1) with their shared series resistors, clamps and unfitted pull-ups. Split off `expansion` in the schematic redraw; circuit and references unchanged. |
| `io` ("Universal IO") | Parent sheet of the ten universal I/O sheets (`io_core`, `io_drivers`, `io_switches`, `io_expanders`, `io_precision`, `io_pressure`, `io_ch1` to `io_ch4`). No parts: it shows their blocks, wires neighbouring columns and joins far ones by net labels. |

## ±15 V rails and power good

The ADP5071 makes the two pre-regulated rails from `+5V_PS15` at 1.2 MHz (SYNC/FREQ low), with SEQ to VREG for a
simultaneous start and SLEW to AGND for the slowest, quietest edges. One LT3097 post-regulates them to **±14.7 V**
(V = 100 µA × R_SET, 147 kΩ; +15 V would sit at the top of the LT3097's 0–15 V positive range, so the nets keep their
`+15V` / `-15V` names but run about 0.3 V low). The compensation and feedback values are from rev 1; check the loops on the
bench.

`PGP_15V` and `PGN_15V` go to MCP23S08 GP0 and GP1, and the amplifier module logs which rail changed
(`amplifier::railFlags()`).

PGP and PGN are open-collector (low = bad). Each drives its own node (`PGP_15V`, `PGN_15V`): +15 V through
220 kΩ / 62 kΩ, about 3.2 V when its rail is good and 0 V when its pin pulls low or the rail is missing (thresholds
from the 432 kΩ / 10 kΩ PGFB dividers, about 13.3 V). Each node turns on a BSS138W that lights its green LED (D11
for +15 V, D12 for −15 V). A BAT54AW (common anode) with a 10 kΩ pull-up to +3V3 ANDs the nodes into `PG_15V`
(3.3 V only when both are good). `PG_15V` gates Q9 (a series BSS138 in the amplifier REM switch) and Q10 (the
`PG_15V_N` flag for GPIO43). The amplifier module logs every change of `PG_15V_N` (they show in the dashboard
console); the firmware should still check it before starting the signal generator.

## GPIO map (ESP32-S3-WROOM-2)

| Signal | GPIO | Signal | GPIO |
|---|---|---|---|
| CS decoder enable / fan PWM | 8 / 9 | CS decoder A / B / C | 3 / 44 (RXD0) / 45 |
| SPI SCK / MOSI / MISO | 42 / 41 / 40 | Universal I/O channels 1 and 2, PWM gate and pulse input (GPIO11 / 13 spare) | 5, 7 |
| LSM6DSOX INT1 / INT2 | 2 / 39 | CAN TX / RX (display link) | 17 / 12 |
| Amp REM enable | 6 | PWR_KILL (LTC2954 KILL#) | 10 |
| PWR_INT (LTC2954 INT#) | 1 | Flow tach | 18 |
| Pump PWM / fan tach | 14 / 15 | NTC ADC | 4 |
| Pump tach | 21 | CS decoder D (via 74LV1T34) | 47 (1.8 V) |
| Status RGB (WS2812B-2020) | 38 | Compressor relay enable | 16 |
| Spare (rev 5; display D/C before) | 48 (1.8 V) | Spare (rev 5; display reset before) | 46 (strap) |

The shared-bus chip selects come from U32 (74HC154BQ, rev 5; rev 4 has an SN74LVC138A): Y0 AD9837, Y1 AD5453, Y2 INA239, Y3 MCP23S08, Y4 spare (the display before rev 5), Y5 ACS37800 (rev 5; the TSC2046 touch controller before, with the ACS37800 select on GPIO17), Y6 ADS1220, Y7 LSM6DSOX, Y8 ADT7320, Y9 to Y15 spare. Address bit D is GPIO47, which is 1.8 V on this module, so a 74LV1T34 buffer (100 k pull-down on its input) lifts it to 3.3 V. Firmware numbers them `CS_ID_BASE + Yn` (`pin_config.h`, `src/spi_select.cpp`). Rev 5 universal I/O and expansion: Y4 DAC60508, Y9 ADS124S08, Y10 the four MCP23S17, Y11 SC16IS750, Y12 / Y13 the expansion header; Y14 and Y15 are spare.

GPIO3 is a strapping pin (JTAG source); R17 (10 kΩ) on CS_ADDR_A keeps it high at reset, which selects the default USB-JTAG. R19 (10 kΩ) on CS_ADDR_C holds strap GPIO45 low, and R18 (10 kΩ) on CS_EN_N keeps the decoder off until firmware runs. The INA239 ALERT pin drives only its LED. GPIO43 (TXD0) toggles with ROM boot messages, so it carries no chip select; it reads the active-low `PG_15V_N` power-good flag through a 1 kΩ series resistor (`PG_15V_N_PIN`). ACS37800 chip-select is on GPIO17. GPIO26–37 are reserved
by the octal flash/PSRAM and are left unconnected.

## Schematic profile

How this project applies the repo-wide drawing rules (`.claude/rules/schematic-drawing.md`, the
`kicad-schematic-design` skill). The details of each helper are in "Drawing conventions" below.

| | |
|---|---|
| Root sheet | `cryocooler.kicad_sch` (project `cryocooler.kicad_pro`) |
| Made by | `tools/gen_schematic.py` (symbols: `tools/make_lib.py`); never hand-edit the `.kicad_sch` files. See "Regenerating" and the `kicad-schematic` skill |
| Descriptions | `tools/part_descriptions.py`: `DESCRIPTIONS` by reference, `NET_DESCRIPTIONS` by label name. `gen_schematic.py` fails on a part or label without one |
| Check config | `schematic_checks.json`: allowed globals `{SPI}` and `{I2C}`, 30 parts per sheet, 85 mm, baseline `tools/sheet_structure_baseline.json` |
| Checks | the `kicad-schematic` skill's list (generator checks, ERC, `datasheet_rules.py`, `verify_netlist.py`, `check_symbols.py`, `check_sheet_structure.py`). Expected counts are in the latest `hardware/HANDOFF_rev*.md` |
| Connectivity gate | `tools/compare_netlists.py --strict` against a baseline netlist: references, pins, net names, values and footprints unchanged (`--renamed` when nets were renamed on the board too) |
| Routed board | Yes: `cryocooler.kicad_pcb` depends on net names, net classes match them by pattern, and `cryocooler.kicad_dru` names nets. A rename reaches the board through `tools/rename_board_nets.py` and `tools/relink_board_sheets.py` (names only, no copper moves) |
| Net names | Named for their job; active-low nets barred through `ACTIVE_LOW` in `tools/active_low.py` |
| Helpers | `net_label(..., to_parent=True)` and `SHEET_PINS` (sheet pins), `root_links()` (joins blocks on the root), `IO_BLOCKS` and `NESTED_SHEETS` (child sheets), `spi_bus()` (the `{SPI}` bus), `gnd_bus` (ground bars), `place_blocks` / `decoupling_block` (decoupling blocks), `LABEL_DIRECTION` in `tools/kicadgen.py` (label shapes), `from_stock` in `tools/make_lib.py` (pin layout), `PINNED_FIELDS` (text moved by hand in KiCad) |
| Exceptions | None |

The IMU board (`imu/`, below) is a second project with its own generator, `tools/gen_imu_schematic.py`. It has
no `schematic_checks.json` yet, so `check_sheet_structure.py --project imu/imu.kicad_pro` uses the defaults.

## Board profile

The counterpart of the schematic profile: the one place that names, for the project in this tree, the files
the repo-wide PCB rules (`.claude/rules/hardware-pcb.md`), the board skills and the `pcb-reviewer` agent point
at. Counts, baselines and accepted exceptions live in these files, never in the rules.

| | |
|---|---|
| Board | `cryocooler.kicad_pcb` (project `cryocooler.kicad_pro`; fab rules in `cryocooler.kicad_dru`) |
| Board script | `tools/rev7_board.py` (density-driven placement, pre-route and finish; other `tools/*_board.py` scripts are one-off). **This board draws no section outlines or names**: parts are grouped by connectivity and pad density, not by schematic sheet, so there is no `sections` step and the placement preview colours parts by sheet |
| Handoff | `hardware/HANDOFF_rev7.md`: board outline, directives, current state, how it was routed, check results, decisions, open items. Rev 7 (UCS 195-145, 170 x 120 mm, 4 layers) is routed and installed; `rev7_board.py place` no longer reproduces it, so the board file is the source |
| Check config | `board_checks.json` beside the `.kicad_pro`: `suppress` entries (each with a reason), the `placement`, `hot_loops`, `net_currents` and `board` sections, and the `baseline` file name |
| Baselines | `tools/board_checks_baseline.json` (down-only; `placement_gate` `TESTPOINT_MISSING` 53). Accepted DRC warnings: `silk_edge_clearance` 4 (all J2, stock Molex footprint) and `lib_footprint_mismatch` 2 (U1, U18); errors, unconnected and parity 0. `board_checks.py` has one suppression (0.2 mm `+12V` neck into U23 pad 8) |
| Checks | `tools/placement_gate.py` (placed, unrouted board), then `tools/board_checks.py` (routed board), `make drc`, `make checks`; `tools/check_gerbers.py` runs at the end of `tools/export_fab.py` |
| Fab folder | `fabrication/` (Gerbers, JLCPCB zip, renders; `fabrication/README.md` has the order settings) |

## Drawing conventions

The drawing rules that apply to every sheet and every board revision are in the
`kicad-schematic-design` skill (`.claude/skills/kicad-schematic-design/SKILL.md`). Two points
close together are joined by a wire; a label pair is for a long or crowding run. This section
describes how this generator carries those rules out.

Power symbols are always upright (supplies point up, grounds hang down) and resistors use the US zig-zag symbol
(`Device:R_US`). In tight spots the small symbols are used instead (`Device:R_Small_US`, `Device:C_Small`, with
`small=True` on `hres` / `vres` / `hcap` / `vcap` in `tools/gen_schematic.py`), and neighbouring grounds share one bar. Every sheet is hand-laid in the same style: signal flow runs left to right, supplies are drawn as
shared rails with decoupling caps hanging off them, switching loops are kept compact, and nets are wired with
lines rather than net labels. Signals between sheets go through hierarchical labels and sheet pins; global labels
are kept for the buses in `allowed_globals` in `schematic_checks.json` (`{SPI}`, and `{I2C}` if one is added). `tools/check_sheet_structure.py` enforces this
along with label pairs that should be wires, a 30-part sheet limit, copied sheets and wires beside a part body.
What is left from before the rules is counted in `tools/sheet_structure_baseline.json`, which may only go down.

**Active-low nets.** The generator and firmware name them in ASCII (`ADS1220_CS`, `IO_EXP_INT_N`); the drawn
label and sheet pin carry an overbar with no `_N` (`~{ADS1220_CS}`, `~{IO_EXP_INT}`). The list is `ACTIVE_LOW`
in `tools/active_low.py`, applied in `kicadgen.label_text()`. Barred labels, sheet pins and symbol pin names are
drawn at 1.0 mm (`kicadgen.label_size()`, `make_lib.pin_line()`) so the bar clears the row 2.54 mm above, and
`textlayout.py` counts the bar's height in its overlap check. `verify_netlist.py` maps the drawn names back for
its checks and fails on an unbarred active-low net. Add a new active-low net to that list. The IMU board
(`gen_imu_schematic.py`) is not barred yet.

**Sheet pins and root links.** A net that leaves a sheet through a pin is drawn with `net_label(..., to_parent=True)`
(a hierarchical label) on the sheet and listed in `SHEET_PINS` (block edge and row) in `tools/gen_schematic.py`.
`root_links()` draws what joins the blocks on the root (A2). Two ends within 85 mm are joined by a wire that
carries one net label. Ends further apart are not wired across the sheet: the net has a net label on the wire at
the ESP32 or 74HC154 pin and another at the block's pin (`LABEL_LINKED`, `end_label()`, `pin_tag()`). Buses are
for communication buses only (`{SPI}`; `{I2C}` if one is added), so chip selects, interrupts and the decoder's
address lines are single labelled nets (user, 2026-11-19).
A net named by a net label on the root is called `/NAME` (`/PWR_INT`), where a global label gave `NAME`. The 38
nets converted so far were renamed to match in `cryocooler.kicad_pcb`, names only: no pad, track, via or zone
moved. `tools/compare_netlists.py --strict --renamed` accepts a net that kept exactly its pins under a new name, and
`class_patterns()` adds the `/NAME` form to the net classes. A net label must not share a name with a global
label anywhere in the project (ERC `same_local_global_label`), so a net is converted on every sheet in one step
(`hardware/HANDOFF_schematic_redraw.md`).
The ten universal I/O sheets sit under one parent, `sheets/io.kicad_sch` ("Universal IO"): `IO_BLOCKS` lays
out its page and sets the children's pins, `fan()` wires neighbouring columns, and nets between columns that
are not neighbours are net-label pairs. Nets named on that page are `/Universal IO/NAME`, and the children's
local nets are `/Universal IO/<sheet>/NAME`. After every regeneration that changes a label, moves a part to
another sheet or changes the order parts are drawn in, run `tools/rename_board_nets.py base.net new.net` and
`tools/relink_board_sheets.py new.net`: both rewrite names and symbol links in the board file only and refuse
to write anything else. `tools/compare_netlists.py --strict --renamed`
then shows 0 differences.
The ESP32 is drawn with a project symbol whose pins are grouped by what they drive (`from_stock` in
`tools/make_lib.py`); `BLOCK_ORDER` sets where each sheet's block sits on the root, on the 1.27 mm grid
(`BOX_ORIGIN`, `BOX_PITCH`, `BOX_SIZE`; `BOX_HEIGHT` for a block with more pins).
A sheet can instead be drawn inside another sheet: `NESTED_SHEETS` maps its file stem to its parent and the cell
of its block there (empty today; a nested sheet's locally named nets take the longer `/Parent/Child/NET` path).
Sheets are converted one at a time; a redrawn sheet is listed in
`OWN_UUID_SEQUENCE` in `tools/kicadgen.py` so that redrawing it leaves the other sheet files unchanged.

**SPI bus.** `SPI_SCK`, `SPI_MOSI` and `SPI_MISO` are drawn as a KiCad bus on the root sheet and on every
sheet with an SPI part (`spi_bus()` in `tools/gen_schematic.py`). Each pin's wire carries a local member label
and a 45° entry onto a short bus that ends in one global `{SPI}` label. `SPI` is a bus alias in
`cryocooler.kicad_pro`, and the group has no name before the braces, so the nets keep their own names
(`SPI_SCK`, not `SPI.SCK`). Chip selects are single labelled nets (above).

**Wire colours.** Power nets are colour-coded by net class in the schematic and the PCB editor, using the
ATX power-supply wire colours: 3.3 V orange (`Power`), 5 V and USB VBUS red (`Power5V`), 12 V input yellow
(`Power12V`), negative analog rails blue (`PowerAnalogNeg`), and by extension +15 V / +16.5 V dark red
(`PowerAnalogPos`) and the isolated 5 V purple (`PowerIso`, after ATX's separate 5 V standby). Schematic shades
are darker for the light sheet. Signals keep the default colour so colour means power; their classes (SPI,
Usb, Analog, Control) stay for filtering. Grounds (`Ground`) are grey on the PCB only. A legend sits at the
top of the root sheet. `NET_CLASSES` in `tools/gen_schematic.py` holds both colours and the name patterns and
writes them to `cryocooler.kicad_pro`. The split-off power classes copy Power's copper rules and the rest copy
Default's, so none of them change the board. The PCB editor shows class colours on copper only with
Appearance → Nets → Net colors: All.

Bypass/decoupling capacitors for each IC are drawn together in a labelled block at the side of the sheet (supply rail, caps, ground bus) and connect to the IC through the shared power nets; regulator input/output and compensation capacitors stay in the circuit.

**Drawings.** `sh.rectangle()` and `sh.polyline()` add drawing-only shapes that connect nothing; the display sheet
uses them for the outline of the off-board Waveshare touchscreen (`waveshare_drawing()`).
A part with `off_board = True` (the display's terminal strip, DS1) is drawn and wired like any other but is left out
of the BOM, the netlist and the board.

**No-overlap text rule.** Reference, value, net-label and note text may not overlap other text or a symbol body
(plus 1 mm for pin numbers). `tools/textlayout.py` places each field in the first free spot, hides a field only
if none exists, and `gen_schematic.py` exits non-zero if `text overlap check` reports any overlap. The same check fails on a wire or bus drawn across a label's text or a global label's flag (`wires_over_labels`). `gen_schematic.py` also exits non-zero on wire geometry (`wire geometry check`): a pin or label within 0.05 mm of a wire but not on it, a pin in the middle of a wire with no junction, a diagonal wire, a wire under 1 mm, and one net's labels drawn with different shapes. Pin names and
numbers drawn inside a library symbol, and labels that sit on their own wire, are outside the rule.

## Regenerating

The schematic files are generated; edit the Python and re-run, don't hand-edit the `.kicad_sch` files.
Each `build_*` function in `tools/gen_schematic.py` sets `sh.handwired = True` and draws its sheet in grid cells
(1 cell = 1.27 mm) with `place_ic`, `pose=at(column, row, rot)`, `wire`, `rail_symbol`, `rail_flag`, `spur` and
`net_label`; `tools/layout.py` (the auto-router) is still there for sheets that leave `handwired` off.
Wires are split at pins automatically, so a pin in the middle of a wire is connected.
A Reference or Value moved by hand in KiCad is lost on the next run unless it is copied into
`PINNED_FIELDS` (sheet file, reference, unit and the two positions in mm); text layout keeps those spots.

```bash
python3 hardware/kicad/tools/make_lib.py        # lib/cryocooler.kicad_sym
python3 hardware/kicad/tools/gen_schematic.py   # root + sheets/
```

Every part's hidden Description field says what it does in this circuit, and every net label's says what the net carries
(open a symbol's or label's properties in KiCad to read it). The text comes from `tools/part_descriptions.py`:
`DESCRIPTIONS` keyed by reference and `NET_DESCRIPTIONS` keyed by label name. `gen_schematic.py` exits non-zero if a
part or label has no entry, or an entry names one that no longer exists.

`tools/gen_bom.py` writes the Digi-Key BOM to `bom/` (see `bom/README.md`).

`tools/gen_wiring_diagram.py` draws the system wiring diagram, `artwork/system-wiring.png` (shown in the root
`README.md`), around the cooler and supply pictures `artwork/cryocooler.png` and `artwork/dell-psu.png`; it needs `rsvg-convert`. Re-run it when an
off-board connector is added, removed or moved.

`tools/verify_netlist.py` checks the GPIO map against `pin_config.h`, missing footprints and
single-pin nets on a `kicad-cli sch export netlist` output; `tools/compare_netlists.py` compares the
connectivity of two netlists (useful after changing layout, which must not change connections; two-pin
passives may be flipped; `--strict` also requires every reference's value and footprint and every net's exact
name and pins to match, which is what a drawing-only change on a routed board needs), `tools/check_symbols.py` reports overlapping symbols and turned power symbols on
the generated sheets, `tools/count_crossings.py` counts wire crossings per sheet (a horizontal and a vertical wire
passing through each other away from their ends; buses not counted), and `tools/datasheet_rules.py` checks
datasheet-critical connections.

### CI

`make sch-checks` runs ERC, the netlist export and the schematic checks, `make drc` runs DRC with schematic
parity, and `make checks` runs both plus `tools/board_checks.py` when it exists and the board has tracks. The
KiCad paths default to the macOS app; set `KICAD_CLI=` and `KICAD_PYTHON=` elsewhere, and `OUT=` for the
report folder (default `build/hardware-checks`). `.github/workflows/hardware.yml` runs `make checks` in the
`kicad/kicad` container on every push or pull request that touches `hardware/`, and uploads the ERC and DRC JSON.

## Review status

Every IC was audited against its datasheet; see [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) for the
errors found and fixed, what was verified, and the open issues that need a decision (notably:
the 12 V → 5 V stage is now an AP63205 buck instead of the over-limit LD1117S50).
`tools/datasheet_rules.py` re-checks 634 datasheet-derived connections on every change.

## PCB layout

**Rev 7 (2026-11-23):** the schematic, `cryocooler.kicad_pcb`, `fabrication/` and the BOM / CPL files describe rev 7:
Phoenix UCS 195-145, 170 x 120 mm, 4 layers, placed, fully routed and installed, not bench tested, no board ID stamp yet.
Its state, routing sequence, checks, decisions and open items are in [`../HANDOFF_rev7.md`](../HANDOFF_rev7.md).
The rev 3 notes further down (`gen_pcb.py` pipeline) are kept where they describe code rev 7 still shares.

**The routed board is the source of truth.** `tools/rev7_board.py place` no longer reproduces it (the placer reacts
to the current netlist, and hand copper lives only in the board file), so edit the installed board with the
`kicad-pcb-edit` tools and do not regenerate it.

* **Board:** 170 x 120 mm, 1.6 mm, 4 layers: F.Cu signal / In1 solid GND (ISO_GND island) / In2 signal + `+3V3` pour /
  B.Cu signal, GND pours and stitching vias on the outer layers. Four 3.2 mm mounting holes on 161.6 x 111.6 mm, 4.45 mm
  corner squares without mask, antenna notch in the top edge (x 74.5-93.5, y 0-6). Net classes (Power, Power5V,
  PowerAnalogPos, PowerAnalogNeg and PowerIso 0.3 mm, Power12V 0.8 mm, Usb) live in `cryocooler.kicad_pro`; SPI, Analog,
  Control and Ground there are colour classes with the Default rules.
* **Placement:** no section boxes. `tools/rev7_board.py` groups parts by connectivity and pad density (about 0.09 pads/mm2
  per 5 mm cell), with the wall connectors, the 12 V block, the isolated amplifier island (x 0-30, y 37.2-71) and a
  fan-out ring round fine-pitch ICs fixed first. The preview colours parts by sheet.
* **Locked current copper:** `tools/rev7_current.py` holds the 12 V path, the amplifier current path (J11 / U18 / J12), the
  fan and pump stubs and the ISO_GND return as locked tracks and vias inside the `CORRIDORS` in `rev7_board.py`.
  `board_checks.py` sizes them against `net_currents` in `board_checks.json` (IPC-2221, 10 C, 1.25 x margin).
* **120 VAC spacing:** the rule `iso_line_to_return` in `cryocooler.kicad_dru` keeps ISO_GND 1.25 mm from the line-side
  copper (figure from memory of IPC-2221, not checked against the standard).
* **Checks (2026-11-23):** DRC with schematic parity: 0 errors, 0 unconnected, 0 parity; baseline warnings
  `silk_edge_clearance` 4 (all J2, KiCad's stock Molex footprint) and `lib_footprint_mismatch` 2 (U1, U18).
  `board_checks.py` exit 0 with one suppression (0.2 mm `+12V` neck into U23 pad 8, user-accepted).
  `placement_gate.py` at its baseline (`TESTPOINT_MISSING` 53). Not done: part labels, pin names, board ID block, test
  points, housing-fit checks.
* **Supply jumpers:** the rev 3 table (JP1-JP5) no longer applies; the jumpers are on the sheets (JP2, JP11-JP20 ...).
  Pulling one cuts that supply only; a part whose supply is pulled can still be fed through its signal pins (the ESD
  diodes), so disconnect its cable too when you need it fully dead.

* **IMU cable (J14, Molex Micro-Lock Plus 2x4):** the LSM6DSOX is the Adafruit breakout (product 4438) mounted on the
  cryocooler. The cable is 8 wires crimped into a Molex 505432 series 8-circuit dual-row housing; odd pins are
  the back row, even pins the row at the mating face. The pins keep the numbering of the RJ45 they replaced, so
  the far end is wired by the table below, not pin for pin. Power the breakout's
  `Vin` from 3V3 so its logic stays 3.3 V, and leave its `3Vo` pad open. Keep the cable short (it hangs on the
  shared SPI bus; each signal passes a NUF6401MN filter channel at J14, 100 Ω in series). Only `IMU` is printed
  beside the connector; its pins aren't labelled. The [IMU board](#imu-board-imu) replaces the breakout: its J1
  has J14's pin map, so that cable is wired pin for pin (1-1 ... 8-8). The table below is for the breakout.

  | J14 pin | Board signal | Breakout pad |
  |---|---|---|
  | 1 | SPI_SCK | SCL |
  | 2 | GND | GND |
  | 3 | SPI_MOSI | SDA |
  | 4 | +3V3 | Vin |
  | 5 | IMU_CS (from the U32 decoder) | CS |
  | 6 | SPI_MISO | DO |
  | 7 | IMU_INT1 (GPIO 2) | I1 |
  | 8 | IMU_INT2 (GPIO 39) | I2 |

* **Connector pin labels:** every terminal and header has its pin functions printed beside the pads on the side
  facing the board interior (`PIN_LABELS` in `tools/gen_pcb.py`): J2 +12V/GND, J3/J4 GND/+12V/TACH/PWM, J5
  GND/+12V/TACH/NC, J6 NTC/GND, J8 REM/GND, J9 GND/SIG (sleeve, tip), J10 F+/S+/S-/F- (4-wire PT1000: force, sense),
  J11 +/-, J12 +/-/GND, J13 12V/GND, J16-J20 IOn/GND (no J19 in rev 5). Pin 1 is the first label in each list. J14 has no pin labels; use the table above.
* **Rev 3 flow (`gen_pcb.py`, not used for rev 7):** `gen_pcb.py place` (placement only) or `gen_pcb.py route freerouting.jar` (placement, Freerouting
  autoroute in two rounds on F.Cu/In2/B.Cu, pours, stitching vias, island vias). `finish` re-opens the routed board
  and redoes the pours and stitching. Freerouting 2.5 needs Java 25.
* **Fabrication export:** every `gen_pcb.py` run and `link_usb_vbus.py` ends by running `tools/export_fab.py` (Gerbers, drill files, the JLCPCB zip and the board renders in `fabrication/`); set `SKIP_FAB_EXPORT=1` to skip it, or run the script yourself after a manual board edit.
* **After `route`:** run `python3 tools/link_usb_vbus.py` (KiCad's python). Freerouting leaves the A4/B9 pair of the USB-C VBUS pads unconnected; the script adds a stub, two vias and a short B.Cu link, trying positions until DRC is clean.
* **After `route` (LT3097 revision, Freerouting 2.5.0):** run `tools/fix_route.py` (KiCad's python) on the routed board. It removes GND vias that short or crowd a foreign-net track, gives pour fragments that lost their via a new one, removes signal vias that touch one layer only, links R67 pad 2 to the J12 current path and pulls the Q2 gate track away from Q4. Its two track edits match one routing result, so re-check them after any re-route. This run did not need `link_usb_vbus.py` (the VBUS pair routed). `gen_pcb.py` also joins the LT3097's same-net 0.5 mm-pitch pads with locked 0.2 mm stubs (`PAD_BRIDGES`) and pre-places its GND pad vias before routing, and it does not write the board stackup, so copy the `(stackup ...)` block from the previous board into `(setup` after a regeneration.
* **Fine-pitch ground pads:** the INA239 (U23 pad 7) and AD9833 (U4 pads 4, 9) ground pads get locked 0.35 mm / 0.2 mm via-in-pad before routing; `cryocooler.kicad_pro` allows 0.35 mm vias and a 0.075 mm annular ring for them (order filled/capped vias, check the fab's minimums).
* **Silkscreen labels:** the placer reserves a label pocket beside every part before the next one is placed (`reserve_pockets` in `gen_pcb.py`), so each reference designator and each small label (`SILK_LABELS`: the RESET / BOOT / POWER buttons, the panel button connector and every indicator LED) sits right next to its own part and inside its module box. The back silkscreen carries a black-and-white trace of the cryocooler (`artwork/`, vectorized with potrace, stickers removed, mirrored so it reads from the back) with "STI Hybrid-98 Cryocooler Control Unit" and "ALPHA DEV UNIT" under it; a large "ALPHA" is on the front. To retrace, see `artwork/trace_cooler.py`.
* **IC part numbers:** each U / PS part gets its part number on the top silkscreen inside its body (between the pads, largest font that fits, two lines if needed), so the soldered part covers it and it helps placement; `add_ic_labels` in `gen_pcb.py` runs with the silkscreen and as `iclabels`. Long values use shorter text (`IC_LABEL_TEXT`). Not labelled (no room under the body, or exposed pad): U2, U4, U8, U11, U12, U13, U15, U23, U24, U26 (SOT-23 / MSOP) and U10, U20, U21, PS1 (exposed pads / pad ring). The pin-1 arrows from the library footprints are unchanged.
* **3D models:** KiCad ships no model file for the SG-8002CA (U3), SRP7050TA (L2, L3) or NANO2 fuse (F1), and PS1 is our own footprint, so `tools/pcbmodels.py` writes box envelope models (`lib/cryocooler.3dshapes/`, sized from the datasheets; the PS1 height of 1.8 mm is an assumption) and attaches them. `gen_pcb.py texts` redoes the silkscreen (box lines, reference designators, part labels, logo) and adds the models on an already routed board without touching tracks. `gen_pcb.py iclabels` only adds the IC part numbers (below).
* **Test points:** every `TP` and the `Debug` sheet LEDs are placed beside a pad on their net by `gen_pcb.py` (ground loops use fixed anchors).

## IMU board (`imu/`)

A separate 18 x 18 mm, 2-layer board for the LSM6DSOX, cabled to J14. KiCad allows one board per project, so it is
its own project in `imu/` (open `imu/imu.kicad_pro`). It shares `lib/` through its `sym-lib-table`, `fp-lib-table`
and `${KIPRJMOD}/../lib` 3D model paths. Not yet fabricated or bench tested.

* **Circuit:** U1 LSM6DSOXTR in 4-wire SPI (DS12814 Mode 1). SDx and SCx to GND, OCS_Aux and SDO_Aux open. 100 nF on
  VDD (C1) and VDDIO (C2), 10 uF bulk at J1 (C3), a 10k CS pull-up (R1) so the part stays deselected while the cable
  is unplugged, and a green power LED (D1, 1.5k R2, about 1 mA). No I2C, LDO or level shifters: it runs on the main
  board's 3.3 V. A test point for each cable net, named by function. Details in `DESIGN_REVIEW.md`, "IMU board".
* **Connector:** J1 is the same Molex 505448-0891 as J14 with the same pin map, so the cable (two 505432-series
  8-circuit housings, not in the BOM) is wired pin for pin. The pin map is on the back silk, behind J1: each pin's number above its escape via and its
  name below it.
* **Mounting:** a 3.2 mm NPTH (M3 clearance), on no net, centred on the top edge opposite J1's mating face. Copper
  stays 3.0 mm from its centre on both layers, clear of the screw head.
* **Axes:** the front silk shows U1's sensing axes (DS12814 Figure 4): +X toward the mounting hole, +Y toward the left
  edge (the test-point column), +Z out of the top face.
* **Order (JLCPCB):** 2 layers, 1.6 mm, 1 oz, black mask (no extra cost on 2 layers), ENIG (the labels are mask
  openings, and JLCPCB calls HASL unsuitable for fine pitch), **tented vias** and the default `0.3mm/(0.4/0.45mm)` via
  size (every via is 0.3 / 0.6 mm; there is no via-in-pad). No silk or mask text crosses a via, so the board does not
  need the main board's filled and capped vias; `imu_board.py` keeps the stitching off the labels and the board ID.
  The 0.7 mm silk is under JLCPCB's published 1.0 mm minimum, and the quote form has no high-precision silk option.
  In the PCB remark, say the text openings in the front mask are intentional.

`tools/imu_board.py` builds the whole board from the tables in the script (parts, tracks, vias), so hand edits in
KiCad don't survive a rebuild. Change the script, then re-apply the labels and export:

```bash
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
python3 hardware/kicad/tools/gen_imu_schematic.py   # imu/imu.kicad_sch and imu.kicad_pro
$KPY hardware/kicad/tools/imu_board.py              # imu/imu.kicad_pcb
$KPY hardware/kicad/tools/mask_labels.py hardware/kicad/imu/imu.kicad_pcb hardware/kicad/imu/mask_labels.json
python3 hardware/kicad/tools/export_fab.py hardware/kicad/imu/imu.kicad_pcb   # imu/fabrication/
python3 hardware/kicad/tools/gen_bom.py --imu       # imu/bom/
```

After review and commit, `$KPY hardware/kicad/tools/imu_board.py boardid` stamps `Cryocooler IMU` / `BETA rev <hash>`
on the back silk; a rebuild drops it, so stamp again after one. Checks (2026-11-12): ERC 0, `datasheet_rules.py --imu`
25/25, and `kicad-cli pcb drc --schematic-parity --severity-all` 0 errors, 0 unconnected, 0 parity, with 22
`text_height` warnings for the 0.5 mm mask and 0.7 mm silk labels (the accepted baseline).
