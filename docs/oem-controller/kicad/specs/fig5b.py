"""FIG 5B - NSP serial digital pots/latch, CST_1/CST_2 switch, CS_CTRL integrator, OF_SET/OF_OFFSET.

Redrawn to the drawing rules: one child sheet per function (input switch, summing amp,
integrator, NSP pot with its buffer, NSP latch), wires inside each, and hierarchical
labels to the figure page. The patent text does not describe FIG 5B; descriptions cite
what the figure prints and mark the rest as inferred.
"""

from oemsch import P, child, port, tap

TITLE = 'FIG 5B - CS_CTRL loop, NSP pots, OF_SET'
SOURCE = 'US6098409 sheet 5 of 25 (PDF p6), FIG 5B'
PAPER = 'A4'
REDRAWN = True

DUP = 'Printed pin number repeats on this symbol; suffix #2 added to keep pins distinct'
_INF = 'Inferred from the circuit: '
NSP = ('NSP = non-volatile set point (service manual SF p.66 "Dump Non-volatile set point '
       'parameters"); the link to these parts is inferred')

SYMBOLS = {
    # DG413 switch 1 as printed (both supply pins printed "V-"; the unnamed pin goes only to
    # C94). Drawn by function: S and IN left, D and the C94 pin right, supplies top (the +15V
    # one first), GND bottom.
    'F5B_DG413_A': {
        'left': [('3', 'S'), None, ('1', 'IN')],
        'right': [('2', 'D'), None, ('?', '?')],
        'top': [('V-#2', 'V-'), None, None, None, ('V-', 'V-')],
        'bottom': [('5', 'GND')], 'vlength': 7.62,
    },
    # switch 2 drawn the same size and order as switch 1 (it has no supply pins)
    'F5B_DG413_B': {'left': [('14', 'S'), None, ('16', 'IN')], 'right': [('15', 'D')],
                    'top': [None, None, None, None, None], 'bottom': [None]},
    # MC2030 dual serial pot: serial inputs left; each pot's RI / WP / RF ends right, spaced so
    # the +5VA and GND symbols on them stay apart; SER_OUT last.
    'F5B_MC2030': {
        'left': [('13', 'PROG'), None, ('14', 'READ'), None, ('2', 'SER.IN'), None, ('1', 'SER.CLK')],
        'right': [('13#2', 'RIA'), None, ('10', 'WPA'), None, ('9', 'RFA'), None, None, None,
                  ('4', 'RID'), None, ('6', 'WPD'), None, ('7', 'RFD'), None, None, ('3', 'SER_OUT')],
        'top': [('UDD', 'UDD')], 'bottom': [('6#2', 'GND')],
    },
    # MC2001 serial latch: serial inputs left in the order that nests the shared NSP lines on
    # the figure page; outputs right; the tied-off bubble input beside GND on the bottom.
    'F5B_MC2001': {
        'left': [('1', 'SER.CLK'), None, ('2', 'SER_IN'), None, ('14', '~{READ}'), None, ('15', '~{PROG}')],
        'right': [('4', 'O7'), ('13', 'O6'), ('5', 'O5'), ('12', 'O4'), ('6', 'O3'),
                  ('11', 'O2'), ('7', 'O1'), ('10', 'O0'), None, ('3', 'SER.OUT')],
        'top': [('UDD', 'UDD')], 'bottom': [('9', 'BUBBLE'), None, ('6#2', 'GND')],
    },
}

OPAMP_PINS = {'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'}

