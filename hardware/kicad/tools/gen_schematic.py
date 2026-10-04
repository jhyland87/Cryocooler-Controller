"""Generates the Cryocooler controller KiCad project (root + hierarchical sheets).

Run: python3 hardware/kicad/tools/gen_schematic.py
GPIO assignments follow include/config/pin_config.h.
"""
import json
import sys
from pathlib import Path

import kicadgen
from kicadgen import Sheet, next_ref, new_uuid, q, fmt, GLOBAL_NETS, POWER_SYMBOLS

ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT = 'cryocooler'

# ── footprints ───────────────────────────────────────────────────────────
R0603 = 'Resistor_SMD:R_0603_1608Metric'
R1206 = 'Resistor_SMD:R_1206_3216Metric'
R2512 = 'Resistor_SMD:R_2512_6332Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
C1210 = 'Capacitor_SMD:C_1210_3225Metric'
CP_ELEC = 'Capacitor_SMD:CP_Elec_8x10'
CP_TANT = 'Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B'
LED0603 = 'LED_SMD:LED_0603_1608Metric'
LED1206 = 'LED_SMD:LED_1206_3216Metric'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
KK3 = 'Connector_Molex:Molex_KK-254_AE-6410-03A_1x03_P2.54mm_Vertical'
KK4 = 'Connector_Molex:Molex_KK-254_AE-6410-04A_1x04_P2.54mm_Vertical'
XH2 = 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'
TERM2 = 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'
INDUCTOR = 'Inductor_SMD:L_Bourns_SRN8040TA'

PITCH = 12.7


def grid(value):
    return round(value / 1.27) * 1.27


# ── component helpers ────────────────────────────────────────────────────
# Discretes are auto-placed beside the pin named by near=(part, pin); ICs/connectors are fixed.
def res(sh, value, a, b, near=None, fp=R0603, pose=None, **props):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add('Device:R_US', next_ref('R'), value, px, py, rot=prot, footprint=fp, props=props, near=near,
                  auto=pose is None)
    sh.connect(part, '1', a)
    sh.connect(part, '2', b)
    return part


def cap(sh, value, a, b='GND', near=None, fp=None, pose=None):
    fp = fp or (C0603 if value in ('100nF', '10nF', '1nF') else C0805 if value in ('1uF', '2.2uF', '4.7uF', '10uF')
                else C1206)
    px, py, prot = pose or (0, 0, 0)
    part = sh.add('Device:C', next_ref('C'), value, px, py, rot=prot, footprint=fp, near=near, auto=pose is None)
    sh.connect(part, '1', a)
    sh.connect(part, '2', b)
    return part


def cap_pol(sh, value, a, b='GND', near=None, fp=CP_TANT, pose=None):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add('Device:C_Polarized', next_ref('C'), value, px, py, rot=prot, footprint=fp, near=near,
                  auto=pose is None)
    sh.connect(part, '1', a)
    sh.connect(part, '2', b)
    return part


def led(sh, value, anode, cathode, near=None, fp=LED0603):
    part = sh.add('Device:LED', next_ref('D'), value, 0, 0, footprint=fp, near=near)
    sh.connect(part, '2', anode)
    sh.connect(part, '1', cathode)
    return part


def diode(sh, lib_id, value, anode, cathode, fp, near=None, pose=None):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(lib_id, next_ref('D'), value, px, py, rot=prot, footprint=fp, near=near, auto=pose is None)
    sh.connect(part, '2', anode)
    sh.connect(part, '1', cathode)
    return part


def nfet(sh, value, gate, drain, source='GND', near=None, fp=SOT23, pose=None):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add('Transistor_FET:BSS138', next_ref('Q'), value, px, py, rot=prot, footprint=fp, near=near,
                  auto=pose is None)
    sh.connect(part, '1', gate)
    sh.connect(part, '3', drain)
    sh.connect(part, '2', source)
    return part


def conn(sh, lib_id, value, x, y, nets, fp, rot=0):
    """Generic connector; nets maps pin number -> net (None = no-connect)."""
    part = sh.add(lib_id, next_ref('J'), value, x, y, rot=rot, footprint=fp, auto=False)
    for number, net in nets.items():
        if net is None:
            sh.nc(part, number)
        else:
            sh.connect(part, number, net)
    return part


def ic(sh, lib_id, value, x, y, nets, ref_prefix='U', fp=None, **kwargs):
    """Fixed IC with pin->net map; None means no-connect."""
    part = sh.add(lib_id, next_ref(ref_prefix), value, x, y, footprint=fp, auto=False, **kwargs)
    for number, net in nets.items():
        if net is None:
            sh.nc(part, number)
        else:
            sh.connect(part, number, net)
    return part


def aux(sh, lib_id, prefix, value, nets, near=None, fp=None, pose=None):
    """Auto-placed multi-pin discrete (reference, switch, fuse...); pose=(x, y, rot) fixes it instead."""
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(lib_id, next_ref(prefix), value, px, py, rot=prot, footprint=fp, near=near, auto=pose is None)
    for number, net in nets.items():
        if net is None:
            sh.nc(part, number)
        else:
            sh.connect(part, number, net)
    return part


def decouple(sh, near, rail, values=('100nF',), gnd='GND'):
    """Decoupling caps from a rail to ground, each anchored at the IC pin."""
    return [cap(sh, value, rail, gnd, near=near) for value in values]



def build_mcu(sh):
    """Hand-laid root sheet: ESP32 in the middle, boot/reset circuits left, USB-C right, I2C pull-ups below."""
    sh.handwired = True
    sh.note('ESP32-S3-WROOM-2-N32R16V: 32 MB octal flash + 16 MB octal PSRAM (GPIO26-37 reserved by module)', 30, 15)
    sh.note('GPIO map follows include/config/pin_config.h', 30, 21)
    esp = place_ic(sh, 'RF_Module:ESP32-S3-WROOM-2', 'ESP32-S3-WROOM-2-N32R16V', 150, 100, None)
    left = {'39': 'IMU_CS', '38': 'IMU_INT1', '4': 'NTC_ADC', '5': 'MCP4921_CS', '6': 'AMP_REM_EN',
            '7': 'AD9833_FSYNC', '12': 'SDA', '17': 'SCL', '18': 'PWR_KILL', '19': 'ACS_SCK', '20': 'ACS_MOSI',
            '21': 'ACS_MISO', '22': 'LED_FAULT', '8': 'LED_READY', '9': 'PWR_INT'}
    right = {'10': 'ACS_CS', '11': 'FLOW_TACH', '23': 'FAN_ALERT', '31': 'STATUS_RGB', '32': 'IMU_INT2',
             '33': 'SPI_MISO', '34': 'SPI_MOSI', '35': 'SPI_SCK'}
    for pin, net in left.items():
        net_label(sh, net, spur(sh, esp, pin, 3), 180, is_global=True)
    for pin, net in right.items():
        net_label(sh, net, spur(sh, esp, pin, 3), 0, is_global=True)
    for pin in ('15', '16', '24', '25', '26', '28', '29', '30', '36', '37'):
        sh.nc(esp, pin)
    # supplies
    vdd = pin_cell(esp, '2')
    wire(sh, vdd, (vdd[0], 72))
    rail_symbol(sh, '+3V3', (vdd[0], 72))
    place_blocks(sh, [('ESP32-S3 DECOUPLING CAPACITORS', '+3V3', ('10uF', '100nF'))], 190, 38)
    gnd = spur(sh, esp, '1', 2)
    ground(sh, gnd)
    # EN: RC power-on reset plus RESET switch, drawn above the module
    en = pin_cell(esp, '3')
    wire(sh, en, (136, en[1]), (136, 70), (108, 70))
    vres(sh, '10k', 124, 64)
    rail_symbol(sh, '+3V3', (124, 64))
    vcap(sh, '1uF', 116, 70)
    drop_ground(sh, (116, 76), 0)
    sw_reset = sh.add('Switch:SW_Push', next_ref('SW'), 'RESET', 108 * 1.27, 74 * 1.27, rot=270, auto=False,
                      footprint='Button_Switch_SMD:SW_SPST_TL3342')
    wire(sh, (108, 70), pin_cell(sw_reset, '1'))
    ground(sh, pin_cell(sw_reset, '2'))
    # BOOT (GPIO0)
    boot = pin_cell(esp, '27')
    wire(sh, boot, (108, boot[1]))
    vres(sh, '10k', 126, boot[1] - 6)
    rail_symbol(sh, '+3V3', (126, boot[1] - 6))
    vcap(sh, '100nF', 116, boot[1])
    drop_ground(sh, (116, boot[1] + 6), 0)
    sw_boot = sh.add('Switch:SW_Push', next_ref('SW'), 'BOOT', 108 * 1.27, (boot[1] + 4) * 1.27, rot=270, auto=False,
                     footprint='Button_Switch_SMD:SW_SPST_TL3342')
    wire(sh, (108, boot[1]), pin_cell(sw_boot, '1'))
    ground(sh, pin_cell(sw_boot, '2'))
    # I2C pull-ups (3.3 V, 100 kHz bus)
    for row, net in ((134, 'SDA'), (140, 'SCL')):
        rail_symbol(sh, '+3V3', (40, row))
        hres(sh, '4.7k', 43, row)
        wire(sh, (46, row), (48, row))
        net_label(sh, net, (48, row), 0, is_global=True)
    # USB-C: data only, VBUS does not power the board
    wire(sh, pin_cell(esp, '13'), (180, 90), (180, 98), (196, 98))
    wire(sh, pin_cell(esp, '14'), (178, 92), (178, 100), (196, 100))
    esd = sh.add('Power_Protection:USBLC6-2SC6', next_ref('U'), 'USBLC6-2SC6', 200 * 1.27, 100 * 1.27, rot=180,
                 auto=False, footprint='Package_TO_SOT_SMD:SOT-23-6')
    usb = sh.add('Connector:USB_C_Receptacle_USB2.0_16P', next_ref('J'), 'USB_C', 240 * 1.27, 100 * 1.27, mirror=True,
                 auto=False, footprint='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal')
    d_minus_esd, d_plus_esd = pin_cell(esd, '3'), pin_cell(esd, '1')
    wire(sh, d_minus_esd, pin_cell(usb, 'A7'))
    wire(sh, pin_cell(usb, 'B7'), (224, pin_cell(usb, 'B7')[1]), (224, pin_cell(usb, 'A7')[1]))
    a6, b6 = pin_cell(usb, 'A6'), pin_cell(usb, 'B6')
    wire(sh, d_plus_esd, (216, d_plus_esd[1]), (216, a6[1]), a6)
    wire(sh, b6, (224, b6[1]), (224, a6[1]))
    gnd_esd = pin_cell(esd, '2')
    wire(sh, gnd_esd, (gnd_esd[0], gnd_esd[1] - 4), (gnd_esd[0] + 4, gnd_esd[1] - 4))
    ground(sh, (gnd_esd[0] + 4, gnd_esd[1] - 4))
    vbus_esd = pin_cell(esd, '5')
    wire(sh, vbus_esd, (vbus_esd[0], vbus_esd[1] + 3))
    net_label(sh, 'USB_VBUS', (vbus_esd[0], vbus_esd[1] + 3), 0)
    vbus = pin_cell(usb, 'A4')
    wire(sh, vbus, (226, vbus[1]), (226, 84), (205, 84))
    net_label(sh, 'USB_VBUS', (205, 84), 180)
    vcap(sh, '4.7uF', 210, 84, fp=C0805)
    drop_ground(sh, (210, 90), 0)
    rail_flag(sh, (218, 84))
    cc1, cc2 = pin_cell(usb, 'A5'), pin_cell(usb, 'B5')
    wire(sh, cc1, (225, cc1[1]))
    hres(sh, '5.1k', 222, cc1[1])
    ground(sh, (219, cc1[1]))
    wire(sh, cc2, (215, cc2[1]))
    hres(sh, '5.1k', 212, cc2[1])
    ground(sh, (209, cc2[1]))
    for pin in ('A8', 'B8'):
        sh.nc(usb, pin)
    ground(sh, spur(sh, usb, 'A1', 2))
    for pin in ('A12', 'B1', 'B12'):
        pass
    wire(sh, pin_cell(usb, 'SH'), (pin_cell(usb, 'SH')[0], pin_cell(usb, 'SH')[1] + 2))
    ground(sh, (pin_cell(usb, 'SH')[0], pin_cell(usb, 'SH')[1] + 2))


