"""FIG 5E - mother-board I/O connectors, HOT TOTAL line driver, serial and SPI peripherals.

The sheet is drawn rotated 90 degrees on the patent page; this page is upright.
"""

from oemsch import P

TITLE = 'FIG 5E - I/O connectors, HOT TOTAL line driver, serial/SPI parts'
SOURCE = 'US6098409 sheet 11 of 25 (PDF p12), FIG 5E (drawn rotated)'
PAPER = 'A2'

# Signals that leave this page.
GLOBALS = [
    'BWH_1P', 'BWH_1R', 'BWH_2P', 'BWH_2R', 'BWH_3P', 'BWH_3R',
    'BWH_4P', 'BWH_4R', 'BWH_5P', 'BWH_5R', 'BWH_6P', 'BWH_6R',
    'RAM_SHUTO_T-', 'SYS.RESET', 'FAM.ALIVE3', 'FAM.ALIVE2', 'FAM.ALIVE1', 'NOT_TFLT-',
    '+27URET', 'CRTS_T', 'MOS_T', 'MOS_TR', 'TKD', 'RXD', 'SFD_SND',
    'HOT_TOTAL', 'HOT_RST-', 'CLK.2M', 'NSP_PROG', 'NSP_READ', 'NSP_SERI', 'NSP_CLK',
    'NSP_SER2', 'MOSI', 'SCLK', '99-', 'UP_CNTRL',
]


def _conn(count, side='left'):
    """Single-row connector with a blank row between pins (room for GND symbols)."""
    pins = []
    for number in range(1, count + 1):
        pins += [(str(number), str(number)), None]
    return {side: pins[:-1], 'prefix': 'J'}


SYMBOLS = {
    'F5E_CONN14': _conn(14),
    'F5E_CONN6': _conn(6),
    'F5E_CONN6R': _conn(6, 'right'),
    # Gate drawn as OR body with bubbled inputs and bubbled output (no ref/type printed).
    # Pin "4" is printed on both an input and the output: output numbered '4_OUT' here.
    'F5E_GATE': {
        'left': [('4', '~{A}'), None, ('3', '~{B}')],
        'right': [None, ('4_OUT', '~{Y}')],
        'prefix': 'U',
    },
    # Serial device, pins/names as printed; unnamed pins '~'. GND pin unnumbered ('G').
    'F5E_SERDEV': {
        'left': [('10', 'URF'), None, ('11', '~'), None, ('13', '~'), None, ('12', 'CLOCK'), None,
                 ('15', '~'), None, ('14', '~'), None, ('2', 'SER.IN'), None, ('1', 'SER.CLK')],
        'right': [('4', 'LINE OUT'), None, None, None, None, None, ('6', 'XXXX'), None, None, None,
                  None, None, ('3', 'SER.OUT')],
        'bottom': [('G', 'GND')],
        'prefix': 'U',
    },
    # SPI device: printed pins 1/2/4/5/7; three supply/ground leads unnumbered.
    'F5E_SPIDEV': {
        'left': [('1', 'MOSI'), None, ('2', 'SCLK'), None, ('4', 'IN'), None, ('5', '~')],
        'right': [None, None, None, ('7', '~')],
        'top': [('VT', '~')],
        'bottom': [('VB', '~'), ('GB', '~')],
        'prefix': 'U',
    },
}

ODD_GND = {str(pin): 'GND' for pin in range(1, 14, 2)}
KEY = 'Polarization key pin (no connection drawn; NC flag)'

