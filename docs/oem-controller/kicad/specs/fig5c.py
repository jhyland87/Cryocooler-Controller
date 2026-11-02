"""FIG 5C - set-point summing, CMT/HOG temperature channels and cooler overstroke back-off counter.

FIG 5C-1 (left half) and FIG 5C-2 (right half) are one drawing split at the page
edge. The eight lines leaving the right edge of 5C-1 continue, in the same order,
on the left edge of 5C-2 (edge y positions at 400 dpi/4: 196/194, 231/230,
266/265, 301/301, 374/376, 531/537, 626/634, 846/860):
  1-5  R192, R189, R193, R195, R199(2nd) -> U34 pin 2 summing bus
  6    R140 (CMT rectifier output)        -> U26 pin 3 / R163 node
  7    SHUTO_T                             -> Q2 gate, U28 CLR pins 3 and 11
  8    U48 comparator output               -> U28 'O' trigger inputs 2 and 10
"""

from oemsch import P

TITLE = 'FIG 5C - Set-point sum, overstroke back-off'
SOURCE = 'US6098409 sheets 6-7 of 25 (PDF p7-8), FIG 5C-1 + FIG 5C-2'
PAPER = 'A1'

# Signals that leave this page (off-page connectors on the drawing).
GLOBALS = [
    'WP.SHOSET', 'WP.SHTR', 'OF_SET', 'OF_CTAL', 'OFT_TE', 'CMTO_T', 'CMT_T',
    'SHUTO_T', 'HOG_T', 'HOG_TR', 'NOT_TOTAL', 'BACK_OFF_COUNT',
]

LT1124_A = {'-': '2', '+': '3', 'out': '1'}
LT1124_B = {'-': '6', '+': '5', 'out': '7'}

SYMBOLS = {
    # LT1011A comparator, pin numbers as printed on FIG 5C-1.
    'F5C_LT1011A': {
        'left': [('2', 'IN+'), None, ('3', 'IN-')],
        'right': [('7', 'OUT'), None, ('5', 'BAL'), ('6', 'BAL/STB')],
        'top': [('8', 'V+')],
        'bottom': [('4', 'V-'), ('1', 'GND')],
        'prefix': 'U',
    },
    # 74HC123 one-shot sections; pin names exactly as printed (X, O, CLR, RK/CK, CK/OK).
    'F5C_HC123_S1': {
        'left': [('15', 'RK/CK'), None, ('14', 'CK'), None, ('1', 'X'), None, ('2', 'O'), None, ('3', '~{CLR}')],
        'right': [None, ('13', 'Q'), None, None, None, ('4', '~{Q}')],
        'prefix': 'U',
    },
    'F5C_HC123_S2': {
        'left': [('7', 'RK/CK'), None, ('6', 'OK'), None, ('9', 'X'), None, ('10', 'O'), None, ('11', '~{CLR}')],
        'right': [None, ('3', 'Q'), None, None, None, ('12', '~{Q}')],
        'prefix': 'U',
    },
    # "INLD110" 4-pin MOSFET as drawn: 1 gate, 3+4 drain (tied), 2 source.
    'F5C_INLD110': {
        'left': [('1', 'G')],
        'top': [('4', 'D'), ('3', 'D')],
        'bottom': [('2', 'S')],
        'prefix': 'Q',
    },
    # 2N4220 N-JFET (TO-72, 4 leads); pin numbers not printed, so lead names are used.
    'F5C_2N4220': {
        'left': [('G', 'G')],
        'right': [('D', 'D'), ('S', 'S')],
        'bottom': [('CASE', 'CASE')],
        'prefix': 'Q',
    },
}

NOTE_SUPPLY_UNNUM = 'Supply pin drawn but its number is not printed (standard pin assumed)'

