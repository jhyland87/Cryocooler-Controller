"""Generates the Cryocooler controller KiCad project (root + sheets).

Run: python3 hardware/kicad/tools/gen_schematic.py
GPIO assignments follow include/config/pin_config.h.
"""

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import kicadgen
from ref_map import REF_MAP
from kicadgen import (
    Sheet,
    next_ref,
    q,
    fmt,
    POWER_SYMBOLS,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT = 'cryocooler'

# ── footprints ───────────────────────────────────────────────────────────
R0603 = 'Resistor_SMD:R_0603_1608Metric'
R1206 = 'Resistor_SMD:R_1206_3216Metric'
R2512 = 'Resistor_SMD:R_2512_6332Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
SMALL_CAPS = ('100nF', '10nF', '1nF/C0G', '120pF', '2pF/C0G', '22pF/C0G')
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
C1210 = 'Capacitor_SMD:C_1210_3225Metric'
CP_ELEC = 'Capacitor_SMD:CP_Elec_8x10'
CP_TANT = 'Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B'
R0402 = 'Resistor_SMD:R_0402_1005Metric'
R0805 = 'Resistor_SMD:R_0805_2012Metric'
# 1206 resistor, or a Bourns 3313J trimmer as a rheostat (make_footprints.py)
R_TRIM = 'cryocooler:R_1206_or_Bourns_3313J'
LED0402 = 'LED_SMD:LED_0402_1005Metric'
SOT323 = 'Package_TO_SOT_SMD:SOT-323_SC-70'
SC70_6 = 'Package_TO_SOT_SMD:SOT-363_SC-70-6'
LED1206 = 'LED_SMD:LED_1206_3216Metric'
LED_RG = 'cryocooler:LED_Kingbright_APGB0607'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
# Right-angle connectors: every plug enters parallel to the board, through the
# housing side walls. Ratings are from each maker's datasheet.
WURTH3_RIGHT_ANGLE = 'cryocooler:Wurth_WR-WTB_61900311021_1x03_P2.54mm_Horizontal'  # 3 A
FAN4_RIGHT_ANGLE = 'cryocooler:FanHeader_4P_P2.54mm_Horizontal'  # takes PC fan plugs
RIGHT_ANGLE_2P = 'cryocooler:Sullins_SWR25X-NRTC-S02-RB-BA_1x02_P2.54mm_Horizontal'  # 3 A
PH_4P = 'cryocooler:Adafruit_4392_JST-PH_1x04_P2.00mm_Horizontal_SMD'  # 2 A
POWER_JACK = 'cryocooler:Tensility_54-00164_5.5x2.1mm_Horizontal_SMD'
SIGNAL_JACK = 'cryocooler:SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD'
# pluggable SMT headers: TE 2305908 (15 A) for the amp current, Phoenix MC 0,5
# (6 A) for the amp control line
TERM_POWER = 'cryocooler:TE_2305908-2_1x02_P5.00mm_Horizontal_SMD'
TERM_POWER3 = 'cryocooler:TE_643228-1_1x03_P6.35mm_Horizontal'
TERM_SIGNAL = 'cryocooler:PhoenixContact_MC_0,5_2-G-2,54_SMD_1x02_P2.54mm_Horizontal'
INDUCTOR = 'cryocooler:L_Bourns_SRP7050TA'

PITCH = 12.7

# Parts added after the first release take numbers above these, clear of
# the sequentially numbered parts (raised for rev 2, whose +-15 V stage had
# more parts than the ADP5071 stage it replaced).
NEW_REFS = {'R': 150, 'C': 120, 'D': 40, 'Q': 20}

# The ADP5071 output capacitors also serve as the LT3097 inputs. No 22 uF / 50 V
# X7R 1210 could be sourced, so the rails use 25 V parts, doubled on -16V5 and
# both LT3097 outputs to hold the required 10 uF effective at 15 V DC.
RAIL_CAP = '22uF/25V X7R'

# Rev 3 parts take numbers above everything earlier, so a surviving part keeps
# its reference. The R, C and D sort by MPN happens before the board is laid out.
REV3_REFS = {'R': 200, 'C': 200, 'D': 60, 'Q': 40, 'U': 32, 'L': 3, 'FB': 0}
BEAD_0402 = 'Inductor_SMD:L_0402_1005Metric'
BEAD_0603 = 'Inductor_SMD:L_0603_1608Metric'


@contextmanager
def high_refs(prefix):
    """Numbers parts created inside the block from the next free number above
    every reference already used on the board.
    """
    with kicadgen.pinned_refs(prefix, NEW_REFS[prefix]):
        yield
        NEW_REFS[prefix] = kicadgen._ref_counters[prefix]


# Parts added for the UCS 125-87 bi-colour LEDs: above every allocated and
# REF_MAP number, so nothing built later shifts.
EXTRA_REFS = {'R': 400, 'Q': 50}


@contextmanager
def extra_refs(prefix):
    """Numbers parts created inside the block from the EXTRA_REFS range."""
    with kicadgen.pinned_refs(prefix, EXTRA_REFS[prefix]):
        yield
        EXTRA_REFS[prefix] = kicadgen._ref_counters[prefix]


@contextmanager
def rev3_refs(*prefixes):
    """Numbers parts created inside the block from the rev 3 ranges."""
    counters = kicadgen._ref_counters
    saved = {prefix: counters[prefix] for prefix in prefixes}
    for prefix in prefixes:
        counters[prefix] = REV3_REFS[prefix]
    yield
    for prefix in prefixes:
        REV3_REFS[prefix] = counters[prefix]
        counters[prefix] = saved[prefix]


def grid(value):
    return round(value / 1.27) * 1.27


# ── component helpers ────────────────────────────────────────────────────
# Discretes are auto-placed beside the pin named by near=(part, pin);
# ICs/connectors are fixed.
def res(sh, value, a, b, near=None, fp=R0402, pose=None, **props):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        'Device:R_US',
        next_ref('R'),
        value,
        px,
        py,
        rot=prot,
        footprint=fp,
        props=props,
        near=near,
        auto=pose is None,
    )
    sh.connect(part, '1', a)
    sh.connect(part, '2', b)
    return part


def cap(sh, value, a, b='GND', near=None, fp=None, pose=None):
    # rev 2 packs small values in 0402 (50 V X7R / C0G), 1 uF in 0603
    fp = fp or (
        C0402
        if value in SMALL_CAPS
        else C0603 if value in ('1uF', '47nF', '68nF')
        else C0805 if value in ('2.2uF', '4.7uF', '10uF') else C1206
    )
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        'Device:C',
        next_ref('C'),
        value,
        px,
        py,
        rot=prot,
        footprint=fp,
        near=near,
        auto=pose is None,
    )
    sh.connect(part, '1', a)
    sh.connect(part, '2', b)
    return part


def cap_pol(sh, value, a, b='GND', near=None, fp=CP_TANT, pose=None):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        'Device:C_Polarized',
        next_ref('C'),
        value,
        px,
        py,
        rot=prot,
        footprint=fp,
        near=near,
        auto=pose is None,
    )
    sh.connect(part, '1', a)
    sh.connect(part, '2', b)
    return part


def led(sh, value, anode, cathode, near=None, fp=LED0402):
    part = sh.add(
        'Device:LED', next_ref('D'), value, 0, 0, footprint=fp, near=near
    )
    sh.connect(part, '2', anode)
    sh.connect(part, '1', cathode)
    return part


def diode(sh, lib_id, value, anode, cathode, fp, near=None, pose=None):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        lib_id,
        next_ref('D'),
        value,
        px,
        py,
        rot=prot,
        footprint=fp,
        near=near,
        auto=pose is None,
    )
    sh.connect(part, '2', anode)
    sh.connect(part, '1', cathode)
    return part


def rg_led(sh, value, column, row, nets):
    """Kingbright APGB0607G22R23C green/red LED centred at (column, row): pins 1 GA
    (row - 2) and 4 RA (row) on the left, 2 GK (row - 2) and 3 RK (row) on the
    right. nets maps a pin to a local label, ('global', name), or None (unused die).
    """
    part = sh.add(
        'cryocooler:APGB0607G22R23C',
        next_ref('D'),
        value,
        column * 1.27,
        row * 1.27,
        auto=False,
        footprint=LED_RG,
    )
    for pin, net in nets.items():
        if net is None:
            sh.nc(part, pin)
            continue
        is_global = isinstance(net, tuple)
        end = spur(sh, part, pin, 2)
        angle = 180 if pin in ('1', '4') else 0
        net_label(sh, net[1] if is_global else net, end, angle, is_global=is_global)
    return part


def nfet(sh, value, gate, drain, source='GND', near=None, fp=SOT23, pose=None):
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        'Transistor_FET:BSS138',
        next_ref('Q'),
        value,
        px,
        py,
        rot=prot,
        footprint=fp,
        near=near,
        auto=pose is None,
    )
    sh.connect(part, '1', gate)
    sh.connect(part, '3', drain)
    sh.connect(part, '2', source)
    return part


def conn(sh, lib_id, value, x, y, nets, fp, rot=0):
    """Generic connector; nets maps pin number -> net (None = no-connect)."""
    part = sh.add(
        lib_id, next_ref('J'), value, x, y, rot=rot, footprint=fp, auto=False
    )
    for number, net in nets.items():
        if net is None:
            sh.nc(part, number)
        else:
            sh.connect(part, number, net)
    return part


def ic(sh, lib_id, value, x, y, nets, ref_prefix='U', fp=None, **kwargs):
    """Fixed IC with pin->net map; None means no-connect."""
    part = sh.add(
        lib_id,
        next_ref(ref_prefix),
        value,
        x,
        y,
        footprint=fp,
        auto=False,
        **kwargs,
    )
    for number, net in nets.items():
        if net is None:
            sh.nc(part, number)
        else:
            sh.connect(part, number, net)
    return part


def aux(sh, lib_id, prefix, value, nets, near=None, fp=None, pose=None):
    """Auto-placed multi-pin discrete (reference, switch, fuse...); pose=(x, y,
    rot) fixes it instead.
    """
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        lib_id,
        next_ref(prefix),
        value,
        px,
        py,
        rot=prot,
        footprint=fp,
        near=near,
        auto=pose is None,
    )
    for number, net in nets.items():
        if net is None:
            sh.nc(part, number)
        else:
            sh.connect(part, number, net)
    return part


def decouple(sh, near, rail, values=('100nF',), gnd='GND'):
    """Decoupling caps from a rail to ground, each anchored at the IC pin."""
    return [cap(sh, value, rail, gnd, near=near) for value in values]


# Decoder output pin -> chip select net. The output number is the firmware's CS
# index (include/config/pin_config.h). The order follows the routed board.
CS_DECODER_OUTPUTS = (
    ('15', 'AD9833_FSYNC'),
    ('14', 'AD5453_SYNC'),
    ('13', 'INA239_CS'),
    ('12', 'EXPANDER_CS'),
    ('11', 'DISP_CS'),
    ('10', 'TOUCH_CS'),
    ('9', 'ADS1220_CS'),
    ('7', 'IMU_CS'),
)
# Last-used numbers: the decoder takes U32, C132, R181-183 and TP45-46.
CS_DECODER_LAST = {'U': 31, 'C': 131, 'R': 180, 'TP': 44}


def cs_decoder(sh):
    """SN74LVC138A: the shared SPI bus chip selects, one low at a time. The enable
    pull-up holds every output high until firmware takes over. The address lines
    are strapping GPIOs, so their strap resistors live here too.
    """
    column, row = 56, 100
    sh.note('SPI CHIP SELECT DECODER', 20 * 1.27, 50 * 1.27, 1.8)
    sh.note(
        'One output low at a time. G2A pull-up: all outputs high at reset.',
        20 * 1.27,
        54 * 1.27,
        1.8,
    )
    sh.note(
        'GPIO3 pull-up and GPIO45 pull-down are strap defaults.',
        20 * 1.27,
        58 * 1.27,
        1.8,
    )
    with kicadgen.pinned_refs('U', CS_DECODER_LAST['U']):
        decoder = place_ic(
            sh,
            'cryocooler:SN74LVC138A',
            'SN74LVC138ARGYR',
            column,
            row,
            'Package_DFN_QFN:Texas_RGY_R-PVQFN-N16_EP2.05x2.55mm',
        )
    for pin, net in (('1', 'CS_ADDR_A'), ('2', 'CS_ADDR_B'), ('3', 'CS_ADDR_C'),
                     ('4', 'CS_EN_N')):
        net_label(sh, net, spur(sh, decoder, pin, 8), 180, is_global=True)
    # G1 and G2B sit at the ends of the side, so their rails have room
    rail_symbol(sh, '+3V3', spur(sh, decoder, '6', 3))
    ground(sh, spur(sh, decoder, '5', 3))
    for pin, net in CS_DECODER_OUTPUTS:
        net_label(sh, net, spur(sh, decoder, pin, 4), 0, is_global=True)
    supply = pin_cell(decoder, '16')
    wire(sh, supply, (supply[0], supply[1] - 4))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
    drop_ground(sh, pin_cell(decoder, '8'), 2)
    drop_ground(sh, pin_cell(decoder, '17'), 2)
    with kicadgen.pinned_refs('C', CS_DECODER_LAST['C']):
        place_blocks(
            sh,
            [('SN74LVC138A DECOUPLING CAPACITOR', '+3V3', ('100nF',))],
            76,
            70,
        )
    with kicadgen.pinned_refs('TP', CS_DECODER_LAST['TP']):
        if keeps_test_point('+3V3'):
            wire(sh, (supply[0], supply[1] - 4), (supply[0] + 4, supply[1] - 4))
            test_point(sh, '+3V3', (supply[0] + 4, supply[1] - 4))
        gnd_cell = pin_cell(decoder, '17')
        if keeps_test_point('GND'):
            wire(sh, (gnd_cell[0], gnd_cell[1] + 2), (gnd_cell[0] + 4, gnd_cell[1] + 2))
            test_point(sh, 'GND', (gnd_cell[0] + 4, gnd_cell[1] + 2), rot=180)
    sh.note('BIAS', 20 * 1.27, 118 * 1.27, 1.8)
    with kicadgen.pinned_refs('R', CS_DECODER_LAST['R']):
        for index, (net, rail) in enumerate(
            (('CS_ADDR_A', '+3V3'), ('CS_EN_N', '+3V3'), ('CS_ADDR_C', 'GND'))
        ):
            bias_row = 124 + index * 8
            rail_symbol(sh, rail, (28, bias_row))
            hres(sh, '10k', 31, bias_row)
            wire(sh, (34, bias_row), (36, bias_row))
            net_label(sh, net, (36, bias_row), 0, is_global=True)


