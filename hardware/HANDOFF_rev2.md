# Rev 2 board handoff (paused 2026-11-02)

Work on `hardware/TODO.md` (bench results of 11/01/2026). Approved plan:
`~/.claude/plans/users-justinhyland-documents-platformio-valiant-pnueli.md`.

## Branch state

- Branch **`ucs-125-87-rev2`**, made from `lt3097-power-good` and rebased onto `main`.
  - The duplicate AGENTS.md commit was dropped.
  - A `.gitignore` conflict was resolved by keeping both `arduino_secrets.h` and `dev/`.
  - `lt3097-power-good` and its origin copy are untouched.
- **Nothing is committed yet.** Everything below is uncommitted in the working tree.
- `include/web_content.h` was already modified before this work started; leave it out of commits.

## Done (uncommitted)

| Item | Where |
|---|---|
| R6 (OPA1656 feedback): 51k → **22k ∥ 1 nF C0G** (gain 7.67, about 2.3 V pk at Vctl 10 V); sheet note updated | `gen_schematic.py` `build_signal_gen`, mirrored in `gen_sim.py` |
| ADP5071 replaced by **LT8582EDKD#PBF** (see "LT8582 design" below) | `make_lib.py` symbol, `gen_schematic.py` `build_rails_15v` |
| Coupled-inductor footprint `L_Coilcraft_MSD7342` (Coilcraft doc 621-1 land pattern) | new `tools/make_footprints.py`, generated `lib/cryocooler.pretty/` |
| LT8582 PG1 / PG2 → nodes `PGP_16V5` / `PGN_16V5` (20k / 39k from `+5V_PS15`; 3.3 V good, 0 V when unpowered; sink 0.25 mA, under the 0.5 mA max) | `build_power_good` (`power_good_node` now takes rail and values) |
| SC18IS604 GPIOs (confirmed in the datasheet; all inputs after reset): GPIO0 (pin 9) `DISP_BL_EN` out; GPIO1 (16) `PGP_15V`, GPIO2 (7) `PGN_15V`, GPIO3 (6) `PGP_16V5`, GPIO4 (5, input-only) `PGN_16V5` | `build_i2c_bridge` |
| ADP5071 datasheet rules replaced by 23 LT8582 / MSD7342 rules | `datasheet_rules.py` |

**Last check run:**
- ERC: one error. `DISP_BL_EN` is a single-pin label because the display sheet isn't written yet.
- Datasheet rules: 197/202 pass. The 5 failures are the old `('nc', 'SC18IS604PW', 9/16/7/6/5)` rules in `datasheet_rules.py` (~line 230). Change them to `net` rules for the GPIO nets above.
- Text overlaps: 0.

Check script (recreate it if the scratchpad is gone; it runs `make_lib`, `gen_schematic`, ERC json, netlist export, `datasheet_rules`, `verify_netlist`):
`/private/tmp/claude-501/.../scratchpad/check.sh`

### LT8582 design (from datasheet `dev/8582f.pdf`, the p.30 "5V to ±12V" circuit)

