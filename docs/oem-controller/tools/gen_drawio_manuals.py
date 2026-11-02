"""
@file gen_drawio_manuals.py
@brief Generate draw.io versions of the block/relay diagrams in the STI manuals.

SuperLink Rx manual: Figure 4 (p14), Figure 13 (p37).
SuperFilter guide: Figure 3 (p16).
The state-machine diagrams live in gen_drawio_states.py.

Run: python3 -I docs/oem-controller/tools/gen_drawio_manuals.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawio import Diagram, save  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIDIR = 'startArrow=block;startFill=1;'
PLAIN = 'endArrow=none;'
THICK = 'strokeWidth=2;'


def superlink_fig4():
    d = Diagram('SuperLink Fig 4', 'SuperLink Rx - Figure 4. Functional Block Diagram',
                'SuperLink Rx Operation and Installation Manual, PDF p14 (manual p9)')
    d.node('core', 'Cryogenic RF Enclosure (CoRE)', 220, -35, 360, 185, 'group')
    d.node('byp_in', 'Bypass\nRelay', 240, 60, 70, 50)
    d.node('fa', 'Filter and Amplifier\n[HTS filter] → [LNA]', 340, 45, 140, 80)
    d.node('byp_out', 'Bypass\nRelay', 500, 60, 70, 50)
    d.text('rf_in', 'RF Input\nFrom Antenna', 90, 65, 110, 40)
    d.text('rf_out', 'RF Output\nTo Base Station', 620, 65, 120, 40)
    d.node('cold', 'Cold\nFinger', 380, 150, 60, 80)
    d.node('cooler', 'Stirling Cycle\nCryogenic Cooler', 340, 245, 140, 80)
    d.text('amb', 'Ambient\nTemperature\nSensor', 690, 250, 100, 50)
    d.node('pca', 'Printed Circuit Assembly', 120, 360, 610, 370, 'group', style='align=center;')
    d.node('drv', 'Cooling\nMotor Driver', 150, 410, 90, 80)
    d.node('tsi', 'Thermal Sensor\nInterface', 560, 410, 130, 50)
    d.node('ctl', 'Control Electronics\n(Digital Signal Processor\n(DSP))', 320, 500, 170, 80)
    d.node('ser', 'Serial Interface', 540, 520, 120, 40)
    d.text('rs232', 'RS-232\nSerial\nDigital\nData', 770, 505, 70, 70)
    d.node('alarm', 'Alarm Relay', 540, 590, 120, 40)
    d.text('panel', 'To Alarm\nPanel', 770, 590, 80, 40)
    d.node('ps', 'Power Supply', 160, 650, 110, 60)
    d.text('reg', 'Regulated power\nto all functions', 330, 672, 130, 36)
    d.text('in27', '27 VDC\nInput Power', 0, 800, 90, 40)
    d.text('fuse', '~ Fuse ~', 170, 810, 70, 20)
    d.dot('jin', 290, 820)
    d.node('fan', 'Fan', 400, 780, 80, 80)
    d.edge('rf_in', 'byp_in')
    d.edge('byp_in', 'fa')
    d.edge('fa', 'byp_out')
    d.edge('byp_out', 'rf_out')
    d.edge('byp_in', 'byp_out', 'bypass path', exit_=(0.5, 0), entry=(0.5, 0), points=[(275, 20), (535, 20)])
    d.edge('fa', 'cold', style=PLAIN)
    d.edge('cold', 'cooler', style=PLAIN)
    d.edge('fa', 'tsi', 'Narrow Range and\nWide Range Cold Stage\nTemperature Sensor', exit_=(0.85, 1),
           entry=(0.75, 0), points=[(459, 180), (657, 180)])
    d.edge('cooler', 'tsi', entry=(0.25, 0), points=[(592, 285)])
    d.text('mts', 'Motor\nTemperature\nSensor', 486, 239, 100, 42)
    d.edge('amb', 'tsi', entry=(0.95, 0))
    d.edge('drv', 'cooler', 'Motor Drive\n60 Hz,\nVariable\nVoltage', exit_=(0.5, 0), entry=(0, 0.5),
           points=[(195, 285)])
    d.edge('drv', 'ctl', 'Motor current &\nvoltage sensors', exit_=(1, 0.75), entry=(0.3, 0),
           points=[(371, 470)])
    d.edge('tsi', 'ctl', exit_=(0.3, 1), entry=(0.75, 0), points=[(599, 480), (447, 480)])
    d.edge('ctl', 'ser', style=BIDIR)
    d.edge('ser', 'rs232', style=BIDIR)
    d.edge('ctl', 'drv', exit_=(0, 0.75), entry=(0, 0.6), points=[(130, 560), (130, 458)])
    d.text('pcd', 'Proportional control\ndrive', 140, 528, 175, 30, style='align=left;')
    d.edge('ctl', 'alarm', exit_=(1, 0.9), entry=(0, 0.5), points=[(510, 572), (510, 610)])
    d.edge('alarm', 'panel')
    d.edge('ps', 'ctl', exit_=(1, 0.15), entry=(120 / 170, 1), points=[(440, 659)])
    d.text('lcs', 'LNA current\nsensor', 446, 628, 90, 30, style='align=left;')
    d.edge('ps', 'ctl', exit_=(0.8, 0), entry=(40 / 170, 1), points=[(248, 612), (360, 612)])
    d.text('ivs', 'Input Voltage\nSensor', 254, 616, 100, 30, style='align=left;')
    d.edge('ps', 'reg', exit_=(1, 40 / 60), entry=(0, 0.5))
    d.edge('in27', 'fuse', style=PLAIN)
    d.edge('fuse', 'jin', style=PLAIN)
    d.edge('jin', 'fan')
    d.edge('jin', 'ps', points=[(290, 750), (140, 750), (140, 680)], entry=(0, 0.5))
    return d


def superlink_fig13():
    d = Diagram('SuperLink Fig 13', 'SuperLink Rx - Figure 13. Alarm Relay in Normal and Alarm States',
                'SuperLink Rx Operation and Installation Manual, PDF p37 (manual p32)')
    d.text('n_head', '<b>Alarm Relay Normal Operation Condition</b><br>NO = Open in normal operation'
           '<br>C = Common<br>NC = Closed in normal operation', 0, 0, 300, 80, raw=True, shape='ltext')
    d.text('n_mode', 'SuperLink Mode', 380, 0, 140, 20)
    d.text('n_c', 'C', 330, 40, 30, 20)
    d.dot('n_pivot', 420, 50)
    d.dot('n_no', 500, 20)
    d.dot('n_nc', 500, 80)
    d.text('n_nol', 'NO', 560, 10, 40, 20)
    d.text('n_ncl', 'NC', 560, 70, 40, 20)
    d.edge('n_c', 'n_pivot', style=PLAIN)
    d.edge('n_pivot', 'n_nc', style=PLAIN + 'edgeStyle=none;' + THICK)
    d.edge('n_no', 'n_nol', style=PLAIN)
    d.edge('n_nc', 'n_ncl', style=PLAIN)
    d.line([(0, 115), (620, 115)])
    d.text('f_head', '<b>Alarm Relay Fault Condition (Failure)</b><br>NO = Closed during fault condition'
           '<br>C = Common<br>NC = Open during fault condition<br><br><b>Note</b>: Alarm Relay, '
           'dry contacts, rated at 2-amps.', 0, 130, 300, 120, raw=True, shape='ltext')
    d.text('f_mode', 'Bypass (Fault) Mode', 370, 130, 160, 20)
    d.text('f_c', 'C', 330, 200, 30, 20)
    d.dot('f_pivot', 420, 210)
    d.dot('f_no', 500, 170)
    d.dot('f_nc', 500, 240)
    d.text('f_nol', 'NO', 560, 160, 40, 20)
    d.text('f_ncl', 'NC', 560, 230, 40, 20)
    d.edge('f_c', 'f_pivot', style=PLAIN)
    d.edge('f_pivot', 'f_no', style=PLAIN + 'edgeStyle=none;' + THICK)
    d.edge('f_no', 'f_nol', style=PLAIN)
    d.edge('f_nc', 'f_ncl', style=PLAIN)
    d.text('logic', 'Logic: relay de-energised/energised mapping is not stated in the manual. '
           'Normal (SuperLink/Regulate) = C-NC closed; any Bypass/fault state = C-NO closed. '
           'See manuals/superlink_states.md.', 0, 280, 620, 40, shape='ltext')
    return d


def superfilter_fig3():
    d = Diagram('SuperFilter Fig 3', 'SuperFilter - Figure 3. SuperFilter Functional Block Diagram',
                'SuperFilter Operation/Install Guide 830-0010A, PDF p16 (manual p11)')
    d.text('rf_in', 'RF Input\nFrom\nAntenna', 0, 72, 80, 56)
    d.node('byp_in', 'Bypass\nRelay', 110, 70, 90, 60)
    d.node('core', 'Cryogenic RF\nEnclosure (CoRE)', 250, 20, 160, 150, 'group')
    d.node('fa', 'Filter\nand\nAmplifier', 280, 68, 100, 64)
    d.node('byp_out', 'Bypass\nRelay and RF\nConfiguration\nOptions\n(See Note 1)', 470, 50, 120, 100)
    d.text('rf_out', 'RF Output to\nBase Station\nFront End\nFilter/LNA', 630, 65, 110, 70)
    d.node('cooler', 'Stirling\nCycle\nCryogenic\nCooler', 280, 240, 110, 90)
    d.node('osd', 'Overstroke\nDetector', 280, 330, 110, 45, style='fontStyle=1;strokeWidth=2;')
    d.node('drv', 'Cooling\nMotor\nDriver', 40, 250, 90, 70)
    d.node('tsi', 'Thermal\nSensor\nInterface', 600, 240, 100, 70)
    d.text('amb', 'Ambient\nTemperature\nSensor', 470, 320, 100, 50)
    d.node('ctl', 'Control\nElectronics\nand\nProcessor', 280, 450, 130, 100)
    d.node('ser', 'Serial\nInterface', 540, 465, 100, 60)
    d.text('modem', 'Digital\nData\nTo/From\nModem\n(See Note 2)', 670, 440, 90, 90)
    d.node('fans', 'Fans', 40, 560, 90, 60)
    d.node('alarm', 'Alarm\nRelay', 500, 610, 100, 60)
    d.text('contacts', 'To\nAlarm\nContacts', 650, 612, 80, 56)
    d.node('ps', 'Power\nSupply', 250, 730, 90, 60)
    d.text('reg', 'Regulated power\nto all functions', 380, 742, 130, 36)
    d.text('in27', '27 VDC\nInput\nPower', 0, 744, 70, 56)
    d.text('fuse', '~ Fuse ~', 100, 762, 70, 20)
    d.dot('jin', 185, 772)
    d.text('notes', 'Notes:\n1. RF Configuration Options include VGO and RO Options.\n'
           '2. External Modem is an option.', 0, 830, 600, 50, shape='ltext')
    d.edge('rf_in', 'byp_in')
    d.edge('byp_in', 'fa')
    d.text('rfin_lbl', 'RF In', 204, 80, 42, 18)
    d.edge('fa', 'byp_out', exit_=(1, 0.5), entry=(0, 0.5))
    d.text('rfout_lbl', 'RF Out', 414, 80, 50, 18)
    d.edge('byp_out', 'rf_out')
    d.edge('byp_in', 'byp_out', 'RF Bypass Path', exit_=(0.5, 0), entry=(0.5, 0), points=[(155, 0), (530, 0)])
    d.edge('fa', 'cooler', style=PLAIN)
    d.text('cf_lbl', 'Cold\nFinger', 336, 186, 50, 30, style='align=left;')
    d.edge('fa', 'tsi', 'WR and NR\nTemperature\nSensors', exit_=(1, 0.75), entry=(0.3, 0),
           points=[(430, 116), (430, 200), (630, 200)])
    d.edge('cooler', 'tsi', 'Motor\nTemperature Sensor', exit_=(1, 0.3889), entry=(0, 0.5))
    d.edge('amb', 'tsi', entry=(0.6, 1), points=[(660, 345)])
    d.edge('drv', 'cooler', '60 Hz, 66 VAC')
    d.edge('drv', 'ctl', 'Driver Current\n(Voltage) Sensor', exit_=(0.5, 1), entry=(0.3, 0),
           points=[(85, 400), (319, 400)])
    d.edge('osd', 'ctl', entry=(0.5, 0))
    d.edge('tsi', 'ctl', 'Multiplexed Sensor Signals', exit_=(0.5, 1), entry=(0.8, 0),
           points=[(650, 420), (384, 420)])
    d.edge('ctl', 'drv', exit_=(0, 0.5), entry=(0, 0.5), points=[(20, 500), (20, 285)])
    d.text('pc_lbl', 'Proportional Control\nTemperature/Cooler Driver', 70, 466, 170, 30)
    d.edge('ctl', 'ser', style=BIDIR + THICK)
    d.edge('ser', 'modem', style=BIDIR)
    d.edge('ctl', 'alarm', 'On/Off', exit_=(1, 0.85), entry=(0, 0.5))
    d.edge('alarm', 'contacts')
    d.edge('ps', 'ctl', exit_=(0.3, 0), entry=(0.3, 1), points=[(277, 600), (319, 600)])
    d.text('ipv_lbl', 'Input Power\nVoltage Sensor', 170, 615, 100, 30, style='align=right;')
    d.edge('ps', 'ctl', exit_=(0.7, 0), entry=(0.7, 1), points=[(313, 640), (371, 640)])
    d.text('lna_lbl', 'LNA\nCurrent\nSensors', 378, 580, 58, 44, style='align=left;')
    d.edge('ps', 'reg')
    d.edge('in27', 'fuse', style=PLAIN)
    d.edge('fuse', 'jin', style=PLAIN)
    d.edge('jin', 'ps', entry=(0, 0.6))
    d.edge('jin', 'fans', entry=(0.5, 1), points=[(185, 670), (85, 670)])
    return d


def main():
    out = os.path.join(ROOT, 'manuals', 'diagrams')
    files = {
        'superlink_fig4_functional_block.drawio': superlink_fig4(),
        'superlink_fig13_alarm_relay_states.drawio': superlink_fig13(),
        'superfilter_fig3_functional_block.drawio': superfilter_fig3(),
    }
    for name, diagram in files.items():
        save(os.path.join(out, name), [diagram])
        print('wrote manuals/diagrams/' + name)


if __name__ == '__main__':
    main()
