"""FIG 5A - board connectors, rack/tower option table, 80_RESET comparator, spare gates/op-amps.

Redrawn to the drawing rules: three child sheets (connectors, reset comparator, unused
IC sections) with wires inside each and hierarchical labels to the figure page. The
patent text does not describe FIG 5A; descriptions cite what the figure prints and
mark the rest as inferred.
"""

from oemsch import P, child, port, tap

TITLE = 'FIG 5A - Connectors, reset comparator'
SOURCE = 'US6098409 sheet 4 of 25 (PDF p5), FIG 5A'
PAPER = 'A3'
REDRAWN = True

DUP = 'Printed pin number repeats on this symbol; suffix #n added to keep pins distinct'
NOREF = 'No reference designator printed for this connector'
_INF = 'Inferred from the circuit: '
MC93 = 'MC14093B quad 2-input NAND Schmitt trigger (printed MC93)'
MC04 = '74HC04 or MC14069 hex inverter (printed MC04)'


def _two_row(pins, extra=(), gaps=3, odd='left'):
    """Dual-row header: odd pins on side `odd`, even pins opposite, `gaps` blank rows between."""
    left, right = [], []
    for number in range(1, pins + 1, 2):
        left += [(str(number), str(number))] + [None] * gaps
        right += [(str(number + 1), str(number + 1))] + [None] * gaps
    for entry in extra:
        left += [entry] + [None] * gaps
    left, right = left[:-gaps], right[:-gaps]
    if odd == 'right':
        left, right = right, left
    return {'left': left, 'right': right, 'prefix': 'J'}


SYMBOLS = {
    # MC93 gates drawn as NAND (U29) / OR-with-inverted-inputs (U44); pin numbers as printed
    # MC93 gates in the shapes printed: U29 as NAND, U44 as OR with inverted inputs (the same
    # function). One symbol per gate: the printed pin numbers repeat across gates of one part.
    'F5A_MC93_U44A': {'gate': 'or_inv', 'inputs': [('?', 'A'), ('2', 'B')], 'output': ('3', 'Y')},
    'F5A_MC93_U44B': {'gate': 'or_inv', 'inputs': [('4', 'A'), ('3', 'B')], 'output': ('4#2', 'Y')},
    'F5A_MC93_U29A': {'gate': 'nand', 'inputs': [('11', 'A'), ('13', 'B')], 'output': ('11#2', 'Y')},
    'F5A_MC93_U29B': {'gate': 'nand', 'inputs': [('1', 'A'), ('2', 'B')], 'output': ('3', 'Y')},
    'F5A_MC04_A': {'gate': 'inv', 'inputs': [('1', 'A')], 'output': ('2', 'Y')},
    'F5A_MC04_B': {'gate': 'inv', 'inputs': [('3', 'A')], 'output': ('4', 'Y')},
    # 74HC153 section 2 with the datasheet pin names and the patent's printed numbers
    # (printed C0/C1/C2/C0-C3/V; see TRANSCRIPTION_NOTES).
    'F5A_74HC153': {
        'left': [('14', 'A'), None, ('2', 'B'), None, ('10', '~{2G}'), None, None,
                 ('10#2', '2C0'), None, ('11', '2C1'), None, ('12', '2C2'), None, ('13', '2C3')],
        'right': [None, None, None, None, None, None, ('10#3', '2Y')],
    },
    # LT1011A as printed on FIG 5A (4 = the +15V pin, ?a/?b unnumbered); laid out like the
    # FIG 5C comparator: inputs left, output and balance pins right, supplies top, GND bottom.
    'F5A_LT1011A': {
        'left': [('2', '+'), None, ('3', '-')],
        'right': [('7', 'OUT'), None, ('5', '5'), None, None, None, None, ('6', '6')],
        'top': [('4', '~'), None, None, ('?a', 'V-')],
        'bottom': [('?b', 'GND')],
        'prefix': 'U',
    },
    'F5A_DG413_S3': {'left': [('11', 'S')], 'right': [('10', 'D')]},
    'F5A_DG413_S4': {'left': [('6', 'S')], 'right': [('7', 'D')]},
    'F5A_CONN34': _two_row(34, extra=[('KEY', 'KEY')], odd='right'),
    'F5A_CONN16': _two_row(16, odd='right'),
    'F5A_CONN26': _two_row(26, gaps=1),
}


