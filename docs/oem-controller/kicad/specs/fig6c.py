"""FIG 6C - daughter board channel J15 (U20 LTC1150 + unlabelled 2nd stage), J10 26-pin board connector, mounting holes."""

from oemsch import P

TITLE = 'FIG 6C - Channel J15, connector J10'
SOURCE = 'US6098409 sheet 25 of 25 (PDF p26), FIG 6C (drawn rotated 90 deg)'
PAPER = 'A2'

NOVAL = 'No value printed on FIG 6C'
NOREF = 'Unlabelled on FIG 6C (no ref, no value printed)'

SYMBOLS = {
    # Pin numbers are NOT printed on FIG 6C; numbering assumed from the identical
    # LTC1150 channels of FIG 6A/6B (2 -, 3 +, 8 out, 6 second output, 7 V+, 4 V-).
    'F6C_LTC1150': {
        'left': [('2', '-'), None, ('3', '+')],
        'right': [('8', 'P8'), None, ('6', 'P6')],
        'top': [('7', 'V+')],
        'bottom': [('4', 'V-')],
        'prefix': 'U',
    },
    # Unidentified op-amp: no ref, no part number, no pin numbers printed.
    'F6C_OPAMP_UNK': {
        'left': [('INM', '-'), None, ('INP', '+')],
        'right': [('OUT', 'OUT'), None, ('AUX', 'AUX')],
        'top': [('VP', 'V+')],
        'bottom': [('VN', 'V-')],
        'prefix': 'U',
    },
    'F6C_CONN4': {
        'right': [('1', '1'), None, ('2', '2'), None, ('3', '3'), None, ('4', '4')],
        'prefix': 'J',
    },
    'F6C_CONN26': {
        # odd pins left, even pins right as drawn; blank rows between pins for label room
        'left': [entry for n in range(1, 26, 2) for entry in ((str(n), str(n)), None)][:-1],
        'right': [entry for n in range(2, 27, 2) for entry in ((str(n), str(n)), None)][:-1],
        'prefix': 'J',
    },
}

SIG, INM, INP, OUT = '6C_J15_SIG', '6C_U20_IN-', '6C_U20_IN+', '6C_U20_OUT'
REFN = '6C_REF_NODE'          # R73/R80 node -> blank off-page connector
B_INM, B_OUT = '6C_OPA2_IN-', '6C_OPA2_OUT'

