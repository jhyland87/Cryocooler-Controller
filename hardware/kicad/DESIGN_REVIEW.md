# Design review: datasheet audit

R, C and D references here use the 2026-11-05 numbering, where parts with the same MPN are consecutive (`tools/ref_map.py`).

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
| OPA1656 (sine gain stage) | R39 33 k gave 3.3 V pk (6.6 Vpp) full scale, under-using the amplifier's input range | ZE500.1 RCA input 0.2-6 V (unverified, from retailer listings); user wants Vctl 10 V = 10 Vpp (5 V pk, 3.5 Vrms) | R39 33 k → 51 k (gain 16.45, ~4.9 V pk with the AD9833's assumed 0.3 V pk; calibrate in firmware) |

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
| LM66100 (added 2026-11-04) | TI SLVSEZ8A | Pinout (1 VIN, 2 GND, 3 CE, 4 NC, 5 ST, 6 VOUT); two wired as Fig. 17, because Fig. 15's plain cross-tied CE turns both off when the inputs are equal; VIN 1.5-5.5 V, 1.5 A, 79 mΩ typ at 5 V; ST sinks 0.5 mA through the 10k pull-up (1 mA abs max); unused ST tied to GND, N/C left open |
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
  J2 is now a 5.5 x 2.1 mm jack (Tensility 54-00164): 5.5 A up to 40 C and derating above, so that inline fuse no longer protects the jack; F1 does.
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
* The INA239 runs from the same 3V3 rail as the ESP32 (derived from the 12 V input or, since 2026-11-04, USB VBUS through the LM66100 pair), so the chip and the MCU lose power together and the SPI lines cannot drive an unpowered INA239 for more than the brief rail fall time. Firmware reports the chip offline after 3 failed ID reads.
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

## SN74LVC138A chip-select decoder (2026-11-05)

The eight shared-bus chip selects now come from U32, freeing GPIO1, 5, 7 and 47. Moving them to the MCP23S08 was rejected: U25 shares the bus, so its deselect write would clock into the still-selected device (`0x40` is a valid ADS1220 WREG).

* **Part:** SN74LVC138A (TI SCAS291), on unswitched +3V3; first SN74LVC138APWR, now SN74LVC138ARGYR (see "U32 in VQFN"). At 3.3 V: VIH 2 V, tpd max 6.7 ns from A/B/C and 6.5 ns from G2A, well under the GPIO write time.
* **Control:** A/B/C = GPIO3/44/45, G2A = GPIO8, G1 +3V3, G2B GND. R18 holds G2A high until firmware runs; R17 and R19 keep the GPIO3 and GPIO45 strap levels.
* **Removed:** U30, R178, C127, net `DISP_CS_1V8` (the 1.8 V GPIO47 display CS problem goes away), and the now-redundant pull-ups (old numbers R45, R61, R168). U31 stays for `DISP_DC`. TP41 (STATUS_RGB) was removed at the user's request, for silk room.
* **Firmware:** chip selects are IDs 100-107, handled by strong `pinMode` / `digitalWrite` overrides in `src/spi_select.cpp`. The ceiling is `int8_t`, Adafruit BusIO's CS type.
* **Open, back-feed:** Y outputs drive high from power-on, while the ADS1220, IMU, AD9833 and MCP4921 can sit on jumpered rails. With JP5 (+3V3_CH) or the +3V3_SG jumper out, the line can back-feed through a CS clamp diode, the rev 1 bench finding on ADS1220 CS. Firmware already drove these lines high after boot, so what is new is the time before firmware runs. No series resistors added.
* **Decoupling:** C39 is about 4 mm of 0.3 mm track from VCC pin 16, because the fan-out left no room closer. Check it on the scope.
* **Not verified on hardware:** clean selects during boot and traffic, all 8 devices responding, normal boot with the straps. AD9833, LSM6DSOX and ST7789 chip-select timing was not checked against a datasheet; GPIO writes take far longer than the decoder delay.

## EMC2303 and SC18IS604 replaced (2026-11-04)

Schematic and firmware only; the PCB still has the old parts. The board now has no I2C. Fan and pump run from ESP32 LEDC and PCNT, and an MCP23S08 takes over the bridge's GPIO job plus the two status LEDs. Every GPIO was in use, so this is what freed the pins.

* **PWM:** GPIO9 (fan) and GPIO14 (pump) -> 1 kΩ -> BSS138 gate, drain to connector pin 4. The Intel 4-wire spec allows 5.25 V open circuit on PWM and the ESP32-S3 limit is VDD + 0.3 V, so a GPIO must not connect directly. 25 kHz sits in the spec's 21-28 kHz range.
* **Inverted:** GPIO high = FET on = 0% drive, and firmware writes `255 - duty`. 10 kΩ gate pull-ups to +3V3 keep 0% drive while the GPIO floats at boot, which matters because the pump stalls above about 4400 RPM.
* **Tach:** connector pin 3 -> 4.7 kΩ to +3V3_COOL -> 1 kΩ -> GPIO15 (fan), GPIO21 (pump).
* **MCP23S08:** on +3V3 so a jumper cannot take down the power-good flags or LEDs. The 74LVC1G125 is gone because the datasheet gives SO a disable time (Fig. 2-6, parameter 14: 100 ns max). VIH is 0.8 VDD = 2.64 V; the power-good nodes are 3.3 V when good.
* **Status LEDs:** READY and FAULT now need SPI and the expander. The WS2812B on GPIO38 still shows status if they fail. `PG_15V_N` stays on GPIO43 and the amplifier interlock stays in hardware.
* **Not specified:** the BSS138 datasheet gives RDS(on) at 4.5 V and 10 V only. The load is under 5 mA, so 3.3 V gate drive is not expected to matter; check the PWM low level (0.8 V max) on the bench. The MCP23S08 pin table does not mention the exposed pad; it is tied to VSS, as Microchip's sibling MCP23S09 allows.
* **Footprint:** KiCad's QFN-20 2.7 mm pad version has pad centres at ±1.95 mm against the datasheet's ±2.00 mm land pattern, with the same 0.2 mm pad-to-centre gap. Thermal vias, if used, must be filled or tented.
* Reference numbers of removed parts stay unused; U25 is now the MCP23S08.

## SC18IS604 I2C bridge (2026-10-14, superseded above)

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

1. **Terminal rating:** J11/J12 are now SMT TE 2305908-2 / -3 (check their rating against the drawing; first pass used Phoenix MKDS 1.5, about 8-12 A) while the ACS37800 path is a 30 A part; the
   pre-routed copper is a single 2 mm F.Cu trace per side (about 4-5 A at 1 oz). Confirm the real cryocooler current and widen / double-side the copper or use heavier terminals.
2. **12 V copper:** VIN / +12 V / VSW reworked for 4 A total (see `hardware/archive/HANDOFF_145.md`); check with a thermal camera at full load.
3. **Via-in-pad:** U11 pin 4 and U2 pin 2 (GND) use 0.45 / 0.2 mm via-in-pad; order filled/capped vias or move the neighbours.
4. **Isolation:** the ISO_GND island has 1.5 mm keep-out bands, which is a pour/copper gap, not a certified creepage figure; the isolator packages set the real barrier.
5. **USB:** D+/D- are 0.2 mm tracks; impedance (90 ohm) is not verified against the fab stackup.
6. **Not checked:** the MIE1W0505 land pattern (vendor model), antenna clearance beyond the module's keep-out, thermal rise of the AP63205 / ADP5071 copper, silkscreen cleanup (21 overlap warnings).

## LT3097 replaces the ADP7142 / ADP7182, with a power-good interlock (2026-10-20)

