"""Builds the Digi-Key BOM (bom/cryocooler_bom_digikey.csv) from the schematic.

Quantities and designators come from the exported netlist, so they cannot drift
from the design. Part numbers come from the tables below:

* 'design'    the schematic value is the orderable part (ICs, FETs, diodes).
* 'suggested' a part picked for the value, package and rating; verify the
              match in Digi-Key's BOM Manager before ordering.
* 'none'      no part number; use the description (and notes) to choose.

Test points are bare PCB pads and are left out.

Also writes the JLCPCB files: bom/cryocooler_bom_full.csv (every part, JLCPCB
columns) and bom/cryocooler_cpl.csv (SMD placements from the PCB).

Usage: python3 tools/gen_bom.py         (needs kicad-cli)
       python3 tools/gen_bom.py --imu   (IMU board: imu/bom/imu_*.csv)
"""

import collections
import csv
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from sexpr import find_all, parse, sval

KICAD_DIR = Path(__file__).resolve().parents[1]
KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
OUTPUT = KICAD_DIR / 'bom' / 'cryocooler_bom_digikey.csv'
FULL_OUTPUT = KICAD_DIR / 'bom' / 'cryocooler_bom_full.csv'
CPL_OUTPUT = KICAD_DIR / 'bom' / 'cryocooler_cpl.csv'
BOARD = KICAD_DIR / 'cryocooler.kicad_pcb'
SCHEMATIC = KICAD_DIR / 'cryocooler.kicad_sch'

# ── resistors (Yageo RC series, 1 %) ────────────────────────────────────────
R0603 = 'R_0603_1608Metric'
R1206 = 'R_1206_3216Metric'
R0402 = 'R_0402_1005Metric'
# 1206 resistor or Bourns 3313J trimmer land, and the trimmer each fitted value swaps for:
# 3.6k (R92, sine gain 15.2-16.8) and 0 (R96, AD5453 gain +0-11 %)
R_TRIM = 'R_1206_or_Bourns_3313J'
TRIMMERS = {'3.6k': '3313J-1-502E (5k)', '0': '3313J-1-102E (1k)'}


def resistor_code(value):
    """'4.7k' -> '4K7', '49.9' -> '49R9', '2.55M' -> '2M55', '100' -> '100R'."""
    match = re.fullmatch(r'(\d+)(?:\.(\d+))?([kM]?)', value)
    if not match:
        raise ValueError(f'unsupported resistor value {value}')
    whole, fraction, unit = match.groups()
    unit = unit.upper() or 'R'
    return f'{whole}{unit}{fraction}' if fraction else f'{whole}{unit}'


# ── capacitors: (value, footprint) -> (MPN, description, note) ──────────────
SAMSUNG = 'Samsung Electro-Mechanics'
CAPS = {
    ('100nF', 'C_0603_1608Metric'): (
        'CL10B104KB8NNNC', 'CAP CER 0.1UF 50V X7R 0603', ''),
    ('100nF', 'C_0402_1005Metric'): (
        'CL05B104KB54PNC', 'CAP CER 0.1UF 50V X7R 0402', ''),
    ('10nF', 'C_0402_1005Metric'): (
        'CL05B103KB5NNNC', 'CAP CER 10000PF 50V X7R 0402', ''),
    ('1nF/C0G', 'C_0402_1005Metric'): (
        'CL05C102JB5NNNC', 'CAP CER 1000PF 50V C0G 0402',
        'across R35 + R92 (50.6k) in the sine gain stage'),
    ('120pF', 'C_0402_1005Metric'): (
        'CL05C121JB5NNNC', 'CAP CER 120PF 50V C0G 0402',
        'TPS62822 feed-forward across the 453k'),
    ('22pF/C0G', 'C_0402_1005Metric'): (
        'CL05C220JB5NNNC', 'CAP CER 22PF 50V C0G 0402',
        'AD5453 output stage stability (datasheet C1), sized for the OPA2991'),
    ('2pF/C0G', 'C_0402_1005Metric'): (
        'CL05C020CB5NNNC', 'CAP CER 2PF 50V C0G 0402',
        'AD5453 output stage stability (datasheet C1)'),
    ('47nF', 'C_0603_1608Metric'): (
        'CL10B473KB8NNNC', 'CAP CER 0.047UF 50V X7R 0603',
        'ADP5071 COMP1; Q1 gate-drain slow start'),
    ('68nF', 'C_0603_1608Metric'): (
        'CL10B683KB8NNNC', 'CAP CER 0.068UF 50V X7R 0603', 'ADP5071 COMP2'),
    ('1uF', 'C_0603_1608Metric'): (
        'CL10A105KB8NNNC', 'CAP CER 1UF 50V X5R 0603', ''),
    ('100nF', 'C_0805_2012Metric'): (
        'CL21B104KBCNNNC', 'CAP CER 0.1UF 50V X7R 0805', ''),
    ('10nF', 'C_0603_1608Metric'): (
        'CL10B103KB8NNNC', 'CAP CER 10000PF 50V X7R 0603', ''),
    ('1uF', 'C_0805_2012Metric'): (
        'CL21B105KBFNNNE', 'CAP CER 1UF 50V X7R 0805', ''),
    ('10uF', 'C_0805_2012Metric'): (
        'CL21A106KAYNNNE', 'CAP CER 10UF 25V X5R 0805', ''),
    ('4.7uF', 'C_0805_2012Metric'): (
        'CL21A475KAQNNNE', 'CAP CER 4.7UF 25V X5R 0805', 'USB VBUS filter'),
    ('470nF', 'C_0805_2012Metric'): (
        'CL21B474KBFNNNE', 'CAP CER 0.47UF 50V X7R 0805',
        'INA239 input filter across IN+/IN-; Q1 gate-source'),
    ('10uF/50V', 'C_1206_3216Metric'): (
        'CL31A106KBHNNNE', 'CAP CER 10UF 50V X5R 1206',
        '12 V rail (U15 input); 50 V so it is rated over the SMBJ16A clamp (about 26 V); '
        'JLCPCB C13585 (basic)'),
    ('10uF/25V', 'C_1206_3216Metric'): (
        'CL31A106KAHNNNE', 'CAP CER 10UF 25V X5R 1206', '12 V rail'),
    ('22uF/25V X7R', 'C_1210_3225Metric'): (
        'GRM32ER71E226KE15L', 'CAP CER 22UF 25V X7R 1210',
        'ADP5071 outputs / LT3097 inputs and LT3097 outputs; the LT3097 needs '
        '>= 10 uF effective at 15 V DC bias (INN and both outputs have two in '
        'parallel; INP needs 4.7 uF), so check the DC-bias curve'),
    ('1uF/50V', 'C_1206_3216Metric'): (
        'CL31B105KBHNNNE', 'CAP CER 1UF 50V X7R 1206',
        'LT3097 SETP / SETN bypass (the pins sit at 14.7 V DC)'),
    ('22uF/10V', 'C_1206_3216Metric'): (
        'CL31A226KPHNNNE', 'CAP CER 22UF 10V X5R 1206',
        '5 V and 3.3 V buck outputs, ISOW7741 VDD and VISOOUT, ESP32'),
    ('22uF/25V', 'C_1210_3225Metric'): (
        'CL32A226KAJNNNE', 'CAP CER 22UF 25V X5R 1210', '12 V rail'),
}
# makers for the caps that are not Samsung
CAP_MAKERS = {
    'GRM32ER71E226KE15L': 'Murata',
}

