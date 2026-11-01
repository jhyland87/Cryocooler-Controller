"""FIG 5B - NSP serial digital pots/latch, CST_1/CST_2 switch, CS_CTRL integrator, OF_SET/OF_OFFSET."""

from oemsch import P

TITLE = 'FIG 5B - CS_CTRL loop, NSP serial pot/latch, OF_SET/OF_OFFSET'
SOURCE = 'US6098409 sheet 5 of 25 (PDF p6), FIG 5B'
PAPER = 'A2'

DUP = 'Printed pin number repeats on this symbol; suffix #2 added to keep pins distinct'

SYMBOLS = {
    'F5B_DG413_A': {
        'left': [('3', 'S')], 'right': [('2', 'D'), None, ('?', '?')],
        'top': [('V-', 'V-'), None, None, ('V-#2', 'V-')],
        'bottom': [('1', 'IN'), None, None, ('5', 'GND')],
    },
    'F5B_DG413_B': {'left': [('14', 'S')], 'right': [('15', 'D')], 'bottom': [('16', 'IN')]},
    'F5B_MC2030': {
        'left': [None, None, None, ('13', 'PROG'), None, ('14', 'READ'), None, ('2', 'SER.IN'),
                 None, ('1', 'SER.CLK')],
        'right': [('13#2', 'RIA'), None, ('10', 'WPA'), None, ('9', 'RFA'), None, None,
                  ('4', 'RID'), None, ('6', 'WPD'), None, ('7', 'RFD'), None, ('3', 'SER_OUT')],
        'top': [('UDD', 'UDD')], 'bottom': [('6#2', 'GND')],
    },
    'F5B_MC2001': {
        'left': [('9', 'BUBBLE'), None, None, None, ('15', '~{PROG}'), ('14', '~{READ}'),
                 ('2', 'SER_IN'), ('1', 'SER.CLK')],
        'right': [('4', 'O7'), ('13', 'O6'), ('5', 'O5'), ('12', 'O4'), ('6', 'O3'),
                  ('11', 'O2'), ('7', 'O1'), ('10', 'O0'), ('3', 'SER.OUT')],
        'top': [('UDD', 'UDD')], 'bottom': [('6#2', 'GND')],
    },
}

OPAMP_PINS = {'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'}