def build_power_input(sh):
    """Hand-laid: screw terminal -> fuse -> VIN rail with TVS and bulk/bypass caps."""
    sh.handwired = True
    sh.note('12 V input from a Dell XYK93 (DPS-2000EB class, ~12.2 V, ~160 A available): use the main 12 V rail with PS_ON held low.', 20, 15)
    sh.note('F1 is a backup only: add an inline high-breaking-capacity fuse (7.5-10 A) at the PSU end. Reverse polarity: TVS forward-clamps and blows the fuse.', 20, 21)
    j_in = sh.add('Connector:Screw_Terminal_01x02', next_ref('J'), '12V IN', 30 * 1.27, 60 * 1.27, rot=0, mirror=True,
                  auto=False, footprint=TERM2)
    raw = pin_cell(j_in, '1')
    fuse = aux(sh, 'Device:Fuse', 'F', '5A backup', {}, pose=at(46, 60, 90), fp='Fuse:Fuse_1812_4532Metric')
    wire(sh, raw, pin_cell(fuse, '1'))
    rail_flag(sh, (raw[0] + 5, raw[1]))
    gnd = spur(sh, j_in, '2', 2)
    ground(sh, gnd)
    rail_flag(sh, (gnd[0] + 3, gnd[1]))
    wire(sh, gnd, (gnd[0] + 3, gnd[1]))
    out = pin_cell(fuse, '2')
    wire(sh, out, (92, out[1]))
    rail_symbol(sh, 'VIN', (92, out[1]))
    rail_flag(sh, (86, out[1]))
    diode(sh, 'Device:D_TVS', 'SMBJ16A', '', '', 'Diode_SMD:D_SMB', pose=at(60, 63, 270))
    drop_ground(sh, (60, 66), 0)
    cap_pol(sh, '100uF/25V', '', '', pose=at(70, 63), fp=CP_ELEC)
    drop_ground(sh, (70, 66), 0)
    cap(sh, '100nF', '', '', pose=at(80, 63), fp=C0805)
    drop_ground(sh, (80, 66), 0)


def build_power_button(sh):
    """Hand-laid: LTC2954 controller top left, P-FET power switch right, power-state LED bridge below."""
    sh.handwired = True
    sh.note('LTC2954-2: tap PB = on, hold = off. EN# drives the P-FET gate; KILL# from GPIO10 (active low, 100 ms pulse).', 20, 15)
    sh.note('PWR_ON follows the +3V3 rail: on = green, standby = red. CL25 (25 mA) feeds both legs, ~9 mA reaches the LED, ~25 mA total from VIN in standby', 20, 21)
    u = place_ic(sh, 'cryocooler:LTC2954CTS8-2', 'LTC2954CTS8-2', 60, 60, 'Package_TO_SOT_SMD:SOT-23-8')
    # supply with bypass above the controller
    vin_pin = pin_cell(u, '1')
    wire(sh, vin_pin, (48, vin_pin[1]), (48, 46), (44, 46))
    rail_symbol(sh, 'VIN', (44, 46))
    place_blocks(sh, [('LTC2954 DECOUPLING CAPACITORS', 'VIN', ('100nF',))], 170, 40)
    drop_ground(sh, pin_cell(u, 'GND') if False else pin_cell(u, '4'), 2)
    # push button, panel connector, ONT left open
    pb = pin_cell(u, '2')
    wire(sh, pb, (36, pb[1]))
    sw = sh.add('Switch:SW_Push', next_ref('SW'), 'POWER', 30 * 1.27, pb[1] * 1.27, mirror=True, auto=False,
                footprint='Button_Switch_SMD:SW_SPST_TL3342')
    wire(sh, (36, pb[1]), pin_cell(sw, '1'))
    wire(sh, pin_cell(sw, '2'), (24, pb[1]))
    ground(sh, (24, pb[1]))
    j_panel = sh.add('Connector_Generic:Conn_01x02', next_ref('J'), 'PANEL BUTTON', 24 * 1.27, 66 * 1.27, rot=0,
                     mirror=True, auto=False, footprint=XH2)
    wire(sh, pin_cell(j_panel, '1'), (36, 66), (36, pb[1]))
    wire(sh, pin_cell(j_panel, '2'), (pin_cell(j_panel, '2')[0] + 2, pin_cell(j_panel, '2')[1]))
    ground(sh, (pin_cell(j_panel, '2')[0] + 2, pin_cell(j_panel, '2')[1]))
    sh.nc(u, '3')
    # KILL#: 220k to the 5 V shunt reference, 10k from the MCU
    kill = pin_cell(u, '8')
    wire(sh, kill, (80, kill[1]))
    vres(sh, '220k', 80, 50)
    vres(sh, '10k', 80, 56)
    wire(sh, (80, 62), (84, 62))
    net_label(sh, 'PWR_KILL', (84, 62), 0, is_global=True)
    wire(sh, (80, 50), (80, 44), (88, 44))
    vres(sh, '82k', 80, 38)
    rail_symbol(sh, 'VIN', (80, 38))
    ref = aux(sh, 'Reference_Voltage:LM4040DBZ-5', 'U', 'LM4040DBZ-5', {}, pose=at(88, 47, 90), fp=SOT23)
    sh.nc(ref, '3')
    ground(sh, (88, 50))
    # PDT cap, EN# to the P-FET gate, INT# with pull-up
    pdt = pin_cell(u, '7')
    wire(sh, pdt, (74, pdt[1]))
    vcap(sh, '100nF', 74, pdt[1])
    drop_ground(sh, (74, pdt[1] + 6), 0)
    en, intr = pin_cell(u, '6'), pin_cell(u, '5')
    wire(sh, en, (72, en[1]), (72, 70), (146, 70))
    wire(sh, intr, (71, intr[1]), (71, 76), (81, 76))
    hres(sh, '10k', 84, 76)
    rail_symbol(sh, '+3V3', (87, 76))
    wire(sh, (76, 76), (76, 80))
    net_label(sh, 'PWR_INT', (76, 80), 0, is_global=True)
    # high-side P-FET switch
    q1 = sh.add('Transistor_FET:IRF4905', next_ref('Q'), 'IRF4905S', 150 * 1.27, 70 * 1.27, rot=180, mirror=True,
                auto=False, footprint='Package_TO_SOT_SMD:TO-263-3_TabPin2')
    wire(sh, pin_cell(q1, '1'), (146, 70))
    vres(sh, '100k', 130, 64)
    rail_symbol(sh, 'VIN', (130, 64))
    wire(sh, pin_cell(q1, '3'), (pin_cell(q1, '3')[0], 62))
    rail_symbol(sh, 'VIN', (pin_cell(q1, '3')[0], 62))
    drain = pin_cell(q1, '2')
    wire(sh, drain, (drain[0], drain[1] + 2), (drain[0] + 4, drain[1] + 2), (drain[0] + 8, drain[1] + 2))
    rail_symbol(sh, 'VSW', (drain[0] + 4, drain[1] + 2))
    rail_flag(sh, (drain[0] + 8, drain[1] + 2))
    # power-state LED: CL25 limiter feeding a bi-colour LED in an H-bridge of N-FETs
    cl = place_ic(sh, 'cryocooler:CL25N8-G', 'CL25N8-G', 44, 110, 'Package_TO_SOT_SMD:SOT-89-3')
    va, vb = pin_cell(cl, '1'), pin_cell(cl, '2')
    wire(sh, va, (va[0] - 2, va[1]))
    rail_symbol(sh, 'VIN', (va[0] - 2, va[1]))
    sh.nc(cl, '3')
    wire(sh, vb, (60, vb[1]), (90, vb[1]))
    vres(sh, '330', 60, vb[1])
    vres(sh, '330', 90, vb[1])
    led = aux(sh, 'Device:LED_Dual_Bidirectional', 'D', 'RED/GREEN', {}, pose=at(75, 114), fp=LED1206)
    wire(sh, (60, 114), pin_cell(led, '2'))
    wire(sh, pin_cell(led, '1'), (90, 114))
    q_a = nfet(sh, 'BSS138', '', '', pose=at(58, 128))
    wire(sh, (60, 114), pin_cell(q_a, '3'))
    ground(sh, spur(sh, q_a, '2', 2))
    q_b = sh.add('Transistor_FET:BSS138', next_ref('Q'), 'BSS138', 92 * 1.27, 128 * 1.27, rot=0, mirror=True,
                 auto=False, footprint=SOT23)
    wire(sh, (90, 114), pin_cell(q_b, '3'))
    ground(sh, spur(sh, q_b, '2', 2))
    q_c = sh.add('Transistor_FET:BSS138', next_ref('Q'), 'BSS138', 30 * 1.27, 128 * 1.27, rot=0, mirror=True,
                 auto=False, footprint=SOT23)
    ground(sh, spur(sh, q_c, '2', 2))
    node = (44, 128)
    wire(sh, pin_cell(q_a, '1'), node, pin_cell(q_c, '1'))
    vres(sh, '10k', 44, 122)
    rail_symbol(sh, '+3V3', (44, 122))
    vres(sh, '100k', 48, 128)
    drop_ground(sh, (48, 134), 0)
    # PWR_ON_N: Q_c drain, Q_b gate and a 100k pull-up to VIN
    wire(sh, pin_cell(q_c, '3'), (28, 100), (106, 100), (106, 128), pin_cell(q_b, '1'))
    vres(sh, '100k', 60, 94)
    rail_symbol(sh, 'VIN', (60, 94))


