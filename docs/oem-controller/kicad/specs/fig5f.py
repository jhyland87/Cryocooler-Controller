"""FIG 5F - voltage references (+5VA, 10V, REF_1) and power supply (UR3 DC-DC, regulators, J12)."""

from oemsch import P

TITLE = 'FIG 5F - References and power supply'
SOURCE = 'US6098409 sheets 12-13 of 25 (PDF p13-14), FIG 5F-1/5F-2'
PAPER = 'A1'

SYMBOLS = {
    'F5F_URE319': {'left': [('2', 'VDD')], 'right': [('6', 'OUT')], 'bottom': [('4', 'GND')],
                   'prefix': 'U'},
    'F5F_AD2710': {'left': [('11', 'VDD')], 'right': [('13', 'OUT')], 'bottom': [('7', 'GND')],
                   'prefix': 'U'},
    'F5F_UR3': {'left': [('4', '+15V'), None, ('5', '+/-'), None, ('6', '-15V')],
                'right': [('3', '+INPUT'), None, ('2', '-INPUT')], 'prefix': 'U'},
    # Three-terminal regulators: no refs, part numbers or pin numbers printed. Terminals
    # lettered "0" (output), "0" (common) and "I" (input); pin "numbers" here are OUT/COM/IN.
    'F5F_REG_COM_BOTTOM': {'left': [None, ('OUT', '0'), None], 'right': [None, ('IN', 'I'), None],
                           'bottom': [None, None, ('COM', '0'), None, None], 'prefix': 'U'},
    'F5F_REG_COM_TOP': {'left': [None, ('OUT', '0'), None], 'right': [None, ('IN', 'I'), None],
                        'top': [None, None, ('COM', '0'), None, None], 'prefix': 'U'},
}

_LT1007 = {'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'}
_V_MINUS = 'V- pin number not printed (4 assumed for LT1007)'
_REG = 'No ref / part number printed; terminals lettered 0 (out), 0 (common), I (in)'
_GND_D = ('5F_GND_D = net of the filled-triangle ground symbol (the "D" side of the '
          'A/GND/D split through R229C)')

