# Design review: datasheet audit

Every IC and active discrete in the schematic was checked against its manufacturer datasheet
(pinout, supply range, required external parts, unused-pin rules, absolute maximums). The
connection-level findings are encoded as regression tests in
[`tools/datasheet_rules.py`](tools/datasheet_rules.py) (162 rules, run against the exported
netlist). ERC alone cannot catch a wrong circuit, so run both after any change:

```bash
kicad-cli sch export netlist --format kicadsexpr -o /tmp/cryo.net hardware/kicad/cryocooler.kicad_sch
python3 hardware/kicad/tools/datasheet_rules.py /tmp/cryo.net
python3 hardware/kicad/tools/verify_netlist.py /tmp/cryo.net      # GPIO map vs pin_config.h
```

## Errors found and fixed

These were wrong in my first version (several were also wrong in the original draft):

| Part | Problem | Datasheet fact | Fix |
|---|---|---|---|
| EMC2303 | ADDR_SEL tied to GND | ADDR_SEL decodes a **pull-up resistor** (Table 5-1): 33 kΩ → 0x4D | 33 kΩ to 3V3 |
| EMC2303 | PWM outputs unpulled | PWM outputs are open-drain by default and need a pull-up | 10 kΩ to 3V3 on PWM1/PWM2 |
| MIE1W0505 | VSEL tied to GND2 but a 5 V rail assumed | VSEL → GND2 gives **3.3 V**; 5 V needs VSEL to VOUT/float | Kept VSEL → GND2; the module now makes ISO_3V3 directly, so the LD1117 and ISO_5V on that side were removed |
| MIE1W0505 | Wrong output cap | 22 µF + 0.1 µF out, 10 µF + 0.1 µF in | Corrected. (It is an MPS part, not Murata.) |
| CL25 | Pin 2/3 swapped (VB was on NC) | VA = 1, VB = 2 (centre lead + tab), NC = 3 in both packages; N3 is TO-92, **N8 is SOT-89** | Fixed pinout; now **CL25N8-G (SOT-89)** as requested |
| Power LED | 120 Ω legs diverted the 25 mA away from the LED | CL25 is a 25 mA source shared by both legs | 330 Ω (about 9 mA reaches the LED) |
| ADP7182 | EN tied to GND | EN is dual-polarity (\|VEN\| ≥ 2 V); **EN = 0 V is off** | EN tied to VIN (−16.5 V) |
| ADP7182 | No stability cap | 100 pF across RFB1 recommended | Added |
| ADP5071 | Draft values (L1 10 µH, RC1 100 k, CC1 10 nF, …) | Tested values in Fig. 47 / Tables 9-11 | L1 3.3 µH, L2 6.8 µH, RC1 5.6 k / CC1 47 nF, RC2 12 k / CC2 68 nF, DFLS240 diodes, 10 µF/50 V outputs |
| ADP5071 | Rails only about ±15 V (no LDO headroom) | VPOS = 0.8 V (1 + RFT1/RFB1); VNEG = 0.8 V − 0.8 V·RFT2/RFB2 | RFT1 2.67 M / RFB1 137 k → +16.39 V; RFT2 2.55 M / RFB2 118 k → −16.49 V |
| ADP7142 / ADP7182 | 2.2 µF caps lose capacitance at 15 V DC bias | ≥ 1.5 µF effective required | 4.7 µF / 25 V |
| LSM6DSOX | SDx (pin 2) and SCx (pin 3) left floating | Must be tied to **VDDIO or GND** in I²C/SPI mode | Tied to GND |
| MCP4921 | Only 100 nF on VDD; Vref bias marginal | 0.1 µF + 10 µF on VDD; LM4040 needs ≥ 60-65 µA | + 10 µF; 8.2 k → 6.8 k |
| WS2812B | 3.3 V data into a 5 V part | VIH = 0.7 × VDD = 3.5 V | 74AHCT1G125 level shifter |
| AD633 | Output offset up to ±50 mV reached the amplifier | AD633 spec: output offset ±5 to ±50 mV | 10 µF DC-blocking cap + 100 kΩ |
| OPA1656 (sine gain stage) | R8 33 k gave 3.3 V pk (6.6 Vpp) full scale, under-using the amplifier's input range | ZE500.1 RCA input 0.2-6 V (unverified, from retailer listings); user wants Vctl 10 V = 10 Vpp (5 V pk, 3.5 Vrms) | R8 33 k → 51 k (gain 16.45, ~4.9 V pk with the AD9833's assumed 0.3 V pk; calibrate in firmware) |