def build_mcu(sh):
    """Hand-laid root sheet: ESP32 in the middle, boot/reset circuits left,
    USB-C right, SPI chip select decoder below.
    """
    sh.handwired = True
    sh.note(
        'ESP32-S3-WROOM-2-N32R16V: 32 MB octal flash + 16 MB octal PSRAM '
        '(GPIO26-37 reserved by module)',
        30,
        15,
    )
    sh.note('GPIO map follows include/config/pin_config.h', 30, 21)
    esp = place_ic(
        sh,
        'RF_Module:ESP32-S3-WROOM-2',
        'ESP32-S3-WROOM-2-N32R16V',
        150,
        100,
        None,
    )
    left = {
        '38': 'IMU_INT1',
        '39': 'PWR_INT',
        '4': 'NTC_ADC',
        '6': 'AMP_REM_EN',
        '12': 'CS_EN_N',
        '17': 'FAN_PWM',
        '18': 'PWR_KILL',
        '19': 'ACS_SCK',
        '20': 'ACS_MOSI',
        '21': 'ACS_MISO',
        '22': 'PUMP_PWM',
        '8': 'FAN_TACH',
        '9': 'COMP_RELAY_EN',
        '15': 'CS_ADDR_A',
    }
    right = {
        '10': 'ACS_CS',
        '11': 'FLOW_TACH',
        '23': 'PUMP_TACH',
        '31': 'STATUS_RGB',
        '32': 'IMU_INT2',
        '33': 'SPI_MISO',
        '34': 'SPI_MOSI',
        '35': 'SPI_SCK',
        '36': 'CS_ADDR_B',
        '37': 'PG_15V_N',
        '26': 'CS_ADDR_C',
        '16': 'DISP_RST',
        '25': 'DISP_DC_1V8',
    }
    for pin, net in left.items():
        net_label(sh, net, spur(sh, esp, pin, 3), 180, is_global=True)
    for pin, net in right.items():
        net_label(sh, net, spur(sh, esp, pin, 3), 0, is_global=True)
    # 28-30 are NC on the module; GPIO5, GPIO7 and GPIO47 (1.8 V) are spare
    for pin in ('28', '29', '30', '5', '7', '24'):
        sh.nc(esp, pin)
    cs_decoder(sh)
    # supplies
    vdd = pin_cell(esp, '2')
    wire(sh, vdd, (vdd[0], 72))
    rail_symbol(sh, '+3V3', (vdd[0], 72))
    place_blocks(
        sh,
        [('ESP32-S3 DECOUPLING CAPACITORS', '+3V3', ('22uF/10V', '100nF'))],
        190,
        38,
    )
    gnd = spur(sh, esp, '1', 2)
    ground(sh, gnd)
    # EN: RC power-on reset plus RESET switch, drawn above the module
    en = pin_cell(esp, '3')
    wire(sh, en, (136, en[1]), (136, 70), (108, 70))
    wire(sh, (136, 70), (136, 67))
    net_label(sh, 'ESP_EN', (136, 67), 0, is_global=True)
    vres(sh, '10k', 124, 64)
    rail_symbol(sh, '+3V3', (124, 64))
    vcap(sh, '1uF', 116, 70)
    drop_ground(sh, (116, 76), 0)
    sw_reset = sh.add(
        'Switch:SW_Push',
        next_ref('SW'),
        'RESET',
        108 * 1.27,
        74 * 1.27,
        rot=270,
        auto=False,
        footprint='cryocooler:SW_Panasonic_EVP-AA',
    )
    wire(sh, (108, 70), pin_cell(sw_reset, '1'))
    ground(sh, pin_cell(sw_reset, '2'))
    # BOOT (GPIO0)
    boot = pin_cell(esp, '27')
    wire(sh, boot, (108, boot[1]))
    wire(sh, (112, boot[1]), (112, boot[1] - 3))
    net_label(sh, 'ESP_BOOT', (112, boot[1] - 3), 180, is_global=True)
    vres(sh, '10k', 126, boot[1] - 6)
    rail_symbol(sh, '+3V3', (126, boot[1] - 6))
    vcap(sh, '100nF', 116, boot[1])
    drop_ground(sh, (116, boot[1] + 6), 0)
    sw_boot = sh.add(
        'Switch:SW_Push',
        next_ref('SW'),
        'BOOT',
        108 * 1.27,
        (boot[1] + 4) * 1.27,
        rot=270,
        auto=False,
        footprint='cryocooler:SW_Panasonic_EVP-AA',
    )
    wire(sh, (108, boot[1]), pin_cell(sw_boot, '1'))
    ground(sh, pin_cell(sw_boot, '2'))
    # USB-C: VBUS can power the logic rail on its own (rails_logic sheet)
    esd = sh.add(
        'cryocooler:SRL05P7',
        next_ref('U'),
        'SRL05P7',
        200 * 1.27,
        100 * 1.27,
        auto=False,
        footprint='cryocooler:MCC_DFN1510-6_1.5x1.0mm_P0.5mm',
    )
    esp_d_minus, esp_d_plus = pin_cell(esd, '4'), pin_cell(esd, '6')
    wire(
        sh, pin_cell(esp, '13'), (180, 90), (180, esp_d_minus[1]), esp_d_minus
    )
    wire(sh, pin_cell(esp, '14'), (178, 92), (178, esp_d_plus[1]), esp_d_plus)
    usb = sh.add(
        'Connector:USB_C_Receptacle_USB2.0_16P',
        next_ref('J'),
        'USB_C',
        240 * 1.27,
        100 * 1.27,
        mirror=True,
        auto=False,
        footprint=(
            'Connector_USB:'
            'USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'
        ),
    )
    d_minus_esd, d_plus_esd = pin_cell(esd, '3'), pin_cell(esd, '1')
    wire(sh, d_minus_esd, pin_cell(usb, 'A7'))
    wire(
        sh,
        pin_cell(usb, 'B7'),
        (224, pin_cell(usb, 'B7')[1]),
        (224, pin_cell(usb, 'A7')[1]),
    )
    a6, b6 = pin_cell(usb, 'A6'), pin_cell(usb, 'B6')
    wire(sh, d_plus_esd, (216, d_plus_esd[1]), (216, a6[1]), a6)
    wire(sh, b6, (224, b6[1]), (224, a6[1]))
    gnd_esd = pin_cell(esd, '2')
    wire(
        sh,
        gnd_esd,
        (gnd_esd[0], gnd_esd[1] + 4),
        (gnd_esd[0] + 4, gnd_esd[1] + 4),
    )
    ground(sh, (gnd_esd[0] + 4, gnd_esd[1] + 4))
    # VBUS: connector, 4.7 uF cap and the ESD clamp share one wire
    vbus_esd = pin_cell(esd, '5')
    vbus = pin_cell(usb, 'A4')
    wire(sh, vbus_esd, (vbus_esd[0], 84), (226, 84), (226, vbus[1]), vbus)
    net_label(sh, 'USB_VBUS', (205, 84), 180, is_global=True)
    vcap(sh, '4.7uF', 210, 84, fp=C0805)
    drop_ground(sh, (210, 90), 0)
    rail_flag(sh, (218, 84))
    cc1, cc2 = pin_cell(usb, 'A5'), pin_cell(usb, 'B5')
    # up one step, so its ground symbol clears the CC2 wire below
    wire(sh, cc1, (225, cc1[1]), (225, cc1[1] - 2))
    hres(sh, '5.1k', 222, cc1[1] - 2)
    ground(sh, (219, cc1[1] - 2))
    wire(sh, cc2, (215, cc2[1]))
    hres(sh, '5.1k', 212, cc2[1])
    ground(sh, (209, cc2[1]))
    for pin in ('A8', 'B8'):
        sh.nc(usb, pin)
    ground(sh, spur(sh, usb, 'A1', 2))
    for pin in ('A12', 'B1', 'B12'):
        pass
    wire(
        sh,
        pin_cell(usb, 'SH'),
        (pin_cell(usb, 'SH')[0], pin_cell(usb, 'SH')[1] + 2),
    )
    ground(sh, (pin_cell(usb, 'SH')[0], pin_cell(usb, 'SH')[1] + 2))


def build_power_input(sh):
    """Hand-laid: DC jack -> fuse -> VIN rail with TVS and bulk/bypass
    caps.
    """
    sh.handwired = True
    sh.note(
        '12 V input from a Dell XYK93 (DPS-2000EB class, ~12.2 V, ~160 A '
        'available): use the main 12 V rail with PS_ON held low.',
        20,
        15,
    )
    sh.note(
        'F1 is a backup only: add an inline high-breaking-capacity fuse '
        '(7.5-10 A) at the PSU end. Reverse polarity: TVS forward-clamps and '
        'blows the fuse.',
        20,
        21,
    )
    # Tensility 54-00164: centre pin positive; the switch contact is tied to the
    # sleeve so a plug can never open the ground return
    j_in = sh.add(
        'Connector:Barrel_Jack_Switch',
        next_ref('J'),
        '12V IN',
        28 * 1.27,
        62 * 1.27,
        rot=0,
        auto=False,
        footprint=POWER_JACK,
    )
    raw = pin_cell(j_in, '1')
    fuse = aux(
        sh,
        'Device:Fuse',
        'F',
        '5A backup',
        {},
        pose=at(46, 60, 90),
        fp='Fuse:Fuse_Littelfuse-NANO2-451_453',
    )
    wire(sh, raw, pin_cell(fuse, '1'))
    rail_flag(sh, (raw[0] + 5, raw[1]))
    gnd = spur(sh, j_in, '2', 2)
    switch = pin_cell(j_in, '3')
    wire(sh, switch, (gnd[0] - 1, switch[1]))
    wire(sh, (gnd[0] - 1, switch[1]), (gnd[0] - 1, gnd[1]))
    # two cells right, so the symbol clears the switch pin's wire
    wire(sh, gnd, (gnd[0] + 2, gnd[1]))
    ground(sh, (gnd[0] + 2, gnd[1]))
    wire(sh, (gnd[0] + 2, gnd[1]), (gnd[0] + 5, gnd[1]))
    rail_flag(sh, (gnd[0] + 5, gnd[1]))
    out = pin_cell(fuse, '2')
    wire(sh, out, (92, out[1]))
    rail_symbol(sh, 'VIN', (92, out[1]))
    rail_flag(sh, (86, out[1]))
    diode(
        sh,
        'Device:D_TVS',
        'SMBJ16A',
        '',
        '',
        'Diode_SMD:D_SMB',
        pose=at(60, 63, 270),
    )
    drop_ground(sh, (60, 66), 0)
    cap_pol(sh, '100uF/35V', '', '', pose=at(70, 63), fp=CP_ELEC)
    drop_ground(sh, (70, 66), 0)
    cap(sh, '100nF', '', '', pose=at(80, 63), fp=C0805)
    drop_ground(sh, (80, 66), 0)


def build_power_button(sh):
    """Hand-laid: LTC2954 controller top left, P-FET power switch right,
    standby LED below.
    """
    sh.handwired = True
    sh.note(
        'LTC2954-2: tap PB = on, hold = off. EN# drives the P-FET gate; KILL# from '
        'GPIO10 (active low, 100 ms pulse). INT# tells GPIO1 to shut down cleanly; '
        'holding PB cuts power about 6.4 s later (1 uF on PDT).',
        20,
        15,
    )
    sh.note(
        'Q1 gate: 10k series and 47 nF to the drain limit the ramp to about 20 V/ms; '
        '470 nF to the source holds Vgs under 1.1 V on a hot plug (10 x Cgd); the '
        'Zener caps Vgs at 15 V for input transients up to the 26 V TVS clamp.',
        20,
        21,
    )
    u = place_ic(
        sh,
        'cryocooler:LTC2954CDDB-2',
        'LTC2954CDDB-2',
        60,
        60,
        'Package_DFN_QFN:DFN-8-1EP_2x3mm_P0.5mm_EP0.61x2.2mm',
    )
    # supply with bypass above the controller
    vin_pin = pin_cell(u, '4')
    wire(sh, vin_pin, (vin_pin[0], 46))
    rail_symbol(sh, 'VIN', (vin_pin[0], 46))
    place_blocks(
        sh, [('LTC2954 DECOUPLING CAPACITORS', 'VIN', ('100nF',))], 170, 40
    )
    gnd_bus(sh, [pin_cell(u, '1'), pin_cell(u, '9')])
    # push button, panel connector, ONT left open
    pb = pin_cell(u, '3')
    wire(sh, pb, (36, pb[1]))
    sw = sh.add(
        'Switch:SW_Push',
        next_ref('SW'),
        'POWER',
        30 * 1.27,
        pb[1] * 1.27,
        mirror=True,
        auto=False,
        footprint='cryocooler:SW_TE_1571300-2',
    )
    wire(sh, (36, pb[1]), pin_cell(sw, '1'))
    wire(sh, pin_cell(sw, '2'), (24, pb[1]))
    ground(sh, (24, pb[1]))
    j_panel = sh.add(
        'Connector_Generic:Conn_01x02',
        next_ref('J'),
        'PANEL BUTTON',
        24 * 1.27,
        66 * 1.27,
        rot=0,
        mirror=True,
        auto=False,
        footprint=RIGHT_ANGLE_2P,
    )
    wire(sh, pin_cell(j_panel, '1'), (36, 66), (36, pb[1]))
    wire(
        sh,
        pin_cell(j_panel, '2'),
        (pin_cell(j_panel, '2')[0] + 2, pin_cell(j_panel, '2')[1]),
    )
    ground(sh, (pin_cell(j_panel, '2')[0] + 2, pin_cell(j_panel, '2')[1]))
    # the panel button sits on a long cable, so its line gets an ESD clamp
    with rev3_refs('U'):
        clamp = place_ic(
            sh,
            'cryocooler:TPD1E05U06DPYR',
            'TPD1E05U06DPYR',
            46,
            76,
            'Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm',
        )
    wire(sh, (36, 66), (36, pin_cell(clamp, '1')[1]), pin_cell(clamp, '1'))
    drop_ground(sh, pin_cell(clamp, '2'), 2)
    sh.nc(u, '2')
    # KILL#: 220k to the 5 V shunt reference, 10k from the MCU
    kill = pin_cell(u, '5')
    wire(sh, kill, (80, kill[1]))
    vres(sh, '220k', 80, 50)
    vres(sh, '10k', 80, 56)
    wire(sh, (80, 62), (84, 62))
    net_label(sh, 'PWR_KILL', (84, 62), 0, is_global=True)
    wire(sh, (80, 50), (80, 44), (88, 44))
    vres(sh, '82k', 80, 38)
    rail_symbol(sh, 'VIN', (80, 38))
    ref = aux(
        sh,
        'Reference_Voltage:LM4040DBZ-5',
        'U',
        'LM4040DBZ-5',
        {},
        pose=at(88, 47, 90),
        fp=SOT23,
    )
    sh.nc(ref, '3')
    ground(sh, (88, 50))
    # PDT cap, EN# to the P-FET gate, INT# with pull-up and its own GPIO
    pdt = pin_cell(u, '6')
    wire(sh, pdt, (74, pdt[1]))
    vcap(sh, '1uF', 74, pdt[1])
    drop_ground(sh, (74, pdt[1] + 6), 0)
    en, intr = pin_cell(u, '7'), pin_cell(u, '8')
    wire(sh, en, (72, en[1]), (72, 70), (100, 70))
    wire(sh, intr, (71, intr[1]), (71, 76), (76, 76), (81, 76))
    hres(sh, '10k', 84, 76)
    rail_symbol(sh, '+3V3', (87, 76))
    if keeps_test_point('LTC2954_INT'):
        wire(sh, (76, 76), (76, 80))
        test_point(sh, 'LTC2954_INT', (76, 80), rot=180)
    else:
        kicadgen.retire_refs('TP', 1)
    wire(sh, (71, 76), (71, 90), (78, 90))
    net_label(sh, 'PWR_INT', (78, 90), 0, is_global=True)
    # high-side P-FET switch: series resistor, then Zener, Cgs, pull-up and Cgd
    with rev3_refs('R'):
        hres(sh, '10k', 103, 70)
    wire(sh, (106, 70), (112, 70), (124, 70), (134, 70), (144, 70), (160, 70))
    q1 = place_ic(
        sh,
        'cryocooler:AONR21307',
        'AONR21307',
        168,
        72,
        'cryocooler:AOS_DFN3x3A_8L_EP1',
        ref_prefix='Q',
    )
    wire(sh, (112, 64), (124, 64), (134, 64))
    rail_symbol(sh, 'VIN', (134, 64))
    with rev3_refs('D'):
        zener = diode(
            sh,
            'Device:D_Zener',
            'BZT52C15',
            '',
            '',
            'Diode_SMD:D_SOD-123',
            pose=at(112, 67, 90),
        )
    if pin_cell(zener, '1')[1] > pin_cell(zener, '2')[1]:
        zener.rot = 270
    with rev3_refs('C'):
        vcap(sh, '470nF', 124, 64, fp=C0805)
        vcap(sh, '47nF', 144, 70)
    vres(sh, '100k', 134, 64)
    source, drain = pin_cell(q1, '1'), pin_cell(q1, '5')
    wire(sh, source, (source[0] + 4, source[1]), (source[0] + 4, source[1] - 8))
    rail_symbol(sh, 'VIN', (source[0] + 4, source[1] - 8))
    wire(
        sh,
        drain,
        (drain[0] + 10, drain[1]),
        (drain[0] + 16, drain[1]),
        (drain[0] + 22, drain[1]),
    )
    rail_symbol(sh, 'VSW', (drain[0] + 16, drain[1]))
    rail_flag(sh, (drain[0] + 22, drain[1]))
    wire(sh, (144, 76), (144, 80), (drain[0] + 10, 80), (drain[0] + 10, drain[1]))
    # numbers of the removed CL25, bi-colour LED and its H-bridge
    kicadgen.retire_refs('U', 1)
    kicadgen.retire_refs('D', 1)
    kicadgen.retire_refs('Q', 3)
    kicadgen.retire_refs('R', 5)
    # status LED: red from VIN in standby (shorted once +3V3 is up), green on +5V;
    # both lit means +5V is up but +3V3 is not
    sh.note(
        'STATUS LED: red = standby (about 0.8 mA from VIN, off when +3V3 is up), '
        'green = on (+5V, about 1 mA), both = +3V3 missing',
        20 * 1.27,
        92 * 1.27,
        1.8,
    )
    rail_symbol(sh, 'VIN', (40, 104))
    wire(sh, (40, 104), (44, 104))
    with rev3_refs('R', 'D', 'Q'):
        hres(sh, '13k', 47, 104)
        indicator = rg_led(
            sh, 'STATUS G=on R=standby', 100, 110, {'1': 'STATUS_GA', '4': 'STATUS_RA'}
        )
        shunt = nfet(sh, 'BSS138', '', '', pose=at(58, 112))
    wire(sh, (50, 104), (60, 104), (70, 104))
    net_label(sh, 'STATUS_RA', (70, 104), 0)
    green_k, red_k = spur(sh, indicator, '2', 2), spur(sh, indicator, '3', 2)
    wire(sh, green_k, red_k)
    drop_ground(sh, red_k, 2)
    rail_symbol(sh, '+5V', (84, 100))
    wire(sh, (84, 100), (88, 100))
    with extra_refs('R'):
        hres(sh, '2.2k', 91, 100)
    wire(sh, (94, 100), (96, 100))
    net_label(sh, 'STATUS_GA', (96, 100), 0)
    wire(sh, (60, 104), pin_cell(shunt, '3'))
    ground(sh, spur(sh, shunt, '2', 2))
    gate = pin_cell(shunt, '1')
    wire(sh, gate, (gate[0] - 4, gate[1]))
    rail_symbol(sh, '+3V3', (gate[0] - 4, gate[1]))


def wire(sh, *points):
    """Hand-drawn polyline through (column, row) cells (1.27 mm grid)."""
    for first, second in zip(points, points[1:]):
        if first == second:
            continue
        sh.wires.append(
            (
                (first[0] * 1.27, first[1] * 1.27),
                (second[0] * 1.27, second[1] * 1.27),
            )
        )


def rail_symbol(sh, net, cell, rot=0):
    """Hand-placed power symbol whose pin sits on the given cell; rot turns
    the symbol (GND points down at 0, +3V3 points up).
    """
    kicadgen._pwr_counter[0] += 1
    part = sh.add(
        f'power:{POWER_SYMBOLS[net]}',
        f'#PWR{kicadgen._pwr_counter[0]:03d}',
        net,
        cell[0] * 1.27,
        cell[1] * 1.27,
        rot=rot,
        auto=False,
    )
    part.is_power = True
    return part


def rail_flag(sh, cell):
    kicadgen._pwr_counter[0] += 1
    part = sh.add(
        'power:PWR_FLAG',
        f'#FLG{kicadgen._pwr_counter[0]:03d}',
        'PWR_FLAG',
        cell[0] * 1.27,
        cell[1] * 1.27,
        rot=0,
        auto=False,
    )
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


def vres(sh, value, column, top, fp=R0402):
    """Vertical resistor: pin 1 on (column, top), pin 2 six cells lower."""
    return res(sh, value, '', '', pose=at(column, top + 3), fp=fp)


def vcap(sh, value, column, top, fp=None):
    """Vertical capacitor with pin 1 on (column, top); pin 2 is six cells
    lower.
    """
    return cap(sh, value, '', '', pose=at(column, top + 3), fp=fp)


def hres(sh, value, column, row, fp=R0402):
    """Horizontal resistor centred on (column, row): pin 1 left, pin 2 right
    (three cells each side).
    """
    return res(sh, value, '', '', pose=at(column, row, 90), fp=fp)


def hcap(sh, value, column, row, fp=None):
    return cap(sh, value, '', '', pose=at(column, row, 90), fp=fp)


TP_PAD = 'TestPoint:TestPoint_Pad_D1.0mm'
TP_LOOP = 'TestPoint:TestPoint_Keystone_5015_Micro_Mini'


