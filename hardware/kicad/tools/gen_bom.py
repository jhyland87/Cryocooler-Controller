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

Usage: python3 tools/gen_bom.py   (needs kicad-cli)
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

# ── resistors (Yageo RC series, 1 %) ────────────────────────────────────────
R0603 = 'R_0603_1608Metric'
R1206 = 'R_1206_3216Metric'
R0402 = 'R_0402_1005Metric'


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
    ('4.7nF', 'C_0402_1005Metric'): (
        'CL05B472KB5NNNC', 'CAP CER 4700PF 50V X7R 0402',
        'LT8582 VC1 compensation'),
    ('2.2nF', 'C_0402_1005Metric'): (
        'CL05B222KB5NNNC', 'CAP CER 2200PF 50V X7R 0402',
        'LT8582 VC2 compensation'),
    ('1nF/C0G', 'C_0402_1005Metric'): (
        'CL05C102JB5NNNC', 'CAP CER 1000PF 50V C0G 0402',
        'across R6 + R170 (49.4k) in the sine gain stage'),
    ('47pF', 'C_0402_1005Metric'): (
        'CL05C470JB5NNNC', 'CAP CER 47PF 50V C0G 0402',
        'LT8582 VC high-frequency poles'),
    ('1uF', 'C_0603_1608Metric'): (
        'CL10A105KB8NNNC', 'CAP CER 1UF 50V X5R 0603', ''),
    ('4.7uF/25V', 'C_0805_2012Metric'): (
        'CL21A475KAQNNNE', 'CAP CER 4.7UF 25V X5R 0805',
        'LT8582 VIN1 / VIN2 input caps'),
    ('2.2uF/50V', 'C_1206_3216Metric'): (
        'CL31B225KBHNNNE', 'CAP CER 2.2UF 50V X7R 1206',
        'LT8582 inverting coupling cap C1 (sees VIN + |VOUT| = 21.5 V)'),
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
        'INA239 input filter across IN+/IN-'),
    ('10uF/25V', 'C_1206_3216Metric'): (
        'CL31A106KAHNNNE', 'CAP CER 10UF 25V X5R 1206', '12 V rail'),
    ('22uF/25V X7R', 'C_1210_3225Metric'): (
        'GRM32ER71E226KE15L', 'CAP CER 22UF 25V X7R 1210',
        'LT8582 outputs / LT3097 inputs and LT3097 outputs; the LT3097 needs '
        '>= 10 uF effective at 15 V DC bias (INN and both outputs have two in '
        'parallel; INP needs 4.7 uF), so check the DC-bias curve'),
    ('1uF/50V', 'C_1206_3216Metric'): (
        'CL31B105KBHNNNE', 'CAP CER 1UF 50V X7R 1206',
        'LT3097 SETP / SETN bypass (the pins sit at 14.7 V DC)'),
    ('22uF/10V', 'C_1206_3216Metric'): (
        'CL31A226KPHNNNE', 'CAP CER 22UF 10V X5R 1206', '5 V buck output'),
    ('22uF', 'C_1206_3216Metric'): (
        'CL31A226KPHNNNE', 'CAP CER 22UF 10V X5R 1206',
        'isolated 3.3 V output (needs 10 V or more)'),
    ('22uF/25V', 'C_1210_3225Metric'): (
        'CL32A226KAJNNNE', 'CAP CER 22UF 25V X5R 1210', '12 V rail'),
    ('47nF', 'C_1206_3216Metric'): (
        'C1206C473K5RACTU', 'CAP CER 0.047UF 50V X7R 1206',
        'ADP5071 compensation (C59)'),
    ('68nF', 'C_1206_3216Metric'): (
        'CC1206KRX7R9BB683', 'CAP CER 0.068UF 50V X7R 1206',
        'ADP5071 compensation (C61)'),
}
# makers for the caps that are not Samsung
CAP_MAKERS = {
    'C1206C473K5RACTU': 'Kemet',
    'CC1206KRX7R9BB683': 'Yageo',
    'GRM32ER71E226KE15L': 'Murata',
}