# ── everything else, keyed by (value, footprint) ────────────────────────────
# (manufacturer, MPN, description, basis, note)
PARTS = {
    ('100uF/25V', 'CP_Elec_8x10'): (
        'Panasonic', 'EEE-FK1E101P',
        'CAP ALUM 100UF 20% 25V SMD 8x10.2', 'suggested', 'switched +12 V rail'),
    ('100uF/35V', 'CP_Elec_8x10'): (
        'Panasonic', 'EEE-FK1V101P',
        'CAP ALUM 100UF 20% 35V SMD 8x10.2', 'suggested',
        'C65 sits on the input rail behind a 26 V TVS clamp; rating taken from '
        'distributor listings, not a Panasonic datasheet'),
    ('1N4148W', 'D_SOD-123'): (
        'Diodes Incorporated', '1N4148W-7-F',
        'DIODE GEN PURP 75V 150MA SOD123', 'design', ''),
    ('DFLS240', 'D_PowerDI-123'): (
        'Diodes Incorporated', 'DFLS240-7',
        'DIODE SCHOTTKY 40V 2A POWERDI123', 'design', ''),
    ('SMBJ16A', 'D_SMB'): (
        'Littelfuse', 'SMBJ16A',
        'TVS DIODE 16VWM 26VC DO214AA', 'design', 'unidirectional'),
    ('WS2812B-2020', 'LED_WS2812B-2020_PLCC4_2.0x2.0mm'): (
        'Adafruit', '4684',
        'LED RGB NEOPIXEL NANO WS2812B-2020 2 X 2 MM (10 pack)', 'design',
        'Adafruit listed the 10 pack out of stock on 2026-11-06; the 100 pack is '
        'Adafruit 6428. Check JLCPCB/LCSC for a WS2812B-2020 if you assemble there'),
    ('5A backup', 'Fuse_Littelfuse-NANO2-451_453'): (
        'Littelfuse', '0453005.MR', 'FUSE BRD MNT 5A 125VAC/VDC 2SMD',
        'suggested',
        'NANO2 453 series, fast acting, 2410 package (6.1 x 2.7 mm); backup '
        'only: add a fuse at the PSU end (see DESIGN_REVIEW.md)'),
    ('SRP4020TA-4R7M', 'L_Bourns_SRP4020TA'): (
        'Bourns', 'SRP4020TA-4R7M', 'FIXED IND 4.7UH 2.6A 105MOHM SMD',
        'design', 'AP63205 buck inductor, shielded; Isat 3.5 A against the 2 A buck'),
    ('SRP4020TA-R47M', 'L_Bourns_SRP4020TA'): (
        'Bourns', 'SRP4020TA-R47M', 'FIXED IND 0.47UH 8A 14MOHM SMD',
        'design', 'TPS62822 inductor, shielded'),
    ('SRP7050TA-3R3M', 'L_Bourns_SRP7050TA'): (
        'Bourns', 'SRP7050TA-3R3M', 'FIXED IND 3.3UH 12A 20.9MOHM SMD',
        'design', 'ADP5071 boost inductor (rev 1 value)'),
    ('SRP7050TA-6R8M', 'L_Bourns_SRP7050TA'): (
        'Bourns', 'SRP7050TA-6R8M', 'FIXED IND 6.8UH 8.5A 51.5MOHM SMD',
        'design', 'ADP5071 inverting inductor (rev 1 value)'),
    ('BLM15EX331SN1D', 'L_0402_1005Metric'): (
        'Murata', 'BLM15EX331SN1D', 'FERRITE BEAD 330 OHM 100MHZ 0402',
        'design', 'ISOW7741 VISOOUT and GND2 beads, named by the TI datasheet'),
    ('BLM18PG121SN1D', 'L_0603_1608Metric'): (
        'Murata', 'BLM18PG121SN1D', 'FERRITE BEAD 120 OHM 100MHZ 2A 0603',
        'suggested', 'ahead of JP5 on the cold head supply; rating from '
        'distributor listings'),
    ('AONR21307', 'AOS_DFN3x3A_8L_EP1'): (
        'Alpha & Omega Semiconductor', 'AONR21307',
        'MOSFET P-CH 30V DFN3X3', 'design',
        'Q1 main power switch; check the turn-on and turn-off SOA on the bench; '
        'datasheet has no package outline, confirm the DFN3x3A land pattern'),
    ('BZT52C15', 'D_SOD-123'): (
        'Diodes Incorporated', 'BZT52C15-7-F', 'DIODE ZENER 15V 500MW SOD123',
        'suggested', 'Q1 gate clamp, 13.8-15.6 V'),
    ('MMBZ9V1ALT1G', 'SOT-23'): (
        'onsemi', 'MMBZ9V1ALT1G', 'TVS DIODE 6VWM DUAL COMMON ANODE SOT23-3',
        'design', 'AD5453 VREF clamp: used between cathodes, under 10.5 V'),
    ('TPD4E05U06DQAR', 'USON-10_2.5x1.0mm_P0.5mm'): (
        'Texas Instruments', 'TPD4E05U06DQAR', 'TVS DIODE 5.5VWM 4CH 10USON',
        'design', 'ESD clamps on tach lines, NTC and J10'),
    ('SP3422-04UTG', 'Littelfuse_DFN-5_1.0x0.6mm_P0.35mm'): (
        'Littelfuse', 'SP3422-04UTG', 'TVS DIODE 5VWM 4CH 5UDFN',
        'design', 'ESD clamps on tach lines, NTC and J10'),
    ('NUF6401MNT1G', 'OnSemi_DFN-12-1EP_506AD'): (
        'onsemi', 'NUF6401MNT1G', 'EMI FILTER 6CH 100 OHM 17PF ESD DFN12',
        'design', 'J14: 100 ohm series, ESD clamps on all six IMU cable signals'),
    ('LSM6DSOXTR', 'LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y'): (
        'STMicroelectronics', 'LSM6DSOXTR', 'IMU ACCEL/GYRO I2C/SPI 14LGA',
        'design', 'IMU board (imu/): SPI mode, datasheet DS12814'),
    ('TPD1E05U06DPYR', 'Texas_DPY0002A_0.6x1mm_P0.65mm'): (
        'Texas Instruments', 'TPD1E05U06DPYR', 'TVS DIODE 5.5VWM 1CH X1SON-2',
        'design', 'ESD clamp on the panel button line'),
    ('ECS-2520MV-160-BN-TR', 'Oscillator_SMD_ECS_2520MV-xxx-xx-4Pin_2.5x2.0mm'): (
        'ECS Inc.', 'ECS-2520MV-160-BN-TR', 'XTAL OSC 16MHZ 1.6-3.6V HCMOS +-50PPM SMD',
        'design', 'AD9837 clock on +3V3_SG (16 MHz max); -40 to 85 C'),
    ('AD5453WBCPZ-RL', 'VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm'): (
        'Analog Devices', 'AD5453WBCPZ-RL', 'IC DAC 14BIT MULTIPLYING SPI 8LFCSP',
        'design', 'amplitude control; powers up at zero scale'),
    ('ISOW7741DFMR', 'TI_DFM0020A'): (
        'Texas Instruments', 'ISOW7741DFMR',
        'DIGITAL ISOLATOR 4CH WITH DC-DC 5KVRMS 20SOIC', 'design',
        '110 mA maximum at 5 V to 5 V; no F suffix = outputs high when input lost'),
    ('ACS37800KMACTR-015B5-SPI', 'SOIC-16W_7.5x10.3mm_P1.27mm'): (
        'Allegro MicroSystems', 'ACS37800KMACTR-015B5-SPI',
        'SENSOR CURRENT/VOLTAGE 15A 5V SPI 16SOIC', 'design', ''),
    ('ADS1220IRVAR', 'Texas_RVA_VQFN-16-1EP_3.5x3.5mm_P0.5mm_EP2.14x2.14mm'): (
        'Texas Instruments', 'ADS1220IRVAR', 'IC ADC 24BIT SIGMA-DELTA 16VQFN',
        'design', ''),
    ('ADP5071ACPZ', 'LFCSP-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm'): (
        'Analog Devices', 'ADP5071ACPZ-R6', 'IC REG BOOST/INVERTING DUAL 20LFCSP',
        'design', 'exposed pad 21 is GND; rev 1 compensation and feedback values'),
    ('TPS62822DLCR', 'Texas_VSON-HR-8_1.5x2mm_P0.5mm'): (
        'Texas Instruments', 'TPS62822DLCR', 'IC REG BUCK ADJ 2A 8VSON-HR',
        'design', ''),
    ('TPS2116DRLR', 'SOT-583-8'): (
        'Texas Instruments', 'TPS2116DRLR', 'IC POWER MUX 2 INPUT 2.5A SOT583-8',
        'design', '+5V / USB VBUS priority mux into +5V_OR'),
    ('LTC2954CDDB-2', 'DFN-8-1EP_2x3mm_P0.5mm_EP0.61x2.2mm'): (
        'Analog Devices', 'LTC2954CDDB-2#TRMPBF',
        'IC PUSHBUTTON ON/OFF CONTROLLER 8DFN', 'suggested',
        'C grade, -2 version (EN# output)'),
    ('BSS138W', 'SOT-323_SC-70'): (
        'Diodes Incorporated', 'BSS138W-7-F', 'MOSFET N-CH 50V 200MA SOT323',
        'suggested', '-15 V power good guard'),
    ('BSS138', 'SOT-323_SC-70'): (
        'Diodes Incorporated', 'BSS138W-7-F', 'MOSFET N-CH 50V 200MA SOT323',
        'suggested', 'power-good stage: same pinout as the SOT-23 BSS138 '
        '(1 gate, 2 source, 3 drain)'),
    ('BAT54AW', 'SOT-323_SC-70'): (
        'Diodes Incorporated', 'BAT54AW-7-F',
        'DIODE ARR SCHOTTKY 30V 200MA SOT323', 'design',
        'common anode on PG_15V (pin 3), cathodes on pins 1 and 2'),
    ('BSS138', 'SOT-23'): (
        'Diodes Incorporated', 'BSS138-7-F', 'MOSFET N-CH 50V 200MA SOT23-3',
        'suggested', ''),
    ('BSS84', 'SOT-23'): (
        'Diodes Incorporated', 'BSS84-7-F', 'MOSFET P-CH 50V 130MA SOT23-3',
        'suggested', 'output stage is limited to about 130 mA'),
    ('15m', 'R_2512_6332Metric'): (
        'Vishay Dale', 'WSL2512R0150FEA18', 'RES 0.015 OHM 1% 2W 2512',
        'suggested',
        'INA239 shunt, about 1.5 W at 10 A: needs 2 W or more; the "18" '
        'suffix is the 2 W part (WSL2512R0150FEA is 1 W)'),
    ('USB_C', 'USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'): (
        'GCT', 'USB4105-GF-A', 'USB-C 2.0 RECEPTACLE 16P, TOP MOUNT',
        'suggested', 'footprint is the GCT USB4105-xx-A'),
    ('USB_C', 'USB_C_Receptacle_GCT_USB4205-GF-A_16P_Flag'): (
        'GCT', 'USB4205-GF-A', 'USB-C 2.0 RECEPTACLE 16P, FLAG TYPE, TOP MOUNT',
        'design', 'J1: stands on its side, 12.5 mm high, mouth 3 mm past the board '
        'edge; four plated shell stakes and two pegs'),
    # XKB X2510 wafers (rev 4): all-SMD, so two can sit back to back. KF2510-style
    # latch wall, so PC fan plugs have to be re-housed.
    ('', 'XKB_X2510WRS-02-9TSN_1x02_P2.54mm_Horizontal'): (
        'XKB Connectivity', 'X2510WRS-02-9TSN',
        'CONN HEADER R/A SMT 2POS 2.54MM, 4 A', 'design',
        'J6 NTC, J13 relay 12 V out, J16-J20 general-purpose I/O; mates with '
        'X2510H-02 housings and X2510T terminals'),
    ('', 'XKB_X2510WRS-04-9TSN_1x04_P2.54mm_Horizontal'): (
        'XKB Connectivity', 'X2510WRS-04-9TSN',
        'CONN HEADER R/A SMT 4POS 2.54MM, 4 A', 'design',
        'J3 fan, J4 pump, J5 flow sensor (pin 4 unused); mates with X2510H-04 '
        'housings, so fan, pump and flow leads are re-housed'),
    ('OPA4990IRUCR', 'Texas_S-PX2QFN-14'): (
        'Texas Instruments', 'OPA4990IRUCR', 'IC OPAMP GP 4 CIRCUIT 14X2QFN',
        'design', 'general-purpose I/O LED drivers, on +5V_OR'),
    ('SN74LVC1G125DRYR', 'Texas_USON-6_1x1.45mm_P0.5mm_SMD'): (
        'Texas Instruments', 'SN74LVC1G125DRYR', 'IC BUF NON-INVERT 5.5V 6SON',
        'design', 'ACS37800 SCK and MISO gates, enabled by ACS_CS'),
    ('BSS138DW', 'SOT-363_SC-70-6'): (
        'Diodes Incorporated', 'BSS138DW-7-F', 'MOSFET 2N-CH 50V 200MA SOT363',
        'design', 'fan and pump PWM drivers in one package'),
    # Right-angle connectors for the UCS 145-125 housing (plugs enter through
    # the side walls). Ratings from each maker's datasheet.
    ('', 'TE_2305908-2_1x02_P5.00mm_Horizontal_SMD'): (
        'TE Connectivity', '2305908-2', 'CONN HEADER R/A SMT 2POS 5MM, 15 A',
        'design', 'J11 amp out. SMT pads carry all plugging force. Mates with '
        'TE 2213934 / 2213935 / 2305909 series plugs (confirm the plug item number '
        'before ordering)'),
    ('', 'TE_643228-1_1x03_P6.35mm_Horizontal'): (
        'TE Connectivity', '643228-1', 'CONN HEADER R/A TH 3POS 6.35MM, UNIVERSAL MATE-N-LOK',
        'design', 'J12 cryocooler: pin 1 +, pin 2 -, pin 3 GND (the plug\'s protective '
        'ground, tied to board GND). Through hole, soldered by hand or selectively, plus '
        '2 screws through the 3.81 mm ear holes. Listed mating plugs: TE 350766-1, '
        '770018-1; one distributor lists 12 A / 600 V (confirm plug and rating with TE '
        'before ordering)'),
    ('', 'Tensility_54-00164_5.5x2.1mm_Horizontal_SMD'): (
        'Tensility', '54-00164', 'CONN JACK R/A SMT 5.5X2.1MM',
        'design', 'J2 12 V in, centre pin positive; 5.5 A up to 40 C, derates '
        'to 0 at 70 C; do not mate under load'),
    ('', 'SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD'): (
        'Same Sky', 'MJ-3523-SMT-TR', 'CONN JACK MONO 3.5MM SMD',
        'design', 'J9 amplifier signal: tip = signal, sleeve = GND'),
    ('', 'PhoenixContact_MC_0,5_2-G-2,54_SMD_1x02_P2.54mm_Horizontal'): (
        'Phoenix Contact', '1821698', 'PCB HEADER MC 0,5/ 2-G-2,54 SMD R24, 6 A',
        'design', 'J8 amplifier REM. Mating plug FMC 0,5/ 2-ST-2,54 (confirm the '
        'plug item number before ordering)'),
    ('', 'FanHeader_4P_P2.54mm_Horizontal'): (
        'MODDIY', 'CO975', 'CONN HEADER 3+1 FAN R/A 4POS 2.54MM',
        'design', 'J3 fan, J4 pump: takes standard 3-pin and 4-pin PC fan '
        'plugs. FC-3+1P-MA; no maker drawing or current rating, so check the '
        'pins and hole fit on a real part before ordering boards'),
    ('', 'Wurth_WR-WTB_61900311021_1x03_P2.54mm_Horizontal'): (
        'Wurth Elektronik', '61900311021',
        'CONN HEADER WR-WTB R/A LOCKING 3POS 2.54MM, 3 A', 'design',
        'J5 flow sensor: check the bottom locking plate clears the sensor plug'),
    ('', 'Sullins_SWR25X-NRTC-S02-RB-BA_1x02_P2.54mm_Horizontal'): (
        'Sullins Connector Solutions', 'SWR25X-NRTC-S02-RB-BA',
        'CONN HEADER R/A WAFER 2POS 2.54MM, 3 A', 'design',
        'J6 NTC, J7 panel button, J13 relay 12 V out; mates with SWH25X '
        'housings, so JST PH pigtails no longer fit'),
    ('', 'TestPoint_Keystone_5015_Micro_Mini'): (
        'Keystone Electronics', '5015', 'PC TEST POINT MINIATURE SMT',
        'design', 'ground test points; needs a via to its ground plane'),
    ('', 'Adafruit_4392_JST-PH_1x04_P2.00mm_Horizontal_SMD'): (
        'Adafruit', '4392', 'CONN HEADER JST PH COMPATIBLE R/A SMT 4POS 2MM, 2 A',
        'design', 'J10 PT1000 4-wire (F+ / S+ / S- / F-); Kaweei '
        'CW2001-04T-H01-BD-A; mates with a JST PHR-4 housing or JST PH '
        '4-pin pigtail'),
    ('74AHCT1G125GM', 'Nexperia_XSON-6_SOT886_1.0x1.45mm_P0.5mm'): (
        'Nexperia', '74AHCT1G125GM,115', 'IC BUF NON-INVERT 5.5V 6XSON',
        'design', '5 V level shifter for the WS2812B'),
    ('74AHCT1G125', 'SOT-23-5'): (
        'Texas Instruments', 'SN74AHCT1G125DBVR', 'IC BUF NON-INVERT 5.5V SOT23-5',
        'suggested', '5 V level shifter for the WS2812B'),
    ('74LV1T34GX', 'Nexperia_X2SON-5_SOT1226-3_0.8x0.8mm_P0.5mm'): (
        'Nexperia', '74LV1T34GXH', 'IC BUF NON-INVERT 5.5V 5X2SON',
        'design', '1.8 V to 3.3 V buffer for DISP_DC'),
    ('SN74LV1T34', 'SOT-23-5'): (
        'Texas Instruments', 'SN74LV1T34DBVR', 'IC BUF NON-INVERT 5.5V SOT23-5',
        'suggested', '1.8 V to 3.3 V buffer for DISP_DC'),
    ('TACTILE', 'SW_Panasonic_EVP-AA'): (
        'Panasonic', 'EVP-AA802Q', 'SWITCH TACTILE SPST-NO 20MA 15V SMD J-LEAD',
        'design', 'SW1 reset, SW2 boot; 3.5 x 2.9 x 1.7 mm, 5.0 N, grey actuator, 100,000 cycles'),
    ('APGB0607G22R23C', 'LED_Kingbright_APGB0607'): (
        'Kingbright', 'APGB0607G22R23C', 'LED GREEN/RED BICOLOR 0.65X0.65MM SMD',
        'design', 'all indicators but D13; independent dies, about 1 mA each. '
        'D6 and D10 use one die'),
    ('TACTILE', 'SW_Panasonic_EVQ-P2F'): (
        'Panasonic', 'EVQ-P2F02K', 'SWITCH TACTILE SPST-NO 20MA 15V SMD',
        'design', 'SW1 reset, SW2 boot; 5.0 N, black actuator, 2.5 mm high, 200,000 cycles'),
    ('TACTILE', 'SW_TE_1571300-2'): (
        'TE Connectivity', '1571300-2', 'SWITCH TACTILE SPST-NO 0.05A 24V R/A SMD IP67',
        'design', 'SW3 power button; right angle, actuator through the right board edge, IP67'),
    ('SN74LVC138ARGYR', 'Texas_RGY_R-PVQFN-N16_EP2.05x2.55mm'): (
        'Texas Instruments', 'SN74LVC138ARGYR', 'IC DECODER/DEMUX 1X3:8 16VQFN',
        'design', 'decodes the shared SPI bus chip selects; SN74LVC138ARGYRG4 is the same part'),
    ('AD9837BCPZ', 'LFCSP-WD-10-1EP_3x3mm_P0.5mm_EP1.64x2.38mm'): (
        'Analog Devices', 'AD9837BCPZ-RL7', 'IC DDS WAVEFORM GEN 10LFCSP', 'design',
        'replaces AD9833BRMZ: same pins and registers, 16 MHz MCLK, exposed pad to GND'),
    ('TSC2046EIRGVT', 'Texas_RGV0016A_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm'): (
        'Texas Instruments', 'TSC2046EIRGVT',
        'IC TOUCH SCREEN CTRLR 4-WIRE 16VQFN', 'design',
        'TI lists it as Last Time Buy; TSC2046IRGVR is the active fallback, same '
        'footprint and pins but no IEC ESD rating'),
    ('FH12-14S-0.5SH(55)',
     'Hirose_FH12-14S-0.5SH_1x14-1MP_P0.50mm_Horizontal'): (
        'Hirose', 'FH12-14S-0.5SH(55)', 'CONN FFC BOTTOM 14POS 0.50MM R/A',
        'design', 'display FPC (Phoenix datasheet 109921); check the FFC '
        'contact side so pin 1 lands on pin 1'),
    ('505448-0891', 'Molex_Micro-Lock_Plus_505448-0891_2x04_P1.25mm_Horizontal'): (
        'Molex', '505448-0891', 'CONN HEADER R/A 8POS 1.25MM DUAL ROW SMD',
        'design', 'J14 IMU cable; Micro-Lock Plus, positive lock, 30 mating '
        'cycles; mates with a 505432 series 8-circuit dual-row housing'),
    ('RJSSE-5380', 'RJ45_Amphenol_RJSSE-5380_Horizontal'): (
        'Amphenol', 'RJSSE-5380', 'CONN MOD JACK 8P8C R/A SHIELDED SMD',
        'design', 'J14 IMU cable; plain jack, no magnetics (drawing '
        'P-RJSSE-5380 rev E)'),
    ('LT3097ADJC', 'DFN-22-2EP_6x3mm_P0.5mm_LT3097'): (
        'Analog Devices', 'LT3097ADJC#PBF',
        'IC REG LINEAR POS/NEG ADJ 500MA 22DFN', 'suggested',
        '#PBF is the tube, #TRPBF the reel; DFN with two exposed pads '
        '(23 = GND, 24 = INN = -16.5 V)'),
    ('AP63205WU-7', 'TSOT-23-6'): (
        'Diodes Incorporated', 'AP63205WU-7', 'IC REG BUCK 5V 2A TSOT26',
        'design', ''),
    ('ESP32-S3-WROOM-2-N32R16V', 'ESP32-S3-WROOM-2'): (
        'Espressif', 'ESP32-S3-WROOM-2-N32R16V',
        'MODULE ESP32-S3 32MB FLASH 16MB PSRAM', 'design', ''),
    ('INA239AIDGSR', 'TSSOP-10_3x3mm_P0.5mm'): (
        'Texas Instruments', 'INA239AIDGSR', 'IC CURRENT/POWER MONITOR 10VSSOP',
        'design', ''),
    ('LM4040DBZ-5', 'SOT-23'): (
        'Texas Instruments', 'LM4040D50IDBZR',
        'IC VREF SHUNT 5V 1% SOT23-3', 'suggested',
        'only biases the LTC2954 KILL input; 1 % is plenty'),
    ('OPA2991IDSGR', 'TI_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm'): (
        'Texas Instruments', 'OPA2991IDSGR', 'IC OPAMP GP 2CIRC RRIO 8WSON',
        'design', 'U5: A is the DDS gain stage, B the AD5453 output stage; stock not checked'),
    ('OPA1655DBVR', 'SOT-23-5'): (
        'Texas Instruments', 'OPA1655DBVR', 'IC OPAMP AUDIO 1CIRC SOT23-5',
        'design', 'single version of the OPA1656'),
    ('OPA188AIDBVR', 'SOT-23-5'): (
        'Texas Instruments', 'OPA188AIDBVR', 'IC OPAMP ZERO-DRIFT 1CIRC SOT23-5',
        'design', 'OPA188AIDBVT is the 250-piece reel. Digi-Key offers OPA180 '
        'parts as substitutes: they are different parts, do not take them'),
    ('MCP23S08-E/ML', 'QFN-20-1EP_4x4mm_P0.5mm_EP2.7x2.7mm'): (
        'Microchip', 'MCP23S08-E/ML', 'IC I/O EXPANDER SPI 8B 20QFN', 'suggested',
        'stock not checked; MCP23S08T-E/ML is the reel'),
    ('SRL05P7', 'MCC_DFN1510-6_1.5x1.0mm_P0.5mm'): (
        'Micro Commercial Components', 'SRL05P7-TP', 'TVS DIODE 5VWM 17VC DFN1510-6',
        'design', 'USB ESD clamp; JLCPCB C3713451'),
    ('USBLC6-2SC6', 'SOT-23-6'): (
        'STMicroelectronics', 'USBLC6-2SC6', 'TVS DIODE 5.25V 17V SOT23-6',
        'design', ''),
}

