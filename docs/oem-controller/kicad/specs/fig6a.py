"""FIG 6A - daughter board sensor input channels J1..J7 (LTC1150 V1..V7) + LT1007 ref buffers V15/V16."""

from oemsch import P

TITLE = 'FIG 6A - Sensor input amplifiers J1-J7 (LTC1150) and REF buffers'
SOURCE = 'US6098409 sheets 21-22 of 25 (PDF p22-23), FIG 6A-1/6A-2'
PAPER = 'A2'

# LTC1150 as drawn: 2 (-), 3 (+), 8 (output used for feedback), 6 (second
# output to the CBY_1 bus), 7 V+, 4 V-. Pin 5 is drawn as a bare unconnected stub
# and is left out of the symbol (see NOTES).
SYMBOLS = {
    'F6A_LTC1150': {
        'left': [('2', '-'), None, ('3', '+')],
        'right': [('8', 'P8'), None, ('6', 'P6')],
        'top': [('7', 'V+')],
        'bottom': [('4', 'V-')],
        'prefix': 'V',
    },
    'F6A_CONN4': {
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
    sig, ni, inv = f'6A_{tag}_SIG', f'6A_{v[0]}_IN+', f'6A_{v[0]}_IN-'

    def part(spec, kind, at, rot, pins, **extra):
        ref, value = spec[0], spec[1]
        printed = spec[2] if len(spec) > 2 else None
        note = spec[3] if len(spec) > 3 else None
        PARTS.append(P(ref, value, kind, at=at, rot=rot, pins=pins, printed=printed,
                       note=note, **extra))

    part(conn, 'F6A_CONN4', (ox + 8, oy + 40), 0,
         {'1': 'GND', '2': 'POLARIZING_KEY', '3': 'GND', '4': sig})
    part(r_ref, 'R', (ox + 40, oy + 22), 0, {'1': ref_net, '2': sig})
    part(r_inv, 'R', (ox + 62, oy + 34), 90, {'1': 'GND', '2': inv})
    part(r_ni, 'R', (ox + 62, oy + 50), 90, {'1': sig, '2': ni})
    part(c_sig, 'C', (ox + 46, oy + 58), 0, {'1': sig, '2': 'GND'})
    part(c_ni, 'C', (ox + 80, oy + 58), 0, {'1': ni, '2': 'GND'})
    part(r_fbref, 'R', (ox + 100, oy + 4), 90, {'1': inv, '2': ref_net})
    part(c_fb, 'C', (ox + 100, oy + 12), 90, {'1': inv, '2': 'CBY_1'})
    part(r_fb, 'R', (ox + 100, oy + 20), 90, {'1': inv, '2': 'CBY_1'})
    part(v, 'F6A_LTC1150', (ox + 108, oy + 42), 0,
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
    in_net = f'6A_{v[0]}_IN+'
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


# ── FIG 6A-1 (left half) ──
REF_A1 = '6A1_V15_OUT'   # V15 output node; no name printed on 6A-1
channel(14, 26, ('J1', 'CONN_4'), ('V1', 'LTC1150'),
        ('R54', '7.07K'), ('R2', '10K'), ('R5', '10K'), ('C3', '.1uF'), ('C4', '.1uF'),
        ('R4', '37.4K'), ('C1', '.1uF'), ('R3', '37.4K'),
        ('C2', '.1uF'), ('C5', '.1uF'), REF_A1)
channel(14, 98, ('J2', 'CONN_4'), ('V2', 'LTC1150'),
        ('R6', '7.07K'), ('R7', '10K'), ('R10', '10K'), ('C8', '.1uF'), ('C9', '.1uF'),
        ('R9', '37.4K'), ('C6', '.1uF'), ('R8', '37.4K'),
        ('C2B', '.1uF', 'C2', 'C2 printed again (V2 +12V decoupling); also on V1 and V3'),
        ('C10', '.1uF'), REF_A1)
channel(14, 170, ('J3', 'CONN_4'), ('V3', 'LTC1150'),
        ('R11', '7.07K'), ('R12', '10K'),
        ('R13B', '10K', 'R13', 'R13 printed twice in this channel (37.4K feedback and 10K + input)'),
        ('C14', '.1uF'), ('C15', '.1uF'),
        ('R14', '37.4K'), ('C12', '.1uF'), ('R13', '37.4K'),
        ('C2C', '.1uF', 'C2', 'C2 printed again (V3 +12V decoupling)'),
        ('C16', '.1uF'), REF_A1)
channel(14, 242, ('J4', 'CONN_4'), ('V4', 'LTC1150'),
        ('R17', '7.07K'), ('R18', '10K'), ('R21', '10K'), ('C21', '.1uF'), ('C22', '.1uF'),
        ('R20', '37.4K'), ('C19', '.1uF'), ('R19', '37.4K'),
        ('C19B', '.1uF', 'C19', 'C19 printed twice in this channel (feedback cap and +12V decoupling)'),
        ('C23', '.1uF'), REF_A1)
ref_buffer(176, 228, ('V15', 'LT1007'), ('R16', '10K'), ('C20', '.1uF'),
           ('C11', '.1uF'), ('C17', '.1uF'), REF_A1)

# ── FIG 6A-2 (right half) ──
channel(236, 26, ('J5', 'CONN_4'), ('V5', 'LTC1150'),
        ('R22', '7.07K'), ('R23', '10K'), ('R27', '10K'), ('C27', '.1uF'), ('C28', '.1uF'),
        ('R25', '37.4K'), ('C25', '.1uF'), ('R24', '37.4K'),
        ('C26', '.1uF'), ('C29', '.1uF'), 'REF_2')
channel(236, 98, ('J6', 'CONN_4'), ('V6', 'LTC1150'),
        ('R28', '7.07K'), ('R29', '10K'), ('R32', '10K'), ('C34', '.1uF'), ('C35', '.1uF'),
        ('R31', '37.4K'), ('C32', '.1uF'), ('R30', '37.4K'),
        ('C33', '.1uF'), ('C37', '.1uF'), 'REF_2')
channel(236, 170, ('J7', 'CONN_4'), ('V7', 'LTC1150'),
        ('R34', '7.07K'), ('R36', '10K'), ('R35', '10K'), ('C40', '.1uF'), ('C41', '.1uF'),
        ('R33', '37.4K'), ('C30', '.1uF'), ('R37', '37.4K'),
        ('C39', '.1uF'), ('C44', '.1uF'), 'REF_2')
ref_buffer(398, 228, ('V16', 'LT1007'),
           ('R25B', '10K', 'R25', 'R25 printed twice on 6A-2 (37.4K in J5 channel and this 10K)'),
           ('C31', '.1uF'), ('C24', '.1uF'),
           ('C30B', '.1uF', 'C30', 'C30 printed twice on 6A-2 (J7 feedback cap and this -15V cap)'),
           'REF_2')

NOTES = [
    ('FIG 6A-1 (left)  |  FIG 6A-2 (right)', 200, 22),
    ('Every LTC1150 pin 8 and the common pin-6 bus end in off-page connectors that\n'
     'are ALL printed "CBY_1" (6A-1 and 6A-2) - drawn as one net here, as printed.\n'
     'Probable drafting error (each channel output presumably had its own name).', 236, 262),
    ('J pin 2 is printed "POLARIZING_KEY" (keyed position) on every channel.\n'
     'J pin 3 is drawn tied to GND on every channel.\n'
     'LTC1150 pin 5 is drawn as an unconnected stub on every channel.', 236, 280),
    ('6A1_V15_OUT: V15 output node - no signal name printed on 6A-1.\n'
     'On 6A-2 the same node of V16 leaves the page as REF_2.', 236, 298),
    ('Supplies printed lower-case: +12v, -12v, +15v, -15v.', 236, 312),
]
