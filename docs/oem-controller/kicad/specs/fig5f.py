"""FIG 5F - voltage references (+5VA, 10V, REF_1) and power supply (UR3 DC-DC, regulators, J12).

Redrawn to the drawing rules: one child sheet per function, wires inside each, and
hierarchical labels / sheet pins between them. Parts, values, pins and nets are as
transcribed; see ../TRANSCRIPTION_NOTES.md for the anomalies.
"""

from oemsch import P, child, port, tap

TITLE = 'FIG 5F - References and power supply'
SOURCE = 'US6098409 sheets 12-13 of 25 (PDF p13-14), FIG 5F-1/5F-2'
PAPER = 'A3'
REDRAWN = True

SYMBOLS = {
    'F5F_URE319': {'left': [('2', 'VDD')], 'right': [('6', 'OUT')], 'bottom': [('4', 'GND')],
                   'prefix': 'U'},
    'F5F_AD2710': {'left': [('11', 'VDD')], 'right': [('13', 'OUT')], 'bottom': [('7', 'GND')],
                   'prefix': 'U'},
    # inputs left, generated rails right, common at the bottom
    'F5F_UR3': {'left': [('3', '+INPUT'), None, ('2', '-INPUT')],
                'right': [('4', '+15V'), None, ('6', '-15V')],
                'bottom': [('5', '+/-')], 'prefix': 'U'},
    # Three-terminal regulators: no refs, part numbers or pin numbers printed. Terminals
    # lettered "I" (input), "0" (output) and "0" (common); pin "numbers" here are IN/OUT/COM.
    'F5F_REG': {'left': [('IN', 'I')], 'right': [('OUT', '0')], 'bottom': [('COM', '0')],
                'prefix': 'U'},
}

_LT1007 = {'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'}
_V_MINUS = 'V- pin number not printed (4 assumed for LT1007)'
_REG = 'No ref / part number printed; terminals lettered 0 (out), 0 (common), I (in)'
_GND_D = ('5F_GND_D = net of the filled-triangle ground symbol (the "D" side of the '
          'A/GND/D split through R229C)')

# ── 10 V reference: U47 / U50 in parallel -> REF_1 ──
REF10 = child(
    'ref10', '10 V reference (U47, U50)', short='10V REF', paper='A4', at=(30, 40),
    parts=[
        P('R230', '10K', 'R', at=(35, 50), rot=180, pins={'1': '5F_REF_VIN', '2': '+15V'},
          note='Lower end runs off sheet 12 and continues on sheet 13 to the +15V rail (match line)',
          desc='Inferred from the circuit: series resistor feeding the U47/U50 reference input '
               'from +15V; with C148/C149 an RC filter on 5F_REF_VIN'),
        P('C148', '2.2uF/25V', 'CP', at=(50, 70), pins={'1': '5F_REF_VIN', '2': 'GND'},
          desc='Inferred from the circuit: filter capacitor on the reference input 5F_REF_VIN (with R230)'),
        P('C149', '2.2uF/25V', 'C', at=(65, 70), pins={'1': '5F_REF_VIN', '2': 'GND'},
          desc='Inferred from the circuit: filter capacitor on the reference input 5F_REF_VIN (with R230)'),
        P('U47', 'URE319', 'F5F_URE319', at=(95, 60), probable='VRE310 (Thaler 10 V ref, DIP pins 2/4/6)',
          pins={'2': '5F_REF_VIN', '6': 'REF_1', '4': 'GND'},
          note='Value printed "URE319"; in parallel with U50 (alternate footprints?)',
          desc='Inferred from the circuit: voltage reference driving REF_1, wired in parallel with '
               'U50 (probably alternative parts for one position)'),
        P('U50', 'AD2710', 'F5F_AD2710', at=(95, 95), probable='AD2710 10 V reference',
          pins={'11': '5F_REF_VIN', '13': 'REF_1', '7': 'GND'},
          desc='Inferred from the circuit: voltage reference driving REF_1, wired in parallel with '
               'U47 (probably alternative parts for one position)'),
        P('C112', '2.2uF/25V', 'C', at=(125, 66), pins={'1': 'REF_1', '2': 'GND'},
          desc='Inferred from the circuit: output capacitor on REF_1'),
    ],
    ports=[port('REF_1', 'output', at=(140, 58), facing='right')],
    wires=[
        ('R230.1', 'U47.2', 'vh'), ('C148.1', 'U47.2', 'vh'), ('C149.1', 'U47.2', 'vh'),
        ('U50.11', 'U47.2', 'vh'),
        ('U47.6', '@REF_1'), ('U50.13', 'U47.6', [(115, 93), (115, 58)]),
        ('C112.1', '@REF_1', 'vh'),
    ],
    names={'5F_REF_VIN': 'U47.2'},
    notes=[("R230's +15V end continues across the sheet 12/13 match line to the +15V rail.", 15, 125)],
)