# ── everything else, keyed by (value, footprint) ────────────────────────────
# (manufacturer, MPN, description, basis, note)
PARTS = {
    ('100uF/25V', 'CP_Elec_8x10'): (
        'Panasonic', 'EEE-FK1E101P',
        'CAP ALUM 100UF 20% 25V SMD 8x10.2', 'suggested',
        'C6 sits on the input rail behind a 26 V TVS clamp; prefer 35 V '
        '(EEE-FK1V101P)'),
    ('22uF', 'CP_EIA-3528-21_Kemet-B'): (
        'Kemet', 'T491B226K016AT',
        'CAP TANT 22UF 10% 16V 3528-21 (B case)', 'suggested',
        '3.3 V rail; pin 1 is the + side'),
    ('1N4148W', 'D_SOD-123'): (
        'Diodes Incorporated', '1N4148W-7-F',
        'DIODE GEN PURP 75V 150MA SOD123', 'design', ''),
    ('DFLS240', 'D_PowerDI-123'): (
        'Diodes Incorporated', 'DFLS240-7',
        'DIODE SCHOTTKY 40V 2A POWERDI123', 'design', ''),
    ('SMBJ16A', 'D_SMB'): (
        'Littelfuse', 'SMBJ16A',
        'TVS DIODE 16VWM 26VC DO214AA', 'design', 'unidirectional'),
    ('WS2812B', 'LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm'): (
        'Adafruit', '1655',
        'LED RGB NEOPIXEL 5050 (WS2812/SK6812, 10 pack)', 'suggested',
        'Digi-Key has no WorldSemi WS2812B; this is the same pinout and '
        'protocol. Adafruit says hand-solder only, not for reflow, so '
        'check JLCPCB/LCSC for a WS2812B-compatible part if you assemble '
        'there'),
    ('5A backup', 'Fuse_Littelfuse-NANO2-451_453'): (
        'Littelfuse', '0453005.MR', 'FUSE BRD MNT 5A 125VAC/VDC 2SMD',
        'suggested',
        'NANO2 453 series, fast acting, 2410 package (6.1 x 2.7 mm); backup '
        'only: add a fuse at the PSU end (see DESIGN_REVIEW.md)'),
    ('SRP6050CA-4R7M', 'L_Bourns_SRP6050CA'): (
        'Bourns', 'SRP6050CA-4R7M', 'FIXED IND 4.7UH 10.5A 18.4MOHM SMD',
        'design', 'AP63205 buck inductor, shielded'),
    ('SRP7050TA-4R7M', 'L_Bourns_SRP7050TA'): (
        'Bourns', 'SRP7050TA-4R7M', 'FIXED IND 4.7UH 10A 30.8MOHM SMD',
        'design', 'LT8582 boost inductor, shielded; L_MIN about 2.9 uH'),
    ('MIE1W0505BGLVH-3R-Z', 'CONV_MIE1W0505BGLVH-3R-Z'): (
        'Monolithic Power Systems', 'MIE1W0505BGLVH-3R-Z',
        'ISOLATED DC/DC 1W 5V IN, 5V/3.3V OUT, LGA-12', 'design', ''),
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
    ('IRF4905S', 'TO-263-3_TabPin2'): (
        'Infineon', 'IRF4905STRLPBF', 'MOSFET P-CH 55V 74A D2PAK', 'design',
        ''),
    ('15m', 'R_2512_6332Metric'): (
        'Vishay Dale', 'WSL2512R0150FEA18', 'RES 0.015 OHM 1% 2W 2512',
        'suggested',
        'INA239 shunt, about 1.5 W at 10 A: needs 2 W or more; the "18" '
        'suffix is the 2 W part (WSL2512R0150FEA is 1 W)'),
    ('USB_C', 'USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'): (
        'GCT', 'USB4105-GF-A', 'USB-C 2.0 RECEPTACLE 16P, TOP MOUNT',
        'suggested', 'footprint is the GCT USB4105-xx-A'),
    # Right-angle connectors for the UCS 145-125 housing (plugs enter through
    # the side walls). Ratings from each maker's datasheet.
    ('', 'TE_2305908-2_1x02_P5.00mm_Horizontal_SMD'): (
        'TE Connectivity', '2305908-2', 'CONN HEADER R/A SMT 2POS 5MM, 15 A',
        'design', 'J11 amp out. SMT pads carry all plugging force. Mates with '
        'TE 2213934 / 2213935 / 2305909 series plugs (confirm the plug item number '
        'before ordering)'),
    ('', 'TE_2305908-3_1x03_P5.00mm_Horizontal_SMD'): (
        'TE Connectivity', '2305908-3', 'CONN HEADER R/A SMT 3POS 5MM, 15 A',
        'design', 'J12 cryocooler: + / - / GND (pin 3 is the plug\'s protective '
        'ground, tied to board GND). SMT pads carry all plugging force. Reported as '
        'last time buy: check stock. Mates with TE 2213934 / 2213935 / 2305909 '
        'series plugs (confirm the plug item number before ordering)'),
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
    ('74AHCT1G125', 'SOT-23-5'): (
        'Texas Instruments', 'SN74AHCT1G125DBVR', 'IC BUF NON-INVERT 5.5V SOT23-5',
        'suggested', '5 V level shifter for the WS2812B'),
    ('SN74LV1T34', 'SOT-23-5'): (
        'Texas Instruments', 'SN74LV1T34DBVR', 'IC BUF NON-INVERT 5.5V SOT23-5',
        'suggested', '1.8 V to 3.3 V buffers for DISP_CS and DISP_DC'),
    ('74LVC1G125', 'SOT-23-5'): (
        'Texas Instruments', 'SN74LVC1G125DBVR', 'IC BUF NON-INVERT 5.5V SOT23-5',
        'suggested', 'gates the SC18IS604 MISO'),
    ('ACS37800KMACTR-030B3-SPI', 'SOIC-16W_7.5x10.3mm_P1.27mm'): (
        'Allegro MicroSystems', 'ACS37800KMACTR-030B3-SPI',
        'SENSOR CURRENT/VOLTAGE 30A SPI 16SOIC', 'design', ''),
    ('AD633JRZ-R7', 'SOIC-8_3.9x4.9mm_P1.27mm'): (
        'Analog Devices', 'AD633JRZ-R7', 'IC ANALOG MULTIPLIER 8SOIC', 'design',
        ''),
    ('AD9833BRMZ', 'MSOP-10_3x3mm_P0.5mm'): (
        'Analog Devices', 'AD9833BRMZ', 'IC DDS WAVEFORM GEN 10MSOP', 'design',
        ''),
    ('LT8582EDKD#PBF', 'DFN-24-1EP_4x7mm_P0.5mm_EP2.64x6.44mm'): (
        'Analog Devices', 'LT8582EDKD#PBF',
        'IC REG BOOST/INVERTING DUAL 3A 24DFN', 'design',
        '#TRPBF is the reel; exposed pad 25 is GND'),
    ('MSD7342-103MLC', 'L_Coilcraft_MSD7342'): (
        'Coilcraft', 'MSD7342-103MLC', 'COUPLED INDUCTOR 10UH 1:1 SMD',
        'design', 'LT8582 inverting channel: 10 uH needed at duty ~0.80 '
        '(datasheet L_MIN ~5.6 uH)'),
    ('TSC2046EIPW', 'TSSOP-16_4.4x5mm_P0.65mm'): (
        'Texas Instruments', 'TSC2046EIPWR',
        'IC TOUCH SCREEN CTRLR 4-WIRE 16TSSOP', 'design', ''),
    ('FH12-14S-0.5SH(55)',
     'Hirose_FH12-14S-0.5SH_1x14-1MP_P0.50mm_Horizontal'): (
        'Hirose', 'FH12-14S-0.5SH(55)', 'CONN FFC BOTTOM 14POS 0.50MM R/A',
        'design', 'display FPC (Phoenix datasheet 109921); check the FFC '
        'contact side so pin 1 lands on pin 1'),
    ('RJSSE-5380', 'RJ45_Amphenol_RJSSE-5380_Horizontal'): (
        'Amphenol', 'RJSSE-5380', 'CONN MOD JACK 8P8C R/A SHIELDED SMD',
        'design', 'J14 IMU cable; plain jack, no magnetics (drawing '
        'P-RJSSE-5380 rev E)'),
    ('LT3097ADJC', 'DFN-22-2EP_6x3mm_P0.5mm_LT3097'): (
        'Analog Devices', 'LT3097ADJC#PBF',
        'IC REG LINEAR POS/NEG ADJ 500MA 22DFN', 'suggested',
        '#PBF is the tube, #TRPBF the reel; DFN with two exposed pads '
        '(23 = GND, 24 = INN = -16.5 V)'),
    ('ADS1220IPW', 'TSSOP-16_4.4x5mm_P0.65mm'): (
        'Texas Instruments', 'ADS1220IPWR', 'IC ADC 24BIT SIGMA-DELTA 16TSSOP',
        'design', ''),
    ('AP63205WU-7', 'TSOT-23-6'): (
        'Diodes Incorporated', 'AP63205WU-7', 'IC REG BUCK 5V 2A TSOT26',
        'design', ''),
    ('CL25N8-G', 'SOT-89-3'): (
        'Microchip', 'CL25N8-G', 'IC LED DRIVER CONSTANT CURRENT 25MA SOT89',
        'design', ''),
    ('EMC2303-x-KP', 'VQFN-12-1EP_4x4mm_P0.8mm_EP2.1x2.1mm_ThermalVias'): (
        'Microchip', 'EMC2303-1-KP-TR', 'IC FAN CONTROLLER 3CH 12QFN',
        'suggested',
        'confirm the "-1" suffix gives the 0x4D address with the 33k ADDR_SEL '
        'resistor (datasheet Table 5-1)'),
    ('ESP32-S3-WROOM-2-N32R16V', 'ESP32-S3-WROOM-2'): (
        'Espressif', 'ESP32-S3-WROOM-2-N32R16V',
        'MODULE ESP32-S3 32MB FLASH 16MB PSRAM', 'design', ''),
    ('INA239AIDGSR', 'TSSOP-10_3x3mm_P0.5mm'): (
        'Texas Instruments', 'INA239AIDGSR', 'IC CURRENT/POWER MONITOR 10VSSOP',
        'design', ''),
    ('ISO7741DW', 'SOIC-16W_7.5x10.3mm_P1.27mm'): (
        'Texas Instruments', 'ISO7741DWR', 'DIGITAL ISOLATOR 4CH 16SOIC',
        'suggested', 'DWR is the reel; DW is the tube'),
    ('LM66100', 'SOT-363_SC-70-6'): (
        'Texas Instruments', 'LM66100DCKR', 'IC IDEAL DIODE 5.5V 1.5A SC70-6',
        'design', '+5V / USB VBUS OR into +5V_OR'),
    ('LD1117S33TR', 'SOT-223-3_TabPin2'): (
        'STMicroelectronics', 'LD1117S33TR', 'IC REG LINEAR 3.3V 800MA SOT223',
        'design', ''),
    ('LM4040DBZ-2.5', 'SOT-23'): (
        'Texas Instruments', 'LM4040B25IDBZR',
        'IC VREF SHUNT 2.5V 0.2% SOT23-3', 'suggested',
        'B grade (0.2 %) for the DAC reference; C or D grade also works'),
    ('LM4040DBZ-5', 'SOT-23'): (
        'Texas Instruments', 'LM4040D50IDBZR',
        'IC VREF SHUNT 5V 1% SOT23-3', 'suggested',
        'only biases the LTC2954 KILL input; 1 % is plenty'),
    ('LTC2954CTS8-2', 'SOT-23-8'): (
        'Analog Devices', 'LTC2954CTS8-2#TRMPBF',
        'IC PUSHBUTTON ON/OFF CONTROLLER TSOT8', 'suggested',
        'C grade, -2 version (EN# output)'),
    ('MCP4921-E/SN', 'SOIC-8_3.9x4.9mm_P1.27mm'): (
        'Microchip', 'MCP4921-E/SN', 'IC DAC 12BIT SPI 8SOIC', 'design', ''),
    ('OPA1656ID', 'SOIC-8_3.9x4.9mm_P1.27mm'): (
        'Texas Instruments', 'OPA1656ID', 'IC OPAMP AUDIO 2CIRC 8SOIC',
        'design', ''),
    ('OPA188ID', 'SOIC-8_3.9x4.9mm_P1.27mm'): (
        'Texas Instruments', 'OPA188AID', 'IC OPAMP ZERO-DRIFT 1CIRC 8SOIC',
        'design', 'the schematic value is OPA188ID; the orderable SOIC part is '
        'OPA188AID (tube) or OPA188AIDR (reel). Digi-Key offers OPA180ID as a '
        'substitute: it is a different part, do not take it'),
    ('MCP23S08-E/ML', 'QFN-20-1EP_4x4mm_P0.5mm_EP2.7x2.7mm'): (
        'Microchip', 'MCP23S08-E/ML', 'IC I/O EXPANDER SPI 8B 20QFN', 'suggested',
        'stock not checked; MCP23S08T-E/ML is the reel'),
    ('SC18IS604PW', 'TSSOP-16_4.4x5mm_P0.65mm'): (
        'NXP', 'SC18IS604PWJ', 'IC SPI TO I2C BRIDGE 16TSSOP', 'suggested',
        'PWJ is the reel'),
    ('SG-8002CA-PH 25MHz', 'Oscillator_SMD_SeikoEpson_SG8002CA-4Pin_7.0x5.0mm'): (
        'Epson', 'SG-8002CA 25.0000M-PHCLX', 'OSC 25.000MHZ CMOS 5V SMD 7x5',
        'suggested',
        'PH = 5 V CMOS with output enable; the PHBB variant is discontinued, '
        'PHCLX is +/-100 ppm which is plenty for the AD9833 clock'),
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
    'TL3342F160QG': ('TL3342F160QG/TR', 'E-Switch'),
    'LTC2954CTS8-2#TRMPBF': ('LTC2954CTS8-2#TRPBF', 'Analog Devices'),
    'SN74LVC1G125DBVR': ('74LVC1G125DBVTG4', 'Texas Instruments'),
}