* The two LDOs are replaced by one **LT3097** (datasheet Rev. 0, read pp. 1-11, 34-45): dual ±500 mA, INP / INN from the ADP5071 rails (limits ±2 V to ±20 V), ENP/UVP and ENN/UVN tied to their inputs, ILIMP / ILIMN to ground, pins 13 and 19 and exposed pad 23 to GND, exposed pad 24 to INN (-16V5, no ground copper or vias under it).
* **Output voltage:** V = 100 µA × R_SET, so 147 kΩ gives ±14.7 V. +15 V is the top of the positive range (0-15 V), and ±1 % on the resistor and the SET current would land above it with 150 kΩ. The rails are therefore about 0.3 V under the old nominal; every load is rated well above 14.7 V.
* **Capacitors:** the datasheet asks for at least 4.7 µF (INP) / 10 µF (INN) on the inputs and 10 µF *effective* on each output, and its Fig. 129 shows X7R parts losing a large share of their capacitance at 15 V DC. The outputs and the -16V5 input each have two 22 µF / 25 V X7R 1210 in parallel and the +16V5 input has one (no 22 µF / 50 V X7R 1210 could be sourced); they double as the LT8582 outputs. **Not verified:** the ADP5071 loop with the larger output capacitance (RC1 5.6 kΩ / CC1 47 nF, RC2 12 kΩ / CC2 68 nF were set for 10 µF) and the effective capacitance from the maker's DC-bias curve.
* **Start-up:** SETP / SETN get 1 µF / 50 V bypass capacitors; with fast start-up disabled the ramp would take about 2.3 × R × C = 0.3 s, and the PGFB dividers (which also set the power-good threshold) keep fast start-up enabled.
* **Power good:** PGP and PGN are open-collector and pull *low* when bad. A plain pull-up to +3V3 would read "good" with no power, so each pin gets its own node fed from +15 V (`PGP_15V`, `PGN_15V`: 220 kΩ / 62 kΩ, about 3.2 V); with its rail missing a node reads under 0.3 V, which relies on the weak PG_15V pull-up below. PGFBP / PGFBN dividers (432 kΩ / 10 kΩ) trip at about 13.3 V (90 %).
* **One LED per PG pin:** each node gates a BSS138W (SOT-323) that pulls a green 0402 LED (1 kΩ to +3V3) low: D11 = +15 V, D12 = −15 V. A BAT54AW (common anode, SOT-323) with a 470 kΩ pull-up to +3V3 (10 kΩ lifted dead nodes to 2.2 V through their 62 kΩ dividers and read good) ANDs the two nodes into `PG_15V`, so the interlock and flag are unchanged: Schottky forward drop plus the pin's saturation voltage keeps PG_15V well under the BSS138's 0.8 V minimum threshold whenever either node is low.
* **Interlock:** Q9, a second BSS138 in series with the amplifier REM level shifter's source, is gated by `PG_15V`; REM cannot turn on without both rails. Q10 (BSS138W) buffers `PG_15V` into the active-low `PG_15V_N` flag on GPIO43 (1 kΩ series resistor; GPIO47/48 are 1.8 V on this module). The amplifier module logs every change of `PG_15V_N`.
* **Reference numbers:** U21 is the LT3097 and U22 is retired; new parts took numbers above the old highest, so no other reference changed at that time.
* **PCB (done 2026-10-20):** regenerated and routed with Freerouting 2.5.0, then cleaned with `tools/fix_route.py` (see README). Module boxes changed: ±15 V +2 mm down, COLD HEAD TEMP 0.3 mm wider, U16 2 mm lower; the new `power_good` sheet lives in the RAILS ±15V box, in its free bottom-left corner next to the LT3097 it indicates (0402 resistors, SOT-323 FETs and one BAT54AW keep it small; its parts are placed last, and the box's own passives and debug LEDs are frozen at their previous positions in `PLACEMENT`, so adding it moved nothing else), Q9 beside the REM FETs. The LT3097's same-net 0.5 mm-pitch pads are joined by 0.2 mm `PAD_BRIDGES` stubs and its GND pad vias are pre-placed. DRC: 0 unconnected, 0 schematic-parity issues, no copper violations (remaining: the old TP24 / U1 courtyard overlap, silkscreen warnings, one dangling 0.2 mm stub). Gerbers, the JLCPCB zip, renders, BOM and CPL were regenerated. **Not checked:** pad 24 (INN, -16.5 V) clearance to ground copper beyond what DRC covers, and the 22 µF / 50 V parts' real capacitance at 15 V.
* **Other open items:** LT3097 availability and price, and the 1 µF / 50 V part number, are unchecked. Bench: rails read about ±14.7 V, PG rises only after both are good, pulling JP2 drops it and REM cannot be switched on.

## Rev 2: bench fixes, LT8582, display, UCS 125-87 board (2026-11-02)

Driven by the rev 1 bench results in `hardware/TODO.md`.

* **R35 (sine gain stage):** 51k → 22k ∥ 1 nF C0G (the bench fix): gain 7.67, about 2.3 V pk at Vctl = 10 V, pole near 7 kHz. The sim project mirrors it.
* **J3 / J4 (2026-11-03):** right-angle 2.54 mm 3+1 PC fan headers replace JST XH, so standard fan plugs fit. Same pinout (GND, +12V, TACH, PWM). No maker drawing or current rating exists for the part; dimensions come from a CAD model.
* **J5 (2026-11-03):** Wurth 61900311021, right-angle 3-pin locking header, 3 A, replaces JST XH (datasheet rev 002.000).
* **J6 / J7 / J13 (2026-11-03):** Sullins SWR25X-NRTC-S02-RB-BA, right-angle 2-pin, 3 A, replaces the Adafruit 1769 JST PH. Cables need SWH25X housings.
* **R35 (superseded 2026-11-03):** feedback is now R35 47k + R92 2.4k in series (49.4k), with the 1 nF across both: gain 15.97, pole near 3.2 kHz. Bench: 51k gave 10.3 Vpp at Vctl = 10 V, so 49.4k should give about 10.0 Vpp (scaled, not yet measured). Swap R92 to trim.
* **LT8582 replaces the ADP5071** (datasheet `dev/8582f.pdf`, the p.30 "5V to ±12V" circuit at 1.5 MHz, RT 53.6k). VIN1/2 and SHDN1/2 tie to `+5V_PS15` (as on p.32), SYNC1 grounded, CLKOUT1 → SYNC2, GATE1/2 unused (no output-disconnect PMOS). RFBX1 = (16.4 − 1.204) / 83.3 µA = 182k, RFBX2 = (16.5 + 0.007) / 83.3 µA = 198k. Boost L 4.7 µH (XAL6060-472, L_MIN about 2.8 µH at duty 0.72). Inverting: the datasheet's subharmonic limit at duty ≈ 0.80 is L ≥ 5.6 µH (L_MAX about 14 µH), so the coupled inductor is a 10 µH **MSD7342-103** (windings 1-3 / 2-4, dots at VIN and VOUT as in the datasheet), C1 2.2 µF / 50 V (sees VIN + |VOUT|), DFLS240 clamp with its anode on node X. **Not verified:** the VC compensation (datasheet ±12 V values) at ±16.5 V; check both loops' transient response on the bench.
* **Power-good flags:** LT8582 PG1 / PG2 (open drain, 0.5 mA max) pull 20k / 39k nodes from `+5V_PS15` (0.25 mA sink, 3.3 V when good, 0 V when unpowered). The four flags (LT3097 PGP / PGN, LT8582 PG1 / PG2) go to SC18IS604 GPIO1-4 (GPIO4 is input-only; all GPIOs power up as inputs, datasheet Table 4/5). The bridge runs from `+3V3_COOL`, so with JP4 removed the flags cannot be read. The `PG_15V` interlock and `PG_15V_N` on GPIO43 are unchanged.
* **Display:** Phoenix DCT T 2,4 QVGA S RTOUCH (datasheet 109921): ST7789V, 4-wire SPI half duplex, VCC 2.6-3.3 V (3.6 V abs max), FH12-14S-0.5SH, pins 1-4 raw resistive touch (YU, XL, YD, XR). The backlight is 4 parallel LEDs at 3.0 V / 60 mA: +5 V through 39 Ω (0805), low-side BSS138 switched by bridge GPIO0 with a 100k pull-down (off until the firmware enables it). Touch: TSC2046E (TI SBAS417B) on the shared bus; DOUT and BUSY are high-Z with CS high, internal VREF needs no bypass, VBAT / AUX grounded. GPIO45 (touch CS) and GPIO46 (display RESET) are strapping pins: 10k pull-downs keep their default levels. **Open:** whether pin 1 of the display's FFC lands on pin 1 here depends on the cable's contact sides (same-side vs opposite); check against the cable before ordering.
* **J14 RJ45:** the three jacks listed in the TODO are all MagJacks (integrated LAN transformers), which would block the DC power and SPI to the IMU. Replaced by the plain shielded SMT Amphenol **RJSSE-5380** (drawing P-RJSSE-5380 rev E, footprint generated by `tools/make_footprints.py`). T568B pairs: 1-2 SCK / GND, 3-6 MOSI / MISO, 4-5 +3V3 / CS, 7-8 INT1 / INT2; shield to GND. The far end needs a matching RJ45-to-breakout adapter.
* **J11 / J12:** 3-way MKDS 1,5/3-5,08; pin 3 of each is a protective earth passed straight through (`EARTH`, 1.5 mm net class), nothing else on the board touches it. J8 / J9 (amp REM and signal) became 3.5 mm Phoenix PT 1,5/2-3,5-H.
* **Jumpers / LEDs / passives:** JP1-JP5 are Keystone 5110 "true zero ohm" 0603 jumpers on standard 0603 pads (catalog p.60). Single-colour LEDs are 0402 at about 1 mA (1.5k on 3.3 V, 3.3k on 5 V, 13k on 15 V; green for good, red for faults); the 5 V (yellow) and ±15 V (white) indicators are now green. Resistors default to 0402 (the CL25 LED resistors keep 0603, see the standby-LED open item), caps ≤ 100 nF are 0402 50 V, 1 µF 0603.
* **Test points:** labelled with their net names on the silkscreen; new ones on DDS_SINE (raw AD9833 output). IMU INT1/2, ESP_EN and ESP_BOOT test points were dropped for space (the last two are reachable on the RESET / BOOT buttons). The SCK, MOSI, MISO, A_MISO, chip-select (TP18-TP28) and SCL (TP31) test points were removed on 2026-11-03; those numbers stay unused and SDA (TP30) stays.
* **J11 / J12 / J8 (2026-11-04):** TE 2305908-2 and 2305908-3 (SMT, drawing C-2305908 rev A1) and Phoenix 1821698 (MC 0,5/2-G-2,54 SMD, drawing 00783144 rev 02). The SMT joints take the plugging force; J11 and J12 have no pegs. 3D: maker STEP files for all three.
* **MCP23S08 board (2026-11-04):** U30 / U31 SN74LV1T34 (VIH 1.36 V at 3.3 V) lift the 1.8 V GPIO47/48 for the display. L1 SRP6050CA-4R7M, L2 SRP7050TA-4R7M, L3 MSD7342-103 kept; the SRP powder cores need a bench check at 1.5 MHz. See `hardware/archive/HANDOFF_145.md`.

## Smaller analog packages (2026-11-05)

Three SOIC-8 parts move to smaller packages at the same board centres, front side.

* **U5:** OPA1656ID (dual, unit B spare) → OPA1655DBVR, the single version, SOT-23-5 (TI SBOS901C). Pins 1 OUT, 2 V-, 3 +IN, 4 -IN, 5 V+. The SPICE project still uses TI's OPA1656 model.
* **U9:** OPA188AID → OPA188AIDBVR, SOT-23-5. Pins 1 OUT, 2 V-, 3 +IN, 4 -IN, 5 V+. It is ordered from Digi-Key, so it leaves the Mouser list; check live stock.
* **U7:** MCP4921-E/SN → MCP4921-E/MC, 3x2 mm DFN-8. Footprint checked against Microchip land pattern C04-2123A. The exposed pad (pin 9) ties to GND with a via (DS22248 3.8). VOUT and VSS keep their pin numbers.
* **Board:** `tools/small_packages_board.py` swaps the parts and rips their nets. New routing, plus three new GND stitching vias around U5 and U9. Three short segments near these parts sit about 1-2° off 45° (AD9833_FSYNC, +15V, -15V).

## U32 in VQFN (2026-11-05)

* **U32:** SN74LVC138APWR (TSSOP-16) → SN74LVC138ARGYR (RGY VQFN-16, 3.5x4 mm), same centre and rotation. Pins 1-16 keep their functions (TI SCAS291). KiCad's stock RGY footprint covers TI's RGY0016A land pattern: EP 2.05x2.55, pads extend 0.2 mm further out.
* **Exposed pad:** tied to GND with one 0.2 mm drill via. TI requires it soldered but this datasheet doesn't name a net; G2B (pin 5) and GND (pin 8) join it on F.Cu.
* **Silk:** the `138` part name is gone, because the exposed pad leaves no room for it.
* **Board:** `tools/u32_rgy_board.py`. The chip-select nets total 50 vias and 514 mm, was 49 and 510. C39 is 4.4 mm from pin 16, was 3.1.

## U27 in VQFN (2026-11-05)

* **U27:** TSC2046EIPWR (TSSOP-16) → TSC2046EIRGVT (RGV VQFN-16, 4x4 mm, 250-piece reel), same centre, back side. Both are TI Last Time Buy. Pins renumbered from TI SBAS417 (5 +VCC, 6 X+, 7 Y+, 8 X-, 9 Y-, 10 GND, 11 VBAT, 12 AUX, 13 VREF, 14 IOVDD, 15 PENIRQ, 16 DOUT, 1 BUSY, 2 DIN, 3 CS, 4 DCLK, 17 exposed pad).
* **ESD:** the part rates X+, X-, Y+ and Y- to ±15 kV IEC contact, so no TVS is added. TSC2046IRGVR is the active fallback: same pins and footprint, but no IEC rating.
* **Exposed pad:** tied to GND with one via, joined to pins 10-12 on B.Cu. TI says analog ground or floating, kept off digital ground if possible; this board has one GND.
* **Footprint:** stock Texas_RGV0016A covers TI's RGV0016A land pattern (drawing in the INA3221 datasheet; the TSC2046E sheet only shows the outline). EP 2.1 vs (2.16), pads extend further out.
* **Decoupling:** C36 (100 nF) moves to (52.7, 11.6) with `tools/c122_move.py`, 3.2 mm from pin 14 and 7.1 mm from pin 5, was 9.1 and 8.2. C47's reference is hidden because there is no room for it.
* **Board:** `tools/u27_rgv_board.py`. Pads 2, 3, 7 and 15 are via-in-pad. Rotation stays 0, so SPI moves to the west side and the panel lines to the north, and SPI_SCK / SPI_MOSI gain 4 and 2 vias.

## TL6800AF260QJ power button (2026-11-05)

* **SW3:** TL3342F160QG → E-Switch TL6800AF260QJ. SPST, 50 mA / 12 VDC (same rating), 260 gf, 500,000 cycles, IP67, 3.1 mm high.
* **Land pattern:** datasheet Recommended PCB Layout, 9.5 x 5.4 mm overall with a 4.0 x 2.6 mm inner gap, so four 2.75 x 1.4 mm pads at (±3.375, ±2.0). The footprint is our own, `SW_E-Switch_TL6800AF`.
* **Pins:** the datasheet joins 1-2 and 3-4. As on the stock TL3342 footprint, pads "1" are pins 1 and 2 and pads "2" are pins 3 and 4, to match `Switch:SW_Push`.
* **Circuit:** unchanged, contact from LTC2954 PB and J7 pin 1 to GND.

## PTS810SJM250SMTR LFS reset and boot buttons (2026-11-05)

* **SW1, SW2:** TL3342F160QG → C&K PTS810SJM250SMTR LFS (Littelfuse datasheet rev 02/02/26). SPST NO, 50 mA / 16 VDC, ≤ 500 mΩ, 1.6 N ± 0.5, 150,000 cycles, grey actuator, 2.5 mm high, listed as available for ordering.
* **Land pattern:** datasheet Recommended PCB Layout, 5.2 x 2.8 mm overall with a 3.1 x 1.5 mm inner gap, so four 1.05 x 0.65 mm pads at (±2.075, ±1.075). The footprint is our own, `SW_CK_PTS810`.
* **Pins:** the datasheet joins 1-2 and 3-4. Pads "1" are pins 1 and 2, pads "2" are pins 3 and 4, as on SW3.
* **Circuit:** unchanged, contact from ESP_EN (SW1) or ESP_BOOT (SW2) to GND.

## EVQ-P2F02K reset and boot buttons (2026-11-06)

* **SW1, SW2:** C&K PTS810SJM250SMTR LFS → Panasonic EVQ-P2F02K (catalog ANCTB19E 202507, `dev/sw_lt_eng_4735s.pdf`, printed p.3). 4.7 x 3.5 mm body, 5.5 mm across the terminals, 2.5 mm high. 5.0 N, black plate, 200,000 cycles. Rated 10 µA at 2 V to 20 mA at 15 V DC resistive, bounce 10 ms max.
* **Force:** 5.0 N is about three times the PTS810's 1.6 N. It's the user's choice.
* **Rating:** pressing a button discharges C42 (1 µF) or C14 (100 nF) through the contact, which goes over 20 mA for a moment. The rating is for resistive loads. Not tested.
* **Land pattern:** the catalog's reference pattern, 6.6 mm overall with a 3.7 mm inner gap and 2.7 mm overall with a 0.7 mm gap, so four 1.0 x 1.45 mm pads at (±0.85, ±2.575). GND land 0.65 x 1.4 mm, 1.7 to 2.35 mm from centre.
* **Pins:** the catalog joins 1-3 and 2-4, so pads "1" are the left column and pads "2" the right. The GND land is pad "2" as well, which only works because pin 2 is GND on both switches. The ground terminal isn't plated, so solder won't wet it; the catalog recommends connecting the land to GND for ESD. Each land has a 0.45 mm via to In1.
* **Circuit:** unchanged, contact from ESP_EN (SW1) or ESP_BOOT (SW2) to GND.
* **Model:** `dev/EVQ-P2F02K.step` is the series file. In it the terminals are at ±0.85 mm, as the catalog draws them. Position measured from a GLB export: x 63.75-69.25, y 8.675-12.175, height 0-2.5 for SW1.
* **Datasheet link:** no Panasonic PDF URL could be confirmed, so the part's Datasheet field points at the Mouser listing.

## WS2812B-2020 status LED (2026-11-06)

* **D13:** Adafruit 1655 (5050) → Adafruit 4684, a WS2812B-2020 (WorldSemi V1.3, `dev/WS2812B-2020_V1.3_EN.pdf`). 2.2 x 2.0 x 0.84 mm. The QBLP1515AB-RGB2A was considered first and dropped: it has no driver, so it needs three control lines.
* **Supply:** VDD 3.7 to 5.3 V, on `+5V`. Note the lower 5.3 V limit. 12 mA per channel.
* **Pins:** 1 DO, 2 GND, 3 DI, 4 VDD, a different order from the 5050. KiCad's `LED:WS2812B-2020` symbol and `LED_WS2812B-2020_PLCC4_2.0x2.0mm` footprint match it.
* **Land pattern:** datasheet p.2, 0.7 x 0.7 mm pads with a 1.13 mm gap across and 0.4 mm between rows. KiCad's footprint has the same pads, turned 180° from the datasheet drawing, with pin 1 at the silk chamfer.
* **Circuit:** unchanged. U24 and the 330 Ω stay. The datasheet gives VIH 2.7 V, so the shifter may no longer be strictly needed, but its input rating (VDD - 0.3 to VDD + 0.7 V) reads oddly, so it stays.
* **Firmware:** this part needs T0H 220-380 ns and T1H, T0L and T1L 580-1000 ns. `neopixelWrite()` sends T0H and T1L of 400 ns, outside both limits, so `indicator.cpp` now sends 300/800 ns and 800/600 ns. It also needs 280 µs of low to latch, and the loop was writing every pass, so frames now go out only on a colour change. Not tested on the part.
* **Model:** seated by GLB measurement at x 67-69, y 33.9-36.1, height 0-0.86. The green bar sits beside pads 1 and 2, as the datasheet's back view shows its polarity mark.

## Rev 3: parts, protection and simplification (2026-11-06)

The PCB is rev 3 as well. Status, PCB notes and bench list are in `../HANDOFF_rev3.md`. Rules for each changed part are in `tools/datasheet_rules.py`.

**Read from the maker's datasheet:** ADP5071, AD5453, LTC2954, TPS2116, TPS62822, ISOW774x, ADS1220, AONR21307, SRP4020TA, ECS-2520MV, TPD4E05U06 / TPD1E05U06, BZT52C15, MMBZ family, TSC2046E, ACS37800, NUF6401MN.

**Not verified from a maker's datasheet:**
* BLM18PG121SN1D and EEE-FK1V101P: secondary sources only.
* BLM15EX331SN1D: named by TI's ISOW7741 datasheet, Murata's own sheet was not read.
* AD9833: the fetch failed twice, so the 100 nF on CAP/2.5V stands from memory.
* TPS62822 footprint: KiCad's stock pads are 0.8 x 0.25 mm, the datasheet shows 0.6 x 0.25 mm. Check this at layout.

**Findings that changed the design:**
* **AD5453 VREF and RFB are limited to ±12 V**, and U5 and U9 run from ±14.7 V. D16 (MMBZ9V1ALT1G, back to back) clamps VREF: 9.66 V peak in simulation with the input well above normal. RFB only exceeds ±12 V if the feedback loop is broken.
* **AD5453 gain:** U5 is 1 + 50.6k/3.3k = 16.33, and R39 (220 Ω) against the 7-11 kΩ VREF input loses about 2.4 %. Simulated 9.96 Vpp at full code, 0 V at code 0, and linear between them. The VREF tolerance means this needs a bench calibration.
* **AD5453 interface:** C1,C0 = 11 changes the data clock edge, so firmware never sends it. It powers up at zero scale.
* **Q1 gate:** a gate-drain capacitor alone (C80) would couple hot-plug edges into the gate and turn Q1 on. C84 (470 nF gate-source) was added beyond the plan to hold it off. R20 and D17 (15 V) keep the gate inside the ±25 V limit.
* **Q1 part:** AONR21307 replaces AONR21305C, which you could not buy. Same -30 V rating and same pinout. 11 mΩ max at -10 V instead of 6.5 mΩ, about 0.38 W at 5 A hot instead of about 0.25 W, and 28 W instead of 42 W at 25 °C case. Turn-on estimate with about 154 µF on +12V: about 2.8 A for about 0.7 ms, about 34 W peak, against about 70 W for 1 ms in its Fig. 10. Its datasheet names the package DFN 3x3 EP, the same as the AONR21305C, but has no outline drawing. The footprint is still the AOS DFN3x3A_8L_EP1 pattern, so check it against the part in hand or a drawing from AOS.
* **LTC2954 INT# can pulse for only 32 ms**, so firmware uses an interrupt rather than polling. C41 = 1 µF gives 6.4 s forced off, and the firmware's 5 s limit stays under that.
* **LTC2954-2 DFN pinout differs from TSOT-23** (VIN is pin 4, not pin 1).
* **TSC2046E PENIRQ** has an internal pull-up (nominal 50 kΩ), so GP7 needs no pull-up. It is disabled during a conversion, and the last control byte needs PD0 = 0.
* **ACS37800-015B5:** ±15 A, 1833.3 LSB/A, 6.15 LSB/mW at 5 V, voltage 110 LSB/mV. **The amplifier current range halves from ±30 A.** `AMPLIFIER_MAX_CURRENT_A` is 5 A.
* **ISOW7741:** 5 V to 5 V gives 110 mA at most, and FB1 and FB2 follow TI's EMI layout.

**J14 filter replaces R52-R57 and the two clamps:** `NUF6401MNT1G` (onsemi NUF6401/D rev 5, active) puts a 100 Ω series resistor (85-115 Ω), 17 pF (20 pF max) and an ESD clamp on each side of six channels in a 3.0 x 1.35 mm DFN12. U36 carries all six J14 signals; it replaced two NUF4001MU (U36, U37, two channels spare), so U37 is retired.
* Compared with the TPD4E05U06 it replaces: ±15 kV IEC contact instead of ±12 kV, and 5 V working voltage instead of 5.5 V, which is fine on 3.3 V signals.
* It adds 34 pF per line (40 pF max). The 110 MHz cut-off is far above the 1 MHz IMU SPI clock.
* 100 mW per resistor, 600 mW per package: logic signals only.
* The operating range is -40 to 105 °C.
* `OnSemi_DFN-12-1EP_506AD` is drawn from the case 506AD soldering footprint (0.479 x 0.265 mm pads, 0.5 mm pitch, 2.352 x 0.351 mm ground pad). Its 3D model is a plain 3.0 x 1.35 x 1.0 mm envelope. **At layout:** the 0.351 mm ground pad can't hold a 0.45 mm via, so route it out from its ends.
* EMI5204MU was also considered (7 pF, ±8 kV), but onsemi marks EMI5204MUTAG and EMI5206MUTAG discontinued as of June 2025.

**Decisions to review:**
* **R44** (100 kΩ USB VBUS bleed) was removed in addition to the plan's list. It was only needed for the old LM66100 CE pin, which the TPS2116 replaces.
* **Tach clamps (U33) sit on the GPIO side of the 4.7 kΩ resistors**, because J3-J5 have 12 V next to the tach pin. At layout, put the resistor at the connector and the clamp straight after it.
* **Back-feed:** the decoder's Y outputs drive high from power-on. U3 and U4 now share `+3V3_SG` with the AD5453. The note under "SN74LVC138A chip-select decoder" still applies, with AD5453 in place of MCP4921.
* **+3V3 now comes from a buck** (U16) rather than an LDO. FB3 isolates `+3V3_CH` from it, and the AD9833 noise needs checking on the bench.
* **The AD5453 replaces a calibrated chain with an unproven one.** The old chain's bench values do not carry over.

**J11 / J12 stay SMT:** rev 3 briefly moved them to through-hole Phoenix MSTBA headers. They are back on TE 2305908-2 / -3 (15 A) at their rev 2 positions, by your decision, so the 2026-11-04 notes above still apply: the SMT joints take the plugging force, with no pegs. One listing shows -3 as Last Time Buy, another as in production, and no TE notice was found, so confirm stock when ordering.

**Superseded:** the MCP4921, AD633, LM4040 reference, LT8582, MIE1W0505, ISO7741, LD1117, LM66100 pair, IRF4905S, SG-8002CA and CL25N8 notes above describe rev 2 and earlier.

## UCS 125-87 board: smaller buttons and bi-colour LEDs (2026-11-08)

**SW1, SW2:** Panasonic EVQ-P2F02K → EVP-AA802Q (catalog ANCTB18E, No. 1, your pick). 3.5 x 2.9 x 1.7 mm with J-bent leads, against 4.7 x 3.5 x 2.5 mm. Same 5.0 N force and 20 mA / 15 V DC rating; grey actuator; life 100,000 cycles instead of 200,000. No ground terminal.
* Land pattern: four 1.15 x 0.4 mm pads, 4.5 mm overall with a 2.2 mm gap, rows 2.5 mm overall. Pads 1-1′ (one row) and 2-2′ (the other) are common, so each row is one pin. Footprint `SW_Panasonic_EVP-AA`.
* 3D model: a plain 3.5 x 2.9 x 1.4 mm body with a 2.2 x 1.5 x 1.7 mm actuator (`EVP-AA_envelope.step`).

**Indicators:** every LED but D13 is now a Kingbright APGB0607G22R23C (datasheet rev V.3A): green and red dies in a 0.65 x 0.65 x 0.25 mm package with four 0.25 mm pads. The dies are independent: 1 green anode, 2 green cathode, 3 red cathode, 4 red anode.
* Ratings: green VF 2.85 V typ / 3.3 V max, red 1.95 V / 2.3 V max at 5 mA; 10 mA DC max per die; VR 5 V; 35 mW. MSL 3. Every die here runs at about 0.5-2 mA.
* **The green die can't run from +3V3** (VF up to 3.3 V), so every green die is fed from +5V.

| LED | Green | Red |
|---|---|---|
| D7 STATUS (was D7 standby + D8 3V3 + D9 5V) | on: 2.2k from +5V, ~1 mA | standby: 13k from VIN, shorted once +3V3 is up. Both lit = +5V up but +3V3 missing |
| D2 AMP, D3 COMP | output on: +12 V bus → green → 2.2k → +5V, ~1.9 mA | output off: +5V → 2.2k → red → bus → 4.7k pull-down, ~0.45 mA |
| D11 PG +15V, D12 PG −15V | node good: the existing BSS138W pulls GK low | node bad: a second BSS138W (Q51, Q52), gated by the first one's drain with 100k to +3V3, pulls RK low; 1.5k from +3V3 |
| D6 ALERT | unused | INA239 ALERT low, 1.5k from +3V3 (as before) |
| D10 ISO 5V | ISO_5V, 3.3k to ISO_GND (as before) | unused |

* D2/D3 dies are anti-parallel, so each one's reverse voltage is the other's VF (under 3.3 V, inside the 5 V VR).
* Off, the AMP and COMP buses still sit at about 2.1 V through the red die and the 4.7k pull-down, as with the old 1206 part.
* When the ±15 V rails are switched off, D11 and D12 show red.
* Retired: D8, D9 and their resistors. New: R401-R405, Q51, Q52 (numbered above every other range so nothing else shifts).
* Footprint `LED_Kingbright_APGB0607` (the datasheet pattern, 0.15 mm pad gaps, matching the board's 0.15 mm clearance). 3D model: a 0.65 x 0.65 x 0.25 mm envelope.
* **Sourcing:** DigiKey 22561020. JLCPCB stock not checked; it may need to be supplied for assembly.
* **Labels:** the LEDs are the only labelled parts on this board: a column on the front (STATE, PWR, +15V, −15V, AMP, COMP, ALERT) and ISO 5V beside D10 in the isolated island.

## AD9837 in place of the AD9833 (2026-11-08)

**U4:** AD9833BRMZ (MSOP-10, 3 x 4.9 mm with leads) → AD9837BCPZ-RL7 (ADI AD9837 rev A, LFCSP-WD-10 CP-10-9, 3 x 3 mm), your pick. The datasheet says it "has the same register settings as the AD9833/AD9834", and the pin numbers match: 1 COMP, 2 VDD, 3 CAP/2.5V, 4 DGND, 5 MCLK, 6 SDATA, 7 SCLK, 8 FSYNC, 9 AGND, 10 VOUT.
* **Exposed pad to ground** (Figure 4). The project symbol `AD9837BCPZ` is KiCad's AD9833 symbol with pin 11 (EP) added; it carries the locked via-in-pad that pins 4 and 9 had.
* **MCLK is 16 MHz max (B grade), against the AD9833's 25 MHz.** U3 is now ECS-2520MV-160-BN-TR: same family, footprint and pinout as the 25 MHz part, 1.6-3.6 V. The A grade is 5 MHz, so order the B grade.
* **Firmware:** MD_AD9833 assumes 25 MHz, so `initWaveform()` calls `setClk(AMPLIFIER_DDS_MCLK_HZ)` (16e6) after `begin()`. Without it the sine would come out at 60 x 16/25 = 38.4 Hz. 28-bit resolution at 16 MHz is 0.06 Hz.
* **Output:** VOUT 37 mV to 0.645 V, the same ~0.6 V p-p sine into the OPA1655 gain stage, so the 16.3 gain and the ~10 Vpp at full code stand. SNR -64 dB, THD -68 dBc at fMCLK/4096 (B grade).
* VDD 2.3-5.5 V, -40 to 125 °C. Footprint `Package_CSP:LFCSP-WD-10-1EP_3x3mm_P0.5mm_EP1.64x2.38mm` (drawn from CP-10-9) with KiCad's STEP model.
* **Sourcing:** DigiKey 2700194; JLCPCB stock not checked.

## SP3422-04UTG ESD clamps (2026-11-08)

**U33, U35:** TPD4E05U06DQAR (USON-10, 2.5 x 1.0 mm) → Littelfuse SP3422-04UTG (rev GD, DFN-5, 1.0 x 0.6 mm), your pick. U33 clamps FAN_TACH, PUMP_TACH, FLOW_TACH and NTC_ADC on the GPIO side of the 4.7 kΩ tach resistors; U35 clamps the four J10 PT1000 lines.
* **Pins:** I/O 1, 3, 4, 5 to GND 2; no supply pin, no NC pins. Land pattern: 0.34 x 0.175 mm pads, 0.35 mm pitch (the datasheet's soldering pad layout, the same as Littelfuse's DFN_04UTG_LTF). STEP model is Littelfuse's.
* **Ratings:** 5 V working voltage (the lines stay under 3.3 V), 0.2 pF, +22/-10 kV IEC contact, 2 A 8/20 µs.
* **Leakage is the one step back:** 20 nA typical, 1 µA max at 5 V, against the TPD4E05U06's 10 nA max at 2.5 V. On the RTD only the RTD-to-Rref line matters (about 1 V at 250 µA); the typical figure is about 0.01 % (0.02 K). The 1 µA bound would be 0.4 %, but it is set at 5 V, not 1 V. On NTC_ADC (10 kΩ divider) 1 µA is at most 10 mV.
* **Semtech RClamp7524T (considered):** 5 A and ±25 kV contact, and 100 nA max leakage at 5 V, in a 1.3 x 0.8 mm flow-through package. These lines only see ESD, so the extra current rating isn't needed; switch to it if the RTD leakage bound matters more than the size.
* **Sourcing:** DigiKey 7897437, LCSC C1974549.

## 74AHCT1G125GM level shifter (2026-11-08)

**U24:** SN74AHCT1G125DBVR (SOT-23-5) → Nexperia 74AHCT1G125GM,115 (rev 15.1, XSON6 SOT886, 1.0 x 1.45 mm), your pick. Same function: 3.3 V GPIO38 to 5 V for the WS2812B data line.
* **Pins differ from the SOT-23-5:** 1 OE, 2 A, 3 GND, 4 Y, 5 n.c., 6 VCC. OE and GND to ground, VCC +5V, pin 5 left open.
* **Levels:** TTL inputs, VIH 2.0 V at VCC 4.5-5.5 V, so a 3.3 V input drives it. The CMOS output swings to the 5 V rail into the WS2812B's high-impedance input (0.7 x VDD = 3.5 V).
* **Footprint:** Nexperia's SOT886 reflow footprint (package information, 1 June 2022): 0.40 x 0.30 mm lands, 0.60 mm column pitch, 0.5 mm row pitch. 3D model: KiCad's 1 x 1.45 mm USON-6 STEP (same body, 0.63 mm tall against 0.5 mm).
* **Sourcing:** DigiKey 2606148.

## 74LV1T34GX display buffer (2026-11-08)

**U31:** TI SN74LV1T34DBVR (SOT-23-5) → Nexperia 74LV1T34GXH (74LV1T34 rev 4, X2SON5 SOT1226-3, 0.8 x 0.8 mm). You asked about the 74AUP1G34GX4Z, but at VCC 3.0-3.6 V it needs VIH 2.0 V and GPIO47/48 only reach 1.8 V. The 74AXP1T34 and 74AUP1T34 need a 1.8 V supply the board doesn't have, and TI's SN74LV1T34 comes only in SOT-23-5 and SC70.
* **Same function as the TI part:** single-supply translator, VIH 1.37 V at VCC 3.0-3.3 V (-40 to 125 °C), inputs to 5.5 V, same pin numbers (1 n.c., 2 A, 3 GND, 4 Y, 5 VCC).
* **Footprint:** Nexperia's SOT1226-3 reflow footprint: 0.32 x 0.26 mm corner lands on a 0.64 x 0.5 mm grid and a 0.28 mm square GND land turned 45° in the centre; corner lands are cut 0.16 mm from it.
* **Land orientation:** the sot1226-3_fr drawing is turned 90° from the datasheet's pin configuration (Fig. 5). In Fig. 5's top view the terminals sit on the left and right body edges (1 and 2 on the left, 5 and 4 on the right), so the lands run out past those edges. The first version of this footprint had them past the top and bottom edges, about 0.07 mm off each terminal. That was caught against the package outline and the vendor model before routing, and fixed.
* **Pin 1 is grounded.** The centre GND land is boxed in by the four corner lands, so no 0.15 mm track or 0.45 mm via fits. A 0.15 mm copper bridge (a second pad 3, copper only, under the solder mask) joins it to pad 1, which is not connected inside the part. Bridge-to-pin-2/5 clearance is 0.2 mm or more.
* **3D model:** `SOT1226-3.step` (SamacSys model of the 74LV1T34GXH, your file), 0.38 mm tall, placed by its terminals with the notched pin 1 terminal on pad 1. Its top dot is at the corner opposite pin 1, which is an error in the model; the silkscreen dot marks pin 1.
* **Sourcing:** Nexperia orderable part 74LV1T34GXH; DigiKey and JLCPCB stock not checked.

## SRL05P7 USB ESD clamp (2026-11-08)

**U2:** ST USBLC6-2SC6 (SOT-23-6) → MCC SRL05P7-TP (DFN1510-6, 1.5 x 1.0 x 0.55 mm, 0.5 mm pitch), your pick for a leadless package.
* **Same pin functions** (MCC rev 3-5): 1, 3, 4, 6 data lines, 5 VBUS, 2 GND, with 1-6 and 3-4 joined inside, so the pass-through wiring stays (connector on 1/3, ESP32 on 6/4). It reuses the stock USBLC6 symbol.
* **Ratings:** 5 V working, breakdown 6.1-9.6 V, leakage 0.9 uA max at 5.25 V, clamp 12 V at 1 A and 17 V at 5 A (8/20 us), 0.6 pF typ / 1 pF max line to GND, ±15 kV contact / ±20 kV air.
* **Footprint:** MCC's suggested pads, 0.20 x 0.35 mm, rows 0.65 mm apart; pin 1 bottom left as in the datasheet's top view.
* **3D model:** a 1.5 x 1.0 x 0.55 mm STEP block (no vendor model).
* **Sourcing:** JLCPCB C3713451 (extended); DigiKey 12177202. Stock not checked.

## OPA2991 dual for U5 and U9 (2026-11-08)

**U5:** TI OPA1655DBVR (U5) and OPA188AIDBVR (U9), both SOT-23-5 → one TI OPA2991IDSGR (WSON-8 DSG, 2 x 2 mm), your call to save board space. U9 is retired; its two 100 nF decoupling caps went with it. This replaces your 2026-11-05 OPA1655 choice for the gain stage.
* **Pinout** (TI SBOS969, DSG): A 1 OUT, 2 -IN, 3 +IN; B 5 +IN, 6 -IN, 7 OUT; 4 V-, 8 V+, thermal pad 9 to V- (datasheet note). The symbol is a copy of KiCad's TLV9062xDSG, which has the same pinout.
* **U5A** is the DDS gain stage (gain 16.3, as before); **U5B** is the AD5453 output stage.
* **Ratings:** 2.7-40 V supply (here ±14.7 V), 4.5 MHz GBW, 21 V/us, 10 pA bias, 750 uV max offset, rail-to-rail in and out. Offset and bias are DC, and the output is AC-coupled (100 ohm + 10 uF), so they don't reach SIG_SINE. It is noisier than the audio-grade OPA1655; at about 10 Vpp that isn't expected to matter, but it wasn't quantified.
* **C86 (datasheet C1): 2 pF → 22 pF C0G.** With the 9k RFB and 13-28 pF on IOUT1 (plus about 10 pF op-amp input), a two-pole op-amp model in ngspice peaks 5.7-7.6 dB at 2 pF and is flat at 22 pF; 22 pF puts the feedback pole at about 800 kHz, far above 60 Hz. (The OPA188 also peaked 3.8-5.6 dB with 2 pF in the same model.) Not yet checked with TI's OPA2991 SPICE model; `sim/` still models the OPA1656 / OPA188.
* **Footprint:** generated from the datasheet's DSG land pattern (0.5 x 0.25 mm pads on 1.9 mm row centres, 0.9 x 1.6 mm pad); KiCad's stock DSG0008A footprint has 0.6 mm pads. 3D model: KiCad's WSON-8 2 x 2 mm STEP.
* **Sourcing:** stock and price not checked.

## Micro-Lock Plus J14 in place of the RJ45 (2026-11-08)

**J14:** Amphenol RJSSE-5380 SMT RJ45 → Molex Micro-Lock Plus **505448-0891** (1.25 mm, 2x4, right angle, SMT, positive lock), your call to free space on the UCS 125-87 board. It takes 10.2 x 10.2 mm of the right edge instead of 19.4 x 17.6 mm.
* **Drawing** 5054480003-SD rev C1 (`dev/5054480891_sd.pdf`; the layout was measured from Molex's 1:1 DXF): pads 0.8 x 2.0 mm at 1.25 mm, rows 7.4 mm apart (odd pins on the back row, even pins at the mating face); solder nails 1.0 x 4.85 mm, 8.15 mm apart, unconnected. Body 9.6 wide, 8.43 deep plus 0.42 mm tails, 8.95 mm high. Rated 1.5 A, 50 V, 30 mating cycles.
* **Pins** keep the RJ45 numbering (1 SCK, 2 GND, 3 MOSI, 4 +3V3, 5 CS, 6 MISO, 7 INT1, 8 INT2), so the schematic, the U36 filter and the rules carry over; the shield pin is gone. The cable no longer has twisted pairs, so keep it short.
* **Placement:** face 0.2 mm inside the right edge (mating-side pads 0.3 mm clear). The plug sticks out past the board edge, so the housing wall needs a slot for it (about 10 x 9 mm), or a gland with the plug inside.
* **Mating parts:** a 505432 series 8-circuit dual-row receptacle housing and its crimp terminals (not in the BOM).
* **3D:** plain 9.6 x 8.43 x 8.95 mm envelope; Molex's STEP isn't in the repo.
* **Sourcing:** stock and price not checked.

## IMU board (2026-11-11)

**New board:** the Adafruit LSM6DSOX breakout (product 4438) → its own 18 x 18 mm, 2-layer board in `imu/`, your call. It keeps the demo board's sensor circuit without I2C, cabled to J14 through the same Molex 505448-0891 with the same pin map (cable wired pin for pin). Checked against ST DS12814 rev 3; the rules are `RULES_IMU` in `tools/datasheet_rules.py` (25, all pass).
* **Mode 1, 4-wire SPI** (Section 3.1, Table 1): CS 12, SPC 13, SDI 14, SDO 1. SDx (2) and SCx (3) to GND ("connect to VDDIO or GND"); OCS_Aux (10) and SDO_Aux (11) unconnected ("leave pin electrically unconnected and soldered", Table 1 note 2; internal pull-ups, Table 20). VDD 8 and VDDIO 5 on +3V3, GND 6 and 7.
* **Decoupling:** 100 nF at VDD (C1) and at VDDIO (C2), the "recommended 100 nF filter capacitor" (Table 1 note 1); 10 uF (C3) at J1 for the supply that arrives over the cable.
* **INT1 at power-up:** "INT1 must be set to '0' or left unconnected during power-on" when I2C/SPI is used (Table 20, note 2). J1 adds no pull-up. On the main board INT1 runs through U36 (NUF6401) to GPIO 2 with no resistor on either side (checked in the netlist), and the firmware sets GPIO 2 to `INPUT_PULLDOWN` (`imu.cpp`). The ESP32-S3's GPIO 2 state before the firmware runs was not checked. A rule (`nores`) keeps a pull-up off pin 4.
* **CS pull-up:** 10k (R1) keeps U1 deselected while the cable is hot-plugged, as on the earlier on-board design.
* **Dropped from the demo board:** the STEMMA I2C connectors and SCL/SDA pull-ups, the BSS138 level shifters, the AP2112K LDO, the CS diode and pull-up, the SDO address jumper and pull-down, and the pin headers. None is needed with 3.3 V supply and logic from the main board.
* **Footprint:** KiCad's stock `LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y`. Its pads (0.35 x 0.625 mm, 0.5 mm pitch) cover the 0.25 x 0.475 mm lands of Figure 28, and its pin order and pin 1 match Figure 4 (bottom view, mirrored). 3D model: the matching KiCad STEP.
* **Axes:** from Figure 4 (top view): on the board (U1 at 90°) +X points to the mounting hole, +Y to the left edge, +Z out of the top face. The front silk carries the glyph.
* **Layout:** no top-layer tracks or vias under U1, equal 0.2 mm stubs leaving each pad, top pour kept off its pads, and U1 kept clear of the screw head. **Unverified:** these follow ST's community summary of TN0018 ("How to optimize your PCB design for MEMS sensors"); TN0018 itself couldn't be downloaded.
* **Not on the board, firmware follow-up:** while CS is high the I2C block stays active and sees the shared SPI traffic on SCL/SDA. DS12814 Section 5.1.1 says to write `I2C_disable = 1` in CTRL4_C (13h). The firmware doesn't set it today (this applies to the breakout too).
* **Not checked:** no bench test; stock and price not checked; the mating cable is not in the BOM.

## Rev 4: shared-bus ACS37800, general-purpose I/O, new connectors (2026-11-12)

Branch `ucs-125-87-rev4`. Not built or bench tested.

**ACS37800 on the shared SPI bus (U41, U42):** frees GPIO 11, 12 and 13. The chip select stays on GPIO17, because all eight U32 decoder outputs are in use.
* **Datasheet (Allegro ACS37800, "Communication Interfaces"):** "The ACS37800 MISO pin continues to drive the MISO line when CS goes high", and it recommends being the only device on the bus. It says nothing about SCLK activity while CS is high. tCS 50 ns, tCHD 5 ns, 0.1-10 MHz.
* **U42** passes the isolator's MISO output (U17 pin 5) to `SPI_MISO` only while `ACS_CS` is low. It sits on the logic side because U17's output also drives all the time.
* **U41** passes `SPI_SCK` to U17 pin 3 only while `ACS_CS` is low, with 10 kΩ (R501) pulling its output high when closed: the mode-3 idle level. This was not in `TODO.md`; it is there because the datasheet doesn't promise that clocks are ignored with CS high, and the probe in `initAcs()` leaves register writes unlocked. MOSI goes straight to U17 pin 2; without clocks it does nothing.
* **Part:** TI SN74LVC1G125DRYR (SCES223, SON-6 DRY, 1.45 x 1.0 mm): 1 OE, 2 A, 3 GND, 4 Y, 5 n.c., 6 VCC; output off while OE is high; ten 5.3 ns and tdis 5 ns max at 3.3 V; 1.65-5.5 V. Footprint `Package_SON:Texas_USON-6_1x1.45mm_P0.5mm_SMD` (KiCad's DRY land pattern). The Nexperia 74LVC1G125GM named in `TODO.md` shares the pinout, but its datasheet could not be fetched, so the TI part was used.
* **R502** (10 kΩ) holds `ACS_CS` high while GPIO17 floats, so both gates start closed.
* **Not verified:** that the ACS37800 tolerates the gated clock edge timing through U17 on real hardware.

**General-purpose I/O (J16-J20):** GPIO 5, 7, 11, 12 and 13, each on a 2-pin header (pin 1 signal, pin 2 GND).
* Per pin: ESD clamp at the header, 100 Ω in series, and a 100 kΩ / 100 kΩ divider to GND whose tap feeds the LED driver. Clamps: one TPD1E05U06 per pin (U45-U49, a part already on the board), each beside its own header. A four-line SP3422 for IO5, IO7, IO11 and IO12 was tried first; on the board its pin order tied the four header nets into a knot between RN3 and the header pads.
* **ADC:** only GPIO5 and GPIO7 are ADC1. GPIO11-13 are ADC2, which the ESP32-S3 can't use while WiFi runs.
* **3.3 V only.** The 5 V clamps and 100 Ω do not make the pins 5 V tolerant.
* **The 200 kΩ to GND** holds an open pin low and loads a source: 0.1 % error for a 100 Ω source, 5 % for 10 kΩ.

**I/O LEDs (U43, U44, D81-D85):** one OPA4990 section per pin drives the green die of an APGB0607 with half the pin voltage across 3.3 kΩ, the LED inside the feedback loop: I = Vpin / 6.6 kΩ, 0.5 mA at 3.3 V.
* **Part:** TI OPA4990IRUCR (SBOS933, X2QFN-14 RUC, 2 x 2 mm), your pick in place of the out-of-stock TLV9004IRUCR. Table 5-5: IN+ 2 / 4 / 9 / 11, IN- 1 / 5 / 8 / 12, OUT 14 / 6 / 7 / 13, V+ 3, V- 10. Same pin numbers as KiCad's TLV9004xRUCR symbol and RUC0014A footprint.
* **Supply: `+5V_OR`, not +12V.** Absolute maximum ratings, note 3: "Input pins are diode-clamped to the power-supply rails", 10 mA max beyond them. `+5V_OR` is up whenever `+3V3` is, including on USB alone, so a driven pin never sits above the op amp's supply. On +12V (the first draft) a GPIO driven high on USB power would have fed the dead 12 V rail through that diode. The LEDs also work on USB this way.
* **Divider:** the op amp input is the tap, so it sits behind 100 kΩ (33 µA worst case into a clamp diode) and sees at most 1.65 V. The output then needs 1.65 V + VF (2.85 V typ, 3.3 V max): inside the 5 V supply at the typical figure, and it only flattens the top of the range at the worst-case VF or a sagging USB supply.
* **Inputs:** rail to rail, ±10 pA bias, rated for differential voltages up to the supply ("MUX-friendly"). That matters here: with the LED off the loop is open and the inputs sit apart.
* **Split over two packages:** U43 drives IO11 and IO12 (sections 3 and 4), U44 drives IO7, IO13 and IO5 (sections 1, 2 and 4). All four pins on one package did not route: the IN- pins are the four corner pins, and the front copper around U43 leaves no room for eight vias.
* **LED resistors R506-R510** (3.3 kΩ, 0402) sit on the front, one just below each LED (IO12's beside it), so an LED net needs no more than its two vias. A shared array would need all the cathode nets to meet in one place.
* **Spare sections** are followers with IN+ on the supply pin next to it: U43 sections 1 and 2 on V+ (pin 3), U44 section 3 on GND (pin 10). Electrical characteristics: common-mode range (V-) - 0.2 V to (V+) + 0.2 V, so either rail is a valid input.

**Multi-element parts:**
* **RN1-RN5:** Yageo YC124 (4 x 0402, 2.0 x 1.0 mm, 0.5 mm pitch, 1/16 W, 25 V working; datasheet V.9). RN1 4.7 kΩ: fan and pump tach pull-ups and series resistors (were R41, R42, R46, R47). RN2 10 kΩ: fan and pump PWM pull-ups and the flow pull-up (were R3, R4, R5); its fourth element is spare, both ends on +3V3_COOL. RN3 100 Ω, RN4 and RN5 100 kΩ (the divider): IO5, IO7, IO11, IO12. IO13 uses discretes (R503-R505). The arrays are 5 %, the parts they replace were 1 %; none of these values is critical.
* **Q61:** Diodes BSS138DW-7-F (ds30203, SOT-363) replaces Q26 and Q27. Top view: D2 G1 S1 over S2 G2 D1, so one FET is pins 1 S / 2 G / 6 D and the other 4 S / 5 G / 3 D. VGS(th) 0.5-1.5 V, as the BSS138.
* **Q5 / Q6 (BSS138 + BSS84) were left as they are.** The BSS8402DW's N-FET is a 2N7002 type with no RDS(on) figure at a 3.3 V gate.
* **No capacitor arrays.** No four 100 nF capacitors sit together in the reworked areas, and each new IC keeps its capacitor at its own pin.

**Headers: XKB X2510WRS (J3-J6, J13, J16-J20):** right-angle, all-SMD, 4 A. X2510WRS-04-9TSN for the fan, pump and flow sensor (pin 4 unused: there is no 3-pin part), X2510WRS-02-9TSN for the rest. This reverses the MODDIY CO975, Würth 61900311021 and Sullins SWR25X choices, at your request.
* **Drawing X-X2510WRS-02-9TSN rev A0** (covers 2, 4 and 5 poles): signal pads 1.2 x 4.0 mm; hold-down pads 1.1 x 3.4 mm, 1.73 mm outside the end pins; 13.6 mm from tail tip to pin tip; body 4.35 mm deep, (N + 1) x 2.54 mm wide, 5.51 mm high.
* **Scaled, not dimensioned:** how far the tails sit inside the signal pads (about 0.44 mm). The mating end's position is good to about ±0.3 mm for that reason.
* **Overhang:** pin tips 3.0 mm past the board edge, level with J11 and J12.
* **Plugs:** X2510H housings with X2510T terminals. The latch wall runs the full width, so PC fan plugs and the Alphacool 3-pin plug will most likely not push on; the leads are to be re-housed. Not checked against a sample.
* **Sourcing:** LCSC C908467 (2-pin), C908468 (4-pin). Not stocked by DigiKey.

**USB-C: GCT USB4205-GF-A (J1):** flag type, standing on its side, 3.71 mm wide, 12.5 mm above the board, in place of the USB4105-GF-A.
* **Drawing USB4205 rev A2:** two columns of eight pads 1.05 mm long, outer edges 2.80 mm apart; GND and VBUS pads 0.45 mm wide, CC / SBU / D pads 0.35 mm; rows at 2.6 / 1.8 / 1.05 / 0.35 mm from the centre. Four 0.60 x 1.20 mm plated shell slots, two Ø0.80 mm pegs. The footprint matches GCT's own KiCad footprint in `dev/USB4205_GF_A` for every pad position.
* **Shell slots are plated and grounded** here. GCT's KiCad footprint draws them unplated, which would leave the shell floating.
* **Board edge:** GCT draws it 2.70 mm past the front slots, which leaves the mouth 4.3 mm past the edge. Here the mouth is 3.0 mm past it, level with the other wall connectors, so the board runs 1.3 mm further under the shell. The shell's underside is about 3 mm above the board, so nothing touches.
* **3D model:** a 3.71 x 14.0 x 12.5 mm envelope. The STEP in `dev/USB4205_GF_A` is not placed.

**J7 removed.** SW3 is the only power button. U34 stays on the button line, which is now named `PWR_BTN`.