# ── +5VA: U55 + NPN pass transistor, R168 -> +SUREF ──
REF5VA = child(
    'ref5va', '+5VA reference buffer (U55, QX1)', short='+5VA', paper='A4', at=(120, 36),
    parts=[
        P('R252', '4.90K', 'R', at=(50, 92), rot=270, pins={'1': '5F_U55_NINV', '2': 'REF_1'},
          desc='Inferred from the circuit: upper leg of the REF_1 divider (with R251) setting the '
               'U55 non-inverting input'),
        P('R251', '4.90K', 'R', at=(65, 102), pins={'1': '5F_U55_NINV', '2': 'GND'},
          desc='Inferred from the circuit: lower leg of the REF_1 divider (with R252) at the U55 '
               'non-inverting input'),
        P('U55', 'LT1007', 'OPAMP', at=(85, 90), pinmap=_LT1007, note=_V_MINUS, text=(7, 3),
          pins={'2': '5F_U55_INV', '3': '5F_U55_NINV', '6': '5F_U55_OUT', '7': '+15V', '4': '-15V'},
          desc='Inferred from the circuit: error amplifier of the +5VA regulator; drives QX1 so '
               'that +5VA (fed back through R271) follows the REF_1 divider'),
        P('C152', '.1uF', 'C', at=(85, 72), rot=270, pins={'1': '5F_U55_OUT', '2': '5F_U55_INV'},
          desc='Inferred from the circuit: U55 feedback (compensation) capacitor, output to inverting input'),
        P('R271', '4.90K', 'R', at=(73, 58), pins={'1': '+5VA', '2': '5F_U55_INV'},
          desc='Inferred from the circuit: feeds +5VA back to the U55 inverting input'),
        P('R273', '4.75K', 'R', at=(118, 90), rot=270, pins={'1': '5F_Q_B', '2': '5F_U55_OUT'},
          desc='Inferred from the circuit: base resistor from U55 output to the QX1 pass transistor'),
        P('QX1', '?', 'NPN', at=(135, 90), pins={'B': '5F_Q_B', 'C': '5F_Q_C', 'E': '+5VA'},
          note='NPN pass transistor; no ref or part number printed',
          desc='Inferred from the circuit: emitter-follower pass transistor that sources +5VA'),
        P('R272', '1K', 'R', at=(137, 74), pins={'1': '+15V', '2': '5F_Q_C'},
          desc='Inferred from the circuit: collector resistor feeding QX1 from +15V'),
        P('C163', '.1uF', 'C', at=(150, 86), pins={'1': '5F_Q_C', '2': 'GND'},
          desc='Inferred from the circuit: bypass capacitor on the QX1 collector supply'),
        P('C159', '2.2uF/25V', 'CP', at=(150, 110), text=(2, -1), pins={'1': '+5VA', '2': 'GND'},
          desc='Inferred from the circuit: bulk output capacitor on +5VA'),
        P('C157', '.1uF', 'C', at=(163, 110), pins={'1': '+5VA', '2': 'GND'},
          desc='Inferred from the circuit: high-frequency output capacitor on +5VA'),
        P('R168', '?', 'R', at=(180, 105), rot=270, pins={'1': '+SUREF', '2': '+5VA'},
          note='No value printed',
          desc='Inferred from the circuit: series resistor from +5VA to the +SUREF output; role unknown '
               'beyond that (no value printed)'),
        P('C130', '.1uF', 'C', at=(50, 140), pins={'1': '+15V', '2': 'GND'},
          desc='Inferred from the circuit: U55 +15V supply decoupling'),
        P('C151', '.1uF', 'C', at=(65, 140), pins={'1': '-15V', '2': 'GND'},
          desc='Inferred from the circuit: U55 -15V supply decoupling'),
    ],
    ports=[port('REF_1', 'input', at=(30, 92), facing='left')],
    # printed as an off-page flag, but no transcribed figure uses it: it ends in a label here
    long_nets={'+SUREF'},
    taps=[tap('p5va', '+5VA', (170, 100))],
    wires=[
        ('@REF_1', 'R252.2'), ('R252.1', 'U55.3'), ('R251.1', 'U55.3', 'vh'),
        ('R271.2', 'U55.2', [(73, 88)]), ('C152.2', 'U55.2', [(73, 72), (73, 88)]),
        ('U55.6', 'R273.2'), ('C152.1', 'U55.6', [(97, 72), (97, 90)]),
        ('R273.1', 'QX1.B'), ('R272.2', 'QX1.C'), ('C163.1', 'R272.2', 'vh'),
        ('QX1.E', 'C159.1', 'vh'), ('C157.1', 'C159.1'), ('R168.2', 'C157.1'),
        ('@p5va', 'C157.1', 'vh'),
        ('C130.2', 'C151.2'),
    ],
    names={'+5VA': ['@p5va', 'R271.1'], '5F_U55_INV': 'R271.2', '5F_U55_OUT': 'R273.2',
           '5F_Q_C': 'R272.2',
           # unnamed before the redraw; a name would be more than a sheet-path rename
           '5F_U55_NINV': None, '5F_Q_B': None},
    notes=[('U55 DECOUPLING CAPACITORS', 42, 128),
           ('"+SUREF" as printed (probably +5VREF).', 15, 150)],
)