## Verified as correct (no change needed)

| Part | Checked against | Result |
|---|---|---|
| LTC2954-2 (TSOT-23-8) | LTC2954 datasheet 2954fb | Pinout; no internal KILL pull-up (so the 5 V bias is required); KILL abs max 7 V; ONT floating = 32 ms; 100 nF PDT ≈ 0.7 s hold-off; EN#/INT# ratings |
| ESP32-S3-WROOM-2 | Datasheet v1.7 | Pins 28-30 are NC; IO47/48 are 1.8 V on R16V parts; strapping pins; EN needs a defined level |
| AD633JR (SOIC) | AD633 Rev A (pin drawing) | 1 Y1, 2 Y2, 3 −VS, 4 Z, 5 W, 6 +VS, 7 X1, 8 X2; ±15 V; RL ≥ 2 kΩ |
| AD9833 | AD9833 Rev E | COMP 10 nF → VDD, CAP/2.5V 100 nF, 0.1 + 10 µF on VDD, VINH 2.8 V at 5 V VDD |
| OPA1656 / OPA188 | TI datasheets | Pinouts, supply (VS ≤ 40 V), NC pins may float |
| INA239 (replaced the I2C INA237 on 2026-10-14) | TI SLYS027A | VSSOP-10 pinout (1 CS, 2 MOSI, 3 ALERT open-drain, 4 MISO, 5 SCLK, 6 VS, 7 GND, 8 VBUS, 9 IN−, 10 IN+); SPI mode 1, up to 10 MHz; **MISO is tri-stated while CS is high, so it shares the main SPI bus**; VS 2.7-5.5 V (3.3 V logic, push-pull MISO at VS); IN+/IN− polarity unchanged from the INA237 design; VBUS shares the filtered IN− node instead of the demo board's unfiltered tap (its 1 MΩ input draws about 12 µA, a 0.6 mV drop across the 49.9 Ω resistor, and pins 8/9 are adjacent so it routes without a via); ±163.84 mV range (about 10.9 A at 15 mΩ); input filter R ≤ 100 Ω with 0.1-1 µF (49.9 Ω ×2 + 470 nF, about 0.1 % gain error against the 92 kΩ input impedance, trim through SHUNT_CAL); MANUFACTURER_ID 0x5449 |
| ADS1220 (replaced the I2C ADS122C04 on 2026-10-14) | TI SBAS501D | TSSOP-16 pinout (1 SCLK, 2 CS, 3 CLK, 4 DGND, 5 AVSS, 6 AIN3/REFN1, 7 AIN2, 8 REFN0, 9 REFP0, 10 AIN1, 11 AIN0/REFP1, 12 AVDD, 13 DVDD, 14 DRDY, 15 DOUT/DRDY, 16 DIN); pins 4-14 sit where the ADS122C04 had the same functions, so the RTD wiring is unchanged; SPI mode 1 only; **DOUT/DRDY is Hi-Z while CS is high**; CLK tied to DGND (internal oscillator); unused DRDY may be left open or pulled up; AIN2 may float; AIN3/REFN1 low-side switch stays open (PSW = 0); ratiometric 4-wire RTD circuit, VREF ≥ 0.75 V (0.975 V); 20 SPS single-shot conversion = 204850 tCLK = 50 ms |
| ISO7741 | TI SLLSEP4K | Pinout and channel directions, 0.1 µF decoupling, default output high |
| ACS37800 | Allegro datasheet | Pinout, 3.3 V variant, 0.1 µF, 4 × 1 MΩ + RSENSE divider (Fig. 1), SPI VIH 2.8 V |
| LD1117S33 | ST Rev 26 | Pinout (tab = VOUT), ≥ 10 µF output cap, 5 V input within the 15 V limit |
| AP63205 | Diodes DS41326 Rev 3-2 | Pinout 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 BST; component values from Fig. 1 / Table 3; VIN ≤ 32 V |
| IRF4905S, BSS84, BSS138 | Infineon / Diodes / onsemi | Ratings and VGS(th); ±20 V gate limit not exceeded |
| USBLC6-2SC6 | ST Rev 7 | Pinout; drawn as a pass-through (ESP32 side on pins 4/6, connector side on 3/1) so each data line crosses the protection device instead of being tied across it |
| LM4040 | TI LM4040-N | SOT-23 pinout (pin 3 may float) |
| SG-8002CA | Epson datasheet (supplied) | Pin map 1 OE/ST, 2 GND, 3 OUT, 4 VCC; **PH = 5 V CMOS** with OE (high or open = enabled); 0.01-0.1 µF bypass; no filter in the supply line; 7.0×5.0 mm, 5.08 mm pitch footprint. Order the PH variant, e.g. SG-8002CA 25.000000 MHz PH |
| Alphacool ES | Datasheet + manual | Standard 3-pin fan connector; NTC 0.53-194 kΩ (10 kΩ at 25 °C) |