# Lines Digi-Key could not supply: Mouser order (Mouser part number is known
# only where a listing was seen).
MOUSER_LINES = {
    'L1': '',
    'PS1': '',
    'U1': '356-SP32S3WM2N32R16V',
    'U3': '732-SG-82CA25M-PHCLX',
    'U9': '595-OPA188AIDR',
    'U15': '621-AP63205WU-7',
    'U23': '595-INA239AIDGSR',
}
MOUSER_MPN = {'OPA188AID': 'OPA188AIDR'}
MOUSER_OUTPUT = KICAD_DIR / 'bom' / 'cryocooler_bom_mouser.csv'

# JLCPCB: manufacturer part number -> LCSC part number (C-number). Fill in as
# parts are matched in JLCPCB's BOM upload; blank cells are left for the upload.
LCSC_PARTS = {}

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
                str(KICAD_DIR / 'cryocooler.kicad_sch'),
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
                ','.join(row['Customer Reference'].split()),
                jlcpcb_footprint(row['Package']),
                LCSC_PARTS.get(mpn, ''),
                '',
            ])
    bom_refs = {ref for row in rows for ref in row['Customer Reference'].split()}
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
    if footprint == 'SW_SPST_TL3342':
        return (
            'E-Switch', 'TL3342F160QG', 'SWITCH TACTILE SPST-NO 0.05A 12V SMD',
            'suggested', 'footprint is the TL3342 family (3.5 x 6 mm)')
    entry = PARTS.get((value, footprint))
    if entry is None:
        return ('', '', f'{value} {footprint}', 'none', 'no part chosen yet')
    return entry


