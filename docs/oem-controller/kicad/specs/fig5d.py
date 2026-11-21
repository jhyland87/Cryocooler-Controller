"""FIG 5D - six butter warmer (heater drive) circuits, FIG 5D-1/5D-2/5D-3.

Redrawn to the drawing rules: one child sheet per circuit, all six drawn by bw_child() with
the same layout. They are six sheet files, not one file placed six times: the copies differ
in printed values (CR13/CR17/CR19 1N4140) and notes, which KiCad cannot vary per placement
(user, 2026-11-21). The patent text does not describe FIG 5D; descriptions cite the figure
and mark the rest as inferred.
"""

from oemsch import P, child, port, tap

TITLE = 'FIG 5D - Butter warmer circuits #1-#6'
SOURCE = 'US6098409 sheets 8-10 of 25 (PDF p9-11), FIG 5D-1/5D-2/5D-3'
PAPER = 'A3'
REDRAWN = True

_INF = 'Inferred from the circuit: '
NSP = ('NSP = non-volatile set point (service manual SF p.66); the link to these parts is inferred')

# MC2030 dual serial pot, pins as printed (the GND pin has no printed number: 'G').
# Drawn by function: the serial lines (in and out) left, each pot's RI / WP / RF ends right.
SYMBOLS = {
    'F5D_MC2030': {
        'left': [('15', 'PROG'), None, ('14', 'READ'), None, ('1', 'SER.CLK'), None, ('2', 'SER.IN'),
                 None, ('3', 'SER.OUT')],
        'right': [('13', 'RIA'), None, ('10', 'WPA'), None, ('9', 'RFA'), None, None, None,
                  ('4', 'RIB'), None, ('6', 'WFB'), None, ('7', 'RFB')],
        'top': [('16', 'VDD')],
        'bottom': [('G', 'GND')],
        'prefix': 'U',
    },
}

OPAMP_P = {'-': '6', '+': '5', 'out': '7', 'v+': '8', 'v-': '4'}
OPAMP_R = {'-': '2', '+': '3', 'out': '1'}