PARTS = [
    # ── J15 channel, first stage (U20) ──
    P('J15', 'CONN_4', 'F6C_CONN4', at=(22, 84),
      pins={'1': 'GND', '2': 'POLARIZATION_KEY', '3': 'GND', '4': SIG},
      note='Pin 2 printed "POLARIZATION KEY" (6A/6B print POLARIZING_KEY)'),
    P('R73', '?', 'R', at=(50, 62), pins={'1': REFN, '2': SIG}, note=NOVAL),
    P('R69', '?', 'R', at=(78, 76), rot=90, pins={'1': 'GND', '2': INM}, note=NOVAL),
    P('R74', '?', 'R', at=(78, 94), rot=90, pins={'1': SIG, '2': INP}, note=NOVAL),
    P('6C_C?1', '?', 'C', at=(58, 106), pins={'1': SIG, '2': 'GND'}, note=NOREF),
    P('6C_C?2', '?', 'C', at=(96, 106), pins={'1': INP, '2': 'GND'}, note=NOREF),
    P('R80', '?', 'R', at=(114, 38), rot=90, pins={'1': INM, '2': REFN}, note=NOVAL),
    P('C74', '?', 'C', at=(114, 48), rot=90, pins={'1': INM, '2': OUT}, note=NOVAL),
    P('R63', '?', 'R', at=(114, 58), rot=90, pins={'1': INM, '2': OUT}, note=NOVAL),
    P('U20', 'LTC1150', 'F6C_LTC1150', at=(124, 86),
      pins={'2': INM, '3': INP, '8': OUT, '6': '6C_U20_P6', '7': '+12V', '4': '-12V'},
      note='Pin numbers not printed on 6C (assumed from 6A/6B). 2nd output line ends in a '
           'blank off-page connector; a pin-5-like stub is drawn unconnected'),
    P('C71', '?', 'C', at=(152, 68), pins={'1': '+12V', '2': 'GND'}, note=NOVAL),
    P('C77', '?', 'C', at=(152, 104), pins={'1': '-12V', '2': 'GND'}, note=NOVAL),

    # ── second stage (entirely unlabelled) ──
    P('6C_R?1', '?', 'R', at=(190, 38), rot=90, pins={'1': REFN, '2': B_INM}, note=NOREF),
    P('6C_R?2', '?', 'R', at=(240, 38), rot=90, pins={'1': B_INM, '2': B_OUT}, note=NOREF),
    P('6C_C?3', '?', 'C', at=(240, 48), rot=90, pins={'1': B_INM, '2': B_OUT}, note=NOREF),
    P('6C_R?3', '?', 'R', at=(200, 78), rot=90, pins={'1': 'GND', '2': B_INM}, note=NOREF),
    P('6C_U?1', '?', 'F6C_OPAMP_UNK', at=(250, 86),
      pins={'INM': B_INM, 'INP': OUT, 'OUT': B_OUT, 'AUX': '6C_OPA2_AUX',
            'VP': '6C_OPA2_VTOP', 'VN': '6C_OPA2_VBOT'},
      note='Unlabelled op-amp: no ref/part/pin numbers; supply arrows unlabelled; output line '
           'ends open; 2nd output line ends in a blank off-page connector'),
    P('6C_C?4', '?', 'C', at=(280, 68), pins={'1': '6C_OPA2_VTOP', '2': 'GND'}, note=NOREF),
    P('6C_C?5', '?', 'C', at=(280, 104), pins={'1': '6C_OPA2_VBOT', '2': 'GND'}, note=NOREF),
    P('6C_R?4', '?', 'R', at=(220, 116), rot=90, pins={'1': OUT, '2': '6C_R?4_OPEN'},
      note=NOREF + '; right end is an open line'),
    P('6C_R?5', '?', 'R', at=(194, 126), pins={'1': OUT, '2': 'GND'}, note=NOREF),

    # ── J10 26-pin board-to-board connector ──
    P('J10', 'CONN_26', 'F6C_CONN26', at=(130, 236), pins={
        '1': 'BWT_1P', '3': 'BWT_2P', '5': 'BWT_3P', '7': 'CST_2', '9': 'BWT_4P',
        '11': 'BWT_4R', '13': 'BWT_5R', '15': 'BWT_6R', '17': '6C_J10_17', '19': '6C_J10_19',
        '23': 'GND', '21': 'GND', '25': 'CFT_T2',
        '2': 'CST_1', '4': 'BWT_1R', '6': 'BWT_2R', '8': 'BWT_3R', '10': 'REF_1',
        '12': 'BWT_5P', '14': 'BWT_6P', '16': 'NC', '18': '6C_J10_18', '20': '6C_J10_20',
        '24': 'GND', '22': 'GND', '26': 'CFT_T1'},
      note='Printed J10, same ref as the J10 sensor input on FIG 6B'),
]

WIRES = [
    ('6C_C?1.1', 'R74.1', 'vh'),
    ('6C_C?2.1', 'R74.2', 'vh'),
    ('C74.1', 'R63.1', 'vh'),
    ('C74.2', 'R63.2', 'vh'),
    ('6C_C?3.1', '6C_R?2.1', 'vh'),
    ('6C_C?3.2', '6C_R?2.2', 'vh'),
    ('J10.21', 'J10.23', 'vh'),
    ('J10.22', 'J10.24', 'vh'),
]

NOTES = [
    ('FIG 6C J15 channel: NO values are printed for any R/C, and the second op-amp stage\n'
     'has no refs at all (named 6C_R?n / 6C_C?n / 6C_U?1 here). The R73/R80 node, the U20\n'
     'and 6C_U?1 second outputs go to off-page connectors with NO names printed; the\n'
     '6C_U?1 output and 6C_R?4 right end are lines that just end. Local names used.', 300, 40),
    ('Supplies: U20 printed +12v / -12v; 6C_U?1 supply arrows unlabelled.', 300, 66),
    ('J10 pins 17 and 19: arrows pointing away (left), pins 18 and 20: arrows pointing\n'
     'away (right) - no names printed. Pin 16 printed N/C. Pins 21-24 tied to GND.\n'
     'CFT_T2 (pin 25) and CFT_T1 (pin 26) are wire names, not connector symbols;\n'
     'they cross the GND loop without a junction dot.', 200, 200),
    ('MOUNTING HOLES (drawn on FIG 6C, not placed as parts):\n'
     '  MH9, MH10, MH11, MH12, MH13, MH14, MH15 - all joined (dots) and tied to GND\n'
     '  MH1, MH4, MH5, MH6 - each drawn with an open lead (no connection)\n'
     '  MH2, MH3, MH7, MH8 are not shown.', 300, 230),
]