**Pins and timing:**
- VIN1/2 and SHDN1/2 go straight to `+5V_PS15` (as in the datasheet's p.32 circuit).
- SYNC1 is grounded and CLKOUT1 drives SYNC2.
- CLKOUT2 and GATE1/2 are not connected (no output-disconnect PMOS).
- RT 53.6k gives 1.5 MHz; SS is 0.1 µF.
- VC1 is 6.49k + 4.7 nF ∥ 47 pF; VC2 is 14.7k + 2.2 nF ∥ 47 pF. These are the datasheet's ±12 V values, so check loop stability on the bench.

**Boost channel (+16V5):**
- L 4.7 µH XAL6060-472MEB, DFLS240 diode, 22 µF/50 V 1210 output cap.
- RFBX1 182k: (16.4 − 1.204) / 83.3 µA.

**Inverting channel (−16V5):**
- Coupled **MSD7342-103MLC** (10 µH), using symbol `Device:L_Coupled_1324`, mirrored.
  - Pin 1 (dot) = VIN, pin 3 = SW2.
  - Pin 2 (dot) = VOUT, pin 4 = node X.
- C1 2.2 µF/50 V 1206 couples SW2 to node X.
- DFLS240 from node X to GND, anode at X (verified in the netlist).
- RFBX2 198k.
- Why 10 µH: the datasheet's subharmonic L_MIN at duty ≈ 0.80 is about 5.6 µH and L_MAX is about 14 µH, so the datasheet's 4.7 µH would be too small here.

## Decisions made with the user

- Power good goes to the bridge GPIOs. `PG_15V` AND, the amp REM interlock and `PG_15V_N` on GPIO43 all stay.
- Antenna: **routed notch**, not an overhang.
- FPC connector: **long edge, top side**.
- RJ45 for the IMU: the TODO's three parts all appear to be **MagJacks**. Kycon GLPLX is Gigabit magnetics; Würth 7498111120AR is an integrated transformer; EASE AAOE-8P8C-10610 is listed as 10/100 AutoMDIX. Their transformers would block DC and SPI. The user chose a **plain SMT 8P8C jack with no magnetics**.
  - The candidate is Amphenol RJSSE-5380 (or RJSSE5080), but no drawing has been found yet.
  - Confirm no magnetics, get the footprint and drawing, then report the choice.
  - The user stopped a curl attempt at amphenol-cs.com; ask before retrying that host.

## Display facts (Phoenix datasheet 109921, DCT T 2,4 QVGA S RTOUCH, p.7)

**Controller and connector:** ST7789V, 4-wire SPI half duplex (SDA is input only). The connector is a **Hirose FH12-14S-0.5SH**; KiCad footprint `Connector_FFC-FPC:Hirose_FH12-14S-0.5SH_1x14-1MP_P0.50mm_Horizontal`. Use symbol `Connector_Generic_MountingPin:Conn_01x14_MountingPin`.

**FPC pinout:**

| Pins | Signal |
|---|---|
| 1 YU, 2 XL, 3 YD, 4 XR | Raw resistive touch lines |
| 5 | GND |
| 6 | VCC: 2.6–3.3 V, 3.6 V absolute max; use +3V3 |
| 7 | /CS |
| 8 | /RST |
| 9 | RS (D/C) |
| 10 | SCL |
| 11 | SDA |
| 12 | NC |
| 13 | A (backlight anode) |
| 14 | C (backlight cathode) |

**Backlight:** 4 LEDs in parallel, 3.0 V at 60 mA typical. Planned drive: +5V → 39 Ω (0805) → A, with C switched to ground by a BSS138. The FET gate is driven by `DISP_BL_EN` and held off by a 100k pull-down.

**Firmware init:** the datasheet gives the init register table on p.8; use it for the firmware.

**FFC cable:** whether pin 1 maps to pin 1 or pin 14 depends on the FFC type (same-side vs opposite-side contacts). Note this for the user and BOM.

**Touch controller TSC2046EIPW (TSSOP-16, TI datasheet checked):**
- Pinout: 1 +VCC, 2 X+, 3 Y+, 4 X−, 5 Y−, 6 GND, 7 VBAT, 8 AUX, 9 VREF, 10 IOVDD, 11 PENIRQ, 12 DOUT, 13 BUSY, 14 DIN, 15 CS, 16 DCLK.
- DOUT and BUSY are high-Z with CS high, so it can share `SPI_MISO`.
- No VREF bypass is needed with the internal reference.
- Bypass with 0.1 µF plus optional 1–10 µF.
- Planned: X+ = XR, X− = XL, Y+ = YU, Y− = YD. VBAT and AUX to GND. BUSY and VREF not connected. PENIRQ goes to a test point only.

**GPIO plan:**

| GPIO | ESP32 pin | Net | Notes |
|---|---|---|---|
| 47 | 24 | `DISP_CS` | |
| 48 | 25 | `DISP_DC` | |
| 46 | 16 | `DISP_RST` | 10k pull-down: the strap stays low and the display is held in reset at boot |
| 45 | 26 | `TOUCH_CS` | 10k pull-down, which matches the default VDD_SPI strap; firmware must drive it high before any SPI traffic |

Add these to the `right` dict in `build_mcu` and remove pins 16/24/25/26 from its nc list.

## Remaining work, in order

1. Fix the 5 SC18IS604 rules. Write `build_display` (a new `display` sheet in `SHEETS`) and the GPIO map changes. Add datasheet rules for the TSC2046 and FPC.
2. RJ45: choose a plain SMT 8P8C part (see above), add its footprint to `make_footprints.py`, and replace J14 in `build_imu`. Document the RJ45 pin → Adafruit pad map.
3. Jumpers JP1-JP5: Keystone **5110** (0603 "true zero ohm" jumper, K75p60) fits the standard `Resistor_SMD:R_0603_1608Metric` footprint. Change `SWITCH_HEADER` and the symbol in `supply_block`.
4. LEDs: every LED goes to 0402, green for good states and red for faults, at about 1 mA. D15 and D16 (±15 V, white) were the too-bright ones. Fix the missing −15V label on the PCB.
5. Test points: name them on the silkscreen (net name, not TP#). Add ±15 V test points beside the LT3097/LT8582 outputs, and one on the AD9833 VOUT.
6. Move passives to 0402 where the voltage and power ratings allow; check the DC-bias derating. Update the `gen_bom.py` tables, including LT8582, MSD7342, XAL6060, TSC2046, FH12, the jumpers and the RJ45.
7. `pin_config.h`: add DISP_*/TOUCH_*. Then the firmware display module (LovyanGFX or TFT_eSPI for the ST7789V, basic status text) and the bridge-GPIO power-good reads, plus tests.
8. PCB:
   - Outline 100 x 62 (UCS 125-87, `dev/UCS_125-87_PCB_Dimensions.png`): M3 holes at 91.6 x 53.6, and 4.45 mm corner keep-outs with no parts and no mask.
   - Antenna notch, new `MODULE_REGIONS`, double-sided placement.
   - Do a fit check before routing, then route, DRC, renders, and restore `.kicad_pro`.
9. Docs: README, DESIGN_REVIEW and TODO ticks. Commit on `ucs-125-87-rev2` (push only when asked).