# ── 10V: U45 inverter -> 10V ──
REF10V = child(
    'ref10v', '10V output (U45)', short='10V OUT', paper='A4', at=(120, 66),
    parts=[
        P('R237', '4.90K', 'R', at=(50, 88), rot=270, pins={'1': '5F_U45_INV', '2': 'REF_1'},
          desc='Inferred from the circuit: input resistor from REF_1 to the U45 inverting input'),
        P('U45', 'LT1007', 'OPAMP', at=(85, 90), pinmap=_LT1007, note=_V_MINUS, text=(7, 3),
          pins={'2': '5F_U45_INV', '3': '5F_U45_NINV', '6': '5F_U45_OUT', '7': '+15V', '4': '-15V'},
          desc='Inferred from the circuit: amplifier driving the 10V rail (+10V) through R250, '
               'with R236 feedback from the rail'),
        P('R235', '2.40K', 'R', at=(66, 102), pins={'1': '5F_U45_NINV', '2': 'GND'},
          desc='Inferred from the circuit: U45 non-inverting input resistor to ground'),
        P('C112B', '2.2uF/25V', 'C', at=(85, 72), rot=270, pins={'1': '5F_U45_OUT', '2': '5F_U45_INV'},
          printed='C112', note='C112 printed twice on 5F-1',
          desc='Inferred from the circuit: U45 feedback capacitor, output to inverting input'),
        P('R236', '4.90K', 'R', at=(73, 58), pins={'1': '+10V', '2': '5F_U45_INV'},
          desc='Inferred from the circuit: feedback resistor from the +10V rail to the U45 inverting input'),
        P('R250', '1K', 'R', at=(118, 90), rot=270, pins={'1': '+10V', '2': '5F_U45_OUT'},
          desc='Inferred from the circuit: series resistor from the U45 output to the +10V rail'),
        P('C147', '1uF90V', 'CP', at=(135, 100), pins={'1': '+10V', '2': 'GND'},
          desc='Inferred from the circuit: bulk capacitor on the +10V rail'),
        P('C137', '.1uF', 'C', at=(148, 100), pins={'1': '+10V', '2': 'GND'},
          desc='Inferred from the circuit: decoupling capacitor on the +10V rail; the loads it serves '
               'are on other figures and not identified (role unknown beyond that)'),
        P('C70', '.1uF', 'C', at=(161, 100), pins={'1': '+10V', '2': 'GND'},
          desc='Inferred from the circuit: decoupling capacitor on the +10V rail; the loads it serves '
               'are on other figures and not identified (role unknown beyond that)'),
        P('C41', '.1uF', 'C', at=(174, 100), pins={'1': '+10V', '2': 'GND'},
          desc='Inferred from the circuit: decoupling capacitor on the +10V rail; the loads it serves '
               'are on other figures and not identified (role unknown beyond that)'),
        P('C34', '.1uF', 'C', at=(187, 100), pins={'1': '+10V', '2': 'GND'},
          desc='Inferred from the circuit: decoupling capacitor on the +10V rail; the loads it serves '
               'are on other figures and not identified (role unknown beyond that)'),
        P('C110', '.1uF', 'C', at=(50, 140), pins={'1': '+15V', '2': 'GND'},
          desc='Inferred from the circuit: U45 +15V supply decoupling'),
        P('C130B', '.1uF', 'C', at=(65, 140), pins={'1': '-15V', '2': 'GND'}, printed='C130',
          note='C130 printed three times on FIG 5F',
          desc='Inferred from the circuit: U45 -15V supply decoupling'),
    ],
    ports=[port('REF_1', 'input', at=(30, 88), facing='left')],
    taps=[tap('p10v', '+10V', (195, 90)), tap('inv', '5F_U45_INV', (73, 88))],
    wires=[
        ('@REF_1', 'R237.2'), ('R237.1', '@inv'), ('@inv', 'U45.2'), ('R235.1', 'U45.3', 'vh'),
        ('R236.2', '@inv'), ('C112B.2', 'R236.2', [(73, 72)]),
        ('U45.6', 'R250.2'), ('C112B.1', 'U45.6', [(97, 72), (97, 90)]),
        ('@p10v', 'R250.1'),
        ('C147.1', 'R250.1', 'vh'), ('C137.1', 'R250.1', 'vh'), ('C70.1', 'R250.1', 'vh'),
        ('C41.1', 'R250.1', 'vh'), ('C34.1', 'R250.1', 'vh'),
        ('C110.2', 'C130B.2'),
    ],
    names={'+10V': ['@p10v', 'R236.1'], '5F_U45_INV': 'R236.2', '5F_U45_OUT': 'R250.2',
           '5F_U45_NINV': 'U45.3'},
    notes=[('U45 DECOUPLING CAPACITORS', 42, 128),
           ('Printed "10V" -> net +10V.', 15, 150)],
)