PARTS = [
    # ── J4 / J3: BWH heater pairs, odd pins grounded ──
    P('J4', 'J4', 'F5E_CONN14', at=(90, 92),
      pins={**ODD_GND, '2': 'BWH_1P', '4': 'BWH_1R', '8': 'BWH_2P', '10': 'BWH_2R',
            '12': 'BWH_3P', '14': 'BWH_3R', '6': 'NC'},
      note='J4-6: ' + KEY),
    P('J3', 'J3', 'F5E_CONN14', at=(90, 216),
      pins={**ODD_GND, '2': 'BWH_4P', '4': 'BWH_4R', '6': 'BWH_5P', '8': 'BWH_5R',
            '12': 'BWH_6P', '14': 'BWH_6R', '10': 'NC'},
      note='J3-10: ' + KEY),

    # ── J8 + gate ──
    P('UG1', '?', 'F5E_GATE', at=(160, 54),
      pins={'4': 'RAM_SHUTO_T-', '3': 'SYS.RESET', '4_OUT': '5E_GATE_OUT'},
      printed='', note=('No ref/type printed. OR shape, bubbled inputs (pins 4, 3) and bubbled output '
                        '(also printed pin 4). Output node also has an unterminated lead drawn upward.')),
    P('J8', 'J8', 'F5E_CONN14', at=(214, 92),
      pins={'1': 'GND', '2': '5E_U10_OUT', '3': '5E_GATE_OUT', '4': '5E_J8_4_STUB',
            '5': 'GND', '6': 'NC', '7': '5E_ARROW_J8_7', '8': 'FAM.ALIVE3', '9': 'FAM.ALIVE2',
            '10': 'FAM.ALIVE1', '11': 'NOT_TFLT-', '12': '5E_J8_12_STUB',
            '13': '5E_J8_13_STUB', '14': '5E_J8_14_STUB'},
      note=('J8-6: ' + KEY + '. J8-7 goes to an unlabeled filled down-arrow. '
            'J8-4, 12, 13, 14 drawn with short unterminated leads.')),

    # ── J14 ──
    P('J14', 'J14', 'F5E_CONN6R', at=(282, 50),
      pins={'1': 'NC', '2': 'GND', '3': '5E_J14_3_STUB', '4': '+27URET', '5': 'CRTS_T', '6': '5E_J14_6'},
      note='J14-1: ' + KEY + '. J14-3 drawn with an unterminated lead. "+27URET" as printed (probably +27VRET).'),
    P('RX1', '?', 'R', at=(318, 72), rot=90, pins={'1': '5E_J14_6', '2': 'GND'},
      printed='', note='Resistor drawn with no ref and no value (J14-6 node to GND)'),
    P('R270', '?', 'R', at=(318, 84), rot=90, pins={'1': '5E_J14_6', '2': '+10V'},
      note='No value printed; far end to a supply arrow printed "10V"'),

    # ── J13 ──
    P('R35', '?', 'R', at=(176, 196), pins={'1': 'MOS_T', '2': 'MOS_TR'}, note='No value printed'),
    P('J13', 'J13', 'F5E_CONN6', at=(214, 202),
      pins={'1': 'MOS_T', '2': 'MOS_TR', '3': 'NC', '4': 'GND', '5': '5E_J13_5_STUB', '6': '5E_J13_6_STUB'},
      note='J13-3: ' + KEY + '. J13-5/6 drawn with unterminated leads.'),

    # ── J9: serial lines through 2100 ferrites ──
    P('C96', '.001uF', 'C', at=(150, 266), pins={'1': 'TKD', '2': '5E_ARROW_C96'},
      note='Bottom end to an unlabeled filled down-arrow'),
    P('L1', '2100', 'L', at=(172, 258), rot=90, pins={'1': 'TKD', '2': '5E_J9_3'},
      probable='Ferrite bead (value "2100")'),
    P('C94', '.001uF', 'C', at=(150, 288), pins={'1': 'RXD', '2': '5E_ARROW_C94'},
      note='Bottom end to an unlabeled filled down-arrow'),
    P('L2', '2100', 'L', at=(172, 280), rot=90, pins={'1': 'RXD', '2': '5E_J9_4'},
      probable='Ferrite bead'),
    P('L4', '2100', 'L', at=(172, 302), rot=90, pins={'1': 'SFD_SND', '2': '5E_J9_5'},
      probable='Ferrite bead'),
    P('J9', 'J9', 'F5E_CONN6', at=(214, 270),
      pins={'1': 'NC', '2': '+5V', '3': '5E_J9_3', '4': '5E_J9_4', '5': '5E_J9_5', '6': '5E_ARROW_J9_6'},
      note='J9-1: ' + KEY + '. J9-6 goes to an unlabeled filled down-arrow.'),

    # ── Serial device + U10 HOT TOTAL line driver ──
    P('R131', '10K', 'R', at=(262, 150), pins={'1': '5E_R131_ARROW', '2': '5E_SER_13'},
      note='Top end to an unlabeled up-arrow (pull-up supply not named)'),
    P('UX1', '?', 'F5E_SERDEV', at=(300, 186),
      pins={'10': 'HOT_TOTAL', '11': 'HOT_RST-', '13': '5E_SER_13', '12': 'CLK.2M',
            '15': 'NSP_PROG', '14': 'NSP_READ', '2': 'NSP_SERI', '1': 'NSP_CLK',
            '4': '5E_LINE_OUT', '6': '5E_SER_XXXX_STUB', '3': 'NSP_SER2', 'G': 'GND'},
      printed='',
      probable='Serial digital pot / DAC of the MC2030 family (same PROG/READ/SER.IN/SER.CLK/SER.OUT pins as FIG 5D)',
      note=('No ref or part number printed. Pins 15/14 labels printed "NSP_PROG-"/"NSP_READ-" '
            '(joined to NSP_PROG/NSP_READ of FIG 5D). Pin 6 "XXXX" drawn as an unterminated lead.')),
    P('R134', '?', 'R', at=(352, 140), rot=90, pins={'1': 'HOT_TOTAL', '2': '5E_U10A_INV'},
      note='No value printed'),
    P('C50', '.15uF', 'C', at=(380, 118), rot=90, pins={'1': '5E_U10A_INV', '2': '5E_U10A_OUT'}),
    P('R133', '14.3K', 'R', at=(380, 130), rot=90, pins={'1': '5E_U10A_INV', '2': '5E_U10A_OUT'}),
    P('R136', '?', 'R', at=(352, 180), rot=90, pins={'1': '5E_LINE_OUT', '2': '5E_U10A_NI'},
      note='No value printed'),
    P('U10A', '1124', 'OPAMP', at=(380, 178),
      pinmap={'-': '2', '+': '3', 'out': '1', 'v+': '8', 'v-': '4'},
      pins={'2': '5E_U10A_INV', '3': '5E_U10A_NI', '1': '5E_U10A_OUT', '8': '+15V', '4': '-15V'},
      printed='U10', probable='LT1124',
      note=('+/- not marked on the drawing (LT1124 pin functions used). Supply pin numbers not printed; '
            'lower supply is an unlabeled down-arrow (-15V assumed).')),
    P('CX1', '?', 'C', at=(394, 158), pins={'1': '+15V', '2': 'GND'}, printed='',
      note='Bypass capacitor drawn with no ref/value'),
    P('CX2', '?', 'C', at=(394, 200), pins={'1': '-15V', '2': 'GND'}, printed='',
      note='Bypass capacitor drawn with no ref/value'),
    P('RX2', '?', 'R', at=(404, 178), rot=90, pins={'1': '5E_U10A_OUT', '2': '5E_U10B_INV'},
      printed='', note='Series resistor drawn with no ref/value (probably R135, missing from the R132-R136 run)'),
    P('C38', '.015uF', 'C', at=(430, 140), rot=90, pins={'1': '5E_U10B_INV', '2': '5E_U10_OUT'}),
    P('R187', '100K', 'R', at=(430, 152), rot=90, pins={'1': '5E_U10B_INV', '2': '5E_U10_OUT'}),
    P('U10B', '1124', 'OPAMP', at=(430, 180), pinmap={'-': '6', '+': '5', 'out': '7'},
      pins={'6': '5E_U10B_INV', '5': '5E_U10B_NI', '7': '5E_U10_OUT'}, printed='U10',
      probable='LT1124', note='+/- not marked on the drawing'),
    P('R185', '10K', 'R', at=(418, 202), pins={'1': '5E_U10B_NI', '2': 'GND'}),
    P('R132', '?', 'R', at=(446, 192), pins={'1': '5E_U10_OUT', '2': '5E_U10_OUT_R'},
      note='No value printed; output end runs up to the test point and back to J8-2'),
    P('TPX2', 'TP', 'TP', at=(452, 150), pins={'1': '5E_U10_OUT_R'}, printed='',
      note='Unlabeled test point'),

    # ── SPI device with ferrite-filtered supplies ──
    P('L6', '2100', 'L', at=(262, 250), rot=90, pins={'1': '5E_L6_ARROW', '2': '5E_SPI_VT'},
      probable='Ferrite bead', note='Far end to an unlabeled arrow'),
    P('CX3', '?', 'C', at=(276, 262), pins={'1': '5E_SPI_VT', '2': 'GND'}, printed='',
      note='No ref/value printed'),
    P('CX4', '?', 'C', at=(290, 262), pins={'1': '5E_SPI_VT', '2': 'GND'}, printed='',
      note='No ref/value printed'),
    P('UX2', '?', 'F5E_SPIDEV', at=(330, 280),
      pins={'1': 'MOSI', '2': 'SCLK', '4': '99-', '5': '5E_ARROW_SPI5', '7': 'UP_CNTRL',
            'VT': '5E_SPI_VT', 'VB': '5E_SPI_VB', 'GB': 'GND'},
      printed='', note=('No ref/part printed. Pin 4 input label printed "99-" (perhaps SS-). '
                        'Pin 5 to an unlabeled filled down-arrow. Top/bottom leads unnumbered.')),
    P('L5', '2100', 'L', at=(262, 312), rot=90, pins={'1': '5E_L5_ARROW', '2': '5E_SPI_VB'},
      probable='Ferrite bead', note='Far end to an unlabeled arrow'),
    P('CX5', '?', 'C', at=(276, 300), pins={'1': '5E_SPI_VB', '2': 'GND'}, printed='',
      note='No ref/value printed'),
    P('CX6', '?', 'C', at=(290, 300), pins={'1': '5E_SPI_VB', '2': 'GND'}, printed='',
      note='No ref/value printed'),
]

WIRES = [
    ('C50.1', 'R133.1', 'vh'),
    ('C50.2', 'R133.2', 'vh'),
    ('C38.1', 'R187.1', 'vh'),
    ('C38.2', 'R187.2', 'vh'),
    ('R136.2', 'U10A.3'),
    ('U10A.1', 'RX2.1'),
    ('RX2.2', 'U10B.6'),
    ('R185.1', 'U10B.5', 'vh'),
    ('U10B.7', 'R132.1'),
]

NOTES = [
    ('Printed "10V" at R270 -> net +10V.  "HOT TOTAL" printed with a space -> HOT_TOTAL.\n'
     '"SYS. RESET" -> SYS.RESET.  No L3 on this figure (L1, L2, L4, L5, L6 only).', 15, 316),
    ('Unlabeled filled down-arrows (J8-7, J9-6, C96, C94, UX2-5) and arrows at L5, L6, R131\n'
     'are kept as separate nets (not named on the drawing).', 240, 316),
]