LED_PARTS = {
    'green': ('Lite-On', 'LTST-C190KGKT', 'LED GREEN CLEAR 0603 SMD'),
    'red': ('Lite-On', 'LTST-C190KRKT', 'LED RED CLEAR 0603 SMD'),
    'yellow': ('Lite-On', 'LTST-C190KSKT', 'LED YELLOW CLEAR 0603 SMD'),
    'white': ('Lite-On', 'LTW-C193TS5', 'LED WHITE CLEAR 0603 SMD'),
}


# Digi-Key order of 2026-10-15: original MPN -> (substitute MPN, maker).
# Applied after classify() so the BOM matches what was actually bought.
SUBSTITUTES = {
    'CL21A106KAYNNNE': ('CL21A106KACLRNC', 'Samsung Electro-Mechanics'),
    'CL10B104KB8NNNC': ('C0603C104K5RACTU', 'Kemet'),
    'CL21B105KBFNNNE': ('08055C105KAT2A', 'Kyocera AVX'),
    'CL21A475KAQNNNE': ('C2012X5R1E475K085AC', 'TDK'),
    'EEE-FK1E101P': ('EEE-FK1E101AP', 'Panasonic'),
    'CL32A226KAJNNNE': ('C1210C226K3PACTU', 'Kemet'),
    'CL31A106KAHNNNE': ('C3216X5R1E106K085AC', 'TDK'),
    'BSS84-7-F': ('BSS84', 'onsemi'),
    'RC0603FR-0710KL': ('AR0603FR-0710KL', 'Yageo'),
    'RC0603FR-075K1L': ('CR0603-FX-5101ELF', 'Bourns'),
    'RC0603FR-07100KL': ('AR0603FR-07100KL', 'Yageo'),
    'RC0603FR-0751KL': ('CR0603-FX-5102ELF', 'Bourns'),
    'RC0603FR-07100RL': ('AR0603FR-07100RL', 'Yageo'),
    'RC0603FR-072M67L': ('CRCW06032M67FKEA', 'Vishay Dale'),
}