CONNECTOR_FOOTPRINTS = (
    'PhoenixContact', 'TE_', 'JST_XH', 'Adafruit_', 'FanHeader_', 'Wurth_', 'Sullins_', 'Tensility_', 'SameSky_', 'TestPoint_Keystone',
)


def bom_value(ref, value, footprint):
    """The value a part is grouped and looked up by in the BOM."""
    if footprint == 'LED_0402_1005Metric':
        return 'red' if '(red)' in value or 'FAULT' in value else 'green'
    if footprint.startswith(CONNECTOR_FOOTPRINTS):
        return ''  # connectors group by footprint, not by label
    if footprint.startswith('SW_SPST'):
        return 'TACTILE'
    if footprint == 'LED_1206_3216Metric':
        return 'RED/GREEN'
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


def main():
    # pad test points are bare copper; the through-hole ground loops are parts
    parts = [
        p for p in load_netlist()
        if not (p[0].startswith('TP') and 'TestPoint_Pad' in p[2])
    ]
    groups = collections.defaultdict(list)
    for ref, value, footprint in parts:
        groups[(bom_value(ref, value, footprint), footprint)].append(ref)
    rows = []
    for (value, footprint), refs in groups.items():
        refs.sort(key=sort_key)
        maker, mpn, description, basis, note = resolve(value, footprint)
        rows.append(
            {
                'sort': sort_key(refs[0]),
                'Quantity': len(refs),
                'Manufacturer Part Number': mpn,
                'Manufacturer': maker,
                'Description': description,
                'Customer Reference': ' '.join(refs),
                'Value': value,
                'Package': footprint,
                'MPN basis': basis,
                'Notes': note,
            }
        )
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
    mouser = [row for row in rows if set(row['Customer Reference'].split())
              & set(MOUSER_LINES)]
    with MOUSER_OUTPUT.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['Mouser Part Number', 'Manufacturer Part Number',
                         'Manufacturer', 'Quantity', 'Description',
                         'Customer Reference', 'Notes'])
        for row in mouser:
            ref = row['Customer Reference'].split()[0]
            mpn = row['Manufacturer Part Number']
            writer.writerow([MOUSER_LINES[ref], MOUSER_MPN.get(mpn, mpn),
                             row['Manufacturer'], row['Quantity'],
                             row['Description'], row['Customer Reference'],
                             row['Notes']])
    total = sum(row['Quantity'] for row in rows)
    counts = collections.Counter(row['MPN basis'] for row in rows)
    print(f'{len(rows)} lines, {total} parts, bases {dict(counts)} -> {OUTPUT}')
    bom_lines, placed = write_jlcpcb_files(rows)
    print(f'JLCPCB: {bom_lines} BOM lines -> {FULL_OUTPUT}, '
          f'{placed} placements -> {CPL_OUTPUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
