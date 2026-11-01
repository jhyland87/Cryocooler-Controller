"""FIG 5D - six butter warmer (heater drive) circuits, FIG 5D-1/5D-2/5D-3."""

from oemsch import P

TITLE = 'FIG 5D - Butter warmer circuits #1-#6'
SOURCE = 'US6098409 sheets 8-10 of 25 (PDF p9-11), FIG 5D-1/5D-2/5D-3'
PAPER = 'A1'

# MC2030 dual 1K digital pot, pins as printed. Blank rows only spread the pins out.
# GND pin has no printed number: numbered 'G' here.
SYMBOLS = {
    'F5D_MC2030': {
        'left': [('15', 'PROG'), None, None, ('14', 'READ'), None, None, ('2', 'SER.IN'),
                 None, None, ('1', 'SER.CLK')],
        'right': [('13', 'RIA'), None, None, ('10', 'WPA'), None, None, ('9', 'RFA'), None, None,
                  ('4', 'RIB'), None, None, ('6', 'WFB'), None, None, ('7', 'RFB'), None, None,
                  ('3', 'SER.OUT')],
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

CELL_W, CELL_H = 212, 210
ORIGIN = (14, 32)


def _printed(ref):
    """Printed ref for a suffixed duplicate (R78B -> R78)."""
    base = ref.rstrip('BC') if ref[-1] in 'BC' and ref[-2].isdigit() else ref
    return base if base != ref else None


def _part(ref, value, kind, at, circuit, rot=0, pins=None, **extra):
    note = circuit['notes'].get(ref)
    return P(ref, value, kind, at=at, rot=rot, pins=pins, printed=_printed(ref), note=note,
             **extra)


def circuit_parts(c):
    """Parts and wires for one butter warmer circuit, placed in its grid cell."""
    ox = ORIGIN[0] + CELL_W * c['cell'][0]
    oy = ORIGIN[1] + CELL_H * c['cell'][1]
    n = c['num']
    net = {k: f'5D{n}_{k}' for k in ('WPA', 'WFB', 'PREF', 'PPLUS', 'PFB', 'POUT', 'PD',
                                      'RREF', 'RPLUS', 'RFB', 'ROUT', 'RD')}

    def at(dx, dy):
        return (ox + dx, oy + dy)

    pot_note = c['notes'].get(c['pot'])
    parts = [
        P(c['pot'], 'MC2030', 'F5D_MC2030', at=at(40, 50),
          pins={'15': 'NSP_PROG', '14': 'NSP_READ', '2': c['ser_in'], '1': 'NSP_CLK',
                '13': '+5VA', '10': net['WPA'], '9': 'GND', '4': '+5VA', '6': net['WFB'],
                '7': 'GND', '3': c['ser_out'], '16': '+5V', 'G': 'GND'},
          note=('Dual 1K digital pot as printed. ' + (pot_note or '')).strip()),
        _part(c['c_vdd'][0], c['c_vdd'][1], 'C', at(58, 22), c, pins={'1': '+5V', '2': 'GND'}),
        _part(c['c_5va'][0], c['c_5va'][1], 'C', at(22, 85), c, pins={'1': '+5VA', '2': 'GND'}),
        _part(c['c_pot'][0], c['c_pot'][1], 'C', at(64, 78), c, pins={'1': '+5VA', '2': 'GND'}),
        # ── P section (op-amp pins 5/6/7) ──
        _part(c['r_wpa'][0], c['r_wpa'][1], 'R', at(72, 38), c, rot=90,
              pins={'1': net['WPA'], '2': net['PPLUS']}),
        _part(c['c_plus'][0], c['c_plus'][1], 'C', at(92, 60), c,
              pins={'1': net['PPLUS'], '2': 'GND'}),
        _part(c['r_plus'][0], c['r_plus'][1], 'R', at(104, 60), c,
              pins={'1': net['PPLUS'], '2': 'GND'}),
        _part(c['r_in_p'][0], c['r_in_p'][1], 'R', at(98, 26), c, rot=90,
              pins={'1': c['p_in'], '2': net['PREF']}),
        _part(c['r_up_p'][0], c['r_up_p'][1], 'R', at(118, 10), c, rot=90,
              pins={'1': '+5VA', '2': net['PREF']}),
        _part(c['r_dn_p'][0], c['r_dn_p'][1], 'R', at(136, 10), c, rot=90,
              pins={'1': net['PREF'], '2': 'GND'}),
        _part(c['r_fb1_p'][0], c['r_fb1_p'][1], 'R', at(140, 26), c, rot=90,
              pins={'1': net['PREF'], '2': net['PFB']}),
        _part(c['r_fb2_p'][0], c['r_fb2_p'][1], 'R', at(155, 26), c, rot=90,
              pins={'1': net['PFB'], '2': net['POUT']}),
        _part(f"{c['opamp']}A", 'LT1124', 'OPAMP', at(130, 48), c, pinmap=OPAMP_P,
              pins={'6': net['PREF'], '5': net['PPLUS'], '7': net['POUT'], '8': '+5VA',
                    '4': '-15V'}) | {'printed': c['opamp']},
        _part(c['c_neg'][0], c['c_neg'][1], 'C', at(140, 66), c, pins={'1': '-15V', '2': 'GND'}),
        _part(c['r_out_p'][0], c['r_out_p'][1], 'R', at(158, 48), c, rot=90,
              pins={'1': net['POUT'], '2': net['PD']}),
        _part(c['d_p'][0], c['d_p'][1], 'D', at(176, 48), c,
              pins={'1': net['PD'], '2': c['p_out']}),
        # ── R section (op-amp pins 2/3/1) ──
        _part(c['r_wfb'][0], c['r_wfb'][1], 'R', at(78, 130), c,
              pins={'1': net['WFB'], '2': net['RPLUS']}),
        _part(c['r_in_r'][0], c['r_in_r'][1], 'R', at(98, 160), c, rot=90,
              pins={'1': c['r_in'], '2': net['RREF']}),
        _part(c['r_up_r'][0], c['r_up_r'][1], 'R', at(118, 122), c, rot=90,
              pins={'1': '+5VA', '2': net['RREF']}),
        _part(c['r_dn_r'][0], c['r_dn_r'][1], 'R', at(136, 122), c, rot=90,
              pins={'1': net['RREF'], '2': 'GND'}),
        _part(c['r_fb1_r'][0], c['r_fb1_r'][1], 'R', at(140, 140), c, rot=90,
              pins={'1': net['RREF'], '2': net['RFB']}),
        _part(c['r_fb2_r'][0], c['r_fb2_r'][1], 'R', at(155, 140), c, rot=90,
              pins={'1': net['RFB'], '2': net['ROUT']}),
        _part(f"{c['opamp']}B", 'LT1124', 'OPAMP', at(130, 164), c, pinmap=OPAMP_R,
              pins={'2': net['RREF'], '3': net['RPLUS'], '1': net['ROUT']}) | {'printed': c['opamp']},
        _part(c['r_out_r'][0], c['r_out_r'][1], 'R', at(158, 164), c, rot=90,
              pins={'1': net['ROUT'], '2': net['RD']}),
        _part(c['d_r'][0], c['d_r'][1], 'D', at(176, 164), c,
              pins={'1': net['RD'], '2': c['r_out']}),
        _part(c['c_rplus'][0], c['c_rplus'][1], 'C', at(92, 184), c,
              pins={'1': net['RPLUS'], '2': 'GND'}),
        _part(c['r_rplus'][0], c['r_rplus'][1], 'R', at(104, 184), c,
              pins={'1': net['RPLUS'], '2': 'GND'}),
    ]
    wires = [
        (f"{c['pot']}.10", f"{c['r_wpa'][0]}.1"),
        (f"{c['r_up_p'][0]}.2", f"{c['r_dn_p'][0]}.1"),
        (f"{c['r_fb1_p'][0]}.2", f"{c['r_fb2_p'][0]}.1"),
        (f"{c['opamp']}A.7", f"{c['r_out_p'][0]}.1"),
        (f"{c['r_out_p'][0]}.2", f"{c['d_p'][0]}.1"),
        (f"{c['opamp']}B.1", f"{c['r_out_r'][0]}.1"),
        (f"{c['r_up_r'][0]}.2", f"{c['r_dn_r'][0]}.1"),
        (f"{c['r_fb1_r'][0]}.2", f"{c['r_fb2_r'][0]}.1"),
        (f"{c['r_out_r'][0]}.2", f"{c['d_r'][0]}.1"),
        (f"{c['c_plus'][0]}.1", f"{c['r_plus'][0]}.1"),
        (f"{c['c_rplus'][0]}.1", f"{c['r_rplus'][0]}.1"),
    ]
    notes = [(f"BUTTER WARMER CIRCUIT #{n}  (FIG {c['sheet']})", ox + 20, oy + 196)]
    return parts, wires, notes


PARTS, WIRES, NOTES = [], [], []
for _circuit in CIRCUITS:
    _parts, _wires, _notes = circuit_parts(_circuit)
    PARTS += _parts
    WIRES += _wires
    NOTES += _notes

NOTES += [
    ('Serial chain (traced across sheet match lines): NSP_SERI -> V9 -> V7 -> V22 -> NSP_SER5'
     '   and   NSP_SERI -> V24 -> V39 -> V51 -> NSP_SER8', 14, 444),
    ('SER.IN of V7/V39/V22/V51 is a line from the previous sheet captioned "NSP_SERI"; '
     'modelled as the wire from the previous pot SER.OUT (nets 5D_SER_*).', 14, 448),
    ('Printed anomalies kept: circuit #1 output BWT_1P (= its input name); circuit #4 input BWH_4P '
     '(= its output name); circuit #5 output BWK_5P.', 14, 452),
]