# Lines Digi-Key could not supply: Mouser order (Mouser part number is known
# only where a listing was seen).
MOUSER_LINES = {
    'U1': '356-SP32S3WM2N32R16V',
    'U15': '621-AP63205WU-7',
    'U23': '595-INA239AIDGSR',
    'SW1': '',  # Mouser listing given by the user; its Mouser number wasn't seen
}
MOUSER_MPN = {}
MOUSER_OUTPUT = KICAD_DIR / 'bom' / 'cryocooler_bom_mouser.csv'

# JLCPCB: manufacturer part number -> LCSC part number (C-number). Fill in as
# parts are matched in JLCPCB's BOM upload; blank cells are left for the upload.
LCSC_PARTS = {
    'X2510WRS-02-9TSN': 'C908467',
    'X2510WRS-04-9TSN': 'C908468',
}

# JLCPCB: KiCad footprint -> degrees added to the KiCad rotation in the CPL.
# JLCPCB's part library orients some packages differently; set these from the
# placement preview in JLCPCB's order page.
ROTATION_OFFSETS = {}


def load_netlist():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'cryocooler.net'
        subprocess.run(
            [
                KICAD_CLI, 'sch', 'export', 'netlist', '--format',
                'kicadsexpr', '-o', str(path),
                str(SCHEMATIC),
            ],
            check=True,
            capture_output=True,
        )
        root = parse(path.read_text())
    parts = []
    for comp in find_all(find_all(root, 'components')[0], 'comp'):
        footprint = find_all(comp, 'footprint')
        parts.append(
            (
                sval(find_all(comp, 'ref')[0][1]),
                sval(find_all(comp, 'value')[0][1]),
                sval(footprint[0][1]).split(':')[-1] if footprint else '',
            )
        )
    return parts