# Each circuit transcribed separately from its drawing. Keys:
#   ref -> (ref, printed, value[, note]); nets in/out exactly as printed.
CIRCUITS = [
    # ── FIG 5D-1 top: BUTTER WARMER CIRCUIT #1 ──
    dict(num=1, cell=(0, 0), sheet='5D-1',
         pot='V9', opamp='V10', ser_in='NSP_SERI', ser_out='5D_SER_V9_V7',
         p_in='BWT_1P', p_out='BWT_1P', r_in='BWT_1R', r_out='BWH_1R',
         c_vdd=('C24', '.1uF'), c_5va=('C27', '.1uF'), c_pot=('C16', '.1uF'),
         r_wpa=('R11', '150K'), c_plus=('C5', '.1uF'), r_plus=('R95', '7.07K'),
         r_in_p=('R14', '20K'), r_up_p=('R16', '10K'), r_dn_p=('R13', '2.67K'),
         r_fb1_p=('R12', '1K'), r_fb2_p=('R9', '1K'), r_out_p=('R10', '33K'),
         d_p=('CR4', '1N4148'), c_neg=('C17', '.1uF'),
         r_wfb=('R78', '150K'), r_in_r=('R81', '10K'), r_up_r=('R83', '10K'),
         r_dn_r=('R90', '2.67K'), r_fb1_r=('R79', '1K'), r_fb2_r=('R76', '1K'),
         r_out_r=('R77', '33K'), d_r=('CR7', '1N4148'), c_rplus=('C28', '.1uF'),
         r_rplus=('R82', '7.07K'),
         notes={'C28': 'Value printed ".1vF"',
                'CR4': 'Anode connector printed BWT_1P (same name as the input; BWH_1P expected)'}),
    # ── FIG 5D-1 bottom: BUTTER WARMER CIRCUIT #4 ──
    dict(num=4, cell=(0, 1), sheet='5D-1',
         pot='V24', opamp='V25', ser_in='NSP_SERI', ser_out='5D_SER_V24_V39',
         p_in='BWH_4P', p_out='BWH_4P', r_in='BWT_4R', r_out='BWH_4R',
         c_vdd=('C46', '.1uF'), c_5va=('C67', '.1uF'), c_pot=('C57', '.1uF'),
         r_wpa=('R120', '150K'), c_plus=('C47', '.1uF'), r_plus=('R124', '7.07K'),
         r_in_p=('R123', '20K'), r_up_p=('R125', '10K'), r_dn_p=('R122', '2.67K'),
         r_fb1_p=('R121', '1K'), r_fb2_p=('R118', '1K'), r_out_p=('R119', '33K'),
         d_p=('CR9', '1N4148'), c_neg=('C59', '.1uF'),
         r_wfb=('R78B', '150K'), r_in_r=('R16B', '10K'), r_up_r=('R161', '10K'),
         r_dn_r=('R158', '2.67K'), r_fb1_r=('R157', '1K'), r_fb2_r=('R154', '1K'),
         r_out_r=('R155', '33K'), d_r=('CR13', '1N4140'), c_rplus=('C68', '.1uF'),
         r_rplus=('R160', '7.07K'),
         notes={'C46': 'Value printed ".1vF"', 'C59': 'Value printed ".1vF"',
                'R78B': 'R78 printed again (also circuits #1 and #2)',
                'R16B': 'R16 printed again (also circuit #1, 10K pull-up)',
                'R123': 'Input connector printed BWH_4P (same name as the output; BWT_4P expected)',
                'CR13': 'Printed 1N4140 (other circuits 1N4148)'}),
    # ── FIG 5D-2 top: BUTTER WARMER CIRCUIT #2 ──
    dict(num=2, cell=(1, 0), sheet='5D-2',
         pot='V7', opamp='V8', ser_in='5D_SER_V9_V7', ser_out='5D_SER_V7_V22',
         p_in='BWT_2P', p_out='BWH_2P', r_in='BWT_2R', r_out='BWH_2R',
         c_vdd=('C2', '.1uF'), c_5va=('C25', '.1uF'), c_pot=('C14', '.1uF'),
         r_wpa=('R3', '150K'), c_plus=('C3', '.1uF'), r_plus=('R7', '7.07K'),
         r_in_p=('R6', '20K'), r_up_p=('R3B', '10K'), r_dn_p=('R5', '2.67K'),
         r_fb1_p=('R4', '1K'), r_fb2_p=('R1', '1K'), r_out_p=('R2', '33K'),
         d_p=('CR3', '1N4148'), c_neg=('C15', '.1uF'),
         r_wfb=('R78C', '150K'), r_in_r=('R73', '10K'), r_up_r=('R75', '10K'),
         r_dn_r=('R72', '2.67K'), r_fb1_r=('R71', '1K'), r_fb2_r=('R68', '1K'),
         r_out_r=('R69', '33K'), d_r=('CR6', '1N4148'), c_rplus=('C26', '.1uF'),
         r_rplus=('R74', '7.07K'),
         notes={'R3B': 'R3 printed twice in circuit #2 (150K and 10K)',
                'R78C': 'R78 printed again (also circuits #1 and #4)',
                'V7': 'SER.IN line enters from FIG 5D-1 (V9 SER_OUT); line is captioned "NSP_SERI"'}),
    # ── FIG 5D-2 bottom: BUTTER WARMER CIRCUIT #5 ──
    dict(num=5, cell=(1, 1), sheet='5D-2',
         pot='V39', opamp='V40', ser_in='5D_SER_V24_V39', ser_out='5D_SER_V39_V51',
         p_in='BWT_5P', p_out='BWK_5P', r_in='BWT_5R', r_out='BWH_5R',
         c_vdd=('C85', '.1uF'), c_5va=('C97', '.1uF'), c_pot=('C90', '.1uF'),
         r_wpa=('R176', '150K'), c_plus=('C86', '.1uF'), r_plus=('R180', '7.07K'),
         r_in_p=('R179', '20K'), r_up_p=('R181', '10K'), r_dn_p=('R176B', '2.67K'),
         r_fb1_p=('R177', '1K'), r_fb2_p=('R174', '1K'), r_out_p=('R175', '33K'),
         d_p=('CR16', '1N4148'), c_neg=('C100', '.1uF'),
         r_wfb=('R219', '150K'), r_in_r=('R222', '10K'), r_up_r=('R224', '10K'),
         r_dn_r=('R221', '2.67K'), r_fb1_r=('R220', '1K'), r_fb2_r=('R217', '1K'),
         r_out_r=('R218', '33K'), d_r=('CR17', '1N4140'), c_rplus=('C99', '.1uF'),
         r_rplus=('R223', '7.07K'),
         notes={'R176B': 'R176 printed twice in circuit #5 (150K and 2.67K)',
                'CR16': 'Output printed BWK_5P (BWH_5P expected)',
                'CR17': 'Printed 1N4140 (other circuits 1N4148)',
                'V39': 'SER.IN line enters from FIG 5D-1 (V24 SER_OUT); line is captioned "NSP_SERI"'}),
    # ── FIG 5D-3 top: BUTTER WARMER CIRCUIT #3 ──
    dict(num=3, cell=(2, 0), sheet='5D-3',
         pot='V22', opamp='V23', ser_in='5D_SER_V7_V22', ser_out='NSP_SER5',
         p_in='BWT_3P', p_out='BWH_3P', r_in='BWT_3R', r_out='BWH_3R',
         c_vdd=('C44', '.1uF'), c_5va=('C65', '.1uF'), c_pot=('C55', '.1uF'),
         r_wpa=('R112', '150K'), c_plus=('C45', '.1uF'), r_plus=('R116', '7.07K'),
         r_in_p=('R6B', '20K'), r_up_p=('R117', '10K'), r_dn_p=('R114', '2.67K'),
         r_fb1_p=('R113', '1K'), r_fb2_p=('R110', '1K'), r_out_p=('R111', '33K'),
         d_p=('CR8', '1N4148'), c_neg=('C56', '.1uF'),
         r_wfb=('R148', '150K'), r_in_r=('R151', '10K'), r_up_r=('R153', '10K'),
         r_dn_r=('R150', '2.67K'), r_fb1_r=('R149', '1K'), r_fb2_r=('R146', '1K'),
         r_out_r=('R147', '33K'), d_r=('CR12', '1N4148'), c_rplus=('C66', '.1uF'),
         r_rplus=('R152', '7.07K'),
         notes={'R6B': 'R6 printed again (also circuit #2)',
                'V22': 'SER.IN line enters from FIG 5D-2 (V7 SER.OUT); line is captioned "NSP_SERI"'}),
    # ── FIG 5D-3 bottom: BUTTER WARMER CIRCUIT #6 ──
    dict(num=6, cell=(2, 1), sheet='5D-3',
         pot='V51', opamp='V52', ser_in='5D_SER_V39_V51', ser_out='NSP_SER8',
         p_in='BWT_6P', p_out='BWH_6P', r_in='BWT_6R', r_out='BWH_6R',
         c_vdd=('C133', '.1uF'), c_5va=('C153', '.1uF'), c_pot=('C144', '.1uF'),
         r_wpa=('R242', '150K'), c_plus=('C134', '.1uF'), r_plus=('R246', '7.07K'),
         r_in_p=('R179B', '20K'), r_up_p=('R247', '10K'), r_dn_p=('R244', '2.67K'),
         r_fb1_p=('R243', '1K'), r_fb2_p=('R240', '1K'), r_out_p=('R241', '33K'),
         d_p=('CR10', '1N4148'), c_neg=('C145', '.1uF'),
         r_wfb=('R259', '150K'), r_in_r=('R262', '10K'), r_up_r=('R264', '10K'),
         r_dn_r=('R261', '2.67K'), r_fb1_r=('R260', '1K'), r_fb2_r=('R257', '1K'),
         r_out_r=('R258', '33K'), d_r=('CR19', '1N4140'), c_rplus=('C154', '.1uF'),
         r_rplus=('R263', '7.07K'),
         notes={'R179B': 'R179 printed again (also circuit #5)',
                'CR19': 'Printed 1N4140 (other circuits 1N4148)',
                'V51': 'SER.IN line enters from FIG 5D-2 (V39 SER.OUT); line is captioned "NSP_SERI"'}),
]

