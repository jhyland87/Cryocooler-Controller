# Pre-order audit (2026-10-14)

Independent check of every part's pinout, the nets, and the PCB before ordering from JLCPCB.
It lowers the risk; it does not prove the board works. Nothing here has run on hardware.

## Result

No wrong pinout, no shorted rail and no reversed polarized part was found. Two documentation
items and three BOM/bench notes came out of it; no schematic or PCB change was needed, so the
Gerber package in `fabrication/` is still valid.

## What was checked and how

| Check | Result |
|---|---|
| Every U/Q/D/J/SW/PS pin-to-net table read by hand (68 parts) | no mismatch found |
| Schematic pin exists on the footprint pad, and no IC footprint has a pad the schematic ignores | 0 problems (EP pads included) |
| Netlist vs PCB pad nets | 807 / 807 match |
| ERC / DRC | 0 / 0 errors, 0 unconnected |
| Rails distinct (VIN, VSW, +12V, +5V, +3V3, ±15V, ±16V5, ISO_3V3, GND, ISO_GND, USB_VBUS) | all present as separate nets, none merged |
| Polarized caps (C6, C43, C71) | pin 1 (+) on the positive rail |
| Isolation spacing | ISO_GND vs GND zones 1.5 mm on every layer; ISO-domain copper at least 2 mm from logic copper on F.Cu and B.Cu |
| LED and diode orientation, FET pin order (BSS138/BSS84 SOT-23, IRF4905S D2PAK) | correct |

## Pinout evidence per part

**A: pin table read from the manufacturer datasheet this session**

| Part | Notes |
|---|---|
| INA239 | pins, SPI mode 1, MISO Hi-Z with CS high, VS/VBUS limits |
| ADS1220 | pins, SPI mode 1, DOUT Hi-Z with CS high, reference and IDAC wiring |
| SC18IS604 | pins, VREFP to VDD, INT#/RESET# rules, SPI mode 3. MISO Hi-Z is **not** stated, so a 74LVC1G125 gates it |
| AD633JR (SOIC) | Y1 1, Y2 2, -VS 3, Z 4, W 5, +VS 6, X1 7, X2 8 (rotated vs the PDIP, matches the schematic) |
| AP63205 | 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 BST; EN may be tied to VIN (abs max 35 V) |
| CL25N8-G | SOT-89: VA 1, VB 2 (tab), N/C 3 |
| LM4040 | SOT-23: cathode 1, anode 2, pin 3 must float or go to the anode |
| 74LVC1G125 | DBV: OE# 1, A 2, GND 3, Y 4, VCC 5 |
| MIE1W0505BGLVH | pins 1,11,12 GND1; 2,3,4 GND2; 5,6 VOUT; 7 VSEL (GND2 = 3.3 V); 8 EN; 9,10 VIN. The footprint's pad groups and land-pattern dimensions match the datasheet drawing (rotated 90 degrees, same handedness) |

**B: confirmed from secondary sources this session (datasheet text not retrievable)**

| Part | Notes |
|---|---|
| ADP7182 | 1 GND, 2 VIN, 3 EN, 4 ADJ, 5 VOUT |
| LTC2954 (TSOT-8) | 1 VIN, 2 PB, 3 ONT, 4 GND, 5 INT#, 6 EN#, 7 PDT, 8 KILL# |
| USBLC6-2SC6 | 1 I/O1, 2 GND, 3 I/O2, 4 I/O2, 5 VBUS, 6 I/O1 |
| LSM6DSOX SDO | The timing table lists an SDO output-disable time and the part is routinely shared on SPI buses, so the output is almost certainly Hi-Z with CS high, but the sentence was not found. Bench item below |

**C: from earlier-session datasheet audits only (see DESIGN_REVIEW.md), not re-fetched**

ESP32-S3-WROOM-2 (pin map also matches the footprint), EMC2303 (KiCad's official symbol, QFN-12 +
EP), ISO7741, ACS37800, ADP5071, ADP7142, AD9833, MCP4921, OPA1656, OPA188, LD1117S33, IRF4905S,
BSS138/BSS84, WS2812B, SG-8002CA (datasheet supplied by the user), USB-C receptacle.

## Findings

1. **Documentation error (fixed):** `DESIGN_REVIEW.md` claimed the ESP32 could drive the INA239 while
   12 V was absent because it is "USB-powered". It is not: USB VBUS feeds only the ESD clamp and a
   4.7 uF cap, and the ESP32 runs from the 3V3 rail, so the MCU and the INA239 lose power together.
2. **BOM: shunt power.** R65, the 15 mOhm shunt in an R2512 footprint, dissipates about 1.5 W at
   10 A. Order a 2 W or 3 W part (a 1 W part is fine up to about 8 A).
3. **BOM: voltage ratings.** Many capacitor values carry no voltage rating. Order at least 25 V parts
   on the 12 V and +/-15 V rails, 50 V where the schematic says so (+/-16.5 V), and 10 V or more on
   5 V and 3.3 V. Consider 35 V for C6 (100 uF on VIN): the TVS clamps at about 26 V, above its 25 V.
4. **Missing pull-ups (low risk):** MCP4921_CS and AD9833_FSYNC have none, so they float while the
   ESP32 resets. No clock runs then, so nothing is written, but 10 kOhm pull-ups would be cleaner on
   the next board revision.
5. **Fans:** the tach lines are pulled up to 3.3 V. A fan with its own pull-up to 5 V or 12 V on the
   tach wire would push current into the 3.3 V rail through that pull-up; standard open-collector
   tachs are fine. Check the fan and pump before connecting them.

## Bench checks (cannot be settled on paper)

* LSM6DSOX SDO is Hi-Z with CS high: scope MISO with the IMU idle, or read the IMU, INA239,
  ADS1220 and SC18IS604 IDs in turn and confirm each answers alone.
* SC18IS604 version string ("SC18IS604 1.0.0") and I2CStat polling; its datasheet disagrees with
  itself about the I2CTO and I2CStat register addresses.
* INA239 manufacturer ID 0x5449 and a current reading against a meter.
* ADS1220 reading with a known resistor in place of the RTD.

## First power-up

1. No fans, pump, RTD, amplifier or USB attached. Use a current-limited bench supply at 12 V,
   limit about 50 mA, and check the input polarity before connecting.
2. Watch the current: it should settle at tens of mA (the standby LED draws about 25 mA by design).
3. Press the panel button. Check +5 V, +3.3 V, +16.5 V / -16.5 V, +15 V / -15 V and ISO 3V3 (against
   ISO_GND) with a meter before anything else; raise the current limit to about 300 mA.
4. Connect USB and flash the firmware; confirm the serial log finds the INA239, ADS1220, SC18IS604
   and IMU.
5. Then the RTD, fans and pump, and last the amplifier REM line and the amplifier output.
