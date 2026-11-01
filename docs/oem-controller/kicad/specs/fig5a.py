"""FIG 5A - board connectors, rack/tower option table, 80_RESET comparator, spare gates/op-amps."""

from oemsch import P

TITLE = 'FIG 5A - Connectors, option table, reset comparator, spare sections'
SOURCE = 'US6098409 sheet 4 of 25 (PDF p5), FIG 5A'
PAPER = 'A2'

DUP = 'Printed pin number repeats on this symbol; suffix #n added to keep pins distinct'
NOREF = 'No reference designator printed for this connector'


def _two_row(pins, extra=(), gaps=3):
    """Dual-row header: odd pins left, even pins right, `gaps` blank rows between pins."""
    left, right = [], []
    for number in range(1, pins + 1, 2):
        left += [(str(number), str(number))] + [None] * gaps
        right += [(str(number + 1), str(number + 1))] + [None] * gaps
    for entry in extra:
        left += [entry] + [None] * gaps
    return {'left': left[:-gaps], 'right': right[:-gaps], 'prefix': 'J'}


SYMBOLS = {
    # MC93 gates drawn as NAND (U29) / OR-with-inverted-inputs (U44); pin numbers as printed
    'F5A_MC93_U44A': {'left': [('?', 'A'), ('2', 'B')], 'right': [('3', 'Y')]},
    'F5A_MC93_U44B': {'left': [('4', 'A'), ('3', 'B')], 'right': [('4#2', 'Y')]},
    'F5A_MC93_U29A': {'left': [('11', 'A'), ('13', 'B')], 'right': [('11#2', 'Y')]},
    'F5A_MC93_U29B': {'left': [('1', 'A'), ('2', 'B')], 'right': [('3', 'Y')]},
    'F5A_MC04_A': {'left': [('1', 'A')], 'right': [('2', '~{Y}')]},
    'F5A_MC04_B': {'left': [('3', 'A')], 'right': [('4', '~{Y}')]},
    'F5A_74HC153': {
        'left': [('10', 'C0'), None, ('14', 'C1'), None, ('2', 'C2'), None, None,
                 ('10#2', 'C0'), None, ('11', 'C1'), None, ('12', 'C2'), None, ('13', 'C3')],
        'right': [None, None, None, None, None, ('10#3', 'V')],
    },
    'F5A_LT1011A': {
        'left': [('2', '+'), ('3', '-')], 'right': [('7', 'OUT')],
        'top': [('4', '4'), ('5', '5'), ('6', '6')],
        'bottom': [('?a', 'V-'), ('?b', 'GND')],
    },
    'F5A_DG413_S3': {'left': [('11', 'S')], 'right': [('10', 'D')]},
    'F5A_DG413_S4': {'left': [('6', 'S')], 'right': [('7', 'D')]},
    'F5A_CONN34': _two_row(34, extra=[('KEY', 'KEY')]),
    'F5A_CONN16': _two_row(16),
    'F5A_CONN26': _two_row(26, gaps=1),
}

# ── 34-pin connector J5A1: BWT_/temperature/CS signals through 1K series resistors ──
J34_AT = (400, 100)
J34_SIGNALS = [  # (resistor, net, odd pin)
    ('R17', 'BWT_6R', 1), ('R18', 'BWT_6P', 3), ('R19', 'BWT_5R', 5), ('R20', 'BWT_5P', 7),
    ('R21', 'BWT_4R', 9), ('R22', 'BWT_4P', 11), ('R23', 'BWT_3R', 13), ('R24', 'BWT_3P', 15),
    ('R25', 'BWT_2R', 17), ('R26', 'BWT_2P', 19), ('R27', 'BWT_1R', 21), ('R28', 'BWT_1P', 23),
    ('R29', 'AMB_TEMP', 25), ('R30', 'DEWAR_TEMP', 27), ('R31', 'CS_CNTRL', 29),
]
# ── 16-pin connector J5A2: CST_/CFT_ through 1K ──
J16_AT = (400, 250)
J16_SIGNALS = [('R84', 'CST_1', 1), ('R85', 'CST_2', 3), ('R86', 'CFT_T2', 9), ('R87', 'CFT_T1', 11)]


