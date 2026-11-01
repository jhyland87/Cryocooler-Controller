"""
@file gen_drawio_states.py
@brief Generate the state-machine diagrams (draw.io).

- manuals/diagrams/superlink_state_machine.drawio   (SuperLink Rx Table 7 + p38)
- manuals/diagrams/superfilter_state_machine.drawio (SuperFilter Table 9 + text)
- analysis/diagrams/firmware_state_machine.drawio   (US6446444 TASKS.C StateMachine)

Solid arrows are transitions a source states; dashed arrows labelled
"inferred" are not stated anywhere and come from reading the tables.
Run: python3 -I docs/oem-controller/tools/gen_drawio_states.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawio import Diagram, save  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INFERRED = 'dashed=1;fontColor=#7f7f7f;strokeColor=#7f7f7f;'
FAULT = 'fillColor=#f8cecc;strokeColor=#b85450;'
NORMAL = 'fillColor=#d5e8d4;strokeColor=#82b366;'
BYPASS = 'fillColor=#fff2cc;strokeColor=#d6b656;'
OFF = 'fillColor=#e6e6e6;strokeColor=#666666;'


def state(d, node_id, title, body, x, y, w=230, h=110, style=''):
    """A state box: bold title line, then detail lines."""
    lines = body.split('\n')
    html = f'<b>{title}</b><hr size="1">' + '<br>'.join(lines)
    d.text(node_id, html, x, y, w, h, raw=True, shape='state',
           style='align=left;verticalAlign=top;spacingLeft=6;fontSize=10;' + style)


def superlink():
    d = Diagram('SuperLink states', 'SuperLink Rx - internal state machine (Table 7)',
                'SuperLink Rx Operation and Installation Manual PDF p39 (Table 7), p38, p13, p42')
    d.node('start', '', 20, 50, 20, 20, 'start')
    state(d, 's0', '0. Initial  (Bypass mode)',
          'Bypass relay: Bypass\nBYPASS(red) On, STATUS(green) On\n'
          'Initializes system; cooler motor to\nminimum power setting', 70, 10, style=BYPASS)
    state(d, 's1', '1. Cooldown  (Bypass mode)',
          'Bypass relay: Bypass\nBYPASS On, STATUS On\nMax motor drive from the cooler\'s\n'
          'cooldown profile. LNAs turn on when NR\ntemp is within operating bounds', 420, 10, 250, 120,
          style=BYPASS)
    state(d, 's2', '2. Regulate  (= SuperLink mode)',
          'Bypass relay: Normal\nBYPASS Off, STATUS On (steady green)\nRegulates cold stage temperature\n'
          'indefinitely', 860, 10, 250, 110, style=NORMAL)
    state(d, 's3', '3. Bypass (Fault)  (Bypass mode)',
          'Bypass relay: Bypass\nBYPASS On, STATUS Off\nContinues to regulate the cooler\ntemperature',
          860, 300, 250, 100, style=FAULT)
    state(d, 's4', '4. Shutdown (Fault)  (Bypass mode)',
          'Bypass relay: Bypass\nBYPASS On, STATUS Off\nCooler motor drive reduces to zero\nand is turned off',
          420, 300, 250, 100, style=FAULT)
    state(d, 's5', '5. Forced Bypass  (Bypass mode)',
          'Bypass relay: Bypass\nLEDs: "Flash if On" (at least one LED\nalways flashes); alarm relay in alarm\n'
          'Forces Bypass regardless of any\nother conditions', 1300, 150, 250, 120, style=BYPASS)
    d.edge('start', 's0')
    d.edge('s0', 's1', 'always\n(Table 7)')
    d.edge('s1', 's2', 'NR temp within operating\ntolerance for 300 s (LNA on)')
    d.edge('s2', 's3', 'Input Voltage out of bounds', exit_=(0.4, 1), entry=(0.4, 0))
    d.edge('s3', 's2', 'Input Voltage fault cleared\n(Automatic mode)', exit_=(0.7, 0), entry=(0.7, 1))
    d.edge('s2', 's4', 'driver current at an\nunacceptable level (p13)', exit_=(0.1, 1), entry=(0.8, 0),
           points=[(885, 250), (620, 250)])
    d.edge('s1', 's4', 'driver current fault (p13)\n[source state inferred]', exit_=(0.5, 1),
           entry=(0.5, 0), style=INFERRED)
    d.edge('s4', 's0', 'NR temp warmed out of its valid range\nAND faults cleared (Automatic mode)',
           exit_=(0, 0.5), entry=(0.5, 1), points=[(185, 350)])
    d.edge('s2', 's5', 'FORCED BYPASS button /\nportal (p42)', exit_=(1, 0.5), entry=(0.5, 0),
           points=[(1425, 65)])
    d.edge('s5', 's2', 'button pressed again → Regulate\n(steady green STATUS) (p42)', exit_=(0, 0.6),
           entry=(1, 0.8), points=[(1200, 222), (1200, 98)])
    d.text('notes', 'Footer of Table 7: "Regulate state = SuperLink mode. In all other states, the SL Rx '
           'is in Bypass mode." Each switch to Bypass activates the alarm relay (p13). '
           'p13 also lists out-of-range temperature or LNA current -> Bypass mode (target state not '
           'numbered). Install expectation: Regulate within 5 hours (p38); ~78 K operating '
           'temperature. Manual mode: the operator selects the state (p69). Forced Bypass is entered '
           'from any state (Table 7: "regardless of any other conditions"); only the Regulate '
           'arrows are drawn.', 20, 440, 1500, 60, shape='ltext')
    return d


def superfilter():
    d = Diagram('SuperFilter states', 'SuperFilter - Cool-Down State Table (Table 9) as a state machine',
                'SuperFilter Operation/Install Guide 830-0010A PDF p33 (Table 9), p32, p14-15, p62, p65')
    rows = [
        ('s0', '0 Initialize', 'Relay: Bypass\nFAULT On**, READY Off**\nInitial power up state', BYPASS),
        ('s1', '1 Idle', 'Relay: Bypass\nFAULT On RED, READY Off\nCold stage warm, Dewar not cooling', BYPASS),
        ('s2', '2 Coarse Cool-down', 'Relay: Bypass\nFAULT Fast flash RED, READY Off\nCooling, cold stage above 85 K', BYPASS),
        ('s3', '3 Fine Cool-down', 'Relay: Bypass\nFAULT Fast RED, READY Slow GREEN\nCooling, cold stage below 85 K', BYPASS),
        ('s4', '4 Over shoot', 'Relay: Bypass\nFAULT Fast RED, READY Fast GREEN\nColder than set point (nom. 78 K);\nintegrator settling', BYPASS),
        ('s5', '5 Settle', 'Relay: Normal\nFAULT Fast RED, READY Fast GREEN\nTemp settling; circuits switched\nto Normal', NORMAL),
        ('s6', '6 Baseline', 'Relay: Normal\nFAULT Off, READY On GREEN\nSettled; baseline data collected', NORMAL),
        ('s7', '7 Operating', 'Relay: Normal\nFAULT Off, READY On GREEN\nOperating; checked for deviations\nfrom the baseline', NORMAL),
    ]
    d.node('start', '', 20, 50, 20, 20, 'start')
    for index, (node_id, title, body, style) in enumerate(rows):
        column, row = index % 4, index // 4
        state(d, node_id, title, body, 70 + column * 360, 10 + row * 230, 240, 110, style=style)
    state(d, 's8', '8 Fault', 'Relay: Bypass\nFAULT On RED, READY Off\nAlarm relay is switched on', 610, 480, 240, 90,
          style=FAULT)
    labels = {
        ('s0', 's1'): ('power-up sequence', True),
        ('s1', 's2'): ('cooling begins\n[condition not stated]', True),
        ('s2', 's3'): ('cold stage < 85 K\n(WR sensor, p63)', False),
        ('s3', 's4'): ('cold stage colder than\nset point (~78 K)', False),
        ('s4', 's5'): ('integrator settled\n[criterion not stated]', True),
        ('s5', 's6'): ('temperature settled\n[criterion not stated]', True),
        ('s6', 's7'): ('baseline collected\n[duration not stated]', True),
    }
    for (a, b), (label, inferred) in labels.items():
        same_row = rows.index(next(r for r in rows if r[0] == a)) // 4 == rows.index(next(r for r in rows if r[0] == b)) // 4
        kwargs = {} if same_row else {'exit_': (0.5, 1), 'entry': (0.5, 0), 'points': [(1270, 160), (1270, 190), (190, 190)]}
        d.edge(a, b, label, style=INFERRED if inferred else '', **kwargs)
    d.edge('start', 's0')
    d.edge('s7', 's8', 'LNA current changes ±20% from\ninitial value → "System State 8" (p65)',
           exit_=(0.5, 1), entry=(1, 0.5), points=[(1270, 525)])
    d.edge('s6', 's8', 'input power / driver current / CoRE temp\nunacceptable → Bypass + alarm (p14-15)\n'
           '[mapping to state 8 inferred]', exit_=(0.3, 1), entry=(0.3, 0), style=INFERRED,
           points=[(862, 420), (682, 420)])
    d.text('fb', '<b>Forced Bypass (overlay, any state)</b><br>SET FORCED BYPASS ON → relay Bypass, READY '
           'slow-flash AMBER in all states, alarm relay in alarm condition. SET FORCED BYPASS OFF → '
           'returns (READY steady green when cooled). (p14, p36, p62)', 70, 480, 380, 90, raw=True,
           shape='note')
    d.text('legend', 'Notes (Table 9): * Fast Flash = twice per second, Slow Flash = once per second. '
           '** On power up both FAULT and READY momentarily illuminate AMBER during state 0. '
           'Exit from state 8 is not stated. Typical cooldown 3-5 h; Normal expected within 5 h (p32). '
           'Grey dashed arrows = order of the table only.', 20, 600, 1300, 40, shape='ltext')
    return d


def firmware():
    d = Diagram('Firmware states', 'US6446444 firmware - StateMachine() (TASKS.C)',
                'US6446444/code/TASKS.C lines 559-1066; runs 60 times/s; advances only in automatic mode '
                '(SMBF_MODE clear)')
    out = 'LEDs: {}\nFAULT relay {}, BYPASS relay {}, LNA {}'
    d.node('start', '', 20, 60, 20, 20, 'start')
    state(d, 'init', 'SM_INIT (0)  L599',
          out.format('FAULT on, READY on', 'ON', 'ON', 'off') + '\nph0 set IO, start timer\nph1 wait 15 s\n'
          'ph2 → IDLE if automatic', 70, 10, 260, 130, style=BYPASS)
    state(d, 'idle', 'SM_IDLE (1)  L651',
          out.format('FAULT on, READY off', 'ON', 'ON', 'off') + '\nph0 ImSp=0, MotorOn(TRUE)\n'
          'ph1 ImSp += POWER_INCR each second\n    until ImSp ≥ ImLoLimit (~40 W)\n'
          'ph2 wait for Tcsw in range', 470, 10, 270, 150, style=BYPASS)
    state(d, 'cool', 'SM_COOLDOWN (2)  L714',
          out.format('FAULT toggle, READY toggle', 'ON', 'ON', 'off') + '\nph0 reset PID state\n'
          'ph1 m,b of cooldown line from Tamb\n    (90 W, 48 V cooler)\n'
          'ph2 ramp ImSp += 0x456/pass (~3App/min)\n    while Tcsn<TcSp and ImSp ≤ CoolDownSp\n'
          'ph3 ImSp = CoolDownSp() while Tcsn<TcSp\n    and CoolDownSp < PidSp\n'
          'ph4 ImSp = PidSp(); → CONTROL if auto', 960, 10, 290, 210, style=BYPASS)
    state(d, 'ctl', 'SM_CONTROL (3)  L842',
          out.format('FAULT off, READY on', 'OFF', 'OFF', 'ON') + '\nImSp = PidSp() every pass\n'
          'ph1 wait 5 min, ph2 enable Tcsn median filter\n'
          'ph3 |TcSp-Tcsn| > 200 → TCSP error,\n    RELAY_OFF(BYPASS); else RELAY_ON(BYPASS)*\n'
          'Ilna outside [Lo,Hi] → ILNA flag only', 960, 320, 290, 170, style=NORMAL)
    state(d, 'pd', 'SM_POWERDOWN (4)  L933',
          out.format('FAULT on, READY off', 'ON', 'ON', 'off') + '\nph1 ImSp -= POWER_INCR every 1/16 s\n'
          'at 0: MotorOn(FALSE)\nph2 → FINAL (any mode)', 470, 320, 270, 130, style=FAULT)
    state(d, 'fin', 'SM_FINAL (5)  L993',
          out.format('FAULT on, READY off', 'ON', 'ON', 'off') + '\n"off state, either by choice\n'
          '(manual mode) or system error"', 70, 320, 260, 120, style=OFF)
    d.edge('start', 'init')
    d.edge('init', 'idle', '15 s elapsed\nAND automatic')
    d.edge('idle', 'cool', 'Tcsw in range\n(TcswHiTemp<Tcsw<TcswLoTemp)\nAND automatic; clears TCSW error')
    d.edge('cool', 'ctl', 'Tcsn reached TcSp, or\nCoolDownSp ≥ PidSp\n(→ ph4) AND automatic')
    d.edge('cool', 'idle', 'Tcsw out of range\n→ set TCSW error', exit_=(0, 0.9), entry=(1, 0.9),
           points=[(850, 199), (850, 145)])
    d.edge('ctl', 'idle', 'Tcsw out of range\n→ set TCSW error', exit_=(0, 0.2), entry=(0.85, 1),
           points=[(700, 354)])
    d.edge('pd', 'fin', 'ImSp reached 0,\nmotor off')
    d.edge('fin', 'init', 'TREJ error AND Trej > TrejLoTemp, or\nVIN error AND VinLo < Vin < VinHi\n'
           '→ clear flag', exit_=(0.5, 0), entry=(0.5, 1))
    d.node('any', 'ANY STATE\n(checked first, every pass, L565-575)', 470, 560, 270, 60, style=FAULT)
    d.edge('any', 'pd', 'Trej < TrejHiTemp (motor too hot;\nthermocouple has neg. tempco) → TREJ error\n'
           'OR Vin outside (VinLo, VinHi) → VIN error')
    d.text('manual', '<b>Manual mode</b> (serial S6 = 1): states only advance when automatic. S8 sets '
           'SmCurrentState.Phase directly (0-5), S7 sets ImSp, S9/S10/S11 set LNA, FAULT and BYPASS '
           'relay bits. An unknown state → SM_POWERDOWN (L1048).', 960, 540, 380, 75, raw=True, shape='note')
    d.text('relay', '* Relay macros (L128-129): RELAY_ON(x) CLEARS the status bit, RELAY_OFF(x) SETS it; '
           'OperationMonitor copies the bits to port D every 500 ms (L1280). So in SM_CONTROL phase 3 a '
           'small tracking error re-issues the same call every bypass state uses. Read literally, that '
           'looks inverted; check it against the hardware polarity. Sensor counts rise as temperature '
           'falls (TCSW_300K=230, TCSW_70K=965), so "Tcsn < TcSp" means warmer than the set point.',
           70, 650, 1250, 55, shape='ltext')
    return d


def main():
    files = {
        os.path.join(ROOT, 'manuals', 'diagrams', 'superlink_state_machine.drawio'): superlink(),
        os.path.join(ROOT, 'manuals', 'diagrams', 'superfilter_state_machine.drawio'): superfilter(),
        os.path.join(ROOT, 'analysis', 'diagrams', 'firmware_state_machine.drawio'): firmware(),
    }
    for path, diagram in files.items():
        save(path, [diagram])
        print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    main()
