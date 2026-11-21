"""FIG 5C - set-point summing, CMT channel, HOG_T (assumed overstroke sensor) channel and back-off counter.

FIG 5C-1 (left half) and FIG 5C-2 (right half) are one drawing split at the page
edge. The eight lines leaving the right edge of 5C-1 continue, in the same order,
on the left edge of 5C-2 (edge y positions at 400 dpi/4: 196/194, 231/230,
266/265, 301/301, 374/376, 531/537, 626/634, 846/860):
  1-5  R192, R189, R193, R195, R199(2nd) -> U34 pin 2 summing bus
  6    R140 (CMT rectifier output)        -> U26 pin 3 / R163 node
  7    SHUTO_T                             -> Q2 gate, U28 CLR pins 3 and 11
  8    U48 comparator output               -> U28 'O' trigger inputs 2 and 10

Redrawn to the drawing rules: one child sheet per function, wires inside each, and
hierarchical labels / sheet pins between them. The circuit is described in
../../analysis/OVERSTROKE.md section 2.3; the patent text says nothing about it, so
descriptions cite what the figure prints and mark the rest as inferred.
"""

from oemsch import P, child, port, tap

TITLE = 'FIG 5C - Set-point sum, overstroke back-off'
SOURCE = 'US6098409 sheets 6-7 of 25 (PDF p7-8), FIG 5C-1 + FIG 5C-2'
PAPER = 'A3'
REDRAWN = True

LT1124_A = {'-': '2', '+': '3', 'out': '1'}
LT1124_B = {'-': '6', '+': '5', 'out': '7'}