# ── One butter warmer circuit per child sheet (cells; 1 cell = 1.27 mm) ──
# Pot left; the P channel (op-amp pins 5/6/7) above, the R channel (2/3/1) below, each an
# inverting stage: input resistor and the R_up/R_dn offset divider into the - input, two 1K
# in series as feedback over the top, the pot wiper through an RC into the + input below,
# the output through R_out and the diode to the off-page line.
POT_AT = (60, 100)
# printed off-page flags that no transcribed figure uses: a net label on the circuit's sheet
LOCAL_FLAGS = {'NSP_SER5', 'NSP_SER8', 'BWK_5P'}
OPAMP_X = 136
CHANNEL_Y = {'P': 62, 'R': 122}
DECOUPLE_Y = 182


def _printed(ref):
    """Printed ref for a suffixed duplicate (R78B -> R78)."""
    base = ref.rstrip('BC') if ref[-1] in 'BC' and ref[-2].isdigit() else ref
    return base if base != ref else None


def _part(c, key, kind, at, desc, rot=0, pins=None, **extra):
    ref, value = c[key]
    return P(ref, value, kind, at=at, rot=rot, pins=pins, printed=_printed(ref),
             note=c['notes'].get(ref), desc=desc, **extra)


def _channel(c, ch):
    """Parts, wires, taps and label spots of one channel ('P' or 'R')."""
    n, X, Y = c['num'], OPAMP_X, CHANNEL_Y[ch]
    p = ch == 'P'
    net = {k: f'5D{n}_{ch}{k}' for k in ('REF', 'PLUS', 'FB', 'OUT', 'D')}
    wiper = f'5D{n}_' + ('WPA' if p else 'WFB')
    k = {'in': 'r_in_p' if p else 'r_in_r', 'up': 'r_up_p' if p else 'r_up_r',
         'dn': 'r_dn_p' if p else 'r_dn_r', 'fb1': 'r_fb1_p' if p else 'r_fb1_r',
         'fb2': 'r_fb2_p' if p else 'r_fb2_r', 'out': 'r_out_p' if p else 'r_out_r',
         'd': 'd_p' if p else 'd_r', 'w': 'r_wpa' if p else 'r_wfb',
         'cp': 'c_plus' if p else 'c_rplus', 'rp': 'r_plus' if p else 'r_rplus'}
    ref = {key: c[name][0] for key, name in k.items()}
    amp = f"{c['opamp']}{'A' if p else 'B'}"
    src, dst = (c['p_in'], c['p_out']) if p else (c['r_in'], c['r_out'])
    pin = OPAMP_P if p else OPAMP_R
    side = 'P' if p else 'R'
    pot_end = 'A' if p else 'B'
    supply = {'8': '+5VA', '4': '-15V'} if p else {}
    parts = [
        _part(c, k['in'], 'R', (X - 21, Y - 30), _INF + f'input resistor from {src} into the {side}-channel '
              'inverting input', rot=90, pins={'1': src, '2': net['REF']}),
        _part(c, k['fb1'], 'R', (X - 11, Y - 30), _INF + f'{side}-channel feedback, first of two 1K in series '
              '(output to inverting input)', rot=90, pins={'1': net['REF'], '2': net['FB']}),
        _part(c, k['fb2'], 'R', (X + 7, Y - 30), _INF + f'{side}-channel feedback, second of two 1K in series',
              rot=90, pins={'1': net['FB'], '2': net['OUT']}),
        _part(c, k['up'], 'R', (X - 24, Y - 15), _INF + f'{side}-channel offset: +5VA to the inverting input',
              pins={'1': '+5VA', '2': net['REF']}, text=(-8, -1)),
        _part(c, k['dn'], 'R', (X - 24, Y - 5), _INF + f'{side}-channel offset: inverting input to ground '
              '(divider with the +5VA resistor)', pins={'1': net['REF'], '2': 'GND'}, text=(-8, -1)),
        P(amp, 'LT1124', 'OPAMP', at=(X, Y), pinmap=pin, text=(4, -9), printed=c['opamp'],
          note=c['notes'].get(amp),
          pins={pin['-']: net['REF'], pin['+']: net['PLUS'], pin['out']: net['OUT'], **supply},
          desc=_INF + f'{side}-channel amplifier of butter warmer circuit #{n}: {src} (inverting, with '
                      f'the offset divider) against the pot {pot_end} level (non-inverting); drives {dst}'),
        _part(c, k['out'], 'R', (X + 30, Y), _INF + f'{side}-channel output series resistor', rot=90,
              pins={'1': net['OUT'], '2': net['D']}),
        _part(c, k['d'], 'D', (X + 48, Y), _INF + f'{side}-channel series diode from the output resistor to '
              f'{dst} (direction as transcribed)', pins={'1': net['D'], '2': dst}, text=(0, -6)),
        _part(c, k['w'], 'R', (X - 48, Y + 10), _INF + f'series resistor from the pot {pot_end} wiper into the '
              f'{side}-channel non-inverting input', rot=90, pins={'1': wiper, '2': net['PLUS']}),
        _part(c, k['cp'], 'C', (X - 36, Y + 15), _INF + f'filter capacitor on the {side}-channel '
              'non-inverting input', pins={'1': net['PLUS'], '2': 'GND'}),
        _part(c, k['rp'], 'R', (X - 24, Y + 15), _INF + f'{side}-channel non-inverting input to ground '
              '(divides the wiper level with the series resistor)', pins={'1': net['PLUS'], '2': 'GND'}),
    ]
    t = {name: f'{ch}{name}' for name in ('n1', 'n2', 'pp', 'o', 'o2')}
    taps = [tap(t['n1'], net['REF'], (X - 16, Y - 2), facing='right'),
            tap(t['n2'], net['REF'], (X - 16, Y - 10)),
            tap(t['pp'], net['PLUS'], (X - 12, Y + 10), facing='left'),
            tap(t['o'], net['OUT'], (X + 16, Y), facing='right'),
            tap(t['o2'], net['OUT'], (X + 16, Y - 30))]
    wires = [
        (f"{ref['in']}.2", f"{ref['fb1']}.1"), (f"{ref['fb1']}.1", f"@{t['n2']}"),
        (f"@{t['n2']}", f"@{t['n1']}"), (f"@{t['n1']}", f"{amp}.{pin['-']}"),
        (f"{ref['up']}.2", f"{ref['dn']}.1"), (f"{ref['up']}.2", f"@{t['n2']}"),
        (f"{ref['fb1']}.2", f"{ref['fb2']}.1"), (f"{ref['fb2']}.2", f"@{t['o2']}"),
        (f"@{t['o2']}", f"@{t['o']}"), (f"{amp}.{pin['out']}", f"@{t['o']}"),
        (f"@{t['o']}", f"{ref['out']}.1"), (f"{ref['out']}.2", f"{ref['d']}.1"),
        (f"{amp}.{pin['+']}", f"@{t['pp']}"), (f"@{t['pp']}", f"{ref['rp']}.1"),
        (f"{ref['rp']}.1", f"{ref['cp']}.1"), (f"{ref['cp']}.1", f"{ref['w']}.2"),
    ]
    names = {net['REF']: f"@{t['n1']}", net['PLUS']: f"@{t['pp']}", net['FB']: f"{ref['fb1']}.2",
             net['OUT']: f"@{t['o']}", net['D']: f"{ref['out']}.2",
             wiper: f"{c['pot']}.{'10' if p else '6'}"}
    return parts, wires, taps, names, (src, dst, ref['in'], ref['d'])