# ── CST_2 / CST_1 through the U43 DG413 switches, both controlled by CST_DEL ──
SWITCH = child(
    'switch', 'CST_1 / CST_2 input switch (U43)', short='SWITCH', paper='A4', at=(104, 66), width=30.48,
    parts=[
        P('R201', '10K', 'R', at=(50, 60), rot=90, pins={'1': 'CST_2', '2': '5B_U43A_S'},
          desc=_INF + 'series resistor from CST_2 into the U43 switch 1 source'),
        P('U43A', 'DG413', 'F5B_DG413_A', at=(85, 62), text=(2, 6), printed='U43',
          pins={'3': '5B_U43A_S', '2': '5B_SW_OUT', '?': '5B_U43_C94', 'V-': '-15V',
                'V-#2': '+15V', '1': 'CST_DEL', '5': 'GND'},
          note='Both supply pins printed "V-" (the one on +15V is presumably V+); '
          'unnamed/unnumbered right-side pin goes only to C94 (presumably VL); S/D/IN names functional',
          desc=_INF + 'analog switch passing CST_2 (through R201) to the U42 summing input when CST_DEL '
                      'turns it on'),
        P('C94', '.1uF', 'C', at=(100, 72), pins={'1': '5B_U43_C94', '2': 'GND'},
          desc=_INF + 'capacitor to ground on the unnamed U43 pin (presumably the VL logic supply)'),
        P('R200', '10K', 'R', at=(50, 84), rot=90, pins={'1': 'CST_1', '2': '5B_U43B_S'},
          note='R200 is also listed in the FIG 5A option table (OMIT for both -001 and -002)',
          desc=_INF + 'series resistor from CST_1 into the U43 switch 2 source (OMIT in both FIG 5A '
                      'builds)'),
        P('U43B', 'DG413', 'F5B_DG413_B', at=(85, 86), text=(2, 6), printed='U43',
          pins={'14': '5B_U43B_S', '15': '5B_SW_OUT', '16': 'CST_DEL'},
          desc=_INF + 'analog switch passing CST_1 (through R200) to the U42 summing input when CST_DEL '
                      'turns it on'),
        P('C113', '.1uF', 'C', at=(40, 140), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U43 -15V supply decoupling'),
        P('C93', '.1uF', 'C', at=(53, 140), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U43 +15V supply decoupling'),
    ],
    ports=[port('CST_2', 'input', on='R201.1', side='left'),
           port('CST_1', 'input', on='R200.1', side='left'),
           port('CST_DEL', 'input', at=(24, 76), facing='left'),
           port('5B_SW_OUT', 'output', at=(130, 60), facing='right')],
    taps=[tap('del', 'CST_DEL', (30, 76)), tap('sw', '5B_SW_OUT', (120, 60))],
    wires=[
        ('R201.2', 'U43A.3'), ('R200.2', 'U43B.14'),
        ('@CST_DEL', '@del'), ('@del', 'U43A.1', 'vh'), ('@del', 'U43B.16', 'vh'),
        ('U43A.2', '@sw'), ('@sw', '@5B_SW_OUT'), ('U43B.15', '@sw', 'hv'),
        ('U43A.?', 'C94.1', 'hv'), ('C113.2', 'C93.2'),
    ],
    names={'5B_U43A_S': None, '5B_U43B_S': None, '5B_U43_C94': None, 'GND': ['C113.2', 'C94.2', 'U43A.5']},
    notes=[('U43 DECOUPLING CAPACITORS', 32, 128),
           ('U43 supply pins are both printed "V-"; the +15V one is presumably V+.\n'
            'The unnamed U43 pin to C94 is presumably VL.', 15, 152)],
)

# ── U42 LT1012 summing amplifier ──
SUM = child(
    'sum', 'Summing amplifier (U42)', short='SUM', paper='A4', at=(140, 40), width=30.48,
    parts=[
        P('R211', '10K', 'R', at=(46, 48), rot=270, pins={'1': '5B_U42_INV', '2': '+10V'},
          note='Supply printed "10V"',
          desc=_INF + 'input resistor from +10V into the U42 summing junction (offset)'),
        P('R213', '10K', 'R', at=(46, 60), rot=90, pins={'1': 'OF_SET', '2': '5B_U42_INV'},
          desc=_INF + 'input resistor from OF_SET (U54) into the U42 summing junction'),
        P('R212', '10K', 'R', at=(46, 72), rot=90, pins={'1': '5B_SW_OUT', '2': '5B_U42_INV'},
          desc=_INF + 'input resistor from the U43 switch output into the U42 summing junction'),
        P('U42', 'LT1012', 'OPAMP', at=(75, 62), text=(5, 4), pinmap=OPAMP_PINS,
          pins={'2': '5B_U42_INV', '3': '5B_U42_NINV', '6': '5B_U42_OUT', '7': '+15V', '4': '-15V'},
          desc=_INF + 'inverting summing amplifier of +10V, OF_SET and the switched CST input; its '
                      'output feeds the U35 integrator'),
        P('R296', '?', 'R', at=(75, 40), rot=90, pins={'1': '5B_U42_INV', '2': '5B_U42_OUT'},
          note='No value printed',
          desc=_INF + 'U42 feedback resistor (sets the gain; value not printed)'),
        P('R214', '24.3K', 'R', at=(67, 80), pins={'1': '5B_U42_NINV', '2': 'GND'},
          desc=_INF + 'U42 non-inverting input resistor to ground'),
        P('C91', '.1uF', 'C', at=(40, 140), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U42 +15V supply decoupling'),
        P('C111', '.1uF', 'C', at=(53, 140), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U42 -15V supply decoupling'),
    ],
    ports=[port('OF_SET', 'input', on='R213.1', side='left'),
           port('5B_SW_OUT', 'input', on='R212.1', side='left'),
           port('5B_U42_OUT', 'output', at=(96, 62), facing='right')],
    taps=[tap('ia', '5B_U42_INV', (59, 60)), tap('ib', '5B_U42_INV', (63, 60)),
          tap('ic', '5B_U42_INV', (59, 48)), tap('il', '5B_U42_INV', (59, 44), facing='right'),
          tap('p10', '+10V', (36, 48)),
          tap('out', '5B_U42_OUT', (86, 62))],
    wires=[
        ('R213.2', '@ia'), ('@ia', '@ib'), ('@ib', 'U42.2'),
        ('R296.1', '@il', [(59, 40)]), ('@il', '@ic'), ('@ic', '@ia'), ('R211.1', '@ic'),
        ('R212.2', '@ib', [(63, 72)]), ('R211.2', '@p10'),
        ('U42.6', '@out'), ('@out', '@5B_U42_OUT'), ('R296.2', '@out', [(86, 40)]),
        ('R214.1', 'U42.3'), ('C91.2', 'C111.2'),
    ],
    names={'5B_U42_INV': '@il', '5B_U42_NINV': None, '+10V': '@p10'},
    notes=[('U42 DECOUPLING CAPACITORS', 32, 128),
           ('"10V" printed at R211: taken as the +10V rail (FIG 5F).', 15, 152)],
)

# ── U35 LMC6001 integrator -> CS_CTRL ──
INTEG = child(
    'integ', 'CS_CTRL integrator (U35)', short='INTEG', paper='A4', at=(176, 40), width=30.48,
    parts=[
        P('R205', '100K', 'R', at=(60, 68), rot=90, pins={'1': '5B_U42_OUT', '2': '5B_R205_R203'},
          desc=_INF + 'input resistor from the U42 output into the U35 integrator (with R203)'),
        P('R203', '1M', 'R', at=(80, 68), rot=90, text=(-2, 2), pins={'1': '5B_R205_R203', '2': '5B_U35_INV'},
          desc=_INF + 'second input resistor in series with R205, bypassed by C109'),
        P('C109', '?', 'C', at=(80, 60), rot=90, pins={'1': '5B_R205_R203', '2': '5B_U35_INV'},
          note='No value printed',
          desc=_INF + 'capacitor across R203 (input lead network; value not printed)'),
        P('U35', 'LMC6001', 'OPAMP', at=(110, 70), text=(4, 4), pinmap=OPAMP_PINS,
          pins={'2': '5B_U35_INV', '3': '5B_U35_NINV', '6': 'CS_CTRL', '7': '+5VA', '4': '-5V'},
          desc=_INF + 'integrator (C108 + R199 and C98 feedback) of the U42 sum; its output is CS_CTRL, '
                      'out on J5A1 pin 29 (FIG 5A) and to FIG 5H'),
        P('R284', '1.10M', 'R', at=(102, 79), text=(-8, 0), pins={'1': '5B_U35_NINV', '2': 'GND'},
          note='R284 is also listed in the FIG 5A option table (-001: 0, -002: OMIT)',
          desc=_INF + 'U35 non-inverting input resistor to ground (0 ohm or OMIT per the FIG 5A '
                      'option table)'),
        P('C108', '10K', 'C', at=(100, 46), rot=90, pins={'1': '5B_U35_INV', '2': '5B_C108_R199'},
          note='Capacitor symbol with value printed "10K"',
          desc=_INF + 'integrating capacitor in the U35 feedback, in series with R199 (value printed '
                      '"10K")'),
        P('R199', '1M', 'R', at=(115, 46), rot=90, pins={'1': '5B_C108_R199', '2': 'CS_CTRL'},
          desc=_INF + 'resistor in series with C108 in the U35 feedback (proportional term)'),
        P('C98', '?', 'C', at=(108, 32), rot=90, pins={'1': '5B_U35_INV', '2': 'CS_CTRL'},
          note='No value printed',
          desc=_INF + 'capacitor across the U35 feedback (roll-off; value not printed)'),
        P('C74', '.1uF', 'C', at=(40, 140), pins={'1': '+5VA', '2': 'GND'},
          desc=_INF + 'U35 +5VA supply decoupling'),
        P('C79', '.1uF', 'C', at=(53, 140), pins={'1': '-5V', '2': 'GND'},
          desc=_INF + 'U35 -5V supply decoupling'),
    ],
    ports=[port('5B_U42_OUT', 'input', on='R205.1', side='left'),
           port('CS_CTRL', 'output', at=(135, 70), facing='right')],
    taps=[tap('n', '5B_U35_INV', (93, 68)), tap('n2', '5B_U35_INV', (93, 46)),
          tap('o', 'CS_CTRL', (125, 70)), tap('o2', 'CS_CTRL', (125, 46))],
    wires=[
        ('R205.2', 'R203.1'), ('C109.1', 'R203.1', 'vh'), ('C109.2', 'R203.2', 'vh'),
        ('R203.2', '@n'), ('@n', 'U35.2'), ('C108.1', '@n2'), ('@n2', '@n'), ('C98.1', '@n2', [(93, 32)]),
        ('C108.2', 'R199.1'), ('R199.2', '@o2'), ('C98.2', '@o2', [(125, 32)]), ('@o2', '@o'),
        ('U35.6', '@o'), ('@o', '@CS_CTRL'),
        ('R284.1', 'U35.3'), ('C74.2', 'C79.2'),
    ],
    names={'5B_R205_R203': None, '5B_U35_INV': None, '5B_U35_NINV': None, '5B_C108_R199': None},
    notes=[('U35 DECOUPLING CAPACITORS', 32, 128)],
)

# ── U36 MC2030 serial dual pot and the U54 buffer -> OF_SET, OF_OFFSET ──
POT = child(
    'pot', 'NSP serial pot and OF_SET buffer (U36, U54)', short='POT', paper='A4', at=(70, 40), width=30.48,
    parts=[
        P('U36', 'MC2030', 'F5B_MC2030', at=(60, 80),
          pins={'13': 'NSP_PROG', '14': 'NSP_READ', '2': 'NSP_SER0', '1': 'NSP_CLK',
                '13#2': '+5VA', '10': '5B_WPA', '9': 'GND', '4': '+5VA', '6': 'OF_OFFSET',
                '7': 'GND', '3': 'NSP_SER9', 'UDD': '+5V', '6#2': 'DGND'},
          probable='unidentified dual serial digital potentiometer (MC2030 family; HANDOFF: dual 1K)',
          note='Pin 13 printed for PROG and RIA; pin 6 printed for WPD and GND. ' + DUP
          + '. UDD unnumbered. Input label read as NSP_SER0 (0 vs O ambiguous in the font)',
          desc=_INF + 'dual serial digital pot loaded over the NSP lines; pot A (+5VA to GND) sets the '
                      'OF_SET level through U54, pot D sets OF_OFFSET. ' + NSP),
        P('R2-49', '10K', 'R', at=(85, 68), rot=90, pins={'1': '5B_WPA', '2': '5B_U54_NINV'},
          note='Ref printed with a hyphen "R2-49"',
          desc=_INF + 'series resistor from the U36 pot A wiper to the U54 buffer input'),
        P('U54', 'LT1124', 'OPAMP', at=(105, 66), text=(4, 4), pinmap={'-': '2', '+': '3', 'out': '7',
                                                        'v+': 'V+', 'v-': 'V-'},
          pins={'2': '5B_U54_INV', '3': '5B_U54_NINV', '7': 'OF_SET', 'V+': '+15V', 'V-': '-15V'},
          note='Supply pins drawn but unnumbered; output printed 7 with inputs 2/3 '
          '(FIG 5A spare U54 section also uses pin 7)',
          desc=_INF + 'unity follower (R2-48 feedback) buffering the U36 pot A wiper as OF_SET, to the '
                      'U42 sum and FIG 5C'),
        P('R2-48', '10K', 'R', at=(105, 48), rot=90, pins={'1': '5B_U54_INV', '2': 'OF_SET'},
          note='Ref printed with a hyphen "R2-48"',
          desc=_INF + 'U54 feedback resistor (output to inverting input: a follower)'),
        P('C90', '.1uF', 'C', at=(40, 140), pins={'1': '+5V', '2': 'GND'},
          desc=_INF + 'U36 +5V (UDD) supply decoupling'),
        P('C92', '.1uF', 'C', at=(53, 140), pins={'1': '+5VA', '2': 'GND'},
          desc=_INF + 'decoupling on +5VA, the U36 pot reference'),
        P('C143', '.1uF', 'C', at=(80, 140), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U54 +15V supply decoupling'),
        P('C146', '.1uF', 'C', at=(93, 140), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U54 -15V supply decoupling'),
    ],
    ports=[port('NSP_PROG', 'input', on='U36.13', side='left'),
           port('NSP_READ', 'input', on='U36.14', side='left'),
           port('NSP_SER0', 'input', on='U36.2', side='left'),
           port('NSP_CLK', 'input', on='U36.1', side='left'),
           port('OF_SET', 'output', at=(128, 66), facing='right')],
    taps=[tap('of', 'OF_SET', (119, 66))],
    wires=[
        ('U36.10', 'R2-49.1'), ('R2-49.2', 'U54.3'),
        ('R2-48.1', 'U54.2', [(93, 48), (93, 64)]), ('R2-48.2', '@of', [(119, 48)]),
        ('U54.7', '@of'), ('@of', '@OF_SET'),
        ('C90.2', 'C92.2'), ('C143.2', 'C146.2'),
    ],
    long_nets={'OF_OFFSET', 'NSP_SER9'},
    names={'5B_WPA': 'U36.10', '5B_U54_NINV': None, '5B_U54_INV': None},
    notes=[('U36 DECOUPLING CAPACITORS', 32, 128), ('U54 DECOUPLING CAPACITORS', 72, 128),
           ('OF_OFFSET and NSP_SER9 are printed as off-page flags; no transcribed figure uses them.\n'
            'DGND = the filled-arrow ground symbol of the patent.', 15, 152)],
)

# ── U29 MC2001 serial latch -> CST_DEL, RAW_SHUTO_T-, NSP_SERI ──
LATCH = child(
    'latch', 'NSP serial latch (U29)', short='LATCH', paper='A4', at=(70, 90), width=30.48,
    parts=[
        P('U29', 'MC2001', 'F5B_MC2001', at=(80, 70),
          pins={'9': 'DGND', '15': 'NSP_PROG', '14': 'NSP_READ', '2': 'NSP_SER0', '1': 'NSP_CLK',
                '4': 'NC', '13': 'NC', '5': 'NC', '12': 'NC', '6': 'RAW_SHUTO_T-', '11': 'NC',
                '7': 'CST_DEL', '10': 'NC', '3': 'NSP_SERI', 'UDD': '+5V', '6#2': 'DGND'},
          note='Pin 6 printed for O3 and GND. ' + DUP + '. O3 line drawn through an "N/C" '
          'note yet continues to RAW_SHUTO_T-. UDD unnumbered; pin 9 bubble input unnamed. '
          'U29 is also printed as MC93 gates on FIG 5A (ref clash)',
          desc=_INF + 'serial latch on the NSP lines: O1 drives CST_DEL (the U43 switches), O3 drives '
                      'RAW_SHUTO_T- (to FIG 5E); its SER.OUT continues the chain as NSP_SERI. ' + NSP),
        P('C90B', '.1uF', 'C', at=(40, 130), printed='C90', pins={'1': '+5V', '2': 'GND'},
          note='C90 printed twice on FIG 5B',
          desc=_INF + 'U29 +5V (UDD) supply decoupling'),
    ],
    ports=[port('NSP_CLK', 'input', on='U29.1', side='left'),
           port('NSP_SER0', 'input', on='U29.2', side='left'),
           port('NSP_READ', 'input', on='U29.14', side='left'),
           port('NSP_PROG', 'input', on='U29.15', side='left'),
           port('CST_DEL', 'output', on='U29.7', extra=2),
           port('RAW_SHUTO_T-', 'output', on='U29.6', extra=2),
           port('NSP_SERI', 'output', on='U29.3', extra=2)],
    wires=[('U29.9', 'U29.6#2')],
    names={'DGND': 'U29.6#2'},
    notes=[('U29 DECOUPLING CAPACITOR', 32, 118),
           ('U29 pin 9 (bubble input, unnamed) and GND go to DGND, the filled-arrow ground.\n'
            'O7, O6, O5, O4, O2 and O0 are drawn unconnected (N/C).', 15, 140)],
)

CHILDREN = [SWITCH, SUM, INTEG, POT, LATCH]

# ── Figure page: the child blocks and how they connect ──
# The four NSP lines reach both POT and LATCH. LATCH takes them in the reverse order, so the
# lines nest without crossing; each figure-level label sits on its own line between them.
PAGE_TAPS = [tap('ofs', 'OF_SET', (100, 44)), tap('del', 'CST_DEL', (100, 94)),
             tap('swl', '5B_SW_OUT', (134, 58), facing='left')]
PAGE_NAMES = {'5B_SW_OUT': '@swl'}
PAGE_WIRES = [
    ('pot:NSP_PROG', '@NSP_PROG', [(30, 44)]), ('latch:NSP_PROG', '@NSP_PROG', [(30, 106)]),
    ('pot:NSP_READ', '@NSP_READ', [(46, 48)]), ('latch:NSP_READ', '@NSP_READ', [(46, 102)]),
    ('pot:NSP_SER0', 'latch:NSP_SER0', [(52, 52), (52, 98)]),
    ('pot:NSP_CLK', '@NSP_CLK', [(64, 56)]), ('latch:NSP_CLK', '@NSP_CLK', [(64, 94)]),
    ('pot:OF_SET', '@ofs'), ('@ofs', 'sum:OF_SET'), ('@ofs', '@OF_SET', [(100, 34)]),
    ('latch:CST_DEL', '@del'), ('@del', 'switch:CST_DEL', [(100, 78)]),
    ('latch:RAW_SHUTO_T-', '@RAW_SHUTO_T-'), ('latch:NSP_SERI', '@NSP_SERI'),
    ('@CST_2', 'switch:CST_2'), ('@CST_1', 'switch:CST_1'),
    ('switch:5B_SW_OUT', '@swl', [(134, 70)]), ('@swl', 'sum:5B_SW_OUT', [(134, 48)]),
    ('sum:5B_U42_OUT', 'integ:5B_U42_OUT'),
    ('integ:CS_CTRL', '@CS_CTRL'),
]
# figure ports: OF_SET first on the right, level with FIG 5C's OF_SET pin on the patent sheet
PORTS = [
    port('CST_2', 'input', at=(96, 70), facing='left'),
    port('CST_1', 'input', at=(96, 74), facing='left'),
    port('NSP_PROG', 'input', at=(30, 75), facing='left'),
    port('NSP_READ', 'input', at=(46, 75), facing='left'),
    port('NSP_CLK', 'input', at=(64, 75), facing='left'),
    port('OF_SET', 'output', at=(104, 34), facing='right'),
    port('CS_CTRL', 'output', at=(210, 44), facing='right'),
    port('NSP_SERI', 'output', at=(106, 102), facing='right'),
    port('RAW_SHUTO_T-', 'output', at=(106, 98), facing='right'),
]

NOTES = [('NSP lines -> POT (U36 pot, U54 buffer -> OF_SET, OF_OFFSET) and LATCH (U29 -> CST_DEL, RAW_SHUTO_T-).\n'
          'CST_2 / CST_1 -> SWITCH (U43, on CST_DEL) -> SUM (U42, with OF_SET and +10V) -> INTEG (U35) -> CS_CTRL.\n'
          'Signal roles are inferred; the patent text does not describe FIG 5B.', 15, 125)]

NET_DESCRIPTIONS = {
    'CST_1': 'Patent: FIG 5B off-page flag CST_1 (also FIG 5A J5A2 pin 1 / J5A3 pin 2, 5H, 6C). Inferred: '
             'an off-board line switched by U43 switch 2 into the U42 sum; role unknown',
    'CST_2': 'Patent: FIG 5B off-page flag CST_2 (also FIG 5A J5A2 pin 3 / J5A3 pin 7, 6C). Inferred: an '
             'off-board line switched by U43 switch 1 into the U42 sum; role unknown',
    'CST_DEL': 'Patent: FIG 5B label CST_DEL. Inferred from the circuit: U29 latch output O1, turns both '
               'U43 switches on',
    '5B_SW_OUT': 'Inferred from the circuit: joined U43 switch outputs (D), into the U42 sum through R212',
    'OF_SET': 'Patent: FIG 5B off-page flag OF_SET, also used on FIG 5C (U46 through R210). Inferred: '
              'U54-buffered U36 pot A level, also summed into U42 through R213',
    '5B_U42_INV': 'Inferred from the circuit: U42 summing junction (R211 from +10V, R213, R212, feedback R296)',
    '5B_U42_OUT': 'Inferred from the circuit: U42 sum output, into the U35 integrator through R205',
    'CS_CTRL': 'Patent: FIG 5B off-page flag CS_CTRL (printed CS_CNTRL on 5A). Inferred: U35 integrator '
               'output, out on J5A1 pin 29 through R31 (FIG 5A) and to FIG 5H',
    'NSP_PROG': 'Patent: FIG 5B label NSP_PROG (also 5D, 5E). Inferred: program strobe of the NSP serial '
                'devices (U36 PROG, U29 ~PROG)',
    'NSP_READ': 'Patent: FIG 5B label NSP_READ (also 5D, 5E). Inferred: read strobe of the NSP serial '
                'devices (U36 READ, U29 ~READ)',
    'NSP_CLK': 'Patent: FIG 5B label NSP_CLK (also 5D, 5E, 5G). Inferred: serial clock of the NSP devices',
    'NSP_SER0': 'Patent: FIG 5B label NSP_SER0 (read from "NSP_SERO"); no other transcribed figure uses it. '
                'Inferred: serial data into U36 and U29',
    'NSP_SER9': 'Patent: FIG 5B off-page flag NSP_SER9 on U36 SER_OUT; no transcribed figure uses it',
    'NSP_SERI': 'Patent: FIG 5B off-page flag NSP_SERI on U29 SER.OUT (also 5D, 5E). Inferred: the serial '
                'chain continued to the FIG 5D/5E devices',
    'OF_OFFSET': 'Patent: FIG 5B off-page flag OF_OFFSET on the U36 pot D wiper; no transcribed figure '
                 'uses it. Inferred (manual SF p.66): possibly the NSP cooler offset; unconfirmed',
    '5B_WPA': 'Inferred from the circuit: U36 pot A wiper, to the U54 buffer through R2-49',
    'RAW_SHUTO_T-': 'Patent: FIG 5B off-page flag RAW_SHUTO_T- on U29 O3 (printed RAM_SHUTO_T- on 5E). '
                    'Inferred: latched shut-off request, active low, ORed into SHUTO_T on FIG 5E',
}