def wire(sh, *points):
    """Hand-drawn polyline; points are (column, row) cells on the 1.27 mm grid."""
    for first, second in zip(points, points[1:]):
        if first == second:
            continue
        sh.wires.append(((first[0] * 1.27, first[1] * 1.27), (second[0] * 1.27, second[1] * 1.27)))


def rail_symbol(sh, net, cell):
    """Hand-placed power symbol whose pin sits on the given cell."""
    kicadgen._pwr_counter[0] += 1
    part = sh.add(f'power:{POWER_SYMBOLS[net]}', f'#PWR{kicadgen._pwr_counter[0]:03d}', net,
                  cell[0] * 1.27, cell[1] * 1.27, rot=0, auto=False)
    part.is_power = True
    return part


def rail_flag(sh, cell):
    kicadgen._pwr_counter[0] += 1
    part = sh.add('power:PWR_FLAG', f'#FLG{kicadgen._pwr_counter[0]:03d}', 'PWR_FLAG',
                  cell[0] * 1.27, cell[1] * 1.27, rot=0, auto=False)
    part.is_power = True
    return part


def at(column, row, rot=0):
    return (column * 1.27, row * 1.27, rot)


def pin_cell(part, pin):
    """Grid cell (column, row) of a part's pin."""
    x, y = part.pin_point(pin)
    return (round(x / 1.27), round(y / 1.27))


DIRECTION = {0: (1, 0), 180: (-1, 0), 90: (0, -1), 270: (0, 1)}


def spur(sh, part, pin, length=2):
    """Wire leaving a pin along its pin direction; returns the far end cell."""
    column, row = pin_cell(part, pin)
    step_x, step_y = DIRECTION[int(part.pin_out_angle(pin)) % 360]
    end = (column + step_x * length, row + step_y * length)
    wire(sh, (column, row), end)
    return end


def vres(sh, value, column, top, fp=R0603):
    """Vertical resistor with pin 1 on (column, top); pin 2 is six cells lower."""
    return res(sh, value, '', '', pose=at(column, top + 3), fp=fp)


def vcap(sh, value, column, top, fp=None):
    """Vertical capacitor with pin 1 on (column, top); pin 2 is six cells lower."""
    return cap(sh, value, '', '', pose=at(column, top + 3), fp=fp)


def hres(sh, value, column, row, fp=R0603):
    """Horizontal resistor centred on (column, row): pin 1 left, pin 2 right (three cells each side)."""
    return res(sh, value, '', '', pose=at(column, row, 90), fp=fp)


def hcap(sh, value, column, row, fp=None):
    return cap(sh, value, '', '', pose=at(column, row, 90), fp=fp)


def ground(sh, cell):
    return rail_symbol(sh, 'GND', cell)


def drop_ground(sh, cell, length=2):
    """Wire straight down from a cell to a GND symbol."""
    wire(sh, cell, (cell[0], cell[1] + length))
    return rail_symbol(sh, 'GND', (cell[0], cell[1] + length))


def net_label(sh, net, cell, angle=0, is_global=False):
    """Net label whose connection point is the given cell (text extends away along angle)."""
    kind = 'global_label' if is_global else 'label'
    sh.labels.append((kind, net, (cell[0] * 1.27, cell[1] * 1.27), angle))


def decoupling_block(sh, title, column, row, supply, values, ground='GND'):
    """Standalone bank of decoupling caps: supply rail on top, ground bus below, one cap per value.

    Returns the width in cells (rail plus title, whichever is wider)."""
    caps = [column + 6 + 12 * index for index in range(len(values))]
    sh.note(title, column * 1.27, (row - 8) * 1.27, 1.8)
    wire(sh, (column, row), (caps[-1], row))
    wire(sh, (column, row + 6), (caps[-1], row + 6))
    rail_symbol(sh, supply, (column, row))
    rail_symbol(sh, ground, (column, row + 6))
    for x, value in zip(caps, values):
        vcap(sh, value, x, row, fp=C0805 if value in ('1uF', '10uF') else None)
    return max(caps[-1] - column, round(len(title) * 1.4)) + 6


def place_blocks(sh, blocks, column, row, max_column=240, row_pitch=22):
    """Lay out decoupling blocks left to right from (column, row), wrapping to a new row at max_column."""
    x = column
    for title, supply, values, *ground in blocks:
        width = max(12 * len(values) + 6, round(len(title) * 1.4)) + 6
        if x + width > max_column:
            x, row = column, row + row_pitch
        decoupling_block(sh, title, x, row, supply, values, ground[0] if ground else 'GND')
        x += width


def build_rails_logic(sh):
    """Hand-laid sheet: input rail, buck switching loop, output rail, then the 3.3 V linear stage."""
    sh.handwired = True
    sh.note('12 V -> 5 V (AP63205 buck, datasheet Fig. 1 / Table 3: 4.7 uH, 10 uF in, 2 x 22 uF out, 100 nF bootstrap) -> 3.3 V (LD1117S33).', 20, 15)
    sh.note('AP63205: VIN 3.8-32 V (40 V for 400 ms), EN tied to VIN, FB tied to the fixed 5 V output.', 20, 21)
    u5 = ic(sh, 'Regulator_Switching:AP63205WU', 'AP63205WU-7', 110.49, 100.33, {},
            fp='Package_TO_SOT_SMD:TSOT-23-6')
    # input rail: +12V symbol, 10 uF and 100 nF down to ground, VIN and EN tied together
    wire(sh, (44, 77), (50, 77), (64, 77), (77, 77), (79, 77))
    rail_symbol(sh, '+12V', (44, 77))
    cap(sh, '10uF/25V', '', '', pose=at(50, 80))
    cap(sh, '100nF', '', '', pose=at(64, 80))
    for column in (50, 64):
        rail_symbol(sh, 'GND', (column, 83))
    wire(sh, (79, 81), (77, 81), (77, 77))
    wire(sh, (87, 85), (87, 87))
    rail_symbol(sh, 'GND', (87, 87))
    # switching loop: SW up and right to the inductor, bootstrap cap between SW and BST
    wire(sh, (95, 77), (97, 77), (97, 73), (101, 73), (105, 73))
    cap(sh, '100nF', '', '', pose=at(101, 76))
    wire(sh, (95, 79), (101, 79))
    inductor = aux(sh, 'Device:L', 'L', 'SRN6045TA-4R7M', {}, pose=at(108, 73, 90), fp='Inductor_SMD:L_Bourns_SRN6045TA')
    # output rail with FB feedback and two 22 uF caps
    wire(sh, (111, 73), (121, 73), (127, 73), (142, 73), (154, 73))
    wire(sh, (95, 81), (119, 81), (119, 73))
    rail_symbol(sh, '+5V', (121, 73))
    for column in (127, 142):
        cap(sh, '22uF/10V', '', '', pose=at(column, 76), fp=C1206)
        rail_symbol(sh, 'GND', (column, 79))
    rail_flag(sh, (154, 73))
    # 3.3 V linear stage
    u3 = ic(sh, 'Regulator_Linear:LD1117S33TR_SOT223', 'LD1117S33TR', 110.49, 140.97, {},
            fp='Package_TO_SOT_SMD:SOT-223-3_TabPin2')
    wire(sh, (64, 111), (72, 111), (81, 111))
    rail_symbol(sh, '+5V', (64, 111))
    wire(sh, (87, 117), (87, 119))
    rail_symbol(sh, 'GND', (87, 119))
    cap(sh, '10uF', '', '', pose=at(72, 114))
    rail_symbol(sh, 'GND', (72, 117))
    wire(sh, (93, 111), (102, 111), (114, 111), (126, 111))
    rail_symbol(sh, '+3V3', (126, 111))
    cap_pol(sh, '22uF', '', '', pose=at(102, 114))
    cap(sh, '100nF', '', '', pose=at(114, 114))
    for column in (102, 114):
        rail_symbol(sh, 'GND', (column, 117))
    return u5, u3, inductor


def place_ic(sh, lib_id, value, column, row, fp, ref_prefix='U', rot=0, **kwargs):
    """Fixed IC centred on a grid cell; wiring is drawn by hand."""
    return ic(sh, lib_id, value, column * 1.27, row * 1.27, {}, ref_prefix=ref_prefix, fp=fp, rot=rot, **kwargs)