PARTS = [
    # ── FIG 5F-1: ground lugs / test points (no refs printed) ──
    P('TPX1', '?', 'TP', at=(20, 45), pins={'1': 'GND'},
      note='Unlabelled circle-on-stem terminal, no ref/value printed; open ground'),
    P('TPX2', '?', 'TP', at=(28, 45), pins={'1': 'GND'},
      note='Unlabelled circle-on-stem terminal, no ref/value printed; open ground'),
    P('TPX3', '?', 'TP', at=(42, 45), pins={'1': '5F_GND_D'},
      note='Unlabelled circle-on-stem terminal, no ref/value printed; filled ground. ' + _GND_D),
    P('TPX4', '?', 'TP', at=(50, 45), pins={'1': '5F_GND_D'},
      note='Unlabelled circle-on-stem terminal, no ref/value printed; filled ground. ' + _GND_D),

    # ── FIG 5F-1: references U47 / U50 (outputs and inputs paralleled) ──
    P('U47', 'URE319', 'F5F_URE319', at=(85, 80), probable='VRE310 (Thaler 10 V ref, DIP pins 2/4/6)',
      pins={'2': '5F_REF_VIN', '6': 'REF_1', '4': 'GND'},
      note='Value printed "URE319"; in parallel with U50 (alternate footprints?)'),
    P('U50', 'AD2710', 'F5F_AD2710', at=(85, 112), probable='AD2710 10 V reference',
      pins={'11': '5F_REF_VIN', '13': 'REF_1', '7': 'GND'}),
    P('R230', '10K', 'R', at=(25, 122), pins={'1': '5F_REF_VIN', '2': '+15V'},
      note='Lower end runs off sheet 12 and continues on sheet 13 to the +15V rail (match line)'),
    P('C148', '2.2uF/25V', 'CP', at=(42, 122), pins={'1': '5F_REF_VIN', '2': 'GND'}),
    P('C149', '2.2uF/25V', 'C', at=(56, 122), pins={'1': '5F_REF_VIN', '2': 'GND'}),
    P('C112', '2.2uF/25V', 'C', at=(112, 122), pins={'1': 'REF_1', '2': 'GND'}),

    # ── FIG 5F-1: U55 + pass transistor -> +5VA, R168 -> +SUREF ──
    P('R252', '4.90K', 'R', at=(140, 72), rot=270, pins={'1': '5F_U55_NINV', '2': 'REF_1'}),
    P('R251', '4.90K', 'R', at=(152, 86), pins={'1': '5F_U55_NINV', '2': 'GND'}),
    P('U55', 'LT1007', 'OPAMP', at=(180, 72), pinmap=_LT1007, note=_V_MINUS,
      pins={'2': '5F_U55_INV', '3': '5F_U55_NINV', '6': '5F_U55_OUT', '7': '+15V', '4': '-15V'}),
    P('C130', '.1uF', 'C', at=(166, 48), pins={'1': '+15V', '2': 'GND'}),
    P('C151', '.1uF', 'C', at=(166, 96), pins={'1': '-15V', '2': 'GND'}),
    P('C152', '.1uF', 'C', at=(184, 54), rot=270, pins={'1': '5F_U55_OUT', '2': '5F_U55_INV'}),
    P('R271', '4.90K', 'R', at=(215, 42), rot=270, pins={'1': '+5VA', '2': '5F_U55_INV'}),
    P('R273', '4.75K', 'R', at=(210, 72), rot=270, pins={'1': '5F_Q_B', '2': '5F_U55_OUT'}),
    P('QX1', '?', 'NPN', at=(236, 72), pins={'B': '5F_Q_B', 'C': '5F_Q_C', 'E': '+5VA'},
      note='NPN pass transistor; no ref or part number printed'),
    P('R272', '1K', 'R', at=(239, 52), pins={'1': '+15V', '2': '5F_Q_C'}),
    P('C163', '.1uF', 'C', at=(256, 62), pins={'1': '5F_Q_C', '2': 'GND'}),
    P('C159', '2.2uF/25V', 'CP', at=(239, 98), pins={'1': '+5VA', '2': 'GND'}),
    P('C157', '.1uF', 'C', at=(256, 98), pins={'1': '+5VA', '2': 'GND'}),
    P('R168', '?', 'R', at=(285, 72), rot=270, pins={'1': '+SUREF', '2': '+5VA'},
      note='No value printed'),

    # ── FIG 5F-1: U45 inverter -> 10V ──
    P('R237', '4.90K', 'R', at=(140, 152), rot=270, pins={'1': '5F_U45_INV', '2': 'REF_1'}),
    P('U45', 'LT1007', 'OPAMP', at=(180, 154), pinmap=_LT1007, note=_V_MINUS,
      pins={'2': '5F_U45_INV', '3': '5F_U45_NINV', '6': '5F_U45_OUT', '7': '+15V', '4': '-15V'}),
    P('R235', '2.40K', 'R', at=(160, 170), pins={'1': '5F_U45_NINV', '2': 'GND'}),
    P('C110', '.1uF', 'C', at=(166, 130), pins={'1': '+15V', '2': 'GND'}),
    P('C130B', '.1uF', 'C', at=(176, 180), pins={'1': '-15V', '2': 'GND'}, printed='C130',
      note='C130 printed three times on FIG 5F'),
    P('C112B', '2.2uF/25V', 'C', at=(184, 136), rot=270, pins={'1': '5F_U45_OUT', '2': '5F_U45_INV'},
      printed='C112', note='C112 printed twice on 5F-1'),
    P('R236', '4.90K', 'R', at=(215, 124), rot=270, pins={'1': '+10V', '2': '5F_U45_INV'}),
    P('R250', '1K', 'R', at=(210, 154), rot=270, pins={'1': '+10V', '2': '5F_U45_OUT'}),
    P('C147', '1uF90V', 'CP', at=(236, 172), pins={'1': '+10V', '2': 'GND'}),
    P('C137', '.1uF', 'C', at=(250, 172), pins={'1': '+10V', '2': 'GND'}),
    P('C70', '.1uF', 'C', at=(264, 172), pins={'1': '+10V', '2': 'GND'}),
    P('C41', '.1uF', 'C', at=(278, 172), pins={'1': '+10V', '2': 'GND'}),
    P('C34', '.1uF', 'C', at=(292, 172), pins={'1': '+10V', '2': 'GND'}),

    # ── FIG 5F-2: UR3 DC-DC converter and input (J12, fuse) ──
    P('UR3', 'UR3', 'F5F_UR3', at=(260, 280),
      pins={'4': '+15V', '5': 'GND', '6': '-15V', '3': '5F_VIN_P', '2': '5F_VIN_RTN'},
      note='DC-DC converter block; ref printed UR3, no part number'),
    P('C161', '100uF', 'CP', at=(330, 262), pins={'1': '5F_VIN_P', '2': '5F_VIN_RTN'}),
    P('FX1', '?', 'FUSE', at=(370, 270), rot=270, pins={'1': '+27VINK(RM)', '2': '5F_VIN_P'},
      note='Fuse; no ref or value printed'),
    P('J12', 'J12', 'CONN_10', at=(440, 280),
      pins={'1': 'FAULT_O', '2': 'FAULT_NO', '3': '+27VINK(RM)', '4': '+27VINK(RM)',
            '5': '5F_VIN_RTN', '6': '5F_VIN_RTN', '7': 'NC', '8': 'GND', '10': 'FAULT_NO'},
      note='Pin 7 = POLARIZING KEY; pin 9 drawn with a dangling lead; '
           'pins 3+4 tied, pins 5+6 tied; FAULT_NO printed on pins 2 and 10'),
    P('R229', '100K', 'R', at=(305, 300), pins={'1': '5F_VIN_P', '2': '5F_U45B_NINV'},
      note='R229 printed three times on 5F-2'),
    P('R229B', '100K', 'R', at=(345, 300), pins={'1': '5F_VIN_RTN', '2': '5F_U45B_INV'},
      printed='R229', note='R229 printed three times on 5F-2'),

    # ── FIG 5F-2: U45 (second) differential input monitor -> PWR_MON ──
    P('U45B', 'LT1007', 'OPAMP', at=(390, 360), pinmap=_LT1007, printed='U45',
      note='Ref U45 also used on 5F-1 for a different LT1007. ' + _V_MINUS,
      pins={'2': '5F_U45B_INV', '3': '5F_U45B_NINV', '6': 'PWR_MON', '7': '+15V', '4': '-15V'}),
    P('R216', '10K', 'R', at=(392, 332), rot=270, pins={'1': 'PWR_MON', '2': '5F_U45B_INV'}),
    P('C121', '100uF', 'C', at=(392, 340), rot=270, pins={'1': 'PWR_MON', '2': '5F_U45B_INV'}),
    P('C123', '.1uF', 'C', at=(408, 340), pins={'1': '+15V', '2': 'GND'}),
    P('C124', '.1uF', 'C', at=(408, 382), pins={'1': '-15V', '2': 'GND'}),
    P('C119', '1uF90V', 'CP', at=(310, 392), pins={'1': '5F_U45B_NINV', '2': 'GND'}),
    P('R231', '10K', 'R', at=(322, 392), pins={'1': '5F_U45B_NINV', '2': 'GND'}),
    P('C120', '1uF90V', 'CP', at=(334, 392), pins={'1': '5F_U45B_NINV', '2': 'GND'}),
    P('R220', '30.1K', 'R', at=(346, 392), pins={'1': '5F_U45B_NINV', '2': 'GND'}),

    # ── FIG 5F-2: +12V / -12V / -5V regulators ──
    P('UX1', '?', 'F5F_REG_COM_BOTTOM', at=(100, 262), pins={'OUT': '+12V', 'IN': '+15V', 'COM': 'GND'},
      note=_REG + '; +15V in, +12V out'),
    P('C114', '2.2uF/25V', 'CP', at=(70, 272), pins={'1': '+12V', '2': 'GND'}),
    P('C129', '2.2uF/25V', 'CP', at=(135, 272), pins={'1': '+15V', '2': 'GND'}),
    P('UX2', '?', 'F5F_REG_COM_TOP', at=(100, 312), pins={'OUT': '-12V', 'IN': '-15V', 'COM': 'GND'},
      note=_REG + '; -15V in, -12V out'),
    P('C159B', '2.2uF/25V', 'CP', at=(70, 312), pins={'1': 'GND', '2': '-12V'}, printed='C159',
      note='C159 printed on 5F-1 and 5F-2'),
    P('C160', '2.2uF/25V', 'CP', at=(135, 312), pins={'1': 'GND', '2': '-15V'}),
    P('UX3', '?', 'F5F_REG_COM_TOP', at=(100, 360), pins={'OUT': '-5V', 'IN': '-15V', 'COM': 'GND'},
      note=_REG + '; -15V in, -5V out'),
    P('C162', '2.2uF/25V', 'CP', at=(70, 360), pins={'1': 'GND', '2': '-5V'}),
    P('C156', '2.2uF/25V', 'CP', at=(135, 360), pins={'1': 'GND', '2': '-15V'}),

    # ── FIG 5F-2: analog/digital ground split and +5V regulator ──
    P('R229C', '100K', 'R', at=(200, 300), pins={'1': 'GND', '2': '5F_GND_D'}, printed='R229',
      note='Between the "A" and "D" points of the GND split. ' + _GND_D),
    P('UX4', '?', 'F5F_REG_COM_BOTTOM', at=(190, 400),
      pins={'OUT': '5F_5V_REG', 'IN': '+15V', 'COM': '5F_GND_D'}, note=_REG + '; +15V in, +5V out'),
    P('C132', '10uF25V', 'CP', at=(225, 400), pins={'1': '+15V', '2': 'GND'}),
    P('C149B', '100uF10V', 'CP', at=(160, 412), pins={'1': '5F_5V_REG', '2': '5F_GND_D'},
      printed='C149', note='C149 printed on 5F-1 and 5F-2'),
    P('L0', 'R100', 'L', at=(120, 400), rot=270, pins={'1': '5F_5V_REG', '2': '+5V'},
      note='Drawn with a dashed core line'),
    P('C128', '.1uF', 'C', at=(60, 414), pins={'1': '+5V', '2': '5F_GND_D'}),
    P('C131', '2.2uF/25V', 'CP', at=(78, 414), pins={'1': '+5V', '2': '5F_GND_D'}),
    P('L7', 'R100', 'L', at=(120, 432), rot=270, pins={'1': '5F_5V_REG', '2': '+5V'},
      note='Drawn with a dashed core line. Its output is also labelled +5V, which puts L0 and L7 '
           'in parallel (lower +5V returns to open GND, upper to the filled ground)'),
    P('C127', '.1uF', 'C', at=(60, 446), pins={'1': '+5V', '2': 'GND'}),
    P('C130C', '2.2uF/25V', 'CP', at=(78, 446), pins={'1': '+5V', '2': 'GND'}, printed='C130',
      note='C130 printed three times on FIG 5F'),
    P('R239', '?', 'R', at=(160, 444), pins={'1': '5F_GND_D', '2': 'GND'},
      note='No value printed; joins the filled-ground return to the open-ground return'),
]

