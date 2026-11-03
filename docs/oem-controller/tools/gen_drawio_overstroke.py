"""
@file gen_drawio_overstroke.py
@brief Generate analysis/diagrams/overstroke_signal_path.drawio.

Page 1: the analog back-off counter and drive clamp (US6098409 FIG 5C/5E/5G).
Page 2: how each STI source handles overstroke.
Text sources and estimates are in analysis/OVERSTROKE.md. Grey dashed = inference.
Run: python3 -I docs/oem-controller/tools/gen_drawio_overstroke.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawio import Diagram, save  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INFERRED = 'dashed=1;fontColor=#7f7f7f;strokeColor=#7f7f7f;'
SENSE = 'fillColor=#dae8fc;strokeColor=#6c8ebf;'
COUNT = 'fillColor=#ffe6cc;strokeColor=#d79b00;'
DRIVE = 'fillColor=#d5e8d4;strokeColor=#82b366;'
MCU = 'fillColor=#e1d5e7;strokeColor=#9673a6;'
RESET = 'fillColor=#f8cecc;strokeColor=#b85450;'
# Edge labels beside the line, so text never covers it.
ABOVE = 'verticalAlign=bottom;labelBackgroundColor=none;spacingBottom=2;'
BELOW = 'verticalAlign=top;labelBackgroundColor=none;spacingTop=2;'


def hardware():
    d = Diagram('Back-off counter (FIG 5C)',
                'Overstroke back-off counter and drive clamp (US6098409 / US6256999)',
                'FIG 5C-1/5C-2 (PDF p7-8), FIG 5E (p12), FIG 5G-3 (p17). Values as printed; '
                '"≈" = estimate from printed values (see analysis/OVERSTROKE.md §2.3)')
    # ── Detection ──
    d.node('sens', 'HOG_T / HOG_TR\n(off-board sensor)\nassumed: knock sensor 64', 0, 40, 140, 60,
           style=INFERRED)
    d.node('amp', 'U53A LT1124\ninverting AC amp\nR266 221K(RM) / 49.0K(TM)', 210, 40, 170, 60, style=SENSE)
    d.node('tc', 'U53B LT1124\nthermistor-compensated (TM)\nRT1 Y4401; R284 0Ω (RM)', 450, 40, 180, 60,
           style=SENSE)
    d.node('cmp', 'U48 LT1011A comparator\nthreshold ≈ 0-94 mV\n(R255/R256, pot R285)', 700, 40, 170, 60,
           style=SENSE)
    d.edge('sens', 'amp', 'C150', style=ABOVE)
    d.edge('amp', 'tc', 'C155', style=ABOVE)
    d.edge('tc', 'cmp', 'R253\nR254', style=ABOVE)
    # ── Counter ──
    d.node('os1', 'U28A HC123 (B = pin 2)\n≈10 ms one-shot\nR144 10K / C53 2.2uF', 970, 0, 170, 60, style=COUNT)
    d.node('os2', 'U28B HC123 (B = pin 10)\n≈30 s, retriggered\nR145 640K / C72 100uF', 970, 120, 170, 60,
           style=COUNT)
    d.node('chg', 'Q5 off → R167 64.8K\n→ Q4 (JFET as diode)\n≈ +40 mV per trip', 1240, 0, 180, 60,
           style=COUNT)
    d.node('bld', 'after ≈30 s with no trip:\nQ1 on, C71 bleeds via\nR130 1M (τ ≈ 10 s)', 1240, 120, 180, 60,
           style=COUNT)
    d.node('cap', 'C71 10uF\nback-off count', 1500, 60, 120, 60, style=COUNT + 'fontStyle=1;')
    d.edge('cmp', 'os1', entry=(0, 0.5))
    d.edge('cmp', 'os2', entry=(0, 0.5))
    d.text('trip', 'trip ↑', 872, 48, 46, 18, style='fontSize=11;')
    d.edge('os1', 'chg', 'Q̄ low', style=ABOVE)
    d.edge('os2', 'bld', 'Q̄ high', style=ABOVE)
    d.edge('chg', 'cap', entry=(0, 0.25))
    d.edge('bld', 'cap', entry=(0, 0.75))
    # ── Reset ──
    d.node('rst', 'SHUTO_T low\n(reset; source not\non transcribed pages)', 700, 250, 170, 60, style=RESET)
    d.node('pre', 'Q2 off → R190/R142 2.5 V\n→ Q3 → C71 ≈ 1.9 V\n(zero-count baseline)', 1240, 250, 180, 60,
           style=RESET)
    d.edge('rst', 'os2', exit_=(1, 0.1), entry=(0.5, 1), points=[(1055, 256)])
    d.text('clr', 'CLR (pins 3, 11)', 1062, 200, 110, 18, shape='ltext', style='fontSize=11;')
    d.edge('rst', 'pre', 'Q2 gate', exit_=(1, 0.5), entry=(0, 0.5), style=BELOW)
    d.edge('pre', 'cap', entry=(0.5, 1), points=[(1560, 280)])
    # ── Output ──
    d.node('fol', 'U27A LMC6-482\nfollower', 1680, 60, 130, 60, style=COUNT)
    d.node('adc1', 'U22 PE3/AN3 (pin 39)\nBACK_OFF_COUNT\nµC ADC (FIG 5G)', 1880, 0, 180, 60, style=MCU)
    d.node('cmpb', 'U27B LMC6-482\n− in: R141 51.1K, and −10V via\nR165 50K + R197 200K pot\n'
           '(no feedback part drawn)', 1880, 110, 200, 80, style=COUNT)
    d.edge('cap', 'fol', 'R143', style=ABOVE)
    d.edge('fol', 'adc1', entry=(0, 0.5))
    d.edge('fol', 'cmpb', entry=(0, 0.5))
    # ── Drive clamp ──
    d.node('cmt', 'CMTO_T → U11\n→ CMT_T', 0, 380, 140, 60, style=DRIVE)
    d.node('rect', 'U26A LT1124\nprecision rectifier\nCR10 / CR11', 210, 380, 170, 60, style=DRIVE)
    d.node('sp', 'U34 LT1012 set-point sum\n(WP.SHOSET, WP.SHTR,\nOF_SET, OF_CTAL, OFT_TE)', 450, 465, 200, 60,
           style=DRIVE)
    d.node('ceil', 'ceiling node\n(U26 pin 3)', 970, 380, 170, 60, style=DRIVE + 'fontStyle=1;')
    d.node('clamp', 'U26 LT1124 + CR14\nideal-diode clamp\nout = min(sum, ceiling)', 1240, 460, 180, 70,
           style=DRIVE + 'fontStyle=1;')
    d.node('u33', 'U33 LMC6-482\n×1.05 → NOT_TOTAL\n(TP1)', 1500, 465, 140, 60, style=DRIVE)
    d.node('pot', 'UX1 serial pot (FIG 5E)\nURF = HOT TOTAL\nset by µC over NSP bus', 1760, 465, 180, 60,
           style=DRIVE)
    d.node('u10', 'U10 LT1124 ×2 → R132\n→ off board: 60 Hz drive\namplitude (multiplier 70)', 2040, 465, 190,
           60, style=DRIVE + INFERRED)
    d.node('adc2', 'U22 PE4/AN4 (pin 38)\nHOT-TOTAL (FIG 5G)', 1760, 590, 180, 50, style=MCU)
    d.edge('cmt', 'rect', 'R127', style=ABOVE)
    d.edge('rect', 'ceil', 'R140 200K', style=ABOVE)
    d.edge('cmpb', 'ceil', 'R163 "XXX"', exit_=(0.5, 1), entry=(0.5, 0), points=[(1980, 340), (1055, 340)],
           style=ABOVE)
    d.edge('ceil', 'clamp', 'limit', exit_=(1, 0.5), entry=(0.5, 0), points=[(1330, 410)], style=ABOVE)
    d.edge('sp', 'clamp', 'R139 10K', exit_=(1, 0.5), entry=(0, 0.5), style=ABOVE)
    d.edge('clamp', 'u33', 'R162', style=ABOVE)
    d.edge('u33', 'pot', '= HOT TOTAL\n(inference)', style=INFERRED + ABOVE)
    d.edge('pot', 'u10', 'LINE OUT', style=ABOVE)
    d.edge('u33', 'adc2', exit_=(0.5, 1), entry=(0, 0.5), points=[(1570, 615)], style=INFERRED)
    d.text('notes', '<b>Reading notes</b><br>'
           '• Higher count → lower ceiling → smaller drive amplitude. With no trips the count holds for '
           '≈30 s, then decays.<br>'
           '• As drawn, U48 output also ties back to the R253/R254 junction (positive feedback; '
           'would latch if taken literally).<br>'
           '• U27B has no feedback part drawn, so as drawn it is a comparator (switches at '
           'BACK_OFF_COUNT ≈ 2-10 V). A proportional amplifier was probably intended.<br>'
           '• The µC only reads the count (PE3) and the clamped command (PE4); the back-off itself is '
           'all hardware. SuperFilter "Back-off Count" (LOOP screen) is this value.',
           0, 580, 1450, 100, raw=True, shape='note')
    return d


def sources():
    d = Diagram('Across sources', 'Overstroke handling in each STI source',
                'US6098409 col. 5 / FIG 3; SuperFilter guide p16, p64-65; US6446444 TASKS.C; '
                'SuperLink Rx manual p14, p67-71')
    columns = [
        ('US6098409 FIG 3 (patent text)', DRIVE, 3, [
            ('Knock sensor 64\n(PZT / back-EMF / current)', ''),
            ('Knock processor 66', ''),
            ('Limiter 68\n(+ thermistor 60/62, PD loop 38)', ''),
            ('Multiplier 70\n× 60 Hz → cryocooler 40', ''),
        ]),
        ('SuperFilter (product of the analog design)', COUNT, 2, [
            ('Overstroke Detector\n(Fig 3, on the cooler)', ''),
            ('FIG 5C back-off counter\n(page 1 of this file)', ''),
            ('"Back-off Count" (LOOP screen)\n0 = no back-off', ''),
            ('"DAC Back Off" = 300\nfactory set, not explained', INFERRED),
        ]),
        ('US6446444 firmware (DSP)', MCU, 0, [
            ('No overstroke / knock code', ''),
            ('CoolDownSp(): ceiling = m·Tcsw + b\n(TASKS.C:1749)', ''),
            ('Motor-hot derating\nTrej < TrejLoTemp (L1755)', ''),
            ('Clamp to MAX_IMOT (90L, 48 V)\n→ ImServo → sine amplitude', ''),
        ]),
        ('SuperLink Rx (later DSP product)', SENSE, 0, [
            ('Motor current & voltage sensors\n(Fig 4, no overstroke block)', ''),
            ('Cooler impedance, current phase\n(likely indicators, inference)', INFERRED),
            ('"Power Drive Limit Foldback"\noff the cooldown table (p67)', ''),
            ('PM fault: impedance out of\nbounds (p71)', ''),
        ]),
    ]
    # arrows: the first `chained` boxes of a column form a stated signal chain
    for col, (title, style, chained, boxes) in enumerate(columns):
        x = col * 300
        d.node(f'h{col}', title, x, 0, 260, 40, style=style + 'fontStyle=1;')
        previous = f'h{col}'
        for row, (text, extra) in enumerate(boxes):
            node_id = f'c{col}r{row}'
            d.node(node_id, text, x + 20, 70 + row * 100, 220, 60, style=style + extra)
            if 0 < row <= chained:
                d.edge(previous, node_id)
            previous = node_id
    return d


def main():
    path = os.path.join(ROOT, 'analysis', 'diagrams', 'overstroke_signal_path.drawio')
    save(path, [hardware(), sources()])
    print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    main()