# Short test point names: the value is what the PCB silkscreen prints beside
# the pad, and JLCPCB's 1.0 mm minimum text height leaves room for about six
# characters on this board. Names not listed print as they are.
TP_NAMES = {
    'LTC2954_INT': 'PB_INT',
    'ADS1220_DRDY': 'DRDY',
    'EXPANDER_INT': 'EXPINT',
    'TOUCH_IRQ': 'T_IRQ',
    'ISO_5V': 'ISO5V',
    'ISO_GND': 'ISOGND',
    'FAN_PWM': 'FANPWM',
    'PUMP_PWM': 'PMPPWM',
    'FAN_TACH': 'FANTCH',
    'PUMP_TACH': 'PMPTCH',
    'PWR_KILL': 'KILL',
    'COMP_RELAY_EN': 'RLY_EN',
    'AMP_REM_EN': 'REM_EN',
    'PG_15V': 'PG15V',
    'DDS_SINE': 'DDS',
    'SIG_SINE': 'SINE',
    'NTC_ADC': 'NTC',
    'FLOW_TACH': 'FLOW',
    'USB_VBUS': 'VBUS',
    '+5V_OR': '5V_OR',
    'U5_OUT': 'U5OUT',
}

# UCS 125-87 board: only the waveform and +-15 V test points stay (plus one
# GND loop, kept in build_debug). Dropped points retire their numbers.
KEPT_TEST_POINTS = {
    'DDS_SINE',
    'U5_OUT',
    'SIG_SINE',
    '+15V',
    '-15V',
    '+16V5',
    '-16V5',
}


def keeps_test_point(label):
    return KEPT_TEST_POINTS is None or label in KEPT_TEST_POINTS


def test_point(sh, label, cell, fp=TP_PAD, rot=0):
    """Test point whose connection sits on the given cell; rot 0 hangs the
    pad above the wire end, rot 180 below it. Its value is the short name
    from TP_NAMES (printed on the board).
    """
    return sh.add(
        'Connector:TestPoint',
        next_ref('TP'),
        TP_NAMES.get(label, label),
        cell[0] * 1.27,
        cell[1] * 1.27,
        rot=rot,
        auto=False,
        footprint=fp,
    )


def ground(sh, cell):
    return rail_symbol(sh, 'GND', cell)


def drop_ground(sh, cell, length=2):
    """Wire straight down from a cell to a GND symbol."""
    wire(sh, cell, (cell[0], cell[1] + length))
    return rail_symbol(sh, 'GND', (cell[0], cell[1] + length))