## Resolved: 12 V → 5 V stage

The LD1117S50 (7 V drop, estimated 1.9-4.1 W in a SOT-223, VIN abs max 15 V) was replaced with the
**Diodes AP63205WU-7** 5 V / 2 A synchronous buck, using the datasheet circuit (DS41326 Fig. 1 / Table 3):
4.7 µH (Bourns SRN6045TA-4R7M: 26 mΩ, Isat 6.8 A, Irms 4.5 A), 10 µF + 100 nF input, 2 × 22 µF output,
100 nF bootstrap, EN to VIN, FB to the 5 V output. VIN rating is 3.8-32 V (40 V for 400 ms), which covers the
26 V TVS clamp. Estimated loss at 0.3-0.6 A is 0.1-0.4 W (θJA 89 °C/W, about 10-36 °C rise). The LD1117S33
stays on the 5 V rail (1.7 V headroom, about 0.7 W at 400 mA).

## Supply: Dell XYK93 (Delta DPS-2000EB class)

Reseller listings give about 12.2 V at about 164 A (200-240 V mains in) and a 12 V standby rail rated 3.5 A. Check
the Delta DPS-2000EB datasheet for the exact figures and the PS_ON pinout (I could not find it).

* **Use the main 12 V rail** with PS_ON held low (breakout board). The standby rail is limited to 3.5 A, which is tight
  for the fans and pump. The LTC2954 button still works, because it switches the board's own supply.
* **Fault current:** the supply can deliver about 160 A, so the 5 A SMD fuse (F1) is a backup only; confirm its
  DC breaking capacity in the chosen part's datasheet (F1 is now the Littelfuse 0453005.MR, 125 V AC/DC, 50 A breaking capacity). Add an **inline high-breaking-capacity fuse (7.5-10 A, for example an
  automotive blade fuse) at the PSU end** of the cable.
* **Standby LED current** (about 25 mA, 0.3 W) is not a concern on a mains-powered supply.
* The 12.2 V level is inside every regulator's limits (AP63205 3.8-32 V, LTC2954 2.7-26.4 V, IRF4905 55 V).

## Open issues

1. Power LED draws about 25 mA from VIN in standby (the CL25 current is always flowing); acceptable on this supply.
2. *Resolved:* ACS37800 chip-select moved from GPIO43 (U0TXD, toggles with ROM boot messages) to **GPIO17**
   (`pin_config.h` updated), and 10 kΩ pull-ups to 3V3 on the ISO7741 CS, SCLK and MOSI inputs give defined idle
   levels while the ESP32 GPIOs float in reset.
2. Order the AP63205 as **AP63205WU-7** (fixed 5 V, 1.1 MHz); the 5 V buck switches with ±6% spread spectrum,
   so keep the SW node and input loop small on the PCB.

## INA239 swap (2026-10-14)

