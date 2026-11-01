"""FIG 6B - daughter board sensor input channels J8..J14 (LTC1150 V8..V14) + LT1007 ref buffers V17/V18."""

from oemsch import P

TITLE = 'FIG 6B - Sensor input amplifiers J8-J14 (LTC1150) and REF buffers'
SOURCE = 'US6098409 sheets 23-24 of 25 (PDF p24-25), FIG 6B-1/6B-2'
PAPER = 'A2'

# LTC1150 as drawn: 2 (-), 3 (+), 8 (output used for feedback), 6 (second
# output to the CBY_1 bus), 7 V+, 4 V-. Pin 5 is drawn as a bare unconnected stub
# and is left out of the symbol (see NOTES).
SYMBOLS = {
    'F6B_LTC1150': {
        'left': [('2', '-'), None, ('3', '+')],
        'right': [('8', 'P8'), None, ('6', 'P6')],
        'top': [('7', 'V+')],
        'bottom': [('4', 'V-')],
        'prefix': 'V',
    },
    'F6B_CONN4': {
        'right': [('1', '1'), None, ('2', '2'), None, ('3', '3'), None, ('4', '4')],
        'prefix': 'J',
    },
}

LT1007 = {'-': '2', '+': '3', 'out': '8', 'v+': '7', 'v-': '4'}
PARTS = []
WIRES = []


def channel(ox, oy, conn, v, r_ref, r_inv, r_ni, c_sig, c_ni, r_fbref, c_fb, r_fb,
            c_vp, c_vn, ref_net):
    """
    One sensor channel exactly as drawn (each argument = (ref, value[, printed[, note]])).

    @param ox, oy   Top-left of the channel block (cells).
    @param conn     Connector J (pin1 GND, pin2 POLARIZING_KEY, pin3 GND, pin4 signal).
    @param v        LTC1150.
    @param r_ref    7.07K from the J pin-4 node up to the reference node.
    @param r_inv    10K from J pin 3 (grounded) to the - input (pin 2).
    @param r_ni     10K from the J pin-4 node to the + input (pin 3).
    @param c_sig    .1uF from the J pin-4 node to GND.
    @param c_ni     .1uF from the + input to GND.
    @param r_fbref  37.4K from the - input to the reference node.
    @param c_fb     .1uF from the - input to pin 8.
    @param r_fb     37.4K from the - input to pin 8.
    @param c_vp     .1uF +12V decoupling.
    @param c_vn     .1uF -12V decoupling.
    @param ref_net  Net of the LT1007 buffer output feeding r_ref / r_fbref.
    @returns None (appends to PARTS / WIRES).
    """
    tag = conn[0]
    sig, ni, inv = f'6B_{tag}_SIG', f'6B_{v[0]}_IN+', f'6B_{v[0]}_IN-'

    def part(spec, kind, at, rot, pins, **extra):
        ref, value = spec[0], spec[1]
        printed = spec[2] if len(spec) > 2 else None
        note = spec[3] if len(spec) > 3 else None
        PARTS.append(P(ref, value, kind, at=at, rot=rot, pins=pins, printed=printed,
                       note=note, **extra))

    part(conn, 'F6B_CONN4', (ox + 8, oy + 40), 0,
         {'1': 'GND', '2': 'POLARIZING_KEY', '3': 'GND', '4': sig})
    part(r_ref, 'R', (ox + 40, oy + 22), 0, {'1': ref_net, '2': sig})
    part(r_inv, 'R', (ox + 62, oy + 34), 90, {'1': 'GND', '2': inv})
    part(r_ni, 'R', (ox + 62, oy + 50), 90, {'1': sig, '2': ni})
    part(c_sig, 'C', (ox + 46, oy + 58), 0, {'1': sig, '2': 'GND'})
    part(c_ni, 'C', (ox + 80, oy + 58), 0, {'1': ni, '2': 'GND'})
    part(r_fbref, 'R', (ox + 100, oy + 4), 90, {'1': inv, '2': ref_net})
    part(c_fb, 'C', (ox + 100, oy + 12), 90, {'1': inv, '2': 'CBY_1'})
    part(r_fb, 'R', (ox + 100, oy + 20), 90, {'1': inv, '2': 'CBY_1'})
    part(v, 'F6B_LTC1150', (ox + 108, oy + 42), 0,
         {'2': inv, '3': ni, '8': 'CBY_1', '6': 'CBY_1', '7': '+12V', '4': '-12V'})
    part(c_vp, 'C', (ox + 136, oy + 30), 0, {'1': '+12V', '2': 'GND'})
    part(c_vn, 'C', (ox + 136, oy + 58), 0, {'1': '-12V', '2': 'GND'})
    WIRES.extend([
        (f'{c_fb[0]}.1', f'{r_fb[0]}.1', 'vh'),
        (f'{c_fb[0]}.2', f'{r_fb[0]}.2', 'vh'),
        (f'{c_sig[0]}.1', f'{r_ni[0]}.1', 'vh'),
        (f'{c_ni[0]}.1', f'{r_ni[0]}.2', 'vh'),
    ])