WIRES = [
    ('R272.2', 'QX1.C', 'vh'),
    ('R273.1', 'QX1.B'), ('U55.6', 'R273.2'), ('U45.6', 'R250.2'),
    ('R252.1', 'U55.3'), ('R237.1', 'U45.2'),
    ('J12.3', 'J12.4'), ('J12.5', 'J12.6'),
    ('R216.1', 'C121.1'), ('R216.2', 'C121.2'),
    ('C119.1', 'R231.1'), ('R231.1', 'C120.1'), ('C120.1', 'R220.1'),
]

NOTES = [
    ('FIG 5F-1', 15, 30),
    ('Printed "10V" -> net +10V.  "+SUREF" as printed (probably +5VREF).\n'
     'R230 lower end continues across the sheet 12/13 match line to the +15V rail.', 15, 195),
    ('FIG 5F-2', 15, 240),
    ('J12-3/4 node (fused side) flag printed "+27VINK(RM) / +48VINK(TM)".\n'
     'J12-5/6 node flag printed with the SAME text; kept as separate net 5F_VIN_RTN\n'
     '(same name would short the converter input). J12-7 = POLARIZING KEY.', 300, 430),
    ('Filled-triangle ground = net 5F_GND_D ("D" side of the A / GND / D split, R229C 100K).\n'
     'Both inductor outputs are printed "+5V".', 240, 440),
]