PARTS = [
    # ════════ FIG 5C-1, top: set-point / offset summing network ════════
    P('R299', '10K', 'R', at=(40, 72), rot=90, pins={'1': '+5VA', '2': '5C_U46_INV'}),
    P('R298', '10K', 'R', at=(66, 58), rot=90, pins={'1': '5C_U46_INV', '2': '5C_U46_OUT'}),
    P('R210', '4.08K', 'R', at=(40, 92), rot=90, pins={'1': 'OF_SET', '2': '5C_U46_NI'}),
    P('U46', 'LT1124', 'OPAMP', at=(80, 82),
      pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
      pins={'6': '5C_U46_INV', '5': '5C_U46_NI', '7': '5C_U46_OUT', '8': '+15V', '4': '-15V'},
      note='Pin 4 drawn to an unlabeled downward supply arrow; -15V assumed (LT1124 V-)'),
    P('C196', '.1uF', 'C', at=(96, 62), pins={'1': '+15V', '2': 'GND'}),
    P('C107', '.1uF', 'C', at=(96, 104), pins={'1': '-15V', '2': 'GND'}),

    P('R192', '113K', 'R', at=(290, 36), rot=90, pins={'1': 'WP.SHOSET', '2': '5C_SUM'}),
    P('R189', '500K', 'R', at=(290, 50), rot=90, pins={'1': 'WP.SHTR', '2': '5C_SUM'}),
    P('R193', '130K', 'R', at=(290, 64), rot=90, pins={'1': '5C_U46_OUT', '2': '5C_SUM'}),
    P('R195', '500K', 'R', at=(290, 78), rot=90, pins={'1': 'OF_CTAL', '2': '5C_SUM'}),

    P('R199', '75K', 'R', at=(220, 112), rot=90, pins={'1': 'OFT_TE', '2': '5C_OFT_LL'}),
    P('C105', '15uF/25V', 'C', at=(200, 98), rot=90, pins={'1': 'OFT_TE', '2': '5C_C105_C104'}),
    P('C104', '15uF25V', 'C', at=(240, 98), rot=90, pins={'1': '5C_C105_C104', '2': '5C_OFT_LL'}),
    P('R199B', '75K', 'R', at=(290, 112), rot=90, pins={'1': '5C_OFT_LL', '2': '5C_SUM'},
      printed='R199', note='R199 printed twice on FIG 5C-1 (both 75K)'),

    # ════════ FIG 5C-1, middle: CMT channel (U11) and precision rectifier (U26 pins 5-7) ════════
    P('R91', '10K', 'R', at=(36, 150), rot=90, pins={'1': '+5VA', '2': '5C_U11_INV'}),
    P('R92', '10K', 'R', at=(36, 186), rot=90, pins={'1': 'CMTO_T', '2': '5C_U11_INV'}),
    P('R93', '1K', 'R', at=(58, 204), pins={'1': '5C_U11_NI', '2': 'GND'}),
    P('C35', '.01uF', 'C', at=(80, 140), rot=90, pins={'1': '5C_U11_INV', '2': 'CMT_T'}),
    P('R82', '10K', 'R', at=(80, 156), rot=90, pins={'1': '5C_U11_INV', '2': 'CMT_T'}),
    P('U11', 'LMC6-482', 'OPAMP', at=(84, 188),
      pinmap={'-': '2', '+': '3', 'out': '1', 'v+': '8', 'v-': '4'},
      pins={'2': '5C_U11_INV', '3': '5C_U11_NI', '1': 'CMT_T', '8': '+5VA', '4': 'GND'},
      probable='LMC6482 (National dual CMOS rail-to-rail op-amp)'),
    P('C29', '.1uF', 'C', at=(100, 170), pins={'1': '+5VA', '2': 'GND'}),

    P('R127', '4.08K', 'R', at=(128, 188), rot=90, pins={'1': 'CMT_T', '2': '5C_U26A_INV'}),
    P('R126', '11.0K', 'R', at=(150, 150), rot=90, pins={'1': '5C_R126_ARROW', '2': '5C_U26A_INV'},
      note='Left end drawn to an unlabeled downward arrow (supply/reference not named)'),
    P('C49', '.001SUF', 'C', at=(190, 160), rot=90, pins={'1': '5C_U26A_INV', '2': '5C_U26A_OUT'},
      note='Value printed ".001SUF" (probably .0015uF)'),
    P('CR10', '1N4140', 'D', at=(190, 172), rot=90, pins={'1': '5C_U26A_INV', '2': '5C_U26A_OUT'},
      probable='1N4148 (printed 1N4140)', note='Cathode to pin 6 node, anode to pin 7'),
    P('U26A', 'LT1124', 'OPAMP', at=(186, 192), pinmap=LT1124_B,
      pins={'6': '5C_U26A_INV', '5': '5C_U26A_NI', '7': '5C_U26A_OUT'}, printed='U26',
      note='U26 is also drawn on FIG 5C-2 with conflicting pins 2/3/6/7 (see U26B)'),
    P('R129', '3.24K', 'R', at=(164, 210), pins={'1': '5C_U26A_NI', '2': 'GND'}),
    P('CR11', '1N4140', 'D', at=(222, 192), rot=90, pins={'1': '5C_U26A_OUT', '2': '5C_CMT_RECT'},
      probable='1N4148 (printed 1N4140)', note='Cathode to U26 pin 7, anode to R128/R140 node'),
    P('R128', '48.3K', 'R', at=(200, 140), rot=90, pins={'1': '5C_U26A_INV', '2': '5C_CMT_RECT'}),
    P('R140', '200K', 'R', at=(262, 192), rot=90, pins={'1': '5C_CMT_RECT', '2': '5C_U26B_NI'}),

    # ════════ FIG 5C-1, bottom: HOG_T channel, thermistor bridge, U48 latch comparator ════════
    P('R285', '2.21K', 'R', at=(34, 372), rot=90, pins={'1': 'HOG_T', '2': '5C_HOG_IN'}),
    P('C155', '.01uF', 'C', at=(70, 330), rot=90, pins={'1': '5C_HOG_IN', '2': '5C_U53A_OUT'}),
    P('C150', '.01uF', 'C', at=(60, 372), rot=90, pins={'1': '5C_HOG_IN', '2': '5C_U53A_INV'}),
    P('R266', '221K(RM) / 49.0K', 'R', at=(90, 350), rot=90,
      pins={'1': '5C_U53A_INV', '2': '5C_U53A_OUT'},
      note='Two values printed: "221K(RM)" above the symbol and "49.0K" below'),
    P('U53A', 'LT1124', 'OPAMP', at=(96, 376), pinmap=LT1124_A,
      pins={'2': '5C_U53A_INV', '3': '5C_U53A_NI', '1': '5C_U53A_OUT'}, printed='U53'),
    P('R267', '221K', 'R', at=(74, 398), pins={'1': '5C_U53A_NI', '2': 'GND'}),
    P('R286', '2.21K', 'R', at=(34, 420), rot=90, pins={'1': 'HOG_TR', '2': 'GND'},
      note='HOG_TR returns to GND through R286 (joined at the R267 ground node)'),
    P('C155B', '.01uF', 'C', at=(128, 380), rot=90, pins={'1': '5C_U53A_OUT', '2': '5C_U53B_NI'},
      printed='C155', note='C155 printed twice on FIG 5C-1'),
    P('R232', '20K', 'R', at=(146, 404), pins={'1': '5C_U53B_NI', '2': 'GND'}),

    P('R281', '3.08(TM)', 'R', at=(126, 268), rot=90, pins={'1': 'GND', '2': '5C_U53B_INV'}),
    P('R282', '12.4(TM)', 'R', at=(166, 268), rot=90, pins={'1': '5C_U53B_INV', '2': '5C_RT1_TOP'}),
    P('R283', '?', 'R', at=(206, 268), rot=90, pins={'1': '5C_RT1_TOP', '2': '5C_U53B_OUT'},
      note='No value printed'),
    P('RT1', 'Y4401', 'THERM', at=(186, 290), pins={'1': '5C_RT1_TOP', '2': '5C_U53B_INV'},
      probable='YSI 44001-series NTC thermistor (guess from "Y4401")', note='Printed "RT1 (TM) Y4401"'),
    P('C167', '.01uF', 'C', at=(200, 310), rot=90, pins={'1': '5C_U53B_INV', '2': '5C_U53B_OUT'}),
    P('R284', '0(RM)', 'R', at=(200, 326), rot=90, pins={'1': '5C_U53B_INV', '2': '5C_U53B_OUT'}),
    P('U53B', 'LT1124', 'OPAMP', at=(180, 382),
      pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
      pins={'6': '5C_U53B_INV', '5': '5C_U53B_NI', '7': '5C_U53B_OUT', '8': '+15V', '4': '-15V'},
      printed='U53', note=NOTE_SUPPLY_UNNUM + ' (V- = 4)'),
    P('C141', '.01uF', 'C', at=(196, 360), pins={'1': '+15V', '2': 'GND'}),
    P('C142', '.01uF', 'C', at=(196, 404), pins={'1': '-15V', '2': 'GND'}),
    P('TPX1', 'TP', 'TP', at=(222, 356), pins={'1': '5C_U53B_OUT'},
      note='Unlabeled test point on U53 pin 7 (top of the R283/C167/R284 node)'),

    P('R253', '10K', 'R', at=(236, 382), rot=90, pins={'1': '5C_U53B_OUT', '2': '5C_U48_OUT'}),
    P('R254', '10K', 'R', at=(266, 382), rot=90, pins={'1': '5C_U48_OUT', '2': '5C_U48_NI'},
      note='R253/R254 junction is wired directly to the U48 output (latching positive feedback)'),
    P('C141B', '.01uF', 'C', at=(282, 362), pins={'1': '5C_U48_NI', '2': 'GND'},
      printed='C141', note='C141 printed twice on FIG 5C-1'),
    P('TP4', 'TP', 'TP', at=(290, 368), pins={'1': '5C_U48_NI'}),
    P('U48', 'LT1011A', 'F5C_LT1011A', at=(318, 386),
      pins={'2': '5C_U48_NI', '3': '5C_U48_INV', '7': '5C_U48_OUT', '8': '+5VA', '4': '-15V',
            '1': 'GND', '5': '5C_U48_BAL', '6': '5C_U48_STB'}),
    P('C126', '.01uF', 'C', at=(350, 400), rot=90, pins={'1': '5C_U48_BAL', '2': '5C_U48_STB'}),
    P('C125', '22uF/25V', 'CP', at=(300, 346), pins={'1': '+5VA', '2': 'GND'}),
    P('R233', '1K', 'R', at=(348, 360), pins={'1': '+5VA', '2': '5C_U48_OUT'}),
    P('TP5', 'TP', 'TP', at=(290, 412), pins={'1': '5C_U48_INV'}),
    P('C169', '.01uF', 'C', at=(274, 424), pins={'1': '5C_U48_INV', '2': 'GND'},
      note='"(TM)" printed between R255 and C169'),
    P('R255', '90.7K', 'R', at=(236, 412), rot=90, pins={'1': '+5VA', '2': '5C_U48_INV'},
      note='"(TM)" printed near R255/C169'),
    P('R285B', '10K', 'POT', at=(252, 436), pins={'1': '5C_U48_INV', '2': 'GND', '3': 'GND'},
      printed='R285', note='R285 printed twice on FIG 5C-1 (2.21K and this 10K pot); wiper tied to pin 3'),
    P('R256', '2.09K', 'R', at=(304, 436), pins={'1': '5C_U48_INV', '2': 'GND'}),

    # ════════ FIG 5C-2, top: U34 summing amp, U26 clamp, U33 -> NOT_TOTAL ════════
    P('R191', '450K', 'R', at=(400, 36), rot=90, pins={'1': '5C_SUM', '2': '5C_R191_ARROW'},
      note='Right end drawn to an unlabeled arrow (destination not named)'),
    P('C77', '.01uF', 'C', at=(400, 60), rot=90, pins={'1': '5C_SUM', '2': '5C_U34_OUT'}),
    P('R196', '220K', 'R', at=(400, 76), rot=90, pins={'1': '5C_SUM', '2': '5C_U34_OUT'}),
    P('U34', 'LT1012', 'OPAMP', at=(386, 112),
      pinmap={'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'},
      pins={'2': '5C_SUM', '3': '5C_U34_NI', '6': '5C_U34_OUT', '7': '+15V', '4': '-15V'},
      note=NOTE_SUPPLY_UNNUM + ' (V- = 4)'),
    P('R194', '200K', 'R', at=(366, 134), pins={'1': '5C_U34_NI', '2': 'GND'}),
    P('C76', '.1uF', 'C', at=(402, 94), pins={'1': '+15V', '2': 'GND'}),
    P('C87', '.1uF', 'C', at=(402, 132), pins={'1': '-15V', '2': 'GND'}),
    P('R139', '10K', 'R', at=(432, 112), rot=90, pins={'1': '5C_U34_OUT', '2': '5C_U26B_INV'}),
    P('U26B', 'LT1124', 'OPAMP', at=(476, 114),
      pinmap={'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'},
      pins={'2': '5C_U26B_INV', '3': '5C_U26B_NI', '6': '5C_U26B_OUT', '7': '+15V', '4': '-15V'},
      printed='U26', note=('Printed U26 LT1124 with pins 2/3 in, 6 out, 7 V+ (LT1012-style single '
                           'pinout) - conflicts with U26 pins 5/6/7 on 5C-1. V- number not printed.')),
    P('C76B', '.1uF', 'C', at=(492, 96), pins={'1': '+15V', '2': 'GND'},
      printed='C76', note='C76 printed twice on FIG 5C-2'),
    P('C70', '.1uF', 'C', at=(492, 134), pins={'1': '-15V', '2': 'GND'}),
    P('C69', '.01uF', 'C', at=(528, 80), pins={'1': '5C_U26B_INV', '2': '5C_U26B_OUT'}),
    P('CR14', '1N4149', 'D', at=(512, 80), pins={'1': '5C_U26B_OUT', '2': '5C_U26B_INV'},
      note='Anode to pin 2 node, cathode to pin 6'),
    P('R162', '10K', 'R', at=(548, 60), rot=90, pins={'1': '5C_U26B_INV', '2': '5C_U33_NI'}),
    P('U33', 'LMC6-482', 'OPAMP', at=(590, 66),
      pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
      pins={'5': '5C_U33_NI', '6': '5C_U33_INV', '7': 'NOT_TOTAL', '8': '+15V', '4': '5C_U33_VNEG'},
      probable='LMC6482',
      note=('V- pin (number not printed) is drawn to the R162(2nd)/R187 node, not to a supply '
            'rail - transcribed as drawn')),
    P('C75', '.1uF', 'C', at=(606, 44), pins={'1': '+15V', '2': 'GND'}),
    P('R185', '10K', 'R', at=(594, 86), rot=90, pins={'1': '5C_U33_INV', '2': 'NOT_TOTAL'}),
    P('R194B', '200K', 'R', at=(566, 96), pins={'1': '5C_U33_INV', '2': 'GND'},
      printed='R194', note='R194 printed twice on FIG 5C-2'),
    P('R162B', '10K', 'R', at=(620, 110), rot=90, pins={'1': '5C_U33_VNEG', '2': '+15V'},
      printed='R162', note='R162 printed twice on FIG 5C-2'),
    P('R187', '30.2', 'R', at=(588, 124), pins={'1': '5C_U33_VNEG', '2': 'GND'}),
    P('TP1', 'TP', 'TP', at=(626, 56), pins={'1': 'NOT_TOTAL'}),

    # ════════ FIG 5C-2, bottom: overstroke back-off counter ════════
    # U28 section 1: short one-shot (R144 10K / C53 2.2uF) fired by each U48 trip.
    P('R144', '10K', 'R', at=(360, 236), pins={'1': '+5V', '2': '5C_U28A_RC'}),
    P('C53', '2.2uF/25V', 'C', at=(360, 262), pins={'1': '5C_U28A_RC', '2': '5C_U28A_CX'}),
    P('U28A', 'HC123', 'F5C_HC123_S1', at=(392, 262),
      pins={'15': '5C_U28A_RC', '14': '5C_U28A_CX', '1': 'GND', '2': '5C_U48_OUT',
            '3': 'SHUTO_T', '4': '5C_U28A_QN', '13': '5C_U28A_Q_STUB'},
      printed='U28', probable='74HC123 dual retriggerable monostable (X = A, O = B inputs)',
      note='Pin 13 (Q) drawn as an unterminated stub'),
    # U28 section 2: long one-shot (R145 640K / C72 100uF), retriggered by each trip.
    P('R145', '640K', 'R', at=(360, 356), pins={'1': '+5V', '2': '5C_U28B_RC'}),
    P('C72', '100uF/25V', 'C', at=(360, 382), pins={'1': '5C_U28B_RC', '2': '5C_U28B_CX'}),
    P('U28B', 'HC123', 'F5C_HC123_S2', at=(392, 382),
      pins={'7': '5C_U28B_RC', '6': '5C_U28B_CX', '9': 'GND', '10': '5C_U48_OUT',
            '11': 'SHUTO_T', '12': '5C_U28B_QN', '3': '5C_U28B_Q_STUB'},
      printed='U28', probable='74HC123 (second section)',
      note=('Q printed as pin 3 (74HC123 2Q is pin 5; pin 3 is 1CLR) - drawn as unterminated stub. '
            'Cext pin printed "OK".')),

    # Q2 + Q3: SHUTO_T low -> Q2 off -> R190/R142 bias Q3 gate -> charges C71.
    P('Q2', 'INLD110', 'F5C_INLD110', at=(440, 222),
      pins={'1': 'SHUTO_T', '4': '5C_Q3_GATE', '3': '5C_Q3_GATE', '2': 'GND'},
      probable='IRLD110 (IR logic-level N-MOSFET, 4-pin HEXDIP; printed INLD110)'),
    P('R190', '10K', 'R', at=(440, 196), pins={'1': '+5V', '2': '5C_Q3_GATE'}),
    P('R142', '10K', 'R', at=(462, 226), pins={'1': '5C_Q3_GATE', '2': 'GND'}),
    P('Q3', '2N4220', 'F5C_2N4220', at=(490, 206),
      pins={'G': '5C_Q3_GATE', 'D': '5C_COUNT_CAP', 'S': '5C_COUNT_CAP', 'CASE': 'GND'},
      note='N-JFET with drain and source tied: used as a low-leakage gate-channel diode'),
    # Q5 + Q4: each U28A pulse turns Q5 off -> R167 pulls Q4 gate up -> charge step into C71.
    P('Q5', 'INLD110', 'F5C_INLD110', at=(440, 300),
      pins={'1': '5C_U28A_QN', '4': '5C_Q4_GATE', '3': '5C_Q4_GATE', '2': 'GND'},
      probable='IRLD110'),
    P('R167', '64.8K', 'R', at=(440, 274), pins={'1': '+5V', '2': '5C_Q4_GATE'}),
    P('Q4', '2N4220', 'F5C_2N4220', at=(490, 286),
      pins={'G': '5C_Q4_GATE', 'D': '5C_COUNT_CAP', 'S': '5C_COUNT_CAP', 'CASE': 'GND'},
      note='N-JFET with drain and source tied (low-leakage diode)'),
    P('C71', '10uF/25V', 'CP', at=(520, 320), pins={'1': '5C_COUNT_CAP', '2': 'GND'}),
    # Q1 + R130: U28B timed out (no trips for ~RC) -> Q1 on -> C71 bleeds through R130.
    P('Q1', 'INLD110', 'F5C_INLD110', at=(440, 400),
      pins={'1': '5C_U28B_QN', '4': '5C_Q1_DRAIN', '3': '5C_Q1_DRAIN', '2': 'GND'},
      probable='IRLD110'),
    P('R130', '1M', 'R', at=(476, 372), rot=90, pins={'1': '5C_Q1_DRAIN', '2': '5C_COUNT_CAP'}),

    # U27: buffer -> BACK_OFF_COUNT, then scaled/offset amp feeding back into the U26 clamp.
    P('R143', '1K', 'R', at=(540, 290), rot=90, pins={'1': '5C_COUNT_CAP', '2': '5C_U27A_NI'}),
    P('U27A', 'LMC6-482', 'OPAMP', at=(572, 288),
      pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
      pins={'5': '5C_U27A_NI', '6': 'BACK_OFF_COUNT', '7': 'BACK_OFF_COUNT', '8': '+5VA', '4': '-5V'},
      printed='U27', probable='LMC6482', note=NOTE_SUPPLY_UNNUM + ' (V- = 4); follower (6 tied to 7)'),
    P('C52', '.1uF', 'C', at=(588, 268), pins={'1': '+5VA', '2': 'GND'}),
    P('C50', '.1uF', 'C', at=(588, 310), pins={'1': '-5V', '2': 'GND'}),
    P('R141', '51.1K', 'R', at=(618, 288), rot=90, pins={'1': 'BACK_OFF_COUNT', '2': '5C_U27B_INV'}),
    P('U27B', 'LMC6-482', 'OPAMP', at=(632, 330), pinmap={'-': '2', '+': '3', 'out': '1'},
      pins={'2': '5C_U27B_INV', '3': '5C_U27B_NI', '1': '5C_U27B_OUT'}, printed='U27', probable='LMC6482'),
    P('R165', '50K', 'R', at=(612, 356), pins={'1': '5C_U27B_INV', '2': '5C_R197_3'}),
    P('R197', '200K', 'POT', at=(612, 380), pins={'3': '5C_R197_3', '2': '-10V', '1': '-10V'},
      note='Wiper (2) tied to pin 1, to -10V'),
    P('R166', '4.01K', 'R', at=(636, 356), pins={'1': '5C_U27B_NI', '2': 'GND'}),
    P('R163', 'XXX', 'R', at=(600, 180), rot=90, pins={'1': '5C_U26B_NI', '2': '5C_U27B_OUT'},
      note='Value printed as XXX (not specified)'),
]