def ref_buffer(ox, oy, v, r_in, c_in, c_vp, c_vn, out_net):
    """LT1007 follower: REF_1 -> 10K -> pin 3 (+ .1uF to GND), pins 2 and 8 tied = out_net."""
    in_net = f'6B_{v[0]}_IN+'
    PARTS.extend([
        P(v[0], v[1], 'OPAMP', at=(ox + 20, oy + 20), pinmap=LT1007,
          pins={'2': out_net, '8': out_net, '3': in_net, '7': '+15V', '4': '-15V'},
          note='LT1007 output drawn on pin 8 (pin 2 looped to pin 8 = follower)'),
        P(r_in[0], r_in[1], 'R', at=(ox + 2, oy + 30), rot=90, pins={'1': 'REF_1', '2': in_net},
          printed=r_in[2] if len(r_in) > 2 else None,
          note=r_in[3] if len(r_in) > 3 else None),
        P(c_in[0], c_in[1], 'C', at=(ox - 8, oy + 38), pins={'1': 'REF_1', '2': 'GND'}),
        P(c_vp[0], c_vp[1], 'C', at=(ox + 34, oy + 8), pins={'1': '+15V', '2': 'GND'}),
        P(c_vn[0], c_vn[1], 'C', at=(ox + 34, oy + 34), pins={'1': '-15V', '2': 'GND'},
          printed=c_vn[2] if len(c_vn) > 2 else None,
          note=c_vn[3] if len(c_vn) > 3 else None),
    ])
    WIRES.append((f'{r_in[0]}.1', f'{c_in[0]}.1', 'vh'))


# ── FIG 6B-1 (left half) ──
# V17 output and V18 output are drawn joined: the V17 node leaves 6B-1 along the top
# edge, enters 6B-2 annotated "REF_3", and ties to R64/R67 and the V18 output node,
# which leaves the page as REF_4. One conductor, two printed names -> net REF_4.
REF_B = 'REF_4'
# J8: the R39 / R42 node is drawn to an off-page connector printed CBY_1 (the line
# crosses the V17 bus without a junction) instead of the reference bus.
channel(14, 26, ('J8', 'CONN_4'), ('V8', 'LTC1150'),
        ('R39', '7.07K', None, 'Top end drawn to the CBY_1 connector, not to the V17 bus'),
        ('R40', '10K'), ('R43', '10K'), ('C47', '.1uF'), ('C49', '.1uF'),
        ('R42', '37.4K', None, 'Right end drawn to the CBY_1 connector, not to the V17 bus'),
        ('C45', '.1uF'), ('R41', '37.4K'),
        ('C46', '.1uF'), ('C50', '.1uF'), 'CBY_1')
channel(14, 98, ('J9', 'CONN_4'), ('V9', 'LTC1150'),
        ('R45', '7.07K'), ('R47', '10K'), ('R46', '10K'), ('C53', '.1uF'), ('C54', '.1uF'),
        ('R44', '37.4K'), ('C51', '.1uF'),
        ('R43B', '37.4K', 'R43', 'R43 printed twice on 6B-1 (10K in J8 channel and this 37.4K)'),
        ('C52', '.1uF'), ('C57', '.1uF'), REF_B)