def bw_child(c):
    """Child sheet for one butter warmer circuit; its block sits in the figure's 2 x 3 grid."""
    n, col, row = c['num'], *c['cell']
    pot = c['pot']
    px, py = POT_AT
    parts = [
        P(pot, 'MC2030', 'F5D_MC2030', at=POT_AT, printed=None, note=('Dual 1K digital pot as printed. '
          + (c['notes'].get(pot) or '')).strip(),
          pins={'15': 'NSP_PROG', '14': 'NSP_READ', '2': c['ser_in'], '1': 'NSP_CLK',
                '13': '+5VA', '10': f'5D{n}_WPA', '9': 'GND', '4': '+5VA', '6': f'5D{n}_WFB',
                '7': 'GND', '3': c['ser_out'], '16': '+5V', 'G': 'GND'},
          probable='unidentified dual serial digital potentiometer (MC2030 family; dual 1K)',
          desc=_INF + f'dual serial digital pot of butter warmer circuit #{n}, loaded over the NSP lines; '
                      'pot A (+5VA to GND) sets the P channel, pot B the R channel. ' + NSP),
    ]
    wires, taps, names, io = [], [], {}, {}
    for ch in ('P', 'R'):
        ch_parts, ch_wires, ch_taps, ch_names, io[ch] = _channel(c, ch)
        parts += ch_parts
        wires += ch_wires
        taps += ch_taps
        names.update(ch_names)
    wires += [(f'{pot}.10', f"{c['r_wpa'][0]}.1", [(px + 20, py - 8), (px + 20, CHANNEL_Y['P'] + 10)]),
              (f'{pot}.6', f"{c['r_wfb'][0]}.1", [(px + 20, py + 8), (px + 20, CHANNEL_Y['R'] + 10)])]
    caps = [('c_vdd', '+5V', 'pot +5V (VDD) supply decoupling'),
            ('c_5va', '+5VA', '+5VA supply decoupling'),
            ('c_pot', '+5VA', '+5VA supply decoupling'),
            ('c_neg', '-15V', f"{c['opamp']} -15V supply decoupling")]
    for index, (key, rail, text) in enumerate(caps):
        parts.append(_part(c, key, 'C', (40 + 13 * index, DECOUPLE_Y), _INF + text,
                           pins={'1': rail, '2': 'GND'}))
    wires += [(f"{c[a][0]}.2", f"{c[b][0]}.2") for a, b in zip(['c_vdd', 'c_5va', 'c_pot'],
                                                               ['c_5va', 'c_pot', 'c_neg'])]
    names['GND'] = f"{c['c_vdd'][0]}.2"

    (p_in, p_out, rin_p, d_p), (r_in, r_out, rin_r, d_r) = io['P'], io['R']
    nsp = [port('NSP_PROG', 'input', on=f'{pot}.15', extra=2, side='left'),
           port('NSP_READ', 'input', on=f'{pot}.14', extra=2, side='left'),
           port('NSP_CLK', 'input', on=f'{pot}.1', extra=2, side='left')]
    ser_in = port(c['ser_in'], 'input', on=f'{pot}.2', extra=2, side='left')
    long_nets = set()
    # row 2: SER.OUT level with the next block's SER.IN (left pin 4), so the chain is straight
    ser_out = [port(c['ser_out'], 'output', on=f'{pot}.3', extra=2, side='right',
                    slot=4 if row == 1 else None)]
    if c['ser_out'] in LOCAL_FLAGS:
        ser_out = []
        long_nets.add(c['ser_out'])
    lines = []  # (net, shape, endpoint, side) of the off-sheet heater lines
    for src, dst, r_in_ref, d_ref in ((p_in, p_out, rin_p, d_p), (r_in, r_out, rin_r, d_r)):
        if src == dst:  # printed with one name at both ends (a short as drawn)
            lines.append(port(src, 'passive', on=f'{r_in_ref}.1', extra=2, side='left'))
            long_nets.add(src)
        else:
            lines.append(port(src, 'input', on=f'{r_in_ref}.1', extra=2, side='left'))
            if dst in LOCAL_FLAGS:  # a net label clear of the diode's text
                long_nets.add(dst)
                taps.append(tap('flag', dst, (OPAMP_X + 57, CHANNEL_Y['P' if dst == p_out else 'R']),
                                facing='right'))
                wires.append((f'{d_ref}.2', '@flag'))
                names[dst] = '@flag'
            else:
                lines.append(port(dst, 'output', on=f'{d_ref}.2', extra=2, side='right'))
    left = [p for p in lines if p.side == 'left']
    right = [p for p in lines if p.side == 'right']
    # block pin order: the NSP lines nest between the two rows of blocks on the figure page
    if row == 0:
        ports = [ser_in] + left + nsp + ser_out + right
    else:
        ports = nsp[::-1] + [ser_in] + left + right + ser_out
    notes = [(f"BUTTER WARMER CIRCUIT #{n}  (FIG {c['sheet']})", 15, 30),
             (f"{pot} / {c['opamp']} DECOUPLING CAPACITORS", 32, DECOUPLE_Y - 12)]
    shorts = [net for net in long_nets if net not in LOCAL_FLAGS]
    flags = sorted(long_nets & LOCAL_FLAGS)
    text = [f'{net} is printed at both the input resistor and the diode: the two are one net as drawn.'
            for net in shorts]
    text += [f'{net} is printed as an off-page flag; no transcribed figure uses it.' for net in flags]
    if text:
        notes.append(('\n'.join(text), 15, DECOUPLE_Y + 14))
    return child(f'bw{n}', f'Butter warmer circuit #{n} ({pot}, {c["opamp"]})', short=f'BW{n}',
                 paper='A3', at=(BLOCK_X[col], BLOCK_Y[row]), width=45.72, parts=parts, wires=wires,
                 ports=ports, taps=taps, names=names, long_nets=long_nets, notes=notes)