def build_rails_15v(sh):
    """Hand-laid: ADP5071 with its input rail above, boost channel upper right, inverting channel lower right."""
    sh.handwired = True
    sh.note('ADP5071AREZ (5 V in): +16.5 V boost and -16.5 V inverting rails; ADP7142 (+15 V) and ADP7182 (-15 V) post-regulate.', 20, 15)
    sh.note('Values from ADP5071 datasheet Fig. 47 / Tables 9-11 (+/-16.5 V output rows rescaled via RFT). ADP7182 EN tied to VIN (auto-start); |VEN| >= 2 V enables.', 20, 21)
    u = place_ic(sh, 'Regulator_Switching:ADP5071AREZ', 'ADP5071AREZ', 110, 100, None)
    px, py = 110, 100
    # +5V input: bus left of the IC, rail above it with three decoupling caps
    wire(sh, (96, 70), (96, 102))
    rail_symbol(sh, '+5V', (96, 70))
    for pin in ('9', '17', '19', '18', '11'):
        spur(sh, u, pin, 2)
    place_blocks(sh, [('ADP5071 DECOUPLING CAPACITORS', '+5V', ('10uF', '10uF', '100nF'))], 190, 150)
    # COMP1 network (left, above the bus crossing): 5.6k then 47nF to ground
    wire(sh, pin_cell(u, '8'), (93, 84))
    hres(sh, '5.6k', 90, 84)
    wire(sh, (87, 84), (84, 84))
    vcap(sh, '47nF', 84, 84)
    drop_ground(sh, (84, 90), 0)
    # VREG: pin 16 and SEQ (pin 5) joined on a loop with its 1 uF cap
    wire(sh, pin_cell(u, '16'), (88, 96), (88, 116), (96, 116), (96, 112), pin_cell(u, '5'))
    wire(sh, (88, 106), (84, 106))
    vcap(sh, '1uF', 84, 106)
    drop_ground(sh, (84, 112), 0)
    # COMP2 network: 12k then 68nF to ground
    wire(sh, pin_cell(u, '12'), (81, 100))
    hres(sh, '12k', 78, 100)
    wire(sh, (75, 100), (72, 100))
    vcap(sh, '68nF', 72, 100)
    drop_ground(sh, (72, 106), 0)
    # SYNC and SLEW tied to ground, SS not connected
    wire(sh, pin_cell(u, '4'), (94, 108), (94, 110), pin_cell(u, '6'))
    drop_ground(sh, (94, 110), 2)
    sh.nc(u, '10')
    # exposed grounds along the bottom
    for pin in ('15', '21', '1'):
        spur(sh, u, pin, 2)
    wire(sh, (108, 120), (114, 120))
    drop_ground(sh, (110, 120), 2)
    # boost channel
    ind1 = aux(sh, 'Device:L', 'L', 'SRN8040TA-3R3M', {}, pose=at(128, 88, 90), fp=INDUCTOR)
    wire(sh, pin_cell(u, '3'), (125, 88))
    wire(sh, pin_cell(u, '2'), (131, 90), (131, 88))
    wire(sh, (131, 90), (135, 90))
    diode(sh, 'Device:D_Schottky', 'DFLS240', '', '', 'Diode_SMD:D_PowerDI-123', pose=at(138, 90, 180))
    wire(sh, (141, 90), (150, 90), (166, 90), (172, 90))
    rail_symbol(sh, '+16V5', (141, 90))
    rail_flag(sh, (172, 90))
    vres(sh, '2.67M', 150, 90)
    vres(sh, '137k', 150, 96)
    drop_ground(sh, (150, 102), 0)
    wire(sh, (150, 96), (124, 96), (124, 92), pin_cell(u, '7'))
    vcap(sh, '10uF/50V', 166, 90, fp=C1210)
    drop_ground(sh, (166, 96), 0)
    # inverting channel
    ind2 = aux(sh, 'Device:L', 'L', 'SRN8040TA-6R8M', {}, pose=at(131, 111), fp=INDUCTOR)
    drop_ground(sh, (131, 114), 0)
    wire(sh, pin_cell(u, '20'), (131, 108), (135, 108))
    diode(sh, 'Device:D_Schottky', 'DFLS240', '', '', 'Diode_SMD:D_PowerDI-123', pose=at(138, 108))
    wire(sh, (141, 108), (150, 108), (166, 108), (172, 108))
    rail_symbol(sh, '-16V5', (141, 108))
    rail_flag(sh, (172, 108))
    wire(sh, (150, 108), (150, 112))
    vres(sh, '2.55M', 150, 112)
    vres(sh, '118k', 150, 118)
    vcap(sh, '10uF/50V', 166, 108, fp=C1210)
    drop_ground(sh, (166, 114), 0)
    wire(sh, (150, 118), (126, 118), (126, 106), pin_cell(u, '13'))
    wire(sh, pin_cell(u, '14'), (124, 104), (124, 124), (150, 124))
    vcap(sh, '1uF', 130, 124)
    drop_ground(sh, (130, 130), 0)
    # +15 V LDO
    pos = place_ic(sh, 'Regulator_Linear:ADP7142AUJZ', 'ADP7142AUJZ', 60, 150, 'Package_TO_SOT_SMD:TSOT-23-5')
    vin, en, vout, adj = (pin_cell(pos, n) for n in ('1', '3', '5', '4'))
    wire(sh, vin, (vin[0] - 14, vin[1]))
    wire(sh, en, (en[0] - 2, en[1]), (en[0] - 2, vin[1]))
    rail_symbol(sh, '+16V5', (vin[0] - 14, vin[1]))
    vcap(sh, '4.7uF/25V', vin[0] - 10, vin[1], fp=C1206)
    drop_ground(sh, (vin[0] - 10, vin[1] + 6), 0)
    spur(sh, pos, '2', 2)
    drop_ground(sh, (pin_cell(pos, '2')[0], pin_cell(pos, '2')[1] + 2), 2)
    wire(sh, vout, (vout[0] + 28, vout[1]))
    rail_symbol(sh, '+15V', (vout[0] + 28, vout[1]))
    vres(sh, '115k', vout[0] + 14, vout[1])
    vres(sh, '10k', vout[0] + 14, vout[1] + 6)
    drop_ground(sh, (vout[0] + 14, vout[1] + 12), 0)
    wire(sh, adj, (adj[0] + 3, adj[1]), (adj[0] + 3, vout[1] + 6), (vout[0] + 14, vout[1] + 6))
    vcap(sh, '4.7uF/25V', vout[0] + 24, vout[1], fp=C1206)
    drop_ground(sh, (vout[0] + 24, vout[1] + 6), 0)
    # -15 V LDO
    neg = place_ic(sh, 'Regulator_Linear:ADP7182AUJZ', 'ADP7182AUJZ', 60, 185, 'Package_TO_SOT_SMD:TSOT-23-5')
    vin, en, vout, adj = (pin_cell(neg, n) for n in ('2', '3', '5', '4'))
    gnd_pin = pin_cell(neg, '1')
    wire(sh, vin, (vin[0] - 14, vin[1]))
    wire(sh, en, (en[0] - 2, en[1]), (en[0] - 2, vin[1]))
    rail_symbol(sh, '-16V5', (vin[0] - 14, vin[1]))
    vcap(sh, '4.7uF/25V', vin[0] - 10, vin[1], fp=C1206)
    drop_ground(sh, (vin[0] - 10, vin[1] + 6), 0)
    wire(sh, gnd_pin, (gnd_pin[0], gnd_pin[1] - 3), (gnd_pin[0] - 20, gnd_pin[1] - 3))
    drop_ground(sh, (gnd_pin[0] - 20, gnd_pin[1] - 3), 2)
    wire(sh, vout, (vout[0] + 28, vout[1]))
    rail_symbol(sh, '-15V', (vout[0] + 28, vout[1]))
    vres(sh, '113k', vout[0] + 14, vout[1])
    vres(sh, '10k', vout[0] + 14, vout[1] + 6)
    drop_ground(sh, (vout[0] + 14, vout[1] + 12), 0)
    vcap(sh, '100pF', vout[0] + 8, vout[1])
    wire(sh, adj, (adj[0] + 3, adj[1]), (adj[0] + 3, vout[1] + 6), (vout[0] + 14, vout[1] + 6))
    vcap(sh, '4.7uF/25V', vout[0] + 26, vout[1], fp=C1206)
    drop_ground(sh, (vout[0] + 26, vout[1] + 6), 0)


def opamp_unit(sh, ref, unit, column, row, footprint='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'):
    """One unit of the OPA1656 (same reference for every unit)."""
    return sh.add('Amplifier_Operational:OPA1656ID', ref, 'OPA1656ID', column * 1.27, row * 1.27, unit=unit,
                  auto=False, footprint=footprint)