# ── Input: J12, fuse, C161, UR3 DC-DC converter ──
DCDC = child(
    'dcdc', 'Power input (J12, FX1, UR3)', short='INPUT', paper='A4', at=(30, 110),
    parts=[
        P('J12', '?', 'CONN_10', at=(35, 90), mirror=True,
          pins={'1': 'FAULT_O', '2': 'FAULT_NO', '3': '+27VINK(RM)', '4': '+27VINK(RM)',
                '5': '5F_VIN_RTN', '6': '5F_VIN_RTN', '7': 'NC', '8': 'GND', '9': 'NC', '10': 'FAULT_NO'},
          note='No value printed; pin 7 = POLARIZING KEY; pin 9 drawn with a dangling lead (no-connect flag); '
               'pins 3+4 tied, pins 5+6 tied; FAULT_NO printed on pins 2 and 10',
          desc='Patent: FIG 5F-2 connector J12 carrying the input supply (+27VINK(RM)/+48VINK(TM) '
               'flags) and the FAULT_O/FAULT_NO lines; pin 7 printed POLARIZING KEY'),
        P('FX1', '?', 'FUSE', at=(70, 86), rot=90, pins={'1': '+27VINK(RM)', '2': '5F_VIN_P'},
          note='Fuse; no ref or value printed',
          desc='Inferred from the circuit: input fuse between J12 pins 3/4 and the converter input'),
        P('C161', '100uF', 'CP', at=(90, 96), pins={'1': '5F_VIN_P', '2': '5F_VIN_RTN'},
          desc='Inferred from the circuit: input bulk capacitor across the UR3 converter input'),
        P('UR3', '?', 'F5F_UR3', probable='24D15 (rack) or 48D15 (tower) DC-DC converter, +-15 V out: the FIG 5A option table lists VR3 with these values, taken to be UR3', at=(120, 96), text=(7, -8),
          pins={'4': '+15V', '5': 'GND', '6': '-15V', '3': '5F_VIN_P', '2': '5F_VIN_RTN'},
          note='DC-DC converter block; ref printed UR3, no value or part number printed',
          desc='Inferred from the circuit: DC-DC converter making +15V and -15V from the fused input'),
    ],
    ports=[port('FAULT_O', 'passive', at=(100, 72), facing='right', side='left'),
           port('FAULT_NO', 'passive', at=(100, 82), facing='right', side='left'),
           port('5F_VIN_P', 'output', at=(115, 86), facing='right'),
           port('5F_VIN_RTN', 'output', at=(115, 112), facing='right')],
    taps=[tap('m15', '-15V', (150, 98)), tap('p15', '+15V', (138, 90)), tap('g8', 'GND', (47, 94), facing='down')],
    wires=[
        ('J12.1', '@FAULT_O', [(43, 72)]),
        ('J12.2', '@FAULT_NO'), ('J12.10', 'J12.2', [(52, 98), (52, 82)]), ('J12.8', '@g8'),
        ('J12.3', 'J12.4'), ('J12.4', 'FX1.1'),
        ('FX1.2', 'UR3.3', [(100, 86), (100, 94)]), ('C161.1', 'FX1.2', 'vh'), ('@5F_VIN_P', 'FX1.2'),
        ('J12.5', 'J12.6'), ('J12.6', 'UR3.2', [(55, 90), (55, 112), (104, 112), (104, 98)]),
        ('C161.2', 'UR3.2', [(90, 112), (104, 112), (104, 98)]), ('@5F_VIN_RTN', 'UR3.2', [(104, 112), (104, 98)]),
        ('UR3.6', '@m15'), ('UR3.4', '@p15', 'hv'),
    ],
    names={'+27VINK(RM)': 'FX1.1', '-15V': '@m15', '+15V': '@p15', 'GND': '@g8'},
    notes=[('J12-3/4 node (input side of fuse FX1) flag printed "+27VINK(RM) / +48VINK(TM)".\n'
            'J12-5/6 node flag printed with the SAME text; kept as separate net 5F_VIN_RTN\n'
            '(same name would short the converter input). J12-7 = POLARIZING KEY.', 15, 125)],
)