* CS is on **GPIO3** (module pin 15). It is a JTAG-source strapping pin, but an idle-high CS with a 10 kΩ pull-up reads 1 at reset, which is the default USB-JTAG selection. IO47/48 are 1.8 V on the N32R16V and IO0/45/46 are boot straps, so IO3 was the only safe free pin.
* ALERT drives only the red LED (10 kΩ pull-up + 1 kΩ + LED, same pattern as the EMC2303 ALERT#); it is not wired to an MCU pin.
* Footprint is unchanged (`TSSOP-10_3x3mm_P0.5mm`); the datasheet's DGS VSSOP-10 is also a 3 x 3 mm, 0.5 mm pitch part, but the land pattern was not compared against the package drawing.
* The INA239 runs from the same 3V3 rail as the ESP32 (derived from the 12 V input; USB VBUS powers nothing on this board), so the chip and the MCU lose power together and the SPI lines cannot drive an unpowered INA239 for more than the brief rail fall time. Firmware reports the chip offline after 3 failed ID reads.
* ERC: the LSM6DSOX SDO pin type was changed to tri-state, matching the INA239 SDO, because both now share MISO. **The LSM6DSOX SDO behaviour with CS high is not confirmed from its datasheet text**; confirm it is high-impedance before relying on the shared bus (bench check: scope MISO with the IMU idle).

## ADS1220 swap and debug aids (2026-10-14)

* ADS1220 CS is on **GPIO44 (U0RXD)**: the console is native USB CDC, UART0 is otherwise unused, and the pin is not a strapping pin. A 10 kΩ pull-up holds CS high. U0TXD (GPIO43) was exposed only as a test point (`UART0_TX`) for the ROM boot log; since 2026-10-20 it carries the `PG_15V_N` power-good flag instead (see below).
* Register values used by the firmware (checked against the register map): REG0 = 0x61 (AIN1/AIN0, gain 1, PGA bypassed), REG1 = 0x00 (20 SPS, normal mode, single-shot), REG2 = 0x54 (REFP0/REFN0, 50/60 Hz rejection, IDAC 250 µA), REG3 = 0x80 (IDAC1 on AIN3). The 50/60 Hz rejection is new compared with the ADS122C04 configuration.
* DRDY is not wired to the MCU; it has a 10 kΩ pull-up and a test point. The firmware waits 60 ms after START/SYNC instead.
* New `debug` sheet: one test point per useful net (power rails, three GND loops, ISO_GND loop, SPI bus, every chip select, I2C, interrupts, PWR_KILL/PWR_INT, EN, BOOT, TXD0, SIG_SINE, NTC_ADC, FLOW_TACH, STATUS_RGB) plus LEDs on +5V, +15V, −15V and ISO 3V3 (4.7 kΩ on the ±15 V rails, 1 kΩ on the others). **The ISO 3V3 LED returns to ISO_GND, not GND**, so the isolation barrier is not bridged. Test points on isolated nets sit inside the ISO_GND island.
* Test points are 1.5 mm SMD pads; ground points are 2.5 mm loops for scope-ground clips.

## Compressor relay driver and sheet cleanups (2026-10-14)

* The compressor relay was never on the board (the old firmware talked to an off-board SparkFun Qwiic relay at I2C 0x19). It is now a GPIO-driven high-side switch on the new `compressor_relay` sheet, the same BSS138 + BSS84 stage and red/green LED as the amplifier REM switch, with a 1N4148W flyback diode across the output. GPIO16 drives it; the LTC2954 INT# line is no longer wired to the MCU (it keeps its pull-up and a test point).
* **Current limit:** the BSS84 stage is rated for about 130 mA, so the output is for a relay coil or SSR input, not a compressor. The output connector is a 2-pin JST XH.
* `amp_control` and `compressor_relay` share one generator function (`rem_switch`), so they stay identical.
* The isolated SPI lines now run as straight wires from the ISO7741 outputs to the ACS37800 (its MOSI/SCLK/CS/MISO symbol pins were reordered to match); the `ISO_*` net labels are gone. Datasheet rules check that each ISO7741 output reaches the matching ACS37800 pin.
* USB VBUS (connector, 4.7 uF cap and the USBLC6 clamp) is one wire with a single label that names the net, instead of two labels.

## SC18IS604 I2C bridge (2026-10-14)

Requested so every ESP32 peripheral is on SPI. The first part named, SC18IS606, bridges the other way (I2C host to SPI devices); the SPI-to-I2C part is the **SC18IS604** (NXP rev. 1.0, 22 Sept 2021, TSSOP16; replaces the discontinued SC18IS600/601).

* Pinout checked from the datasheet: 1 SDA, 2 SCL, 3 INT#, 4 RESET#, 5 GPIO4 (input only), 6 GPIO3, 7 GPIO2, 8 CS#, 9 GPIO0, 10 MOSI, 11 SCLK, 12 VDD, 13 VSS, 14 MISO, 15 VREFP (connect to VDD), 16 GPIO1. VDD 1.71-3.6 V, SPI mode 3 up to 1.2 MHz, at least 8 us between SPI bytes, I2C up to 375 kHz.
* INT# is open-drain and must not be held low at power-on or reset, so it only gets a 10 kΩ pull-up and a test point; firmware polls I2CStat (0xF0 = done, 0xF3 = busy). RESET# has a 10 kΩ pull-up and GPIO9.
* **MISO:** the datasheet does not say MISO is high-impedance while CS is high, and the ACS37800 already showed a part that corrupts a shared bus. A 74LVC1G125 (OE# = CS) gates MISO onto SPI_MISO, so the bridge cannot drive the bus unselected. Remove it only after confirming the behaviour on the bench.
* Unused GPIO0-4 are left open (they are input-only after reset with weak pull-ups; the datasheet gives no unused-pin rule).
* I2C pull-ups (4.7 kΩ to 3.3 V) moved from the root sheet to the bridge sheet; the EMC2303 sheet still connects through the global SDA/SCL nets.
* The datasheet is inconsistent about the I2CTO / I2CStat register addresses (Table 4 says 0x03 / 0x04, Table 8's title says 0x04); the firmware only uses I2CClock (0x02) and I2CStat (0x04, matching Table 4 and the SC18IS600 family). **Verify on hardware.**
* The EMC2303 now costs about a millisecond per register access (SPI command, I2C transfer, status poll, buffer read) instead of a few hundred microseconds on a direct I2C bus.
* The bridge cannot free an EMC2303 that holds SDA low; only cycling the EMC2303's power does.

## Not verifiable from a datasheet I could read

* **LM4040 accuracy grade:** choose the A or B grade for the DAC reference.
* **MIE1W0505 footprint:** your vendor model (SnapEDA); I checked pad names, not the land pattern.
* **SPI modes** (AD9833 mode 2, ACS37800 mode 3, others mode 0/3): set by the firmware libraries.
* **PCB-level items** (creepage between ISO_GND and the logic side, ground returns, copper pours).

## PCB layout open items (updated 2026-10-14)

0. **New this round:** 0.35 mm via-in-pad on 0.5 mm pitch ground pads (U23, U4), 0.075 mm annular ring; the INA239 VBUS joins IN− (adjacent pads); the compressor relay output connector and the bridge sit in the open middle of the board rather than on an edge; the PCB shares a 4-layer stack with 40 test points.

## PCB layout open items (first pass, 2026-10-05)

1. **Screw-terminal rating:** J11/J12 are Phoenix MKDS 1.5 (about 8-12 A) while the ACS37800 path is a 30 A part; the
   pre-routed copper is a single 2 mm F.Cu trace per side (about 4-5 A at 1 oz). Confirm the real cryocooler current and widen / double-side the copper or use heavier terminals.
2. **12 V copper:** VIN / +12 V / VSW are 0.8 mm traces; fine for the fan and pump loads, check against the actual draw.
3. **Via-in-pad:** U11 pin 4 and U2 pin 2 (GND) use 0.45 / 0.2 mm via-in-pad; order filled/capped vias or move the neighbours.
4. **Isolation:** the ISO_GND island has 1.5 mm keep-out bands, which is a pour/copper gap, not a certified creepage figure; the isolator packages set the real barrier.
5. **USB:** D+/D- are 0.2 mm tracks; impedance (90 ohm) is not verified against the fab stackup.
6. **Not checked:** the MIE1W0505 land pattern (vendor model), antenna clearance beyond the module's keep-out, thermal rise of the AP63205 / ADP5071 copper, silkscreen cleanup (21 overlap warnings).

## LT3097 replaces the ADP7142 / ADP7182, with a power-good interlock (2026-10-20)

* The two LDOs are replaced by one **LT3097** (datasheet Rev. 0, read pp. 1-11, 34-45): dual ±500 mA, INP / INN from the ADP5071 rails (limits ±2 V to ±20 V), ENP/UVP and ENN/UVN tied to their inputs, ILIMP / ILIMN to ground, pins 13 and 19 and exposed pad 23 to GND, exposed pad 24 to INN (-16V5, no ground copper or vias under it).
* **Output voltage:** V = 100 µA × R_SET, so 147 kΩ gives ±14.7 V. +15 V is the top of the positive range (0-15 V), and ±1 % on the resistor and the SET current would land above it with 150 kΩ. The rails are therefore about 0.3 V under the old nominal; every load is rated well above 14.7 V.
* **Capacitors:** the datasheet asks for at least 4.7 µF (INP) / 10 µF (INN) on the inputs and 10 µF *effective* on each output, and its Fig. 129 shows X7R parts losing a large share of their capacitance at 15 V DC. The output capacitors are 22 µF / 50 V 1210, and the ADP5071 output capacitors were upsized to 22 µF / 50 V and double as the LT3097 inputs (the module box has no room for a second set). **Not verified:** the ADP5071 loop with the larger output capacitance (RC1 5.6 kΩ / CC1 47 nF, RC2 12 kΩ / CC2 68 nF were set for 10 µF) and the effective capacitance from the maker's DC-bias curve.
* **Start-up:** SETP / SETN get 1 µF / 50 V bypass capacitors; with fast start-up disabled the ramp would take about 2.3 × R × C = 0.3 s, and the PGFB dividers (which also set the power-good threshold) keep fast start-up enabled.
* **Power good:** PGP and PGN are open-collector and pull *low* when bad. A plain pull-up to +3V3 would read "good" with no power, so `PG_15V` is fed from +15 V (220 kΩ / 62 kΩ, about 3.2 V) and the pins pull it down; with either rail missing it reads 0 V. PGFBP / PGFBN dividers (432 kΩ / 10 kΩ) trip at about 13.3 V (90 %).
* **Interlock:** Q9, a second BSS138 in series with the amplifier REM level shifter's source, is gated by `PG_15V`; REM cannot turn on without both rails. Q10 buffers `PG_15V` for a green LED and the active-low `PG_15V_N` flag on GPIO43 (1 kΩ series resistor; GPIO47/48 are 1.8 V on this module).
* **Reference numbers:** U21 is the LT3097 and U22 is retired; new parts take numbers above the old highest (R101-R107, Q9, Q10, D23) so no other reference changed.
* **PCB (done 2026-10-20):** regenerated and routed with Freerouting 2.5.0, then cleaned with `tools/fix_route.py` (see README). Module boxes changed: ±15 V +2 mm down, COLD HEAD TEMP 0.3 mm wider, U16 2 mm lower; the new `power_good` sheet is in the POWER INPUT & RAILS box (Q10 / D23 in its top-left corner), Q9 beside the REM FETs. The LT3097's same-net 0.5 mm-pitch pads are joined by 0.2 mm `PAD_BRIDGES` stubs and its GND pad vias are pre-placed. DRC: 0 unconnected, 0 schematic-parity issues, no copper violations (remaining: the old TP24 / U1 courtyard overlap, silkscreen warnings, one dangling 0.2 mm stub). Gerbers, the JLCPCB zip, renders, BOM and CPL were regenerated. **Not checked:** pad 24 (INN, -16.5 V) clearance to ground copper beyond what DRC covers, and the 22 µF / 50 V parts' real capacitance at 15 V.
* **Other open items:** LT3097 availability and price, and the 22 µF / 50 V and 1 µF / 50 V part numbers, are unchecked. Bench: rails read about ±14.7 V, PG rises only after both are good, pulling JP2 drops it and REM cannot be switched on.