# ── Figure page: 2 rows x 3 columns as in the patent (5D-1, 5D-2, 5D-3) ──
BLOCK_X = [80, 168, 256]
BLOCK_Y = [40, 84]
LINE_ROW = 76  # NSP line labels, in the gap between the rows

CHILDREN = [bw_child(c) for c in CIRCUITS]
_BY_NUM = {c['num']: c for c in CIRCUITS}

PAGE_TAPS, PAGE_WIRES, PORTS = [], [], []
PAGE_NAMES = {c['ser_out']: None for c in CIRCUITS if c['ser_out'].startswith('5D_SER')}
PAGE_LONG_NETS = {'NSP_PROG', 'NSP_READ', 'NSP_CLK'}
for col in range(3):
    top, bottom = (f"bw{c['num']}" for c in sorted(CIRCUITS, key=lambda c: c['cell'][1])
                   if c['cell'][0] == col)
    bx = BLOCK_X[col]
    for net, dx in (('NSP_PROG', -30), ('NSP_READ', -18), ('NSP_CLK', -6)):
        x = bx + dx
        if col == 0:
            end = f'@{net}'
            PORTS.append(port(net, 'input', at=(x, LINE_ROW), facing='left'))
        else:
            end = f'@{net}{col}'
            PAGE_TAPS.append(tap(f'{net}{col}', net, (x, LINE_ROW), facing='left'))
            PAGE_NAMES.setdefault(net, []).append(end)
        PAGE_WIRES += [(f'{top}:{net}', end, 'hv'), (f'{bottom}:{net}', end, 'hv')]