channel(14, 170, ('J10', 'CONN_4'), ('V10', 'LTC1150'),
        ('R50', '7.07K'), ('R51', '10K'), ('R54', '10K'), ('C61', '.1uF'), ('C62', '.1uF'),
        ('R53', '37.4K'),
        ('C50B', '.1uF', 'C50', 'C50 printed twice on 6B-1 (J8 -12V cap and this feedback cap)'),
        ('R52', '37.4K'),
        ('C59', '.1uF'), ('C63', '.1uF'), REF_B)
channel(14, 242, ('J11', 'CONN_4'), ('V11', 'LTC1150'),
        ('R56', '7.07K'), ('R57', '10K'), ('R62', '10K'), ('C68', '.1uF'), ('C69', '.1uF'),
        ('R61', '37.4K'), ('C66', '.1uF'), ('R58', '37.4K'),
        ('C67', '.1uF'), ('C70', '.1uF'), REF_B)
ref_buffer(176, 228, ('V17', 'LT1007'), ('R38', '10K'), ('C43', '.1uF'),
           ('C36', '.1uF'), ('C42', '.1uF'), REF_B)

# ── FIG 6B-2 (right half) ──
channel(236, 26, ('J12', 'CONN_4'), ('V12', 'LTC1150'),
        ('R64', '7.07K'), ('R65', '10K'), ('R60', '10K'), ('C75', '.1uF'), ('C76', '.1uF'),
        ('R67', '37.4K'), ('C72', '.1uF'), ('R66', '37.4K'),
        ('C73', '.1uF'), ('C78', '.1uF'), REF_B)
channel(236, 98, ('J13', 'CONN_4'), ('V13', 'LTC1150'),
        ('R70', '7.07K'), ('R71', '10K'), ('R76', '10K'), ('C82', '.1uF'), ('C83', '.1uF'),
        ('R75', '37.4K'), ('C79', '.1uF'), ('R72', '37.4K'),
        ('C80', '.1uF'), ('C84', '.1uF'), REF_B)
channel(236, 170, ('J14', 'CONN_4'), ('V14', 'LTC1150'),
        ('R77', '7.07K'), ('R78', '10K'), ('R82', '10K'), ('C88', '.1uF'), ('C89', '.1uF'),
        ('R81', '37.4K'), ('C96', '.1uF'), ('R79', '37.4K'),
        ('C87', '.1uF'), ('C90', '.1uF'), REF_B)
ref_buffer(398, 228, ('V18', 'LT1007'), ('R49', '10K'), ('C56', '.1uF'),
           ('C49B', '.1uF', 'C49', 'C49 printed twice (J8 + input cap on 6B-1 and this +15V cap on 6B-2)'),
           ('C55', '.1uF'), REF_B)

NOTES = [
    ('FIG 6B-1 (left)  |  FIG 6B-2 (right)', 200, 22),
    ('Every LTC1150 pin 8 and the common pin-6 bus end in off-page connectors that\n'
     'are ALL printed "CBY_1" - drawn as one net here, as printed (probable drafting error).\n'
     'J8: R39/R42 reference node also drawn to a CBY_1 connector (crosses the V17 line, no junction).', 236, 258),
    ('REF_4 = V17 out + V18 out: the V17 output line runs off the top of 6B-1 into 6B-2,\n'
     'where it is annotated "REF_3", feeds R64/R67 and joins the V18 output (label REF_4).\n'
     'Two LT1007 outputs drawn shorted; printed name REF_3 is on this same conductor.', 236, 276),
    ('J pin 2 printed "POLARIZING_KEY"; J pin 3 drawn tied to GND; LTC1150 pin 5 drawn as\n'
     'an unconnected stub (omitted). J10 here is a sensor input; FIG 6C reuses J10 (26-pin).', 236, 294),
    ('Supplies printed lower-case: +12v, -12v, +15v, -15v.', 236, 312),
]