def gnd_bus(sh, cells, net='GND', length=2):
    """Joins several ground pin tips on one bar below them and drops a ground
    symbol from the middle pin.
    """
    ordered = sorted(cells)
    bar = max(cell[1] for cell in ordered) + length
    middle = ordered[len(ordered) // 2]
    for column, row in ordered:
        wire(sh, (column, row), (column, bar))
    wire(sh, (ordered[0][0], bar), (ordered[-1][0], bar))
    wire(sh, (middle[0], bar), (middle[0], bar + 2))
    rail_symbol(sh, net, (middle[0], bar + 2))


def net_label(sh, net, cell, angle=0, is_global=False):
    """Net label whose connection point is the given cell (text extends away
    along angle).
    """
    kind = 'global_label' if is_global else 'label'
    sh.labels.append((kind, net, (cell[0] * 1.27, cell[1] * 1.27), angle))


def decoupling_block(sh, title, column, row, supply, values, ground='GND'):
    """Standalone bank of decoupling caps: supply rail on top, ground bus
    below, one cap per value.

    Returns the width in cells (rail plus title, whichever is wider)."""
    caps = [column + 6 + 12 * index for index in range(len(values))]
    sh.note(title, column * 1.27, (row - 8) * 1.27, 1.8)
    wire(sh, (column, row), (caps[-1], row))
    wire(sh, (column, row + 6), (caps[-1], row + 6))
    rail_symbol(sh, supply, (column, row))
    rail_symbol(sh, ground, (column, row + 6))
    for x, value in zip(caps, values):
        vcap(sh, value, x, row, fp=C0805 if value == '10uF' else None)
    return max(caps[-1] - column, round(len(title) * 1.4)) + 6


def place_blocks(sh, blocks, column, row, max_column=240, row_pitch=22):
    """Lay out decoupling blocks left to right from (column, row), wrapping to
    a new row at max_column. A number in place of a block retires that many
    capacitor references.
    """
    x = column
    for block in blocks:
        if isinstance(block, int):
            kicadgen.retire_refs('C', block)
            continue
        title, supply, values, *ground = block
        width = max(12 * len(values) + 6, round(len(title) * 1.4)) + 6
        if x + width > max_column:
            x, row = column, row + row_pitch
        decoupling_block(
            sh, title, x, row, supply, values, ground[0] if ground else 'GND'
        )
        x += width


def build_rails_logic(sh):
    """Hand-laid sheet: input rail, 5 V buck switching loop, output rail, the
    3.3 V buck, then the +5V / USB power mux.
    """
    sh.handwired = True
    sh.note(
        '12 V -> 5 V (AP63205 buck, datasheet Fig. 1 / Table 3: 4.7 uH, 10 '
        'uF in, 2 x 22 uF out, 100 nF bootstrap) -> 3.3 V (TPS62822 buck, 2 A).',
        20,
        15,
    )
    sh.note(
        'AP63205: VIN 3.8-32 V (40 V for 400 ms), EN tied to VIN, FB tied to '
        'the fixed 5 V output.',
        20,
        21,
    )
    sh.note(
        'TPS62822 (SLUSCY3): VOUT = 0.6 V x (1 + 453k/100k) = 3.32 V, Cff = 12 us / R2 '
        '= 120 pF, 0.47 uH, 22 uF ceramic out. PG and NC stay open.',
        20,
        27,
    )
    u5 = ic(
        sh,
        'Regulator_Switching:AP63205WU',
        'AP63205WU-7',
        110.49,
        100.33,
        {},
        fp='Package_TO_SOT_SMD:TSOT-23-6',
    )
    # input rail: +12V symbol, 10 uF and 100 nF down to ground, VIN and EN tied
    # together
    wire(sh, (44, 77), (50, 77), (64, 77), (77, 77), (79, 77))
    rail_symbol(sh, '+12V', (44, 77))
    cap(sh, '10uF/50V', '', '', pose=at(50, 80))
    cap(sh, '100nF', '', '', pose=at(64, 80))
    for column in (50, 64):
        rail_symbol(sh, 'GND', (column, 83))
    wire(sh, (79, 81), (77, 81), (77, 77))
    wire(sh, (87, 85), (87, 87))
    rail_symbol(sh, 'GND', (87, 87))
    # switching loop: SW up and right to the inductor, bootstrap cap between SW
    # and BST
    wire(sh, (95, 77), (97, 77), (97, 73), (101, 73), (105, 73))
    cap(sh, '100nF', '', '', pose=at(101, 76))
    wire(sh, (95, 79), (101, 79))
    inductor = aux(
        sh,
        'Device:L',
        'L',
        'SRP4020TA-4R7M',
        {},
        pose=at(108, 73, 90),
        fp='cryocooler:L_Bourns_SRP4020TA',
    )
    # output rail with FB feedback and two 22 uF caps
    wire(sh, (111, 73), (121, 73), (127, 73), (142, 73), (154, 73))
    wire(sh, (95, 81), (119, 81), (119, 73))
    rail_symbol(sh, '+5V', (121, 73))
    cap(sh, '22uF/10V', '', '', pose=at(127, 76), fp=C1206)
    rail_symbol(sh, 'GND', (127, 79))
    cap(sh, '22uF/10V', '', '', pose=at(72, 114), fp=C1206)  # buck input, on +5V_OR
    rail_symbol(sh, 'GND', (72, 117))
    rail_flag(sh, (154, 73))
    # 3.3 V buck: VIN and EN on +5V_OR, then SW -> 0.47 uH -> +3V3
    u3 = place_ic(
        sh,
        'cryocooler:TPS62822DLCR',
        'TPS62822DLCR',
        87,
        115,
        'Package_SON:Texas_VSON-HR-8_1.5x2mm_P0.5mm',
    )
    wire(sh, (64, 111), (72, 111), (77, 111), (79, 111))
    rail_symbol(sh, '+5V_OR', (64, 111))
    wire(sh, pin_cell(u3, '1'), (77, pin_cell(u3, '1')[1]), (77, 111))
    gnd_bus(sh, [pin_cell(u3, '3'), pin_cell(u3, '5')])
    sh.nc(u3, '8')
    sh.nc(u3, '4')
    cap(sh, '22uF/10V', '', '', pose=at(142, 76), fp=C1206)
    rail_symbol(sh, 'GND', (142, 79))
    with rev3_refs('L'):
        aux(
            sh,
            'Device:L',
            'L',
            'SRP4020TA-R47M',
            {},
            pose=at(100, 111, 90),
            fp='cryocooler:L_Bourns_SRP4020TA',
        )
    wire(sh, pin_cell(u3, '6'), (97, 111))
    cap(sh, '22uF/10V', '', '', pose=at(112, 114), fp=C1206)
    wire(sh, (103, 111), (112, 111), (120, 111), (130, 111), (138, 111), (146, 111), (152, 111))
    rail_symbol(sh, '+3V3', (146, 111))
    rail_flag(sh, (152, 111))  # the inductor is passive, so nothing else drives the rail
    cap(sh, '100nF', '', '', pose=at(120, 114))
    for column in (112, 120):
        rail_symbol(sh, 'GND', (column, 117))
    # feedback divider and feed-forward cap
    with rev3_refs('R', 'C'):
        vres(sh, '453k', 130, 111)
        vres(sh, '100k', 130, 117)
        vcap(sh, '120pF', 138, 111)
    drop_ground(sh, (130, 123), 0)
    wire(sh, (138, 117), (136, 117), (130, 117))
    feedback = pin_cell(u3, '2')
    wire(sh, feedback, (97, feedback[1]), (97, 129), (136, 129), (136, 117))
    usb_power_path(sh)
    return u5, u3, inductor


def usb_power_path(sh):
    """TPS2116 feeding +5V_OR from +5V, or from USB VBUS when +5V falls below about
    4.3 V (0.92-1.08 V at PR1 through 33k / 10k). Priority mode needs MODE on VIN1.
    """
    sh.note(
        '+5V_OR: USB alone powers +3V3 and the logic, not the +5V rail or the +-15 V stage. '
        'TPS2116 SLVSEH8 7.6.1: MODE on VIN1, divider VIN1 to PR1 sets the changeover.',
        20,
        178,
    )
    with kicadgen.pinned_refs('U', 27):
        mux = place_ic(
            sh,
            'cryocooler:TPS2116DRLR',
            'TPS2116DRLR',
            100,
            160,
            'Package_TO_SOT_SMD:SOT-583-8',
        )
    # main input: +5V, MODE tied to it, divider to PR1
    vin1, mode, priority = (pin_cell(mux, pin) for pin in ('3', '5', '4'))
    wire(sh, vin1, (86, vin1[1]), (70, vin1[1]), (62, vin1[1]))
    rail_symbol(sh, '+5V', (62, vin1[1]))
    wire(sh, mode, (86, mode[1]), (86, vin1[1]))
    with rev3_refs('R'):
        vres(sh, '33k', 70, vin1[1])
        vres(sh, '10k', 70, vin1[1] + 6)
    drop_ground(sh, (70, vin1[1] + 12), 0)
    wire(sh, priority, (82, priority[1]), (82, vin1[1] + 6), (70, vin1[1] + 6))
    # USB input with its own 1 uF and test point
    usb_in = pin_cell(mux, '6')
    wire(sh, usb_in, (84, usb_in[1]), (84, 176), (68, 176), (60, 176), (52, 176))
    net_label(sh, 'USB_VBUS', (52, 176), 180, is_global=True)
    with kicadgen.pinned_refs('C', 125):
        vcap(sh, '1uF', 60, 176)
    drop_ground(sh, (60, 182), 0)
    with kicadgen.pinned_refs('TP', 42):
        if keeps_test_point('USB_VBUS'):
            test_point(sh, 'USB_VBUS', (68, 176), rot=0)
    # common output
    out = pin_cell(mux, '2')
    wire(sh, out, (150, out[1]))
    rail_symbol(sh, '+5V_OR', (150, out[1]))
    with kicadgen.pinned_refs('TP', 43):
        if keeps_test_point('+5V_OR'):
            wire(sh, (150, out[1]), (156, out[1]))
            test_point(sh, '+5V_OR', (156, out[1]), rot=0)
    sh.nc(mux, '8')
    drop_ground(sh, pin_cell(mux, '1'), 2)


def place_ic(
    sh, lib_id, value, column, row, fp, ref_prefix='U', rot=0, **kwargs
):
    """Fixed IC centred on a grid cell; wiring is drawn by hand."""
    return ic(
        sh,
        lib_id,
        value,
        column * 1.27,
        row * 1.27,
        {},
        ref_prefix=ref_prefix,
        fp=fp,
        rot=rot,
        **kwargs,
    )


def build_rails_15v(sh):
    """Hand-laid: ADP5071 with its input rail to the left, boost channel upper
    right, inverting channel lower right, one LT3097 below.
    """
    sh.handwired = True
    sh.note(
        'ADP5071ACPZ (5 V in): +16.4 V boost and -16.5 V inverting rails; '
        'one LT3097 post-regulates them to +/-14.7 V.',
        20,
        15,
    )
    sh.note(
        'ADP5071 values from datasheet Fig. 47 / Tables 9-11. LT3097: VOUT = '
        '100 uA x RSET (147k = 14.7 V, +15 V is the top of its range); '
        'PGFB dividers 432k/10k trip power good near 13.3 V (also enables '
        'fast start-up).',
        20,
        21,
    )
    sh.note(
        'ADP5071 layout: keep PGND off the exposed pad on the top layer (datasheet '
        'layout section). SEQ on VREG starts both channels together when EN2 rises.',
        20,
        27,
    )
    u = place_ic(
        sh,
        'cryocooler:ADP5071ACPZ',
        'ADP5071ACPZ',
        110,
        100,
        'Package_CSP:LFCSP-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm',
    )
    # +5V input: bus left of the IC, rail above it, three decoupling caps
    wire(sh, (96, 70), (96, 102))
    rail_symbol(sh, '+5V_PS15', (96, 70))
    for pin in ('7', '15', '17', '16', '9'):
        spur(sh, u, pin, 2)
    place_blocks(
        sh,
        [('ADP5071 DECOUPLING CAPACITORS', '+5V_PS15', ('10uF', '10uF', '100nF'))],
        190,
        150,
    )
    # COMP1 network (left, above the bus crossing): 5.6k then 47nF to ground
    wire(sh, pin_cell(u, '6'), (93, 84))
    hres(sh, '5.6k', 90, 84)
    wire(sh, (87, 84), (84, 84))
    vcap(sh, '47nF', 84, 84)
    drop_ground(sh, (84, 90), 0)
    # VREG: pin 14 and SEQ (pin 3) joined on one wire with its 1 uF cap
    wire(sh, pin_cell(u, '14'), (88, 96), (88, 106), (88, 108))
    wire(sh, pin_cell(u, '3'), (88, pin_cell(u, '3')[1]))
    wire(sh, (88, 106), (84, 106))
    vcap(sh, '1uF', 84, 106)
    drop_ground(sh, (84, 112), 0)
    # COMP2 network: 12k then 68nF to ground
    wire(sh, pin_cell(u, '10'), (81, 100))
    hres(sh, '12k', 78, 100)
    wire(sh, (75, 100), (72, 100))
    vcap(sh, '68nF', 72, 100)
    drop_ground(sh, (72, 106), 0)
    # SS not connected; SYNC, SLEW and the grounds share one bar along the bottom
    sh.nc(u, '8')
    gnd_bus(
        sh, [pin_cell(u, number) for number in ('2', '4', '13', '21', '19')]
    )
    # boost channel
    aux(
        sh,
        'Device:L',
        'L',
        'SRP7050TA-3R3M',
        {},
        pose=at(128, 88, 90),
        fp=INDUCTOR,
    )
    wire(sh, pin_cell(u, '1'), (125, 88))
    wire(sh, pin_cell(u, '20'), (131, 90), (131, 88))
    wire(sh, (131, 90), (135, 90))
    diode(
        sh,
        'Device:D_Schottky',
        'DFLS240',
        '',
        '',
        'Diode_SMD:D_PowerDI-123',
        pose=at(138, 90, 180),
    )
    wire(sh, (141, 90), (150, 90), (166, 90), (172, 90))
    rail_symbol(sh, '+16V5', (141, 90))
    rail_flag(sh, (172, 90))
    vres(sh, '2.67M', 150, 90)
    vres(sh, '137k', 150, 96)
    drop_ground(sh, (150, 102), 0)
    wire(sh, (150, 96), (124, 96), (124, 92), pin_cell(u, '5'))
    vcap(sh, RAIL_CAP, 166, 90, fp=C1210)
    drop_ground(sh, (166, 96), 0)
    # inverting channel
    aux(
        sh,
        'Device:L',
        'L',
        'SRP7050TA-6R8M',
        {},
        pose=at(131, 111),
        fp=INDUCTOR,
    )
    drop_ground(sh, (131, 114), 0)
    wire(sh, pin_cell(u, '18'), (131, 108), (135, 108))
    diode(
        sh,
        'Device:D_Schottky',
        'DFLS240',
        '',
        '',
        'Diode_SMD:D_PowerDI-123',
        pose=at(138, 108),
    )
    wire(sh, (141, 108), (150, 108), (166, 108), (178, 108), (184, 108))
    rail_symbol(sh, '-16V5', (141, 108))
    rail_flag(sh, (184, 108))
    wire(sh, (150, 108), (150, 112))
    vres(sh, '2.55M', 150, 112)
    vres(sh, '118k', 150, 118)
    vcap(sh, RAIL_CAP, 166, 108, fp=C1210)
    drop_ground(sh, (166, 114), 0)
    with kicadgen.pinned_refs('C', 130):
        vcap(sh, RAIL_CAP, 178, 108, fp=C1210)
    drop_ground(sh, (178, 114), 0)
    wire(sh, (150, 118), (126, 118), (126, 106), pin_cell(u, '11'))
    wire(sh, pin_cell(u, '12'), (124, 104), (124, 124), (130, 124), (150, 124))
    vcap(sh, '1uF', 130, 124)
    drop_ground(sh, (130, 130), 0)
    # the rev 2 stage used two more capacitors than this one
    kicadgen.retire_refs('C', 2)
    # LT3097: +15 V regulator on top, -15 V regulator below, both inputs on
    # the left, feedback and power-good parts on the right
    reg = place_ic(
        sh,
        'cryocooler:LT3097ADJC',
        'LT3097ADJC',
        84,
        172,
        'cryocooler:DFN-22-2EP_6x3mm_P0.5mm_LT3097',
    )
    kicadgen.retire_refs('U', 1)  # U22 was the ADP7182
    for rail, input_pin, enable_pin in (
        ('+16V5', '1', '3'),
        ('-16V5', '6', '8'),
    ):
        vin, enable = pin_cell(reg, input_pin), pin_cell(reg, enable_pin)
        wire(sh, vin, (vin[0] - 14, vin[1]))
        rail_symbol(sh, rail, (vin[0] - 14, vin[1]))
        # ENP/UVP and ENN/UVN tied to the input: on whenever the rail is up
        wire(sh, enable, (enable[0] - 2, enable[1]), (enable[0] - 2, vin[1]))
    # grounds and the unused current-limit pins share one bar
    gnd_bus(sh, [pin_cell(reg, number) for number in ('5', '13', '11')])
    channels = (
        # output, sense, PGFB, PG, SET pin, rail net, power-good node
        ('21', '20', '17', '4', '18', '+15V', 'PGP_15V'),
        ('15', '14', '10', '9', '12', '-15V', 'PGN_15V'),
    )
    for index, channel in enumerate(channels):
        out, sense, feedback, good, setpoint, rail, good_net = channel
        o, s = pin_cell(reg, out), pin_cell(reg, sense)
        # output rail: Kelvin sense joins the output wire, 2 x 22 uF at the end
        wire(sh, o, (o[0] + 46, o[1]))
        rail_symbol(sh, rail, (o[0] + 46, o[1]))
        wire(sh, s, (s[0] + 4, s[1]), (s[0] + 4, o[1]))
        vcap(sh, RAIL_CAP, o[0] + 40, o[1], fp=C1210)
        drop_ground(sh, (o[0] + 40, o[1] + 6), 0)
        with kicadgen.pinned_refs('C', 128 + index):
            vcap(sh, RAIL_CAP, o[0] + 34, o[1], fp=C1210)
        drop_ground(sh, (o[0] + 34, o[1] + 6), 0)
        # power-good threshold divider from the output (tap = PGFB pin)
        pgfb = pin_cell(reg, feedback)
        divider = o[0] + 14
        vres(sh, '432k', divider, o[1])
        with high_refs('R'):
            vres(sh, '10k', divider, o[1] + 6)
        drop_ground(sh, (divider, o[1] + 12), 0)
        wire(sh, pgfb, (divider, pgfb[1]))
        # open-collector power-good pin to its own node
        net_label(
            sh, good_net, spur(sh, reg, good, 2), 0, is_global=True
        )
        # SET resistor and bypass cap to ground
        pin = pin_cell(reg, setpoint)
        wire(sh, pin, (pin[0] + 14, pin[1]))
        vres(sh, '147k', pin[0] + 8, pin[1])
        vcap(sh, '1uF/50V', pin[0] + 14, pin[1], fp=C1206)
        wire(sh, (pin[0] + 8, pin[1] + 6), (pin[0] + 14, pin[1] + 6))
        drop_ground(sh, (pin[0] + 8, pin[1] + 6), 2)
    kicadgen.retire_refs('C', 1)  # the old block used five capacitors


def build_power_good(sh):
    """Hand-laid: one node and LED per LT3097 power-good pin, their AND as
    PG_15V, the active-low flag for the ESP32 and the -15 V guard.
    """
    sh.handwired = True
    sh.note(
        'PGP and PGN pull their own node low when bad. Each node is the +15 V '
        'rail through 220k/62k (about 3.2 V when good, under 0.3 V if its pin '
        'pulls low or the rail is missing) and lights its LED green, or red when low.',
        20,
        15,
    )
    sh.note(
        'PG_15V = the two nodes ANDed by a BAT54AW with a 470k pull-up to +3V3 '
        '(weak so it cannot lift dead nodes; 3.3 V only when both are good); it gates the amplifier REM '
        'switch and reads LOW on GPIO43 (PG_15V_N) when both rails are good.',
        20,
        21,
    )
    power_good_node(sh, 'PGP_15V', 30, 40)
    power_good_node(sh, 'PGN_15V', 50, 40)
    NEW_REFS['R'] += 4  # the removed +-16.5 V power good dividers
    power_good_and(sh, 90, 44)
    power_good_flag(sh, 160, 80)
    power_good_led(sh, 'PGP_15V', 'PG +15V G=good R=bad', 30, 110)
    power_good_led(sh, 'PGN_15V', 'PG -15V G=good R=bad', 100, 110)
    power_good_guard(sh, 30, 150)


def power_good_guard(sh, column, row):
    """An unpowered LT3097 negative channel can't pull PGN low, so PGN_15V would
    read good with -15 V missing. The midpoint of two 470k resistors between the
    rails sits near 0 V when both are up and about +7.5 V when -15 V is gone, which
    turns a BSS138W on and pulls the node low.
    """
    sh.note(
        '-15 V GUARD: an unpowered LT3097 cannot pull PGN low. Midpoint near 0 V with '
        'both rails up, about +7.5 V with -15 V missing.',
        (column - 10) * 1.27,
        (row - 10) * 1.27,
        1.8,
    )
    rail_symbol(sh, '+15V', (column, row))
    wire(sh, (column, row + 12), (column, row + 14), (column - 4, row + 14))
    rail_symbol(sh, '-15V', (column - 4, row + 14))
    with rev3_refs('R', 'Q'):
        vres(sh, '470k', column, row)
        vres(sh, '470k', column, row + 6)
        fet = nfet(sh, 'BSS138W', '', '', pose=at(column + 14, row + 6), fp=SOT323)
    gate, drain = pin_cell(fet, '1'), pin_cell(fet, '3')
    wire(sh, (column, row + 6), gate)
    ground(sh, spur(sh, fet, '2', 2))
    wire(sh, drain, (drain[0], drain[1] - 4), (drain[0] + 4, drain[1] - 4))
    net_label(sh, 'PGN_15V', (drain[0] + 4, drain[1] - 4), 0, is_global=True)


def power_good_node(
    sh, label, column, row, rail='+15V', values=('220k', '62k')
):
    """rail -> upper resistor -> node -> lower resistor -> ground; the node
    carries the label.
    """
    rail_symbol(sh, rail, (column, row))
    with high_refs('R'):
        vres(sh, values[0], column, row, fp=R0402)
        vres(sh, values[1], column, row + 6, fp=R0402)
    drop_ground(sh, (column, row + 12), 0)
    wire(sh, (column, row + 6), (column + 4, row + 6))
    net_label(sh, label, (column + 4, row + 6), 0, is_global=True)


def power_good_and(sh, column, row):
    """BAT54AW (two Schottky diodes, common anode on PG_15V, cathodes on
    PGP_15V / PGN_15V) with a 470k pull-up to +3V3: PG_15V is high only while
    both nodes are. A stiffer pull-up lifts the dead nodes through their 62k
    dividers and turns the BSS138s on with no rail present.
    """
    with high_refs('D'):
        pair = sh.add(
            'Diode:BAT54AW',
            next_ref('D'),
            'BAT54AW',
            column * 1.27,
            row * 1.27,
            auto=False,
            footprint=SOT323,
        )
    k1, k2, anode = (pin_cell(pair, number) for number in ('1', '2', '3'))
    wire(sh, k1, (k1[0] - 4, k1[1]))
    net_label(sh, 'PGP_15V', (k1[0] - 4, k1[1]), 180, is_global=True)
    wire(sh, k2, (k2[0] + 4, k2[1]))
    net_label(sh, 'PGN_15V', (k2[0] + 4, k2[1]), 0, is_global=True)
    node = (anode[0], anode[1] + 2)
    wire(sh, anode, node)
    wire(sh, node, (node[0] + 12, node[1]))
    net_label(sh, 'PG_15V', (node[0] + 12, node[1]), 0, is_global=True)
    # pull-up hangs below the output wire; +3V3 steps sideways to stay upright
    with high_refs('R'):
        vres(sh, '470k', node[0] + 5, node[1], fp=R0402)
    wire(sh, (node[0] + 5, node[1] + 6), (node[0] + 9, node[1] + 6))
    rail_symbol(sh, '+3V3', (node[0] + 9, node[1] + 6))


def power_good_flag(sh, column, row):
    """PG_15V gates a BSS138W whose drain, pulled up to +3V3 and through 1k,
    reads as PG_15V_N (low = both rails good) on the ESP32.
    """
    with high_refs('Q'):
        fet = nfet(sh, 'BSS138', '', '', pose=at(column, row), fp=SOT323)
    gate, drain = pin_cell(fet, '1'), pin_cell(fet, '3')
    wire(sh, gate, (gate[0] - 4, gate[1]))
    net_label(sh, 'PG_15V', (gate[0] - 4, gate[1]), 180, is_global=True)
    spur(sh, fet, '2', 2)
    ground(
        sh,
        (pin_cell(fet, '2')[0], pin_cell(fet, '2')[1] + 2),
    )
    node = (drain[0], drain[1] - 4)
    wire(sh, drain, node)
    # +3V3 -> 10k pull-up -> node
    wire(sh, node, (node[0] - 10, node[1]))
    pull_x = node[0] - 10
    with high_refs('R'):
        vres(sh, '10k', pull_x, node[1] - 6, fp=R0402)
    rail_symbol(sh, '+3V3', (pull_x, node[1] - 6))
    # node -> 1k -> PG_15V_N (ESP32 GPIO43)
    wire(sh, node, (node[0] + 4, node[1]))
    with high_refs('R'):
        hres(sh, '1k', node[0] + 7, node[1], fp=R0402)
    wire(sh, (node[0] + 10, node[1]), (node[0] + 14, node[1]))
    net_label(sh, 'PG_15V_N', (node[0] + 14, node[1]), 0, is_global=True)


def power_good_led(sh, node_net, text, column, row):
    """A good node turns a BSS138W on and its drain lights the green die. A second
    BSS138W, gated by that drain (100k to +3V3), lights the red die when the node
    is low. Green 2.2k from +5V, red 1.5k from +3V3, about 1 mA each.
    """
    stem = node_net.split('_')[0]
    with high_refs('Q'):
        good = nfet(sh, 'BSS138', '', '', pose=at(column, row), fp=SOT323)
    with extra_refs('Q'):
        bad = nfet(sh, 'BSS138', '', '', pose=at(column + 26, row), fp=SOT323)
    gate = pin_cell(good, '1')
    wire(sh, gate, (gate[0] - 4, gate[1]))
    net_label(sh, node_net, (gate[0] - 4, gate[1]), 180, is_global=True)
    for fet in (good, bad):
        spur(sh, fet, '2', 2)
        ground(sh, (pin_cell(fet, '2')[0], pin_cell(fet, '2')[1] + 2))
    green_k, red_k = f'{stem}_LED_GK', f'{stem}_LED_RK'
    drain = pin_cell(good, '3')
    node = (drain[0], drain[1] - 4)
    wire(sh, drain, node, (node[0] + 3, node[1]))
    net_label(sh, green_k, (node[0] + 3, node[1]), 0)
    with extra_refs('R'):
        vres(sh, '100k', node[0], node[1] - 6, fp=R0402)
    rail_symbol(sh, '+3V3', (node[0], node[1] - 6))
    gate = pin_cell(bad, '1')
    wire(sh, gate, (gate[0] - 2, gate[1]))
    net_label(sh, green_k, (gate[0] - 2, gate[1]), 180)
    drain = pin_cell(bad, '3')
    wire(sh, drain, (drain[0], drain[1] - 4))
    net_label(sh, red_k, (drain[0], drain[1] - 4), 0)
    top = row - 26
    for offset, rail, ohms, die in ((0, '+5V', '2.2k', 'GA'), (4, '+3V3', '1.5k', 'RA')):
        cell_row = top + offset
        rail_symbol(sh, rail, (column - 6, cell_row))
        wire(sh, (column - 6, cell_row), (column - 3, cell_row))
        with high_refs('R') if die == 'GA' else extra_refs('R'):
            hres(sh, ohms, column, cell_row)
        wire(sh, (column + 3, cell_row), (column + 5, cell_row))
        net_label(sh, f'{stem}_LED_{die}', (column + 5, cell_row), 0)
    with high_refs('D'):
        rg_led(
            sh,
            text,
            column + 36,
            top + 4,
            {'1': f'{stem}_LED_GA', '2': green_k, '3': red_k, '4': f'{stem}_LED_RA'},
        )


def opamp_dual(sh, ref, column, row, unit):
    """One unit of the OPA2991 dual op amp, WSON-8 DSG (TI SBOS969): A is pins 1-3,
    B pins 5-7, and unit 3 holds V- (4), V+ (8) and the thermal pad (9)."""
    return sh.add(
        'cryocooler:OPA2991IDSG',
        ref,
        'OPA2991IDSGR',
        column * 1.27,
        row * 1.27,
        unit=unit,
        auto=False,
        footprint='cryocooler:TI_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm',
    )


def build_signal_gen(sh):
    """Hand-laid: clock + AD9837 + gain stage + VREF clamp + AD5453 MDAC + output
    stage across the top, decoupling below. U5 (OPA2991 dual) is both op amps.
    """
    sh.handwired = True
    sh.note(
        'AD9837 (16 MHz clock) 60 Hz sine -> U5A gain stage -> AD5453 VREF. The 14-bit MDAC sets '
        'the amplitude: VOUT = -VREF x code / 16384. U5B is its output stage. Zero '
        'scale at power-on.',
        20,
        15,
    )
    sh.note(
        'VREF and RFB are limited to +/-12 V but the op-amps run from +/-14.7 V, so R50 '
        'and a 9.1 V bidirectional clamp protect VREF (under 10.5 V; 56 mW in R50). '
        'About 10 Vpp at full code; ZE500.1 RCA input range 0.2-6 V.',
        20,
        21,
    )
    # clock oscillator: tri-state pin tied to VDD, bypass cap, output into MCLK
    osc = place_ic(
        sh,
        'cryocooler:ECS-2520MV',
        'ECS-2520MV-160-BN-TR',
        22,
        66,
        'Oscillator:Oscillator_SMD_ECS_2520MV-xxx-xx-4Pin_2.5x2.0mm',
    )
    oe, vcc_osc = pin_cell(osc, '1'), pin_cell(osc, '4')
    wire(sh, oe, (oe[0], 56))
    wire(sh, vcc_osc, (vcc_osc[0], 56))
    wire(sh, (oe[0], 56), (vcc_osc[0], 56))
    rail_symbol(sh, '+3V3_SG', (vcc_osc[0], 56))
    drop_ground(sh, pin_cell(osc, '2'), 2)
    # AD9837: the AD9833's pins and registers in a 3 x 3 mm LFCSP, 16 MHz max MCLK
    dds = place_ic(
        sh,
        'cryocooler:AD9837BCPZ',
        'AD9837BCPZ',
        60,
        60,
        'Package_CSP:LFCSP-WD-10-1EP_3x3mm_P0.5mm_EP1.64x2.38mm',
    )
    wire(sh, pin_cell(osc, '3'), pin_cell(dds, '5'))
    for pin, net in (
        ('6', 'SPI_MOSI'),
        ('7', 'SPI_SCK'),
        ('8', 'AD9833_FSYNC'),
    ):
        net_label(sh, net, spur(sh, dds, pin, 2), 180, is_global=True)
    for pin in ('4', '9', '11'):  # DGND, AGND, exposed pad
        spur(sh, dds, pin, 2)
    wire(sh, (58, 72), (62, 72))
    drop_ground(sh, (60, 72), 2)
    vdd = pin_cell(dds, '2')
    wire(sh, vdd, (vdd[0], 48), (75, 48))
    rail_symbol(sh, '+3V3_SG', (vdd[0], 48))
    comp = pin_cell(dds, '1')
    wire(sh, comp, (75, comp[1]), (75, 54))
    vcap(sh, '10nF', 75, 48)
    cap_pin = pin_cell(dds, '3')
    wire(sh, cap_pin, (cap_pin[0], 39), (52, 39))
    vcap(sh, '100nF', 52, 39)
    drop_ground(sh, (52, 45), 0)
    rail_flag(sh, (cap_pin[0], 48))
    # AC coupling into the buffer; the raw DDS output is named for its
    # debug test point
    wire(sh, pin_cell(dds, '10'), (74, 62))
    wire(sh, (74, 62), (74, 67))
    net_label(sh, 'DDS_SINE', (74, 67), 270, is_global=True)
    hcap(sh, '1uF', 77, 62)
    opa_a = opamp_dual(sh, next_ref('U'), 110, 60, 1)
    positive_a = pin_cell(opa_a, '3')
    wire(sh, (80, 62), (92, 62), (92, positive_a[1]), positive_a)
    vres(sh, '100k', 86, 62)
    drop_ground(sh, (86, 68), 0)
    # U5A: non-inverting gain of 16.3 (1 + 50.6k/3.3k) sets about 10 Vpp at
    # full code through R50 and the 9k VREF input. The feedback is two series
    # resistors; the 3.6k sits on a 1206 / 3313J land, so a 5k trimmer can replace
    # it (gain 15.2-16.8). 1 nF across both rolls off above ~3 kHz.
    wire(sh, pin_cell(opa_a, '2'), (100, 62), (100, 76))
    hres(sh, '47k', 105, 76)
    with kicadgen.pinned_refs('R', 169):
        hres(sh, '3.6k', 111, 76, fp=R_TRIM)
    with high_refs('C'):
        hcap(sh, '1nF/C0G', 108, 80)
    wire(sh, (102, 76), (102, 80), (105, 80))
    wire(sh, (114, 76), (114, 80), (111, 80))
    wire(sh, (102, 76), (100, 76))
    vres(sh, '3.3k', 100, 76)
    drop_ground(sh, (100, 82), 0)
    wire(sh, pin_cell(opa_a, '1'), (120, 60), (120, 76), (114, 76))
    wire(sh, (120, 60), (122, 60), (124, 60))
    hres(sh, '220', 127, 60)
    if keeps_test_point('U5_OUT'):
        wire(sh, (122, 60), (122, 56))
        with kicadgen.pinned_refs('TP', 46):
            test_point(sh, 'U5_OUT', (122, 56), rot=0)
    # U5 supply unit: V+ to +15V, V- and the thermal pad (datasheet: to V-) to -15V
    power = opamp_dual(sh, opa_a.ref, 160, 86, 3)
    top, bottom, pad = pin_cell(power, '8'), pin_cell(power, '4'), pin_cell(power, '9')
    wire(sh, top, (top[0], top[1] - 4))
    rail_symbol(sh, '+15V', (top[0], top[1] - 4))
    wire(sh, bottom, (bottom[0], bottom[1] + 4), (bottom[0] + 4, bottom[1] + 4))
    rail_symbol(sh, '-15V', (bottom[0] + 4, bottom[1] + 4))
    wire(sh, pad, (pad[0] + 6, pad[1]))
    rail_symbol(sh, '-15V', (pad[0] + 6, pad[1]))
    # AD5453 VREF: series resistor, then the bidirectional clamp to ground
    with rev3_refs('D'):
        clamp = place_ic(
            sh,
            'cryocooler:MMBZ9V1ALT1G',
            'MMBZ9V1ALT1G',
            142,
            70,
            SOT23,
            ref_prefix='D',
        )
    sh.nc(clamp, '3')
    ground(sh, pin_cell(clamp, '2'))
    mdac = place_ic(
        sh,
        'cryocooler:AD5453WBCPZ',
        'AD5453WBCPZ-RL',
        190,
        64,
        'Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm',
    )
    kicadgen.retire_refs('U', 2)  # U7 (MCP4921) and U8 (LM4040)
    vref = pin_cell(mdac, '7')
    wire(sh, (130, vref[1]), (pin_cell(clamp, '1')[0], vref[1]), vref)
    wire(sh, (pin_cell(clamp, '1')[0], vref[1]), pin_cell(clamp, '1'))
    for pin, net in (('5', 'AD5453_SYNC'), ('3', 'SPI_SCK'), ('4', 'SPI_MOSI')):
        net_label(sh, net, spur(sh, mdac, pin, 5), 180, is_global=True)
    supply = pin_cell(mdac, '6')
    wire(sh, supply, (supply[0], supply[1] - 6))
    rail_symbol(sh, '+3V3_SG', (supply[0], supply[1] - 6))
    gnd_bus(sh, [pin_cell(mdac, '2'), pin_cell(mdac, '9')])
    # output stage (U5B): IOUT1 into the inverting input, RFB back from the output,
    # C1 from IOUT1 to the output for stability, non-inverting input grounded. C1 is
    # 22 pF: with 9k RFB, up to ~38 pF on IOUT1 and 4.5 MHz GBW, 2 pF peaks 6-8 dB
    # (ngspice, two-pole model); 22 pF is flat and its 800 kHz pole is far above 60 Hz
    kicadgen.retire_refs('U', 1)  # U9 (OPA188) merged into U5
    output_stage = opamp_dual(sh, opa_a.ref, 224, 58, 2)
    iout, rfb = pin_cell(mdac, '1'), pin_cell(mdac, '8')
    inverting = pin_cell(output_stage, '6')
    wire(sh, iout, (206, iout[1]), inverting)
    with rev3_refs('C'):
        vcap(sh, '22pF/C0G', 206, iout[1])
    ground(sh, spur(sh, output_stage, '5', 2))
    out = pin_cell(output_stage, '7')
    feedback_x = out[0] + 4
    # RFB to the output through a 0 ohm on a 1206 / 3313J land: a 1k trimmer there
    # adds up to ~11 % DAC gain. C1 goes to the output side of it (Figure 44, R2/C1).
    wire(sh, rfb, (204, rfb[1]), (204, 80))
    trim_x = (204 + feedback_x) // 2
    wire(sh, (204, 80), (trim_x - 3, 80))
    with kicadgen.pinned_refs('R', 299):  # R300, mapped to R96 in ref_map.py
        hres(sh, '0', trim_x, 80, fp=R_TRIM)
    wire(sh, (trim_x + 3, 80), (feedback_x, 80), (feedback_x, 72))
    wire(sh, (206, iout[1] + 6), (206, 72), (feedback_x, 72))
    wire(sh, (feedback_x, 72), (feedback_x, out[1]))
    resistor_x = feedback_x + 8
    wire(sh, out, (feedback_x, out[1]), (resistor_x - 3, out[1]))
    hres(sh, '100', resistor_x, out[1])
    wire(sh, (resistor_x + 3, out[1]), (resistor_x + 7, out[1]))
    hcap(sh, '10uF', resistor_x + 10, out[1])
    wire(
        sh,
        (resistor_x + 13, out[1]),
        (resistor_x + 17, out[1]),
        (resistor_x + 23, out[1]),
    )
    net_label(sh, 'SIG_SINE', (resistor_x + 23, out[1]), 0, is_global=True)
    vres(sh, '100k', resistor_x + 17, out[1])
    drop_ground(sh, (resistor_x + 17, out[1] + 6), 0)
    kicadgen.retire_refs('R', 3)  # R58, R59 and R3 went with the amplitude DAC
    kicadgen.retire_refs('C', 1)  # C9 likewise
    place_blocks(
        sh,
        [
            ('ECS-2520MV DECOUPLING CAPACITORS', '+3V3_SG', ('100nF',)),
            ('AD9837 DECOUPLING CAPACITORS', '+3V3_SG', ('100nF', '10uF')),
            ('OPA2991 +15V DECOUPLING CAPACITORS', '+15V', ('100nF',)),
            ('OPA2991 -15V DECOUPLING CAPACITORS', '-15V', ('100nF',)),
            2,  # the AD633 capacitors
            ('AD5453 DECOUPLING CAPACITORS', '+3V3_SG', ('100nF', '10uF')),
            2,  # the OPA188's pair (U9 merged into U5)
        ],
        20,
        110,
        max_column=300,
    )


def rem_switch(
    sh,
    enable_net,
    bus_net,
    terminal,
    flyback=False,
    footprint=None,
    rail='+12V',
    interlock_net=None,
):
    """GPIO -> N-FET level shifter -> P-FET high-side +12 V switch -> output
    terminal with a red/green state LED; drawn left to right from row 60.
    flyback adds a diode across the output for inductive loads; interlock_net
    adds a second N-FET in series with the level shifter's source, so the
    output stays off unless that net is high.
    """
    net_label(sh, enable_net, (24, 60), 180, is_global=True)
    wire(sh, (24, 60), (28, 60))
    hres(sh, '1k', 31, 60)
    wire(sh, (34, 60), (46, 60))
    vres(sh, '100k', 40, 60)
    drop_ground(sh, (40, 66), 0)
    q_n = nfet(sh, 'BSS138', '', '', pose=at(50, 60))
    if interlock_net:
        # series interlock FET (Q9) below the level shifter: its drain takes
        # the level shifter's source, its gate the power-good net
        with high_refs('Q'):
            q_il = nfet(sh, 'BSS138', '', '', pose=at(50, 72))
        wire(sh, pin_cell(q_n, '2'), pin_cell(q_il, '3'))
        gate = pin_cell(q_il, '1')
        wire(sh, gate, (gate[0] - 4, gate[1]))
        net_label(sh, interlock_net, (gate[0] - 4, gate[1]), 180, is_global=True)
        spur(sh, q_il, '2', 2)
        ground(sh, pin_cell(q_il, '2')[0:1] + (pin_cell(q_il, '2')[1] + 2,))
    else:
        spur(sh, q_n, '2', 2)
        ground(sh, pin_cell(q_n, '2')[0:1] + (pin_cell(q_n, '2')[1] + 2,))
    wire(sh, pin_cell(q_n, '3'), (52, 50), (76, 50))
    vres(sh, '100k', 62, 44)
    rail_symbol(sh, rail, (62, 44))
    q_p = sh.add(
        'Transistor_FET:BSS84',
        next_ref('Q'),
        'BSS84',
        80 * 1.27,
        50 * 1.27,
        rot=180,
        mirror=True,
        auto=False,
        footprint=SOT23,
    )
    top, bottom = pin_cell(q_p, '2'), pin_cell(q_p, '3')
    wire(sh, top, (top[0], top[1] - 4))
    rail_symbol(sh, rail, (top[0], top[1] - 4))
    # AMP_REM bus: drain, pull-down, LED branch and the REM terminal
    wire(sh, bottom, (bottom[0], 58), (136, 58))
    net_label(sh, bus_net, (104, 58), 0)
    vres(sh, '4.7k', 90, 58)
    drop_ground(sh, (90, 64), 0)
    # state LED dies anti-parallel between +5V/2.2k and the bus: green when the
    # bus is at +12 V, red (through the 4.7k pull-down) when it is off
    vres(sh, '2.2k', 96, 40)
    rail_symbol(sh, '+5V', (96, 40))
    wire(sh, (96, 46), (96, 48))
    net_label(sh, f'{bus_net}_LED', (96, 48), 0)
    rg_led(
        sh,
        f'{bus_net} G=on R=off',
        134,
        48,
        {'1': bus_net, '3': bus_net, '2': f'{bus_net}_LED', '4': f'{bus_net}_LED'},
    )
    j_rem = conn(
        sh,
        'Connector:Screw_Terminal_01x02',
        terminal,
        140 * 1.27,
        58 * 1.27,
        {},
        footprint or TERM_SIGNAL,
    )
    spur(sh, j_rem, '2', 2)
    ground(sh, (pin_cell(j_rem, '2')[0] - 2, pin_cell(j_rem, '2')[1]))
    if flyback:
        diode_part = sh.add(
            'Device:D',
            next_ref('D'),
            '1N4148W',
            120 * 1.27,
            61 * 1.27,
            rot=270,
            auto=False,
            footprint='Diode_SMD:D_SOD-123',
        )
        # cathode lands on the output bus wire, anode goes to ground
        ground(sh, pin_cell(diode_part, '2'))
        return j_rem, diode_part
    return j_rem, None


def build_amp_control(sh):
    """Hand-laid, left to right: GPIO -> N-FET level shifter -> P-FET high-side
    switch -> REM terminal and LED.
    """
    sh.handwired = True
    sh.note(
        'GPIO6 high -> +12 V on the amplifier REM terminal (P-FET high-side '
        'switch), but only while PG_15V is high (both +-15 V rails good: Q9 '
        'in series with the level shifter). LED: green = on, red = off.',
        20,
        15,
    )
    sh.note(
        'Amplifier: AUDIOZERONE ZE500.1 (external): REM terminal + RCA/line '
        'input. Its power leads do not pass through this board.',
        20,
        21,
    )
    rem_switch(
        sh,
        'AMP_REM_EN',
        'AMP_REM',
        'AMP REM / GND',
        rail='+12V',
        interlock_net='PG_15V',
        footprint=TERM_SIGNAL,
    )
    # Same Sky MJ-3523-SMT-TR: tip = signal, sleeve = GND, tip switch unused
    j_sig = conn(
        sh,
        'cryocooler:MJ-3523-SMT-TR',
        'AMP SIGNAL IN / GND',
        140 * 1.27,
        90 * 1.27,
        {'10': None},
        SIGNAL_JACK,
    )
    sig = pin_cell(j_sig, '2')
    wire(sh, sig, (sig[0] - 6, sig[1]))
    net_label(sh, 'SIG_SINE', (sig[0] - 6, sig[1]), 180, is_global=True)
    spur(sh, j_sig, '1', 2)
    ground(sh, (pin_cell(j_sig, '1')[0] - 2, pin_cell(j_sig, '1')[1]))


def build_compressor_relay(sh):
    """Hand-laid like amp_control: GPIO16 high -> +12 V on the compressor
    relay terminal (P-FET high-side switch, flyback diode for a relay coil).
    """
    sh.handwired = True
    sh.note(
        'COMP_RELAY_EN (GPIO16) high -> +12 V on the compressor relay '
        'terminal (BSS84 high-side switch, 130 mA max: drive an external '
        'relay or SSR coil). Flyback diode across the output. LED: green = '
        'on, red = off.',
        20,
        15,
    )
    rem_switch(
        sh,
        'COMP_RELAY_EN',
        'COMP_RELAY',
        'COMPRESSOR RELAY / GND',
        True,
        RIGHT_ANGLE_2P,
        '+12V',
    )


def build_amp_current(sh):
    """Hand-laid: isolator with its integrated supply on the left, ACS37800 and
    divider to the right.
    """
    sh.handwired = True
    sh.note(
        'Amplifier output V/I monitor: ACS37800 (SPI) on an isolated 5 V domain from '
        'the ISOW7741 (110 mA max at 5 V to 5 V; VSEL on VISOOUT selects 5 V). Beads '
        'on VISOOUT-VISOIN and GND2-GISOIN follow the ISOW774x datasheet for emissions.',
        20,
        15,
    )
    sh.note(
        'Mains-class creepage/clearance applies between ISO_GND domain and '
        'the logic side on the PCB. EN/FLT is an open-drain fault flag as well as '
        'the enable, so it has a pull-up rather than a tie to VIO.',
        20,
        21,
    )
    iso = place_ic(
        sh,
        'cryocooler:ISOW7741DFMR',
        'ISOW7741DFMR',
        60,
        58,
        'cryocooler:TI_DFM0020A',
    )
    for pin, net in (
        ('2', 'ACS_MOSI'),
        ('3', 'ACS_SCK'),
        ('4', 'ACS_CS'),
        ('5', 'ACS_MISO'),
    ):
        net_label(sh, net, spur(sh, iso, pin, 3), 180, is_global=True)
    # logic-side enables: EN/FLT through 10k, EN_IO1 tied to +3V3
    enable = pin_cell(iso, '8')
    wire(sh, enable, (40, enable[1]))
    # the removed logic pull-ups, DC-DC module, its capacitors and enable resistor
    kicadgen.retire_refs('R', 3)
    kicadgen.retire_refs('PS', 1)
    kicadgen.retire_refs('C', 2)
    kicadgen.retire_refs('R', 1)
    kicadgen.retire_refs('C', 2)
    with rev3_refs('R'):
        hres(sh, '10k', 37, enable[1])
    rail_symbol(sh, '+3V3', (34, enable[1]))
    channel_enable = pin_cell(iso, '7')
    wire(sh, channel_enable, (28, channel_enable[1]), (28, channel_enable[1] - 6))
    rail_symbol(sh, '+3V3', (28, channel_enable[1] - 6))
    # logic and supply inputs
    vio, vdd = pin_cell(iso, '1'), pin_cell(iso, '9')
    wire(sh, vio, (vio[0], 44))
    rail_symbol(sh, '+3V3', (vio[0], 44))
    wire(sh, vdd, (vdd[0], 40))
    rail_symbol(sh, '+5V_ISO', (vdd[0], 40))
    gnd_bus(sh, [pin_cell(iso, '6'), pin_cell(iso, '10')])
    # isolated output: VSEL on VISOOUT sets 5 V, a bead feeds VISOIN, EN_IO2 and
    # the ACS37800
    iso_out, iso_in = pin_cell(iso, '12'), pin_cell(iso, '20')
    wire(sh, iso_out, (iso_out[0], 40), (66, 40), (72, 40), (82, 40))
    rail_symbol(sh, 'VISOOUT', (72, 40))
    voltage_select = pin_cell(iso, '13')
    wire(sh, voltage_select, (82, voltage_select[1]), (82, 40))
    with rev3_refs('FB'):
        aux(
            sh,
            'Device:FerriteBead',
            'FB',
            'BLM15EX331SN1D',
            {},
            pose=at(66, 43),
            fp=BEAD_0402,
        )
    wire(sh, iso_in, (66, 46))
    side_two_enable = pin_cell(iso, '14')
    wire(
        sh,
        side_two_enable,
        (78, side_two_enable[1]),
        (78, 46),
        (70, 46),
        (66, 46),
    )
    rail_symbol(sh, 'ISO_5V', (70, 46))
    # isolated grounds, joined through the second bead
    iso_return, side_two_ground = pin_cell(iso, '15'), pin_cell(iso, '11')
    wire(sh, iso_return, (iso_return[0], 74), (72, 74))
    rail_symbol(sh, 'ISO_GND', (iso_return[0], 74))
    with rev3_refs('FB'):
        aux(
            sh,
            'Device:FerriteBead',
            'FB',
            'BLM15EX331SN1D',
            {},
            pose=at(75, 74, 90),
            fp=BEAD_0402,
        )
    wire(sh, side_two_ground, (side_two_ground[0], 70), (80, 70), (80, 74))
    wire(sh, (78, 74), (80, 74))
    rail_symbol(sh, 'ISO_GND2', (80, 74))
    # the isolated rails have no power output pin of their own on these two nets
    wire(sh, (24, 100), (30, 100))
    rail_symbol(sh, 'ISO_5V', (24, 100))
    rail_flag(sh, (30, 100))
    wire(sh, (24, 112), (30, 112))
    rail_symbol(sh, 'ISO_GND', (24, 112))
    rail_flag(sh, (30, 112))
    wire(sh, (50, 112), (56, 112))
    rail_symbol(sh, 'ISO_GND2', (50, 112))
    rail_flag(sh, (56, 112))
    # ACS37800
    acs = place_ic(
        sh,
        'cryocooler:ACS37800KMACTR-015B5-SPI',
        'ACS37800KMACTR-015B5-SPI',
        110,
        62,
        'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
        mirror=True,
    )
    # isolated SPI: the ACS37800 pins are ordered like the ISOW7741 outputs
    # (MOSI, SCK, CS, MISO) so each signal is a straight wire across
    for iso_pin, acs_pin in (
        ('19', '10'),
        ('18', '11'),
        ('17', '9'),
        ('16', '12'),
    ):
        wire(sh, pin_cell(iso, iso_pin), pin_cell(acs, acs_pin))
    gnd = pin_cell(acs, '14')
    wire(sh, gnd, (gnd[0], gnd[1] + 2), (gnd[0] - 4, gnd[1] + 2))
    rail_symbol(sh, 'ISO_GND', (gnd[0] - 4, gnd[1] + 2))
    vcc = pin_cell(acs, '13')
    wire(sh, vcc, (vcc[0], vcc[1] - 4), (vcc[0] + 4, vcc[1] - 4))
    rail_symbol(sh, 'ISO_5V', (vcc[0] + 4, vcc[1] - 4))
    vinn = spur(sh, acs, '15', 2)
    rail_symbol(sh, 'ISO_GND', vinn)
    vinp = pin_cell(acs, '16')
    wire(sh, vinp, (124, vinp[1]), (124, 38), (150, 38))
    wire(sh, (124, 46), (130, 46))
    vres(sh, '4.02k', 130, 46, fp=R0603)
    rail_symbol(sh, 'ISO_GND', (130, 52))
    # four 1M divider resistors from the load side up to VSENSE
    ip_minus, ip_plus = pin_cell(acs, '5'), pin_cell(acs, '1')
    wire(sh, ip_minus, (159, ip_minus[1]), (159, 58), (174, 58))
    for index in range(4):
        vres(sh, '1M', 150, 38 + index * 6, fp=R1206)
    # the amplifier output is 2-way; the cryocooler plug is 3-way, its pin 3
    # (protective ground) tied to board GND
    j_out = conn(
        sh,
        'Connector:Screw_Terminal_01x02',
        'AMP OUT (+ / -)',
        170 * 1.27,
        72 * 1.27,
        {},
        TERM_POWER,
    )
    j_load = conn(
        sh,
        'Connector:Screw_Terminal_01x03',
        'CRYOCOOLER (+ / - / GND)',
        178 * 1.27,
        60 * 1.27,
        {},
        TERM_POWER3,
    )
    out_plus = pin_cell(j_out, '1')
    wire(sh, ip_plus, (159, ip_plus[1]), (159, out_plus[1]), out_plus)
    drop_ground(sh, pin_cell(j_load, '3'), 1)
    # J12's longer spur keeps ISO_GND and its name clear of the GND symbol on pin 3
    for connector, length in ((j_out, 2), (j_load, 7)):
        rail_symbol(sh, 'ISO_GND', spur(sh, connector, '2', length))
    with rev3_refs('C'):
        place_blocks(
            sh,
            [
                ('ISOW7741 VIO DECOUPLING', '+3V3', ('1uF', '10nF')),
                ('ISOW7741 VDD DECOUPLING', '+5V_ISO', ('22uF/10V', '1uF', '10nF')),
                (
                    'ISOW7741 VISOOUT DECOUPLING',
                    'VISOOUT',
                    ('22uF/10V', '1uF', '10nF'),
                    'ISO_GND2',
                ),
                ('ISOW7741 VISOIN DECOUPLING', 'ISO_5V', ('1uF', '10nF'), 'ISO_GND'),
            ],
            20,
            130,
            max_column=300,
        )
    place_blocks(
        sh,
        [
            2,  # the ISO7741 capacitors
            (
                'ACS37800 DECOUPLING CAPACITORS',
                'ISO_5V',
                ('1uF', '100nF'),
                'ISO_GND',
            ),
        ],
        20,
        154,
        max_column=300,
    )


def build_system_current(sh):
    """Hand-laid: 15 mOhm shunt between VSW and +12V with kelvin sense lines
    through the 49.9 ohm / 470 nF input filter into the INA239 (SPI).
    """
    sh.handwired = True
    sh.note(
        'INA239 monitors the switched 12 V rail: 15 mOhm shunt, SPI mode 1 '
        'on the main bus (CS from the decoder), +/-163.84 mV range (~10.9 A). ALERT '
        'drives its LED and MCP23S08 GP6.',
        20,
        15,
    )
    ina = place_ic(
        sh,
        'cryocooler:INA239AIDGSR',
        'INA239AIDGSR',
        110,
        62,
        'Package_SO:TSSOP-10_3x3mm_P0.5mm',
    )
    vbus, in_minus, in_plus = (pin_cell(ina, pin) for pin in ('8', '9', '10'))
    tip_x, row = vbus
    # shunt: VSW (IN+ side) on the left, +12V (IN- and VBUS side) on the right
    shunt_row = row - 22
    shunt_x = tip_x - 40
    left, right = shunt_x - 3, shunt_x + 3
    hres(sh, '15m', shunt_x, shunt_row, fp=R2512)
    wire(sh, (left, shunt_row), (left - 6, shunt_row))
    rail_symbol(sh, 'VSW', (left - 6, shunt_row))
    # +12V rail to the right with its bulk and bypass caps
    wire(
        sh,
        (right, shunt_row),
        (right + 8, shunt_row),
        (right + 16, shunt_row),
        (right + 22, shunt_row),
    )
    rail_symbol(sh, '+12V', (right + 22, shunt_row))
    rail_flag(sh, (right + 4, shunt_row))
    vcap(sh, '100nF', right + 8, shunt_row, fp=C0805)
    drop_ground(sh, (right + 8, shunt_row + 6), 0)
    cap_pol(
        sh, '100uF/25V', '', '', pose=at(right + 16, shunt_row + 3), fp=CP_ELEC
    )
    drop_ground(sh, (right + 16, shunt_row + 6), 0)
    # kelvin taps: IN- and IN+ through the filter; VBUS shares the filtered
    # IN- node (its 1 Mohm input draws ~12 uA, a 0.6 mV drop in 49.9 ohm)
    filter_x = right + 7
    cap_x = filter_x + 8
    jog_x = cap_x + (tip_x - cap_x) // 2
    wire(sh, (right, shunt_row), (right, row + 2))
    wire(sh, vbus, (tip_x - 3, row), (tip_x - 3, row + 2))
    wire(sh, (right, row + 2), (filter_x - 3, row + 2))
    hres(sh, '49.9', filter_x, row + 2)
    wire(sh, (filter_x + 3, row + 2), (cap_x, row + 2), in_minus)
    wire(sh, (left, shunt_row), (left, row + 8), (filter_x - 3, row + 8))
    hres(sh, '49.9', filter_x, row + 8)
    wire(
        sh,
        (filter_x + 3, row + 8),
        (cap_x, row + 8),
        (jog_x, row + 8),
        (jog_x, in_plus[1]),
        in_plus,
    )
    vcap(sh, '470nF', cap_x, row + 2, fp=C0805)
    # SPI: chip select with pull-up, bus labels, ALERT with LED
    for pin, net in (
        ('1', 'INA239_CS'),
        ('5', 'SPI_SCK'),
        ('2', 'SPI_MOSI'),
        ('4', 'SPI_MISO'),
    ):
        net_label(sh, net, spur(sh, ina, pin, 12), 0, is_global=True)
    # the decoder drives CS push-pull; R68 stays retired
    kicadgen.retire_refs('R', 1)
    alert = spur(sh, ina, '3', 4)
    wire(sh, alert, (alert[0] + 8, alert[1]))
    net_label(sh, 'INA239_ALERT', (alert[0] + 8, alert[1]), 0, is_global=True)
    pull = (alert[0], alert[1] + 6)
    wire(sh, alert, pull)
    hres(sh, '10k', pull[0] + 3, pull[1])
    rail_symbol(sh, '+3V3', (pull[0] + 6, pull[1]))
    # red die only: +3V3 -> 1.5k -> RA, RK on the open-drain ALERT
    row = pull[1] + 8
    rail_symbol(sh, '+3V3', (pull[0] - 2, row))
    wire(sh, (pull[0] - 2, row), (pull[0], row))
    hres(sh, '1.5k', pull[0] + 3, row)
    wire(sh, (pull[0] + 6, row), (pull[0] + 8, row))
    net_label(sh, 'ALERT_LED_A', (pull[0] + 8, row), 0)
    rg_led(
        sh,
        'ALERT (red)',
        pull[0] + 26,
        row + 2,
        {'1': None, '2': None, '4': 'ALERT_LED_A', '3': ('global', 'INA239_ALERT')},
    )
    # supply and ground
    vs = pin_cell(ina, '6')
    wire(sh, vs, (vs[0], vs[1] - 4))
    rail_symbol(sh, '+3V3', (vs[0], vs[1] - 4))
    drop_ground(sh, pin_cell(ina, '7'), 2)
    place_blocks(
        sh,
        [('INA239 DECOUPLING CAPACITORS', '+3V3', ('100nF', '1uF'))],
        120,
        100,
    )
    # numbers of the removed 3V3 power LED and its resistor (now the STATUS LED's
    # green die)
    kicadgen.retire_refs('R', 1)
    kicadgen.retire_refs('D', 1)


DEBUG_RAILS = (
    'VIN',
    '+12V',
    'VSW',
    '+5V',
    '+3V3',
    '+15V',
    '-15V',
    '+16V5',
    '-16V5',
    'ISO_5V',
)
DEBUG_GROUNDS = ('GND', 'GND', 'GND', 'ISO_GND')
# TP18-TP28 (SPI clock, MOSI, MISO and chip selects) were removed; later points keep
# their numbers. A None entry in a group retires one number the same way.
RETIRED_SPI_TEST_POINTS = 11
DEBUG_SIGNALS = (
    ('Fan, pump, interrupts and control', (
        'FAN_PWM',
        'PUMP_PWM',
        'PUMP_TACH',
        'FAN_TACH',
        'PWR_KILL',
        'COMP_RELAY_EN',
        'AMP_REM_EN',
        'PG_15V',
    )),
    ('Analog and sensors', (
        'DDS_SINE',
        'SIG_SINE',
        'NTC_ADC',
        'FLOW_TACH',
        None,  # TP41 (STATUS_RGB) removed for silk room
    )),
)
# (rail, resistor, LED description[, return net]): LEDs on rails that have no
# indicator yet; the isolated rail returns to ISO_GND, never to GND. None retires
# the numbers of a removed LED: the two power good LEDs already cover +-15 V.
DEBUG_RAIL_LEDS = (
    None,  # the 5V LED is the STATUS LED's green die now
    None,
    None,
    ('ISO_5V', '3.3k', 'ISO 5V (green)', 'ISO_GND'),
)


def debug_unit(sh, kind, net, column, row):
    """One test point on a net: a power symbol or global label on top of a
    short wire, the pad below it (ground units hang the symbol below).
    """
    if kind == 'ground':
        test_point(sh, net, (column, row), TP_LOOP)
        wire(sh, (column, row), (column, row + 3))
        rail_symbol(sh, net, (column, row + 3))
        return
    if kind == 'rail':
        rail_symbol(sh, net, (column, row))
    else:
        net_label(sh, net, (column, row), 180, is_global=True)
    wire(sh, (column, row), (column, row + 3))
    test_point(sh, net, (column, row + 3), rot=180)


def debug_rail_led(sh, net, ohms, label, column, row, ground='GND'):
    """Rail -> resistor -> green die -> ground, drawn left to right; the red die
    is unused.
    """
    rail_symbol(sh, net, (column, row))
    wire(sh, (column, row), (column + 3, row))
    hres(sh, ohms, column + 6, row)
    wire(sh, (column + 9, row), (column + 11, row))
    net_label(sh, f'{net}_LED_A', (column + 11, row), 0)
    indicator = rg_led(
        sh, label, column + 42, row + 4, {'1': f'{net}_LED_A', '3': None, '4': None}
    )
    green_k = spur(sh, indicator, '2', 2)
    wire(sh, green_k, (green_k[0] + 2, green_k[1]))
    rail_symbol(sh, ground, (green_k[0] + 2, green_k[1]))
    return indicator


def build_debug(sh):
    """Hand-laid: one test point per useful net (rails, grounds, fan
    and pump lines, control lines) and a power LED on each rail that has no
    indicator yet. Placement on the board follows the net's own pads.
    """
    sh.handwired = True
    sh.note(
        'Debug aids: test points (pad per net, loops for ground) and rail '
        'LEDs. Each test point sits on a global label or power symbol; the '
        'PCB generator places it beside a pad on the same net.',
        20,
        15,
    )
    column, row = 24, 36
    sh.note('POWER RAILS', 20 * 1.27, (row - 8) * 1.27, 1.8)
    for net in DEBUG_RAILS:
        if keeps_test_point(net):
            debug_unit(sh, 'rail', net, column, row)
        else:
            kicadgen.retire_refs('TP', 1)
        column += 22
    column = 24
    row += 22
    sh.note('GROUND (scope loops)', 20 * 1.27, (row - 8) * 1.27, 1.8)
    for index, net in enumerate(DEBUG_GROUNDS):
        # one GND loop stays for the scope ground clip
        if keeps_test_point(net) or (index == 0 and KEPT_TEST_POINTS is not None):
            debug_unit(sh, 'ground', net, column, row)
        else:
            kicadgen.retire_refs('TP', 1)
        column += 22
    kicadgen.retire_refs('TP', RETIRED_SPI_TEST_POINTS)
    for title, nets in DEBUG_SIGNALS:
        column = 36
        row += 24
        sh.note(title.upper(), 20 * 1.27, (row - 8) * 1.27, 1.8)
        for net in nets:
            if net is None or not keeps_test_point(net):
                kicadgen.retire_refs('TP', 1)
                continue
            debug_unit(sh, 'signal', net, column, row)
            column += 28
    column = 24
    row += 30
    sh.note('RAIL LEDS', 20 * 1.27, (row - 8) * 1.27, 1.8)
    for entry in DEBUG_RAIL_LEDS:
        if entry is None:
            kicadgen.retire_refs('R', 1)
            kicadgen.retire_refs('D', 1)
            continue
        net, ohms, label, *ground = entry
        debug_rail_led(sh, net, ohms, label, column, row, *ground)
        column += 50


def build_gpio_expander(sh):
    """Hand-laid: MCP23S08 SPI GPIO expander for the signals that have no ESP32
    pin of their own: power-good flags, backlight enable, INA239 alert and touch
    interrupt. Runs
    from +3V3, not a switched rail, so pulling a jumper does not take it down.
    """
    sh.handwired = True
    sh.note(
        'MCP23S08: SPI mode 0 slave on the main bus (CS from the decoder). SO releases '
        'within 100 ns of CS rising (datasheet Fig. 2-6, parameter 14), so it '
        'shares SPI_MISO without a buffer. A1/A0 low: opcodes 0x40 / 0x41.',
        20,
        15,
    )
    sh.note(
        'All pins power up as inputs. RESET, A1 and A0 must be biased (datasheet '
        'Table 1-1). Exposed pad to VSS, in addition to pin 17. GP2, GP3 and GP5 are '
        'spare; firmware enables weak pull-ups on them. TSC2046 PENIRQ drives GP7.',
        20,
        21,
    )
    expander = place_ic(
        sh,
        'cryocooler:MCP23S08',
        'MCP23S08-E/ML',
        80,
        70,
        'Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.7x2.7mm',
    )
    vdd = pin_cell(expander, '18')
    wire(sh, vdd, (vdd[0], vdd[1] - 6))
    rail_symbol(sh, '+3V3', (vdd[0], vdd[1] - 6))
    drop_ground(sh, pin_cell(expander, '17'), 2)
    drop_ground(sh, pin_cell(expander, '21'), 2)
    place_blocks(
        sh,
        [('MCP23S08 DECOUPLING CAPACITOR', '+3V3', ('100nF',))],
        150,
        100,
    )
    # the removed SC18IS604 and 74LVC1G125 capacitors keep their numbers free
    kicadgen.retire_refs('C', 2)
    for pin, net in (
        ('5', 'EXPANDER_CS'),
        ('19', 'SPI_SCK'),
        ('20', 'SPI_MOSI'),
    ):
        net_label(sh, net, spur(sh, expander, pin, 12), 180, is_global=True)
    # past the global labels above it, so the symbol clears their text
    rail_symbol(sh, '+3V3', spur(sh, expander, '4', 28))
    # A1 and A0 share one ground symbol
    address_low, address_high = spur(sh, expander, '3', 3), spur(sh, expander, '2', 3)
    wire(sh, address_low, address_high)
    ground(sh, address_high)
    net_label(sh, 'SPI_MISO', spur(sh, expander, '1', 6), 0, is_global=True)
    for pin, net in (
        ('9', 'PGP_15V'),
        ('10', 'PGN_15V'),
        ('13', 'DISP_BL_EN'),
        ('15', 'INA239_ALERT'),
        ('16', 'TOUCH_IRQ'),
    ):
        net_label(sh, net, spur(sh, expander, pin, 6), 0, is_global=True)
    for pin in ('11', '12', '14'):
        sh.nc(expander, pin)
    # past the global labels above it, so the two label texts do not touch
    if keeps_test_point('EXPANDER_INT'):
        int_end = spur(sh, expander, '7', 22)
        net_label(sh, 'EXPANDER_INT', int_end, 0)
        wire(sh, int_end, (int_end[0], int_end[1] + 4))
        test_point(sh, 'EXPANDER_INT', (int_end[0], int_end[1] + 4), rot=180)
    else:
        sh.nc(expander, '7')
        kicadgen.retire_refs('TP', 1)
    # the removed CS and RESET pull-ups, the bridge's other pull-ups and the
    # 74LVC1G125 keep their numbers free
    kicadgen.retire_refs('R', 5)
    kicadgen.retire_refs('U', 1)


def pullup(sh, value, cell):
    """Horizontal pull-up ending on a +3V3 symbol three cells left of `cell`'s
    wire end; returns nothing.
    """
    column, row = cell
    hres(sh, value, column - 3, row)
    wire(sh, (column - 6, row), (column - 6, row))
    rail_symbol(sh, '+3V3', (column - 6, row))


# Last reference numbers used on the board before the direct fan and pump
# drivers were added; the new parts take the numbers above them.
LAST_RESISTOR_BEFORE_FAN_DRIVERS, LAST_FET_BEFORE_FAN_DRIVERS = 171, 25


# SP3422 I/O pins, in symbol order IO1-IO4 (pin 2 is GND)
ESD_ARRAY_IO_PINS = ('1', '3', '4', '5')


def esd_array(sh, column, row):
    """SP3422-04UTG four-channel ESD clamp with its ground pin tied down; returns
    the part so callers can wire ESD_ARRAY_IO_PINS.
    """
    clamp = place_ic(
        sh,
        'cryocooler:SP3422-04UTG',
        'SP3422-04UTG',
        column,
        row,
        'cryocooler:Littelfuse_DFN-5_1.0x0.6mm_P0.35mm',
    )
    drop_ground(sh, pin_cell(clamp, '2'), 2)
    return clamp


def fan_channel(sh, title, pwm_net, tach_net, row, index):
    """One 4-pin fan channel, drawn left to right from `row`: GPIO -> BSS138
    open-drain PWM driver -> connector, and connector -> tach pull-up -> 4.7k ->
    GPIO, which limits a 12 V short on the connector to about 2 mA. The gate pull-up to +3V3 holds the PWM line low (0% drive) while the
    GPIO floats during boot and reset.
    """
    first_resistor = LAST_RESISTOR_BEFORE_FAN_DRIVERS + index * 3
    net_label(sh, pwm_net, (28, row), 180, is_global=True)
    with kicadgen.pinned_refs('R', first_resistor):
        vres(sh, '10k', 34, row - 6)
    rail_symbol(sh, '+3V3', (34, row - 6))
    wire(sh, (28, row), (38, row))
    with kicadgen.pinned_refs('R', first_resistor + 1):
        hres(sh, '1k', 41, row)
    wire(sh, (44, row), (46, row))
    with kicadgen.pinned_refs('Q', LAST_FET_BEFORE_FAN_DRIVERS + index):
        driver = nfet(sh, 'BSS138', '', '', pose=at(50, row))
    ground(sh, spur(sh, driver, '2', 2))
    connector = sh.add(
        'Connector_Generic:Conn_01x04',
        next_ref('J'),
        title,
        150 * 1.27,
        (row + 8) * 1.27,
        rot=180,
        mirror=True,
        auto=False,
        footprint=FAN4_RIGHT_ANGLE,
    )
    pwm_pin, tach_pin = pin_cell(connector, '4'), pin_cell(connector, '3')
    drain = pin_cell(driver, '3')
    wire(
        sh,
        drain,
        (drain[0], pwm_pin[1] - 10),
        (138, pwm_pin[1] - 10),
        (138, pwm_pin[1]),
        pwm_pin,
    )
    vres(sh, '10k', 100, pwm_pin[1] - 16)
    rail_symbol(sh, '+3V3_COOL', (100, pwm_pin[1] - 16))
    # the pull-up stays on the connector side so the 4.7k does not form a
    # divider with it when the open-collector tach output pulls low
    wire(sh, tach_pin, (120, tach_pin[1]))
    vres(sh, '4.7k', 126, tach_pin[1] - 6)
    rail_symbol(sh, '+3V3_COOL', (126, tach_pin[1] - 6))
    with kicadgen.pinned_refs('R', first_resistor + 2):
        hres(sh, '4.7k', 117, tach_pin[1])
    wire(sh, (114, tach_pin[1]), (70, tach_pin[1]))
    net_label(sh, tach_net, (70, tach_pin[1]), 180, is_global=True)
    plus = pin_cell(connector, '2')
    # jogs down so the +12V symbol stays clear of the tach wire above it
    jog = (plus[0] - 28, plus[1] + 5)
    wire(sh, plus, (plus[0] - 24, plus[1]), (plus[0] - 24, jog[1]), jog)
    rail_symbol(sh, '+12V', jog)
    vcap(sh, '22uF/25V', plus[0] - 18, plus[1], fp=C1210)
    drop_ground(sh, (plus[0] - 18, plus[1] + 6), 0)
    ground(sh, spur(sh, connector, '1', 2))


def build_cooling(sh):
    """Hand-laid: BSS138 PWM drivers on the left, fan and pump connectors on
    the right, flow sensor and NTC below.
    """
    sh.handwired = True
    sh.note(
        'Fan and pump: LEDC PWM at 25 kHz through a BSS138, because the PWM '
        'input can sit at 5.25 V (Intel 4-wire spec) and GPIOs are not 5 V '
        'tolerant. GPIO high = FET on = 0% drive; firmware inverts the duty.',
        20,
        15,
    )
    sh.note(
        'Tach: open collector, 2 pulses/rev, counted with PCNT. Alphacool ES: '
        'tach -> GPIO18, NTC -> GPIO4.',
        20,
        21,
    )
    # numbers of the removed EMC2303 and its straps, decoupling and alert LED
    kicadgen.retire_refs('U', 1)
    kicadgen.retire_refs('C', 2)
    kicadgen.retire_refs('R', 4)
    kicadgen.retire_refs('D', 1)
    fan_channel(sh, 'FAN (4-pin PWM)', 'FAN_PWM', 'FAN_TACH', 60, 0)
    fan_channel(sh, 'PUMP (4-pin PWM)', 'PUMP_PWM', 'PUMP_TACH', 86, 1)
    # Alphacool ES flow sensor and NTC
    # pin 1 at the bottom, like the fan and pump headers, so GND has room
    j_flow = sh.add(
        'Connector_Generic:Conn_01x03',
        next_ref('J'),
        'ALPHACOOL ES FLOW (3-pin)',
        110 * 1.27,
        124 * 1.27,
        rot=180,
        mirror=True,
        auto=False,
        footprint=WURTH3_RIGHT_ANGLE,
    )
    raw = pin_cell(j_flow, '3')
    wire(sh, raw, (raw[0] - 6, raw[1]))
    hres(sh, '4.7k', raw[0] - 9, raw[1])
    wire(sh, (raw[0] - 12, raw[1]), (raw[0] - 30, raw[1]))
    net_label(sh, 'FLOW_TACH', (raw[0] - 30, raw[1]), 180, is_global=True)
    vres(sh, '10k', raw[0] - 20, raw[1] - 6)
    rail_symbol(sh, '+3V3_COOL', (raw[0] - 20, raw[1] - 6))
    plus_pin, gnd_pin = pin_cell(j_flow, '2'), pin_cell(j_flow, '1')
    # jogs down so the +12V symbol stays clear of the tach wire above it
    plus_jog = (plus_pin[0] - 12, plus_pin[1] + 5)
    wire(sh, plus_pin, (plus_pin[0] - 8, plus_pin[1]), (plus_pin[0] - 8, plus_jog[1]), plus_jog)
    rail_symbol(sh, '+12V', plus_jog)
    ground(sh, spur(sh, j_flow, '1', 2))
    j_ntc = conn(
        sh,
        'Connector_Generic:Conn_01x02',
        'ALPHACOOL ES NTC 10k',
        110 * 1.27,
        150 * 1.27,
        {},
        RIGHT_ANGLE_2P,
    )
    ntc = pin_cell(j_ntc, '1')
    wire(sh, ntc, (ntc[0] - 30, ntc[1]))
    net_label(sh, 'NTC_ADC', (ntc[0] - 30, ntc[1]), 180, is_global=True)
    vres(sh, '10k', ntc[0] - 14, ntc[1] - 6)
    rail_symbol(sh, '+3V3_COOL', (ntc[0] - 14, ntc[1] - 6))
    vcap(sh, '100nF', ntc[0] - 22, ntc[1])
    drop_ground(sh, (ntc[0] - 22, ntc[1] + 6), 0)
    ground(sh, spur(sh, j_ntc, '2', 2))
    # ESD clamp on the GPIO side of the tach resistors: J3-J5 carry 12 V beside the
    # tach pin, and a 5 V clamp on the connector side would not survive that short
    sh.note('ESD CLAMP (GPIO SIDE)', 150 * 1.27, 112 * 1.27, 1.8)
    with rev3_refs('U'):
        clamp = esd_array(sh, 180, 128)
    for pin, net in zip(ESD_ARRAY_IO_PINS, ('FAN_TACH', 'PUMP_TACH', 'FLOW_TACH', 'NTC_ADC')):
        net_label(sh, net, spur(sh, clamp, pin, 3), 180, is_global=True)


def build_cold_head(sh):
    """Hand-laid: ADS1220 centre; RTD inputs fan out to the connector with
    nested jogs so nothing crosses.
    """
    sh.handwired = True
    sh.note(
        'PT1000 4-wire ratiometric: IDAC1 (AIN3) excites through 1k (1.5 V at 250 uA '
        'if the cable shorts), AIN1/AIN0 sense, Rref (3.9k) on REFP0/REFN0. SPI mode 1 '
        'on the main bus (CS from the decoder), internal oscillator (CLK tied low).',
        20,
        15,
    )
    sh.note(
        'DRDY goes to its test point only: firmware polls the conversion. The ESD '
        'clamp sits on the connector side of the 1k resistors; 10 nA of leakage is '
        'about 0.01 K.',
        20,
        21,
    )
    adc = place_ic(
        sh,
        'cryocooler:ADS1220IRVAR',
        'ADS1220IRVAR',
        54,
        60,
        'Package_DFN_QFN:Texas_RVA_VQFN-16-1EP_3.5x3.5mm_P0.5mm_EP2.14x2.14mm',
    )
    # supplies
    avdd, dvdd = pin_cell(adc, '10'), pin_cell(adc, '11')
    wire(sh, avdd, (avdd[0], 42))
    wire(sh, dvdd, (dvdd[0], 42))
    wire(sh, (avdd[0], 42), (dvdd[0], 42))
    rail_symbol(sh, '+3V3_CH', ((avdd[0] + dvdd[0]) // 2, 42))
    place_blocks(
        sh,
        [('ADS1220 DECOUPLING CAPACITORS', '+3V3_CH', ('100nF', '1uF'))],
        190,
        100,
    )
    gnd_bus(sh, [pin_cell(adc, number) for number in ('6', '3', '2', '1', '17')])
    # left side: SPI bus labels; the decoder drives CS push-pull and DRDY is unread
    for pin, net in (
        ('16', 'ADS1220_CS'),
        ('15', 'SPI_SCK'),
        ('14', 'SPI_MOSI'),
        ('13', 'SPI_MISO'),
    ):
        net_label(sh, net, spur(sh, adc, pin, 12), 180, is_global=True)
    kicadgen.retire_refs('R', 2)
    if keeps_test_point('ADS1220_DRDY'):
        drdy_end = spur(sh, adc, '12', 4)
        drdy = (drdy_end[0], drdy_end[1] + 8)
        wire(sh, drdy_end, drdy)
        test_point(sh, 'ADS1220_DRDY', drdy, rot=180)
    else:
        sh.nc(adc, '12')
        kicadgen.retire_refs('TP', 1)
    # right side inputs
    sh.nc(adc, '5')
    j_rtd = conn(
        sh,
        'Connector_Generic:Conn_01x04',
        'RTD PT1000 4-wire',
        170 * 1.27,
        60 * 1.27,
        {},
        PH_4P,
    )
    fp_pin, sp_pin, sn_pin, ref_pin = (
        pin_cell(j_rtd, n) for n in ('1', '2', '3', '4')
    )
    excitation = pin_cell(adc, '4')
    wire(sh, excitation, (74, excitation[1]), (74, 44), (122, 44))
    with rev3_refs('R'):
        hres(sh, '1k', 125, 44)
    wire(sh, (128, 44), (140, 44), (160, 44), (160, fp_pin[1]), fp_pin)
    ain1, ain0, refp = (
        pin_cell(adc, '8'),
        pin_cell(adc, '9'),
        pin_cell(adc, '7'),
    )
    wire(sh, ain1, (76, ain1[1]), (76, 50), (93, 50))
    hres(sh, '1k', 96, 50)
    wire(sh, (99, 50), (140, 50), (156, 50), (156, sp_pin[1]), sp_pin)
    vcap(sh, '10nF', 82, 50)
    drop_ground(sh, (82, 56), 0)
    vcap(sh, '100nF', 88, 50)
    wire(sh, (88, 56), (88, 68))
    wire(sh, ain0, (78, ain0[1]), (78, 68), (93, 68))
    hres(sh, '1k', 96, 68)
    wire(sh, (99, 68), (140, 68), (152, 68), (152, sn_pin[1]), sn_pin)
    vcap(sh, '10nF', 82, 68)
    drop_ground(sh, (82, 74), 0)
    wire(
        sh,
        refp,
        (76, refp[1]),
        (76, 80),
        (140, 80),
        (160, 80),
        (160, ref_pin[1]),
        ref_pin,
    )
    vres(sh, '3.9k', 100, 80)
    drop_ground(sh, (100, 86), 0)
    vcap(sh, '100nF', 108, 80)
    drop_ground(sh, (108, 86), 0)
    # ESD clamp on all four cable lines
    with rev3_refs('U'):
        clamp = esd_array(sh, 150, 104)
    for pin, (net, tap_row) in zip(
        ESD_ARRAY_IO_PINS,
        (('RTD_1', 44), ('RTD_2', 50), ('RTD_3', 68), ('RTD_4', 80)),
    ):
        wire(sh, (140, tap_row), (140, tap_row - 3), (142, tap_row - 3))
        net_label(sh, net, (142, tap_row - 3), 0)
        net_label(sh, net, spur(sh, clamp, pin, 3), 180)


def build_imu(sh):
    """Hand-laid: J14 (Molex Micro-Lock Plus 2x4 cabled to the off-board Adafruit
    LSM6DSOX module) on the right, +3V3 / ground pins tied off beside it, each
    signal fanned out to a 100 R series resistor and a global label on the
    left. Pins follow the T568B pairs: 1-2 SCK/GND, 3-6 MOSI/MISO,
    4-5 +3V3/CS, 7-8 INT1/INT2.
    """
    sh.handwired = True
    sh.note(
        'LSM6DSOX is the off-board Adafruit module (product 4438) on the '
        'cooler, cabled to J14 (Molex Micro-Lock Plus 2x4, 1.25 mm) over the main SPI '
        'bus (CS from the decoder, INT1 GPIO2 single-tap, INT2 GPIO39 wake-up).',
        20,
        15,
    )
    sh.note(
        'J14 pin -> module pad: 1 SCL, 2 GND, 3 SDA, 4 Vin, 5 CS, 6 DO, '
        '7 I1, 8 I2 (3Vo pad open). Keep the cable short and twist SCK with '
        'GND (pins 1-2 sit one above the other).',
        20,
        21,
    )
    sh.note(
        'Module Vin = +3V3 keeps its logic at 3.3 V. NUF6401MN filter: 100 R in '
        'series to damp the cable, 17 pF and an ESD clamp on each side of all six '
        'signals.',
        20,
        27,
    )
    # the on-board sensor (U19) and its three capacitors (C53-C55) are gone;
    # their numbers stay retired so every later part keeps its reference
    kicadgen.retire_refs('U', 1)
    kicadgen.retire_refs('C', 3)
    with kicadgen.pinned_refs('J', 13):
        header = sh.add(
            'cryocooler:Conn_02x04_Rails_At_Ends',
            next_ref('J'),
            '505448-0891',
            200 * 1.27,
            60 * 1.27,
            mirror=True,
            auto=False,
            footprint='cryocooler:Molex_Micro-Lock_Plus_505448-0891_2x04_P1.25mm_Horizontal',
        )
    tips = {
        number: pin_cell(header, number)
        for number in [str(n) for n in range(1, 9)]
    }
    column = tips['1'][0]
    # +3V3 and the cable ground sit at the ends of the side, so their rails have
    # room
    wire(sh, tips['4'], (column - 2, tips['4'][1]))
    rail_symbol(sh, '+3V3', (column - 2, tips['4'][1]))
    wire(sh, tips['2'], (column - 2, tips['2'][1]))
    rail_symbol(sh, 'GND', (column - 2, tips['2'][1]))
    signals = sorted(
        (
            ('1', 'SPI_SCK'),
            ('3', 'SPI_MOSI'),
            ('6', 'SPI_MISO'),
            ('5', 'IMU_CS'),
            ('7', 'IMU_INT1'),
            ('8', 'IMU_INT2'),
        ),
        key=lambda signal: tips[signal[0]][1],
    )
    with rev3_refs('U'):
        part = imu_filter(sh, column - 36, 84)
        # one six-channel part replaces the two NUF4001s (U36, U37): U37 retires
        kicadgen.retire_refs('U', 1)
    # the removed series resistors leave one number retired, as the old CS pull-up did
    kicadgen.retire_refs('R', 1)
    jack_pins = ('12', '11', '10', '9', '8', '7')
    module_pins = ('1', '2', '3', '4', '5', '6')
    # staircase fan-out, top signal turning furthest left, so no wires cross
    for channel, (number, net) in enumerate(signals):
        target = pin_cell(part, jack_pins[channel])
        bend = column - 8 - 3 * (len(signals) - 1 - channel)
        wire(sh, tips[number], (bend, tips[number][1]), (bend, target[1]), target)
        far = spur(sh, part, module_pins[channel], 12)
        net_label(sh, net, far, 180, is_global=True)


def imu_filter(sh, column, row):
    """NUF6401MN six-channel 100 R filter with its ground pad tied off."""
    part = place_ic(
        sh,
        'cryocooler:NUF6401MNT1G',
        'NUF6401MNT1G',
        column,
        row,
        'cryocooler:OnSemi_DFN-12-1EP_506AD',
    )
    drop_ground(sh, pin_cell(part, '13'), 2)
    return part


FPC14 = (
    'Connector_FFC-FPC:Hirose_FH12-14S-0.5SH_1x14-1MP_P0.50mm_Horizontal'
)


def build_display(sh):
    """Display sheet; its parts take high reference numbers."""
    with high_refs('R'), high_refs('C'), high_refs('Q'):
        display_parts(sh)


def display_parts(sh):
    """Hand-laid: the FPC to the Phoenix 2.4" touch display (ST7789V, 4-wire
    SPI) on the right, its TSC2046 touch controller on the left, backlight
    switch and strap pull-downs below.
    """
    sh.handwired = True
    sh.note(
        'Phoenix DCT T 2,4 QVGA S RTOUCH (in the UCS 125-87-F-GD-D2,4 lid), '
        'datasheet 109921: ST7789V, 4-wire SPI half duplex (SDA is input '
        'only), VCC 2.6-3.3 V, FPC FH12-14S-0.5SH.',
        20,
        15,
    )
    sh.note(
        'Pin 1 YU, 2 XL, 3 YD, 4 XR (raw resistive touch), 5 GND, 6 VCC, '
        '7 /CS, 8 /RST, 9 RS (D/C), 10 SCL, 11 SDA, 12 NC, 13 A, 14 C. '
        'Backlight: 4 LEDs in parallel, 3.0 V / 60 mA typ.',
        20,
        21,
    )
    sh.note(
        'GPIO46 (DISP_RST) is a strapping pin: a 10k pull-down holds its '
        'default (low) level at reset. DISP_CS and TOUCH_CS come from the CS '
        'decoder on the root sheet.',
        20,
        27,
    )
    with kicadgen.pinned_refs('J', 14):
        fpc_ref = next_ref('J')
    fpc = sh.add(
        'Connector_Generic_MountingPin:Conn_01x14_MountingPin',
        fpc_ref,
        'FH12-14S-0.5SH(55)',
        200 * 1.27,
        80 * 1.27,
        rot=180,
        mirror=True,
        auto=False,
        footprint=FPC14,
    )
    tips = {
        number: pin_cell(fpc, number)
        for number in [str(n) for n in range(1, 15)] + ['MP']
    }
    # supply pins run out past the signal labels, where nothing is above or below
    for pin, net in (('6', '+3V3'), ('5', 'GND')):
        end = (tips[pin][0] - 26, tips[pin][1])
        wire(sh, tips[pin], end)
        rail_symbol(sh, net, end)
    mount = tips['MP']
    wire(sh, mount, (mount[0], mount[1] - 2), (mount[0] + 3, mount[1] - 2))
    rail_symbol(sh, 'GND', (mount[0] + 3, mount[1] - 2))
    sh.nc(fpc, '12')
    for number, net, is_global in (
        ('1', 'TOUCH_YP', False),
        ('2', 'TOUCH_XN', False),
        ('3', 'TOUCH_YN', False),
        ('4', 'TOUCH_XP', False),
        ('7', 'DISP_CS', True),
        ('8', 'DISP_RST', True),
        ('9', 'DISP_DC', True),
        ('10', 'SPI_SCK', True),
        ('11', 'SPI_MOSI', True),
        ('13', 'DISP_BL_A', False),
        ('14', 'DISP_BL_K', False),
    ):
        net_label(sh, net, spur(sh, fpc, number, 12), 180, is_global=is_global)
    # touch controller: panel lines on the left, SPI on the right
    touch = place_ic(
        sh,
        'cryocooler:TSC2046EIRGVT',
        'TSC2046EIRGVT',
        80,
        74,
        'Package_DFN_QFN:Texas_RGV0016A_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm',
    )
    for pin, net in (
        ('6', 'TOUCH_XP'),
        ('7', 'TOUCH_YP'),
        ('8', 'TOUCH_XN'),
        ('9', 'TOUCH_YN'),
    ):
        net_label(sh, net, spur(sh, touch, pin, 4), 180)
    for pin, net in (
        ('4', 'SPI_SCK'),
        ('3', 'TOUCH_CS'),
        ('2', 'SPI_MOSI'),
        ('16', 'SPI_MISO'),
    ):
        net_label(sh, net, spur(sh, touch, pin, 4), 0, is_global=True)
    sh.nc(touch, '1')
    irq = spur(sh, touch, '15', 4)
    net_label(sh, 'TOUCH_IRQ', irq, 0, is_global=True)
    if keeps_test_point('TOUCH_IRQ'):
        wire(sh, irq, (irq[0], irq[1] + 4))
        test_point(sh, 'TOUCH_IRQ', (irq[0], irq[1] + 4), rot=180)
    else:
        kicadgen.retire_refs('TP', 1)
    vcc, iovdd = pin_cell(touch, '5'), pin_cell(touch, '14')
    wire(sh, vcc, (vcc[0], vcc[1] - 4), (iovdd[0], iovdd[1] - 4), iovdd)
    rail_symbol(sh, '+3V3', (vcc[0], vcc[1] - 4))
    sh.nc(touch, '13')
    # VBAT and AUX are unused ADC inputs: grounded with GND and the exposed pad
    gnd_bus(sh, [pin_cell(touch, number) for number in ('10', '11', '12', '17')])
    place_blocks(
        sh,
        [
            ('TSC2046 DECOUPLING CAPACITORS', '+3V3', ('100nF', '1uF')),
            ('DISPLAY DECOUPLING CAPACITORS', '+3V3', ('100nF', '4.7uF')),
        ],
        150,
        130,
    )
    # backlight: +5V_OR -> 39R -> anode; cathode switched to ground by a
    # BSS138 that an expander pin turns on (pulled off at reset)
    sh.note('BACKLIGHT', 20 * 1.27, 112 * 1.27, 1.8)
    rail_symbol(sh, '+5V_OR', (24, 120))
    wire(sh, (24, 120), (28, 120))
    hres(sh, '39', 31, 120, fp=R1206)
    wire(sh, (34, 120), (38, 120))
    net_label(sh, 'DISP_BL_A', (38, 120), 0)
    fet = nfet(sh, 'BSS138', '', '', pose=at(60, 130), fp=SOT23)
    gate, drain = pin_cell(fet, '1'), pin_cell(fet, '3')
    wire(sh, drain, (drain[0], drain[1] - 4))
    net_label(sh, 'DISP_BL_K', (drain[0], drain[1] - 4), 90)
    drop_ground(sh, pin_cell(fet, '2'), 2)
    wire(sh, gate, (gate[0] - 10, gate[1]))
    net_label(sh, 'DISP_BL_EN', (gate[0] - 10, gate[1]), 180, is_global=True)
    vres(sh, '100k', gate[0] - 5, gate[1])
    drop_ground(sh, (gate[0] - 5, gate[1] + 6), 0)
    # strap pull-downs
    sh.note('STRAP PULL-DOWNS', 90 * 1.27, 104 * 1.27, 1.8)
    # the GPIO45 pull-down moved to the decoder's address line; R168 stays retired
    kicadgen.retire_refs('R', 1)
    net_label(sh, 'DISP_RST', (116, 116), 90, is_global=True)
    wire(sh, (116, 116), (116, 120))
    vres(sh, '10k', 116, 120)
    drop_ground(sh, (116, 126), 0)
    display_buffers(sh)


# Last-used numbers: the DISP_DC buffer takes U31, R179, C128 (U30, R178, C127
# went with the DISP_CS buffer).
DISPLAY_BUFFER_REFS = ((30, 178),)
DISPLAY_BUFFER_LAST_CAP = 127


def display_buffers(sh):
    """GPIO47/48 swing 1.8 V on the R16V module, too low for the display's 3.3 V
    logic. 74LV1T34GX: VIH 1.37 V at 3.3 V supply, input to 5.5 V. Pull-downs hold
    the inputs defined while the GPIOs float during boot. Pin 1 (n.c.) is grounded:
    the footprint bridges it to the centre GND land.
    """
    sh.note('DISPLAY LOGIC BUFFERS', 20 * 1.27, 148 * 1.27, 1.8)
    sh.note(
        'GPIO47/48 are 1.8 V on N32R16V. 74LV1T34GX: VIH 1.37 V at 3.3 V.',
        20 * 1.27,
        152 * 1.27,
    )
    for (column, in_net, out_net), (buffer_ref, resistor_ref) in zip(
        ((120, 'DISP_DC_1V8', 'DISP_DC'),),
        DISPLAY_BUFFER_REFS,
    ):
        with kicadgen.pinned_refs('U', buffer_ref):
            buffer_part = place_ic(
                sh,
                'cryocooler:74LV1T34GX',
                '74LV1T34GX',
                column,
                168,
                'cryocooler:Nexperia_X2SON-5_SOT1226-3_0.8x0.8mm_P0.5mm',
            )
        supply = pin_cell(buffer_part, '5')
        wire(sh, supply, (supply[0], supply[1] - 4))
        rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
        gnd_bus(sh, [pin_cell(buffer_part, '1'), pin_cell(buffer_part, '3')])
        in_end = spur(sh, buffer_part, '2', 12)
        net_label(sh, in_net, in_end, 180, is_global=True)
        with kicadgen.pinned_refs('R', resistor_ref):
            vres(sh, '100k', in_end[0] + 6, in_end[1])
        drop_ground(sh, (in_end[0] + 6, in_end[1] + 6), 0)
        net_label(sh, out_net, spur(sh, buffer_part, '4', 6), 0, is_global=True)
    with kicadgen.pinned_refs('C', DISPLAY_BUFFER_LAST_CAP):
        place_blocks(
            sh,
            [('74LV1T34GX DECOUPLING CAPACITOR', '+3V3', ('100nF',))],
            180,
            160,
        )


def build_indicators(sh):
    """Hand-laid: the WS2812B-2020 status LED behind its level shifter."""
    sh.handwired = True
    sh.note(
        'WS2812B-2020 status LED on GPIO38 via a 74AHCT1G125GM 3.3 V -> 5 V level shifter. '
        'Works without the SPI bus, so it can show faults '
        'the bus would hide.',
        20,
        15,
    )
    # numbers of the removed READY and FAULT LEDs
    kicadgen.retire_refs('R', 2)
    kicadgen.retire_refs('D', 2)
    buf = place_ic(
        sh,
        'cryocooler:74AHCT1G125GM',
        '74AHCT1G125GM',
        60,
        102,
        'cryocooler:Nexperia_XSON-6_SOT886_1.0x1.45mm_P0.5mm',
    )
    rgb = sh.add(
        'LED:WS2812B-2020',
        next_ref('D'),
        'WS2812B-2020',
        100 * 1.27,
        100 * 1.27,
        auto=False,
        footprint='LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm',
    )
    # buffer: output enable to ground, 5 V supply with bypass, input with
    # pull-down
    sh.nc(buf, '5')
    vcc = pin_cell(buf, '6')
    wire(sh, vcc, (vcc[0], vcc[1] - 4))
    rail_symbol(sh, '+5V', (vcc[0], vcc[1] - 4))
    gnd_bus(sh, [pin_cell(buf, '1'), pin_cell(buf, '3')])
    a_pin = pin_cell(buf, '2')
    net_label(sh, 'STATUS_RGB', (a_pin[0] - 14, a_pin[1]), 180, is_global=True)
    wire(sh, a_pin, (a_pin[0] - 14, a_pin[1]))
    vres(sh, '10k', a_pin[0] - 6, a_pin[1])
    drop_ground(sh, (a_pin[0] - 6, a_pin[1] + 6), 0)
    y_pin = pin_cell(buf, '4')
    wire(sh, y_pin, (y_pin[0] + 2, y_pin[1]))
    hres(sh, '330', y_pin[0] + 5, y_pin[1])
    wire(sh, (y_pin[0] + 8, y_pin[1]), pin_cell(rgb, '3'))
    vdd = pin_cell(rgb, '4')
    wire(sh, vdd, (vdd[0], vdd[1] - 6))
    rail_symbol(sh, '+5V', (vdd[0], vdd[1] - 6))
    place_blocks(
        sh,
        [
            ('74AHCT1G125GM DECOUPLING CAPACITORS', '+5V', ('100nF',)),
            ('WS2812B-2020 DECOUPLING CAPACITORS', '+5V', ('100nF',)),
        ],
        150,
        70,
        max_column=300,
    )
    drop_ground(sh, pin_cell(rgb, '2'), 2)
    sh.nc(rgb, '1')


# ═════════════════════════════════════════════════════════════════════════
# Project assembly
# ═════════════════════════════════════════════════════════════════════════
# root sheet uuid KiCad has recorded for this project (instance paths must
# start with it)
ROOT_UUID = '8aa5b67b-a486-4448-878d-4d9f2d51f462'

# ── supply switches ──────────────────────────────────────────────────────
# One SMT 0R jumper in series with each load's supply feed (desolder it to
# power that part off). Each switched rail is a power net of its own:
# (key, main rail, switched rail, title).
# Keystone 5110: a 'true zero ohm' 0603 SMT jumper that drops onto a
# standard 0603 resistor land pattern (Keystone catalog p.60)
SWITCH_HEADER = 'Resistor_SMD:R_0603_1608Metric'
SWITCHES = (
    ('SG3', '+3V3', '+3V3_SG', 'SIGNAL GEN +3V3'),
    ('PS15', '+5V', '+5V_PS15', '+-15V RAILS ENABLE (+5V IN)'),
    ('ISO5', '+5V_OR', '+5V_ISO', 'ISOLATED SUPPLY +5V IN'),
    ('COOL', '+3V3', '+3V3_COOL', 'WATER COOLING +3V3 (FAN, PUMP, FLOW, NTC)'),
    ('CH', '+3V3', '+3V3_CH', 'COLD HEAD +3V3 (ADS1220 RTD ADC)'),
)
kicadgen.POWER_SYMBOLS.update({spec[2]: spec[1] for spec in SWITCHES})
kicadgen.POWER_SYMBOLS['+5V_ISO'] = '+5V'
kicadgen.POWER_SYMBOLS['VISOOUT'] = '+5VA'
kicadgen.POWER_SYMBOLS['ISO_GND2'] = 'GNDREF'
# The ADS1220 reference is ratiometric but its supply is shared with the buck, so
# the cold head feed gets a ferrite ahead of its jumper.
BEAD_AHEAD_OF_JUMPER = {'CH'}


def supply_block(sh, spec, column, row):
    """Main rail -> jumper -> switched rail, with a PWR_FLAG on the switched rail."""
    key, main, switched, title = spec
    sh.note(title, column * 1.27, (row - 6) * 1.27, 1.6)
    jumper = sh.add(
        'Jumper:Jumper_2_Bridged',
        next_ref('JP'),
        f'EN {key}',
        (column + 10) * 1.27,
        row * 1.27,
        rot=0,
        auto=False,
        footprint=SWITCH_HEADER,
    )
    first, second = pin_cell(jumper, '1'), pin_cell(jumper, '2')
    if key in BEAD_AHEAD_OF_JUMPER:
        with rev3_refs('FB'):
            aux(
                sh,
                'Device:FerriteBead',
                'FB',
                'BLM18PG121SN1D',
                {},
                pose=at(first[0] - 3, first[1], 90),
                fp=BEAD_0603,
            )
        rail_symbol(sh, main, (first[0] - 10, first[1]))
        wire(sh, (first[0] - 10, first[1]), (first[0] - 6, first[1]))
    else:
        rail_symbol(sh, main, (first[0] - 4, first[1]))
        wire(sh, (first[0] - 4, first[1]), first)
    flag_x, switched_x = second[0] + 3, second[0] + 6
    wire(sh, second, (flag_x, second[1]), (switched_x, second[1]))
    rail_flag(sh, (flag_x, second[1]))
    rail_symbol(sh, switched, (switched_x, second[1]))


def build_supply_switches(sh):
    """Hand-laid grid of supply blocks, one per switched load."""
    sh.handwired = True
    sh.note(
        'Each Keystone 5110 0603 jumper sits in series with one load supply: '
        'remove it to power that part off. A part left unpowered can still be fed '
        'through its signal pins, so disconnect the cable too when you need it fully dead.',
        20,
        15,
    )
    for index, spec in enumerate(SWITCHES):
        supply_block(sh, spec, 36 + 90 * (index // 6), 40 + 28 * (index % 6))


SHEETS = [
    ('Power Input', 'power_input', build_power_input, 'A3'),
    ('Signal Generator', 'signal_gen', build_signal_gen, 'A3'),
    ('Water Cooling', 'cooling', build_cooling, 'A3'),
    ('Power Button', 'power_button', build_power_button, 'A3'),
    ('Amp Control', 'amp_control', build_amp_control, 'A3'),
    ('Cold Head Temp', 'cold_head', build_cold_head, 'A3'),
    ('Rails 5V 3V3', 'rails_logic', build_rails_logic, 'A3'),
    ('Amp Current', 'amp_current', build_amp_current, 'A3'),
    ('IMU', 'imu', build_imu, 'A3'),
    ('Rails +-15V', 'rails_15v', build_rails_15v, 'A3'),
    ('Power Good', 'power_good', build_power_good, 'A3'),
    ('System Current', 'system_current', build_system_current, 'A3'),
    ('Indicators', 'indicators', build_indicators, 'A3'),
    (
        'Compressor Relay',
        'compressor_relay',
        build_compressor_relay,
        'A3',
    ),
    ('GPIO Expander', 'gpio_expander', build_gpio_expander, 'A3'),
    ('Debug', 'debug', build_debug, 'A3'),
    ('Supply Switches', 'supply_switches', build_supply_switches, 'A3'),
    ('Display', 'display', build_display, 'A3'),
]


def sheet_symbol(root_uuid, child, index, x, y):
    width, height = 50.8, 12.7
    return (
        f'\t(sheet (at {fmt(x)} {fmt(y)}) (size {fmt(width)} {fmt(height)}) '
        f'(exclude_from_sim no) '
        f'(in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes) '
        f'(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0)) (uuid '
        f'{q(child.uid)})\n'
        f'\t\t(property "Sheetname" {q(child.title)} (at {fmt(x)} '
        f'{fmt(y - 0.7)} 0) (show_name no) '
        f'(do_not_autoplace no) (effects (font (size 1.27 1.27)) (justify '
        f'left bottom)))\n'
        f'\t\t(property "Sheetfile" {q("sheets/" + child.filename)} (at '
        f'{fmt(x)} {fmt(y + height + 0.6)} 0) '
        f'(show_name no) (do_not_autoplace no) (effects (font (size 1.27 '
        f'1.27)) (justify left top)))\n'
        f'\t\t(instances (project {q(PROJECT)} (path {q("/" + root_uuid)} '
        f'(page {q(str(index + 2))}))))\n\t)'
    )


def main():
    kicadgen.reset_uuids()
    root_uuid = ROOT_UUID
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
        root.sheet_symbols.append(
            sheet_symbol(
                root_uuid, child, index, 20 + column * 70, 190 + row * 25
            )
        )
    # final references; the builders keep allocating their own numbers
    for sheet in [root] + children:
        for part in sheet.parts:
            part.ref = REF_MAP.get(part.ref, part.ref)

    import textlayout
    import part_links

    unlinked = []
    for sheet in [root] + children:
        for part in sheet.parts:
            if part.ref.startswith('#'):
                continue
            footprint = part.footprint or kicadgen.symbol_prop(
                kicadgen.get_symbol(part.lib_id), 'Footprint'
            )
            found = part_links.links(part.ref, part.value, footprint)
            if not found and not part.ref.startswith('TP'):
                unlinked.append(part.ref)
            part.props.update(found)
    print(f'part links: {len(unlinked)} parts without a part number:',
          ' '.join(unlinked))

    overlaps = 0
    junctions = 0
    for sheet in [root] + children:
        sheet.finalize()
        for column, row, count in sheet.four_way_junctions():
            print(
                f'  [{sheet.title}] {count}-way junction at column '
                f'{column:.0f}, row {row:.0f}'
            )
            junctions += 1
        for problem in textlayout.check_text(sheet):
            overlaps += 1
            print(f'  [{sheet.title}] {problem}')
        for missing in textlayout.unlabeled_power(sheet):
            overlaps += 1
            print(f'  [{sheet.title}] power symbol name hidden: {missing}')
    print(f'text overlap check: {overlaps} overlaps')
    # a reference used by two different parts silently merges them in the
    # netlist; units of one multi-unit part share theirs on purpose
    owners = {}
    duplicates = 0
    for sheet in [root] + children:
        for part in sheet.parts:
            if part.ref.startswith('#'):
                continue
            owner = (sheet.title, part.lib_id, part.value)
            if owners.setdefault(part.ref, owner) != owner:
                duplicates += 1
                print(f'  duplicate reference {part.ref}: {owners[part.ref]} '
                      f'and {owner}')
    print(f'duplicate reference check: {duplicates} found')
    (ROOT_DIR / 'sheets').mkdir(exist_ok=True)
    (ROOT_DIR / 'cryocooler.kicad_sch').write_text(root.render(root_uuid))
    for child in children:
        (ROOT_DIR / 'sheets' / child.filename).write_text(
            child.render(root_uuid)
        )
    # the project file lists every sheet's uuid; keep it in step with the
    # generated files
    project_file = ROOT_DIR / 'cryocooler.kicad_pro'
    project = json.loads(project_file.read_text())
    project['sheets'] = [[root_uuid, 'cryocooler']] + [
        [child.uid, child.title] for child in children
    ]
    project_file.write_text(json.dumps(project, indent=2) + '\n')
    print('wrote', 1 + len(children), 'sheets')
    if duplicates:
        sys.exit(1)
    print(f'4-way junction check: {junctions} found')
    if overlaps or junctions:
        sys.exit(1)


if __name__ == '__main__':
    main()
