"""FIG 5H - analog multiplexers, temperature channels and monitor switches (5H-1, 5H-2, 5H-3)."""

from oemsch import P

TITLE = 'FIG 5H - Sensor muxes, temperature channels, monitor switches'
SOURCE = 'US6098409 sheets 18-20 of 25 (PDF p19-21), FIG 5H-1/5H-2/5H-3'
PAPER = 'A1'

# Mux symbol: printed pin number + printed internal name (the drawing numbers the
# inputs 15..01, then labels pin 19 "A4" (drafting error; the address pins are A3..A0).
# GND pin number printed "L2" (probably 12); output D pin number printed "XX".
_MUX_LEFT = [('4', '15'), ('5', '14'), ('6', '13'), ('7', '12'), ('8', '11'), ('9', '10'),
             ('10', '09'), ('11', '08'), ('26', '07'), ('25', '06'), ('24', '05'), ('23', '04'),
             ('22', '03'), ('21', '02'), ('20', '01'), ('19', 'A4'), ('14', 'A3'), ('15', 'A2'),
             ('16', 'A1'), ('17', 'A0'), ('18', 'EN')]

SYMBOLS = {
    'F5H_D6496': {'left': _MUX_LEFT, 'right': [None] * 10 + [('XX', 'D')],
                  'top': [('1', 'V+')], 'bottom': [('27', 'V-'), None, None, ('L2', 'GND')],
                  'prefix': 'V'},
    # AD590 current-source sensor; pin numbers are not printed (1=+, 2=-, 3=case lead)
    'F5H_AD590': {'left': [('3', 'CASE')], 'top': [('1', '+')], 'bottom': [('2', '-')],
                  'prefix': 'U'},
    # DG413 ("D6413" as printed) sections, pin numbers as printed per section
    'F5H_D6413_S1': {'left': [None, ('3', 'S'), None], 'right': [None, ('2', 'D'), None],
                     'top': [None, None, ('12', 'VL'), None, None],
                     'bottom': [None, None, ('1', 'IN'), None, None], 'prefix': 'V'},
    'F5H_D6413_S2': {'left': [None, ('14', 'S'), None], 'right': [None, ('15', 'D'), None],
                     'bottom': [None, None, ('16', 'IN'), None, None], 'prefix': 'V'},
    'F5H_D6413_S4': {'left': [None, ('6', 'S'), None], 'right': [None, ('7', 'D'), None],
                     'bottom': [None, None, ('8', 'IN'), None, None], 'prefix': 'V'},
    'F5H_D6413_S3': {'left': [None, ('11', 'S'), None], 'right': [None, ('10', 'D'), None],
                     'top': [('4', 'V-'), None, None, None, ('13', 'V+')],
                     'bottom': [('9', 'IN'), None, None, None, ('5', 'GND')], 'prefix': 'V'},
}

_BWT = ['BWT_6R', 'BWT_6P', 'BWT_5R', 'BWT_5P', 'BWT_4R', 'BWT_4P', 'BWT_3R', 'BWT_3P',
        'BWT_2R', 'BWT_2P', 'BWT_1R', 'BWT_1P', 'OFT_T2', 'OFT_T1', 'RST_8', 'CST_1']
_BWH = ['BWH_6R', 'BWH_6P', 'BWH_5R', 'BWH_5P', 'BWH_4R', 'BWH_4P', 'BWH_3R', 'BWH_3P',
        'BWH_2R', 'BWH_2P', 'BWH_1R', 'BWH_1P', None, None, 'DEMAR_TEMP', 'AMB_TEMP']
_ADDR = {'14': 'MM(3)', '15': 'MM(8)', '16': 'MM(1)', '17': 'MM(0)'}


def _mux_pins(inputs, prefix):
    pins = {number: net for (number, _), net in zip(_MUX_LEFT, inputs) if net}
    pins.update(_ADDR)
    pins.update({'18': f'{prefix}_EN', 'XX': f'{prefix}_D', '1': '+15V', '27': '-15V',
                 'L2': 'GND'})
    return pins


