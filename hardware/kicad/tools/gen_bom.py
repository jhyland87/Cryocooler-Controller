"""Builds the Digi-Key BOM (bom/cryocooler_bom_digikey.csv) from the schematic.

Quantities and designators come from the exported netlist, so they cannot drift
from the design. Part numbers come from the tables below:

* 'design'    the schematic value is the orderable part (ICs, FETs, diodes).
* 'suggested' a part picked for the value, package and rating; verify the
              match in Digi-Key's BOM Manager before ordering.
* 'none'      no part number; use the description (and notes) to choose.

Test points are bare PCB pads and are left out.

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

# ── resistors (Yageo RC series, 1 %) ────────────────────────────────────────
R0603 = 'R_0603_1608Metric'
R1206 = 'R_1206_3216Metric'


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
    ('4.7uF/25V', 'C_1206_3216Metric'): (
        'CL31A475KAHNNNE', 'CAP CER 4.7UF 25V X5R 1206', '+/-15 V LDO outputs'),
    ('22uF/10V', 'C_1206_3216Metric'): (
        'CL31A226KPHNNNE', 'CAP CER 22UF 10V X5R 1206', '5 V buck output'),
    ('22uF', 'C_1206_3216Metric'): (
        'CL31A226KPHNNNE', 'CAP CER 22UF 10V X5R 1206',
        'isolated 3.3 V output (needs 10 V or more)'),
    ('22uF/25V', 'C_1210_3225Metric'): (
        'CL32A226KAJNNNE', 'CAP CER 22UF 25V X5R 1210', '12 V rail'),
    ('10uF/50V', 'C_1210_3225Metric'): (
        'CL32B106KBJNNNE', 'CAP CER 10UF 50V X7R 1210',
        '+/-16.5 V rails (50 V needed: DC bias derating)'),
    ('100pF', 'C_1206_3216Metric'): (
        '', 'CAP CER 100PF 50V C0G/NP0 1206', '-15 V rail, C0G dielectric'),
    ('47nF', 'C_1206_3216Metric'): (
        '', 'CAP CER 0.047UF 50V X7R 1206',
        'ADP5071 compensation, X7R or C0G'),
    ('68nF', 'C_1206_3216Metric'): (
        '', 'CAP CER 0.068UF 50V X7R 1206',
        'ADP5071 compensation, X7R or C0G'),
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
        'Worldsemi', '',
        'LED RGB WS2812B 5050 addressable', 'none',
        'search "WS2812B"; check it is the 5 V PLCC4 5.0x5.0 mm part'),
    ('5A backup', 'Fuse_1812_4532Metric'): (
        '', '', 'FUSE 5A 1812 SMD (32 VDC or more)', 'none',
        'backup only: the supply can deliver far more; add a fuse at the '
        'PSU end (see DESIGN_REVIEW.md)'),
    ('SRN6045TA-4R7M', 'L_Bourns_SRN6045TA'): (
        'Bourns', 'SRN6045TA-4R7M', 'FIXED IND 4.7UH 4.5A 26MOHM SMD',
        'design', ''),
    ('SRN8040TA-3R3M', 'L_Bourns_SRN8040TA'): (
        'Bourns', 'SRN8040TA-3R3M', 'FIXED IND 3.3UH SMD', 'design',
        'ADP5071 boost inductor'),
    ('SRN8040TA-6R8M', 'L_Bourns_SRN8040TA'): (
        'Bourns', 'SRN8040TA-6R8M', 'FIXED IND 6.8UH SMD', 'design',
        'ADP5071 inverting inductor'),
    ('MIE1W0505BGLVH-3R-Z', 'CONV_MIE1W0505BGLVH-3R-Z'): (
        'Monolithic Power Systems', 'MIE1W0505BGLVH-3R-Z',
        'ISOLATED DC/DC 1W 5V IN, 5V/3.3V OUT, LGA-12', 'design', ''),
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
        '', '', 'RES 0.015 OHM 1% 2W 2512 (3W is better)', 'none',
        'INA239 shunt, about 1.5 W at 10 A: needs 2 W or more; low TCR'),
    ('USB_C', 'USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'): (
        'GCT', 'USB4105-GF-A', 'USB-C 2.0 RECEPTACLE 16P, TOP MOUNT',
        'suggested', 'footprint is the GCT USB4105-xx-A'),
    ('', 'TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'): (
        'Phoenix Contact', '1729128', 'TERM BLOCK 2POS 5.08MM, MKDS 1,5/ 2-5,08',
        'suggested', 'screw terminals: 12 V in, amplifier REM, amplifier signal, amp out, cryocooler out'),
    ('', 'Molex_KK-254_AE-6410-04A_1x04_P2.54mm_Vertical'): (
        'Molex', '0022232041', 'CONN HEADER KK 254 VERT 4POS', 'suggested', 'fan and pump (4-pin PWM)'),
    ('', 'Molex_KK-254_AE-6410-03A_1x03_P2.54mm_Vertical'): (
        'Molex', '0022232031', 'CONN HEADER KK 254 VERT 3POS', 'suggested', ''),
    ('', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): (
        'JST', 'B2B-XH-A(LF)(SN)', 'CONN HEADER XH VERT 2POS 2.5MM',
        'suggested', 'NTC, panel button, compressor relay'),
    ('', 'JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'): (
        'JST', 'B4B-XH-A(LF)(SN)', 'CONN HEADER XH VERT 4POS 2.5MM',
        'suggested', ''),
    ('74AHCT1G125', 'SOT-23-5'): (
        'Texas Instruments', 'SN74AHCT1G125DBVR', 'IC BUF NON-INVERT 5.5V SOT23-5',
        'suggested', '5 V level shifter for the WS2812B'),
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
    ('ADP5071AREZ', 'ETSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3x4.2mm'): (
        'Analog Devices', 'ADP5071AREZ', 'IC REG DC DC +/- 16.5V 20TSSOP-EP',
        'design', ''),
    ('ADP7142AUJZ', 'TSOT-23-5'): (
        'Analog Devices', 'ADP7142AUJZ-R7', 'IC REG LINEAR ADJ 200MA TSOT5',
        'suggested', 'adjustable version, +15 V'),
    ('ADP7182AUJZ', 'TSOT-23-5'): (
        'Analog Devices', 'ADP7182AUJZ-R7', 'IC REG LINEAR NEG ADJ 200MA TSOT5',
        'suggested', 'adjustable version, -15 V'),
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
    ('LSM6DSOXTR', 'LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y'): (
        'STMicroelectronics', 'LSM6DSOXTR', 'IMU 6-AXIS SPI/I2C 14LGA', 'design',
        ''),
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
        'Texas Instruments', 'OPA188ID', 'IC OPAMP ZERO-DRIFT 1CIRC 8SOIC',
        'design', ''),
    ('SC18IS604PW', 'TSSOP-16_4.4x5mm_P0.65mm'): (
        'NXP', 'SC18IS604PWJ', 'IC SPI TO I2C BRIDGE 16TSSOP', 'suggested',
        'PWJ is the reel'),
    ('SG-8002CA-PH 25MHz', 'Oscillator_SMD_SeikoEpson_SG8002CA-4Pin_7.0x5.0mm'): (
        'Epson', '', 'OSC 25.000MHZ CMOS 5V SMD 7x5', 'none',
        'SG-8002CA, PH = 5 V CMOS with output enable; pick the 25.000000 MHz PH '
        'variant'),
    ('USBLC6-2SC6', 'SOT-23-6'): (
        'STMicroelectronics', 'USBLC6-2SC6', 'TVS DIODE 5.25V 17V SOT23-6',
        'design', ''),
}

LED_PARTS = {
    'green': ('Lite-On', 'LTST-C190KGKT', 'LED GREEN CLEAR 0603 SMD'),
    'red': ('Lite-On', 'LTST-C190KRKT', 'LED RED CLEAR 0603 SMD'),
    'yellow': ('Lite-On', 'LTST-C190KSKT', 'LED YELLOW CLEAR 0603 SMD'),
    'white': ('', '', 'LED WHITE CLEAR 0603 SMD'),
}


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


def sort_key(ref):
    match = re.match(r'([A-Z]+)(\d+)', ref)
    return (match.group(1), int(match.group(2)))


def classify(value, footprint):
    """Returns (manufacturer, mpn, description, basis, note) for one group."""
    if footprint.startswith('R_'):
        if value == '15m':
            return PARTS[('15m', footprint)]
        series = 'RC1206FR-07' if footprint == R1206 else 'RC0603FR-07'
        note = ''
        if value == '3.9k':
            note = ('Rref for the ADS1220: use 0.1 % 25 ppm (for example Yageo '
                    'RT0603BRD073K9L); the firmware assumes 3854 ohm, so '
                    'measure it')
        if value == '4.02k':
            note = 'ACS37800 voltage divider tap'
        return (
            'Yageo',
            f'{series}{resistor_code(value)}L',
            f'RES {value.upper()} OHM 1% 1/10W {footprint[2:6]}',
            'suggested',
            note,
        )
    if footprint.startswith('C_') and (value, footprint) in CAPS:
        mpn, description, note = CAPS[(value, footprint)]
        return (SAMSUNG if mpn else '', mpn, description,
                'suggested' if mpn else 'none', note)
    if footprint.startswith('LED_0603'):
        color = re.search(r'\((\w+)\)', value)
        color = color.group(1) if color else 'red'
        maker, mpn, description = LED_PARTS[color]
        note = 'colour assumed red' if '(' not in value else ''
        return (maker, mpn, description, 'suggested' if mpn else 'none', note)
    if footprint == 'LED_1206_3216Metric':
        return (
            '', '', 'LED RED/GREEN BICOLOR 1206 SMD (common anode or two-pin '
            'anti-parallel, 2 pin)', 'none',
            'two-pin anti-parallel bicolor (Device:LED_Dual_Bidirectional)')
    if footprint == 'SW_SPST_TL3342':
        return (
            'E-Switch', 'TL3342F160QG', 'SWITCH TACTILE SPST-NO 0.05A 12V SMD',
            'suggested', 'footprint is the TL3342 family (3.5 x 6 mm)')
    entry = PARTS.get((value, footprint))
    if entry is None:
        return ('', '', f'{value} {footprint}', 'none', 'no part chosen yet')
    return entry


def main():
    parts = [p for p in load_netlist() if not p[0].startswith('TP')]
    groups = collections.defaultdict(list)
    for ref, value, footprint in parts:
        if footprint.startswith(('TerminalBlock', 'Molex_KK', 'JST_XH')):
            value = ''  # connectors group by footprint, not by label
        if footprint.startswith('SW_SPST'):
            value = 'TACTILE'
        if footprint == 'LED_1206_3216Metric':
            value = 'RED/GREEN'
        groups[(value, footprint)].append(ref)
    rows = []
    for (value, footprint), refs in groups.items():
        refs.sort(key=sort_key)
        maker, mpn, description, basis, note = classify(value, footprint)
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
    total = sum(row['Quantity'] for row in rows)
    counts = collections.Counter(row['MPN basis'] for row in rows)
    print(f'{len(rows)} lines, {total} parts, bases {dict(counts)} -> {OUTPUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