def _pin_row(conn_at, pin, rows):
    """Sheet row of an odd/even pin on a _two_row header with `rows` symbol rows."""
    half = 2 * ((rows + 2) // 2)
    index = 4 * ((pin - 1) // 2)
    return conn_at[1] - half + 2 + 2 * index


def _series(conn_at, rows, signals, conn_ref):
    parts, wires = [], []
    for ref, net, pin in signals:
        row = _pin_row(conn_at, pin, rows)
        node = f'5A_{conn_ref}_{pin}'
        parts.append(P(ref, '1K', 'R', at=(conn_at[0] - 30, row), rot=90,
                       pins={'1': net, '2': node}))
        wires.append((f'{ref}.2', f'{conn_ref}.{pin}'))
    return parts, wires


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

PARTS = [
    # ── Spare MC93 gates (inputs tied to GND, outputs open) ──
    P('U44A', 'MC93', 'F5A_MC93_U44A', at=(40, 50), printed='U44',
      pins={'?': '5A_U44A_A_open', '2': 'GND', '3': '5A_U44A_3_open'}, probable='MC14093B (quad 2-in NAND Schmitt)',
      note='Upper input drawn with an inversion bubble but no pin number and no connection'),
    P('U44B', 'MC93', 'F5A_MC93_U44B', at=(40, 70), printed='U44',
      pins={'4': 'GND', '3': 'GND', '4#2': '5A_U44B_4_open'}, probable='MC14093B',
      note='Inputs printed 4 and 3, output printed 4 (pin 4 printed twice). ' + DUP),
    P('U29A', 'MC93', 'F5A_MC93_U29A', at=(40, 90), printed='U29',
      pins={'11': 'GND', '13': 'GND', '11#2': '5A_U29A_11_open'}, probable='MC14093B',
      note='Inputs printed 11 and 13, output printed 11. ' + DUP
      + '. U29 is also printed as MC2001 on FIG 5B (ref clash)'),
    P('U29B', 'MC93', 'F5A_MC93_U29B', at=(40, 110), printed='U29',
      pins={'1': 'GND', '2': 'GND', '3': '5A_U29B_3_open'}, probable='MC14093B',
      note='U29 is also printed as MC2001 on FIG 5B (ref clash)'),
    # ── Spare MC04 inverters ──
    P('U19A', 'MC04', 'F5A_MC04_A', at=(95, 45), printed='U19',
      pins={'1': 'GND', '2': '5A_U19A_2_open'}, probable='MC74HC04 / MC14069 hex inverter'),
    P('U19B', 'MC04', 'F5A_MC04_B', at=(150, 45), printed='U19',
      pins={'3': 'GND', '4': '5A_U19B_4_open'}, probable='MC74HC04 / MC14069 hex inverter'),
    # ── Spare op-amp sections (drawn as followers, + input marked on the fed-back pin) ──
    P('U11', 'LMC6-482', 'OPAMP', at=(100, 72), rot=180, mirror=True,
      pinmap={'+': '6', '-': '5', 'out': '2'},
      pins={'6': '5A_U11_FB', '2': '5A_U11_FB', '5': 'GND'}, probable='LMC6482',
      note='Output printed 2 with inputs 6/5; + sign drawn on the fed-back pin 6'),
    P('U33', 'LMC6-482', 'OPAMP', at=(100, 100), rot=180, mirror=True,
      pinmap={'+': '2', '-': '3', 'out': '7'},
      pins={'2': '5A_U33_FB', '7': '5A_U33_FB', '3': 'GND'}, probable='LMC6482',
      note='Output printed 7 with inputs 2/3; + sign drawn on the fed-back pin 2'),
    P('U14', 'LMC6-482', 'OPAMP', at=(150, 100), rot=180, mirror=True,
      pinmap={'+': '6', '-': '5', 'out': '7'},
      pins={'6': '5A_U14_FB', '7': '5A_U14_FB', '5': 'GND'}, probable='LMC6482',
      note='+ sign drawn on the fed-back pin 6'),
    P('U46', 'LT1124', 'OPAMP', at=(45, 140), rot=180, mirror=True,
      pinmap={'+': '2', '-': '3', 'out': '7'},
      pins={'2': '5A_U46_FB', '7': '5A_U46_FB', '3': 'GND'},
      note='Output printed 7 with inputs 2/3; + sign drawn on the fed-back pin 2'),
    P('U54', 'LT1124', 'OPAMP', at=(100, 140), rot=180, mirror=True, printed='U54',
      pinmap={'+': '6', '-': '5', 'out': '7'},
      pins={'6': '5A_U54_FB', '7': '5A_U54_FB', '5': 'GND'},
      note='+ sign drawn on the fed-back pin 6. FIG 5B U54 also uses output pin 7'),
    # ── U17 74HC153 (selects from PA5/PA6, data inputs grounded, output open) ──
    P('U17', '74HC153', 'F5A_74HC153', at=(55, 190),
      pins={'10': 'GND', '14': 'PA5', '2': 'PA6', '10#2': 'GND', '11': 'GND', '12': 'GND',
            '13': 'GND', '10#3': '5A_U17_V_open'},
      note='Pin 10 printed three times (upper C0, lower C0, output V). '
      'PA5/PA6 drive pins 14/2 (74HC153 select A/B) though labelled C1/C2. ' + DUP),
    # ── U56 LT1011A 80_RESET comparator ──
    P('U56', 'LT1011A', 'F5A_LT1011A', at=(160, 225),
      pins={'2': '5A_U56_P', '3': '5A_U56_N', '7': '80_RESET', '4': '+15V', '5': '5A_U56_5',
            '6': '5A_U56_6', '?a': '-15V', '?b': 'DGND'},
      note='+15V line drawn into the pin printed 4; -15V pin and filled-arrow ground pin '
      'unnumbered (LT1011 data sheet: 4=V-, 8=V+, 1=GND)'),
    P('R274', '32.0k', 'R', at=(140, 200), pins={'1': '+15V', '2': '5A_U56_P'}),
    P('R276', '?', 'R', at=(175, 195), rot=90, pins={'1': '5A_U56_P', '2': '80_RESET'},
      note='No value printed'),
    P('R277', '12.4k', 'R', at=(125, 223), rot=90, pins={'1': 'GND', '2': '5A_U56_P'}),
    P('R278', '7.2k', 'R', at=(125, 232), rot=90, pins={'1': '+5V', '2': '5A_U56_N'}),
    P('C170', '.001uF', 'C', at=(140, 240), pins={'1': '5A_U56_N', '2': 'GND'}),
    P('C165', '.01uF', 'C', at=(165, 210), rot=90, pins={'1': '5A_U56_5', '2': '5A_U56_6'}),
    P('C164', '.1uF', 'C', at=(110, 200), pins={'1': '+15V', '2': 'GND'}),
    P('C166', '.1uF', 'C', at=(175, 250), pins={'1': '-15V', '2': 'GND'}),
    P('R275', '10k', 'R', at=(195, 215), pins={'1': '+5V', '2': '80_RESET'}),
    # ── U43 spare DG413 sections (unconnected) ──
    P('U43A', 'DG413', 'F5A_DG413_S3', at=(60, 275), printed='U43',
      pins={'11': '5A_U43_11_open', '10': '5A_U43_10_open'},
      note='Spare switch; control pin drawn but unnumbered and unconnected'),
    P('U43B', 'DG413', 'F5A_DG413_S4', at=(110, 275), printed='U43',
      pins={'6': '5A_U43_6_open', '7': '5A_U43_7_open'},
      note='Spare switch; control pin drawn but unnumbered and unconnected'),
    # ── Connectors ──
    P('J5A1', '34-pin', 'F5A_CONN34', at=J34_AT, pins=J34_PINS, printed='(none)',
      note=NOREF + '; even pins bussed to GND; 31/33 drawn open; KEY row below 33'),
    P('J5A2', '16-pin', 'F5A_CONN16', at=J16_AT, pins=J16_PINS, printed='(none)',
      note=NOREF + '; even pins bussed to GND; 5/7/13 drawn open; pin 15 labelled KEY'),
    P('J5A3', '26-pin', 'F5A_CONN26', at=(300, 265), pins=J26_PINS, printed='(none)',
      note=NOREF + '; BWT_4P printed on both pin 9 and pin 11; pin 16 N/C'),
]

WIRES = []
for _parts, _wires in (_series(J34_AT, 69, J34_SIGNALS, 'J5A1'),
                       _series(J16_AT, 29, J16_SIGNALS, 'J5A2')):
    PARTS += _parts
    WIRES += _wires

# even-pin GND busses
WIRES += [(f'J5A1.{n}', f'J5A1.{n + 2}', 'vh') for n in range(2, 34, 2)]
WIRES += [(f'J5A2.{n}', f'J5A2.{n + 2}', 'vh') for n in range(2, 16, 2)]
WIRES += [('J5A3.21', 'J5A3.23', 'vh'), ('J5A3.22', 'J5A3.24', 'vh')]
WIRES += [
    ('U29A.11', 'U29A.13', 'vh'), ('U29B.1', 'U29B.2', 'vh'), ('U44B.4', 'U44B.3', 'vh'),
    ('R277.2', 'U56.2'), ('R274.2', 'U56.2', 'vh'), ('R276.1', 'R274.2', 'vh'),
    ('R278.2', 'U56.3'), ('C170.1', 'R278.2', 'vh'), ('C165.1', 'U56.5'), ('C165.2', 'U56.6', 'vh'),
    ('U56.7', 'R275.2'),
    ('U17.11', 'U17.12', 'vh'), ('U17.12', 'U17.13', 'vh'), ('U17.10#2', 'U17.11', 'vh'),
]

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
     'R189      OMIT              OMIT', 215, 40),
    ('Connector refs J5A1/J5A2/J5A3 are placeholders: no refs printed on FIG 5A.\n'
     'Nets ending _open = pin drawn with an unterminated line.\n'
     'DGND = filled-arrow ground symbol (distinct from hollow-triangle GND).', 215, 300),
]
