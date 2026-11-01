"""
@file gen_drawio_patents.py
@brief Generate draw.io versions of the patent logic/block diagrams.

US6446444: FIG 5A (also the cover drawing), 5B, 6, 7, 8.
US6098409 (same drawings as US6256999): FIG 2, 3, 4.

Run from anywhere: python3 -I docs/oem-controller/tools/gen_drawio_patents.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawio import Diagram, save  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIDIR = 'startArrow=block;startFill=1;'
DASHED = 'dashed=1;'
PLAIN = 'endArrow=none;'


def boundary_labels(d, x_left, x_right, y):
    """DSP/firmware vs external hardware captions under a boundary line."""
    d.text('lbl_dsp', 'DSP/FIRMWARE (22)', x_left, y, 160, 20)
    d.text('lbl_ext', 'EXTERNAL HARDWARE (24)', x_right, y, 180, 20)


# ─── US6446444 ───

def fig5a():
    d = Diagram('FIG 5A', 'US6446444 FIG 5A - Cryocooler drive (current) control loop 20',
                'US6446444 sheet 4 of 7 (PDF p5); the same drawing is on the cover (PDF p1)')
    d.text('r1', 'R1\nCRYOCOOLER\nDRIVING CURRENT\nSETPOINT\n(46)', 0, 105, 120, 80)
    d.node('sum', 'SUM', 150, 115, 60, 60, 'circle', ref=44)
    d.node('pi', 'PROP.-\nINTEGRAL\nCOMP', 250, 120, 110, 50, ref=48)
    d.node('dfc', 'DRIVE\nFACTOR\nCALC', 400, 120, 110, 50, ref=50)
    d.node('sine', 'SINE\nWAVE\nGENERATION', 545, -15, 80, 80, 'circle', ref=54)
    d.node('mult', 'MULTI-\nPLIER', 550, 110, 70, 70, 'circle', ref=52)
    d.node('pwm', 'PWM', 670, 125, 70, 40, ref=56)
    d.node('hb', 'H-BRIDGE', 800, 115, 90, 60, 'tri', ref=30)
    d.dot('j', 950, 145)
    d.text('cooler', 'COOLER (8)', 990, 130, 90, 30)
    d.node('cst', 'CURRENT\nSENSE\nTRANSFORMER', 900, 250, 110, 60, ref=32)
    d.node('buf', 'BUFFER', 760, 255, 80, 50, 'tri_left', ref=34)
    d.node('aaf', 'ANTI-\nALIASING\nFILTER', 600, 255, 110, 50, ref=36)
    d.node('adc', 'ADC', 450, 255, 90, 50, 'pentagon', ref=38, style='flipH=1;')
    d.node('rms', 'RMS\nCURRENT\nCALC', 300, 255, 110, 50, ref=40)
    d.node('dec', '8:1 TIME\nDECIMATION', 140, 255, 110, 50, ref=42)
    d.edge('r1', 'sum', '+')
    d.edge('sum', 'pi')
    d.edge('pi', 'dfc')
    d.edge('dfc', 'mult')
    d.edge('sine', 'mult')
    d.edge('mult', 'pwm')
    d.edge('pwm', 'hb')
    d.edge('hb', 'j', style=PLAIN)
    d.edge('j', 'cooler', '28')
    d.edge('j', 'cst', 'CRYOCOOLER\nDRIVING\nCURRENT', points=[(950, 230)])
    d.edge('cst', 'buf')
    d.edge('buf', 'aaf')
    d.edge('aaf', 'adc')
    d.edge('adc', 'rms')
    d.edge('rms', 'dec')
    d.edge('dec', 'sum', '−', entry=(0.5, 1))
    d.line([(760, -30), (760, 225), (570, 225), (570, 350)], DASHED, label='26')
    boundary_labels(d, 380, 600, 350)
    d.text('sys', '20 (drive controller)', 900, -20, 160, 20)
    return d


def fig5b():
    d = Diagram('FIG 5B', 'US6446444 FIG 5B - Temperature control loop 60',
                'US6446444 sheet 5 of 7 (PDF p6)')
    d.text('rt', 'RT\nTEMP\nSET POINT\n(88)', 0, 105, 110, 75)
    d.node('sum', 'SUM', 130, 115, 60, 60, 'circle', ref=86)
    d.node('pid', 'COMPENSATOR\n(PID)', 230, 120, 120, 50, ref=92)
    d.node('dls', 'DRIVE\nLEVEL\nSET', 390, 120, 100, 50, ref=84)
    d.node('cdsp', 'COOLER DRIVE\nSIGNAL PROCESSING\n(FIG 5A loop)', 540, 110, 150, 70, ref=20)
    d.node('cooler', 'COOLER\nAND\nDEWAR', 770, 115, 110, 60, ref=8)
    d.dot('j', 930, 145)
    d.text('out', 'FILTER COLD\nSTAGE (17)', 960, 125, 110, 40)
    d.node('tsd', 'TEMP\nSENSE\nDIODE', 875, 300, 110, 50, ref=62)
    d.node('buf', 'BUFFER', 735, 300, 80, 50, 'tri_left', ref=64)
    d.node('aaf', 'ANTI-\nALIASING\nFILTER', 585, 300, 110, 50, ref=66)
    d.node('adc', 'ADC', 440, 300, 90, 50, 'pentagon', ref=68, style='flipH=1;')
    d.node('swf', 'SOFT-\nWARE\nFILTERS', 300, 300, 100, 50, ref=70)
    d.node('state', 'STATE?', 115, 290, 90, 70, 'diamond', ref=72)
    d.node('cdp', 'COOLDOWN\nPROFILE\nCALC', 385, 200, 110, 55, ref=78)
    d.edge('rt', 'sum', '+')
    d.edge('sum', 'pid')
    d.edge('pid', 'dls')
    d.edge('dls', 'cdsp', 'R1 (46)')
    d.edge('cdsp', 'cooler', '28')
    d.edge('cooler', 'j', style=PLAIN)
    d.edge('j', 'out')
    d.edge('j', 'tsd')
    d.edge('tsd', 'buf')
    d.edge('buf', 'aaf')
    d.edge('aaf', 'adc')
    d.edge('adc', 'swf')
    d.edge('swf', 'state')
    d.edge('state', 'sum', exit_=(0.5, 0), entry=(0.5, 1))
    d.text('op', 'OPERATING (74)', 50, 240, 105, 20)
    d.text('minus', '−', 165, 180, 20, 20)
    d.edge('state', 'cdp', exit_=(0.75, 0.25), entry=(0, 0.5), points=[(183, 228)])
    d.edge('cdp', 'dls')
    d.text('cd', 'COOLDOWN (76)', 230, 208, 110, 20)
    d.line([(615, -30), (615, 270), (555, 270), (555, 390)], DASHED, label='26')
    boundary_labels(d, 360, 590, 390)
    d.text('sys', '60 (temperature control loop)', 0, -20, 200, 20)
    return d


def fig6():
    d = Diagram('FIG 6', 'US6446444 FIG 6 - DSP board block diagram',
                'US6446444 sheet 6 of 7 (PDF p7)')
    d.node('dsp', 'DSP', 440, 40, 100, 560, ref=100, style='fontSize=20;')
    d.node('rs232', 'RS-232\nBUFFER', 210, 40, 150, 50, ref=102)
    d.text('port', 'RS-232\nSERIAL COMM\nPORT (104)', 20, 35, 120, 60)
    d.node('temp', 'TEMP SENSOR\nBUFFERS\nGAIN & OFFSET', 210, 130, 150, 90, ref=110)
    d.text('amb', 'AMBIENT (90)', 20, 135, 120, 20)
    d.text('hrej', 'HEAT REJECT (80)', 20, 165, 120, 20)
    d.text('cryo', 'CRYO (82)', 20, 195, 120, 20)
    d.node('lna', 'LNA POWER\nREGULATOR\nAND CURRENT SENSE', 210, 250, 150, 70, ref=112)
    d.text('lnas', "LNA'S (114)", 20, 275, 120, 20)
    d.node('fault', 'FAULT\nALARM RELAY\nFORM C', 210, 350, 150, 60, ref=116)
    d.text('falarm', 'FAULT ALARM (118)', 20, 370, 120, 20)
    d.node('led', 'LED DRIVE', 210, 440, 150, 40, ref=120)
    d.text('leds', "LED'S (122)", 20, 450, 120, 20)
    d.node('nvm', 'NON-\nVOLATILE\nMEMORY', 210, 520, 150, 60, ref=124)
    d.node('spi', 'SPI BUS\nINTERFACE', 600, 40, 150, 50, ref=128)
    d.text('aux', 'AUXILIARY (130)', 800, 50, 120, 20)
    d.node('cs', 'CURRENT\nSENSE', 600, 120, 160, 45, ref='134 (32)')
    d.node('ocl', 'OVER-\nCURRENT\nLOCKOUT', 600, 165, 160, 60, ref=136)
    d.node('opto', 'OPTO-\nISO', 600, 260, 100, 70, ref=132)
    d.node('hb', 'H-BRIDGE\nLEVEL SHIFT\nAND DRIVE', 700, 260, 140, 70, ref=30)
    d.dot('j', 880, 295)
    d.text('cooler', 'COOLER (8)', 910, 285, 90, 20)
    d.node('hz', 'HIGH-Z\nDIFF\nBUFFER', 590, 380, 100, 60, ref=146)
    d.node('ps', 'POWER\nSUPPLY', 650, 480, 110, 60, ref=144)
    d.text('p5v', '+5V', 565, 495, 50, 30)
    d.node('pf', 'POWER\nFILTER\nEMP/EMI', 960, 480, 110, 60, ref=140)
    d.text('mains', '27VDC\nMAINS', 1110, 490, 70, 40)
    d.dot('j2', 900, 510)
    d.text('fan', 'FAN & AUX (142)', 940, 395, 130, 20)
    d.edge('port', 'rs232', style=BIDIR)
    d.edge('rs232', 'dsp', style=BIDIR, entry=(0, 0.06))
    for name, frac in (('amb', 0.1), ('hrej', 0.43), ('cryo', 0.76)):
        d.edge(name, 'temp', entry=(0, frac))
    for index, frac in enumerate((0.2, 0.4, 0.6, 0.8)):
        d.edge('temp', 'dsp', '(106,108,12,13,16)' if index == 0 else '',
               exit_=(1, frac), entry=(0, (130 + 90 * frac - 40) / 560))
    d.edge('dsp', 'lna', exit_=(0, 0.425), entry=(1, 0.3))
    d.edge('lna', 'dsp', exit_=(1, 0.7), entry=(0, 0.475))
    d.edge('lna', 'lnas')
    d.edge('dsp', 'fault', exit_=(0, 0.6), entry=(1, 0.5))
    d.edge('fault', 'falarm')
    d.edge('dsp', 'led', exit_=(0, 0.75), entry=(1, 0.5))
    d.edge('led', 'leds')
    d.text('bus', 'SPI OR PARALLEL BUS (126)', 365, 500, 75, 40)
    d.edge('dsp', 'nvm', exit_=(0, 0.89), entry=(1, 0.5))
    d.edge('dsp', 'spi', exit_=(1, 0.05), entry=(0, 0.5))
    d.edge('spi', 'aux')
    d.edge('cs', 'dsp', exit_=(0, 0.5), entry=(1, 0.17))
    d.edge('ocl', 'dsp', exit_=(0, 0.5), entry=(1, 0.27))
    d.edge('dsp', 'opto', exit_=(1, 0.46), entry=(0, 0.5))
    d.edge('hb', 'j', style=PLAIN)
    d.edge('j', 'cooler', '28')
    d.edge('j', 'cs', '32', points=[(880, 142)], entry=(1, 0.5))
    d.edge('hz', 'dsp', exit_=(0, 0.5), entry=(1, 0.66))
    d.edge('mains', 'pf')
    d.edge('pf', 'j2', style=PLAIN)
    d.edge('j2', 'ps')
    d.edge('j2', 'hz', points=[(900, 410)])
    d.edge('j2', 'fan', points=[(900, 405)], entry=(0, 0.5))
    d.edge('ps', 'p5v')
    d.line([(700, -20), (700, 620)], DASHED)
    d.text('iso', 'ISOLATION BARRIER (138)', 640, -60, 120, 20)
    d.text('gnd_l', 'CHASSIS GROUND REF', 555, -30, 140, 20)
    d.text('gnd_r', 'INPUT GROUND REF', 705, -30, 130, 20)
    return d


def fig7():
    d = Diagram('FIG 7', 'US6446444 FIG 7 - Software pace-loop kernel 150',
                'US6446444 sheet 7 of 7 (PDF p8, top)')
    steps = [
        ('spin', 'SPIN == 0', 'WAIT HERE FOR END OF CYCLE (16.7 MS)\nINTERRUPTS OCCURING\n8 SAMPLES OF WAVEFORM'),
        ('rms', 'RMS', 'CALCULATE RMS OF SAMPLED DATA\nCOMPUTE POWER'),
        ('ctl', 'CONTROL\nALGORITHM', 'MEASURE SYSTEM PARAMETERS\nDETERMINE STATE OF MACHINE\nRECALCULATE NECESSARY DRIVE'),
        ('hk', 'HOUSEKEEPING', 'DISPATCH OF COMMUNICATIONS\nSET STATE MACHINE FUNCTIONS'),
    ]
    for index, (node_id, label, note) in enumerate(steps):
        y = 40 + index * 100
        d.node(node_id, label, 100, y, 130, 50)
        d.text(node_id + '_n', note, 270, y, 330, 55, shape='ltext')
    for (a, _, _), (b, _, _) in zip(steps, steps[1:]):
        d.edge(a, b)
    d.edge('hk', 'spin', points=[(40, 365), (40, 10), (165, 10)], exit_=(0, 0.5), entry=(0.5, 0))
    d.text('ref', '150', 200, 0, 40, 20)
    d.text('note', 'Spec text (col. 7-8): after HOUSEKEEPING the loop returns to spin mode; '
           'RS-232 communications (on-chip UART) and state machine functions are dispatched '
           'before returning to spin.', 100, 450, 500, 50, shape='ltext')
    return d


def fig8():
    d = Diagram('FIG 8', 'US6446444 FIG 8 - Software interrupts and clock dividers',
                'US6446444 sheet 7 of 7 (PDF p8, bottom)')
    rows = [('INT 1', 'FAILSAFE', 'WATCHDOG, LOCKOUT'),
            ('INT 2', 'TIMER 1', 'SINEWAVE GENERATION'),
            ('INT 3', 'TIMER 2', 'SPIN DECREMENT'),
            ('INT 4', 'NOT USED', ''),
            ('INT 5', 'COMM/SPI', 'ALL OTHER INTERRUPTS')]
    table = ('<table border="1" cellpadding="4" style="border-collapse:collapse;width:100%">'
             + ''.join(f'<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>' for a, b, c in rows)
             + '</table>')
    d.text('table', table, 100, 0, 420, 140, raw=True, shape='ltext')
    d.text('prio', 'Priority (spec col. 8): failsafe watchdog/lockout highest, sine '
           'generation next (keeps the sine shape intact), communications lowest.',
           540, 0, 300, 70, shape='ltext')
    d.node('clk', '20 MHZ\nCLOCK', 100, 200, 110, 50)
    d.node('d1302', 'DIVIDE\nBY 1302', 100, 300, 110, 50)
    d.node('d32', 'DIVIDE\nBY 32', 100, 400, 110, 50)
    d.text('end', '', 140, 490, 30, 20)
    d.edge('clk', 'd1302')
    d.edge('d1302', 'd32')
    d.edge('d32', 'end')
    d.text('n_clk', 'RAW SYSTEM CLOCK', 250, 210, 360, 30, shape='ltext')
    d.text('n_1302', 'INTERRUPT AT END OF COUNTDOWN\nPERFORM SINEWAVE UPDATE\n'
           '65.1 USEC OR 256 TIMES PER 60 HZ CYCLE', 250, 300, 360, 60, shape='ltext')
    d.text('n_32', 'INTERRUPT AT END OF COUNTDOWN\nPERFORM SPIN LOOP DECREMENT\nKICK WATCHDOG\n'
           'A/D CONVERSION ON SINEWAVE', 250, 400, 360, 75, shape='ltext')
    d.text('n_spec', 'Spec text (col. 8): the 65.1 µs interrupt updates the on-chip PWM with the '
           'next sine point; the /32 interval is 2.08 ms, when the cryocooler driving current 28 '
           'is sampled and the watchdog is pulsed (8 samples per 16.7 ms cycle).',
           640, 300, 300, 110, shape='ltext')
    return d


# ─── US6098409 (identical drawings in US6256999) ───

def fig2():
    d = Diagram('FIG 2', 'US6098409 FIG 2 - Two-loop temperature controller 30',
                'US6098409 sheet 1 of 25 (PDF p2); identical in US6256999')
    d.node('tref', 'T_REF', 0, 160, 80, 60)
    d.node('outer', 'OUTER\nLOOP', 130, 150, 90, 80, 'tri', ref=34)
    d.node('inner', 'INNER\nLOOP', 290, 40, 90, 80, 'tri', ref=32)
    d.node('cooler', 'CRYO\nCOOLER', 440, 45, 70, 70, 'circle', ref=40)
    d.node('cfs', 'COLD\nFINGER\nSENSOR', 570, 50, 110, 60, 'rbox', ref=16)
    d.node('css', 'COLD\nSTAGE\nSENSOR', 570, 260, 110, 60, 'rbox', ref=20)
    d.edge('tref', 'outer', '42', entry=(0, 0.35))
    d.edge('outer', 'inner', '36', entry=(0, 0.3))
    d.edge('inner', 'cooler', '38')
    d.edge('cooler', 'cfs', style=PLAIN)
    d.edge('cfs', 'inner', '33', exit_=(0.5, 1), entry=(0, 0.75), points=[(625, 150), (270, 150), (270, 100)])
    d.edge('css', 'outer', '44', entry=(0, 0.75), points=[(110, 290), (110, 210)])
    d.text('note', 'Arrowheads added to show signal direction; the patent draws plain lines.',
           0, 350, 500, 20, shape='ltext')
    return d


def fig3():
    d = Diagram('FIG 3', 'US6098409 FIG 3 - Temperature control system 50 (analog loops + microcontroller)',
                'US6098409 sheet 2 of 25 (PDF p3); identical in US6256999')
    up = dict(shape='circle')
    d.node('sref', 'SYSTEM\nTEMP\nREFERENCE (µP)', 0, 360, 120, 60, ref=78)
    d.node('pid', 'PID\nAMP', 180, 200, 90, 80, 'tri', ref=34)
    d.node('pd', 'PD\nAMP', 340, 340, 90, 80, 'tri', ref=32)
    d.node('sw', 'LIMITER\n(drawn as a\nclipping box)', 475, 345, 90, 70, ref=68)
    d.node('mult', '×', 610, 355, 50, 50, ref=70, **up)
    d.text('sine', '60Hz sine\n(µP)', 590, 260, 90, 40)
    d.node('drv', 'COOLER\nDRIVER', 700, 340, 100, 80, 'trap')
    d.node('cooler', 'CRYO\nCOOLER', 850, 340, 80, 80, ref=40, **up)
    d.text('th60', 'thermistor (60)', 730, 440, 100, 20)
    d.node('therm', 'THERMISTOR\nSENSOR\nPROCESSOR', 620, 480, 130, 60, ref=62)
    d.text('k64', 'knock sensor (64)', 950, 300, 120, 20)
    d.node('knock', '"KNOCK"\nSENSOR\nPROCESSOR', 1000, 440, 130, 60, ref=66)
    d.node('up66', 'µP', 1160, 452, 36, 36, 'circle')
    d.text('ctl68', '(unlabelled input -\nlimit setting)', 460, 270, 120, 35)
    d.text('d16', '▶| sensor diode\non cold finger', 840, 560, 110, 35)
    d.node('tsp16', 'TEMP\nSENSOR\nPROCESSOR', 980, 560, 130, 60, ref=16)
    d.node('up33', 'µP', 367, 470, 36, 36, 'circle')
    d.node('fcs', 'FILTER\nCOLD STAGE', 990, 190, 110, 50, 'rbox')
    d.text('dcs', '▶| sensor diode\non cold stage', 990, 110, 110, 35)
    d.node('tsp20', 'TEMP\nSENSOR\nPROCESSOR', 980, 10, 130, 60, ref=20)
    d.node('up44', 'µP', 140, 120, 36, 36, 'circle')
    d.node('mc', 'MICROCONTROLLER', 0, 620, 150, 60, ref=52)
    d.node('eprom', 'EPROM', 30, 730, 90, 40, ref=54)
    d.node('il', 'INTERFACE\nLOGIC', 230, 620, 140, 60, ref=56)
    d.node('adc', 'A/D\nCONVERTER', 250, 730, 100, 50, ref=58)
    d.node('upil', 'µP', 420, 632, 36, 36, 'circle')
    # Analog loop
    d.edge('sref', 'pd', '74', entry=(0, 0.5))
    d.edge('sref', 'pid', entry=(0, 0.7), points=[(150, 390), (150, 256)])
    d.edge('up44', 'pid', 'inverting', entry=(0, 0.3), points=[(158, 224)])
    d.edge('tsp20', 'up44', '44', exit_=(0, 0.5), points=[(158, 40)])
    d.edge('pid', 'pd', '36', entry=(0, 0.2), points=[(300, 240), (300, 356)])
    d.edge('up33', 'pd', 'inverting', entry=(0, 0.8), points=[(330, 488), (330, 404)])
    d.edge('tsp16', 'up33', '33', exit_=(0.5, 1), points=[(1045, 700), (385, 700)])
    d.edge('pd', 'sw', '38')
    d.edge('therm', 'sw', exit_=(0, 0.5), entry=(0.5, 1), points=[(520, 510)])
    d.edge('ctl68', 'sw')
    d.edge('sw', 'mult', '72')
    d.edge('sine', 'mult')
    d.edge('mult', 'drv')
    d.edge('drv', 'cooler')
    d.edge('cooler', 'th60', style=PLAIN)
    d.edge('th60', 'therm')
    d.edge('cooler', 'k64', style=PLAIN)
    d.edge('k64', 'knock', points=[(1065, 310)])
    d.edge('knock', 'up66', style=PLAIN)
    d.edge('cooler', 'd16', style=DASHED + PLAIN)
    d.edge('d16', 'tsp16', style=PLAIN)
    d.edge('cooler', 'fcs', style=DASHED + PLAIN)
    d.edge('fcs', 'dcs', style=DASHED + PLAIN)
    d.edge('dcs', 'tsp20', style=PLAIN)
    # Microcontroller section
    d.edge('mc', 'eprom', style=BIDIR)
    d.edge('mc', 'il', style=BIDIR)
    d.edge('il', 'upil', style=BIDIR)
    d.edge('il', 'adc', exit_=(0.4, 1), entry=(0.3, 0))
    d.edge('adc', 'il', exit_=(0.7, 0), entry=(0.6, 1))
    d.text('note', 'µP circles mark points the microcontroller sets or reads (spec: sensor '
           'readings, references and the 60 Hz drive are under processor control). Spec col. 5: '
           'limiter 68 clamps the inner-loop output 38; together with the knock sensor 64/66 '
           '(PZT/microphone, back-EMF or current analyzer detecting OVERSTROKES) it keeps the '
           'cooler from being overdriven, e.g. at start-up; with thermistor 60/62 it limits power '
           'when the cooler gets too hot. Multiplier 70 amplitude-modulates the 60 Hz drive with '
           'limiter output 72. PD amp 32 inputs: 36 (primary), reference 74, cold finger 33. '
           'See analysis/OVERSTROKE.md.',
           480, 740, 640, 110, shape='ltext')
    return d


def fig4():
    d = Diagram('FIG 4', 'US6098409 FIG 4 - Filter loop 100 (per-carrier heater control)',
                'US6098409 sheet 3 of 25 (PDF p4); identical in US6256999')
    d.node('tref', 'T_REF', 0, 200, 80, 60)
    d.node('fl', 'FILTER\nLOOP\n(PID)', 120, 190, 100, 80, 'tri', ref=100)
    d.node('pkg', 'HTSC filter carrier package (90), mounted on heat-sink 10', 300, 40, 420, 280, 'group')
    d.node('f1', 'glass\npads (92)\non mounting\nedge', 310, 80, 70, 220, ref=94)
    d.node('f2', 'glass\npads (92)\non mounting\nedge', 640, 80, 70, 220, ref=94)
    d.node('heat', 'THICK FILM\nRESISTORS (96)\ntwo in parallel', 420, 90, 170, 60)
    d.text('gnd', '⏚ GND', 610, 105, 60, 25)
    d.node('sens', 'TEMP\nSENSOR', 460, 220, 90, 50, ref=98)
    d.edge('tref', 'fl')
    d.edge('fl', 'heat', '90', points=[(250, 230), (250, 120)])
    d.edge('heat', 'gnd', style=PLAIN)
    d.edge('sens', 'fl', exit_=(0.5, 1), entry=(0.5, 1), points=[(505, 360), (170, 360)])
    d.text('note', 'Spec col. 6: PID controller 100 regulates the voltage across resistors 96 to fine-tune '
           'each carrier package temperature (range on the order of 1 degree); glass pads 92 on '
           'mounting edges 94 thermally isolate the package from the heat-sink. Also usable to tune '
           'filter centre frequency. Filter loop per US5818097.', 0, 380, 700, 50, shape='ltext')
    return d


def main():
    out6446 = os.path.join(ROOT, 'US6446444', 'diagrams')
    out6098 = os.path.join(ROOT, 'US6098409', 'diagrams')
    files = {
        os.path.join(out6446, 'fig5a_drive_current_loop.drawio'): [fig5a()],
        os.path.join(out6446, 'fig5b_temperature_control_loop.drawio'): [fig5b()],
        os.path.join(out6446, 'fig6_dsp_board_block.drawio'): [fig6()],
        os.path.join(out6446, 'fig7_pace_loop_kernel.drawio'): [fig7()],
        os.path.join(out6446, 'fig8_interrupts_and_clock.drawio'): [fig8()],
        os.path.join(out6098, 'fig2_two_loop_controller.drawio'): [fig2()],
        os.path.join(out6098, 'fig3_system_block.drawio'): [fig3()],
        os.path.join(out6098, 'fig4_filter_loop.drawio'): [fig4()],
    }
    for path, pages in files.items():
        save(path, pages)
        print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    main()