_MUX_NOTE = ('Printed "D6496" (probably DG506A, 16-ch mux: pinout matches). Pin 19 printed '
             '"A4" (should be input 00); GND pin printed "L2" (probably 12); D pin printed "XX"; '
             'A2 address net printed MM(8) (probably MM(2)).')
_LMC = {'-': '2', '+': '3', 'out': '1', 'v+': '0', 'v-': '4'}
_LT_A = {'-': '6', '+': '5', 'out': '7'}
_LT_B = {'-': '2', '+': '3', 'out': '1', 'v+': '0', 'v-': '4'}
_V_PLUS_0 = 'V+ pin number printed "0" (probably 8)'

PARTS = [
    # ── FIG 5H-1: V1 mux (BWT_/OFT/RST/CST) -> V15 -> T.CLUSTER ──
    P('V1', 'D6496', 'F5H_D6496', at=(60, 85), pins=_mux_pins(_BWT, '5H1_V1'),
      probable='DG506A', note=_MUX_NOTE),
    P('C10', '.1uF', 'C', at=(74, 52), pins={'1': '+15V', '2': 'GND'}),
    P('C1', '.1uF', 'C', at=(40, 125), pins={'1': '-15V', '2': 'GND'}),
    P('R33', '10K', 'R', at=(28, 112), rot=270, pins={'1': '5H1_V1_EN', '2': '+5V'}),
    P('R32', '15K', 'R', at=(84, 85), rot=270, pins={'1': '5H1_R32_R57', '2': '5H1_V1_D'}),
    P('R57B', '51.1K', 'R', at=(100, 85), rot=270, pins={'1': '5H1_V15_INV', '2': '5H1_R32_R57'},
      printed='R57', note='R57 printed twice on 5H-1 (both 51.1K)'),
    P('R57', '51.1K', 'R', at=(120, 70), rot=270, pins={'1': '5H1_V15_INV', '2': '-10V'}),
    P('R102', 'XX.XK', 'R', at=(152, 58), rot=270, pins={'1': 'T.CLUSTER', '2': '5H1_V15_INV'},
      note='Value printed as XX.XK (not specified)'),
    P('V15', 'LMC6482', 'OPAMP', at=(150, 87), pinmap=_LMC,
      pins={'2': '5H1_V15_INV', '3': '5H1_V15_NINV', '1': 'T.CLUSTER', '0': '+5VA', '4': 'GND'},
      note=_V_PLUS_0),
    P('C22', '.1uF', 'C', at=(162, 72), pins={'1': '+5VA', '2': 'GND'}),
    P('R103', '10.7K', 'R', at=(132, 104), pins={'1': '5H1_V15_NINV', '2': '5H1_R103_ARROW'},
      note='Lower end drawn to a bare supply arrow with no label'),

    # ── FIG 5H-1: V2 mux (BWH_/DEMAR/AMB) -> V14 -> ERR.WARMERS ──
    P('V2', 'D6496', 'F5H_D6496', at=(60, 195), pins=_mux_pins(_BWH, '5H1_V2'),
      probable='DG506A', note=_MUX_NOTE + ' Pins 22/21 drawn as open stubs.'),
    P('C11', '.1uF', 'C', at=(74, 162), pins={'1': '+15V', '2': 'GND'}),
    P('C6', '.1uF', 'C', at=(40, 235), pins={'1': '-15V', '2': 'GND'}),
    P('R34', '10K', 'R', at=(28, 222), rot=270, pins={'1': '5H1_V2_EN', '2': '+5V'}),
    P('R55', '11.3K', 'R', at=(84, 195), rot=270, pins={'1': '5H1_R55_R56', '2': '5H1_V2_D'}),
    P('R56', '49.9K', 'R', at=(100, 195), rot=270, pins={'1': '5H1_V14_INV', '2': '5H1_R55_R56'}),
    P('R98', '20K', 'R', at=(152, 168), rot=270, pins={'1': 'ERR.WARMERS', '2': '5H1_V14_INV'}),
    P('V14', 'LMC6482', 'OPAMP', at=(150, 197), pinmap=_LMC,
      pins={'2': '5H1_V14_INV', '3': '5H1_V14_NINV', '1': 'ERR.WARMERS', '0': '+5VA', '4': 'GND'},
      note=_V_PLUS_0),
    P('C21', '.1uF', 'C', at=(162, 182), pins={'1': '+5VA', '2': 'GND'}),
    P('R99', '17.0K', 'R', at=(132, 214), pins={'1': '5H1_V14_NINV', '2': '5H1_R99_ARROW'},
      note='Lower end drawn to a bare supply arrow with no label'),

    # ── FIG 5H-2: ambient AD590 channel -> AMB_TEMP ──
    P('U21', 'AD590JM', 'F5H_AD590', at=(250, 80),
      pins={'1': '+5VA', '2': '5H2_AMB_SENSE', '3': 'GND'}, printed='21',
      note='Printed "21" beside the AD590 symbol (no U prefix); pin numbers not printed'),
    P('C31', '.1uF', 'C', at=(266, 62), pins={'1': '+5VA', '2': 'GND'},
      note='Value printed ".1vF" twice'),
    P('R51', '1.000K .1v', 'R', at=(250, 104), pins={'1': '5H2_AMB_SENSE', '2': 'GND'},
      note='Tolerance printed ".1v" (probably .1%)'),
    P('V12A', 'LT1124', 'OPAMP', at=(296, 90), pinmap=_LT_A, printed='V12',
      pins={'5': '5H2_AMB_SENSE', '6': '5H2_V12A_FB', '7': '5H2_V12A_OUT'}),
    P('R94', '1K', 'R', at=(296, 66), rot=270, pins={'1': '5H2_V12A_OUT', '2': '5H2_V12A_FB'},
      note='Between pin 6 and pin 7'),
    P('C36', '.1uF', 'C', at=(296, 74), rot=270, pins={'1': '5H2_V12A_OUT', '2': '5H2_V12A_FB'}),
    P('R59', '10K', 'R', at=(320, 92), rot=270, pins={'1': '5H2_V12B_INV', '2': '5H2_V12A_OUT'}),
    P('V12B', 'LT1124', 'OPAMP', at=(350, 94), pinmap=_LT_B, printed='V12',
      pins={'2': '5H2_V12B_INV', '3': '5H2_V12B_NINV', '1': 'AMB_TEMP', '0': '+15V', '4': '-15V'},
      note=_V_PLUS_0),
    P('RXX', 'XX.K', 'R', at=(352, 66), rot=270, pins={'1': 'AMB_TEMP', '2': '5H2_V12B_INV'},
      note='Ref printed RXX, value printed XX.K (not specified)'),
    P('R95', '7.07K', 'R', at=(334, 116), pins={'1': '5H2_V12B_NINV', '2': 'GND'}),
    P('C19', '.1uF', 'C', at=(366, 78), pins={'1': '+15V', '2': 'GND'}),
    P('C19B', '.1uF', 'C', at=(366, 110), pins={'1': '-15V', '2': 'GND'}, printed='C19',
      note='C19 printed twice on 5H-2'),

    # ── FIG 5H-2: dewar AD590 (off-board via J2) -> DEMAR_TEMP; J15 ──
    P('J2', 'J2', 'CONN_4', at=(430, 140),
      pins={'1': '+5VA', '2': '5H2_DEMAR_SENSE', '3': 'NC', '4': 'GND'},
      note='Pin 3 = POLARIZING_KEY'),
    P('J15', 'J15', 'CONN_4', at=(430, 190), pins={'1': '+5VA', '2': 'NC', '3': 'CHT_T', '4': 'GND'},
      note='Pin 2 = POLARIZING_KEY'),
    P('R48', '1.000K .1v', 'R', at=(250, 184), pins={'1': '5H2_DEMAR_SENSE', '2': 'GND'},
      note='Tolerance printed ".1v" (probably .1%)'),
    P('V13A', 'LT1124', 'OPAMP', at=(296, 170), pinmap=_LT_A, printed='V13',
      pins={'5': '5H2_DEMAR_SENSE', '6': '5H2_V13A_FB', '7': '5H2_V13A_OUT'}),
    P('R96', '1K', 'R', at=(296, 146), rot=270, pins={'1': '5H2_V13A_OUT', '2': '5H2_V13A_FB'},
      note='Between pin 6 and pin 7'),
    P('C37', '.1uF', 'C', at=(296, 154), rot=270, pins={'1': '5H2_V13A_OUT', '2': '5H2_V13A_FB'}),
    P('R53', '10K', 'R', at=(320, 172), rot=270, pins={'1': '5H2_V13B_INV', '2': '5H2_V13A_OUT'}),
    P('V13B', 'LT1124', 'OPAMP', at=(350, 174), pinmap=_LT_B, printed='V13',
      pins={'2': '5H2_V13B_INV', '3': '5H2_V13B_NINV', '1': 'DEMAR_TEMP', '0': '+15V', '4': '-15V'},
      note=_V_PLUS_0),
    P('R52', '37.4K', 'R', at=(352, 146), rot=270, pins={'1': 'DEMAR_TEMP', '2': '5H2_V13B_INV'}),
    P('R54', '7.07K', 'R', at=(334, 196), pins={'1': '5H2_V13B_NINV', '2': 'GND'}),
    P('C20', '.1uF', 'C', at=(366, 158), pins={'1': '+15V', '2': 'GND'}),
    P('C32', '.1uF', 'C', at=(366, 190), pins={'1': '-15V', '2': 'GND'}),

    # ── FIG 5H-3: V13 (LM06482) error amp -> ERR.SYS.LOOP ──
    P('R104', '10K', 'R', at=(130, 300), rot=270, pins={'1': '5H3_R104_R59', '2': 'CS_CTRL'}),
    P('R59C', '10K', 'R', at=(146, 300), rot=270, pins={'1': '5H3_V13_INV', '2': '5H3_R104_R59'},
      printed='R59', note='R59 printed twice on 5H-3 (64.9K and 10K) and once on 5H-2'),
    P('R59B', '64.9K', 'R', at=(166, 284), rot=270, pins={'1': '5H3_V13_INV', '2': '-10V'},
      printed='R59', note='R59 printed twice on 5H-3 (64.9K and 10K) and once on 5H-2'),
    P('R69', '16.0K', 'R', at=(196, 276), rot=270, pins={'1': 'ERR.SYS.LOOP', '2': '5H3_V13_INV'}),
    P('V13C', 'LM06482', 'OPAMP', at=(196, 302), pinmap={'-': '6', '+': '5', 'out': '7'},
      pins={'6': '5H3_V13_INV', '5': '5H3_V13_NINV', '7': 'ERR.SYS.LOOP'}, printed='V13',
      probable='LMC6482',
      note='Ref V13 also used on 5H-2 for an LT1124; printed "LM06482" (probably LMC6482)'),
    P('R41', '7.07K', 'R', at=(180, 326), pins={'1': '5H3_V13_NINV', '2': 'GND'}),

    # ── FIG 5H-3: V16 DG413 ("D6413") monitor switches ──
    P('R61', '1K', 'R', at=(262, 290), rot=270, pins={'1': '5H3_V16_S1', '2': 'ERR.SYS.LOOP'}),
    P('V16A', 'D6413', 'F5H_D6413_S1', at=(290, 290), printed='V16', probable='DG413',
      pins={'3': '5H3_V16_S1', '2': 'SYS.AMB', '1': '5H3_XXX', '12': '+5V'},
      note='Marked (MC); switch drawn open'),
    P('C24', '.1uF', 'C', at=(306, 266), pins={'1': '+5V', '2': 'GND'}),
    P('R62', '1K', 'R', at=(262, 322), rot=270, pins={'1': '5H3_V16_S2', '2': 'MDT_TOTAL'}),
    P('V16B', 'D6413', 'F5H_D6413_S2', at=(290, 322), printed='V16', probable='DG413',
      pins={'14': '5H3_V16_S2', '15': 'SYS.AMB', '16': '5H3_XXX'},
      note='Marked (MC); switch drawn closed'),
    P('R105', '2K', 'R', at=(262, 352), rot=270, pins={'1': '5H3_V16_S4', '2': 'CNT_T'}),
    P('V16C', 'D6413', 'F5H_D6413_S4', at=(290, 352), printed='V16', probable='DG413',
      pins={'6': '5H3_V16_S4', '7': 'COOLER.MON', '8': '5H3_XXX'},
      note='Marked (MC); switch drawn open'),
    P('R42', '1K', 'R', at=(262, 400), rot=270, pins={'1': '5H3_V16_S3', '2': 'FUR_MON_T'}),
    P('V16D', 'D6413', 'F5H_D6413_S3', at=(290, 400), printed='V16', probable='DG413',
      pins={'11': '5H3_V16_S3', '10': 'COOLER.MON', '9': '5H3_XXX', '4': '-15V', '13': '+15V',
            '5': 'GND'},
      note='Marked (MC); switch drawn closed'),
    P('C33', '.1uF', 'C', at=(272, 376), pins={'1': '-15V', '2': 'GND'}),
    P('C23', '.1uF', 'C', at=(310, 376), pins={'1': '+15V', '2': 'GND'}),
    P('R63', '10K', 'R', at=(330, 412), pins={'1': 'COOLER.MON', '2': 'GND'}),

    # ── FIG 5H-3: V4 rectifier/filter -> FUR_MON_T ──
    P('R288', 'CNET', 'R', at=(30, 392), rot=270, pins={'1': '5H3_R288_R48', '2': '5H3_R288_FLAG'},
      note='Left end goes to an off-page flag with no name printed'),
    P('R48B', '10K', 'R', at=(48, 392), rot=270, pins={'1': '5H3_V4A_INV', '2': '5H3_R288_R48'},
      printed='R48', note='R48 also printed on 5H-2 (1.000K)'),
    P('R287', 'CNET', 'R', at=(30, 416), rot=270, pins={'1': '5H3_R287_R47', '2': '5H3_R287_FLAG'},
      note='Left end goes to an off-page flag with no name printed'),
    P('R47', '10K', 'R', at=(48, 416), rot=270, pins={'1': 'GND', '2': '5H3_R287_R47'}),
    P('V4A', 'LM06482', 'OPAMP', at=(80, 396), printed='V4', probable='LMC6482',
      pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
      pins={'6': '5H3_V4A_INV', '5': 'GND', '7': '5H3_V4A_OUT', '8': '+5VA', '4': 'GND'},
      note='V+ pin number not printed (8 assumed for LMC6482); +5VA drawn'),
    P('CX1', '.1uF', 'C', at=(64, 376), pins={'1': '+5VA', '2': 'GND'},
      note='No reference designator printed'),
    P('R43', '10K', 'R', at=(96, 364), rot=270, pins={'1': '5H3_CR5_K', '2': '5H3_V4A_INV'}),
    P('CR5', '1N4148', 'D', at=(112, 396), rot=180, pins={'1': '5H3_CR5_K', '2': '5H3_V4A_OUT'}),
    P('R36', '10', 'R', at=(132, 396), rot=270, pins={'1': '5H3_R36_C8', '2': '5H3_CR5_K'}),
    P('C8', '.1uF', 'C', at=(146, 410), pins={'1': '5H3_R36_C8', '2': 'GND'}),
    P('R45', '10K', 'R', at=(160, 396), rot=270, pins={'1': '5H3_V4B_NINV', '2': '5H3_R36_C8'}),
    P('V4B', 'LM06482', 'OPAMP', at=(200, 394), printed='V4', probable='LMC6482',
      pinmap={'-': '2', '+': '3', 'out': '1'},
      pins={'2': '5H3_V4B_INV', '3': '5H3_V4B_NINV', '1': 'FUR_MON_T'}),
    P('R43B', '10K', 'R', at=(176, 368), rot=270, pins={'1': '5H3_V4B_INV', '2': 'GND'},
      printed='R43', note='R43 printed twice on 5H-3'),
    P('R44', '10K', 'R', at=(200, 368), rot=270, pins={'1': 'FUR_MON_T', '2': '5H3_V4B_INV'}),
    P('C12', '.1uF/50V', 'C', at=(200, 376), rot=270, pins={'1': 'FUR_MON_T', '2': '5H3_V4B_INV'}),
]