# ── Input voltage monitor: U45 (second LT1007) -> PWR_MON ──
MONITOR = child(
    'monitor', 'Input voltage monitor (second U45, ref U45B; PWR_MON)', short='MONITOR', paper='A4', at=(120, 110),
    parts=[
        P('R229B', '100K', 'R', at=(55, 74), rot=90, pins={'1': '5F_VIN_RTN', '2': '5F_U45B_INV'},
          printed='R229', note='R229 printed three times on 5F-2',
          desc='Inferred from the circuit: input resistor from the converter input return to the '
               'U45 (monitor) inverting input'),
        P('U45B', 'LT1007', 'OPAMP', at=(100, 90), pinmap=_LT1007, printed='U45', text=(7, 3),
          note='Ref U45 also used on 5F-1 for a different LT1007. ' + _V_MINUS,
          pins={'2': '5F_U45B_INV', '3': '5F_U45B_NINV', '6': 'PWR_MON', '7': '+15V', '4': '-15V'},
          desc='Inferred from the circuit: differential amplifier across the converter input '
               '(5F_VIN_P / 5F_VIN_RTN) whose output is PWR_MON'),
        P('R216', '10K', 'R', at=(100, 66), rot=270, pins={'1': 'PWR_MON', '2': '5F_U45B_INV'},
          desc='Inferred from the circuit: U45 (monitor) feedback resistor, sets the gain with R229B'),
        P('C121', '100uF', 'C', at=(100, 56), rot=270, pins={'1': 'PWR_MON', '2': '5F_U45B_INV'},
          desc='Inferred from the circuit: U45 (monitor) feedback capacitor, filters PWR_MON'),
        P('R229', '100K', 'R', at=(55, 100), rot=90, pins={'1': '5F_VIN_P', '2': '5F_U45B_NINV'},
          note='R229 printed three times on 5F-2',
          desc='Inferred from the circuit: input resistor from the fused input to the U45 (monitor) '
               'non-inverting input'),
        P('C119', '1uF90V', 'CP', at=(70, 120), text=(2, -1), pins={'1': '5F_U45B_NINV', '2': 'GND'},
          desc='Inferred from the circuit: filter capacitor on the U45 (monitor) non-inverting input'),
        P('R231', '10K', 'R', at=(80, 120), pins={'1': '5F_U45B_NINV', '2': 'GND'},
          desc='Inferred from the circuit: resistor to ground at the U45 (monitor) non-inverting '
               'input, divider with R229'),
        P('C120', '1uF90V', 'CP', at=(90, 120), text=(2, -1), pins={'1': '5F_U45B_NINV', '2': 'GND'},
          desc='Inferred from the circuit: filter capacitor on the U45 (monitor) non-inverting input'),
        P('R220', '30.1K', 'R', at=(100, 120), pins={'1': '5F_U45B_NINV', '2': 'GND'},
          desc='Inferred from the circuit: resistor to ground at the U45 (monitor) non-inverting '
               'input, in parallel with R231'),
        P('C123', '.1uF', 'C', at=(35, 140), pins={'1': '+15V', '2': 'GND'},
          desc='Inferred from the circuit: U45 (monitor) +15V supply decoupling'),
        P('C124', '.1uF', 'C', at=(48, 140), pins={'1': '-15V', '2': 'GND'},
          desc='Inferred from the circuit: U45 (monitor) -15V supply decoupling'),
    ],
    ports=[port('5F_VIN_P', 'input', at=(30, 100), facing='left'),
           port('5F_VIN_RTN', 'input', at=(30, 74), facing='left'),
           port('PWR_MON', 'output', at=(130, 90), facing='right')],
    wires=[
        ('@5F_VIN_RTN', 'R229B.1'), ('R229B.2', 'U45B.2', [(86, 74), (86, 88)]),
        ('R216.2', 'U45B.2', [(86, 66), (86, 88)]), ('C121.2', 'U45B.2', [(86, 56), (86, 88)]),
        ('U45B.6', '@PWR_MON'),
        ('R216.1', 'U45B.6', [(114, 66), (114, 90)]), ('C121.1', 'U45B.6', [(114, 56), (114, 90)]),
        ('@5F_VIN_P', 'R229.1'), ('R229.2', 'U45B.3', [(85, 100), (85, 92)]),
        ('@nb', 'R229.2', [(85, 100)]),
        ('C119.1', 'R231.1'), ('R231.1', '@nb'), ('@nb', 'C120.1'), ('R220.1', 'C120.1'),
        ('C123.2', 'C124.2'),
    ],
    taps=[tap('nb', '5F_U45B_NINV', (85, 115))],
    names={'5F_U45B_INV': 'R229B.2', '5F_U45B_NINV': 'R229.2'},
    notes=[('U45 (MONITOR) DECOUPLING CAPACITORS', 25, 128)],
)