# serial chains: NSP_SERI -> #1 -> #2 -> #3 -> NSP_SER5 and NSP_SERI -> #4 -> #5 -> #6 -> NSP_SER8
PORTS.append(port('NSP_SERI', 'input', at=(28, 44), facing='left'))
PAGE_TAPS.append(tap('seri', 'NSP_SERI', (34, 44)))
PAGE_WIRES += [('@NSP_SERI', '@seri'), ('@seri', 'bw1:NSP_SERI'), ('@seri', 'bw4:NSP_SERI', [(34, 100)])]
for a, b in ((1, 2), (2, 3)):
    PAGE_WIRES.append((f"bw{a}:{_BY_NUM[a]['ser_out']}", f"bw{b}:{_BY_NUM[b]['ser_in']}"))
for a, b in ((4, 5), (5, 6)):
    PAGE_WIRES.append((f"bw{a}:{_BY_NUM[a]['ser_out']}", f"bw{b}:{_BY_NUM[b]['ser_in']}"))
# heater lines, in circuit order: a figure port on each block pin (a flag no other figure
# uses is a net label on the circuit's sheet instead)
for c in sorted(CIRCUITS, key=lambda c: c['num']):
    for net in dict.fromkeys((c['p_in'], c['r_in'], c['p_out'], c['r_out'])):
        if net in LOCAL_FLAGS:
            continue
        both = net in (c['p_in'], c['r_in']) and net in (c['p_out'], c['r_out'])
        shape = 'passive' if both else 'input' if net in (c['p_in'], c['r_in']) else 'output'
        PORTS.append(port(net, shape, on=f"bw{c['num']}:{net}", extra=2))