WIRES = [
    ('R299.2', 'R298.1', 'vh'),
    ('R162B.1', 'R187.1', 'vh'),
    ('U33.4', 'R162B.1', 'hv'),
    ('C105.2', 'C104.1'),
    ('C104.2', 'R199B.1', 'vh'),
    ('C35.1', 'R82.1', 'vh'),
    ('R82.2', 'C35.2', 'vh'),
    ('C49.1', 'CR10.1', 'vh'),
    ('C49.2', 'CR10.2', 'vh'),
    ('C155B.2', 'R232.1'),
    ('R281.2', 'R282.1'),
    ('R282.2', 'R283.1'),
    ('C167.1', 'R284.1', 'vh'),
    ('C167.2', 'R284.2', 'vh'),
    ('R144.2', 'C53.1'),
    ('R145.2', 'C72.1'),
    ('R190.2', 'Q2.4'),
    ('R167.2', 'Q5.4'),
    ('Q2.4', 'Q2.3'),
    ('Q5.4', 'Q5.3'),
    ('Q1.4', 'Q1.3'),
    ('Q3.D', 'Q3.S', 'vh'),
    ('Q4.D', 'Q4.S', 'vh'),
    ('C77.1', 'R196.1', 'vh'),
    ('C77.2', 'R196.2', 'vh'),
    ('CR14.2', 'C69.1', 'vh'),
    ('CR14.1', 'C69.2', 'vh'),
]

NOTES = [
    ('FIG 5C-1 | FIG 5C-2 page seam: the 8 lines leaving 5C-1 right edge continue in order on 5C-2 left edge\n'
     '(R192/R189/R193/R195/R199 -> U34 pin 2; R140 -> U26 pin 3; SHUTO_T -> Q2/U28 CLR; U48 out -> U28 O inputs)',
     15, 437),
    ('OVERSTROKE BACK-OFF COUNTER: each U48 trip fires U28 (pin 2 O) -> Q5 off -> R167 charges C71 via Q4 (JFET diode);\n'
     'U28 (pin 10 O) is retriggered by each trip and holds Q1 off; after ~R145*C72 with no trips Q1 bleeds C71 via R130.\n'
     'SHUTO_T low: clears both one-shots and turns Q2 off so R190/R142 charge C71 via Q3. C71 -> U27 buffer -> BACK_OFF_COUNT.',
     345, 430),
    ('Unlabeled arrows: R126 left end (down arrow), R191 right end (arrow), U46 pin 4 (taken as -15V).', 15, 445),
    ('"(TM)" / "(RM)" value suffixes printed as-is (meaning not given).', 15, 450),
]