def load_placements():
    """Returns the SMD placements from the PCB as (ref, x, y, side, rotation, package, value).

    Coordinates are absolute (board origin), the same as the Gerbers that
    export_fab.py writes, so the CPL lines up with the fabricated pads.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'positions.csv'
        subprocess.run(
            [
                KICAD_CLI, 'pcb', 'export', 'pos', '--format', 'csv',
                '--units', 'mm', '--side', 'both', '--smd-only',
                '-o', str(path), str(BOARD),
            ],
            check=True,
            capture_output=True,
        )
        with path.open(newline='') as handle:
            return [
                (row['Ref'], float(row['PosX']), float(row['PosY']),
                 row['Side'], float(row['Rot']), row['Package'], row['Val'])
                for row in csv.DictReader(handle)
            ]


def jlcpcb_footprint(footprint):
    """'R_0603_1608Metric' -> '0603'; other footprints keep their KiCad name."""
    match = re.match(r'(?:R|C|LED|D)_(\d{4})_', footprint)
    return match.group(1) if match else footprint


def write_jlcpcb_files(rows):
    """Writes the full JLCPCB BOM and the CPL; returns (bom lines, placements).

    Both follow JLCPCB's samples: the BOM has Comment, Designator, Footprint and
    the part number column; the CPL has Mid X / Mid Y in mm, Top / Bottom layer.
    """
    with FULL_OUTPUT.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['Comment', 'Designator', 'Footprint',
                         'JLCPCB Part #\uff08optional\uff09', ''])
        for row in rows:
            mpn = row['Manufacturer Part Number']
            writer.writerow([
                row['Value'] or mpn or row['Description'],
                ','.join(row['Designators']),
                jlcpcb_footprint(row['Package']),
                LCSC_PARTS.get(mpn, ''),
                '',
            ])
    bom_refs = {ref for row in rows for ref in row['Designators']}
    placements = [p for p in load_placements() if p[0] in bom_refs]
    placements.sort(key=lambda placement: sort_key(placement[0]))
    with CPL_OUTPUT.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['Designator', 'Val', 'Package', 'Mid X', 'Mid Y',
                         'Rotation', 'Layer'])
        for ref, pos_x, pos_y, side, rotation, package, value in placements:
            rotation = (rotation + ROTATION_OFFSETS.get(package, 0)) % 360
            writer.writerow([ref, value, package, f'{pos_x:.4f}mm',
                             f'{pos_y:.4f}mm', f'{rotation:g}',
                             side.capitalize()])
    return len(rows), len(placements)


def sort_key(ref):
    match = re.match(r'([A-Z]+)(\d+)', ref)
    return (match.group(1), int(match.group(2)))


def classify(value, footprint):
    """Returns (manufacturer, mpn, description, basis, note) for one group."""
    if value.startswith('EN '):
        return ('Keystone', '5110', 'JUMPER SMT 0603 ZERO OHM', 'design',
                'supply disable jumpers JP1-JP5 ("true zero ohm", 0603 '
                'resistor land pattern); desolder to cut a section')
    if footprint == R_TRIM:
        trimmer = TRIMMERS[value]
        if value == '0':
            return ('Yageo', 'RC1206JR-070RL', 'RES 0 OHM JUMPER 1/4W 1206', 'suggested',
                    f'trim land: fit a Bourns {trimmer} instead to adjust (wiper tied to '
                    'pin 3, clockwise raises it)')
        return ('Yageo', f'RC1206FR-07{resistor_code(value)}L',
                f'RES {value.upper()} OHM 1% 1/4W 1206', 'suggested',
                f'trim land: fit a Bourns {trimmer} instead to adjust (wiper tied to pin 3, '
                'clockwise raises it)')
    if footprint == 'R_Array_Convex_4x0402':
        return ('Yageo', f'YC124-JR-07{resistor_code(value)}L',
                f'RES ARRAY 4 RES {value.upper()} OHM 5% 0804', 'suggested',
                'four isolated 0402 elements, 2.0 x 1.0 mm')
    if footprint.startswith('R_'):
        if value == '15m':
            return PARTS[('15m', footprint)]
        series = {
            R1206: 'RC1206FR-07',
            R0402: 'RC0402FR-07',
            'R_0805_2012Metric': 'RC0805FR-07',
        }.get(footprint, 'RC0603FR-07')
        watts = {
            R1206: '1/4W',
            R0402: '1/16W',
            'R_0805_2012Metric': '1/8W',
        }.get(footprint, '1/10W')
        note = ''
        if value == '3.9k':
            return ('Yageo', 'RT0402BRD073K9L',
                    'RES 3.9K OHM 0.1% 25PPM 1/16W 0402', 'suggested',
                    'Rref for the ADS1220; the firmware assumes 3854 ohm '
                    '(PT1000_REF_R), so measure it and update the constant')
        if value == '4.02k':
            note = 'ACS37800 voltage divider tap'
        return (
            'Yageo',
            f'{series}{resistor_code(value)}L',
            f'RES {value.upper()} OHM 1% {watts} {footprint[2:6]}',
            'suggested',
            note,
        )
    if footprint.startswith('C_') and (value, footprint) in CAPS:
        mpn, description, note = CAPS[(value, footprint)]
        return (CAP_MAKERS.get(mpn, SAMSUNG) if mpn else '', mpn, description,
                'suggested' if mpn else 'none', note)
    if footprint == 'LED_0402_1005Metric':
        if value == 'red':
            return ('Kingbright', 'APHHS1005SURCK', 'LED RED (630 NM) CLEAR 0402 SMD',
                'suggested', 'fault indicators at ~1 mA; AlGaInP hyper red, '
                'Vf 1.95 V typ')
        return ('Kingbright', 'APHHS1005CGCK', 'LED GREEN (570 NM) CLEAR 0402 SMD',
                'suggested', 'indicators sized for ~1 mA (1.5k on 3.3 V, '
                '3.3k on 5 V, 13k on 15 V); AlGaInP green, Vf 2.1 V typ')
    if footprint.startswith('LED_0603'):
        color = re.search(r'\((\w+)\)', value)
        color = color.group(1) if color else 'red'
        maker, mpn, description = LED_PARTS[color]
        note = 'colour assumed red' if '(' not in value else ''
        return (maker, mpn, description, 'suggested' if mpn else 'none', note)
    if footprint == 'LED_1206_3216Metric':
        return (
            'SunLED', 'XZMDKVG55W-4',
            'LED RED/GREEN BICOLOR 1206 SMD, 2 pin anti-parallel', 'suggested',
            'AlGaInP red and green, 30 mA max each; XZMDKVG55W-7 is the same '
            'with a domed lens. Avoid XZMDKDGK55W-4 (green is InGaN, 25 mA max)')
    entry = PARTS.get((value, footprint))
    if entry is None:
        return ('', '', f'{value} {footprint}', 'none', 'no part chosen yet')
    return entry


CONNECTOR_FOOTPRINTS = (
    'PhoenixContact', 'TE_', 'JST_XH', 'Adafruit_', 'FanHeader_', 'Wurth_', 'Sullins_', 'Tensility_', 'SameSky_', 'TestPoint_Keystone',
    'XKB_',
)


def bom_value(ref, value, footprint):
    """The value a part is grouped and looked up by in the BOM."""
    if footprint == 'LED_0402_1005Metric':
        return 'red' if '(red)' in value or 'FAULT' in value else 'green'
    if footprint.startswith(CONNECTOR_FOOTPRINTS):
        return ''  # connectors group by footprint, not by label
    if footprint.startswith('SW_'):
        return 'TACTILE'
    if footprint == 'LED_1206_3216Metric':
        return 'RED/GREEN'
    if footprint == 'LED_Kingbright_APGB0607':
        return 'APGB0607G22R23C'
    return value


def resolve(value, footprint):
    """classify() with the ordered substitutes applied: (manufacturer, mpn,
    description, basis, note).
    """
    maker, mpn, description, basis, note = classify(value, footprint)
    if mpn in SUBSTITUTES:
        note = '; '.join(filter(None, [note, f'substitute for {mpn}']))
        mpn, maker = SUBSTITUTES[mpn]
        basis = 'ordered'
    return maker, mpn, description, basis, note


def compact_refs(refs):
    """Joins sorted references, shortening runs of three or more to first-last."""
    runs = []
    for ref in refs:
        prefix, number = sort_key(ref)
        if runs and runs[-1][0] == prefix and runs[-1][2] + 1 == number:
            runs[-1][2] = number
        else:
            runs.append([prefix, number, number])
    pieces = []
    for prefix, first, last in runs:
        if last - first >= 2:
            pieces.append(f'{prefix}{first}-{prefix}{last}')
        else:
            pieces.extend(f'{prefix}{number}' for number in range(first, last + 1))
    return ' '.join(pieces)


def write_mouser(rows):
    """The lines Digi-Key could not supply, as a Mouser upload."""
    mouser = [row for row in rows if set(row['Designators']) & set(MOUSER_LINES)]
    with MOUSER_OUTPUT.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['Mouser Part Number', 'Manufacturer Part Number',
                         'Manufacturer', 'Quantity', 'Description',
                         'Customer Reference', 'Notes'])
        for row in mouser:
            ref = row['Designators'][0]
            mpn = row['Manufacturer Part Number']
            writer.writerow([MOUSER_LINES[ref], MOUSER_MPN.get(mpn, mpn),
                             row['Manufacturer'], row['Quantity'],
                             row['Description'], row['Customer Reference'],
                             row['Notes']])


def use_imu_board():
    """Points the inputs and outputs at the IMU board project (imu/). Its
    references overlap the main board's, so the Mouser lines (keyed by
    reference) don't apply.
    """
    global OUTPUT, FULL_OUTPUT, CPL_OUTPUT, MOUSER_OUTPUT, BOARD, SCHEMATIC
    imu = KICAD_DIR / 'imu'
    OUTPUT = imu / 'bom' / 'imu_bom_digikey.csv'
    FULL_OUTPUT = imu / 'bom' / 'imu_bom_full.csv'
    CPL_OUTPUT = imu / 'bom' / 'imu_cpl.csv'
    MOUSER_OUTPUT = None
    BOARD = imu / 'imu.kicad_pcb'
    SCHEMATIC = imu / 'imu.kicad_sch'
    MOUSER_LINES.clear()


def main():
    if '--imu' in sys.argv[1:]:
        use_imu_board()
    # pad test points are bare copper; the through-hole ground loops are parts
    parts = [
        p for p in load_netlist()
        if not (p[0].startswith('TP') and 'TestPoint_Pad' in p[2])
    ]
    groups = collections.defaultdict(list)
    for ref, value, footprint in parts:
        groups[(bom_value(ref, value, footprint), footprint)].append(ref)
    # one line per orderable part, whatever value text its symbols carry
    by_part = {}
    for (value, footprint), refs in groups.items():
        maker, mpn, description, basis, note = resolve(value, footprint)
        key = (mpn, footprint) if mpn else (value, footprint)
        row = by_part.setdefault(key, {
            'Designators': [],
            'Manufacturer Part Number': mpn,
            'Manufacturer': maker,
            'Description': description,
            'Value': value,
            'Package': footprint,
            'MPN basis': basis,
            'Notes': '',
        })
        row['Designators'] += refs
        if note and note not in row['Notes']:
            row['Notes'] = '; '.join(filter(None, [row['Notes'], note]))
    rows = list(by_part.values())
    for row in rows:
        row['Designators'].sort(key=sort_key)
        row['sort'] = sort_key(row['Designators'][0])
        row['Quantity'] = len(row['Designators'])
        row['Customer Reference'] = compact_refs(row['Designators'])
    rows.sort(key=lambda row: row['sort'])
    OUTPUT.parent.mkdir(exist_ok=True)
    fields = [
        'Quantity', 'Manufacturer Part Number', 'Manufacturer', 'Description',
        'Customer Reference', 'Value', 'Package', 'MPN basis', 'Notes',
    ]
    with OUTPUT.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    if MOUSER_OUTPUT is not None:
        write_mouser(rows)
    total = sum(row['Quantity'] for row in rows)
    counts = collections.Counter(row['MPN basis'] for row in rows)
    print(f'{len(rows)} lines, {total} parts, bases {dict(counts)} -> {OUTPUT}')
    bom_lines, placed = write_jlcpcb_files(rows)
    print(f'JLCPCB: {bom_lines} BOM lines -> {FULL_OUTPUT}, '
          f'{placed} placements -> {CPL_OUTPUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