# ── +12V / -12V / -5V regulators ──
REGS = child(
    'regs', '+12V, -12V and -5V regulators', short='REGULATORS', paper='A3', at=(30, 150),
    parts=[
        P('C129', '2.2uF/25V', 'CP', at=(80, 60), pins={'1': '+15V', '2': 'GND'},
          desc='Inferred from the circuit: input capacitor of the +12V regulator UX1'),
        P('UX1', '?', 'F5F_REG', probable='7812-type +12 V three-terminal regulator (not printed; from +15V in, +12V out)', text=(-4, -6), at=(100, 50), pins={'OUT': '+12V', 'IN': '+15V', 'COM': 'GND'},
          note=_REG + '; +15V in, +12V out',
          desc='Inferred from the circuit: three-terminal regulator making +12V from +15V'),
        P('C114', '2.2uF/25V', 'CP', at=(120, 60), pins={'1': '+12V', '2': 'GND'},
          desc='Inferred from the circuit: output capacitor of the +12V regulator UX1'),
        P('C160', '2.2uF/25V', 'CP', at=(80, 105), rot=180, pins={'1': 'GND', '2': '-15V'},
          desc='Inferred from the circuit: input capacitor of the -12V regulator UX2'),
        P('UX2', '?', 'F5F_REG', probable='7912-type -12 V three-terminal regulator (not printed; from -15V in, -12V out)', text=(-4, -6), at=(100, 95), pins={'OUT': '-12V', 'IN': '-15V', 'COM': 'GND'},
          note=_REG + '; -15V in, -12V out',
          desc='Inferred from the circuit: three-terminal regulator making -12V from -15V'),
        P('C159B', '2.2uF/25V', 'CP', at=(120, 105), rot=180, pins={'1': 'GND', '2': '-12V'},
          printed='C159', note='C159 printed on 5F-1 and 5F-2',
          desc='Inferred from the circuit: output capacitor of the -12V regulator UX2'),
        P('C156', '2.2uF/25V', 'CP', at=(80, 150), rot=180, pins={'1': 'GND', '2': '-15V'},
          desc='Inferred from the circuit: input capacitor of the -5V regulator UX3'),
        P('UX3', '?', 'F5F_REG', probable='7905-type -5 V three-terminal regulator (not printed; from -15V in, -5V out)', text=(-4, -6), at=(100, 140), pins={'OUT': '-5V', 'IN': '-15V', 'COM': 'GND'},
          note=_REG + '; -15V in, -5V out',
          desc='Inferred from the circuit: three-terminal regulator making -5V from -15V'),
        P('C162', '2.2uF/25V', 'CP', at=(120, 150), rot=180, pins={'1': 'GND', '2': '-5V'},
          desc='Inferred from the circuit: output capacitor of the -5V regulator UX3'),
    ],
    taps=[tap('i1', '+15V', (70, 50)), tap('o1', '+12V', (130, 50)), tap('g1', 'GND', (100, 70), facing='down'), tap('c1', 'GND', (80, 70), facing='down'),
          tap('i2', '-15V', (70, 95)), tap('o2', '-12V', (130, 95)), tap('g2', 'GND', (100, 115), facing='down'), tap('c2', 'GND', (80, 115), facing='down'),
          tap('i3', '-15V', (70, 140)), tap('o3', '-5V', (130, 140)), tap('g3', 'GND', (100, 160), facing='down'), tap('c3', 'GND', (80, 160), facing='down')],
    wires=[
        ('@i1', 'UX1.IN'), ('C129.1', 'UX1.IN', 'vh'), ('UX1.OUT', '@o1'), ('C114.1', 'UX1.OUT', 'vh'),
        ('UX1.COM', '@g1'), ('C129.2', '@c1'), ('@c1', '@g1'), ('C114.2', '@g1', [(120, 70)]),
        ('@i2', 'UX2.IN'), ('C160.2', 'UX2.IN', 'vh'), ('UX2.OUT', '@o2'), ('C159B.2', 'UX2.OUT', 'vh'),
        ('UX2.COM', '@g2'), ('C160.1', '@c2'), ('@c2', '@g2'), ('C159B.1', '@g2', [(120, 115)]),
        ('@i3', 'UX3.IN'), ('C156.2', 'UX3.IN', 'vh'), ('UX3.OUT', '@o3'), ('C162.2', 'UX3.OUT', 'vh'),
        ('UX3.COM', '@g3'), ('C156.1', '@c3'), ('@c3', '@g3'), ('C162.1', '@g3', [(120, 160)]),
    ],
    names={'+15V': '@i1', '+12V': '@o1', '-15V': ['@i2', '@i3'], '-12V': '@o2', '-5V': '@o3',
           'GND': ['@c1', '@c2', '@c3']},
    notes=[('+12V', 92, 40), ('-12V', 92, 85), ('-5V', 92, 130)],
)