def _pin_row(conn_at, pin, rows):
    """Sheet row of an odd pin on a _two_row header with `rows` symbol rows."""
    half = 2 * ((rows + 2) // 2)
    index = 4 * ((pin - 1) // 2)
    return conn_at[1] - half + 2 + 2 * index


# ── Connectors: J5A1 (34-pin) and J5A2 (16-pin) through 1K series resistors, J5A3 (26-pin) ──
J34_AT = (45, 105)
J34_SIGNALS = [  # (resistor, net, odd pin)
    ('R17', 'BWT_6R', 1), ('R18', 'BWT_6P', 3), ('R19', 'BWT_5R', 5), ('R20', 'BWT_5P', 7),
    ('R21', 'BWT_4R', 9), ('R22', 'BWT_4P', 11), ('R23', 'BWT_3R', 13), ('R24', 'BWT_3P', 15),
    ('R25', 'BWT_2R', 17), ('R26', 'BWT_2P', 19), ('R27', 'BWT_1R', 21), ('R28', 'BWT_1P', 23),
    ('R29', 'AMB_TEMP', 25), ('R30', 'DEWAR_TEMP', 27), ('R31', 'CS_CTRL', 29),
]
J16_AT = (135, 80)
J16_SIGNALS = [('R84', 'CST_1', 1), ('R85', 'CST_2', 3), ('R86', 'CFT_T2', 9), ('R87', 'CFT_T1', 11)]
J26_AT = (250, 105)

J34_PINS = {str(n): 'GND' for n in range(2, 35, 2)}
J34_PINS.update({'31': '5A_J5A1_31_open', '33': '5A_J5A1_33_open', 'KEY': '5A_J5A1_KEY_open'})
J34_PINS.update({str(pin): f'5A_J5A1_{pin}' for _, _, pin in J34_SIGNALS})

J16_PINS = {str(n): 'GND' for n in range(2, 17, 2)}
J16_PINS.update({'5': '5A_J5A2_5_open', '7': '5A_J5A2_7_open', '13': '5A_J5A2_13_open',
                 '15': '5A_J5A2_15_KEY_open'})
J16_PINS.update({str(pin): f'5A_J5A2_{pin}' for _, _, pin in J16_SIGNALS})

J26_PINS = {
    '1': 'BWT_1P', '2': 'CST_1', '3': 'BWT_2P', '4': 'BWT_1R', '5': 'BWT_3P', '6': 'BWT_2R',
    '7': 'CST_2', '8': 'BWT_3R', '9': 'BWT_4P', '10': 'REF_1', '11': 'BWT_4P', '12': 'BWT_5P',
    '13': 'BWT_4R', '14': 'BWT_6P', '15': 'BWT_5R', '16': 'NC', '17': '+12V', '18': '+15V',
    '19': '-12V', '20': '-15V', '21': 'GND', '22': 'GND', '23': 'GND', '24': 'GND',
    '25': 'CFT_T2', '26': 'CFT_T1',
}


def _series(conn_at, rows, signals, conn_ref):
    """1K series resistors in line with a header's odd pins: parts, wires, ports, net names."""
    parts, wires, ports = [], [], []
    for ref, net, pin in signals:
        row = _pin_row(conn_at, pin, rows)
        parts.append(P(ref, '1K', 'R', at=(conn_at[0] + 30, row), rot=270,
                       pins={'1': net, '2': f'5A_{conn_ref}_{pin}'},
                       desc=_INF + f'1K series resistor between {conn_ref} pin {pin} and {net} '
                                   '(isolates the off-board line; role inferred)'))
        wires.append((f'{ref}.2', f'{conn_ref}.{pin}'))
        ports.append(port(net, SHAPES.get(net, 'passive'), on=f'{ref}.1', side='right'))
    return parts, wires, ports


# direction seen from FIG 5A, where another figure states it; the rest are connector lines
SHAPES = {'CS_CTRL': 'input', 'REF_1': 'input'}
_P34, _W34, _PORTS34 = _series(J34_AT, 69, J34_SIGNALS, 'J5A1')
_P16, _W16, _PORTS16 = _series(J16_AT, 29, J16_SIGNALS, 'J5A2')
OPEN_CONN = ['5A_J5A1_31_open', '5A_J5A1_33_open', '5A_J5A1_KEY_open', '5A_J5A2_5_open',
             '5A_J5A2_7_open', '5A_J5A2_13_open', '5A_J5A2_15_KEY_open']

CONN = child(
    'conn', 'Board connectors J5A1, J5A2, J5A3', short='CONN', paper='A3', at=(20, 36), width=50.8,
    parts=[
        P('J5A1', '34-pin', 'F5A_CONN34', at=J34_AT, pins=J34_PINS, printed='(none)',
          probable='2x17 0.1 in dual-row header (from the pin layout; not printed)',
          note=NOREF + '; even pins bussed to GND; 31/33 drawn open; KEY row below 33',
          desc='Patent: FIG 5A 34-pin connector (no ref printed). Inferred from the circuit: off-board '
               'cable for the six BWT_ P/R pairs, AMB_TEMP, DEWAR_TEMP and CS_CTRL, each through a 1K '
               'resistor; every even pin is ground'),
        P('J5A2', '16-pin', 'F5A_CONN16', at=J16_AT, pins=J16_PINS, printed='(none)',
          probable='2x8 0.1 in dual-row header (from the pin layout; not printed)',
          note=NOREF + '; even pins bussed to GND; 5/7/13 drawn open; pin 15 labelled KEY',
          desc='Patent: FIG 5A 16-pin connector (no ref printed). Inferred from the circuit: off-board '
               'cable for CST_1, CST_2, CFT_T1 and CFT_T2, each through a 1K resistor; every even pin '
               'is ground'),
        P('J5A3', '26-pin', 'F5A_CONN26', at=J26_AT, pins=J26_PINS, printed='(none)',
          probable='2x13 0.1 in dual-row header (from the pin layout; not printed)',
          note=NOREF + '; BWT_4P printed on both pin 9 and pin 11; pin 16 N/C',
          desc='Patent: FIG 5A 26-pin connector (no ref printed). Inferred from the circuit: the '
               'mother-board end of the daughter-board cable (same pin-out as J10 on FIG 6C), carrying '
               'the BWT_, CST_, CFT_ lines, REF_1 and the +-12V/+-15V supplies'),
    ] + _P34 + _P16,
    ports=_PORTS34 + _PORTS16 + [port('REF_1', 'input', on='J5A3.10', side='right')],
    wires=_W34 + _W16
    + [(f'J5A1.{n}', f'J5A1.{n + 2}') for n in range(2, 34, 2)]
    + [(f'J5A2.{n}', f'J5A2.{n + 2}') for n in range(2, 16, 2)]
    + [('J5A3.21', 'J5A3.23'), ('J5A3.22', 'J5A3.24'), ('J5A3.9', 'J5A3.11')],
    long_nets={net for _, net, _ in J34_SIGNALS + J16_SIGNALS} | set(OPEN_CONN),
    names={'GND': ['J5A1.34', 'J5A2.16', 'J5A3.23', 'J5A3.24'], 'BWT_4P': 'J5A3.11'},
    notes=[('J5A1 34-PIN CONNECTOR, 1K SERIES RESISTORS', 25, 27),
           ('J5A2 16-PIN CONNECTOR, 1K SERIES RESISTORS', 115, 42),
           ('J5A3 26-PIN CONNECTOR (DAUGHTER-BOARD CABLE)', 215, 70),
           ('Connector refs J5A1/J5A2/J5A3 are placeholders: no refs printed on FIG 5A.\n'
            'Nets ending _open = pin drawn with an unterminated line.\n'
            'J5A1 pin 29 is printed CS_CNTRL; joined to CS_CTRL (5B, 5H) as a misprint.', 15, 200)],
)

# ── 80_RESET comparator: U56 LT1011A ──
RESET = child(
    'reset', '80_RESET comparator (U56)', short='RESET', paper='A4', at=(100, 36), width=35.56,
    parts=[
        P('U56', 'LT1011A', 'F5A_LT1011A', at=(110, 80), text=(-13, -14),
          pins={'2': '5A_U56_P', '3': '5A_U56_N', '7': '80_RESET', '4': '+15V', '5': '5A_U56_5',
                '6': '5A_U56_6', '?a': '-15V', '?b': 'DGND'},
          note='+15V line drawn into the pin printed 4; -15V pin and filled-arrow ground pin '
          'unnumbered (LT1011 data sheet: 4=V-, 8=V+, 1=GND)',
          desc=_INF + 'comparator making 80_RESET. + input: +15V divided by R274/R277 (about 4.2 V), '
                      'with R276 feedback from the output; - input: +5V through R278, filtered by C170. '
                      'Inferred role: supply monitor / reset; the patent does not describe it'),
        P('R274', '32.0k', 'R', at=(86, 62), pins={'1': '+15V', '2': '5A_U56_P'},
          desc=_INF + 'upper leg of the +15V divider into the U56 + input'),
        P('R277', '12.4k', 'R', at=(70, 82), rot=180, pins={'1': 'GND', '2': '5A_U56_P'},
          desc=_INF + 'lower leg of the +15V divider into the U56 + input'),
        P('R276', '?', 'R', at=(110, 48), rot=90, pins={'1': '5A_U56_P', '2': '80_RESET'},
          note='No value printed',
          desc=_INF + 'feedback from the U56 output to its + input (hysteresis); value not printed'),
        P('R278', '7.2k', 'R', at=(82, 86), pins={'1': '+5V', '2': '5A_U56_N'},
          desc=_INF + 'feeds +5V into the U56 - input'),
        P('C170', '.001uF', 'C', at=(88, 101), pins={'1': '5A_U56_N', '2': 'GND'},
          desc=_INF + 'filter capacitor on the U56 - input'),
        P('C165', '.01uF', 'C', at=(136, 81), pins={'1': '5A_U56_5', '2': '5A_U56_6'},
          desc=_INF + 'capacitor across the U56 balance pins 5 and 6 (response shaping)'),
        P('R275', '10k', 'R', at=(136, 62), pins={'1': '+5V', '2': '80_RESET'},
          desc=_INF + 'pull-up to +5V for the U56 open-collector output'),
        P('C164', '.1uF', 'C', at=(40, 140), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U56 +15V supply decoupling'),
        P('C166', '.1uF', 'C', at=(52, 140), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U56 -15V supply decoupling'),
    ],
    taps=[tap('rst', '80_RESET', (150, 72), facing='right')],
    wires=[
        ('R274.2', 'U56.2', 'vh'), ('R277.2', 'U56.2', [(70, 72)]),
        ('R276.1', 'U56.2', [(76, 48), (76, 72)]), ('R276.2', 'U56.7', [(130, 48), (130, 72)]),
        ('R278.2', 'C170.1', [(82, 96)]), ('C170.1', 'U56.3', [(92, 96), (92, 76)]),
        ('U56.5', 'C165.1'), ('U56.6', 'C165.2'),
        ('R275.2', 'U56.7', 'vh'), ('U56.7', '@rst'),
        ('C164.2', 'C166.2'),
    ],
    long_nets={'80_RESET'},
    names={'80_RESET': '@rst', '5A_U56_P': 'U56.2', '5A_U56_N': 'U56.3', '5A_U56_5': 'U56.5',
           '5A_U56_6': 'U56.6', 'GND': ['C164.2']},
    notes=[('80_RESET COMPARATOR (U56)', 60, 36),
           ('U56 DECOUPLING CAPACITORS', 32, 128),
           ('80_RESET is printed as an off-page flag; no transcribed figure uses it.\n'
            'U56 pin ?b: DGND, the filled-arrow ground (distinct from the hollow-triangle GND).', 15, 150)],
)

# ── Unused IC sections, tied off as printed ──
_OP_COLS = (40, 95, 150, 205, 260)
_OPAMPS = [  # ref, value, + (fed back), -, out, printed, note
    ('U11', 'LMC6-482', '6', '5', '2', None, 'Output printed 2 with inputs 6/5; + sign drawn on the fed-back pin 6'),
    ('U33', 'LMC6-482', '2', '3', '7', None, 'Output printed 7 with inputs 2/3; + sign drawn on the fed-back pin 2'),
    ('U14', 'LMC6-482', '6', '5', '7', None, '+ sign drawn on the fed-back pin 6'),
    ('U46', 'LT1124', '2', '3', '7', None, 'Output printed 7 with inputs 2/3; + sign drawn on the fed-back pin 2'),
    ('U54', 'LT1124', '6', '5', '7', 'U54', '+ sign drawn on the fed-back pin 6. FIG 5B U54 also uses output pin 7'),
]


def _opamp_parts():
    parts, wires, names = [], [], {}
    for col, (ref, value, plus, minus, out, printed, note) in zip(_OP_COLS, _OPAMPS):
        net = f'5A_{ref}_FB'
        parts.append(P(ref, value, 'OPAMP', at=(col, 100), rot=180, mirror=True, printed=printed, text=(-4, 6),
                       pinmap={'+': plus, '-': minus, 'out': out},
                       pins={plus: net, out: net, minus: 'GND'},
                       probable='LMC6482' if value == 'LMC6-482' else None, note=note,
                       desc=f'Patent: FIG 5A unused section of {ref}, drawn as a follower with the + sign on '
                            'the fed-back input and the other input grounded (transcribed as printed)'))
        wires.append((f'{ref}.{out}', f'{ref}.{plus}', [(col + 8, 92), (col - 12, 92), (col - 12, 98)]))
        names[net] = f'{ref}.{out}'
    return parts, wires, names


_OP_PARTS, _OP_WIRES, _OP_NAMES = _opamp_parts()
_GATE = 'Patent: FIG 5A unused gate of {}; inputs tied to GND, output drawn open'

SPARES = child(
    'spares', 'Spare and tied-off IC sections (as printed)', short='SPARES', paper='A3', at=(100, 64),
    width=35.56,
    parts=[
        P('U44A', 'MC93', 'F5A_MC93_U44A', at=(40, 50), text=(-4, -8), printed='U44', probable=MC93,
          pins={'?': '5A_U44A_A_open', '2': 'GND', '3': '5A_U44A_3_open'},
          note='Upper input drawn with an inversion bubble but no pin number and no connection',
          desc='Patent: FIG 5A unused gate of U44; one input grounded, the other and the output drawn open'),
        P('U44B', 'MC93', 'F5A_MC93_U44B', at=(90, 50), text=(-4, -8), printed='U44', probable=MC93,
          pins={'4': 'GND', '3': 'GND', '4#2': '5A_U44B_4_open'},
          note='Inputs printed 4 and 3, output printed 4 (pin 4 printed twice). ' + DUP,
          desc=_GATE.format('U44')),
        P('U29A', 'MC93', 'F5A_MC93_U29A', at=(140, 50), text=(-4, -8), printed='U29', probable=MC93,
          pins={'11': 'GND', '13': 'GND', '11#2': '5A_U29A_11_open'},
          note='Inputs printed 11 and 13, output printed 11. ' + DUP
          + '. U29 is also printed as MC2001 on FIG 5B (ref clash)',
          desc=_GATE.format('U29')),
        P('U29B', 'MC93', 'F5A_MC93_U29B', at=(190, 50), text=(-4, -8), printed='U29', probable=MC93,
          pins={'1': 'GND', '2': 'GND', '3': '5A_U29B_3_open'},
          note='U29 is also printed as MC2001 on FIG 5B (ref clash)',
          desc=_GATE.format('U29')),
        P('U19A', 'MC04', 'F5A_MC04_A', at=(240, 50), text=(-4, -7), printed='U19', probable=MC04,
          pins={'1': 'GND', '2': '5A_U19A_2_open'},
          desc='Patent: FIG 5A unused inverter of U19; input grounded, output drawn open'),
        P('U19B', 'MC04', 'F5A_MC04_B', at=(285, 50), text=(-4, -7), printed='U19', probable=MC04,
          pins={'3': 'GND', '4': '5A_U19B_4_open'},
          desc='Patent: FIG 5A unused inverter of U19; input grounded, output drawn open'),
    ] + _OP_PARTS + [
        P('U43A', 'DG413', 'F5A_DG413_S3', at=(40, 150), text=(-3, -5), printed='U43',
          pins={'11': '5A_U43_11_open', '10': '5A_U43_10_open'},
          note='Spare switch; control pin drawn but unnumbered and unconnected',
          desc='Patent: FIG 5A unused switch of U43; both ends drawn open'),
        P('U43B', 'DG413', 'F5A_DG413_S4', at=(100, 150), text=(-3, -5), printed='U43',
          pins={'6': '5A_U43_6_open', '7': '5A_U43_7_open'},
          note='Spare switch; control pin drawn but unnumbered and unconnected',
          desc='Patent: FIG 5A unused switch of U43; both ends drawn open'),
        P('U17', '74HC153', 'F5A_74HC153', at=(200, 160),
          pins={'10': 'GND', '14': 'PA5', '2': 'PA6', '10#2': 'GND', '11': 'GND', '12': 'GND',
                '13': 'GND', '10#3': '5A_U17_V_open'},
          note='Pin 10 printed three times (upper C0, lower C0, output V). Drawn with the '
          '74HC153 datasheet names: printed C1/C2 (pins 14/2) are A/B, upper C0 is taken as '
          'the strobe 2G (pin 15), V as 2Y (pin 9); printed numbers kept. ' + DUP,
          desc='Patent: FIG 5A U17 with PA5/PA6 on pins 14/2 (the 74HC153 select inputs), its data '
               'inputs grounded and its output drawn open. Inferred: an unused multiplexer section'),
    ],
    taps=[],
    wires=[
        ('U44B.4', 'U44B.3'), ('U29A.11', 'U29A.13'), ('U29B.1', 'U29B.2'),
        ('U17.10', 'U17.10#2'), ('U17.10#2', 'U17.11'), ('U17.11', 'U17.12'), ('U17.12', 'U17.13'),
    ] + _OP_WIRES,
    long_nets={'PA5', 'PA6', '5A_U44A_A_open', '5A_U44A_3_open', '5A_U44B_4_open', '5A_U29A_11_open',
               '5A_U29B_3_open', '5A_U19A_2_open', '5A_U19B_4_open', '5A_U43_11_open',
               '5A_U43_10_open', '5A_U43_6_open', '5A_U43_7_open', '5A_U17_V_open'},
    names={'GND': ['U44B.3', 'U29A.13', 'U29B.2', 'U17.13'], **_OP_NAMES},
    notes=[('UNUSED GATES (U44, U29: MC93; U19: MC04)', 22, 34),
           ('UNUSED OP-AMP SECTIONS (as printed: "+" on the fed-back input)', 22, 84),
           ('UNUSED SWITCHES (U43 DG413)', 22, 138),
           ('U17 74HC153: PA5/PA6 ON THE SELECT PINS, DATA GROUNDED, OUTPUT OPEN', 150, 136)],
)

CHILDREN = [CONN, RESET, SPARES]

# ── Figure page ──
_CONN_NETS = [p.net for p in CONN.PORTS]
PORTS = [port(net, SHAPES.get(net, 'passive'), at=(80, 36 + 4 * (index + 1)), facing='right', side='right')
         for index, net in enumerate(_CONN_NETS)]
PAGE_WIRES = [(f'conn:{net}', f'@{net}') for net in _CONN_NETS]

NOTES = [
    ('OPTION TABLE (as printed)\n'
     'REF DES   RACK MOUNT -001   TOWER MOUNT -002\n'
     'C167      OMIT              .001\n'
     'C168      OMIT              .01\n'
     'C169      OMIT              .01\n'
     'R35       10                49.9\n'
     'R229      100K              200K\n'
     'R230      100K              200K\n'
     'R256      2.05K             OMIT\n'
     'R266      221K              49.9K\n'
     'R267      221K              49.0K\n'
     'R281      OMIT              3.09K\n'
     'R282      OMIT              12.4K\n'
     'R283      OMIT              576\n'
     'R284      0                 OMIT\n'
     'R285      OMIT              10K PDT\n'
     'RT1       OMIT              Y44017\n'
     'VR3       24D15             48D15\n'
     'R287      OMIT              OMIT\n'
     'R200      OMIT              OMIT\n'
     'J15       OMIT              INSTALL\n'
     'R189      OMIT              OMIT', 190, 36),
]

_BWT = {'P': 'P', 'R': 'R'}


def _bwt(net):
    n, side = net[4], net[5]
    return (f'Patent: FIG 5A label {net}. Inferred from the circuit: butter-warmer {n} sensor line '
            f'({side} of the P/R pair), carried between J5A1 (through a 1K resistor), J5A3 and the '
            'FIG 5D driver / FIG 5H multiplexer; exact signal role not stated in the patent')


NET_DESCRIPTIONS = {
    **{net: _bwt(net) for _, net, _ in J34_SIGNALS if net.startswith('BWT_')},
    'AMB_TEMP': 'Patent: FIG 5A label AMB_TEMP. Inferred: ambient temperature signal from the FIG 5H AD590 '
                'channel, out on J5A1 pin 25 through R29',
    'DEWAR_TEMP': 'Patent: FIG 5A label DEWAR_TEMP (printed DEMAR_TEMP on 5H). Inferred: dewar temperature '
                  'signal shared with FIG 5H, on J5A1 pin 27 through R30',
    'CS_CTRL': 'Patent: FIG 5A label CS_CNTRL (= CS_CTRL on 5B/5H). Inferred: output of the FIG 5B U35 '
               'integrator, out on J5A1 pin 29 through R31',
    'CST_1': 'Patent: FIG 5A label CST_1. Inferred: line switched by U43 on FIG 5B, on J5A2 pin 1 (R84) '
             'and J5A3 pin 2; role unknown',
    'CST_2': 'Patent: FIG 5A label CST_2. Inferred: line switched by U43 on FIG 5B, on J5A2 pin 3 (R85) '
             'and J5A3 pin 7; role unknown',
    'CFT_T1': 'Patent: FIG 5A label CFT_T1, on J5A2 pin 11 (R87) and J5A3 pin 26; role unknown',
    'CFT_T2': 'Patent: FIG 5A label CFT_T2, on J5A2 pin 9 (R86) and J5A3 pin 25; role unknown',
    'REF_1': 'Patent: FIG 5A label REF_1 on J5A3 pin 10. Inferred: the 10 V reference from FIG 5F, sent '
             'to the daughter board',
    **{f'5A_J5A1_{pin}': f'Inferred from the circuit: J5A1 pin {pin} side of {ref}'
       for ref, _, pin in J34_SIGNALS},
    **{f'5A_J5A2_{pin}': f'Inferred from the circuit: J5A2 pin {pin} side of {ref}'
       for ref, _, pin in J16_SIGNALS},
    **{net: 'Patent: FIG 5A draws this connector pin with an unterminated line' for net in OPEN_CONN},
    '80_RESET': 'Patent: FIG 5A off-page flag 80_RESET; no transcribed figure uses it. Inferred: U56 '
                'comparator output (pulled up to +5V by R275)',
    '5A_U56_P': 'Inferred from the circuit: U56 + input, +15V divided by R274/R277 with R276 feedback',
    '5A_U56_N': 'Inferred from the circuit: U56 - input, +5V through R278, filtered by C170',
    '5A_U56_5': 'Inferred from the circuit: U56 balance pin 5, to C165',
    '5A_U56_6': 'Inferred from the circuit: U56 balance pin 6, to C165',
    'PA5': 'Patent: FIG 5A off-page flag PA5 into U17 pin 14 (select A). Inferred: a U22 port A line '
           '(FIG 5G); no transcribed figure names it',
    'PA6': 'Patent: FIG 5A off-page flag PA6 into U17 pin 2 (select B). Inferred: a U22 port A line '
           '(FIG 5G); no transcribed figure names it',
    **{f'5A_{ref}_FB': f'Patent: FIG 5A {ref} output fed back to its input (unused follower)'
       for ref, *_ in _OPAMPS},
    **{net: 'Patent: FIG 5A draws this pin with an unterminated line (unused)'
       for net in ('5A_U44A_A_open', '5A_U44A_3_open', '5A_U44B_4_open', '5A_U29A_11_open',
                   '5A_U29B_3_open', '5A_U19A_2_open', '5A_U19B_4_open', '5A_U43_11_open',
                   '5A_U43_10_open', '5A_U43_6_open', '5A_U43_7_open', '5A_U17_V_open')},
}