NOTES = [
    ('Serial chains: NSP_SERI -> #1 (V9) -> #2 (V7) -> #3 (V22) -> NSP_SER5   and   '
     'NSP_SERI -> #4 (V24) -> #5 (V39) -> #6 (V51) -> NSP_SER8.\n'
     'The SER.IN lines of #2, #3, #5 and #6 come from the previous sheet, captioned "NSP_SERI"; drawn as the '
     'wire from the previous pot SER.OUT.\n'
     'Printed anomalies kept: #1 output BWT_1P (= its input), #4 input BWH_4P (= its output), #5 output BWK_5P.\n'
     'Signal roles are inferred; the patent text does not describe FIG 5D.', 15, 126),
]

_SIDES = {'P': 'P (op-amp pins 5/6/7)', 'R': 'R (op-amp pins 2/3/1)'}


def _descriptions():
    d = {
        'NSP_PROG': 'Patent: FIG 5D label NSP_PROG (also 5B, 5E). Inferred: program strobe of the NSP serial pots',
        'NSP_READ': 'Patent: FIG 5D label NSP_READ (also 5B, 5E). Inferred: read strobe of the NSP serial pots',
        'NSP_CLK': 'Patent: FIG 5D label NSP_CLK (also 5B, 5E, 5G). Inferred: serial clock of the NSP pots',
        'NSP_SERI': 'Patent: FIG 5D label NSP_SERI (from FIG 5B U29 SER.OUT; also 5E). Inferred: serial data '
                    'into the first pot of each chain (V9, V24)',
        'NSP_SER5': 'Patent: FIG 5D off-page flag NSP_SER5 on V22 SER.OUT (end of the #1-#2-#3 chain); no '
                    'transcribed figure uses it',
        'NSP_SER8': 'Patent: FIG 5D off-page flag NSP_SER8 on V51 SER.OUT (end of the #4-#5-#6 chain); no '
                    'transcribed figure uses it',
    }
    for c in CIRCUITS:
        n = c['num']
        if c['ser_out'].startswith('5D_SER'):
            d[c['ser_out']] = (f"Patent: FIG 5D serial line from {c['pot']} SER.OUT to the next pot's SER.IN "
                               '(continued across the sheet match line, captioned "NSP_SERI")')
        for ch, src, dst in (('P', c['p_in'], c['p_out']), ('R', c['r_in'], c['r_out'])):
            if src == dst:
                d[src] = (f'Patent: FIG 5D label {src}, printed at both the input resistor and the output diode of '
                          f'circuit #{n} channel {ch} (a short as drawn). Role unknown')
            else:
                d[src] = (f'Patent: FIG 5D label {src} (also FIG 5A/5H). Inferred: butter warmer #{n} sensor line '
                          f'into channel {ch} through its input resistor; role unknown')
                d[dst] = (f'Patent: FIG 5D label {dst}. Inferred: butter warmer #{n} channel {ch} drive output '
                          '(through the series resistor and diode); role unknown')
            pre = f'5D{n}_{ch}'
            d[pre + 'REF'] = f'Inferred from the circuit: #{n} channel {ch} inverting input (input, offset, feedback)'
            d[pre + 'PLUS'] = f'Inferred from the circuit: #{n} channel {ch} non-inverting input (filtered pot level)'
            d[pre + 'FB'] = f'Inferred from the circuit: #{n} channel {ch} node between the two 1K feedback resistors'
            d[pre + 'OUT'] = f'Inferred from the circuit: #{n} channel {ch} op-amp output'
            d[pre + 'D'] = f'Inferred from the circuit: #{n} channel {ch} node between the output resistor and diode'
        d[f'5D{n}_WPA'] = f"Inferred from the circuit: {c['pot']} pot A wiper, to the channel P + input"
        d[f'5D{n}_WFB'] = f"Inferred from the circuit: {c['pot']} pot B wiper (printed WFB), to the channel R + input"
    d['BWK_5P'] = ('Patent: FIG 5D off-page flag BWK_5P on the circuit #5 channel P diode (BWH_5P expected); '
                   'no transcribed figure uses it')
    return d


NET_DESCRIPTIONS = _descriptions()
