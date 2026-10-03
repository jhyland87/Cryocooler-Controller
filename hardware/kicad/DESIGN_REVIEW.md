# Design review: datasheet audit

Every IC and active discrete in the schematic was checked against its manufacturer datasheet
(pinout, supply range, required external parts, unused-pin rules, absolute maximums). The
connection-level findings are encoded as regression tests in
[`tools/datasheet_rules.py`](tools/datasheet_rules.py) (117 rules, run against the exported
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

## Verified as correct (no change needed)

| Part | Checked against | Result |
|---|---|---|
| LTC2954-2 (TSOT-23-8) | LTC2954 datasheet 2954fb | Pinout; no internal KILL pull-up (so the 5 V bias is required); KILL abs max 7 V; ONT floating = 32 ms; 100 nF PDT ≈ 0.7 s hold-off; EN#/INT# ratings |
| ESP32-S3-WROOM-2 | Datasheet v1.7 | Pins 28-30 are NC; IO47/48 are 1.8 V on R16V parts; strapping pins; EN needs a defined level |
| AD633JR (SOIC) | AD633 Rev A (pin drawing) | 1 Y1, 2 Y2, 3 −VS, 4 Z, 5 W, 6 +VS, 7 X1, 8 X2; ±15 V; RL ≥ 2 kΩ |
| AD9833 | AD9833 Rev E | COMP 10 nF → VDD, CAP/2.5V 100 nF, 0.1 + 10 µF on VDD, VINH 2.8 V at 5 V VDD |
| OPA1656 / OPA188 | TI datasheets | Pinouts, supply (VS ≤ 40 V), NC pins may float |
| INA237 | TI datasheet | Pinout, 0x40 with A0 = A1 = GND, IN+/IN− polarity, ±163.84 mV range |
| ADS122C04 | TI SBAS751B | Pinout, 0x45 (A0 = A1 = DVDD), ratiometric 4-wire RTD circuit, VREF ≥ 0.75 V (0.975 V), AIN2 may float |
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
  DC breaking capacity in the chosen part's datasheet. Add an **inline high-breaking-capacity fuse (7.5-10 A, for example an
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

## Not verifiable from a datasheet I could read

* **LM4040 accuracy grade:** choose the A or B grade for the DAC reference.
* **MIE1W0505 footprint:** your vendor model (SnapEDA); I checked pad names, not the land pattern.
* **SPI modes** (AD9833 mode 2, ACS37800 mode 3, others mode 0/3): set by the firmware libraries.
* **PCB-level items** (creepage between ISO_GND and the logic side, ground returns, copper pours).