PARTS = [
    # ── CST_2 / CST_1 through U43 DG413 switches (both controlled by CST_DEL) ──
    P('R201', '10K', 'R', at=(215, 76), rot=90, pins={'1': 'CST_2', '2': '5B_U43A_S'}),
    P('U43A', 'DG413', 'F5B_DG413_A', at=(240, 78), printed='U43',
      pins={'3': '5B_U43A_S', '2': '5B_SW_OUT', '?': '5B_U43_C94', 'V-': '-15V',
            'V-#2': '+15V', '1': 'CST_DEL', '5': 'GND'},
      note='Both supply pins printed "V-" (the one on +15V is presumably V+); '
      'unnamed/unnumbered right-side pin goes only to C94 (presumably VL); S/D/IN names functional'),
    P('C113', '.1uF', 'C', at=(222, 55), pins={'1': '-15V', '2': 'GND'}),
    P('C93', '.1uF', 'C', at=(258, 55), pins={'1': '+15V', '2': 'GND'}),
    P('C94', '.1uF', 'C', at=(265, 88), pins={'1': '5B_U43_C94', '2': 'GND'}),
    P('R200', '10K', 'R', at=(215, 128), rot=90, pins={'1': 'CST_1', '2': '5B_U43B_S'},
      note='R200 is also listed in the FIG 5A option table (OMIT for both -001 and -002)'),
    P('U43B', 'DG413', 'F5B_DG413_B', at=(240, 128), printed='U43',
      pins={'14': '5B_U43B_S', '15': '5B_SW_OUT', '16': 'CST_DEL'}),
    # ── U42 LT1012 summing amp ──
    P('R212', '10K', 'R', at=(285, 76), rot=90, pins={'1': '5B_SW_OUT', '2': '5B_U42_INV'}),
    P('U42', 'LT1012', 'OPAMP', at=(330, 78), pinmap=OPAMP_PINS,
      pins={'2': '5B_U42_INV', '3': '5B_U42_NINV', '6': '5B_U42_OUT', '7': '+15V', '4': '-15V'}),
    P('R296', '?', 'R', at=(330, 55), rot=90, pins={'1': '5B_U42_INV', '2': '5B_U42_OUT'},
      note='No value printed'),
    P('R214', '24.3K', 'R', at=(318, 90), pins={'1': '5B_U42_NINV', '2': 'GND'}),
    P('C91', '.1uF', 'C', at=(345, 100), pins={'1': '+15V', '2': 'GND'}),
    P('C111', '.1uF', 'C', at=(355, 100), pins={'1': '-15V', '2': 'GND'}),
    P('R213', '10K', 'R', at=(290, 160), rot=90, pins={'1': 'OF_SET', '2': '5B_U42_INV'}),
    P('R211', '10K', 'R', at=(306, 160), rot=90, pins={'1': '5B_U42_INV', '2': '+10V'},
      note='Supply printed "10V"'),
    # ── U35 LMC6001 integrator -> CS_CTRL ──
    P('R205', '100K', 'R', at=(355, 78), rot=90, pins={'1': '5B_U42_OUT', '2': '5B_R205_R203'}),
    P('R203', '1M', 'R', at=(375, 78), rot=90, pins={'1': '5B_R205_R203', '2': '5B_U35_INV'}),
    P('C109', '?', 'C', at=(375, 68), rot=90, pins={'1': '5B_R205_R203', '2': '5B_U35_INV'},
      note='No value printed'),
    P('U35', 'LMC6001', 'OPAMP', at=(405, 80), pinmap=OPAMP_PINS,
      pins={'2': '5B_U35_INV', '3': '5B_U35_NINV', '6': 'CS_CTRL', '7': '+5VA', '4': '-5V'}),
    P('R284', '1.10M', 'R', at=(393, 92), pins={'1': '5B_U35_NINV', '2': 'GND'},
      note='R284 is also listed in the FIG 5A option table (-001: 0, -002: OMIT)'),
    P('C108', '10K', 'C', at=(398, 58), rot=90, pins={'1': '5B_U35_INV', '2': '5B_C108_R199'},
      note='Capacitor symbol with value printed "10K"'),
    P('R199', '1M', 'R', at=(415, 58), rot=90, pins={'1': '5B_C108_R199', '2': 'CS_CTRL'}),
    P('C98', '?', 'C', at=(405, 46), rot=90, pins={'1': '5B_U35_INV', '2': 'CS_CTRL'},
      note='No value printed'),
    P('C74', '.1uF', 'C', at=(425, 100), pins={'1': '+5VA', '2': 'GND'}),
    P('C79', '.1uF', 'C', at=(435, 100), pins={'1': '-5V', '2': 'GND'}),
    # ── U36 MC2030 serial dual pot ──
    P('U36', 'MC2030', 'F5B_MC2030', at=(95, 170),
      pins={'13': 'NSP_PROG', '14': 'NSP_READ', '2': 'NSP_SER0', '1': 'NSP_CLK',
            '13#2': '+5VA', '10': '5B_WPA', '9': 'GND', '4': '+5VA', '6': 'OF_OFFSET',
            '7': 'GND', '3': 'NSP_SER9', 'UDD': '+5V', '6#2': 'DGND'},
      note='Pin 13 printed for PROG and RIA; pin 6 printed for WPD and GND. ' + DUP
      + '. UDD unnumbered. Input label read as NSP_SER0 (0 vs O ambiguous in the font)'),
    P('C90', '.1uF', 'C', at=(112, 140), pins={'1': '+5V', '2': 'GND'}),
    P('C92', '.1uF', 'C', at=(135, 150), pins={'1': '+5VA', '2': 'GND'}),
    # ── U54 LT1124 buffer -> OF_SET ──
    P('R2-49', '10K', 'R', at=(170, 152), rot=90, pins={'1': '5B_WPA', '2': '5B_U54_NINV'},
      note='Ref printed with a hyphen "R2-49"'),
    P('U54', 'LT1124', 'OPAMP', at=(190, 150), pinmap={'-': '2', '+': '3', 'out': '7',
                                                     'v+': 'V+', 'v-': 'V-'},
      pins={'2': '5B_U54_INV', '3': '5B_U54_NINV', '7': 'OF_SET', 'V+': '+15V', 'V-': '-15V'},
      note='Supply pins drawn but unnumbered; output printed 7 with inputs 2/3 '
      '(FIG 5A spare U54 section also uses pin 7)'),
    P('R2-48', '10K', 'R', at=(190, 132), rot=90, pins={'1': '5B_U54_INV', '2': 'OF_SET'},
      note='Ref printed with a hyphen "R2-48"'),
    P('C143', '.1uF', 'C', at=(218, 145), pins={'1': '+15V', '2': 'GND'}),
    P('C146', '.1uF', 'C', at=(218, 170), pins={'1': '-15V', '2': 'GND'}),
    # ── U29 MC2001 serial latch -> CST_DEL, RAW_SHUTO_T- ──
    P('U29', 'MC2001', 'F5B_MC2001', at=(165, 255),
      pins={'9': 'DGND', '15': 'NSP_PROG', '14': 'NSP_READ', '2': 'NSP_SER0', '1': 'NSP_CLK',
            '4': 'NC', '13': 'NC', '5': 'NC', '12': 'NC', '6': 'RAW_SHUTO_T-', '11': 'NC',
            '7': 'CST_DEL', '10': 'NC', '3': 'NSP_SERI', 'UDD': '+5V', '6#2': 'DGND'},
      note='Pin 6 printed for O3 and GND. ' + DUP + '. O3 line drawn through an "N/C" '
      'note yet continues to RAW_SHUTO_T-. UDD unnumbered; pin 9 bubble input unnamed. '
      'U29 is also printed as MC93 gates on FIG 5A (ref clash)'),
    P('C90B', '.1uF', 'C', at=(185, 222), printed='C90', pins={'1': '+5V', '2': 'GND'},
      note='C90 printed twice on FIG 5B'),
]

WIRES = [
    ('R201.2', 'U43A.3'), ('U43A.2', 'R212.1'), ('R200.2', 'U43B.14'),
    ('R212.2', 'U42.2'), ('R296.1', 'U42.2', 'vh'), ('R296.2', 'U42.6'),
    ('U42.3', 'R214.1'), ('R213.2', 'R211.1'),
    ('U42.6', 'R205.1'), ('R205.2', 'R203.1'), ('C109.1', 'R203.1', 'vh'),
    ('C109.2', 'R203.2', 'vh'), ('R203.2', 'U35.2'), ('U35.3', 'R284.1'),
    ('C108.1', 'U35.2', 'vh'), ('C98.1', 'C108.1'), ('C108.2', 'R199.1'),
    ('R199.2', 'U35.6', 'vh'), ('C98.2', 'R199.2'),
    ('R2-49.2', 'U54.3'), ('R2-48.1', 'U54.2'), ('R2-48.2', 'U54.7'),
]

NOTES = [
    ('"10V" printed at R211 -> net +10V', 300, 170),
    ('DGND = filled-arrow ground symbol (U36/U29 GND, U29 pin 9).\n'
     'Dashed boxes on the drawing (NSP bus group, U36, U29) are omitted.', 250, 290),
]