# ── +5V digital supply, A/D ground split, ground lugs ──
DIGITAL = child(
    'digital', '+5V supply (UX4, L0, L7)', short='+5V', paper='A3', at=(120, 150),
    parts=[
        P('C132', '10uF25V', 'CP', at=(80, 70), pins={'1': '+15V', '2': 'GND'},
          desc='Inferred from the circuit: input capacitor of the +5V regulator UX4'),
        P('UX4', '?', 'F5F_REG', probable='7805-type +5 V three-terminal regulator (not printed; from +15V in, +5V out)', text=(-4, -6), at=(100, 60),
          pins={'OUT': '5F_5V_REG', 'IN': '+15V', 'COM': '5F_GND_D'}, note=_REG + '; +15V in, +5V out',
          desc='Inferred from the circuit: three-terminal regulator making +5V from +15V, its common '
               'on the filled-triangle ground 5F_GND_D'),
        P('C149B', '100uF10V', 'CP', at=(120, 70), pins={'1': '5F_5V_REG', '2': '5F_GND_D'},
          printed='C149', note='C149 printed on 5F-1 and 5F-2',
          desc='Inferred from the circuit: output capacitor of the +5V regulator UX4'),
        P('L7', 'R100', 'L', at=(140, 36), rot=90, pins={'1': '5F_5V_REG', '2': '+5V'},
          note='Drawn with a dashed core line. Its output is also labelled +5V, which puts L0 and L7 '
               'in parallel (lower +5V returns to open GND, upper to the filled ground)',
          desc='Inferred from the circuit: filter inductor from the UX4 output to a +5V output '
               'decoupled to the open ground GND'),
        P('C127', '.1uF', 'C', at=(155, 46), pins={'1': '+5V', '2': 'GND'},
          desc='Inferred from the circuit: filter capacitor after L7 on +5V'),
        P('C130C', '2.2uF/25V', 'CP', at=(168, 46), pins={'1': '+5V', '2': 'GND'}, printed='C130',
          note='C130 printed three times on FIG 5F',
          desc='Inferred from the circuit: filter capacitor after L7 on +5V'),
        P('L0', 'R100', 'L', at=(140, 60), rot=90, pins={'1': '5F_5V_REG', '2': '+5V'},
          note='Drawn with a dashed core line',
          desc='Inferred from the circuit: filter inductor from the UX4 output to a +5V output '
               'decoupled to the filled ground 5F_GND_D'),
        P('C128', '.1uF', 'C', at=(155, 70), pins={'1': '+5V', '2': '5F_GND_D'},
          desc='Inferred from the circuit: filter capacitor after L0 on +5V, to 5F_GND_D'),
        P('C131', '2.2uF/25V', 'CP', at=(168, 70), pins={'1': '+5V', '2': '5F_GND_D'},
          desc='Inferred from the circuit: filter capacitor after L0 on +5V, to 5F_GND_D'),
        P('R239', '?', 'R', at=(185, 88), pins={'1': '5F_GND_D', '2': 'GND'},
          note='No value printed; joins the filled-ground return to the open-ground return',
          desc='Inferred from the circuit: links the filled ground 5F_GND_D to the open ground GND; '
               'role unknown beyond that (no value printed)'),
        P('R229C', '100K', 'R', at=(198, 88), rot=180, pins={'1': 'GND', '2': '5F_GND_D'},
          printed='R229',
          note='Between the "A" and "D" points of the GND split. ' + _GND_D,
          desc='Patent: FIG 5F-2 draws it between the A and D points of the GND split; '
               'Inferred from the circuit: ties the two grounds together through 100K'),
        P('TPX3', '?', 'TP', at=(210, 76), text=(2, -4), pins={'1': '5F_GND_D'},
          note='Unlabelled circle-on-stem terminal, no ref/value printed; filled ground. ' + _GND_D,
          desc='Inferred from the circuit: ground terminal (lug or test point) on 5F_GND_D'),
        P('TPX4', '?', 'TP', at=(224, 76), text=(2, -4), pins={'1': '5F_GND_D'},
          note='Unlabelled circle-on-stem terminal, no ref/value printed; filled ground. ' + _GND_D,
          desc='Inferred from the circuit: ground terminal (lug or test point) on 5F_GND_D'),
        P('TPX1', '?', 'TP', at=(210, 100), text=(2, -4), pins={'1': 'GND'},
          note='Unlabelled circle-on-stem terminal, no ref/value printed; open ground',
          desc='Inferred from the circuit: ground terminal (lug or test point) on GND'),
        P('TPX2', '?', 'TP', at=(224, 100), text=(2, -4), pins={'1': 'GND'},
          note='Unlabelled circle-on-stem terminal, no ref/value printed; open ground',
          desc='Inferred from the circuit: ground terminal (lug or test point) on GND'),
    ],
    taps=[tap('p15', '+15V', (72, 60)), tap('p5a', '+5V', (176, 36)), tap('p5b', '+5V', (176, 60)),
          tap('gd', '5F_GND_D', (232, 80), facing='right')],
    wires=[
        ('@p15', 'UX4.IN'), ('C132.1', 'UX4.IN', 'vh'),
        ('C149B.1', 'UX4.OUT', 'vh'), ('UX4.OUT', 'L0.1'), ('L7.1', 'UX4.OUT', [(128, 36), (128, 60)]),
        ('C127.1', 'L7.2', 'vh'), ('C130C.1', 'L7.2', 'vh'), ('L7.2', '@p5a'), ('C127.2', 'C130C.2'),
        ('C128.1', 'L0.2', 'vh'), ('C131.1', 'L0.2', 'vh'), ('L0.2', '@p5b'),
        ('UX4.COM', 'R229C.2', [(100, 80), (198, 80)]),
        ('C149B.2', 'UX4.COM', [(120, 80), (100, 80)]), ('C128.2', 'UX4.COM', [(155, 80), (100, 80)]),
        ('C131.2', 'UX4.COM', [(168, 80), (100, 80)]), ('R239.1', 'UX4.COM', [(185, 80), (100, 80)]),
        ('TPX3.1', 'R229C.2', [(210, 80), (198, 80)]), ('TPX4.1', 'TPX3.1', [(224, 80), (210, 80)]),
        ('@gd', 'TPX4.1', [(224, 80)]),
    ],
    names={'+15V': '@p15', '+5V': ['@p5a', '@p5b'], '5F_5V_REG': 'UX4.OUT', '5F_GND_D': '@gd'},
    notes=[('Filled-triangle ground = net 5F_GND_D ("D" side of the A / GND / D split, R229C 100K).\n'
            'Both inductor outputs are printed "+5V".', 15, 175)],
)