SYMBOLS = {
    # LT1011A comparator, pin numbers as printed on FIG 5C-1; drawn by function: inputs
    # left, output right, balance/strobe right and spaced for C126, supplies top/bottom.
    'F5C_LT1011A': {
        'left': [('2', 'IN+'), None, ('3', 'IN-')],
        'right': [('7', 'OUT'), None, ('5', 'BAL'), None, None, None, None, ('6', 'BAL/STB')],
        'top': [('8', 'V+')],
        'bottom': [('1', 'GND'), None, ('4', 'V-')],
        'prefix': 'U',
    },
    # 74HC123 one-shot sections; pin names exactly as printed (X, O, CLR, RK/CK, CK/OK).
    # Same left-side order on both; ~{CLR} faces the shared SHUTO_T line between them
    # (bottom edge on the upper section, top edge on the lower), so no wires cross.
    'F5C_HC123_S1': {
        'left': [('15', 'RK/CK'), None, ('14', 'CK'), None, ('1', 'X'), None, ('2', 'O'), None, None],
        'right': [None, ('13', 'Q'), None, None, None, ('4', '~{Q}')],
        'bottom': [None, None, ('3', '~{CLR}')],
        'prefix': 'U',
    },
    'F5C_HC123_S2': {
        'left': [('7', 'RK/CK'), None, ('6', 'OK'), None, ('9', 'X'), None, ('10', 'O'), None, None],
        'right': [None, ('3', 'Q'), None, None, None, ('12', '~{Q}')],
        'top': [None, None, ('11', '~{CLR}')],
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
_INF = 'Inferred from the circuit: '
_OVS = 'Inferred from the circuit (analysis/OVERSTROKE.md 2.3): '

# ── Set-point sum: U46 offset stage and U34 summing amplifier ──
SUM = child(
    'sum', 'Set-point summing amplifier (U46, U34)', short='SUM', paper='A3', at=(30, 36), width=35.56,
    parts=[
        P('R299', '10K', 'R', at=(46, 58), rot=90, pins={'1': '+5VA', '2': '5C_U46_INV'},
          desc=_INF + 'input resistor from +5VA to the U46 inverting input (offset)'),
        P('R210', '4.08K', 'R', at=(46, 66), rot=90, pins={'1': 'OF_SET', '2': '5C_U46_NI'},
          desc=_INF + 'input resistor from OF_SET (FIG 5B) to the U46 non-inverting input'),
        P('U46', 'LT1124', 'OPAMP', at=(70, 60), text=(7, 3),
          pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
          pins={'6': '5C_U46_INV', '5': '5C_U46_NI', '7': '5C_U46_OUT', '8': '+15V', '4': '-15V'},
          note='Pin 4 drawn to an unlabeled downward supply arrow; -15V assumed (LT1124 V-)',
          desc=_INF + 'offsets and scales OF_SET against +5VA; its output feeds the U34 sum through R193'),
        P('R298', '10K', 'R', at=(70, 42), rot=90, pins={'1': '5C_U46_INV', '2': '5C_U46_OUT'},
          desc=_INF + 'U46 feedback resistor (gain with R299)'),
        P('C196', '.1uF', 'C', at=(40, 180), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U46 +15V supply decoupling'),
        P('C107', '.1uF', 'C', at=(53, 180), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U46 -15V supply decoupling'),
        P('R192', '113K', 'R', at=(130, 30), rot=90, pins={'1': 'WP.SHOSET', '2': '5C_SUM'},
          desc=_INF + 'summing resistor from WP.SHOSET into the U34 summing junction'),
        P('R189', '500K', 'R', at=(130, 40), rot=90, pins={'1': 'WP.SHTR', '2': '5C_SUM'},
          desc=_INF + 'summing resistor from WP.SHTR into the U34 summing junction'),
        P('R193', '130K', 'R', at=(130, 60), rot=90, pins={'1': '5C_U46_OUT', '2': '5C_SUM'},
          desc=_INF + 'summing resistor from the U46 output into the U34 summing junction'),
        P('R195', '500K', 'R', at=(130, 70), rot=90, pins={'1': 'OF_CTAL', '2': '5C_SUM'},
          desc=_INF + 'summing resistor from OF_CTAL into the U34 summing junction'),
        P('R199', '75K', 'R', at=(110, 90), rot=90, pins={'1': 'OFT_TE', '2': '5C_OFT_LL'},
          desc=_INF + 'series resistor of the OFT_TE input network (with C105/C104)'),
        P('C105', '15uF/25V', 'C', at=(100, 100), rot=90, pins={'1': 'OFT_TE', '2': '5C_C105_C104'},
          desc=_INF + 'one of two capacitors in series across R199 (OFT_TE input network)'),
        P('C104', '15uF25V', 'C', at=(115, 100), rot=90, pins={'1': '5C_C105_C104', '2': '5C_OFT_LL'},
          desc=_INF + 'one of two capacitors in series across R199 (OFT_TE input network)'),
        P('R199B', '75K', 'R', at=(130, 90), rot=90, pins={'1': '5C_OFT_LL', '2': '5C_SUM'},
          printed='R199', note='R199 printed twice on FIG 5C-1 (both 75K)',
          desc=_INF + 'summing resistor from the OFT_TE network into the U34 summing junction'),
        P('R191', '450K', 'R', at=(140, 110), rot=270, pins={'1': '5C_SUM', '2': '5C_R191_ARROW'},
          note='Right end drawn to an unlabeled arrow (destination not named)',
          desc=_INF + 'resistor from the U34 summing junction to an unnamed arrow; role unknown'),
        P('C77', '.01uF', 'C', at=(175, 30), rot=90, pins={'1': '5C_SUM', '2': '5C_U34_OUT'},
          desc=_INF + 'U34 feedback capacitor (filters the summed set point)'),
        P('R196', '220K', 'R', at=(175, 40), rot=90, pins={'1': '5C_SUM', '2': '5C_U34_OUT'},
          desc=_INF + 'U34 feedback resistor; sets the gain of the sum'),
        P('U34', 'LT1012', 'OPAMP', at=(175, 64),
          pinmap={'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'},
          pins={'2': '5C_SUM', '3': '5C_U34_NI', '6': '5C_U34_OUT', '7': '+15V', '4': '-15V'},
          note=NOTE_SUPPLY_UNNUM + ' (V- = 4)',
          desc=_OVS + 'inverting summing amplifier; its output is the drive set point fed to the U26 clamp'),
        P('R194', '200K', 'R', at=(155, 74), pins={'1': '5C_U34_NI', '2': 'GND'},
          desc=_INF + 'U34 non-inverting input resistor to ground'),
        P('C76', '.1uF', 'C', at=(80, 180), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U34 +15V supply decoupling'),
        P('C87', '.1uF', 'C', at=(93, 180), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U34 -15V supply decoupling'),
    ],
    ports=[port('OF_SET', 'input', at=(30, 66), facing='left'),
           port('5C_U34_OUT', 'output', at=(200, 64), facing='right')],
    long_nets={'WP.SHOSET', 'WP.SHTR', 'OF_CTAL', '5C_R191_ARROW'},
    taps=[tap('u46inv', '5C_U46_INV', (57, 50), facing='left'),
          tap('ofte', 'OFT_TE', (85, 90), facing='left')],
    wires=[
        ('@OF_SET', 'R210.1'), ('R299.2', 'U46.6'), ('R210.2', 'U46.5', 'hv'),
        ('R298.1', '@u46inv', [(57, 42)]), ('@u46inv', 'U46.6', [(57, 58)]),
        ('R298.2', 'U46.7', 'hv'), ('U46.7', 'R193.1'),
        ('R192.2', 'U34.2', [(150, 30), (150, 62)]), ('R189.2', 'U34.2', [(150, 40), (150, 62)]),
        ('R193.2', 'U34.2', [(150, 60), (150, 62)]), ('R195.2', 'U34.2', [(150, 70), (150, 62)]),
        ('R199B.2', 'U34.2', [(150, 90), (150, 62)]), ('R191.1', 'U34.2', [(150, 110), (150, 62)]),
        ('C77.1', 'U34.2', [(160, 30), (160, 62)]), ('R196.1', 'U34.2', [(160, 40), (160, 62)]),
        ('C77.2', 'U34.6', [(190, 30), (190, 64)]), ('R196.2', 'U34.6', [(190, 40), (190, 64)]),
        ('U34.6', '@5C_U34_OUT'), ('R194.1', 'U34.3', 'vh'),
        ('@ofte', 'R199.1'), ('R199.2', 'R199B.1'), ('C105.1', 'R199.1', [(92, 100), (92, 90)]),
        ('C105.2', 'C104.1'), ('C104.2', 'R199B.1', [(120, 90)]),
        ('C196.2', 'C107.2'), ('C76.2', 'C87.2'),
    ],
    names={'5C_U46_INV': '@u46inv', '5C_U46_NI': 'R210.2', '5C_U46_OUT': 'R193.1', 'OFT_TE': '@ofte',
           '5C_OFT_LL': 'C104.2', '5C_SUM': 'C77.1', '5C_U34_NI': 'U34.3',
           # unnamed before the redraw; a name would be more than a sheet-path rename
           '5C_C105_C104': None},
    notes=[('U46 DECOUPLING CAPACITORS', 32, 168), ('U34 DECOUPLING CAPACITORS', 72, 168),
           ('WP.SHOSET, WP.SHTR, OF_CTAL and OFT_TE are printed as off-page flags; no transcribed\n'
            'figure uses them. R191 right end: unlabeled arrow. U46 pin 4: unlabeled arrow, taken as -15V.',
            15, 140)],
)

# ── CMT channel: U11 amplifier and U26A precision rectifier ──
CMT = child(
    'cmt', 'CMT channel and precision rectifier (U11, U26A)', short='CMT', paper='A4', at=(30, 70), width=35.56,
    parts=[
        P('R91', '10K', 'R', at=(38, 60), rot=90, pins={'1': '+5VA', '2': '5C_U11_INV'},
          desc=_INF + 'input resistor from +5VA to the U11 inverting input (offset)'),
        P('R92', '10K', 'R', at=(38, 68), rot=90, pins={'1': 'CMTO_T', '2': '5C_U11_INV'},
          desc=_INF + 'input resistor from CMTO_T to the U11 inverting input'),
        P('C35', '.01uF', 'C', at=(60, 38), rot=90, pins={'1': '5C_U11_INV', '2': 'CMT_T'},
          desc=_INF + 'U11 feedback capacitor'),
        P('R82', '10K', 'R', at=(60, 46), rot=90, pins={'1': '5C_U11_INV', '2': 'CMT_T'},
          desc=_INF + 'U11 feedback resistor'),
        P('U11', 'LMC6-482', 'OPAMP', at=(60, 70), text=(3, 5),
          pinmap={'-': '2', '+': '3', 'out': '1', 'v+': '8', 'v-': '4'},
          pins={'2': '5C_U11_INV', '3': '5C_U11_NI', '1': 'CMT_T', '8': '+5VA', '4': 'GND'},
          probable='LMC6482 (National dual CMOS rail-to-rail op-amp)',
          desc=_INF + 'inverting amplifier making CMT_T from CMTO_T and +5VA'),
        P('R93', '1K', 'R', at=(40, 82), pins={'1': '5C_U11_NI', '2': 'GND'},
          desc=_INF + 'U11 non-inverting input resistor to ground'),
        P('C29', '.1uF', 'C', at=(40, 140), pins={'1': '+5VA', '2': 'GND'},
          desc=_INF + 'U11 +5VA supply decoupling'),
        P('R127', '4.08K', 'R', at=(85, 70), rot=90, pins={'1': 'CMT_T', '2': '5C_U26A_INV'},
          desc=_INF + 'input resistor from CMT_T to the U26A precision rectifier'),
        P('R126', '11.0K', 'R', at=(92, 60), rot=90, pins={'1': '5C_R126_ARROW', '2': '5C_U26A_INV'},
          note='Left end drawn to an unlabeled downward arrow (supply/reference not named)',
          desc=_INF + 'offset resistor into the U26A inverting input from an unnamed arrow; role unknown '
                      'beyond that'),
        P('R128', '48.3K', 'R', at=(115, 42), rot=90, pins={'1': '5C_U26A_INV', '2': '5C_CMT_RECT'},
          desc=_INF + 'U26A feedback resistor taken after CR11 (precision rectifier gain)'),
        P('C49', '.001SUF', 'C', at=(115, 50), rot=90, pins={'1': '5C_U26A_INV', '2': '5C_U26A_OUT'},
          note='Value printed ".001SUF" (probably .0015uF)',
          desc=_INF + 'U26A feedback capacitor (rectifier stability)'),
        P('CR10', '1N4140', 'D', at=(115, 58), text=(-3, -4), pins={'1': '5C_U26A_INV', '2': '5C_U26A_OUT'},
          probable='1N4148 (printed 1N4140)', note='Cathode to pin 6 node, anode to pin 7',
          desc=_INF + 'precision-rectifier diode: clamps U26A when the output swings the other way'),
        P('U26A', 'LT1124', 'OPAMP', at=(115, 72), pinmap=LT1124_B,
          pins={'6': '5C_U26A_INV', '5': '5C_U26A_NI', '7': '5C_U26A_OUT'}, printed='U26',
          note='U26 is also drawn on FIG 5C-2 with conflicting pins 2/3/6/7 (see U26B)',
          desc=_OVS + 'precision rectifier on CMT_T (with CR10/CR11)'),
        P('R129', '3.24K', 'R', at=(94, 84), pins={'1': '5C_U26A_NI', '2': 'GND'},
          desc=_INF + 'U26A non-inverting input resistor to ground'),
        P('CR11', '1N4140', 'D', at=(145, 72), pins={'1': '5C_U26A_OUT', '2': '5C_CMT_RECT'},
          probable='1N4148 (printed 1N4140)', note='Cathode to U26 pin 7, anode to R128/R140 node',
          desc=_INF + 'precision-rectifier output diode'),
        P('R140', '200K', 'R', at=(163, 72), rot=90, pins={'1': '5C_CMT_RECT', '2': '5C_U26B_NI'},
          desc=_OVS + 'feeds the rectified CMT_T into the ceiling node at the U26B clamp'),
    ],
    ports=[port('5C_U26B_NI', 'output', at=(178, 72), facing='right')],
    long_nets={'CMTO_T', '5C_R126_ARROW'},
    taps=[tap('inv11', '5C_U11_INV', (50, 53), facing='left')],
    wires=[
        ('R92.2', 'U11.2'), ('R91.2', 'U11.2', [(50, 60), (50, 68)]),
        ('C35.1', '@inv11', [(50, 38)]), ('R82.1', '@inv11', [(50, 46)]), ('@inv11', 'U11.2', [(50, 68)]),
        ('C35.2', 'U11.1', [(72, 38), (72, 70)]), ('R82.2', 'U11.1', [(72, 46), (72, 70)]),
        ('U11.1', 'R127.1'), ('R93.1', 'U11.3', 'vh'),
        ('R127.2', 'U26A.6'), ('R126.2', 'U26A.6', [(104, 60), (104, 70)]),
        ('CR10.1', 'U26A.6', [(104, 58), (104, 70)]), ('C49.1', 'U26A.6', [(104, 50), (104, 70)]),
        ('R128.1', 'U26A.6', [(104, 42), (104, 70)]),
        ('C49.2', 'U26A.7', [(127, 50), (127, 72)]), ('CR10.2', 'U26A.7', [(127, 58), (127, 72)]),
        ('U26A.7', 'CR11.1'), ('R129.1', 'U26A.5', 'vh'),
        ('R128.2', 'CR11.2', [(154, 42), (154, 72)]), ('CR11.2', 'R140.1'), ('R140.2', '@5C_U26B_NI'),
    ],
    names={'CMT_T': 'C35.2', '5C_U11_INV': '@inv11', '5C_U11_NI': 'U11.3', '5C_U26A_INV': 'R127.2',
           '5C_U26A_NI': 'U26A.5', '5C_U26A_OUT': 'CR11.1', '5C_CMT_RECT': 'R128.2'},
    notes=[('U11 DECOUPLING CAPACITOR', 32, 128),
           ('CMTO_T and CMT_T are printed as off-page flags; no transcribed figure uses them.\n'
            'R126 left end: unlabeled downward arrow.', 15, 112)],
)

# ── HOG channel: U53A band-pass, U53B thermistor-compensated amplifier ──
HOG = child(
    'hog', 'HOG_T sensor amplifier (U53)', short='HOG', paper='A3', at=(30, 114), width=35.56,
    parts=[
        P('R285', '2.21K', 'R', at=(34, 76), rot=90, pins={'1': 'HOG_T', '2': '5C_HOG_IN'},
          desc=_OVS + 'input resistor from HOG_T (off-board sensor) to the U53A stage'),
        P('C150', '.01uF', 'C', at=(56, 76), rot=90, text=(-3, -5), pins={'1': '5C_HOG_IN', '2': '5C_U53A_INV'},
          desc=_INF + 'input coupling capacitor of the U53A stage'),
        P('C155', '.01uF', 'C', at=(66, 58), rot=90, pins={'1': '5C_HOG_IN', '2': '5C_U53A_OUT'},
          desc=_INF + 'U53A feedback capacitor to the input node (multiple-feedback filter)'),
        P('R266', '221K(RM) / 49.0K', 'R', at=(75, 66), rot=90,
          pins={'1': '5C_U53A_INV', '2': '5C_U53A_OUT'},
          note='Two values printed: "221K(RM)" above the symbol and "49.0K" below',
          desc=_OVS + 'U53A feedback resistor; sets the gain (value differs for the RM build)'),
        P('U53A', 'LT1124', 'OPAMP', at=(75, 78), pinmap=LT1124_A,
          pins={'2': '5C_U53A_INV', '3': '5C_U53A_NI', '1': '5C_U53A_OUT'}, printed='U53',
          desc=_OVS + 'first amplifier of the HOG_T (assumed overstroke sensor) channel'),
        P('R267', '221K', 'R', at=(55, 90), pins={'1': '5C_U53A_NI', '2': 'GND'},
          desc=_INF + 'U53A non-inverting input bias resistor to ground'),
        P('R286', '2.21K', 'R', at=(40, 103), rot=90, pins={'1': 'HOG_TR', '2': 'GND'},
          note='HOG_TR returns to GND through R286 (joined at the R267 ground node)',
          desc=_OVS + 'returns the HOG_TR sensor line to ground'),
        P('C155B', '.01uF', 'C', at=(100, 88), rot=90, pins={'1': '5C_U53A_OUT', '2': '5C_U53B_NI'},
          printed='C155', note='C155 printed twice on FIG 5C-1',
          desc=_OVS + 'AC coupling from U53A to U53B'),
        P('R232', '20K', 'R', at=(118, 98), pins={'1': '5C_U53B_NI', '2': 'GND'},
          desc=_INF + 'U53B non-inverting input resistor to ground (with C155B, a high-pass)'),
        P('R281', '3.08(TM)', 'R', at=(110, 50), rot=90, pins={'1': 'GND', '2': '5C_U53B_INV'},
          desc=_OVS + 'gain resistor to ground in the U53B thermistor network (TM build)'),
        P('R282', '12.4(TM)', 'R', at=(128, 42), rot=90, pins={'1': '5C_U53B_INV', '2': '5C_RT1_TOP'},
          desc=_OVS + 'resistor across RT1 in the U53B feedback network (TM build)'),
        P('R283', '?', 'R', at=(156, 42), rot=90, pins={'1': '5C_RT1_TOP', '2': '5C_U53B_OUT'},
          note='No value printed',
          desc=_OVS + 'series resistor of the U53B thermistor feedback network (no value printed)'),
        P('RT1', 'Y4401', 'THERM', at=(128, 32), rot=270, pins={'1': '5C_RT1_TOP', '2': '5C_U53B_INV'},
          probable='YSI 44001-series NTC thermistor (guess from "Y4401")', note='Printed "RT1 (TM) Y4401"',
          desc=_OVS + 'thermistor in the U53B feedback: temperature-compensates the gain (TM build)'),
        P('R284', '0(RM)', 'R', at=(135, 56), rot=90, pins={'1': '5C_U53B_INV', '2': '5C_U53B_OUT'},
          desc=_OVS + '0 ohm link for the RM build, making U53B a unity follower'),
        P('C167', '.01uF', 'C', at=(135, 66), rot=90, pins={'1': '5C_U53B_INV', '2': '5C_U53B_OUT'},
          desc=_INF + 'U53B feedback capacitor'),
        P('U53B', 'LT1124', 'OPAMP', at=(135, 86),
          pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
          pins={'6': '5C_U53B_INV', '5': '5C_U53B_NI', '7': '5C_U53B_OUT', '8': '+15V', '4': '-15V'},
          printed='U53', note=NOTE_SUPPLY_UNNUM + ' (V- = 4)',
          desc=_OVS + 'second amplifier of the HOG_T channel; output to the U48 trip comparator'),
        P('C141', '.01uF', 'C', at=(40, 180), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U53 +15V supply decoupling'),
        P('C142', '.01uF', 'C', at=(53, 180), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U53 -15V supply decoupling'),
        P('TPX1', 'TP', 'TP', at=(173, 84), pins={'1': '5C_U53B_OUT'},
          note='Unlabeled test point on U53 pin 7 (top of the R283/C167/R284 node)',
          desc='Patent: FIG 5C-1 draws an unlabeled test point on the U53 pin 7 output'),
    ],
    ports=[port('5C_U53B_OUT', 'output', at=(183, 86), facing='right')],
    long_nets={'HOG_T', 'HOG_TR'},
    taps=[tap('a_inv', '5C_U53A_INV', (64, 69), facing='right'),
          tap('b_inv', '5C_U53B_INV', (112, 32), facing='left')],
    wires=[
        ('R285.2', 'C150.1'), ('C155.1', 'C150.1', [(48, 58), (48, 76)]),
        ('C150.2', 'U53A.2'), ('R266.1', '@a_inv', [(64, 66)]), ('@a_inv', 'U53A.2', [(64, 76)]),
        ('R266.2', 'U53A.1', [(87, 66), (87, 78)]), ('C155.2', 'U53A.1', [(87, 58), (87, 78)]),
        ('R267.1', 'U53A.3', 'vh'), ('U53A.1', 'C155B.1', [(91, 78), (91, 88)]),
        ('C155B.2', 'U53B.5'), ('R232.1', 'U53B.5', 'vh'),
        ('@b_inv', 'RT1.2'), ('RT1.2', 'U53B.6', [(120, 32), (120, 84)]),
        ('R282.1', 'U53B.6', [(120, 42), (120, 84)]), ('R281.2', 'U53B.6', [(120, 50), (120, 84)]),
        ('R284.1', 'U53B.6', [(120, 56), (120, 84)]), ('C167.1', 'U53B.6', [(120, 66), (120, 84)]),
        ('R282.2', 'R283.1'), ('RT1.1', 'R283.1', [(147, 32), (147, 42)]),
        ('R283.2', 'U53B.7', [(165, 42), (165, 86)]), ('R284.2', 'U53B.7', [(165, 56), (165, 86)]),
        ('C167.2', 'U53B.7', [(165, 66), (165, 86)]),
        ('U53B.7', 'TPX1.1'), ('TPX1.1', '@5C_U53B_OUT'),
        ('C141.2', 'C142.2'),
    ],
    names={'5C_HOG_IN': 'C155.1', '5C_U53A_INV': '@a_inv', '5C_U53A_OUT': 'C155.2', '5C_U53A_NI': 'U53A.3',
           '5C_U53B_NI': 'C155B.2', '5C_U53B_INV': '@b_inv', '5C_RT1_TOP': 'R282.2'},
    notes=[('U53 DECOUPLING CAPACITORS', 32, 168),
           ('HOG_T / HOG_TR are printed as off-page flags (assumed: overstroke sensor, see\n'
            'TRANSCRIPTION_NOTES.md). "(TM)" / "(RM)" value suffixes printed as-is (tower / rack build).',
            15, 140)],
)

# ── Trip comparator: U48 LT1011A ──
TRIP = child(
    'trip', 'Overstroke trip comparator (U48)', short='TRIP', paper='A4', at=(80, 114), width=35.56,
    parts=[
        P('R253', '10K', 'R', at=(70, 40), rot=90, pins={'1': '5C_U53B_OUT', '2': '5C_U48_OUT'},
          desc=_OVS + 'from the U53B output to the U48 output node (wired to the output as drawn)'),
        P('R254', '10K', 'R', at=(110, 50), rot=270, pins={'1': '5C_U48_OUT', '2': '5C_U48_NI'},
          note='R253/R254 junction is wired directly to the U48 output (latching positive feedback)',
          desc=_OVS + 'from the U48 output node to its + input: positive feedback, latching as drawn'),
        P('TP4', 'TP', 'TP', at=(76, 64), pins={'1': '5C_U48_NI'},
          desc='Patent: FIG 5C-1 test point TP4 on the U48 + input'),
        P('C141B', '.01uF', 'C', at=(82, 76), pins={'1': '5C_U48_NI', '2': 'GND'},
          printed='C141', note='C141 printed twice on FIG 5C-1',
          desc=_INF + 'filter capacitor on the U48 + input'),
        P('U48', 'LT1011A', 'F5C_LT1011A', at=(110, 74),
          pins={'2': '5C_U48_NI', '3': '5C_U48_INV', '7': '5C_U48_OUT', '8': '+5VA', '4': '-15V',
                '1': 'GND', '5': '5C_U48_BAL', '6': '5C_U48_STB'},
          desc=_OVS + 'trip comparator: its output goes high when the HOG_T signal passes the threshold '
                      'set at its - input; open-collector output pulled up by R233'),
        P('C126', '.01uF', 'C', at=(136, 75), pins={'1': '5C_U48_BAL', '2': '5C_U48_STB'},
          desc=_INF + 'capacitor across the U48 balance/strobe pins (response shaping)'),
        P('R233', '1K', 'R', at=(150, 56), pins={'1': '+5VA', '2': '5C_U48_OUT'},
          desc=_OVS + 'pull-up for the U48 open-collector output'),
        P('TP5', 'TP', 'TP', at=(86, 104), text=(2, -4), pins={'1': '5C_U48_INV'},
          desc='Patent: FIG 5C-1 test point TP5 on the U48 - input (trip threshold)'),
        P('R255', '90.7K', 'R', at=(100, 101), pins={'1': '+5VA', '2': '5C_U48_INV'},
          note='"(TM)" printed near R255/C169',
          desc=_OVS + 'upper leg of the trip-threshold divider from +5VA'),
        P('C169', '.01uF', 'C', at=(110, 111), text=(2, -1), pins={'1': '5C_U48_INV', '2': 'GND'},
          note='"(TM)" printed between R255 and C169',
          desc=_INF + 'filter capacitor on the trip threshold'),
        P('R256', '2.09K', 'R', at=(120, 111), pins={'1': '5C_U48_INV', '2': 'GND'},
          desc=_OVS + 'lower leg of the trip-threshold divider'),
        P('R285B', '10K', 'POT', at=(130, 111), pins={'1': '5C_U48_INV', '2': 'GND', '3': 'GND'},
          printed='R285', note='R285 printed twice on FIG 5C-1 (2.21K and this 10K pot); wiper tied to pin 3',
          desc=_OVS + 'trip-threshold adjustment pot in parallel with R256'),
        P('C125', '22uF/25V', 'CP', at=(40, 140), pins={'1': '+5VA', '2': 'GND'},
          desc=_INF + 'U48 +5VA supply bypass capacitor'),
    ],
    ports=[port('5C_U53B_OUT', 'input', at=(30, 40), facing='left'),
           port('5C_U48_OUT', 'output', at=(162, 66), facing='right')],
    taps=[tap('ni48', '5C_U48_NI', (68, 66), facing='left'),
          tap('inv48', '5C_U48_INV', (78, 106), facing='left'),
          tap('rg', 'GND', (135, 116), facing='down')],
    wires=[
        ('@5C_U53B_OUT', 'R253.1'), ('R253.2', 'U48.7', [(142, 40), (142, 66)]),
        ('R254.1', 'U48.7', [(142, 50), (142, 66)]), ('R254.2', 'U48.2', [(88, 50), (88, 66)]),
        ('@ni48', 'TP4.1'), ('TP4.1', 'U48.2'), ('C141B.1', 'U48.2', 'vh'),
        ('U48.7', '@5C_U48_OUT'), ('R233.2', 'U48.7', 'vh'),
        ('U48.5', 'C126.1'), ('U48.6', 'C126.2'),
        ('U48.3', 'R255.2', [(92, 70), (92, 106)]),
        ('@inv48', 'TP5.1'), ('TP5.1', 'R255.2'), ('R255.2', 'C169.1'), ('C169.1', 'R256.1'),
        ('R256.1', 'R285B.1'), ('R285B.2', '@rg', 'vh'), ('R285B.3', '@rg', 'hv'),
    ],
    names={'GND': '@rg', '5C_U48_NI': '@ni48', '5C_U48_INV': '@inv48', '5C_U48_BAL': 'U48.5', '5C_U48_STB': 'U48.6'},
    notes=[('U48 DECOUPLING CAPACITOR', 32, 128),
           ('As drawn, the R253/R254 junction is the U48 output (latching feedback);\n'
            'transcribed as printed, see TRANSCRIPTION_NOTES.md.', 15, 150)],
)

# ── Ideal-diode clamp U26B and output buffer U33 -> NOT_TOTAL ──
CLAMP = child(
    'clamp', 'Set-point ceiling clamp to NOT_TOTAL (U26B, U33)', short='CLAMP', paper='A4',
    at=(110, 36), width=35.56,
    parts=[
        P('R139', '10K', 'R', at=(42, 68), rot=90, pins={'1': '5C_U34_OUT', '2': '5C_U26B_INV'},
          desc=_OVS + 'feeds the U34 set-point sum into the U26B clamp node'),
        P('U26B', 'LT1124', 'OPAMP', at=(70, 70),
          pinmap={'-': '2', '+': '3', 'out': '6', 'v+': '7', 'v-': '4'},
          pins={'2': '5C_U26B_INV', '3': '5C_U26B_NI', '6': '5C_U26B_OUT', '7': '+15V', '4': '-15V'},
          printed='U26', note=('Printed U26 LT1124 with pins 2/3 in, 6 out, 7 V+ (LT1012-style single '
                               'pinout) - conflicts with U26 pins 5/6/7 on 5C-1. V- number not printed.'),
          desc=_OVS + 'ideal-diode clamp (with CR14): holds the set point at or below the ceiling node '
                      'on its + input'),
        P('C69', '.01uF', 'C', at=(70, 44), rot=90, pins={'1': '5C_U26B_INV', '2': '5C_U26B_OUT'},
          desc=_INF + 'U26B feedback capacitor (clamp stability)'),
        P('CR14', '1N4149', 'D', at=(70, 52), rot=180, pins={'1': '5C_U26B_OUT', '2': '5C_U26B_INV'},
          note='Anode to pin 2 node, cathode to pin 6',
          desc=_OVS + 'clamp diode from the U26B - input to its output'),
        P('R162', '10K', 'R', at=(72, 36), rot=90, pins={'1': '5C_U26B_INV', '2': '5C_U33_NI'},
          desc=_OVS + 'from the clamped node to the U33 + input'),
        P('U33', 'LMC6-482', 'OPAMP', at=(125, 60),
          pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
          pins={'5': '5C_U33_NI', '6': '5C_U33_INV', '7': 'NOT_TOTAL', '8': '+15V', '4': '5C_U33_VNEG'},
          probable='LMC6482',
          note=('V- pin (number not printed) is drawn to the R162(2nd)/R187 node, not to a supply '
                'rail - transcribed as drawn'),
          desc=_OVS + 'non-inverting buffer (gain 1 + R185/R194B) driving NOT_TOTAL'),
        P('R185', '10K', 'R', at=(127, 40), rot=90, pins={'1': '5C_U33_INV', '2': 'NOT_TOTAL'},
          desc=_INF + 'U33 feedback resistor'),
        P('R194B', '200K', 'R', at=(102, 46), rot=270, pins={'1': '5C_U33_INV', '2': 'GND'},
          printed='R194', note='R194 printed twice on FIG 5C-2',
          desc=_INF + 'U33 gain resistor to ground'),
        P('R162B', '10K', 'R', at=(145, 80), rot=180, pins={'1': '5C_U33_VNEG', '2': '+15V'},
          printed='R162', note='R162 printed twice on FIG 5C-2',
          desc=_INF + 'from +15V to the U33 V- pin node (as drawn; role unknown)'),
        P('R187', '30.2', 'R', at=(123, 96), pins={'1': '5C_U33_VNEG', '2': 'GND'},
          desc=_INF + 'from the U33 V- pin node to ground (as drawn; role unknown)'),
        P('TP1', 'TP', 'TP', at=(147, 58), pins={'1': 'NOT_TOTAL'},
          desc='Patent: FIG 5C-2 test point TP1 on NOT_TOTAL'),
        P('C76B', '.1uF', 'C', at=(35, 140), pins={'1': '+15V', '2': 'GND'},
          printed='C76', note='C76 printed twice on FIG 5C-2',
          desc=_INF + 'U26B +15V supply decoupling'),
        P('C70', '.1uF', 'C', at=(48, 140), pins={'1': '-15V', '2': 'GND'},
          desc=_INF + 'U26B -15V supply decoupling'),
        P('C75', '.1uF', 'C', at=(61, 140), pins={'1': '+15V', '2': 'GND'},
          desc=_INF + 'U33 +15V supply decoupling'),
    ],
    ports=[port('5C_U34_OUT', 'input', at=(28, 68), facing='left'),
           port('5C_U26B_NI', 'input', at=(28, 80), facing='left'),
           port('NOT_TOTAL', 'output', at=(160, 60), facing='right')],
    wires=[
        ('@5C_U34_OUT', 'R139.1'), ('R139.2', 'U26B.2'),
        ('@5C_U26B_NI', 'U26B.3', [(54, 80), (54, 72)]),
        ('C69.1', 'U26B.2', [(60, 44), (60, 68)]), ('CR14.2', 'U26B.2', [(60, 52), (60, 68)]),
        ('R162.1', 'U26B.2', [(60, 36), (60, 68)]),
        ('C69.2', 'U26B.6', [(88, 44), (88, 70)]), ('CR14.1', 'U26B.6', [(88, 52), (88, 70)]),
        ('R162.2', 'U33.5', [(92, 36), (92, 62)]),
        ('R185.1', 'U33.6', [(109, 40), (109, 58)]), ('R194B.1', 'U33.6', [(109, 46), (109, 58)]),
        ('R185.2', 'U33.7', [(137, 40), (137, 60)]), ('U33.7', 'TP1.1'), ('TP1.1', '@NOT_TOTAL'),
        ('U33.4', 'R187.1'), ('R162B.1', 'R187.1', [(145, 91)]),
        ('C76B.2', 'C70.2'), ('C70.2', 'C75.2'),
    ],
    names={'5C_U26B_INV': 'R139.2', '5C_U26B_OUT': 'C69.2', '5C_U33_NI': 'R162.2', '5C_U33_INV': 'R185.1',
           # unnamed before the redraw
           '5C_U33_VNEG': None},
    notes=[('U26 / U33 DECOUPLING CAPACITORS', 25, 128)],
)

# ── Back-off counter: U28 one-shots, Q1-Q5, C71 ──
COUNTER = child(
    'counter', 'Overstroke back-off counter (U28, C71)', short='COUNT', paper='A3', at=(130, 114),
    width=35.56,
    parts=[
        P('R144', '10K', 'R', at=(44, 54), pins={'1': '+5V', '2': '5C_U28A_RC'},
          desc=_OVS + 'timing resistor of the short (count-step) one-shot, about 10 ms with C53'),
        P('C53', '2.2uF/25V', 'C', at=(46, 66), rot=90, text=(-3, 4), pins={'1': '5C_U28A_RC', '2': '5C_U28A_CX'},
          desc=_OVS + 'timing capacitor of the short (count-step) one-shot'),
        P('U28A', 'HC123', 'F5C_HC123_S1', at=(70, 70),
          pins={'15': '5C_U28A_RC', '14': '5C_U28A_CX', '1': 'GND', '2': '5C_U48_OUT',
                '3': 'SHUTO_T', '4': '5C_U28A_QN', '13': '5C_U28A_Q_STUB'},
          printed='U28', probable='74HC123 dual retriggerable monostable (X = A, O = B inputs)',
          note='Pin 13 (Q) drawn as an unterminated stub',
          desc=_OVS + 'short one-shot fired by each U48 trip; its Q-bar turns Q5 off to add one count '
                      'step to C71'),
        P('R145', '640K', 'R', at=(44, 114), pins={'1': '+5V', '2': '5C_U28B_RC'},
          desc=_OVS + 'timing resistor of the long (hold) one-shot, about 30 s with C72'),
        P('C72', '100uF/25V', 'C', at=(46, 126), rot=90, pins={'1': '5C_U28B_RC', '2': '5C_U28B_CX'},
          desc=_OVS + 'timing capacitor of the long (hold) one-shot'),
        P('U28B', 'HC123', 'F5C_HC123_S2', at=(70, 130),
          pins={'7': '5C_U28B_RC', '6': '5C_U28B_CX', '9': 'GND', '10': '5C_U48_OUT',
                '11': 'SHUTO_T', '12': '5C_U28B_QN', '3': '5C_U28B_Q_STUB'},
          printed='U28', probable='74HC123 (second section)',
          note=('Q printed as pin 3 (74HC123 2Q is pin 5; pin 3 is 1CLR) - drawn as unterminated stub. '
                'Cext pin printed "OK".'),
          desc=_OVS + 'long one-shot retriggered by each trip; holds Q1 off so C71 keeps its count'),
        P('Q5', 'INLD110', 'F5C_INLD110', at=(110, 74),
          pins={'1': '5C_U28A_QN', '4': '5C_Q4_GATE', '3': '5C_Q4_GATE', '2': 'GND'},
          probable='IRLD110',
          desc=_OVS + 'off while the short one-shot runs, letting R167 charge C71 through Q4'),
        P('R167', '64.8K', 'R', at=(118, 61), pins={'1': '+5V', '2': '5C_Q4_GATE'},
          desc=_OVS + 'sets the count-step charging current into C71'),
        P('Q4', '2N4220', 'F5C_2N4220', at=(140, 68),
          pins={'G': '5C_Q4_GATE', 'D': '5C_COUNT_CAP', 'S': '5C_COUNT_CAP', 'CASE': 'GND'},
          note='N-JFET with drain and source tied (low-leakage diode)',
          desc=_OVS + 'JFET used as a low-leakage diode: steers the count step into C71'),
        P('Q2', 'INLD110', 'F5C_INLD110', at=(110, 104),
          pins={'1': 'SHUTO_T', '4': '5C_Q3_GATE', '3': '5C_Q3_GATE', '2': 'GND'},
          probable='IRLD110 (IR logic-level N-MOSFET, 4-pin HEXDIP; printed INLD110)',
          desc=_OVS + 'off while SHUTO_T is low, letting R190/R142 reset C71 through Q3'),
        P('R190', '10K', 'R', at=(115, 91), pins={'1': '+5V', '2': '5C_Q3_GATE'},
          desc=_OVS + 'upper leg of the reset divider (with R142) for C71'),
        P('R142', '10K', 'R', at=(120, 101), pins={'1': '5C_Q3_GATE', '2': 'GND'},
          desc=_OVS + 'lower leg of the reset divider (with R190) for C71'),
        P('Q3', '2N4220', 'F5C_2N4220', at=(140, 98),
          pins={'G': '5C_Q3_GATE', 'D': '5C_COUNT_CAP', 'S': '5C_COUNT_CAP', 'CASE': 'GND'},
          note='N-JFET with drain and source tied: used as a low-leakage gate-channel diode',
          desc=_OVS + 'JFET used as a low-leakage diode: sets C71 to the reset level'),
        P('Q1', 'INLD110', 'F5C_INLD110', at=(110, 134),
          pins={'1': '5C_U28B_QN', '4': '5C_Q1_DRAIN', '3': '5C_Q1_DRAIN', '2': 'GND'},
          probable='IRLD110',
          desc=_OVS + 'on when the long one-shot times out; bleeds C71 through R130'),
        P('R130', '1M', 'R', at=(140, 126), rot=90, pins={'1': '5C_Q1_DRAIN', '2': '5C_COUNT_CAP'},
          desc=_OVS + 'bleed resistor that decays the count (about 10 s with C71)'),
        P('C71', '10uF/25V', 'CP', at=(170, 115), pins={'1': '5C_COUNT_CAP', '2': 'GND'},
          desc=_OVS + 'count capacitor: its voltage is the back-off count'),
    ],
    ports=[port('5C_U48_OUT', 'input', at=(26, 74), facing='left'),
           port('5C_COUNT_CAP', 'output', at=(190, 110), facing='right')],
    long_nets={'5C_U28A_Q_STUB', '5C_U28B_Q_STUB'},
    taps=[tap('sh', 'SHUTO_T', (72, 102), facing='right')],
    wires=[
        ('R144.2', 'U28A.15', 'vh'), ('C53.1', 'U28A.15', [(41, 62)]), ('C53.2', 'U28A.14'),
        ('R145.2', 'U28B.7', 'vh'), ('C72.1', 'U28B.7', [(41, 122)]), ('C72.2', 'U28B.6'),
        ('@5C_U48_OUT', 'U28A.2'), ('U28B.10', 'U28A.2', [(34, 134), (34, 74)]),
        ('U28B.11', '@sh'), ('@sh', 'U28A.3'), ('@sh', 'Q2.1'),
        ('U28A.4', 'Q5.1'), ('Q5.4', 'Q5.3'), ('Q5.3', 'R167.2'), ('R167.2', 'Q4.G'),
        ('Q2.4', 'Q2.3'), ('Q2.3', 'R190.2'), ('R190.2', 'R142.1'), ('R142.1', 'Q3.G'),
        ('U28B.12', 'Q1.1'), ('Q1.4', 'Q1.3'), ('Q1.3', 'R130.1'),
        ('Q4.D', 'Q4.S'), ('Q3.D', 'Q3.S'),
        ('Q4.D', 'R130.2', [(160, 66), (160, 126)]), ('Q3.D', 'R130.2', [(160, 96), (160, 126)]),
        ('C71.1', 'R130.2', [(160, 110), (160, 126)]), ('C71.1', '@5C_COUNT_CAP'),
    ],
    names={'SHUTO_T': '@sh', '5C_U28A_RC': 'U28A.15', '5C_U28A_CX': 'U28A.14',
           '5C_U28B_RC': 'U28B.7', '5C_U28B_CX': 'U28B.6', '5C_U28A_QN': 'Q5.1', '5C_U28B_QN': 'Q1.1',
           '5C_Q4_GATE': 'Q4.G', '5C_Q3_GATE': 'Q3.G', '5C_Q1_DRAIN': 'R130.1'},
    notes=[('OVERSTROKE BACK-OFF COUNTER (U28, C71)', 22, 36),
           ('OVERSTROKE BACK-OFF COUNTER (inferred, analysis/OVERSTROKE.md 2.3): each U48 trip fires U28 (pin 2 O):\n'
            'Q5 off, R167 charges C71 through Q4 (JFET diode). U28 (pin 10 O) is retriggered by each trip and holds\n'
            'Q1 off; after about R145*C72 with no trips Q1 bleeds C71 through R130. SHUTO_T low clears both one-shots\n'
            'and turns Q2 off, so R190/R142 set C71 through Q3. SHUTO_T is printed as an off-page flag; its source is\n'
            'not on the transcribed pages.', 15, 160)],
)

# ── U27: count buffer -> BACK_OFF_COUNT, and the back-off stage feeding the ceiling node ──
BUFFER = child(
    'buffer', 'Back-off count stage (U27)', short='BKOFF', paper='A4', at=(180, 114),
    width=35.56,
    parts=[
        P('R143', '1K', 'R', at=(45, 62), rot=90, pins={'1': '5C_COUNT_CAP', '2': '5C_U27A_NI'},
          desc=_OVS + 'series resistor from C71 to the U27A follower'),
        P('U27A', 'LMC6-482', 'OPAMP', at=(70, 60),
          pinmap={'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'},
          pins={'5': '5C_U27A_NI', '6': 'BACK_OFF_COUNT', '7': 'BACK_OFF_COUNT', '8': '+5VA', '4': '-5V'},
          printed='U27', probable='LMC6482', note=NOTE_SUPPLY_UNNUM + ' (V- = 4); follower (6 tied to 7)',
          desc=_OVS + 'unity follower buffering the C71 count as BACK_OFF_COUNT (to the microcontroller ADC)'),
        P('C52', '.1uF', 'C', at=(40, 140), pins={'1': '+5VA', '2': 'GND'},
          desc=_INF + 'U27 +5VA supply decoupling'),
        P('C50', '.1uF', 'C', at=(53, 140), pins={'1': '-5V', '2': 'GND'},
          desc=_INF + 'U27 -5V supply decoupling'),
        P('R141', '51.1K', 'R', at=(100, 75), pins={'1': 'BACK_OFF_COUNT', '2': '5C_U27B_INV'},
          desc=_OVS + 'input resistor from BACK_OFF_COUNT to the U27B - input'),
        P('U27B', 'LMC6-482', 'OPAMP', at=(120, 100), pinmap={'-': '2', '+': '3', 'out': '1'},
          pins={'2': '5C_U27B_INV', '3': '5C_U27B_NI', '1': '5C_U27B_OUT'}, printed='U27', probable='LMC6482',
          desc=_OVS + 'back-off stage: lowers the ceiling node as the count rises; no feedback part is '
                      'drawn, so as printed it is an open-loop comparator'),
        P('R165', '50K', 'R', at=(92, 98), rot=270, pins={'1': '5C_U27B_INV', '2': '5C_R197_3'},
          desc=_OVS + 'offset resistor from the R197 pot (-10V) to the U27B - input'),
        P('R197', '200K', 'POT', at=(72, 98), rot=90, pins={'3': '5C_R197_3', '2': '-10V', '1': '-10V'},
          note='Wiper (2) tied to pin 1, to -10V',
          desc=_OVS + 'adjusts the U27B offset (back-off threshold), wired as a variable resistor to -10V'),
        P('R166', '4.01K', 'R', at=(101, 110), pins={'1': '5C_U27B_NI', '2': 'GND'},
          desc=_INF + 'U27B + input resistor to ground'),
        P('R163', 'XXX', 'R', at=(150, 100), rot=270, pins={'1': '5C_U26B_NI', '2': '5C_U27B_OUT'},
          note='Value printed as XXX (not specified)',
          desc=_OVS + 'from the U27B output to the ceiling node at the U26B + input (value printed XXX)'),
    ],
    ports=[port('5C_COUNT_CAP', 'input', at=(28, 62), facing='left'),
           port('BACK_OFF_COUNT', 'output', at=(160, 60), facing='right'),
           port('5C_U26B_NI', 'output', at=(170, 100), facing='right')],
    wires=[
        ('@5C_COUNT_CAP', 'R143.1'), ('R143.2', 'U27A.5'),
        ('U27A.6', 'U27A.7', [(58, 58), (58, 40), (84, 40), (84, 60)]),
        ('U27A.7', '@BACK_OFF_COUNT'), ('R141.1', 'U27A.7', 'vh'),
        ('R141.2', 'U27B.2', [(100, 98)]), ('R165.1', 'U27B.2'),
        ('R197.3', 'R165.2'), ('R197.2', 'R197.1', [(67, 93)]),
        ('R166.1', 'U27B.3', 'vh'), ('U27B.1', 'R163.2'), ('R163.1', '@5C_U26B_NI'),
        ('C52.2', 'C50.2'),
    ],
    names={'5C_U27A_NI': 'R143.2', '5C_U27B_INV': 'U27B.2', '5C_U27B_NI': 'U27B.3', '5C_U27B_OUT': 'R163.2',
           '5C_R197_3': 'R165.2', '-10V': 'R197.2'},
    notes=[('U27 DECOUPLING CAPACITORS', 32, 128)],
)

CHILDREN = [SUM, CMT, HOG, TRIP, CLAMP, COUNTER, BUFFER]

# ── Figure page: the child blocks and how they connect ──
PAGE_WIRES = [
    ('@OF_SET', 'sum:OF_SET'),
    ('sum:5C_U34_OUT', 'clamp:5C_U34_OUT'),
    ('cmt:5C_U26B_NI', 'clamp:5C_U26B_NI', [(85, 74), (85, 44)]),
    ('clamp:NOT_TOTAL', '@NOT_TOTAL'),
    ('hog:5C_U53B_OUT', 'trip:5C_U53B_OUT'),
    ('trip:5C_U48_OUT', 'counter:5C_U48_OUT'),
    ('counter:5C_COUNT_CAP', 'buffer:5C_COUNT_CAP'),
    ('buffer:BACK_OFF_COUNT', '@BACK_OFF_COUNT'),
]
PORTS = [
    port('OF_SET', 'input', at=(20, 40), facing='left'),
    port('NOT_TOTAL', 'output', at=(155, 40), facing='right'),
    port('BACK_OFF_COUNT', 'output', at=(225, 118), facing='right'),
]
# the back-off stage drives the ceiling node from the far side of the page: a label at each end
PAGE_LONG_NETS = {'5C_U26B_NI'}

NOTES = [('Set point: SUM -> CLAMP (limited by the ceiling node from CMT and BACK-OFF) -> NOT_TOTAL.\n'
          'Overstroke: HOG -> TRIP -> COUNTER -> BACK-OFF (BACK_OFF_COUNT, and the ceiling node).\n'
          'Signal roles are inferred (analysis/OVERSTROKE.md 2.3); the patent text does not describe FIG 5C.',
          15, 140)]

NET_DESCRIPTIONS = {
    'OF_SET': 'Patent: FIG 5C-1 off-page flag OF_SET, from FIG 5B (U54 buffer). Inferred from the circuit: '
              'offset set point into U46',
    'NOT_TOTAL': 'Patent: FIG 5C-2 off-page flag NOT_TOTAL (joined to HOT TOTAL on 5E and HOT-TOTAL on 5G, '
                 'an inference). Inferred: the clamped drive command from U33, to the UX1 pot reference (5E) '
                 'and U22 PE4/AN4 (5G)',
    'BACK_OFF_COUNT': 'Patent: FIG 5C-2 off-page flag BACK_OFF_COUNT, to U22 PE3/AN3 on FIG 5G. Inferred: '
                      'buffered C71 count voltage',
    '5C_U34_OUT': 'Inferred from the circuit: U34 set-point sum, into the U26B clamp through R139',
    '5C_U26B_NI': 'Inferred from the circuit (analysis/OVERSTROKE.md 2.3): ceiling node at the U26B + input, '
                  'driven by the CMT rectifier (R140) and the back-off stage (R163)',
    '5C_U53B_OUT': 'Inferred from the circuit: amplified HOG_T signal from U53B (TPX1) to the U48 trip comparator',
    '5C_U48_OUT': 'Inferred from the circuit: U48 trip output (pulled up to +5VA), triggers both U28 one-shots',
    '5C_COUNT_CAP': 'Inferred from the circuit: C71 count voltage, to the U27A buffer',
    'WP.SHOSET': 'Patent: FIG 5C-1 off-page flag WP.SHOSET; no transcribed figure uses it. Summed into U34 '
                 'through R192',
    'WP.SHTR': 'Patent: FIG 5C-1 off-page flag WP.SHTR; no transcribed figure uses it. Summed into U34 '
               'through R189',
    'OF_CTAL': 'Patent: FIG 5C-1 off-page flag OF_CTAL; no transcribed figure uses it. Summed into U34 '
               'through R195',
    'OFT_TE': 'Patent: FIG 5C-1 off-page flag OFT_TE; no transcribed figure uses it. Into U34 through the '
              'R199/C105/C104 network',
    '5C_R191_ARROW': 'Patent: FIG 5C-2 draws R191 to an unlabeled arrow; destination unknown',
    '5C_U46_INV': 'Inferred from the circuit: U46 inverting input (+5VA through R299, feedback R298)',
    '5C_U46_NI': 'Inferred from the circuit: U46 non-inverting input (OF_SET through R210)',
    '5C_U46_OUT': 'Inferred from the circuit: U46 output, summed into U34 through R193',
    '5C_SUM': 'Inferred from the circuit: U34 summing junction (inverting input)',
    '5C_OFT_LL': 'Inferred from the circuit: OFT_TE network output into R199B',
    '5C_U34_NI': 'Inferred from the circuit: U34 non-inverting input, grounded through R194',
    'CMTO_T': 'Patent: FIG 5C-1 off-page flag CMTO_T; no transcribed figure uses it. U11 input through R92',
    'CMT_T': 'Patent: FIG 5C-1 off-page flag CMT_T; no transcribed figure uses it. U11 output, to the U26A '
             'rectifier',
    '5C_U11_INV': 'Inferred from the circuit: U11 inverting input (R91, R92, feedback R82/C35)',
    '5C_U11_NI': 'Inferred from the circuit: U11 non-inverting input, grounded through R93',
    '5C_R126_ARROW': 'Patent: FIG 5C-1 draws R126 to an unlabeled downward arrow; source unknown',
    '5C_U26A_INV': 'Inferred from the circuit: U26A rectifier summing node (R127, R126, R128, C49, CR10)',
    '5C_U26A_NI': 'Inferred from the circuit: U26A non-inverting input, grounded through R129',
    '5C_U26A_OUT': 'Inferred from the circuit: U26A output, before the CR11 rectifier diode',
    '5C_CMT_RECT': 'Inferred from the circuit: rectified CMT_T after CR11, to R140',
    'HOG_T': 'Patent: FIG 5C-1 off-page flag HOG_T. [assumption] overstroke (knock) sensor signal; into U53A '
             'through R285',
    'HOG_TR': 'Patent: FIG 5C-1 off-page flag HOG_TR; returned to GND through R286',
    '5C_HOG_IN': 'Inferred from the circuit: HOG_T input node after R285 (C150, C155)',
    '5C_U53A_INV': 'Inferred from the circuit: U53A inverting input (C150, feedback R266)',
    '5C_U53A_NI': 'Inferred from the circuit: U53A non-inverting input, biased through R267',
    '5C_U53A_OUT': 'Inferred from the circuit: U53A output, AC-coupled to U53B through C155B',
    '5C_U53B_NI': 'Inferred from the circuit: U53B non-inverting input after C155B (R232 to ground)',
    '5C_U53B_INV': 'Inferred from the circuit: U53B inverting input (thermistor network R281/R282/RT1, '
                   'R284, C167)',
    '5C_RT1_TOP': 'Inferred from the circuit: junction of RT1, R282 and R283 in the U53B feedback',
    '5C_U48_NI': 'Inferred from the circuit: U48 + input (TP4, C141B, R254 feedback)',
    '5C_U48_INV': 'Inferred from the circuit: U48 - input, the trip threshold (TP5; R255, R256, R285B)',
    '5C_U48_BAL': 'Inferred from the circuit: U48 balance pin 5, to C126',
    '5C_U48_STB': 'Inferred from the circuit: U48 balance/strobe pin 6, to C126',
    '5C_U26B_INV': 'Inferred from the circuit (analysis/OVERSTROKE.md 2.3): clamped set-point node at the '
                   'U26B - input, to U33 through R162',
    '5C_U26B_OUT': 'Inferred from the circuit: U26B output, to the CR14 clamp diode and C69',
    '5C_U33_NI': 'Inferred from the circuit: U33 + input, the clamped set point through R162',
    '5C_U33_INV': 'Inferred from the circuit: U33 - input (R185 feedback, R194B to ground)',
    'SHUTO_T': 'Patent: FIG 5C-2 off-page flag SHUTO_T; its source is not on the transcribed pages. '
               'Inferred: low clears both U28 one-shots and turns Q2 off (C71 reset)',
    '5C_U28A_RC': 'Inferred from the circuit: U28A timing node (R144, C53)',
    '5C_U28A_CX': 'Inferred from the circuit: U28A Cext pin, to C53',
    '5C_U28A_QN': 'Inferred from the circuit: U28A Q-bar, drives the Q5 gate',
    '5C_U28A_Q_STUB': 'Patent: FIG 5C-2 draws U28 pin 13 (Q) as an unterminated stub',
    '5C_U28B_RC': 'Inferred from the circuit: U28B timing node (R145, C72)',
    '5C_U28B_CX': 'Inferred from the circuit: U28B Cext pin (printed "OK"), to C72',
    '5C_U28B_QN': 'Inferred from the circuit: U28B Q-bar, drives the Q1 gate',
    '5C_U28B_Q_STUB': 'Patent: FIG 5C-2 draws the second U28 Q (printed pin 3) as an unterminated stub',
    '5C_Q4_GATE': 'Inferred from the circuit: Q5 drain / R167 node, the Q4 gate (count-step current)',
    '5C_Q3_GATE': 'Inferred from the circuit: Q2 drain / R190-R142 divider, the Q3 gate (reset level)',
    '5C_Q1_DRAIN': 'Inferred from the circuit: Q1 drain, to the R130 bleed resistor',
    '5C_U27A_NI': 'Inferred from the circuit: U27A + input, C71 through R143',
    '5C_U27B_INV': 'Inferred from the circuit: U27B - input (BACK_OFF_COUNT through R141, offset through R165)',
    '5C_U27B_NI': 'Inferred from the circuit: U27B + input, grounded through R166',
    '5C_U27B_OUT': 'Inferred from the circuit: U27B output, to the ceiling node through R163',
    '5C_R197_3': 'Inferred from the circuit: R197 pot end, the offset into R165',
}