def build_signal_gen(sh):
    """Hand-laid: clock + AD9833 + sine buffer + AD633 across the top, DAC amplitude control below."""
    sh.handwired = True
    sh.note('AD9833 60 Hz sine -> OPA1656 gain stage -> AD633 multiplier; MCP4921 + OPA188 give a 0-10 V amplitude control.', 20, 15)
    sh.note('Vctl 0-10 V (2.5 V ref x4) x sine +/-3.3 V pk / 10 = 0..3.3 V pk to amplifier input', 20, 21)
    # clock oscillator: OE tied to Vcc, bypass cap, output straight into MCLK
    osc = place_ic(sh, 'Oscillator:SG-8002CA', 'SG-8002CA-PH 25MHz', 22, 64,
                   'Oscillator:Oscillator_SMD_SeikoEpson_SG8002CA-4Pin_7.0x5.0mm')
    wire(sh, pin_cell(osc, '4'), (22, 56))
    wire(sh, (14, 56), (22, 56))
    rail_symbol(sh, '+5V', (22, 56))
    wire(sh, pin_cell(osc, '1'), (14, 64), (14, 56))
    drop_ground(sh, pin_cell(osc, '2'), 2)
    # AD9833
    dds = place_ic(sh, 'Interface:AD9833xRM', 'AD9833BRMZ', 60, 60, 'Package_SO:MSOP-10_3x3mm_P0.5mm')
    wire(sh, pin_cell(osc, '3'), pin_cell(dds, '5'))
    for pin, net in (('6', 'SPI_MOSI'), ('7', 'SPI_SCK'), ('8', 'AD9833_FSYNC')):
        net_label(sh, net, spur(sh, dds, pin, 2), 180, is_global=True)
    for pin in ('4', '9'):
        spur(sh, dds, pin, 2)
    wire(sh, (58, 72), (62, 72))
    drop_ground(sh, (60, 72), 2)
    vdd = pin_cell(dds, '2')
    wire(sh, vdd, (vdd[0], 48), (75, 48))
    rail_symbol(sh, '+5V', (vdd[0], 48))
    comp = pin_cell(dds, '1')
    wire(sh, comp, (75, comp[1]), (75, 54))
    vcap(sh, '10nF', 75, 48)
    cap_pin = pin_cell(dds, '3')
    wire(sh, cap_pin, (cap_pin[0], 47), (52, 47))
    vcap(sh, '100nF', 52, 47)
    drop_ground(sh, (52, 53), 0)
    rail_flag(sh, (55, 47))
    # AC coupling into the buffer
    wire(sh, pin_cell(dds, '10'), (74, 62))
    hcap(sh, '1uF', 77, 62)
    wire(sh, (80, 62), (92, 62), (92, 58), (104, 58))
    vres(sh, '100k', 86, 62)
    drop_ground(sh, (86, 68), 0)
    # OPA1656 unit A: non-inverting gain of 11
    opa_a = opamp_unit(sh, next_ref('U'), 1, 110, 60)
    opa_ref = opa_a.ref
    wire(sh, pin_cell(opa_a, '2'), (100, 62), (100, 70))
    hres(sh, '33k', 110, 70)
    wire(sh, (107, 70), (100, 70))
    vres(sh, '3.3k', 100, 70)
    drop_ground(sh, (100, 76), 0)
    wire(sh, pin_cell(opa_a, '1'), (120, 60), (120, 70), (113, 70))
    wire(sh, (120, 60), (124, 60))
    hres(sh, '100', 127, 60)
    wire(sh, (130, 60), (192, 60))
    # OPA1656 unit B: spare half as a grounded follower, unit C: power pins
    opa_b = opamp_unit(sh, opa_ref, 2, 230, 110)
    wire(sh, pin_cell(opa_b, '5'), (222, 108 + 0))
    wire(sh, pin_cell(opa_b, '6'), (222, 112), (222, 118), (240, 118), (240, 110), pin_cell(opa_b, '7'))
    drop_ground(sh, (222, 108), 2)
    opa_p = opamp_unit(sh, opa_ref, 3, 260, 90, 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')
    top, bottom = pin_cell(opa_p, '8'), pin_cell(opa_p, '4')
    wire(sh, top, (top[0], top[1] - 6))
    rail_symbol(sh, '+15V', (top[0], top[1] - 6))
    wire(sh, bottom, (bottom[0], bottom[1] + 4), (bottom[0] + 4, bottom[1] + 4))
    rail_symbol(sh, '-15V', (bottom[0] + 4, bottom[1] + 4))
    # AD633 multiplier
    mult = place_ic(sh, 'cryocooler:AD633JRZ-R7', 'AD633JRZ-R7', 200, 66, 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')
    wire(sh, pin_cell(mult, '8'), (188, 62), (188, 68))
    wire(sh, pin_cell(mult, '2'), (188, 66))
    wire(sh, pin_cell(mult, '4'), (188, 68))
    drop_ground(sh, (188, 68), 2)
    plus = pin_cell(mult, '6')
    wire(sh, plus, (plus[0], 48))
    rail_symbol(sh, '+15V', (plus[0], 48))
    minus = pin_cell(mult, '3')
    wire(sh, minus, (minus[0], 80), (minus[0] + 4, 80))
    rail_symbol(sh, '-15V', (minus[0] + 4, 80))
    wire(sh, pin_cell(mult, '5'), (214, 60))
    hres(sh, '100', 217, 60)
    wire(sh, (220, 60), (224, 60))
    hcap(sh, '10uF', 227, 60)
    wire(sh, (230, 60), (240, 60))
    net_label(sh, 'SIG_SINE', (240, 60), 0, is_global=True)
    vres(sh, '100k', 234, 60)
    drop_ground(sh, (234, 66), 0)
    # amplitude control: MCP4921 -> OPA188 (gain of 4) -> AMP_CTL
    dac = place_ic(sh, 'Analog_DAC:MCP4921', 'MCP4921-E/SN', 60, 110, 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')
    for pin, net in (('2', 'MCP4921_CS'), ('3', 'SPI_SCK'), ('4', 'SPI_MOSI')):
        net_label(sh, net, spur(sh, dac, pin, 5), 180, is_global=True)
    wire(sh, pin_cell(dac, '5'), (50, 108))
    ground(sh, (50, 108))
    vdd = pin_cell(dac, '1')
    wire(sh, vdd, (vdd[0], 94), (76, 94))
    rail_symbol(sh, '+3V3', (vdd[0], 94))
    vres(sh, '6.8k', 76, 94)
    vref_pin = pin_cell(dac, '6')
    wire(sh, vref_pin, (vref_pin[0], 100), (92, 100))
    ref = aux(sh, 'Reference_Voltage:LM4040DBZ-2.5', 'U', 'LM4040DBZ-2.5', {}, pose=at(84, 103, 90), fp=SOT23)
    drop_ground(sh, (84, 106), 2)
    vcap(sh, '100nF', 92, 100)
    drop_ground(sh, (92, 106), 0)
    rail_flag(sh, (88, 100))
    spur(sh, dac, '7', 2)
    drop_ground(sh, pin_cell(dac, '7'), 0)
    wire(sh, pin_cell(dac, '7'), (60, 120))
    drop_ground(sh, (60, 120), 2)
    opa188 = place_ic(sh, 'Amplifier_Operational:OPA188xxD', 'OPA188ID', 130, 110, 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')
    wire(sh, pin_cell(dac, '8'), (110, 110), (110, 108), pin_cell(opa188, '3'))
    for pin in ('1', '5', '8'):
        sh.nc(opa188, pin)
    wire(sh, pin_cell(opa188, '2'), (120, 112), (120, 132))
    wire(sh, pin_cell(opa188, '6'), (146, 110), (146, 132), (133, 132))
    hres(sh, '30k', 130, 132)
    wire(sh, (127, 132), (120, 132))
    vres(sh, '10k', 120, 132)
    drop_ground(sh, (120, 138), 0)
    top, bottom = pin_cell(opa188, '7'), pin_cell(opa188, '4')
    wire(sh, top, (top[0], 98))
    rail_symbol(sh, '+15V', (top[0], 98))
    wire(sh, bottom, (bottom[0], 120), (bottom[0] + 4, 120))
    rail_symbol(sh, '-15V', (bottom[0] + 4, 120))
    wire(sh, (146, 110), (170, 110), (170, 64), pin_cell(mult, '1'))
    place_blocks(sh, [
        ('SG-8002CA DECOUPLING CAPACITORS', '+5V', ('100nF',)),
        ('AD9833 DECOUPLING CAPACITORS', '+5V', ('100nF', '10uF')),
        ('OPA1656 +15V DECOUPLING CAPACITORS', '+15V', ('100nF',)),
        ('OPA1656 -15V DECOUPLING CAPACITORS', '-15V', ('100nF',)),
        ('AD633 +15V DECOUPLING CAPACITORS', '+15V', ('100nF',)),
        ('AD633 -15V DECOUPLING CAPACITORS', '-15V', ('100nF',)),
        ('MCP4921 DECOUPLING CAPACITORS', '+3V3', ('100nF', '10uF')),
        ('OPA188 +15V DECOUPLING CAPACITORS', '+15V', ('100nF',)),
        ('OPA188 -15V DECOUPLING CAPACITORS', '-15V', ('100nF',)),
    ], 20, 160, max_column=300)


def build_amp_control(sh):
    """Hand-laid, left to right: GPIO -> N-FET level shifter -> P-FET high-side switch -> REM terminal and LED."""
    sh.handwired = True
    sh.note('GPIO6 high -> +12 V on the amplifier REM terminal (P-FET high-side switch). LED: green = on, red = off.', 20, 15)
    sh.note('Amplifier: AUDIOZERONE ZE500.1 (external): REM terminal + RCA/line input. Its power leads do not pass through this board.', 20, 21)
    net_label(sh, 'AMP_REM_EN', (24, 60), 180, is_global=True)
    wire(sh, (24, 60), (28, 60))
    hres(sh, '1k', 31, 60)
    wire(sh, (34, 60), (46, 60))
    vres(sh, '100k', 40, 60)
    drop_ground(sh, (40, 66), 0)
    q_n = nfet(sh, 'BSS138', '', '', pose=at(50, 60))
    spur(sh, q_n, '2', 2)
    ground(sh, pin_cell(q_n, '2')[0:1] + (pin_cell(q_n, '2')[1] + 2,))
    wire(sh, pin_cell(q_n, '3'), (52, 50), (76, 50))
    vres(sh, '100k', 62, 44)
    rail_symbol(sh, '+12V', (62, 44))
    q_p = sh.add('Transistor_FET:BSS84', next_ref('Q'), 'BSS84', 80 * 1.27, 50 * 1.27, rot=180, mirror=True,
                 auto=False, footprint=SOT23)
    top, bottom = pin_cell(q_p, '2'), pin_cell(q_p, '3')
    wire(sh, top, (top[0], top[1] - 4))
    rail_symbol(sh, '+12V', (top[0], top[1] - 4))
    # AMP_REM bus: drain, pull-down, LED branch and the REM terminal
    wire(sh, bottom, (bottom[0], 58), (136, 58))
    net_label(sh, 'AMP_REM', (104, 58), 0)
    vres(sh, '1k', 90, 58)
    drop_ground(sh, (90, 64), 0)
    vres(sh, '2.2k', 96, 40)
    rail_symbol(sh, '+5V', (96, 40))
    led = aux(sh, 'Device:LED_Dual_Bidirectional', 'D', 'RED/GREEN', {}, pose=at(96, 52, 90), fp=LED1206)
    wire(sh, (96, 46), pin_cell(led, '1') if pin_cell(led, '1')[1] == 46 else pin_cell(led, '2'))
    j_rem = conn(sh, 'Connector:Screw_Terminal_01x02', 'AMP REM / GND', 140 * 1.27, 58 * 1.27, {}, TERM2)
    spur(sh, j_rem, '2', 2)
    ground(sh, (pin_cell(j_rem, '2')[0] - 2, pin_cell(j_rem, '2')[1]))
    j_sig = conn(sh, 'Connector:Screw_Terminal_01x02', 'AMP SIGNAL IN / GND', 140 * 1.27, 90 * 1.27, {}, TERM2)
    sig = pin_cell(j_sig, '1')
    wire(sh, sig, (sig[0] - 6, sig[1]))
    net_label(sh, 'SIG_SINE', (sig[0] - 6, sig[1]), 180, is_global=True)
    spur(sh, j_sig, '2', 2)
    ground(sh, (pin_cell(j_sig, '2')[0] - 2, pin_cell(j_sig, '2')[1]))


def build_amp_current(sh):
    """Hand-laid: logic-side isolator top left, isolated supply bottom left, ACS37800 and divider to the right."""
    sh.handwired = True
    sh.note('Amplifier output V/I monitor: ACS37800 (SPI) on an isolated 3.3 V domain (MIE1W0505, VSEL=GND2 -> 3.3 V); SPI bus GPIO11/12/13, CS GPIO17.', 20, 15)
    sh.note('Mains-class creepage/clearance applies between ISO_GND domain and the logic side on the PCB.', 20, 21)
    iso = place_ic(sh, 'cryocooler:ISO7741DW', 'ISO7741DW', 60, 60, 'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm')
    for pin, net in (('3', 'ACS_MOSI'), ('4', 'ACS_SCK'), ('5', 'ACS_CS'), ('6', 'ACS_MISO')):
        net_label(sh, net, spur(sh, iso, pin, 3), 180, is_global=True)
    en1 = pin_cell(iso, '7')
    wire(sh, en1, (en1[0] - 6, en1[1]), (en1[0] - 6, en1[1] + 8), (en1[0] - 2, en1[1] + 8))
    rail_symbol(sh, '+3V3', (en1[0] - 2, en1[1] + 8))
    vcc1 = pin_cell(iso, '1')
    wire(sh, vcc1, (vcc1[0], 44))
    rail_symbol(sh, '+3V3', (vcc1[0], 44))
    gnd1 = spur(sh, iso, '2', 2)
    ground(sh, gnd1)
    for pin, net in (('14', 'ISO_MOSI'), ('13', 'ISO_SCK'), ('12', 'ISO_CS'), ('11', 'ISO_MISO')):
        net_label(sh, net, spur(sh, iso, pin, 3), 0)
    en2 = pin_cell(iso, '10')
    wire(sh, en2, (en2[0] + 6, en2[1]), (en2[0] + 6, en2[1] + 8), (en2[0] + 2, en2[1] + 8))
    rail_symbol(sh, 'ISO_3V3', (en2[0] + 2, en2[1] + 8))
    vcc2 = pin_cell(iso, '16')
    wire(sh, vcc2, (vcc2[0], 44))
    rail_symbol(sh, 'ISO_3V3', (vcc2[0], 44))
    rail_symbol(sh, 'ISO_GND', spur(sh, iso, '9', 2))
    # pull-ups for the three idle-state lines, drawn as a small block
    for index, net in enumerate(('ACS_CS', 'ACS_SCK', 'ACS_MOSI')):
        row = 82 + index * 6
        rail_symbol(sh, '+3V3', (28, row))
        hres(sh, '10k', 31, row)
        wire(sh, (34, row), (36, row))
        net_label(sh, net, (36, row), 0, is_global=True)
    # isolated supply
    dc = place_ic(sh, 'cryocooler:MIE1W0505BGLVH-3R-Z', 'MIE1W0505BGLVH-3R-Z', 60, 122,
                  'cryocooler:CONV_MIE1W0505BGLVH-3R-Z', ref_prefix='PS')
    vin = pin_cell(dc, '9_10')
    wire(sh, vin, (vin[0], 108), (24, 108))
    rail_symbol(sh, '+5V', (24, 108))
    for column, value in ((30, '10uF'), (38, '100nF')):
        vcap(sh, value, column, 108)
        drop_ground(sh, (column, 114), 0)
    en = pin_cell(dc, '8')
    wire(sh, en, (46, en[1]))
    vres(sh, '100k', 46, en[1] - 6)
    rail_symbol(sh, '+5V', (46, en[1] - 6))
    drop_ground(sh, pin_cell(dc, '1'), 2)
    vout = pin_cell(dc, '5_6')
    wire(sh, vout, (vout[0], vout[1]), (96, vout[1]))
    rail_symbol(sh, 'ISO_3V3', (96, vout[1]))
    for column, value in ((78, '22uF'), (88, '100nF')):
        vcap(sh, value, column, vout[1], fp=C1206 if value == '22uF' else None)
        rail_symbol(sh, 'ISO_GND', (column, vout[1] + 6))
    vsel, gnd2 = pin_cell(dc, '7'), pin_cell(dc, '2')
    wire(sh, vsel, (vsel[0] + 2, vsel[1]), (vsel[0] + 2, gnd2[1]), gnd2)
    rail_symbol(sh, 'ISO_GND', (vsel[0] + 2, gnd2[1]))
    wire(sh, (vsel[0] + 2, vsel[1]), (vsel[0] + 4, vsel[1]))
    rail_flag(sh, (vsel[0] + 4, vsel[1]))
    # ACS37800
    acs = place_ic(sh, 'cryocooler:ACS37800KMACTR-030B3-SPI', 'ACS37800KMACTR-030B3-SPI', 110, 60,
                   'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm', rot=180)
    for pin, net in (('9', 'ISO_CS'), ('10', 'ISO_MOSI'), ('11', 'ISO_SCK'), ('12', 'ISO_MISO')):
        net_label(sh, net, spur(sh, acs, pin, 3), 180)
    gnd = pin_cell(acs, '14')
    wire(sh, gnd, (gnd[0], gnd[1] - 2), (gnd[0] - 4, gnd[1] - 2))
    rail_symbol(sh, 'ISO_GND', (gnd[0] - 4, gnd[1] - 2))
    vcc = pin_cell(acs, '13')
    wire(sh, vcc, (vcc[0], vcc[1] + 4), (vcc[0] + 4, vcc[1] + 4))
    rail_symbol(sh, 'ISO_3V3', (vcc[0] + 4, vcc[1] + 4))
    vinn = spur(sh, acs, '15', 2)
    rail_symbol(sh, 'ISO_GND', vinn)
    vinp = pin_cell(acs, '16')
    wire(sh, vinp, (124, vinp[1]), (124, 38), (150, 38))
    wire(sh, (124, 46), (130, 46))
    vres(sh, '4.02k', 130, 46, fp=R0603)
    rail_symbol(sh, 'ISO_GND', (130, 52))
    # four 1M divider resistors from the load side up to VSENSE
    ip_minus, ip_plus = pin_cell(acs, '5'), pin_cell(acs, '1')
    wire(sh, ip_minus, (160, ip_minus[1]), (160, 58), (166, 58))
    for index in range(4):
        vres(sh, '1M', 150, 38 + index * 6, fp=R1206)
    wire(sh, ip_plus, (166, ip_plus[1]))
    j_out = conn(sh, 'Connector:Screw_Terminal_01x02', 'AMP OUT (+ / -)', 170 * 1.27, 64 * 1.27, {}, TERM2)
    j_load = conn(sh, 'Connector:Screw_Terminal_01x02', 'CRYOCOOLER (+ / -)', 170 * 1.27, 58 * 1.27, {}, TERM2)
    for connector in (j_out, j_load):
        spur(sh, connector, '2', 2)
        rail_symbol(sh, 'ISO_GND', (pin_cell(connector, '2')[0] - 2, pin_cell(connector, '2')[1]))
    place_blocks(sh, [
        ('ISO7741 VCC1 DECOUPLING CAPACITORS', '+3V3', ('100nF',)),
        ('ISO7741 VCC2 DECOUPLING CAPACITORS', 'ISO_3V3', ('100nF',), 'ISO_GND'),
        ('ACS37800 DECOUPLING CAPACITORS', 'ISO_3V3', ('1uF', '100nF'), 'ISO_GND'),
    ], 110, 150, max_column=300)


def build_system_current(sh):
    """Hand-laid: 15 mOhm shunt between VSW and +12V with kelvin sense lines into the INA237."""
    sh.handwired = True
    sh.note('INA237 monitors the switched 12 V rail: 15 mOhm shunt, I2C 0x40, +/-163.84 mV range (~10.9 A).', 20, 15)
    ina = place_ic(sh, 'Sensor_Energy:INA237', 'INA237AIDGSR', 60, 60, 'Package_SO:TSSOP-10_3x3mm_P0.5mm')
    # shunt: VSW side straight into Vin+, +12V side to Vin- and Vbus
    hres(sh, '15m', 30, 62, fp=R2512)
    wire(sh, (33, 62), pin_cell(ina, '10'))
    rail_symbol(sh, 'VSW', (40, 62))
    wire(sh, (25, 62), (25, 54), pin_cell(ina, '8'))
    wire(sh, (27, 62), (27, 66), (46, 66), (46, 64), pin_cell(ina, '9'))
    wire(sh, (27, 62), (14, 62))
    rail_symbol(sh, '+12V', (14, 62))
    rail_flag(sh, (20, 62))
    vcap(sh, '100nF', 18, 62, fp=C0805)
    drop_ground(sh, (18, 68), 0)
    cap_pol(sh, '100uF/25V', '', '', pose=at(22, 65), fp=CP_ELEC)
    drop_ground(sh, (22, 68), 0)
    # I2C, address straps, supply
    for pin, net in (('4', 'SDA'), ('5', 'SCL')):
        net_label(sh, net, spur(sh, ina, pin, 8), 0, is_global=True)
    wire(sh, pin_cell(ina, '1'), (72, 54), (72, 56), pin_cell(ina, '2'))
    ground(sh, (72, 56))
    sh.nc(ina, '3')
    vs = pin_cell(ina, '6')
    wire(sh, vs, (vs[0], 44))
    rail_symbol(sh, '+3V3', (vs[0], 44))
    place_blocks(sh, [('INA237 DECOUPLING CAPACITORS', '+3V3', ('100nF',))], 120, 100)
    drop_ground(sh, pin_cell(ina, '7'), 2)


def pullup(sh, value, cell):
    """Horizontal pull-up ending on a +3V3 symbol three cells left of `cell`'s wire end; returns nothing."""
    column, row = cell
    hres(sh, value, column - 3, row)
    wire(sh, (column - 6, row), (column - 6, row))
    rail_symbol(sh, '+3V3', (column - 6, row))


def build_cooling(sh):
    """Hand-laid: EMC2303 centre, pull-ups and I2C on the left, fan and pump connectors on the right."""
    sh.handwired = True
    sh.note('EMC2303: ADDR_SEL 33k pull-up -> SMBus 0x4D (datasheet Table 5-1); CLK 4.7k pull-up -> default fan drive 0%. ch1 fans, ch2 pump. Alphacool ES: tach -> GPIO18, NTC -> GPIO4.', 20, 15)
    emc = place_ic(sh, 'Driver_Motor:EMC2303-x-KP', 'EMC2303-x-KP', 60, 70,
                   'Package_DFN_QFN:VQFN-12-1EP_4x4mm_P0.8mm_EP2.1x2.1mm_ThermalVias')
    # supply and ground
    vdd = pin_cell(emc, '3')
    wire(sh, vdd, (vdd[0], 50))
    rail_symbol(sh, '+3V3', (vdd[0], 50))
    place_blocks(sh, [('EMC2303 DECOUPLING CAPACITORS', '+3V3', ('1uF', '100nF'))], 190, 45)
    drop_ground(sh, pin_cell(emc, '13'), 2)
    # left side: I2C, address strap, clock strap, alert with LED
    for pin, net in (('1', 'SDA'), ('2', 'SCL')):
        net_label(sh, net, spur(sh, emc, pin, 3), 180, is_global=True)
    for pin, value in (('4', '33k'), ('9', '4.7k')):
        end = spur(sh, emc, pin, 5)
        hres(sh, value, end[0] - 3, end[1])
        rail_symbol(sh, '+3V3', (end[0] - 6, end[1]))
    alert = spur(sh, emc, '10', 4)
    hres(sh, '10k', alert[0] - 3, alert[1])
    rail_symbol(sh, '+3V3', (alert[0] - 6, alert[1]))
    wire(sh, alert, (alert[0], alert[1] + 6), (alert[0] - 1, alert[1] + 6))
    d_fault = sh.add('Device:LED', next_ref('D'), 'FAN FAULT', (alert[0] - 4) * 1.27, (alert[1] + 6) * 1.27,
                     rot=180, auto=False, footprint=LED0603)
    k_cell, a_cell = pin_cell(d_fault, '1'), pin_cell(d_fault, '2')
    wire(sh, (alert[0] - 1, alert[1] + 6), k_cell)
    wire(sh, a_cell, (a_cell[0] - 1, a_cell[1]))
    hres(sh, '1k', a_cell[0] - 4, a_cell[1])
    rail_symbol(sh, '+3V3', (a_cell[0] - 7, a_cell[1]))
    wire(sh, (alert[0], alert[1] + 6), (alert[0], alert[1] + 10))
    net_label(sh, 'FAN_ALERT', (alert[0], alert[1] + 10), 180, is_global=True)
    # right side: fan on channel 1
    pwm1, tach1 = pin_cell(emc, '5'), pin_cell(emc, '6')
    j_fan = sh.add('Connector_Generic:Conn_01x04', next_ref('J'), 'FAN (4-pin PWM)', 150 * 1.27, 68 * 1.27,
                   rot=180, mirror=True, auto=False, footprint=KK4)
    wire(sh, pwm1, (74, pwm1[1]), (74, 52), (110, 52), (110, pin_cell(j_fan, '4')[1]), pin_cell(j_fan, '4'))
    wire(sh, tach1, pin_cell(j_fan, '3'))
    vres(sh, '10k', 84, 46)
    rail_symbol(sh, '+3V3', (84, 46))
    vres(sh, '4.7k', 92, tach1[1] - 6)
    rail_symbol(sh, '+3V3', (92, tach1[1] - 6))
    plus, ground_pin = pin_cell(j_fan, '2'), pin_cell(j_fan, '1')
    wire(sh, plus, (plus[0] - 10, plus[1]))
    rail_symbol(sh, '+12V', (plus[0] - 6, plus[1]))
    vcap(sh, '22uF/25V', plus[0] - 10, plus[1], fp=C1210)
    drop_ground(sh, (plus[0] - 10, plus[1] + 6), 0)
    ground(sh, spur(sh, j_fan, '1', 2))
    # pump on channel 2
    pwm2, tach2 = pin_cell(emc, '7'), pin_cell(emc, '8')
    j_pump = sh.add('Connector_Generic:Conn_01x04', next_ref('J'), 'PUMP (4-pin PWM)', 150 * 1.27, 94 * 1.27,
                    rot=180, mirror=True, auto=False, footprint=KK4)
    wire(sh, pwm2, (76, pwm2[1]), (76, 84), (120, 84), (120, pin_cell(j_pump, '4')[1]), pin_cell(j_pump, '4'))
    wire(sh, tach2, (74, tach2[1]), (74, pin_cell(j_pump, '3')[1]), pin_cell(j_pump, '3'))
    vres(sh, '10k', 90, 78)
    rail_symbol(sh, '+3V3', (90, 78))
    vres(sh, '4.7k', 104, pin_cell(j_pump, '3')[1] - 6)
    rail_symbol(sh, '+3V3', (104, pin_cell(j_pump, '3')[1] - 6))
    plus = pin_cell(j_pump, '2')
    wire(sh, plus, (plus[0] - 10, plus[1]))
    rail_symbol(sh, '+12V', (plus[0] - 6, plus[1]))
    vcap(sh, '22uF/25V', plus[0] - 10, plus[1], fp=C1210)
    drop_ground(sh, (plus[0] - 10, plus[1] + 6), 0)
    ground(sh, spur(sh, j_pump, '1', 2))
    sh.nc(emc, '11')
    ground(sh, spur(sh, emc, '12', 2))
    # Alphacool ES flow sensor and NTC
    j_flow = conn(sh, 'Connector_Generic:Conn_01x03', 'ALPHACOOL ES FLOW (3-pin)', 110 * 1.27, 124 * 1.27, {}, KK3)
    raw = pin_cell(j_flow, '3')
    wire(sh, raw, (raw[0] - 6, raw[1]))
    hres(sh, '1k', raw[0] - 9, raw[1])
    wire(sh, (raw[0] - 12, raw[1]), (raw[0] - 30, raw[1]))
    net_label(sh, 'FLOW_TACH', (raw[0] - 30, raw[1]), 180, is_global=True)
    vres(sh, '10k', raw[0] - 20, raw[1] - 6)
    rail_symbol(sh, '+3V3', (raw[0] - 20, raw[1] - 6))
    plus_pin, gnd_pin = pin_cell(j_flow, '2'), pin_cell(j_flow, '1')
    wire(sh, plus_pin, (plus_pin[0] - 4, plus_pin[1]))
    rail_symbol(sh, '+12V', (plus_pin[0] - 4, plus_pin[1]))
    wire(sh, gnd_pin, (gnd_pin[0] - 8, gnd_pin[1]))
    ground(sh, (gnd_pin[0] - 8, gnd_pin[1]))
    j_ntc = conn(sh, 'Connector_Generic:Conn_01x02', 'ALPHACOOL ES NTC 10k', 110 * 1.27, 150 * 1.27, {}, XH2)
    ntc = pin_cell(j_ntc, '1')
    wire(sh, ntc, (ntc[0] - 30, ntc[1]))
    net_label(sh, 'NTC_ADC', (ntc[0] - 30, ntc[1]), 180, is_global=True)
    vres(sh, '10k', ntc[0] - 14, ntc[1] - 6)
    rail_symbol(sh, '+3V3', (ntc[0] - 14, ntc[1] - 6))
    vcap(sh, '100nF', ntc[0] - 22, ntc[1])
    drop_ground(sh, (ntc[0] - 22, ntc[1] + 6), 0)
    ground(sh, spur(sh, j_ntc, '2', 2))


def build_cold_head(sh):
    """Hand-laid: ADS122C04 centre; RTD inputs fan out to the connector with nested jogs so nothing crosses."""
    sh.handwired = True
    sh.note('PT1000 4-wire ratiometric: IDAC1 (AIN3) excites, AIN1/AIN0 sense, Rref (3.9k) on REFP/REFN. I2C 0x45 (A0=A1=DVDD).', 20, 15)
    adc = place_ic(sh, 'cryocooler:ADS122C04IPWR', 'ADS122C04IPWR', 60, 60, 'Package_SO:TSSOP-16_4.4x5mm_P0.65mm')
    # supplies
    avdd, dvdd = pin_cell(adc, '12'), pin_cell(adc, '13')
    wire(sh, avdd, (avdd[0], 42))
    wire(sh, dvdd, (dvdd[0], 42))
    wire(sh, (avdd[0], 42), (dvdd[0], 42))
    rail_symbol(sh, '+3V3', (60, 42))
    place_blocks(sh, [('ADS122C04 DECOUPLING CAPACITORS', '+3V3', ('100nF', '1uF'))], 190, 100)
    avss, dgnd = spur(sh, adc, '5', 2), spur(sh, adc, '4', 2)
    wire(sh, avss, dgnd)
    drop_ground(sh, (60, 72), 2)
    # left side: address straps, reset and data-ready pull-ups, I2C labels
    a0, a1 = pin_cell(adc, '1'), pin_cell(adc, '2')
    wire(sh, a0, (46, a0[1]), (46, a1[1]), a1)
    rail_symbol(sh, '+3V3', (46, a0[1]))
    reset = pin_cell(adc, '3')
    wire(sh, reset, (34, reset[1]))
    vres(sh, '10k', 34, reset[1] - 6)
    rail_symbol(sh, '+3V3', (34, reset[1] - 6))
    for pin, net in (('15', 'SDA'), ('16', 'SCL')):
        net_label(sh, net, spur(sh, adc, pin, 3), 180, is_global=True)
    drdy = pin_cell(adc, '14')
    wire(sh, drdy, (28, drdy[1]))
    vres(sh, '10k', 28, drdy[1] - 6)
    rail_symbol(sh, '+3V3', (28, drdy[1] - 6))
    # right side inputs
    sh.nc(adc, '7')
    ground(sh, spur(sh, adc, '8', 2))
    j_rtd = conn(sh, 'Connector_Generic:Conn_01x04', 'RTD PT1000 4-wire', 170 * 1.27, 60 * 1.27, {},
                 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical')
    fp_pin, sp_pin, sn_pin, ref_pin = (pin_cell(j_rtd, n) for n in ('1', '2', '3', '4'))
    wire(sh, pin_cell(adc, '6'), (74, 54), (74, 44), (160, 44), (160, fp_pin[1]), fp_pin)
    ain1, ain0, refp = pin_cell(adc, '10'), pin_cell(adc, '11'), pin_cell(adc, '9')
    wire(sh, ain1, (76, ain1[1]), (76, 50), (93, 50))
    hres(sh, '1k', 96, 50)
    wire(sh, (99, 50), (156, 50), (156, sp_pin[1]), sp_pin)
    vcap(sh, '10nF', 82, 50)
    drop_ground(sh, (82, 56), 0)
    vcap(sh, '100nF', 88, 50)
    wire(sh, (88, 56), (88, 68))
    wire(sh, ain0, (78, ain0[1]), (78, 68), (93, 68))
    hres(sh, '1k', 96, 68)
    wire(sh, (99, 68), (152, 68), (152, sn_pin[1]), sn_pin)
    vcap(sh, '10nF', 82, 68)
    drop_ground(sh, (82, 74), 0)
    wire(sh, refp, (76, refp[1]), (76, 80), (160, 80), (160, ref_pin[1]), ref_pin)
    vres(sh, '3.9k', 100, 80)
    drop_ground(sh, (100, 86), 0)
    vcap(sh, '100nF', 108, 80)
    drop_ground(sh, (108, 86), 0)


def build_imu(sh):
    """Hand-laid: SPI labels on the left, interrupts on the right, supplies above."""
    sh.handwired = True
    sh.note('LSM6DSOX in 4-wire SPI mode on the main bus (CS GPIO1, INT1 GPIO2 single-tap, INT2 GPIO39 wake-up).', 20, 15)
    imu = place_ic(sh, 'cryocooler:LSM6DSOXTR', 'LSM6DSOXTR', 80, 60, 'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y')
    for pin, net in (('12', 'IMU_CS'), ('13', 'SPI_SCK'), ('14', 'SPI_MOSI'), ('1', 'SPI_MISO')):
        net_label(sh, net, spur(sh, imu, pin, 12), 180, is_global=True)
    cs = pin_cell(imu, '12')
    vres(sh, '10k', cs[0] - 6, cs[1] - 6)
    rail_symbol(sh, '+3V3', (cs[0] - 6, cs[1] - 6))
    wire(sh, pin_cell(imu, '2'), (66, 60), (66, 62), pin_cell(imu, '3'))
    ground(sh, (66, 62))
    sh.nc(imu, '10')
    sh.nc(imu, '11')
    for pin, net in (('4', 'IMU_INT1'), ('9', 'IMU_INT2')):
        net_label(sh, net, spur(sh, imu, pin, 3), 0, is_global=True)
    vdd, vddio = pin_cell(imu, '8'), pin_cell(imu, '5')
    wire(sh, vdd, (vdd[0], 38), (vddio[0], 38), vddio)
    rail_symbol(sh, '+3V3', (80, 38))
    place_blocks(sh, [('LSM6DSOX DECOUPLING CAPACITORS', '+3V3', ('100nF', '10uF', '100nF'))], 130, 45)
    drop_ground(sh, pin_cell(imu, '6'), 2)


def led_chain(sh, net, value, row):
    """GPIO label -> 470 ohm -> LED -> ground, drawn left to right."""
    net_label(sh, net, (36, row), 180, is_global=True)
    wire(sh, (36, row), (40, row))
    hres(sh, '470', 43, row)
    wire(sh, (46, row), (48, row))
    led_part = sh.add('Device:LED', next_ref('D'), value, 51 * 1.27, row * 1.27, rot=180, auto=False, footprint=LED0603)
    drop_ground(sh, pin_cell(led_part, '1'), 2)
    return led_part


def build_indicators(sh):
    """Hand-laid: two simple LED chains and the WS2812B behind its level shifter."""
    sh.handwired = True
    sh.note('READY (GPIO15) and FAULT (GPIO14) LEDs, active high; WS2812B status LED on GPIO38 via a 74AHCT1G125 3.3 V -> 5 V level shifter (WS2812B VIH = 0.7 x VDD).', 20, 15)
    led_chain(sh, 'LED_READY', 'READY (green)', 40)
    led_chain(sh, 'LED_FAULT', 'FAULT (red)', 56)
    buf = place_ic(sh, '74xGxx:74AHCT1G125', '74AHCT1G125', 60, 100, 'Package_TO_SOT_SMD:SOT-23-5')
    rgb = sh.add('LED:WS2812B', next_ref('D'), 'WS2812B', 100 * 1.27, 100 * 1.27, auto=False,
                 footprint='LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm')
    # buffer: output enable to ground, 5 V supply with bypass, input with pull-down
    oe, vcc = pin_cell(buf, '1'), pin_cell(buf, '5')
    wire(sh, oe, (oe[0], oe[1] - 2), (oe[0] + 4, oe[1] - 2))
    ground(sh, (oe[0] + 4, oe[1] - 2))
    wire(sh, vcc, (vcc[0], vcc[1] - 4))
    rail_symbol(sh, '+5V', (vcc[0], vcc[1] - 4))
    drop_ground(sh, pin_cell(buf, '3'), 2)
    a_pin = pin_cell(buf, '2')
    net_label(sh, 'STATUS_RGB', (a_pin[0] - 14, a_pin[1]), 180, is_global=True)
    wire(sh, a_pin, (a_pin[0] - 14, a_pin[1]))
    vres(sh, '10k', a_pin[0] - 6, a_pin[1])
    drop_ground(sh, (a_pin[0] - 6, a_pin[1] + 6), 0)
    y_pin = pin_cell(buf, '4')
    wire(sh, y_pin, (y_pin[0] + 2, y_pin[1]))
    hres(sh, '330', y_pin[0] + 5, y_pin[1])
    wire(sh, (y_pin[0] + 8, y_pin[1]), pin_cell(rgb, '4'))
    vdd = pin_cell(rgb, '1')
    wire(sh, vdd, (vdd[0], vdd[1] - 6))
    rail_symbol(sh, '+5V', (vdd[0], vdd[1] - 6))
    place_blocks(sh, [('74AHCT1G125 DECOUPLING CAPACITORS', '+5V', ('100nF',)),
                      ('WS2812B DECOUPLING CAPACITORS', '+5V', ('100nF',))], 150, 70, max_column=300)
    drop_ground(sh, pin_cell(rgb, '3'), 2)
    sh.nc(rgb, '2')


# ═════════════════════════════════════════════════════════════════════════
# Project assembly
# ═════════════════════════════════════════════════════════════════════════
SHEETS = [
    ('Power Input', 'power_input', build_power_input, 'A3'),
    ('Power Button', 'power_button', build_power_button, 'A3'),
    ('Rails 5V 3V3', 'rails_logic', build_rails_logic, 'A3'),
    ('Rails +-15V', 'rails_15v', build_rails_15v, 'A3'),
    ('Signal Generator', 'signal_gen', build_signal_gen, 'A3'),
    ('Amp Control', 'amp_control', build_amp_control, 'A3'),
    ('Amp Current', 'amp_current', build_amp_current, 'A3'),
    ('System Current', 'system_current', build_system_current, 'A3'),
    ('Cooling', 'cooling', build_cooling, 'A3'),
    ('Cold Head', 'cold_head', build_cold_head, 'A3'),
    ('IMU', 'imu', build_imu, 'A3'),
    ('Indicators', 'indicators', build_indicators, 'A3'),
]


def sheet_symbol(root_uuid, child, index, x, y):
    width, height = 50.8, 12.7
    return (f'\t(sheet (at {fmt(x)} {fmt(y)}) (size {fmt(width)} {fmt(height)}) (exclude_from_sim no) '
            f'(in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes) '
            f'(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0)) (uuid {q(child.uid)})\n'
            f'\t\t(property "Sheetname" {q(child.title)} (at {fmt(x)} {fmt(y - 0.7)} 0) (show_name no) '
            f'(do_not_autoplace no) (effects (font (size 1.27 1.27)) (justify left bottom)))\n'
            f'\t\t(property "Sheetfile" {q("sheets/" + child.filename)} (at {fmt(x)} {fmt(y + height + 0.6)} 0) '
            f'(show_name no) (do_not_autoplace no) (effects (font (size 1.27 1.27)) (justify left top)))\n'
            f'\t\t(instances (project {q(PROJECT)} (path {q("/" + root_uuid)} (page {q(str(index + 2))}))))\n\t)')


def main():
    kicadgen.reset_uuids()
    root_uuid = kicadgen.stable_uuid('root')
    root = Sheet('Cryocooler Controller', 'cryocooler.kicad_sch', 'A3')
    root.uid = root_uuid
    root.path = '/' + root_uuid
    build_mcu(root)
    children = []
    for index, (title, name, builder, paper) in enumerate(SHEETS):
        child = Sheet(title, name + '.kicad_sch', paper)
        child.uid = kicadgen.stable_uuid('sheet/' + name)
        child.path = f'/{root_uuid}/{child.uid}'
        builder(child)
        children.append(child)
        column, row = index % 4, index // 4
        root.sheet_symbols.append(sheet_symbol(root_uuid, child, index, 20 + column * 70, 190 + row * 25))
    import textlayout
    overlaps = 0
    junctions = 0
    for sheet in [root] + children:
        sheet.finalize()
        for column, row, count in sheet.four_way_junctions():
            print(f'  [{sheet.title}] {count}-way junction at column {column:.0f}, row {row:.0f}')
            junctions += 1
        for problem in textlayout.check_text(sheet):
            overlaps += 1
            print(f'  [{sheet.title}] {problem}')
    print(f'text overlap check: {overlaps} overlaps')
    (ROOT_DIR / 'sheets').mkdir(exist_ok=True)
    (ROOT_DIR / 'cryocooler.kicad_sch').write_text(root.render(root_uuid))
    for child in children:
        (ROOT_DIR / 'sheets' / child.filename).write_text(child.render(root_uuid))
    # the project file lists every sheet's uuid; keep it in step with the generated files
    project_file = ROOT_DIR / 'cryocooler.kicad_pro'
    project = json.loads(project_file.read_text())
    project['sheets'] = [[root_uuid, 'cryocooler']] + [[child.uid, child.title] for child in children]
    project_file.write_text(json.dumps(project, indent=2) + '\n')
    print('wrote', 1 + len(children), 'sheets')
    print(f'4-way junction check: {junctions} found')
    if overlaps or junctions:
        sys.exit(1)


if __name__ == '__main__':
    main()