CHILDREN = [REF10, REF5VA, REF10V, DCDC, MONITOR, REGS, DIGITAL]

# ── Figure page: the child blocks and how they connect ──
PAGE_WIRES = [
    ('ref10:REF_1', '@t1', [(95, 44)]), ('@t1', 'ref5va:REF_1'),
    ('ref10:REF_1', 'ref10v:REF_1', [(95, 44), (95, 70)]),
    ('@REF_1', '@t1', [(95, 30)]),
    ('dcdc:5F_VIN_P', 'monitor:5F_VIN_P'),
    ('dcdc:5F_VIN_RTN', 'monitor:5F_VIN_RTN'),
]
PORTS = [
    port('REF_1', 'output', at=(165, 30), facing='right'),
    port('FAULT_O', 'passive', on='dcdc:FAULT_O', side='left'),
    port('FAULT_NO', 'passive', on='dcdc:FAULT_NO', side='left'),
    port('PWR_MON', 'output', on='monitor:PWR_MON'),
]

PAGE_TAPS = [tap('t1', 'REF_1', (95, 40))]

NOTES = [('Rails in: +15V, -15V from INPUT (UR3).\nOut: +12V, -12V, -5V.', 30, 166),
         ('Rails in: +15V from INPUT (UR3).\nOut: +5V (two L-C outputs).', 120, 166),
         ('FIG 5F-1: 10 V reference, +5VA and 10V outputs (top).  FIG 5F-2: input, converter, monitor\n'
          'and regulators (bottom). Each block is one function; see its sheet.', 15, 200)]

NET_DESCRIPTIONS = {
    'REF_1': 'Patent: FIG 5F-1 off-page flag REF_1. Inferred from the circuit: the U47/U50 '
             'reference output; used here by the +5VA and 10V stages and on FIGS 5A, 6A-6C',
    '+SUREF': 'Patent: FIG 5F-1 off-page flag "+SUREF" (probably +5VREF), fed from +5VA through '
              'R168; no transcribed figure uses it',
    'FAULT_O': 'Patent: FIG 5F-2 flag FAULT_O on J12 pin 1. Inferred from the circuit: relay '
               'contact line from FIG 5G (K3) out to J12',
    'FAULT_NO': 'Patent: FIG 5F-2 flag FAULT_NO on J12 pins 2 and 10. Inferred from the circuit: '
                'relay contact line from FIG 5G (K3) out to J12',
    'PWR_MON': 'Patent: FIG 5F-2 off-page flag PWR_MON. Inferred from the circuit: U45 (monitor) '
               'output proportional to the input supply, read by the microcontroller ADC (FIG 5G PE6)',
    '5F_VIN_P': 'Inferred from the circuit: fused input supply (after FX1) to the UR3 converter '
                '+INPUT and the input monitor',
    '5F_VIN_RTN': 'Inferred from the circuit: input supply return (J12 pins 5/6) to the UR3 converter '
                  '-INPUT and the input monitor',
    '+27VINK(RM)': 'Patent: FIG 5F-2 flag "+27VINK(RM) / +48VINK(TM)" on J12 pins 3/4. '
                   'Inferred from the circuit: input supply before the fuse',
    '5F_REF_VIN': 'Inferred from the circuit: filtered +15V (R230, C148, C149) feeding the U47/U50 '
                  'reference inputs',
    '5F_U55_INV': 'Inferred from the circuit: +5VA feedback (R271) at the U55 inverting input',
    '5F_U55_OUT': 'Inferred from the circuit: U55 output driving the QX1 base through R273',
    '5F_Q_C': 'Inferred from the circuit: QX1 collector supply from +15V through R272',
    '5F_U45_INV': 'Inferred from the circuit: U45 inverting input (REF_1 through R237, +10V through R236)',
    '5F_U45_NINV': 'Inferred from the circuit: U45 non-inverting input, to ground through R235',
    '5F_U45_OUT': 'Inferred from the circuit: U45 output, to the +10V rail through R250',
    '5F_U45B_INV': 'Inferred from the circuit: monitor amplifier inverting input (5F_VIN_RTN through R229B)',
    '5F_U45B_NINV': 'Inferred from the circuit: monitor amplifier non-inverting input (5F_VIN_P through R229, '
                    'divided and filtered by R231, R220, C119, C120)',
    '5F_5V_REG': 'Inferred from the circuit: UX4 regulator output before the L0/L7 filter inductors',
    '5F_GND_D': 'Patent: FIG 5F-2 filled-triangle ground (the "D" point of the A / GND / D split). '
                'Inferred from the circuit: UX4 common and the L0 filter return, tied to GND '
                'through R239 and R229C',
}