WIRES = [
    ('V1.XX', 'R32.2'), ('R32.1', 'R57B.2'), ('R57B.1', 'V15.2'),
    ('V2.XX', 'R55.2'), ('R55.1', 'R56.2'), ('R56.1', 'V14.2'),
    ('U21.2', 'R51.1'), ('U21.2', 'V12A.5', 'vh'), ('R48.1', 'V13A.5', 'vh'),
    ('R43B.1', 'R44.2'),
    ('R94.1', 'C36.1'), ('R94.2', 'C36.2'),
    ('V12A.7', 'R59.2'), ('R59.1', 'V12B.2'),
    ('R96.1', 'C37.1'), ('R96.2', 'C37.2'),
    ('V13A.7', 'R53.2'), ('R53.1', 'V13B.2'),
    ('R104.1', 'R59C.2'),
    ('R61.1', 'V16A.3'), ('R62.1', 'V16B.14'), ('R105.1', 'V16C.6'), ('R42.1', 'V16D.11'),
    ('R288.1', 'R48B.2'), ('R287.1', 'R47.2'),
    ('V4A.7', 'CR5.2'), ('CR5.1', 'R36.2'), ('R36.1', 'R45.2'), ('R45.1', 'V4B.3'),
    ('R44.1', 'C12.1'), ('R44.2', 'C12.2'),
]

NOTES = [
    ('FIG 5H-1', 15, 30),
    ('[F(U) <- 25/102+2.5]  (T.CLUSTER scale)', 140, 112),
    ('[F(U) <- 50/153V]  (ERR.WARMERS scale)', 140, 222),
    ('V1/V2 address bus printed MM(3), MM(8), MM(1), MM(0) (MM(8) as printed, probably MM(2)).\n'
     'Mux pin 19 printed "A4", GND pin printed "L2", D pin printed "XX".\n'
     'R103/R99 lower ends drawn to bare supply arrows (no label).', 15, 255),
    ('FIG 5H-2', 230, 30),
    ('[V <- 37.4V/00]  (AMB_TEMP scale)', 345, 126),
    ('[V <- 37.4V/00]  (DEMAR_TEMP scale)', 345, 206),
    ('J2-3 / J15-2: POLARIZING_KEY', 410, 215),
    ('U21: printed "21"; dewar AD590 is off-board on J2', 230, 125),
    ('FIG 5H-3', 15, 262),
    ('[F(V) <- 25/51V]', 205, 330),
    ('5H3_XXX: off-page flag printed "XXX" driving all four V16 IN pins', 240, 440),
    ('R288/R287 left ends: off-page flags with no printed names', 15, 440),
]
