"""Generates the Cryocooler controller KiCad project (root + sheets).

Run: python3 hardware/kicad/tools/gen_schematic.py
GPIO assignments follow include/config/pin_config.h.
"""

import fnmatch
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import kicadgen
import textlayout
import sexpr
from ref_map import REF_MAP
from kicadgen import (
    label_shape,
    Sheet,
    next_ref,
    q,
    fmt,
    POWER_SYMBOLS,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT = 'cryocooler'
ROOT_FILE = 'cryocooler.kicad_sch'

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
LED_1005 = 'cryocooler:LED_Kingbright_APHHS1005'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
R_ARRAY = 'Resistor_SMD:R_Array_Convex_4x0402'  # Yageo YC124, four isolated elements
# Right-angle connectors: every plug enters parallel to the board, through the
# housing side walls. Ratings are from each maker's datasheet. The XKB X2510WRS
# wafers are all-SMD (4 A) and take X2510H housings, not PC fan plugs.
X2510_4P = 'cryocooler:XKB_X2510WRS-04-9TSN_1x04_P2.54mm_Horizontal'
X2510_2P = 'cryocooler:XKB_X2510WRS-02-9TSN_1x02_P2.54mm_Horizontal'
USB_C_FLAG = 'cryocooler:USB_C_Receptacle_GCT_USB4205-GF-A_16P_Flag'
PH_4P = 'cryocooler:Adafruit_4392_JST-PH_1x04_P2.00mm_Horizontal_SMD'  # 2 A
# Top-entry JST PH (2 A, datasheet ePH.pdf): cabled inside the housing, so these
# sit inboard on the front and leave the board edges to the wall ports (rev 6)
PH_V4 = 'Connector_JST:JST_PH_B4B-PH-SM4-TB_1x04-1MP_P2.00mm_Vertical'
PH_V5 = 'Connector_JST:JST_PH_B5B-PH-SM4-TB_1x05-1MP_P2.00mm_Vertical'
PH_V6 = 'Connector_JST:JST_PH_B6B-PH-SM4-TB_1x06-1MP_P2.00mm_Vertical'
PH_V10 = 'Connector_JST:JST_PH_B10B-PH-SM4-TB_1x10-1MP_P2.00mm_Vertical'
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

# The ADP5071 output capacitors also serve as the LT3045 / LT3094 inputs. No 22 uF / 50 V
# X7R 1210 could be sourced, so the rails use 25 V parts, doubled on -16V5 and
# both regulator outputs to hold the required 10 uF effective at 15 V DC.
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


# Rev 4 parts take numbers above every reference on the rev 3 board and every
# ref_map.py key, so nothing built earlier or later shifts. RN = resistor array.
REV4_REFS = {'R': 500, 'C': 300, 'D': 80, 'Q': 60, 'U': 40, 'J': 15, 'RN': 0}


@contextmanager
def ranged_refs(ranges, prefixes):
    """Numbers parts created inside the block from `ranges`, which keeps count."""
    counters = kicadgen._ref_counters
    saved = {prefix: counters[prefix] for prefix in prefixes}
    for prefix in prefixes:
        counters[prefix] = ranges[prefix]
    yield
    for prefix in prefixes:
        ranges[prefix] = counters[prefix]
        counters[prefix] = saved[prefix]


def rev3_refs(*prefixes):
    """Numbers parts created inside the block from the rev 3 ranges."""
    return ranged_refs(REV3_REFS, prefixes)


def rev4_refs(*prefixes):
    """Numbers parts created inside the block from the rev 4 ranges."""
    return ranged_refs(REV4_REFS, prefixes)


def grid(value):
    return round(value / 1.27) * 1.27


# ── component helpers ────────────────────────────────────────────────────
# Discretes are auto-placed beside the pin named by near=(part, pin);
# ICs/connectors are fixed.
def res(sh, value, a, b, near=None, fp=R0402, pose=None, small=False, **props):
    """small draws the compact symbol (pins 2 cells from the centre, not 3), for
    tight spots.
    """
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        'Device:R_Small_US' if small else 'Device:R_US',
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


def cap(sh, value, a, b='GND', near=None, fp=None, pose=None, small=False):
    # rev 2 packs small values in 0402 (50 V X7R / C0G), 1 uF in 0603
    fp = fp or (
        C0402
        if value in SMALL_CAPS
        else C0603 if value in ('1uF', '47nF', '68nF')
        else C0805 if value in ('2.2uF', '4.7uF', '10uF') else C1206
    )
    px, py, prot = pose or (0, 0, 0)
    part = sh.add(
        'Device:C_Small' if small else 'Device:C',
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


def chip_led(sh, value, column, row):
    """Kingbright APHHS1005 single LED centred at (column, row), anode (pin 2)
    on the left and cathode (pin 1) on the right; the caller wires both."""
    return sh.add(
        'Device:LED', next_ref('D'), value, column * 1.27, row * 1.27, rot=180,
        auto=False, footprint=LED_1005,
    )


def rg_led(sh, value, column, row, nets, labels=True, antiparallel=False):
    """Kingbright APGB0607G22R23C green/red LED centred at (column, row): pins 1 GA
    (row - 2) and 4 RA (row) on the left, 2 GK (row - 2) and 3 RK (row) on the
    right. nets maps a pin to a local label, ('global', name), or None (unused die).
    labels=False draws only the pin stubs, for the caller to wire. antiparallel
    uses the symbol drawn for dies wired back to back: RA and GK on the left,
    GA and RK on the right (same rows), so each pair joins with a short tee.
    """
    part = sh.add(
        'cryocooler:APGB0607G22R23C' + ('_AP' if antiparallel else ''),
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
        if not labels:
            continue
        angle = 180 if pin in ('1', '4') else 0
        net_label(sh, net[1] if is_global else net, end, angle, is_global=is_global)
    return part


def nfet(sh, value, gate, drain, source='GND', near=None, fp=SOT23, pose=None, mirror=False):
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
        mirror=mirror,
    )
    sh.connect(part, '1', gate)
    sh.connect(part, '3', drain)
    sh.connect(part, '2', source)
    return part


# BSS138DW (Diodes ds30203, SOT-363): each element's (gate, source, drain) pins
DUAL_NFET_PINS = {1: ('2', '1', '6'), 2: ('5', '4', '3')}


def nfet_dual(sh, ref, unit, column, row):
    """One element of a BSS138DW dual N-FET, drawn like a single BSS138."""
    return sh.add(
        'Transistor_FET:Q_Dual_NMOS_S1G1D2S2G2D1',
        ref,
        'BSS138DW',
        column * 1.27,
        row * 1.27,
        unit=unit,
        auto=False,
        footprint=SC70_6,
    )


def array_res(sh, ref, unit, value, column, row, rot=0):
    """Element `unit` of a 4 x 0402 resistor array (pins n and 9 - n). rot 0 is
    vertical with its upper pin (9 - n) on (column, row), like vres, and rot 180
    the same with pin n on top; rot 90 is horizontal and centred on (column, row),
    like hres.
    """
    return sh.add(
        'cryocooler:R_Pack04_Split_US',
        ref,
        value,
        column * 1.27,
        (row + 3 if rot in (0, 180) else row) * 1.27,
        rot=rot,
        unit=unit,
        auto=False,
        footprint=R_ARRAY,
    )


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
    ('1', 'AD9833_FSYNC'),
    ('2', 'AD5453_SYNC'),
    ('3', 'INA239_CS'),
    ('4', 'EXPANDER_CS'),
    ('6', 'ACS_CS'),
    ('7', 'ADS1220_CS'),
    ('8', 'IMU_CS'),
    ('9', 'AMBIENT_CS'),
    ('5', 'IO_DAC_CS'),
    ('10', 'IO_ADC_CS'),
    ('11', 'IO_EXP_CS'),
    ('13', 'RS485_CS'),
    ('14', 'EXP_CS_A'),
    ('15', 'EXP_CS_B'),
)
# Y14 and Y15 are spare chip selects
CS_DECODER_SPARE_PINS = ('16', '17')
# Highest numbers on the rev 4 board; rev 5 parts count up from here so no earlier
# part is renumbered. The ambient sensor sheet takes U+1, C+1, R+1..2, the
# address bit D buffer U+2, C+2, R+3 and the display link (CAN transceiver,
# clamps) U+3..5, C+3, R+5..8.
REV5_LAST = {'U': 49, 'C': 304, 'R': 510, 'TP': 47}
# Last-used numbers: the decoder takes U32, C132, R181-183 and TP45-46.
CS_DECODER_LAST = {'U': 31, 'C': 131, 'R': 180, 'TP': 44}


def cs_decoder(sh):
    """74HC154: the shared SPI bus chip selects, one low at a time. The enable
    pull-up holds every output high until firmware takes over. The address lines
    A, B and C are strapping GPIOs, so their strap resistors live here too. Address
    bit D comes from GPIO47 (1.8 V) through a 74LV1T34 buffer.
    """
    column, row = 56, 100
    sh.note('SPI CHIP SELECT DECODER', 20 * 1.27, 50 * 1.27, 1.8)
    sh.note(
        'One output low at a time. E0 pull-up: all outputs high at reset.',
        20 * 1.27,
        54 * 1.27,
        1.8,
    )
    sh.note(
        'GPIO3 pull-up and GPIO45 pull-down are strap defaults. 74HC154 exposed pad: '
        'floating (datasheet).',
        20 * 1.27,
        58 * 1.27,
        1.8,
    )
    with kicadgen.pinned_refs('U', CS_DECODER_LAST['U']):
        decoder = place_ic(
            sh,
            'cryocooler:74HC154BQ',
            '74HC154BQ',
            column,
            row,
            'cryocooler:Nexperia_SOT815-1_DHVQFN-24-1EP_3.5x5.5mm_P0.5mm',
        )
    # the address and enable lines are more than 85 mm from the ESP32 and the
    # bit-D buffer: a net label at each end. The enable pull-up and the two
    # strap resistors hang on the decoder's own wires, each tee further out
    # than the label above or below it.
    tips = {
        net: spur(sh, decoder, pin, 2)
        for pin, net in (('18', 'CS_EN_N'), ('23', 'CS_ADDR_A'), ('22', 'CS_ADDR_B'),
                         ('21', 'CS_ADDR_C'), ('20', 'CS_ADDR_D'))
    }
    with kicadgen.pinned_refs('R', CS_DECODER_LAST['R']):
        for net, reach in (('CS_ADDR_A', 18), ('CS_EN_N', 2)):
            tip = tips[net]
            tips[net] = (tip[0] + reach, tip[1])
            vres(sh, '10k', tip[0] + reach, tip[1] - 6)
            rail_symbol(sh, '+3V3', (tip[0] + reach, tip[1] - 6))
            wire(sh, tip, tips[net])
        tip = tips['CS_ADDR_C']
        tips['CS_ADDR_C'] = (tip[0] + 18, tip[1])
        # pin 2 on the net and pin 1 on ground, as the board has it
        res(sh, '10k', '', '', pose=at(tip[0] + 18, tip[1] + 3, 180), fp=R0402)
        drop_ground(sh, (tip[0] + 18, tip[1] + 6), 0)
        wire(sh, tip, tips['CS_ADDR_C'])
    sh.link_ends['CS_ADDR_D'] = tips.pop('CS_ADDR_D')
    for net, tip in tips.items():
        end_label(sh, net, tip, 1)
    ground(sh, spur(sh, decoder, '19', 3))
    for pin, net in CS_DECODER_OUTPUTS:
        end_label(sh, net, spur(sh, decoder, pin, 2), -1)
    for pin in (*CS_DECODER_SPARE_PINS, '25'):
        sh.nc(decoder, pin)
    supply = pin_cell(decoder, '24')
    wire(sh, supply, (supply[0], supply[1] - 4))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
    drop_ground(sh, pin_cell(decoder, '12'), 2)
    with kicadgen.pinned_refs('C', CS_DECODER_LAST['C']):
        place_blocks(
            sh,
            [('74HC154 DECOUPLING CAPACITOR', '+3V3', ('100nF',))],
            34,
            142,
        )
    with kicadgen.pinned_refs('TP', CS_DECODER_LAST['TP']):
        if keeps_test_point('+3V3'):
            wire(sh, (supply[0], supply[1] - 4), (supply[0] + 4, supply[1] - 4))
            test_point(sh, '+3V3', (supply[0] + 4, supply[1] - 4))
        gnd_cell = pin_cell(decoder, '12')
        if keeps_test_point('GND'):
            wire(sh, (gnd_cell[0], gnd_cell[1] + 2), (gnd_cell[0] + 4, gnd_cell[1] + 2))
            test_point(sh, 'GND', (gnd_cell[0] + 4, gnd_cell[1] + 2), rot=180)
    address_d_buffer(sh)


def address_d_buffer(sh):
    """GPIO47 swings 1.8 V on the R16V module, too low for the 74HC154 at 3.3 V.
    74LV1T34GX (VIH 1.37 V at 3.3 V) lifts it to CS_ADDR_D. The pull-down holds the
    input, so address bit D reads 0 while the GPIO floats during boot.
    """
    # heading and notes sit above the buffer
    sh.note('ADDRESS BIT D BUFFER', 102 * 1.27, 72 * 1.27, 1.8)
    sh.note('GPIO47 is 1.8 V on N32R16V.', 102 * 1.27, 76 * 1.27, 1.8)
    sh.note('74LV1T34GX: VIH 1.37 V at 3.3 V.', 102 * 1.27, 80 * 1.27, 1.8)
    start = sh.link_ends['CS_ADDR_D_1V8']
    # mirrored: input on the right, facing the ESP32; output toward the decoder
    with kicadgen.pinned_refs('U', REV5_LAST['U'] + 1):
        buffer_part = place_ic(
            sh,
            'cryocooler:74LV1T34GX',
            '74LV1T34GX',
            142,
            start[1] + 2,
            'cryocooler:Nexperia_X2SON-5_SOT1226-3_0.8x0.8mm_P0.5mm',
            mirror=True,
        )
    supply = pin_cell(buffer_part, '5')
    wire(sh, supply, (supply[0], supply[1] - 4))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
    gnd_bus(sh, [pin_cell(buffer_part, '1'), pin_cell(buffer_part, '3')])
    # GPIO47 is within 85 mm: a wire, with its pull-down and its name on it
    wire(sh, start, pin_cell(buffer_part, '2'))
    with kicadgen.pinned_refs('R', REV5_LAST['R'] + 3):
        vres(sh, '100k', 170, start[1])
    drop_ground(sh, (170, start[1] + 6), 0)
    net_label(sh, 'CS_ADDR_D_1V8', (start[0] - 1, start[1]), 180)
    # bit D is within 85 mm of the decoder too: a wire, under the pull-down
    # on A2 and up to A3
    out, pin = pin_cell(buffer_part, '4'), sh.link_ends['CS_ADDR_D']
    wire(sh, out, (pin[0] + 10, out[1]), (pin[0] + 10, pin[1]), pin)
    net_label(sh, 'CS_ADDR_D', (pin[0] - 1, pin[1]), 0)
    with kicadgen.pinned_refs('C', REV5_LAST['C'] + 1):
        place_blocks(
            sh,
            [('74LV1T34GX DECOUPLING CAPACITOR', '+3V3', ('100nF',))],
            138,
            132,
        )


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
    colour_legend(sh, 30, 28)
    marks = sheet_marks(sh)
    sh.link_ends = {}
    mcu_and_usb(sh)
    # the MCU and USB sit right of the decoder and its buffer, with room between
    shift_since(sh, marks, MCU_SHIFT, 0)
    sh.link_ends = {
        net: (column + MCU_SHIFT, row)
        for net, (column, row) in sh.link_ends.items()
    }
    cs_decoder(sh)
    root_links(sh)


# Cells between the reset / boot parts and the module's left-hand labels,
# kept free for the wires that leave the module.
ESP_ROOM = 24
# Cells the MCU / USB group moves right of where mcu_and_usb() draws it.
MCU_SHIFT = 50 + ESP_ROOM

# Sheet blocks on the root, in grid cells, six per row, with room between them
# for the labels at their pins. Column 1 holds the sensors, column 2 starts
# with the Signal Generator beside Debug; rows 1 and 2 hold what the ESP32
# drives directly, rows 3 to 5 the universal I/O.
BOX_ORIGIN, BOX_PITCH, BOX_SIZE = (36, 180), (58, 22), (40, 10)
# Blocks with more pins than the standard height holds: stem -> cells.
BOX_HEIGHT = {'cooling': 16, 'gpio_expander': 14, 'io': 22, 'expansion': 16}
BLOCK_ORDER = (
    'cold_head', 'signal_gen', 'debug', 'amp_control', 'display', 'cooling',
    'imu', 'power_good', 'supply_switches', 'power_button', 'compressor_relay', 'indicators',
    'ambient', 'ldo_15v', 'rails_15v', None, 'power_input', 'rails_logic',
    'system_current', 'gpio_expander', 'io', 'expansion', 'aux_header', None,
    'amp_current',
)
COOLING_NETS = ('FAN_PWM', 'PUMP_PWM', 'FAN_TACH', 'PUMP_TACH', 'FLOW_TACH', 'NTC_ADC')
# Sheet pins by sheet file stem: net or bus -> (block edge, cells down from
# its top). Each needs a hierarchical label of the same name on the sheet.
SHEET_PINS = {
    'amp_control': {'AMP_REM_EN': ('left', 4), 'PG_15V': ('left', 6), 'SIG_SINE': ('left', 8)},
    'signal_gen': {
        'AD9833_FSYNC': ('left', 4), 'AD5453_SYNC': ('left', 6),
        'DDS_SINE': ('right', 4), 'SIG_SINE': ('right', 6),
    },
    'debug': {'DDS_SINE': ('left', 4), 'SIG_SINE': ('left', 6)},
    'power_good': {
        'PG_15V': ('left', 2), 'PGN_15V': ('left', 4), 'PG_15V_N': ('right', 4),
        'PGP_15V': ('right', 6),
    },
    'power_button': {'PWR_INT': ('left', 4), 'PWR_KILL': ('left', 6), 'PWR_BTN': ('right', 2)},
    'compressor_relay': {'COMP_RELAY_EN': ('left', 6)},
    'indicators': {'STATUS_RGB': ('left', 4)},
    'display': {
        'CAN_TX': ('left', 4), 'CAN_RX': ('left', 6), 'PWR_BTN': ('left', 8),
        'ESP_EN': ('left', 2),
    },
    'rails_logic': {'USB_VBUS': ('left', 4)},
    'cooling': {net: ('left', 2 + 2 * index) for index, net in enumerate(COOLING_NETS)},
    'amp_current': {'ACS_CS': ('left', 4)},
    # Universal I/O: what leaves the group of I/O sheets for the root
    'io': {
        'IO_EXP_INT_N': ('left', 6), 'IO_ADC_DRDY_N': ('left', 8),
        'IO_DAC_CS': ('left', 12), 'IO_ADC_CS': ('left', 14), 'IO_EXP_CS': ('left', 16),
        'AUX_IO5': ('left', 18), 'AUX_IO7': ('left', 20),
        'RS485_IRQ_N': ('right', 2), 'EXP_INT_N': ('right', 4), 'ESP_EN': ('right', 6),
    },
    # inputs from the blocks around it: the left edge faces the sensor column
    'gpio_expander': {
        'PGN_15V': ('left', 2), 'AMBIENT_INT': ('left', 4), 'AMBIENT_CT': ('left', 6),
        'INA239_ALERT': ('left', 8), 'EXPANDER_CS': ('left', 10),
        'PGP_15V': ('right', 2), 'IO_EXP_INT_N': ('right', 6), 'IO_ADC_DRDY_N': ('right', 8),
    },
    'ldo_15v': {'PGN_15V': ('left', 2), 'PGP_15V': ('right', 2)},
    'expansion': {
        'RS485_IRQ_N': ('left', 2), 'EXP_INT_N': ('left', 4), 'ESP_EN': ('left', 6),
        'RS485_CS': ('left', 8), 'EXP_CS_A': ('left', 10), 'EXP_CS_B': ('left', 12),
    },
    'aux_header': {'AUX_IO11': ('left', 4), 'AUX_IO13': ('left', 6)},
    'imu': {'IMU_CS': ('left', 4), 'IMU_INT1': ('left', 6), 'IMU_INT2': ('left', 8)},
    'ambient': {'AMBIENT_CS': ('left', 4), 'AMBIENT_INT': ('right', 4), 'AMBIENT_CT': ('right', 6)},
    'cold_head': {'ADS1220_CS': ('left', 4)},
    'system_current': {'INA239_CS': ('left', 4), 'INA239_ALERT': ('right', 8)},
}
# Root nets that leave the ESP32 on a wire instead of a global label at the pin.
ROOT_LINKED = {'AMP_REM_EN', 'CS_ADDR_D_1V8'}
# Nets too far from the ESP32 or the decoder for a wire (85 mm rule): a net
# label at the pin that drives or reads them and one at the block's pin. Sheet
# stem -> nets.
LABEL_LINKED = {
    'cold_head': ('ADS1220_CS',),
    'imu': ('IMU_CS', 'IMU_INT1', 'IMU_INT2'),
    'ambient': ('AMBIENT_CS',),
    'system_current': ('INA239_CS',),
    'amp_current': ('ACS_CS',),
    'signal_gen': ('AD9833_FSYNC', 'AD5453_SYNC'),
    'gpio_expander': ('EXPANDER_CS',),
    'io': ('IO_DAC_CS', 'IO_ADC_CS', 'IO_EXP_CS', 'AUX_IO5', 'AUX_IO7'),
    'expansion': ('RS485_CS', 'EXP_CS_A', 'EXP_CS_B'),
    'aux_header': ('AUX_IO11', 'AUX_IO13'),
    'power_good': ('PG_15V_N', 'PG_15V'),
    'amp_control': ('PG_15V',),
    'rails_logic': ('USB_VBUS',),
    'power_button': ('PWR_INT', 'PWR_KILL'),
    'compressor_relay': ('COMP_RELAY_EN',),
    'indicators': ('STATUS_RGB',),
    'display': ('CAN_TX', 'CAN_RX', 'ESP_EN'),
    'cooling': COOLING_NETS,
}


# Sheets drawn inside another sheet instead of on the root: stem -> (parent
# stem, top-left cell of its block on the parent's page). A nested sheet is
# left out of BLOCK_ORDER and must come after its parent in SHEETS. Its nets
# named by a local label take the longer path (/Parent/Child/NET), so nesting
# a sheet that has such nets renames them on the board.
# The Universal I/O page: block -> (top-left cell, nets on its left edge, nets
# on its right edge), pins two cells apart from the top. Columns left to right:
# port expanders, range and pull-up switches, the four channels, drivers and
# the analog ports, DAC and ADC. Neighbouring columns are wired; a net between
# columns that are not neighbours is a pair of net labels.
IO_CHANNELS_ON_PAGE = {1: 50, 2: 78, 3: 106, 4: 134}
# channels that keep a direct ESP32 pin for PWM and pulse input: channel -> GPIO
IO_FAST = {1: 5, 2: 7}
IO_PORT_LINES = [
    f'IO{n}_{name}' for n in IO_CHANNELS_ON_PAGE
    for name in (('BUF_OE_N',) if n in IO_FAST else ()) + ('BURDEN', 'SENS_EN', 'SENS_FLT_N')
]
IO_DRIVER_LINES = [f'IO{n}_OUT_EN' for n in IO_CHANNELS_ON_PAGE] + ['IO_OUT_FLT_A_N']
IO_SWITCH_LINES = [f'IO{n}_{name}' for n in IO_CHANNELS_ON_PAGE for name in ('DIRECT', 'PULLUP')]
IO_PRECISION_INPUTS = ['PREC_A_P', 'PREC_A_N', 'PREC_B_P', 'PREC_B_N', 'PREC_REFP', 'PREC_REFN']
# A labelled pin faces its partner: the expanders' control lines leave on the
# right, toward the columns they drive. On an edge that has both, the labelled
# pins stand above the wired ones, clear of the risers.
IO_BLOCKS = {
    'io_expanders': (
        (32, 36),
        ['IO_EXP_INT_N', 'IO_EXP_CS', 'RS485_IRQ_N', 'EXP_INT_N', 'ESP_EN'],
        IO_PORT_LINES + IO_DRIVER_LINES + ['PREC_EXC_EN', 'PREC_EXC_FLT_N'] + IO_SWITCH_LINES,
    ),
    'io_switches': (
        (118, 90),
        IO_SWITCH_LINES,
        [f'IO{n}_{name}' for n in IO_CHANNELS_ON_PAGE for name in ('PIN', 'DIV')],
    ),
    **{
        f'io_ch{n}': (
            (206, row),
            [f'IO{n}_PIN', f'IO{n}_DIV'] + [net for net in IO_PORT_LINES if net[2] == str(n)],
            ([f'IO{n}_LEVEL', f'IO{n}_ADC', f'IO{n}_DAC', f'AUX_IO{IO_FAST[n]}']
             if n in IO_FAST else [f'IO{n}_ADC']),
        )
        for n, row in IO_CHANNELS_ON_PAGE.items()
    },
    'io_drivers': (
        (292, 62),
        [f'IO{n}_LEVEL' for n in IO_FAST] + [f'IO{n}_PIN' for n in IO_CHANNELS_ON_PAGE]
        + IO_DRIVER_LINES,
        ['IO3_DAC', 'IO4_DAC'],
    ),
    'io_precision': (
        (292, 94),
        ['PREC_EXC_EN', 'PREC_EXC_FLT_N', 'PREC_EXC'],
        IO_PRECISION_INPUTS,
    ),
    'io_pressure': ((292, 118), ['PREC_EXC'], ['PRESS1_ADC', 'PRESS2_ADC']),
    'io_core': (
        (386, 50),
        ['IO1_ADC', 'IO1_DAC', 'IO2_ADC', 'IO2_DAC', 'IO3_ADC', 'IO4_ADC', 'IO3_DAC', 'IO4_DAC']
        + IO_PRECISION_INPUTS + ['PRESS1_ADC', 'PRESS2_ADC'],
        ['IO_DAC_CS', 'IO_ADC_CS', 'IO_ADC_DRDY_N'],
    ),
}
# Nets the Universal I/O page passes on to the root.
IO_TO_ROOT = (
    'IO_EXP_INT_N', 'IO_EXP_CS', 'IO_DAC_CS', 'IO_ADC_CS', 'IO_ADC_DRDY_N',
    'RS485_IRQ_N', 'EXP_INT_N', 'ESP_EN', 'AUX_IO5', 'AUX_IO7',
)
NESTED_SHEETS = {stem: ('io', cell) for stem, (cell, _, _) in IO_BLOCKS.items()}
for _stem, (_cell, _left, _right) in IO_BLOCKS.items():
    SHEET_PINS[_stem] = {
        net: (edge, 2 + 2 * index)
        for edge, nets in (('left', _left), ('right', _right))
        for index, net in enumerate(nets)
    }
    BOX_HEIGHT[_stem] = max(BOX_SIZE[1], 2 * max(len(_left), len(_right)) + 2)
# Sheets that hold other sheets' blocks: a net named there by a net label.
PARENT_FILES = {ROOT_FILE} | {parent + '.kicad_sch' for parent, _ in NESTED_SHEETS.values()}
# Nets named by a net (local) label on the root: every net with a sheet pin,
# and the decoder's lines, which never leave the root. Any other net keeps a
# global label until its sheets get pins.
ROOT_LOCAL = {net for pins in SHEET_PINS.values() for net in pins} | {
    'CS_ADDR_A', 'CS_ADDR_B', 'CS_ADDR_C', 'CS_ADDR_D', 'CS_ADDR_D_1V8', 'CS_EN_N',
    'ESP_BOOT',
}


def box_cell(stem):
    """Top-left cell of a sheet's block on its parent's page."""
    if stem in NESTED_SHEETS:
        return NESTED_SHEETS[stem][1]
    index = BLOCK_ORDER.index(stem)
    return (
        BOX_ORIGIN[0] + (index % 6) * BOX_PITCH[0],
        BOX_ORIGIN[1] + (index // 6) * BOX_PITCH[1],
    )


def sheet_pin_cell(stem, net):
    edge, down = SHEET_PINS[stem][net]
    left, top = box_cell(stem)
    return (left + (BOX_SIZE[0] if edge == 'right' else 0), top + down)


def name_tag(sh, net, tee, end):
    """Stub off a wire ending in a net label that names a net which stays on
    its sheet (ACS_SCK).
    """
    wire(sh, tee, end)
    net_label(sh, net, end, 0 if end[0] > tee[0] else 180)


def end_label(sh, net, end, side):
    """Net label on a pin's wire: the wire runs on from `end` (side +1 to the
    right, -1 to the left) for the length of the name, and the label closes
    its far end, reading back along the wire.
    """
    far = (end[0] + side * (len(net) + 2), end[1])
    wire(sh, end, far)
    net_label(sh, net, far, 180 if side == 1 else 0)


def pin_tag(sh, stem, net):
    """Net label on a wire out of a sheet pin: the block end of a connection
    too long for a wire."""
    pin = sheet_pin_cell(stem, net)
    side = 1 if SHEET_PINS[stem][net][0] == 'right' else -1
    end_label(sh, net, pin, side)


def root_links(sh):
    """What joins the ESP32, the decoder and the sheet blocks: a wire where the
    ends are within 85 mm, a global label at each end where they are not.
    """
    ends = sh.link_ends
    grid_top = BOX_ORIGIN[1]
    # amplifier remote enable: IO6, the lowest pin on the left, drops straight
    # to Amp Control; its name sits on the run into the block
    start, pin = ends['AMP_REM_EN'], sheet_pin_cell('amp_control', 'AMP_REM_EN')
    riser = pin[0] - 13
    wire(sh, start, (riser, start[1]), (riser, pin[1]), pin)
    net_label(sh, 'AMP_REM_EN', (riser + 1, pin[1]), 0)

    # block ends of the nets that leave the module or the decoder on a label
    for stem, nets in LABEL_LINKED.items():
        for net in nets:
            pin_tag(sh, stem, net)

    # GPIO Expander inputs: every source is a neighbouring block, so wires.
    # Each riser stands in the gap beside the expander's column, far enough
    # out for its name to fit on the run into the block; a net that enters
    # lower on the block stands further out.
    def link(net, *stems, riser=None):
        pins = [sheet_pin_cell(stem, net) for stem in stems]
        last = pins[-1]
        if riser is None:
            wire(sh, pins[0], last)
            net_label(sh, net, (min(pins[0][0], last[0]) + 1, last[1]), 0)
            return
        wire(sh, pins[0], (riser, pins[0][1]), (riser, last[1]), last)
        for pin in pins[1:-1]:
            wire(sh, pin, (riser, pin[1]))
        # the name reads along the run into the last block
        net_label(sh, net, (min(riser, last[0]) + 1, last[1]), 0)

    left, right = box_cell('gpio_expander')[0], box_cell('gpio_expander')[0] + BOX_SIZE[0]
    link('PGN_15V', 'power_good', 'ldo_15v', 'gpio_expander', riser=left - 8)
    link('AMBIENT_INT', 'ambient', 'gpio_expander', riser=left - 12)
    link('AMBIENT_CT', 'ambient', 'gpio_expander', riser=left - 15)
    link('INA239_ALERT', 'system_current', 'gpio_expander')
    link('PGP_15V', 'power_good', 'ldo_15v', 'gpio_expander', riser=right + 10)
    link('IO_EXP_INT_N', 'io', 'gpio_expander')
    link('IO_ADC_DRDY_N', 'io', 'gpio_expander')
    # expansion interrupts: read by the I/O port expanders next door
    link('RS485_IRQ_N', 'io', 'expansion')
    link('EXP_INT_N', 'io', 'expansion')
    # the module's reset line, shared by the two neighbours (the ESP32 and
    # the Display reach it by label)
    link('ESP_EN', 'io', 'expansion')
    # the display's button output presses the power button's line
    pin = sheet_pin_cell('power_button', 'PWR_BTN')
    link('PWR_BTN', 'power_button', 'display', riser=pin[0] + 6)

    # sine path: Signal Generator to the Debug test points beside it, and
    # SIG_SINE on under Debug to Amp Control
    for net in ('DDS_SINE', 'SIG_SINE'):
        source = sheet_pin_cell('signal_gen', net)
        wire(sh, source, sheet_pin_cell('debug', net))
        net_label(sh, net, (source[0] + 3, source[1]), 0)
    source, pin = sheet_pin_cell('signal_gen', 'SIG_SINE'), sheet_pin_cell('amp_control', 'SIG_SINE')
    tee, under, rise = source[0] + 14, grid_top + BOX_SIZE[1] + 4, pin[0] - 6
    wire(sh, (tee, source[1]), (tee, under), (rise, under), (rise, pin[1]), pin)


def sheet_marks(sh):
    """How many of each drawn item the sheet holds now (see shift_since)."""
    return {
        name: len(getattr(sh, name))
        for name in ('parts', 'wires', 'buses', 'bus_entries', 'labels', 'text_items')
    }


def shift_since(sh, marks, columns, rows):
    """Moves everything drawn since `marks` by whole grid cells."""
    dx, dy = columns * 1.27, rows * 1.27
    for part in sh.parts[marks['parts']:]:
        part.x += dx
        part.y += dy
    for name in ('wires', 'buses'):
        items = getattr(sh, name)
        items[marks[name]:] = [
            ((x1 + dx, y1 + dy), (x2 + dx, y2 + dy))
            for (x1, y1), (x2, y2) in items[marks[name]:]
        ]
    sh.bus_entries[marks['bus_entries']:] = [
        (x + dx, y + dy, width, height)
        for x, y, width, height in sh.bus_entries[marks['bus_entries']:]
    ]
    sh.labels[marks['labels']:] = [
        (kind, net, (x + dx, y + dy), angle)
        for kind, net, (x, y), angle in sh.labels[marks['labels']:]
    ]
    sh.text_items[marks['text_items']:] = [
        (text, x + dx, y + dy, size, color)
        for text, x, y, size, color in sh.text_items[marks['text_items']:]
    ]


def mcu_and_usb(sh):
    """The ESP32-S3 module with its reset and boot circuits, and the USB-C port."""
    esp = place_ic(
        sh,
        'cryocooler:ESP32-S3-WROOM-2',
        'ESP32-S3-WROOM-2-N32R16V',
        150,
        110,
        None,
    )
    # pin -> net, in the symbol's groups (tools/make_lib.py)
    signals = {
        '15': 'CS_ADDR_A',
        '36': 'CS_ADDR_B',
        '26': 'CS_ADDR_C',
        '24': 'CS_ADDR_D_1V8',
        '12': 'CS_EN_N',
        '38': 'IMU_INT1',
        '32': 'IMU_INT2',
        '39': 'PWR_INT',
        '18': 'PWR_KILL',
        '37': 'PG_15V_N',
        '9': 'COMP_RELAY_EN',
        '6': 'AMP_REM_EN',
        '17': 'FAN_PWM',
        '22': 'PUMP_PWM',
        '8': 'FAN_TACH',
        '23': 'PUMP_TACH',
        '11': 'FLOW_TACH',
        '4': 'NTC_ADC',
        '10': 'CAN_TX',
        '20': 'CAN_RX',
        '31': 'STATUS_RGB',
        '5': 'AUX_IO5',
        '7': 'AUX_IO7',
        '19': 'AUX_IO11',
        '21': 'AUX_IO13',
    }
    for pin, net in signals.items():
        end = spur(sh, esp, pin, 3)
        if net in ROOT_LINKED:
            sh.link_ends[net] = end
            continue
        on_left = end[0] < pin_cell(esp, pin)[0]
        if net in ROOT_LOCAL:
            end_label(sh, net, end, -1 if on_left else 1)
            continue
        net_label(sh, net, end, 180 if on_left else 0, is_global=True)
    sck_row = pin_cell(esp, '35')[1]
    spi_bus(
        sh,
        [
            (spur(sh, esp, pin, 3), net)
            for pin, net in (('33', 'SPI_MISO'), ('34', 'SPI_MOSI'), ('35', 'SPI_SCK'))
        ],
        186,
        1,
        [(186, sck_row + 10), (190, sck_row + 10)],
        label_at=1,
    )
    # 28-30 are NC on the module; GPIO47 (1.8 V) is address bit D, buffered;
    # GPIO46 (pin 16, strap) and GPIO48 (pin 25, 1.8 V) are spare; GPIO11 and
    # GPIO13 go to the AUX header (Expansion sheet)
    for pin in ('16', '25', '28', '29', '30'):
        sh.nc(esp, pin)
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
    sh.note('RESET AND BOOT BUTTONS', (104 - ESP_ROOM) * 1.27, 56 * 1.27, 1.8)
    # EN: RC power-on reset plus RESET switch, drawn above the module
    en = pin_cell(esp, '3')
    riser = en[0] - 2
    wire(sh, en, (riser, en[1]), (riser, 70), (108 - ESP_ROOM, 70))
    wire(sh, (riser, 70), (riser, 67))
    net_label(sh, 'ESP_EN', (riser, 67), 0, is_global=True)
    vres(sh, '10k', 124 - ESP_ROOM, 64)
    rail_symbol(sh, '+3V3', (124 - ESP_ROOM, 64))
    vcap(sh, '1uF', 116 - ESP_ROOM, 70)
    drop_ground(sh, (116 - ESP_ROOM, 76), 0)
    sw_reset = sh.add(
        'Switch:SW_Push',
        next_ref('SW'),
        'RESET',
        (108 - ESP_ROOM) * 1.27,
        74 * 1.27,
        rot=270,
        auto=False,
        footprint='cryocooler:SW_Panasonic_EVP-AA',
    )
    wire(sh, (108 - ESP_ROOM, 70), pin_cell(sw_reset, '1'))
    ground(sh, pin_cell(sw_reset, '2'))
    # BOOT (GPIO0)
    boot = pin_cell(esp, '27')
    wire(sh, boot, (108 - ESP_ROOM, boot[1]))
    wire(sh, (108 - ESP_ROOM, boot[1]), (104 - ESP_ROOM, boot[1]))
    net_label(sh, 'ESP_BOOT', (104 - ESP_ROOM, boot[1]), 180, is_global=True)
    vres(sh, '10k', 126 - ESP_ROOM, boot[1] - 6)
    rail_symbol(sh, '+3V3', (126 - ESP_ROOM, boot[1] - 6))
    vcap(sh, '100nF', 116 - ESP_ROOM, boot[1])
    drop_ground(sh, (116 - ESP_ROOM, boot[1] + 6), 0)
    sw_boot = sh.add(
        'Switch:SW_Push',
        next_ref('SW'),
        'BOOT',
        (108 - ESP_ROOM) * 1.27,
        (boot[1] + 4) * 1.27,
        rot=270,
        auto=False,
        footprint='cryocooler:SW_Panasonic_EVP-AA',
    )
    wire(sh, (108 - ESP_ROOM, boot[1]), pin_cell(sw_boot, '1'))
    ground(sh, pin_cell(sw_boot, '2'))
    # USB-C: VBUS can power the logic rail on its own (rails_logic sheet)
    usb_marks = sheet_marks(sh)
    sh.note('USB-C PORT AND ESD PROTECTION', 196 * 1.27, 62 * 1.27, 1.8)
    esd = sh.add(
        'cryocooler:SRL05P7',
        next_ref('U'),
        'SRL05P7',
        200 * 1.27,
        92 * 1.27,
        auto=False,
        footprint='cryocooler:MCC_DFN1510-6_1.5x1.0mm_P0.5mm',
    )
    usb = sh.add(
        'Connector:USB_C_Receptacle_USB2.0_16P',
        next_ref('J'),
        'USB_C',
        240 * 1.27,
        92 * 1.27,
        mirror=True,
        auto=False,
        footprint=USB_C_FLAG,
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
    drop_ground(sh, gnd_esd, 4)
    # VBUS: connector, 4.7 uF cap and the ESD clamp share one wire
    vbus_esd = pin_cell(esd, '5')
    vbus = pin_cell(usb, 'A4')
    wire(sh, vbus_esd, (vbus_esd[0], 72), (226, 72), (226, vbus[1]), vbus)
    # the flag sits left of the clamp's riser, clear of the wire
    label_end = (vbus_esd[0] - 3, 72)
    wire(sh, (vbus_esd[0], 72), label_end)
    net_label(sh, 'USB_VBUS', label_end, 180, is_global=True)
    # the VBUS capacitor and both CC pull-downs return on one ground bar. CC1
    # steps up five rows before its pull-down, so neither line runs beside the
    # other's resistor (pin 1 of each on the bar, as the board has it)
    vcap(sh, '4.7uF', 214, 72, fp=C0805)
    rail_flag(sh, (220, 72))
    cc1, cc2 = pin_cell(usb, 'A5'), pin_cell(usb, 'B5')
    wire(sh, (214, 78), (214, cc2[1]))
    for cc, row in ((cc1, cc1[1] - 5), (cc2, cc2[1])):
        hres(sh, '5.1k', 220, row, small=True)
        wire(sh, (214, row), (218, row))
        wire(sh, (222, row), (224, row), (224, cc[1]), cc)
    drop_ground(sh, (214, cc2[1]), 1)
    for pin in ('A8', 'B8'):
        sh.nc(usb, pin)
    ground(sh, spur(sh, usb, 'A1', 2))
    wire(
        sh,
        pin_cell(usb, 'SH'),
        (pin_cell(usb, 'SH')[0], pin_cell(usb, 'SH')[1] + 2),
    )
    ground(sh, (pin_cell(usb, 'SH')[0], pin_cell(usb, 'SH')[1] + 2))
    # the USB group is drawn around row 92; move it level with the module's
    # USB pins, so D- and D+ run straight into the clamp
    shift_since(
        sh, usb_marks, 0, pin_cell(esp, '13')[1] - pin_cell(esd, '4')[1]
    )
    wire(sh, pin_cell(esp, '13'), pin_cell(esd, '4'))
    wire(sh, pin_cell(esp, '14'), pin_cell(esd, '6'))


def build_power_input(sh):
    """Hand-laid: ATX 12 V header -> fuse -> VIN rail with TVS and bulk/bypass
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
        'Sized for 10 A (about 7.5 A continuous): fans and pump up to 4.2 A plus the I/O. '
        'F1 is a backup only: add an inline high-breaking-capacity fuse at the PSU end. '
        'Reverse polarity: the TVS forward-clamps and blows the fuse.',
        20,
        21,
    )
    # Molex Mini-Fit Jr 2 x 2, pinned like the ATX 12 V (CPU) connector: 1 and 2
    # ground, 3 and 4 +12 V. The 5.5 A barrel jack it replaces limited the board
    j_in = sh.add(
        'cryocooler:ATX12V_2x2',
        next_ref('J'),
        '12V IN (ATX 4-PIN)',
        24 * 1.27,
        62 * 1.27,
        rot=0,
        auto=False,
        footprint='Connector_Molex:Molex_Mini-Fit_Jr_5569-04A2_2x02_P4.20mm_Horizontal',
    )
    raw = pin_cell(j_in, '3')
    fuse = aux(
        sh,
        'Device:Fuse',
        'F',
        '10A backup',
        {},
        pose=at(46, raw[1], 90),
        fp='Fuse:Fuse_Littelfuse-NANO2-451_453',
    )
    wire(sh, raw, (raw[0] + 5, raw[1]), pin_cell(fuse, '1'))
    rail_flag(sh, (raw[0] + 5, raw[1]))
    gnd = spur(sh, j_in, '1', 2)
    wire(sh, gnd, (gnd[0], gnd[1] + 4), (gnd[0] + 5, gnd[1] + 4))
    ground(sh, (gnd[0], gnd[1] + 4))
    rail_flag(sh, (gnd[0] + 5, gnd[1] + 4))
    out = pin_cell(fuse, '2')
    wire(sh, out, (102, out[1]))
    rail_symbol(sh, 'VIN', (102, out[1]))
    # PWR_FLAG on a short stub above the rail (hand-placed in KiCad, b8e851e)
    wire(sh, (98, out[1] - 2), (98, out[1]))
    rail_flag(sh, (98, out[1] - 2))
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
    cap(sh, '100nF', '', '', pose=at(90, 63), fp=C0805)
    drop_ground(sh, (90, 66), 0)


def display_buttons(sh, column, row):
    """The off-board display's two open-collector outputs (DO0, DO1) act as the
    power button and the RESET button. Each line has 100 R in series and an ESD
    clamp on the cable side, left of (column, row); they reach the display
    connector through the DISP_PWR_BTN and DISP_RESET labels.
    """
    sh.note('POWER BUTTON AND RESET FROM THE DISPLAY', 20 * 1.27, (row - 30) * 1.27, 1.8)
    sh.note(
        'DO0 / DO1 on the Waveshare display are NPN open collectors to its ground '
        '(PC817 + transistor, 100 nF to GND): DO0 presses PWR_BTN like SW3, DO1 '
        'pulls ESP_EN low like the RESET button.',
        20 * 1.27,
        (row - 26) * 1.27,
        1.5,
    )
    press_row, reset_row = row, row - 20
    left = column - 60
    with kicadgen.pinned_refs('U', REV5_LAST['U'] + 3), kicadgen.pinned_refs(
        'R', REV5_LAST['R'] + 6
    ):
        clamp_refs = (next_ref('U'), next_ref('U'))
        for net, cable_net, line, tap, clamp_ref in (
            ('ESP_EN', 'DISP_RESET', reset_row, column - 46, clamp_refs[1]),
            ('PWR_BTN', 'DISP_PWR_BTN', press_row, column - 46, clamp_refs[0]),
        ):
            hres(sh, '100', left, line)
            wire(sh, (left - 3, line), (left - 16, line))
            net_label(sh, net, (left - 16, line), 180, is_global=True)
            wire(sh, (left + 3, line), (column - 28, line))
            net_label(sh, cable_net, (column - 28, line), 0)
            clamp = sh.add(
                'cryocooler:TPD1E05U06DPYR',
                clamp_ref,
                'TPD1E05U06DPYR',
                (tap + 6) * 1.27,
                (line + 7) * 1.27,
                auto=False,
                footprint='Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm',
            )
            wire(sh, (tap, line), pin_cell(clamp, '1'))
            drop_ground(sh, pin_cell(clamp, '2'), 2)


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
    sh.note('PUSH-BUTTON CONTROLLER', 20 * 1.27, 30 * 1.27, 1.8)
    sh.note('12 V LOAD SWITCH', 140 * 1.27, 54 * 1.27, 1.8)
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
    # push button, ONT left open
    pb = pin_cell(u, '3')
    wire(sh, pb, (40, pb[1]), (36, pb[1]))
    # global: the display's DO0 presses the same line from the Display sheet
    wire(sh, (40, pb[1]), (40, pb[1] - 3))
    net_label(sh, 'PWR_BTN', (40, pb[1] - 3), 180, is_global=True)
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
    # J7, the panel button header, was dropped in rev 4
    kicadgen.retire_refs('J', 1)
    # the button is pressed through the housing wall, so its line keeps the ESD clamp
    with rev3_refs('U'):
        clamp = place_ic(
            sh,
            'cryocooler:TPD1E05U06DPYR',
            'TPD1E05U06DPYR',
            46,
            76,
            'Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm',
        )
    wire(sh, (36, pb[1]), (36, pin_cell(clamp, '1')[1]), pin_cell(clamp, '1'))
    drop_ground(sh, pin_cell(clamp, '2'), 2)
    sh.nc(u, '2')
    # KILL#: 220k pull-up to the 5 V shunt reference above the node, 10k in
    # series from the MCU on the same line
    kill = pin_cell(u, '5')
    wire(sh, kill, (88, kill[1]))
    vres(sh, '220k', 88, 50)
    hres(sh, '10k', 93, 56)
    wire(sh, (88, 56), (90, 56))
    wire(sh, (96, 56), (100, 56))
    net_label(sh, 'PWR_KILL', (100, 56), 0, to_parent=True)
    wire(sh, (88, 50), (88, 44), (96, 44))
    vres(sh, '82k', 88, 38)
    rail_symbol(sh, 'VIN', (88, 38))
    ref = aux(
        sh,
        'Reference_Voltage:LM4040DBZ-5',
        'U',
        'LM4040DBZ-5',
        {},
        pose=at(96, 47, 90),
        fp=SOT23,
    )
    sh.nc(ref, '3')
    ground(sh, (96, 50))
    # PDT cap, EN# to the P-FET gate, INT# with pull-up and its own GPIO
    pdt = pin_cell(u, '6')
    wire(sh, pdt, (80, pdt[1]))
    vcap(sh, '1uF', 80, pdt[1])
    drop_ground(sh, (80, pdt[1] + 6), 0)
    en, intr = pin_cell(u, '7'), pin_cell(u, '8')
    wire(sh, en, (72, en[1]), (72, 70), (100, 70))
    wire(sh, intr, (70, intr[1]), (70, 88), (80, 88), (92, 88))
    # pull-up above the run (pin 1 on the net and pin 2 on the rail, as the
    # board has it)
    res(sh, '10k', '', '', pose=at(80, 85, 180))
    rail_symbol(sh, '+3V3', (80, 82))
    if keeps_test_point('LTC2954_INT'):
        wire(sh, (86, 88), (86, 92))
        test_point(sh, 'LTC2954_INT', (86, 92), rot=180)
    else:
        kicadgen.retire_refs('TP', 1)
    net_label(sh, 'PWR_INT', (92, 88), 0, to_parent=True)
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
    with rev3_refs('R', 'D', 'Q'):
        hres(sh, '13k', 47, 114)
        indicator = rg_led(
            sh, 'STATUS G=on R=standby', 112, 114, {'1': '', '4': ''}, labels=False
        )
        shunt = nfet(sh, 'BSS138', '', '', pose=at(62, 122))
    # red anode: VIN through 13k straight to the LED, the shunt FET hanging
    # below the line
    red_a, green_a = pin_cell(indicator, '4'), pin_cell(indicator, '1')
    rail_symbol(sh, 'VIN', (40, 114))
    wire(sh, (40, 114), (44, 114))
    drain = pin_cell(shunt, '3')
    wire(sh, (50, 114), (drain[0], 114), (red_a[0] - 2, red_a[1]))
    wire(sh, (drain[0], 114), drain)
    net_label(sh, 'STATUS_RA', (drain[0] + 4, 114), 0)
    green_k, red_k = spur(sh, indicator, '2', 2), spur(sh, indicator, '3', 2)
    wire(sh, green_k, red_k)
    drop_ground(sh, red_k, 2)
    # green anode: +5V through 2.2k above the red line, stepping down at the LED
    rail_symbol(sh, '+5V', (76, 104))
    wire(sh, (76, 104), (80, 104))
    with extra_refs('R'):
        hres(sh, '2.2k', 83, 104)
    step = green_a[0] - 6
    wire(sh, (86, 104), (step, 104), (step, green_a[1]), (green_a[0] - 2, green_a[1]))
    net_label(sh, 'STATUS_GA', (88, 104), 0)
    ground(sh, spur(sh, shunt, '2', 2))
    gate = pin_cell(shunt, '1')
    wire(sh, gate, (gate[0] - 4, gate[1]))
    rail_symbol(sh, '+3V3', (gate[0] - 4, gate[1]))
    auto_power_on(sh)


def auto_power_on(sh):
    """Optional: with the jumper fitted, 2.2 uF holds PB low while its internal
    pull-up charges it after 12 V arrives, which the LTC2954 takes as a button
    press. The diode empties the capacitor into VIN when the supply drops.
    """
    sh.note('AUTO POWER-ON (OPTIONAL, NOT BENCH TESTED)', 20 * 1.27, 140 * 1.27, 1.8)
    sh.note(
        'Fit the jumper to switch on as soon as 12 V arrives. PB then stays low for '
        'roughly 80-500 ms (2.2 uF on the 100k pull-up to 1.9 V), longer than the 32 ms '
        'turn-on debounce. Holding the button still forces power off.',
        20 * 1.27, 144 * 1.27, 1.5,
    )
    sh.note(
        'Assumed, not verified: the LTC2954 accepts PB low from power-up as a turn-on '
        '(its datasheet describes a high-to-low transition). Try it on a rev 4 board with '
        'a capacitor across SW3 first.',
        20 * 1.27, 147 * 1.27, 1.5,
    )
    with io_refs():
        net_label(sh, 'PWR_BTN', (30, 166), 180, is_global=True)
        jumper = sh.add(
            'Jumper:Jumper_2_Open', next_ref('JP'), 'AUTO ON', 40 * 1.27, 166 * 1.27,
            auto=False, footprint=SWITCH_HEADER,
        )
        jumper.dnp = True
        role(jumper, 'auto_on_jumper')
        wire(sh, (30, 166), pin_cell(jumper, '1'))
        wire(sh, pin_cell(jumper, '2'), (52, 166), (62, 166), (62, 163))
        role(vcap(sh, '2.2uF', 52, 166), 'auto_on_cap')
        drop_ground(sh, (52, 172), 2)
        discharge = sh.add(
            'Device:D', next_ref('D'), '1N4148W', 62 * 1.27, 160 * 1.27, rot=270, auto=False,
            footprint='Diode_SMD:D_SOD-123',
        )
        role(discharge, 'auto_on_diode')
        top = pin_cell(discharge, '1')
        wire(sh, top, (top[0], top[1] - 2))
        rail_symbol(sh, 'VIN', (top[0], top[1] - 2))


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


def retire_power_symbol():
    """Keeps the number and the id of a power symbol that a redraw removed, so
    every later sheet's file stays as it was.
    """
    kicadgen._pwr_counter[0] += 1
    kicadgen.new_uuid()


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


def vres(sh, value, column, top, fp=R0402, small=False):
    """Vertical resistor: pin 1 on (column, top), pin 2 six cells lower (four
    with the small symbol).
    """
    centre = top + (2 if small else 3)
    return res(sh, value, '', '', pose=at(column, centre), fp=fp, small=small)


def vcap(sh, value, column, top, fp=None, small=False):
    """Vertical capacitor with pin 1 on (column, top); pin 2 is six cells
    lower (four with the small symbol).
    """
    centre = top + (2 if small else 3)
    return cap(sh, value, '', '', pose=at(column, centre), fp=fp, small=small)


def hres(sh, value, column, row, fp=R0402, small=False):
    """Horizontal resistor centred on (column, row): pin 1 left, pin 2 right
    (three cells each side, two with the small symbol).
    """
    return res(sh, value, '', '', pose=at(column, row, 90), fp=fp, small=small)


def hcap(sh, value, column, row, fp=None, small=False):
    return cap(sh, value, '', '', pose=at(column, row, 90), fp=fp, small=small)


TP_PAD = 'TestPoint:TestPoint_Pad_D1.0mm'
TP_LOOP = 'TestPoint:TestPoint_Keystone_5015_Micro_Mini'


# Short test point names: the value is what the PCB silkscreen prints beside
# the pad, and JLCPCB's 1.0 mm minimum text height leaves room for about six
# characters on this board. Names not listed print as they are.
TP_NAMES = {
    'LTC2954_INT': 'PB_INT',
    'ADS1220_DRDY': 'DRDY',
    'EXPANDER_INT': 'EXPINT',
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
    symbol from the last pin (under an inner pin the bar, the pin and the drop
    would meet four ways).
    """
    ordered = sorted(cells)
    bar = max(cell[1] for cell in ordered) + length
    last = ordered[-1][0]
    for column, row in ordered:
        wire(sh, (column, row), (column, bar))
    wire(sh, (ordered[0][0], bar), (last, bar))
    wire(sh, (last, bar), (last, bar + 2))
    rail_symbol(sh, net, (last, bar + 2))


def net_label(sh, net, cell, angle=0, is_global=False, to_parent=False):
    """Net label whose connection point is the given cell (text extends away
    along angle). to_parent makes it a hierarchical label, which needs a pin
    on the sheet's block (SHEET_PINS).
    """
    kind = 'global_label' if is_global else 'label'
    if is_global and net in ROOT_LOCAL:
        # a net with a sheet pin is never global: a net label on the root or
        # the parent sheet that joins it, a hierarchical label on its sheets
        kind = 'label' if sh.filename in PARENT_FILES else 'hierarchical_label'
    if to_parent:
        kind = 'hierarchical_label'
    sh.labels.append((kind, net, (cell[0] * 1.27, cell[1] * 1.27), angle))


# The shared SPI bus as an unnamed group bus: its members keep their own net
# names (SPI_SCK, not SPI.SCK). SPI is a bus alias written to the project file.
SPI_BUS = '{SPI}'
# Bus aliases written to the project file. Buses are for communication buses
# only (SPI; I2C if one is added).
BUS_ALIASES = {
    'SPI': ['SPI_SCK', 'SPI_MOSI', 'SPI_MISO'],
}


def bus(sh, *cells):
    """Bus polyline through (column, row) cells."""
    for first, second in zip(cells, cells[1:]):
        sh.buses.append(
            (
                (first[0] * 1.27, first[1] * 1.27),
                (second[0] * 1.27, second[1] * 1.27),
            )
        )


def spi_bus(sh, taps, column, slant, tail, label_at=0):
    """SPI taps on a short {SPI} bus ending in one global {SPI} label."""
    bus_taps(sh, taps, column, slant, tail, SPI_BUS, label_at)


def bus_taps(sh, taps, column, slant, tail, name, label_at=0, to_parent=False):
    """Taps on a short bus at `column`.

    Each (start cell, net) gets a wire to two cells short of the bus, a local
    member label `label_at` cells along it (text toward the bus) and a
    45-degree entry; slant +1 runs the entries down to the bus, -1 up. The bus
    runs from the farthest entry through the `tail` cells and ends in one
    label `name`: global, or hierarchical with to_parent.
    """
    side = 1 if column > taps[0][0][0] else -1
    rows = []
    for start, net in taps:
        stub = (column - 2 * side, start[1])
        label = (start[0] + label_at * side, start[1])
        wire(sh, start, label, stub)
        net_label(sh, net, label, 0 if side == 1 else 180)
        sh.bus_entries.append(
            (stub[0] * 1.27, stub[1] * 1.27, 2 * side * 1.27, 2 * slant * 1.27)
        )
        rows.append(start[1] + 2 * slant)
    far = max(rows, key=lambda row: abs(row - tail[0][1]))
    bus(sh, (column, far), *tail)
    (x1, y1), (x2, y2) = tail[-2] if len(tail) > 1 else (column, far), tail[-1]
    angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[
        ((x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1))
    ]
    net_label(
        sh, name, tail[-1], angle, is_global=not to_parent, to_parent=to_parent
    )


def decoupling_block(sh, title, column, row, supply, values, ground='GND', pitch=12):
    """Standalone bank of decoupling caps: supply rail on top, ground bus
    below, one cap per value, `pitch` cells apart (wider for long values).

    Returns the width in cells (rail plus title, whichever is wider)."""
    caps = [column + 6 + pitch * index for index in range(len(values))]
    sh.note(title, column * 1.27, (row - 8) * 1.27, 1.8)
    wire(sh, (column, row), (caps[-1], row))
    wire(sh, (column, row + 6), (caps[-1], row + 6))
    rail_symbol(sh, supply, (column, row))
    rail_symbol(sh, ground, (column, row + 6))
    for x, value in zip(caps, values):
        vcap(sh, value, x, row, fp=C0805 if value == '10uF' else None)
    return max(caps[-1] - column, round(len(title) * 1.4)) + 6


def place_blocks(sh, blocks, column, row, max_column=240, row_pitch=22, pitch=12):
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
        width = max(pitch * len(values) + 6, round(len(title) * 1.4)) + 6
        if x + width > max_column:
            x, row = column, row + row_pitch
        decoupling_block(
            sh, title, x, row, supply, values, ground[0] if ground else 'GND', pitch
        )
        x += width


RAILS_MUX_ROW = 122  # centre row of the +5V / USB power mux
RAILS_3V3_ROW = 168  # row of the 3.3 V buck's input and output rail


def build_rails_logic(sh):
    """Hand-laid sheet, top to bottom in the order the power flows: the 5 V
    buck, the +5V / USB power mux, the 3.3 V buck the mux feeds.
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
    # 3.3 V buck, drawn below the power mux that feeds it: `rail` is its row
    rail = RAILS_3V3_ROW
    cap(sh, '22uF/10V', '', '', pose=at(72, rail + 3), fp=C1206)  # buck input, on +5V_OR
    rail_symbol(sh, 'GND', (72, rail + 6))
    rail_flag(sh, (154, 73))
    # VIN and EN on +5V_OR, then SW -> 0.47 uH -> +3V3
    u3 = place_ic(
        sh,
        'cryocooler:TPS62822DLCR',
        'TPS62822DLCR',
        87,
        rail + 4,
        'Package_SON:Texas_VSON-HR-8_1.5x2mm_P0.5mm',
    )
    wire(sh, (64, rail), (72, rail), (77, rail), (79, rail))
    rail_symbol(sh, '+5V_OR', (64, rail))
    wire(sh, pin_cell(u3, '1'), (77, pin_cell(u3, '1')[1]), (77, rail))
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
            pose=at(100, rail, 90),
            fp='cryocooler:L_Bourns_SRP4020TA',
        )
    wire(sh, pin_cell(u3, '6'), (97, rail))
    cap(sh, '22uF/10V', '', '', pose=at(112, rail + 3), fp=C1206)
    wire(
        sh, (103, rail), (112, rail), (126, rail), (140, rail), (152, rail),
        (162, rail), (168, rail),
    )
    rail_symbol(sh, '+3V3', (162, rail))
    rail_flag(sh, (168, rail))  # the inductor is passive, so nothing else drives the rail
    cap(sh, '100nF', '', '', pose=at(126, rail + 3))
    for column in (112, 126):
        rail_symbol(sh, 'GND', (column, rail + 6))
    # feed-forward cap, then the feedback divider; FB returns under the output
    # caps' grounds and meets the cap's lower end, so no point joins four ways
    with rev3_refs('R', 'C'):
        vres(sh, '453k', 152, rail)
        vres(sh, '100k', 152, rail + 6)
        vcap(sh, '120pF', 140, rail)
    drop_ground(sh, (152, rail + 12), 0)
    feedback = pin_cell(u3, '2')
    wire(
        sh, feedback, (97, feedback[1]), (97, rail + 12), (140, rail + 12),
        (140, rail + 6), (152, rail + 6),
    )
    sh.note('5 V BUCK (AP63205)', 44 * 1.27, 60 * 1.27, 1.8)
    sh.note('3.3 V BUCK (TPS62822)', 44 * 1.27, (rail - 12) * 1.27, 1.8)
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
        (RAILS_MUX_ROW - 20) * 1.27,
    )
    sh.note('+5V / USB POWER MUX (TPS2116)', 44 * 1.27, (RAILS_MUX_ROW - 12) * 1.27, 1.8)
    usb_row = RAILS_MUX_ROW + 16
    with kicadgen.pinned_refs('U', 27):
        mux = place_ic(
            sh,
            'cryocooler:TPS2116DRLR',
            'TPS2116DRLR',
            100,
            RAILS_MUX_ROW,
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
    wire(
        sh, usb_in, (84, usb_in[1]), (84, usb_row), (68, usb_row), (60, usb_row),
        (52, usb_row),
    )
    net_label(sh, 'USB_VBUS', (52, usb_row), 180, is_global=True)
    with kicadgen.pinned_refs('C', 125):
        vcap(sh, '1uF', 60, usb_row)
    drop_ground(sh, (60, usb_row + 6), 0)
    with kicadgen.pinned_refs('TP', 42):
        if keeps_test_point('USB_VBUS'):
            test_point(sh, 'USB_VBUS', (68, usb_row), rot=0)
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
    right, inverting channel lower right. The two linear regulators it feeds
    are on the Regulators +-15V sheet (build_ldo_15v).
    """
    sh.handwired = True
    sh.note('ADP5071 +-16.5 V CONVERTER', 56 * 1.27, 62 * 1.27, 1.8)
    sh.note(
        'ADP5071ACPZ (5 V in): +16.4 V boost and -16.5 V inverting rails for the two '
        'post-regulators on the Regulators +-15V sheet.',
        20,
        15,
    )
    sh.note(
        'ADP5071 values from datasheet Fig. 47 / Tables 9-11.',
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
    # +5V input: bus left of the IC down to the lowest of the five pins on it,
    # rail above it, three decoupling caps
    rows = {name: pin_cell(u, pin)[1] for name, pin in (
        ('en2', '9'), ('comp1', '6'), ('comp2', '10'), ('vreg', '14'), ('seq', '3'),
        ('inbk', '1'), ('sw1', '20'), ('fb1', '5'), ('sw2', '18'), ('fb2', '11'), ('vref', '12'),
    )}
    wire(sh, (96, 70), (96, rows['en2']))
    rail_symbol(sh, '+5V_PS15', (96, 70))
    for pin in ('7', '15', '17', '16', '9'):
        spur(sh, u, pin, 2)
    place_blocks(
        sh,
        [('ADP5071 DECOUPLING CAPACITORS', '+5V_PS15', ('10uF', '10uF', '100nF'))],
        190,
        150,
    )
    # COMP1 network, below the input rail's end: 5.6k then 47nF to ground
    row = rows['comp1']
    wire(sh, pin_cell(u, '6'), (93, row))
    hres(sh, '5.6k', 90, row)
    wire(sh, (87, row), (84, row))
    vcap(sh, '47nF', 84, row)
    drop_ground(sh, (84, row + 6), 0)
    # VREG: pin 14 and SEQ (pin 3) joined on one wire with its 1 uF cap
    row = rows['vreg']
    wire(sh, pin_cell(u, '14'), (88, row), (84, row))
    wire(sh, pin_cell(u, '3'), (88, rows['seq']), (88, row))
    vcap(sh, '1uF', 84, row)
    drop_ground(sh, (84, row + 6), 0)
    # COMP2 network, further out than COMP1's: 12k then 68nF to ground
    row = rows['comp2']
    wire(sh, pin_cell(u, '10'), (81, row))
    hres(sh, '12k', 78, row)
    wire(sh, (75, row), (72, row))
    vcap(sh, '68nF', 72, row)
    drop_ground(sh, (72, row + 6), 0)
    # SS not connected; SYNC, SLEW and the grounds share one bar along the bottom
    sh.nc(u, '8')
    gnd_bus(
        sh, [pin_cell(u, number) for number in ('2', '4', '13', '21', '19')]
    )
    # boost channel
    row = rows['sw1']
    aux(
        sh,
        'Device:L',
        'L',
        'SRP7050TA-3R3M',
        {},
        pose=at(128, rows['inbk'], 90),
        fp=INDUCTOR,
    )
    wire(sh, pin_cell(u, '1'), (125, rows['inbk']))
    wire(sh, pin_cell(u, '20'), (131, row), (131, rows['inbk']))
    wire(sh, (131, row), (135, row))
    diode(
        sh,
        'Device:D_Schottky',
        'DFLS240',
        '',
        '',
        'Diode_SMD:D_PowerDI-123',
        pose=at(138, row, 180),
    )
    wire(sh, (141, row), (150, row), (166, row), (176, row), (182, row))
    rail_symbol(sh, '+16V5', (176, row))
    rail_flag(sh, (182, row))
    vres(sh, '2.67M', 150, row)
    vres(sh, '137k', 150, row + 6)
    drop_ground(sh, (150, row + 12), 0)
    wire(sh, (150, row + 6), (124, row + 6), (124, rows['fb1']), pin_cell(u, '5'))
    vcap(sh, RAIL_CAP, 166, row, fp=C1210)
    drop_ground(sh, (166, row + 6), 0)
    # inverting channel: switch node, feedback tap and the reference the
    # divider stands on, each one row lower and one riser further in
    row = rows['sw2']
    aux(
        sh,
        'Device:L',
        'L',
        'SRP7050TA-6R8M',
        {},
        pose=at(131, row + 3),
        fp=INDUCTOR,
    )
    drop_ground(sh, (131, row + 6), 0)
    wire(sh, pin_cell(u, '18'), (131, row), (135, row))
    diode(
        sh,
        'Device:D_Schottky',
        'DFLS240',
        '',
        '',
        'Diode_SMD:D_PowerDI-123',
        pose=at(138, row),
    )
    wire(sh, (141, row), (150, row), (166, row), (186, row), (196, row), (202, row))
    rail_symbol(sh, '-16V5', (196, row))
    rail_flag(sh, (202, row))
    wire(sh, (150, row), (150, row + 6))
    vres(sh, '2.55M', 150, row + 6)
    vres(sh, '118k', 150, row + 12)
    vcap(sh, RAIL_CAP, 166, row, fp=C1210)
    drop_ground(sh, (166, row + 6), 0)
    with kicadgen.pinned_refs('C', 130):
        vcap(sh, RAIL_CAP, 186, row, fp=C1210)
    drop_ground(sh, (186, row + 6), 0)
    wire(sh, pin_cell(u, '11'), (126, rows['fb2']), (126, row + 12), (150, row + 12))
    wire(sh, pin_cell(u, '12'), (124, rows['vref']), (124, row + 18), (130, row + 18),
         (150, row + 18))
    vcap(sh, '1uF', 130, row + 18)
    drop_ground(sh, (130, row + 24), 0)
    # the rev 2 stage used two more capacitors than this one
    kicadgen.retire_refs('C', 2)


def build_ldo_15v(sh):
    """Hand-laid: the two post-regulators. Split off the Rails +-15V sheet, which
    was over 30 parts; built straight after it so the parts keep their numbers.

    LT3045 (+15 V) on top and LT3094 (-15 V) below: the two halves of the LT3097
    they replace, with the same external parts. Inputs on the left, feedback and
    power-good parts on the right. The LT3094 takes the number the ADP7182 had.
    """
    sh.handwired = True
    sh.note(
        'LT3045 (+15 V) and LT3094 (-15 V) post-regulate the ADP5071 rails (+16.4 V / '
        '-16.5 V, Rails +-15V sheet) to +/-14.7 V: VOUT = 100 uA x RSET (147k; +15 V is '
        'the top of the LT3045 range).',
        20, 15,
    )
    sh.note(
        'PGFB dividers 432k/10k trip power good near 13.3 V (also enables fast '
        'start-up). Each open-collector PG pin goes to its node on the Power Good sheet.',
        20, 21,
    )
    sh.note('+15 V REGULATOR', 44 * 1.27, 30 * 1.27, 1.8)
    sh.note('-15 V REGULATOR', 44 * 1.27, 70 * 1.27, 1.8)
    marks = sheet_marks(sh)
    positive = place_ic(
        sh,
        'cryocooler:LT3045DD',
        'LT3045EDD',
        84,
        156,
        'Package_DFN_QFN:DFN-10-1EP_3x3mm_P0.5mm_EP1.65x2.38mm',
    )
    negative = place_ic(
        sh,
        'cryocooler:LT3094DD',
        'LT3094HDD',
        84,
        198,
        'Package_DFN_QFN:DFN-12-1EP_3x3mm_P0.45mm_EP1.65x2.38mm',
    )
    sh.nc(negative, '7')
    for reg, rail, input_pin, enable_pin, limit_pin, ground_pin in (
        (positive, '+16V5', '1', '3', '5', '8'),
        (negative, '-16V5', '1', '3', '6', '9'),
    ):
        vin, enable = pin_cell(reg, input_pin), pin_cell(reg, enable_pin)
        wire(sh, vin, (vin[0] - 14, vin[1]))
        rail_symbol(sh, rail, (vin[0] - 14, vin[1]))
        # EN/UV tied to the input: on whenever the rail is up
        wire(sh, enable, (enable[0] - 2, enable[1]), (enable[0] - 2, vin[1]))
        # ground and the unused current-limit pin share one bar
        gnd_bus(sh, [pin_cell(reg, limit_pin), pin_cell(reg, ground_pin)])
    channels = (
        # regulator, output, sense, PGFB, PG, SET pin, rail net, power-good node
        (positive, '10', '9', '6', '4', '7', '+15V', 'PGP_15V'),
        (negative, '11', '10', '5', '4', '8', '-15V', 'PGN_15V'),
    )
    for index, channel in enumerate(channels):
        reg, out, sense, feedback, good, setpoint, rail, good_net = channel
        o, s = pin_cell(reg, out), pin_cell(reg, sense)
        # output rail: Kelvin sense joins the output wire, 2 x 22 uF at the end
        rail_symbol(sh, rail, (o[0] + 66, o[1]))
        wire(sh, s, (s[0] + 4, s[1]), (s[0] + 4, o[1]))
        wire(sh, o, (o[0] + 66, o[1]))
        vcap(sh, RAIL_CAP, o[0] + 50, o[1], fp=C1210)
        drop_ground(sh, (o[0] + 50, o[1] + 6), 0)
        with kicadgen.pinned_refs('C', 128 + index):
            vcap(sh, RAIL_CAP, o[0] + 30, o[1], fp=C1210)
        drop_ground(sh, (o[0] + 30, o[1] + 6), 0)
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
    # drawn where it stood under the ADP5071; move it up the page
    shift_since(sh, marks, 0, -112)


# Power Good sheet: rows of the two node lines and the columns along them. The
# -15 V line is the upper one, so it reaches the AND diode from above and the
# +15 V line from below, and PG_15V leaves to the right without a crossing.
PG_ROWS = {'PGN_15V': 66, 'PGP_15V': 160}
PG_ENTRY, PG_DIVIDER, PG_LED, PG_AND = 20, 44, 88, (176, 112)


def build_power_good(sh):
    """Hand-laid: one node line per regulator power-good pin, running left to
    right past its divider and its LED driver to the AND diode; PG_15V and the
    active-low flag for the ESP32 leave on the right; the -15 V guard hangs on
    the -15 V line.
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
    for net, heading in (('PGN_15V', '-15 V GOOD: NODE AND LED'), ('PGP_15V', '+15 V GOOD: NODE AND LED')):
        sh.note(heading, PG_DIVIDER * 1.27, (PG_ROWS[net] - 40) * 1.27, 1.8)
    sh.note('BOTH GOOD (AND)', (PG_AND[0] - 24) * 1.27, (PG_AND[1] - 10) * 1.27, 1.8)
    sh.note('ACTIVE-LOW FLAG TO THE ESP32', (PG_AND[0] + 30) * 1.27, (PG_AND[1] - 18) * 1.27, 1.8)
    for net in ('PGP_15V', 'PGN_15V'):
        power_good_node(sh, PG_DIVIDER, PG_ROWS[net])
    NEW_REFS['R'] += 4  # the removed +-16.5 V power good dividers
    output = power_good_and(sh)
    power_good_flag(sh, output)
    power_good_led(sh, 'PGP_15V', 'PG +15V G=good R=bad')
    power_good_led(sh, 'PGN_15V', 'PG -15V G=good R=bad')
    power_good_guard(sh, 16, PG_ROWS['PGN_15V'] + 10)


def power_good_guard(sh, column, row):
    """An unpowered LT3094 can't pull PGN low, so PGN_15V would
    read good with -15 V missing. The midpoint of two 470k resistors between the
    rails sits near 0 V when both are up and about +7.5 V when -15 V is gone, which
    turns a BSS138W on and pulls the node line above it low.
    """
    for index, text in enumerate((
        '-15 V GUARD: an unpowered LT3094 cannot pull PGN low.',
        'Midpoint near 0 V with both rails up, about +7.5 V with -15 V missing.',
    )):
        sh.note(text, (column - 2) * 1.27, (row + 22 + 4 * index) * 1.27, 1.8)
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
    wire(sh, drain, (drain[0], PG_ROWS['PGN_15V']))


def power_good_node(sh, column, row, rail='+15V', values=('220k', '62k')):
    """Divider on the node line at `row`: the upper resistor from the rail down
    to the line, the lower one from the line to ground six cells further on,
    so each meets the line in a T.
    """
    rail_symbol(sh, rail, (column, row - 6))
    with high_refs('R'):
        vres(sh, values[0], column, row - 6, fp=R0402)
        vres(sh, values[1], column + 6, row, fp=R0402)
    drop_ground(sh, (column + 6, row + 6), 0)


def power_good_and(sh):
    """BAT54AW (two Schottky diodes, common anode on PG_15V, cathodes on
    PGP_15V / PGN_15V) with a 470k pull-up to +3V3: PG_15V is high only while
    both nodes are. A stiffer pull-up lifts the dead nodes through their 62k
    dividers and turns the BSS138s on with no rail present. Each node line ends
    on its cathode; returns the cell where PG_15V leaves.
    """
    column, row = PG_AND
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
    for net, cathode, side in (('PGP_15V', k1, -1), ('PGN_15V', k2, 1)):
        line, turn = PG_ROWS[net], cathode[0] + 6 * side
        wire(sh, (PG_ENTRY, line), (turn, line), (turn, cathode[1]), cathode)
        net_label(sh, net, (PG_ENTRY, line), 180, to_parent=True)
    node = (anode[0], anode[1] + 4)
    wire(sh, anode, node)
    # pull-up above the output line, right of the -15 V line's drop
    # (pin 1 on the net and pin 2 on the rail, as the board has it)
    with high_refs('R'):
        res(sh, '470k', '', '', pose=at(node[0] + 24, node[1] - 3, 180), fp=R0402)
    rail_symbol(sh, '+3V3', (node[0] + 24, node[1] - 6))
    # PG_15V leaves through its sheet pin from a tee ahead of the flag FET
    tee = (node[0] + 30, node[1])
    wire(sh, tee, (tee[0], tee[1] + 12), (tee[0] + 34, tee[1] + 12))
    net_label(sh, 'PG_15V', (tee[0] + 34, tee[1] + 12), 0, to_parent=True)
    return node


def power_good_flag(sh, node):
    """PG_15V gates a BSS138W whose drain, pulled up to +3V3 and through 1k,
    reads as PG_15V_N (low = both rails good) on the ESP32.
    """
    with high_refs('Q'):
        fet = nfet(sh, 'BSS138', '', '', pose=at(node[0] + 44, node[1]), fp=SOT323)
    gate, drain = pin_cell(fet, '1'), pin_cell(fet, '3')
    wire(sh, node, (gate[0], node[1]), gate)
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
    net_label(sh, 'PG_15V_N', (node[0] + 14, node[1]), 0, to_parent=True)


def power_good_led(sh, node_net, text):
    """A good node turns a BSS138W on and its drain lights the green die. A second
    BSS138W, gated by that drain (100k to +3V3), lights the red die when the node
    is low. Green 2.2k from +5V, red 1.5k from +3V3, about 1 mA each. Drawn above
    its node line: resistors, LED, then the red driver (mirrored, so its gate
    faces the green driver's drain line) and the green driver.
    """
    stem = node_net.split('_')[0]
    line = PG_ROWS[node_net]
    fets, led_row = line - 14, line - 28
    with high_refs('Q'):
        good = nfet(sh, 'BSS138', '', '', pose=at(PG_LED + 40, fets), fp=SOT323)
    with extra_refs('Q'):
        bad = nfet(sh, 'BSS138', '', '', pose=at(PG_LED + 24, fets), fp=SOT323, mirror=True)
    gate = pin_cell(good, '1')
    wire(sh, gate, (gate[0] - 2, gate[1]), (gate[0] - 2, line))
    for fet in (good, bad):
        spur(sh, fet, '2', 2)
        ground(sh, (pin_cell(fet, '2')[0], pin_cell(fet, '2')[1] + 2))
    green_k, red_k = f'{stem}_LED_GK', f'{stem}_LED_RK'
    green_drain, red_drain, red_gate = pin_cell(good, '3'), pin_cell(bad, '3'), pin_cell(bad, '1')
    with extra_refs('R'):
        vres(sh, '100k', green_drain[0], led_row - 8, fp=R0402)
    rail_symbol(sh, '+3V3', (green_drain[0], led_row - 8))
    for row, rail, ohms, die in (
        (led_row - 2, '+5V', '2.2k', 'GA'), (led_row + 8, '+3V3', '1.5k', 'RA'),
    ):
        rail_symbol(sh, rail, (PG_LED - 30, row))
        wire(sh, (PG_LED - 30, row), (PG_LED - 27, row))
        with high_refs('R') if die == 'GA' else extra_refs('R'):
            hres(sh, ohms, PG_LED - 24, row)
        net_label(sh, f'{stem}_LED_{die}', (PG_LED - 20, row), 0)
    with high_refs('D'):
        indicator = rg_led(sh, text, PG_LED, led_row, {'1': '', '2': '', '3': '', '4': ''}, labels=False)
    green_a, red_a = pin_cell(indicator, '1'), pin_cell(indicator, '4')
    wire(sh, (PG_LED - 21, led_row - 2), (green_a[0] - 2, green_a[1]))
    jog = red_a[0] - 4
    wire(sh, (PG_LED - 21, led_row + 8), (jog, led_row + 8), (jog, red_a[1]), (red_a[0] - 2, red_a[1]))
    # green cathode: over to the green driver's drain, with a drop to the red
    # driver's gate on the way
    start = (pin_cell(indicator, '2')[0] + 2, pin_cell(indicator, '2')[1])
    wire(sh, start, (green_drain[0], start[1]), green_drain)
    wire(sh, (red_gate[0] + 2, start[1]), (red_gate[0] + 2, red_gate[1]), red_gate)
    net_label(sh, green_k, (start[0] + 1, start[1]), 0)
    # red cathode: straight over and down to the red driver's drain
    start = (pin_cell(indicator, '3')[0] + 2, pin_cell(indicator, '3')[1])
    wire(sh, start, (red_drain[0], start[1]), red_drain)
    net_label(sh, red_k, (start[0] + 1, start[1]), 0)


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


# Cells everything right of the clock moves, so the AD9837's chip-select label
# fits between the clock and the SPI bus.
SIGNAL_GEN_SHIFT = 8


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
        'VREF and RFB are limited to +/-12 V but the op-amps run from +/-14.7 V, so R39 '
        'and a 9.1 V bidirectional clamp protect VREF (under 10.5 V; 56 mW in R39). '
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
    # strapped the same way as the UART clock on the Expansion sheet
    wire(sh, oe, (oe[0], oe[1] - 3), (vcc_osc[0], vcc_osc[1] - 3), vcc_osc)
    wire(sh, (vcc_osc[0], vcc_osc[1] - 3), (vcc_osc[0], vcc_osc[1] - 5))
    rail_symbol(sh, '+3V3_SG', (vcc_osc[0], vcc_osc[1] - 5))
    drop_ground(sh, pin_cell(osc, '2'), 2)
    sh.note('CLOCK', 14 * 1.27, 48 * 1.27, 1.8)
    # everything after the clock is drawn, then moved right to make room for
    # the chip-select label between the clock and the SPI bus
    marks = sheet_marks(sh)
    # AD9837: the AD9833's pins and registers in a 3 x 3 mm LFCSP, 16 MHz max MCLK
    dds = place_ic(
        sh,
        'cryocooler:AD9837BCPZ',
        'AD9837BCPZ',
        60,
        60,
        'Package_CSP:LFCSP-WD-10-1EP_3x3mm_P0.5mm_EP1.64x2.38mm',
    )
    sh.note('AD9837 SINE SOURCE', 34 * 1.27, 25 * 1.27, 1.8)
    fsync = pin_cell(dds, '8')
    wire(sh, fsync, (38, fsync[1]))
    net_label(sh, 'AD9833_FSYNC', (38, fsync[1]), 180, to_parent=True)
    spi_bus(
        sh,
        [(spur(sh, dds, pin, 2), net) for pin, net in (('7', 'SPI_SCK'), ('6', 'SPI_MOSI'))],
        35,
        -1,
        [(35, 44), (39, 44)],
    )
    for pin in ('4', '9', '11'):  # DGND, AGND, exposed pad
        spur(sh, dds, pin, 2)
    # the drop is under the last pin, so no point meets four ways
    wire(sh, (58, 72), (62, 72))
    drop_ground(sh, (62, 72), 2)
    vdd = pin_cell(dds, '2')
    wire(sh, vdd, (vdd[0], 48), (75, 48))
    rail_symbol(sh, '+3V3_SG', (vdd[0], 48))
    comp = pin_cell(dds, '1')
    wire(sh, comp, (75, comp[1]), (75, 54))
    vcap(sh, '10nF', 75, 48)
    cap_pin = pin_cell(dds, '3')
    # the capacitor sits high, so its ground clears U4's name; the flag is on
    # the run beside it, away from the VDD rail's name
    wire(sh, cap_pin, (cap_pin[0], 30), (50, 30))
    vcap(sh, '100nF', 50, 30)
    drop_ground(sh, (50, 36), 0)
    rail_flag(sh, (54, 30))
    # AC coupling into the buffer; the raw DDS output is named for its
    # debug test point
    wire(sh, pin_cell(dds, '10'), (74, 62))
    wire(sh, (74, 62), (74, 68), (78, 68))
    net_label(sh, 'DDS_SINE', (78, 68), 0, to_parent=True)
    wire(sh, (74, 62), (79, 62))
    hcap(sh, '1uF', 82, 62)
    opa_a = opamp_dual(sh, next_ref('U'), 110, 60, 1)
    positive_a = pin_cell(opa_a, '3')
    wire(sh, (85, 62), (92, 62), (92, positive_a[1]), positive_a)
    vres(sh, '100k', 89, 62)
    drop_ground(sh, (89, 68), 0)
    # U5A: non-inverting gain of 16.3 (1 + 50.6k/3.3k) sets about 10 Vpp at
    # full code through R39 and the 9k VREF input. The feedback is two series
    # resistors; the 3.6k sits on a 1206 / 3313J land, so a 5k trimmer can replace
    # it (gain 15.2-16.8). 1 nF across both rolls off above ~3 kHz.
    wire(sh, pin_cell(opa_a, '2'), (100, 62), (100, 76))
    hres(sh, '47k', 107, 76)
    with kicadgen.pinned_refs('R', 169):
        hres(sh, '3.6k', 113, 76, fp=R_TRIM)
    # the 1 nF bridges both, below them and clear of the 3.3k
    with high_refs('C'):
        hcap(sh, '1nF/C0G', 110, 80)
    wire(sh, (104, 76), (104, 80), (107, 80))
    wire(sh, (116, 76), (116, 80), (113, 80))
    wire(sh, (104, 76), (100, 76))
    vres(sh, '3.3k', 100, 76)
    drop_ground(sh, (100, 82), 0)
    wire(sh, pin_cell(opa_a, '1'), (120, 60), (120, 76), (116, 76))
    wire(sh, (120, 60), (122, 60), (124, 60))
    hres(sh, '220', 127, 60)
    if keeps_test_point('U5_OUT'):
        wire(sh, (122, 60), (122, 56))
        with kicadgen.pinned_refs('TP', 46):
            test_point(sh, 'U5_OUT', (122, 56), rot=0)
    # U5 supply unit: V+ to +15V, V- and the thermal pad (datasheet: to V-) to -15V
    power = opamp_dual(sh, opa_a.ref, 160, 94, 3)
    top, bottom, pad = pin_cell(power, '8'), pin_cell(power, '4'), pin_cell(power, '9')
    wire(sh, top, (top[0], top[1] - 4))
    rail_symbol(sh, '+15V', (top[0], top[1] - 4))
    wire(sh, bottom, (bottom[0], bottom[1] + 4), (bottom[0] + 6, bottom[1] + 4))
    wire(sh, pad, (pad[0], pad[1] + 4))
    rail_symbol(sh, '-15V', (bottom[0] + 6, bottom[1] + 4))
    # V- and the pad had a symbol each
    retire_power_symbol()
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
    sync = pin_cell(mdac, '5')
    wire(sh, sync, (160, sync[1]))
    net_label(sh, 'AD5453_SYNC', (160, sync[1]), 180, to_parent=True)
    spi_bus(
        sh,
        [(spur(sh, mdac, pin, 2), net) for pin, net in (('3', 'SPI_SCK'), ('4', 'SPI_MOSI'))],
        165,
        1,
        [(165, 70), (169, 70)],
    )
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
    # C1 sits clear of the RFB wire that drops beside it
    wire(sh, iout, (208, iout[1]), inverting)
    with rev3_refs('C'):
        vcap(sh, '22pF/C0G', 208, iout[1])
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
    wire(sh, (208, iout[1] + 6), (208, 72), (feedback_x, 72))
    wire(sh, (feedback_x, 72), (feedback_x, out[1]))
    resistor_x = feedback_x + 8
    wire(sh, out, (feedback_x, out[1]), (resistor_x - 3, out[1]))
    hres(sh, '100', resistor_x, out[1])
    wire(sh, (resistor_x + 3, out[1]), (resistor_x + 9, out[1]))
    hcap(sh, '10uF', resistor_x + 12, out[1])
    wire(
        sh,
        (resistor_x + 15, out[1]),
        (resistor_x + 19, out[1]),
        (resistor_x + 25, out[1]),
    )
    net_label(sh, 'SIG_SINE', (resistor_x + 25, out[1]), 0, to_parent=True)
    vres(sh, '100k', resistor_x + 19, out[1])
    drop_ground(sh, (resistor_x + 19, out[1] + 6), 0)
    kicadgen.retire_refs('R', 3)  # R58, R59 and R3 went with the amplitude DAC
    kicadgen.retire_refs('C', 1)  # C9 likewise
    for text, column, row in (
        ('GAIN STAGE', 98, 46),
        ('VREF CLAMP', 134, 56),
        ('AMPLITUDE DAC', 174, 44),
        ('OUTPUT STAGE', 216, 46),
        ('U5 SUPPLY', 142, 92),
    ):
        sh.note(text, column * 1.27, row * 1.27, 1.8)
    shift_since(sh, marks, SIGNAL_GEN_SHIFT, 0)
    wire(sh, pin_cell(osc, '3'), pin_cell(dds, '5'))
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
        124,
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
    output stays off unless that net is high. The enable net comes in through
    a sheet pin.
    """
    net_label(sh, enable_net, (24, 60), 180, to_parent=True)
    wire(sh, (24, 60), (28, 60))
    hres(sh, '1k', 31, 60)
    wire(sh, (34, 60), (46, 60))
    vres(sh, '100k', 40, 60)
    drop_ground(sh, (40, 66), 0)
    q_n = nfet(sh, 'BSS138', '', '', pose=at(50, 60))
    if interlock_net:
        # series interlock FET (Q21) below the level shifter: its drain takes
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
    # the supply symbol lines up with the pull-up's at row 44
    wire(sh, top, (top[0], 44))
    rail_symbol(sh, rail, (top[0], 44))
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
    net_label(sh, f'{bus_net}_LED', (100, 48), 0)
    rg_led(
        sh,
        f'{bus_net} G=on R=off',
        134,
        48,
        {'1': bus_net, '3': bus_net, '2': f'{bus_net}_LED', '4': f'{bus_net}_LED'},
        labels=False,
        antiparallel=True,
    )
    # LED net: along row 48 to the green cathode, with a tee up to the red anode
    wire(sh, (96, 48), (126, 48))
    wire(sh, (122, 48), (122, 46), (126, 46))
    # output bus: green anode and red cathode joined on the right, then down
    # and back to the bus
    wire(sh, (142, 46), (146, 46), (146, 48), (142, 48))
    wire(sh, (146, 48), (146, 54), (128, 54), (128, 58))
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
            118 * 1.27,
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
        'switch), but only while PG_15V is high (both +-15 V rails good: Q21 '
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
    sh.note('REM HIGH-SIDE SWITCH', 24 * 1.27, 30 * 1.27, 1.8)
    sh.note('REM STATE LED', 94 * 1.27, 30 * 1.27, 1.8)
    sh.note('AMPLIFIER SIGNAL OUTPUT', 126 * 1.27, 74 * 1.27, 1.8)
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
    net_label(sh, 'SIG_SINE', (sig[0] - 6, sig[1]), 180, to_parent=True)
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
    sh.note('RELAY HIGH-SIDE SWITCH', 24 * 1.27, 30 * 1.27, 1.8)
    sh.note('RELAY STATE LED', 94 * 1.27, 30 * 1.27, 1.8)
    rem_switch(
        sh,
        'COMP_RELAY_EN',
        'COMP_RELAY',
        'COMPRESSOR RELAY / GND',
        True,
        X2510_2P,
        '+12V',
    )


# Cells the isolated side of the Amp Current sheet moves right, and the column
# where the gated clock turns up toward the isolator.
AMP_CURRENT_SHIFT = 52
ACS_SCK_TURN = 72


def build_amp_current(sh):
    """Hand-laid: isolator with its integrated supply on the left, ACS37800 and
    divider to the right.
    """
    sh.handwired = True
    sh.note(
        'Amplifier output V/I monitor: ACS37800 (SPI, 15 mA max) on an isolated 5 V domain '
        'from the ISOW7841A (SEL on VISO selects 5 V). It runs from +3V3_ISO because its one '
        'supply pin also sets the logic thresholds; 3.3 V in gives 40 mA at 5 V out.',
        20,
        15,
    )
    sh.note(
        'Mains-class creepage/clearance applies between ISO_GND domain and '
        'the logic side on the PCB. No F suffix: the isolated outputs go high (CS '
        'inactive, SCK idle) if the logic side loses power.',
        20,
        21,
    )
    sh.note(
        'The ACS37800 and the isolator drive MISO all the time, so MISO reaches the shared bus '
        'only while ACS_CS is low. SCK is gated the same way, so bus traffic for other '
        'devices never clocks the ACS37800.',
        20,
        27,
    )
    sh.note('ACS_CS comes from the CS decoder, which holds it high at reset.', 20, 33)
    # the isolated side is drawn first, then moved right of the SPI gates
    marks = sheet_marks(sh)
    # the isolator sits so its outputs line up with the ACS37800 pins they drive
    iso_row = 62 + pin_offset('cryocooler:ACS37800KMACTR-015B5-SPI', '10')[1] - pin_offset(
        'cryocooler:ISOW7841A', '14')[1]
    iso = place_ic(
        sh,
        'cryocooler:ISOW7841A',
        'ISOW7841AQDWERQ1',
        60,
        iso_row,
        'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
    )
    # logic-side SPI: MOSI straight from the shared bus; SCK and MISO pass through
    # the gates drawn by acs_bus_gates
    sh.nc(iso, '7')
    # the removed logic pull-ups, DC-DC module, its capacitors and enable resistor
    kicadgen.retire_refs('R', 3)
    kicadgen.retire_refs('PS', 1)
    kicadgen.retire_refs('C', 2)
    kicadgen.retire_refs('R', 1)
    kicadgen.retire_refs('C', 2)
    # the ISOW7741 EN/FLT pull-up and its two ferrite beads keep their numbers free
    with rev3_refs('R'):
        kicadgen.retire_refs('R', 1)
    with rev3_refs('FB'):
        kicadgen.retire_refs('FB', 2)
    # one supply: +3V3_ISO feeds the converter and sets the logic levels
    supply = pin_cell(iso, '1')
    wire(sh, supply, (supply[0], 40))
    rail_symbol(sh, '+3V3_ISO', (supply[0], 40))
    drop_ground(sh, pin_cell(iso, '2'), 2)
    # isolated output: SEL on VISO selects 5 V
    iso_out, select = pin_cell(iso, '16'), pin_cell(iso, '10')
    wire(sh, iso_out, (iso_out[0], iso_out[1] - 3), (select[0], select[1] - 3), select)
    wire(sh, (iso_out[0], iso_out[1] - 3), (iso_out[0], 40))
    rail_symbol(sh, 'ISO_5V', (iso_out[0], 40))
    # ISO_5V is driven by VISO; the isolated ground has no power output pin, so
    # its flag sits on the isolator's own ground stub
    iso_return = pin_cell(iso, '9')
    wire(sh, iso_return, (iso_return[0], iso_return[1] + 4))
    rail_symbol(sh, 'ISO_GND', (iso_return[0], iso_return[1] + 4))
    wire(sh, (iso_return[0], iso_return[1] + 2), (iso_return[0] + 4, iso_return[1] + 2))
    retire_power_symbol()  # the flag had an ISO_GND symbol of its own
    rail_flag(sh, (iso_return[0] + 4, iso_return[1] + 2))
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
    # isolated SPI: the ACS37800 pins are ordered like the isolator outputs
    # (MOSI, SCK, CS, MISO) so each signal is a straight wire across
    for iso_pin, acs_pin in (
        ('14', '10'),
        ('13', '11'),
        ('12', '9'),
        ('11', '12'),
    ):
        wire(sh, pin_cell(iso, iso_pin), pin_cell(acs, acs_pin))
    gnd = pin_cell(acs, '14')
    wire(sh, gnd, (gnd[0], gnd[1] + 2))
    rail_symbol(sh, 'ISO_GND', (gnd[0], gnd[1] + 2))
    vcc = pin_cell(acs, '13')
    wire(sh, vcc, (vcc[0], vcc[1] - 4))
    rail_symbol(sh, 'ISO_5V', (vcc[0], vcc[1] - 4))
    vinn = spur(sh, acs, '15', 2)
    rail_symbol(sh, 'ISO_GND', vinn)
    # the divider hangs from the cooler line: four 1M down to the VINP tap,
    # the 4.02k from the tap to the isolated ground
    vinp = pin_cell(acs, '16')
    divider_top = vinp[1] - 24
    wire(sh, vinp, (150, vinp[1]))
    vres(sh, '4.02k', 138, vinp[1], fp=R0603)
    rail_symbol(sh, 'ISO_GND', (138, vinp[1] + 6))
    ip_minus, ip_plus = pin_cell(acs, '5'), pin_cell(acs, '1')
    wire(sh, ip_minus, (159, ip_minus[1]), (159, divider_top), (150, divider_top))
    wire(sh, (159, 58), (174, 58))
    # R64 stays the one on the tap: the chain is numbered from the bottom, each
    # with pin 1 down, as the board has it
    for index in range(4):
        centre = divider_top + (3 - index) * 6 + 3
        res(sh, '1M', '', '', pose=at(150, centre, 180), fp=R1206)
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
    wire(sh, ip_plus, (163, ip_plus[1]), (163, out_plus[1]), out_plus)
    drop_ground(sh, pin_cell(j_load, '3'), 1)
    # J12's longer spur keeps ISO_GND and its name clear of the GND symbol on pin 3
    for connector, length in ((j_out, 2), (j_load, 7)):
        rail_symbol(sh, 'ISO_GND', spur(sh, connector, '2', length))
    for text, column, row in (
        ('ISOLATOR AND 5 V SUPPLY', 46, 32),
        ('V / I MONITOR', 90, 42),
        ('VSENSE DIVIDER', 124, 30),
        ('AMPLIFIER AND COOLER TERMINALS', 166, 50),
    ):
        sh.note(text, column * 1.27, row * 1.27, 1.8)
    shift_since(sh, marks, AMP_CURRENT_SHIFT, 0)
    with rev3_refs('C'):
        place_blocks(
            sh,
            [
                # the ISOW7741 had ten capacitors on four pins: the six that are gone
                # keep their numbers free
                2,
                ('ISOW7841 VCC DECOUPLING CAPACITORS', '+3V3_ISO', ('22uF/10V', '100nF')),
                1,
                ('ISOW7841 VISO DECOUPLING CAPACITORS', 'ISO_5V', ('10uF', '100nF'), 'ISO_GND'),
                1,
                2,
            ],
            20,
            130,
            max_column=300,
            pitch=16,
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
    acs_bus_gates(sh, iso)


def acs_bus_gates(sh, iso):
    """Two SN74LVC1G125 gates that connect the ACS37800 to the shared SPI bus only
    while ACS_CS is low: one passes SCK to the isolator (pulled high when closed, the
    SPI mode 3 idle level), the other passes the isolator's MISO to the bus. They sit
    left of the isolator, in the order of its inputs, with ACS_CS on one spine.
    """
    mosi, clock_in, select, data_out = (pin_cell(iso, pin) for pin in '3456')
    top = mosi[1]
    clock_row, select_row, data_row = top + 20, top + 34, top + 50
    sh.note('SPI GATES (LOGIC SIDE)', 30 * 1.27, (top + 4) * 1.27, 1.8)
    buffer_fp = 'Package_SON:Texas_USON-6_1x1.45mm_P0.5mm_SMD'
    with rev4_refs('U', 'R', 'C'):
        clock_gate = place_ic(
            sh, 'cryocooler:SN74LVC1G125DRY', 'SN74LVC1G125DRYR', 50, clock_row, buffer_fp
        )
        data_gate = place_ic(
            sh,
            'cryocooler:SN74LVC1G125DRY',
            'SN74LVC1G125DRYR',
            50,
            data_row,
            buffer_fp,
            mirror=True,
        )
        for gate in (clock_gate, data_gate):
            sh.nc(gate, '5')
            supply = pin_cell(gate, '6')
            wire(sh, supply, (supply[0], supply[1] - 4))
            rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
            drop_ground(sh, pin_cell(gate, '3'), 2)
        # gated SCK to the isolator, pulled high while the gate is closed. The
        # net stays on this sheet; its one global label keeps the board name
        clock_out = pin_cell(clock_gate, '4')
        wire(
            sh, clock_out, (ACS_SCK_TURN, clock_out[1]),
            (ACS_SCK_TURN, clock_in[1]), clock_in,
        )
        name_tag(sh, 'ACS_SCK', (ACS_SCK_TURN, clock_out[1]), (ACS_SCK_TURN + 3, clock_out[1]))
        vres(sh, '10k', 64, clock_out[1] - 6)
        rail_symbol(sh, '+3V3', (64, clock_out[1] - 6))
        # ACS_CS: one spine between the gates and the isolator, a branch to each
        # enable pin
        spine = ACS_SCK_TURN + 16
        enable = pin_cell(clock_gate, '1')
        low = pin_cell(data_gate, '1')
        wire(sh, (36, select_row), (spine, select_row))
        net_label(sh, 'ACS_CS', (36, select_row), 180, to_parent=True)
        wire(sh, enable, (enable[0], select_row))
        wire(sh, select, (spine, select[1]), (spine, low[1] + 3), (low[0], low[1] + 3), low)
        # isolator MISO into the second gate, drawn right to left
        data_in = pin_cell(data_gate, '2')
        turn = spine + 6
        wire(sh, data_out, (turn, data_out[1]), (turn, data_in[1]), data_in)
        name_tag(sh, 'ACS_MISO', (turn, data_in[1]), (turn + 3, data_in[1]))
        spi_bus(
            sh,
            [
                (spur(sh, iso, '3', 2), 'SPI_MOSI'),
                (spur(sh, clock_gate, '2', 2), 'SPI_SCK'),
                (spur(sh, data_gate, '4', 2), 'SPI_MISO'),
            ],
            24,
            -1,
            [(24, top - 8), (20, top - 8)],
        )
        # the decoder drives ACS_CS push-pull (high while it is disabled), so the
        # pull-up it had on GPIO17 is gone; its number stays retired
        kicadgen.retire_refs('R', 1)
        place_blocks(
            sh,
            [('SN74LVC1G125 DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF'))],
            140,
            130,
            max_column=300,
        )


def build_system_current(sh):
    """Hand-laid: 10 mOhm 4-terminal shunt between VSW and +12V, its sense pins
    through the 49.9 ohm / 470 nF input filter into the INA239 (SPI).
    """
    sh.handwired = True
    sh.note(
        'INA239 monitors the switched 12 V rail: 10 mOhm 4-terminal shunt (1 W at 10 A), '
        'SPI mode 1 on the main bus (CS from the decoder), +/-163.84 mV range (16.4 A). ALERT '
        'drives its LED and MCP23S08 GP6.',
        20,
        15,
    )
    sh.note('12 V SHUNT', 40.64, 31.75, 1.8)
    sh.note('INA239 CURRENT MONITOR', 109.22, 55.88, 1.8)
    sh.note('ALERT LED', 162.56, 88.9, 1.8)
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
    left, right = shunt_x - 4, shunt_x + 4
    # 4-terminal shunt: the sense pins are nets of their own, so the board can only
    # pick the signal up at the shunt's own sense pads (rev 4 read 2.9x high through
    # shared 12 V copper)
    shunt = sh.add(
        'Device:R_Shunt_US', next_ref('R'), '10m', shunt_x * 1.27, shunt_row * 1.27, rot=270,
        auto=False, footprint='Resistor_SMD:R_Shunt_Vishay_WSK2512_6332Metric_T1.19mm',
    )
    sense_minus, sense_plus = pin_cell(shunt, '2'), pin_cell(shunt, '3')
    wire(sh, (left, shunt_row), (left - 6, shunt_row))
    rail_symbol(sh, 'VSW', (left - 6, shunt_row))
    # +12V rail to the right with its bulk and bypass caps
    wire(
        sh,
        (right, shunt_row),
        (right + 8, shunt_row),
        (right + 20, shunt_row),
        (right + 28, shunt_row),
    )
    rail_symbol(sh, '+12V', (right + 28, shunt_row))
    rail_flag(sh, (right + 4, shunt_row))
    vcap(sh, '100nF', right + 8, shunt_row, fp=C0805)
    drop_ground(sh, (right + 8, shunt_row + 6), 0)
    cap_pol(
        sh, '100uF/25V', '', '', pose=at(right + 20, shunt_row + 3), fp=CP_ELEC
    )
    drop_ground(sh, (right + 20, shunt_row + 6), 0)
    # kelvin taps from the shunt's sense pins through the filter. VBUS goes straight
    # to +12V: on the filtered IN- node its 12 uA dropped 0.6 mV in the 49.9 ohm
    filter_x = right + 7
    cap_x = filter_x + 8
    jog_x = cap_x + (tip_x - cap_x) // 2
    wire(sh, vbus, (tip_x - 5, row), (tip_x - 5, row - 6))
    rail_symbol(sh, '+12V', (tip_x - 5, row - 6))
    wire(sh, sense_minus, (sense_minus[0], row + 2), (filter_x - 3, row + 2))
    hres(sh, '49.9', filter_x, row + 2)
    wire(sh, (filter_x + 3, row + 2), (cap_x, row + 2), in_minus)
    wire(sh, sense_plus, (sense_plus[0], row + 8), (filter_x - 3, row + 8))
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
    net_label(sh, 'INA239_CS', spur(sh, ina, '1', 12), 0, to_parent=True)
    spi_bus(
        sh,
        [
            (spur(sh, ina, pin, 2), net)
            for pin, net in (('5', 'SPI_SCK'), ('2', 'SPI_MOSI'), ('4', 'SPI_MISO'))
        ],
        150,
        -1,
        [(150, 52), (154, 52)],
    )
    # the decoder drives CS push-pull; R68 stays retired
    kicadgen.retire_refs('R', 1)
    alert = spur(sh, ina, '3', 4)
    pull = (alert[0], alert[1] + 6)
    # pull-up above the line, right of the SPI flag (pin 1 on the net and pin 2
    # on the rail, as the board has it)
    res(sh, '10k', '', '', pose=at(alert[0] + 30, alert[1] - 3, 180))
    rail_symbol(sh, '+3V3', (alert[0] + 30, alert[1] - 6))
    # red LED: +3V3 -> 1.5k -> anode, cathode on the open-drain ALERT
    row = pull[1] + 8
    rail_symbol(sh, '+3V3', (pull[0] - 2, row))
    wire(sh, (pull[0] - 2, row), (pull[0], row))
    hres(sh, '1.5k', pull[0] + 3, row)
    indicator = chip_led(sh, 'ALERT (red)', pull[0] + 30, row)
    red_a, red_k = pin_cell(indicator, '2'), pin_cell(indicator, '1')
    wire(sh, (pull[0] + 6, row), red_a)
    net_label(sh, 'ALERT_LED_A', (pull[0] + 8, row), 0)
    # ALERT: past the pull-up, down to the cathode and out to its sheet pin
    turn = red_k[0] + 4
    wire(sh, alert, (turn, alert[1]), (turn + 8, alert[1]))
    wire(sh, (turn, alert[1]), (turn, red_k[1]), red_k)
    net_label(sh, 'INA239_ALERT', (turn + 8, alert[1]), 0, to_parent=True)
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
    """One test point on a net: a power symbol or sheet-pin label on top of a
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
        net_label(sh, net, (column, row), 180, to_parent=True)
    wire(sh, (column, row), (column, row + 3))
    test_point(sh, net, (column, row + 3), rot=180)


def debug_rail_led(sh, net, ohms, label, column, row, ground='GND'):
    """Rail -> resistor -> green LED -> ground, drawn left to right."""
    rail_symbol(sh, net, (column, row))
    wire(sh, (column, row), (column + 3, row))
    hres(sh, ohms, column + 6, row)
    wire(sh, (column + 9, row), (column + 11, row))
    indicator = chip_led(sh, label, column + 36, row)
    green_a = pin_cell(indicator, '2')
    wire(sh, (column + 11, row), green_a)
    net_label(sh, f'{net}_LED_A', (column + 11, row), 0)
    green_k = pin_cell(indicator, '1')
    wire(sh, green_k, (green_k[0] + 4, green_k[1]))
    rail_symbol(sh, ground, (green_k[0] + 4, green_k[1]))
    return indicator


def build_debug(sh):
    """Hand-laid: one test point per useful net (rails, grounds, fan
    and pump lines, control lines) and a power LED on each rail that has no
    indicator yet. Placement on the board follows the net's own pads.
    """
    sh.handwired = True
    sh.note(
        'Debug aids: test points (pad per net, loops for ground) and rail '
        'LEDs. Each test point sits on a sheet pin or power symbol; the '
        'PCB generator places it beside a pad on the same net.',
        20,
        15,
    )
    column, row = 24, 36
    sh.note('POWER RAILS', 20 * 1.27, (row - 8) * 1.27, 1.8)
    for net in DEBUG_RAILS:
        if keeps_test_point(net):
            debug_unit(sh, 'rail', net, column, row)
            column += 22
        else:
            kicadgen.retire_refs('TP', 1)
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
        if any(net and keeps_test_point(net) for net in nets):
            sh.note(title.upper(), 20 * 1.27, (row - 8) * 1.27, 1.8)
        for net in nets:
            if net is None or not keeps_test_point(net):
                kicadgen.retire_refs('TP', 1)
                continue
            debug_unit(sh, 'signal', net, column, row)
            column += 28
    column = 24
    row += 30
    sh.note('ISO 5V RAIL LED', 20 * 1.27, (row - 8) * 1.27, 1.8)
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
    pin of their own: power-good flags and the INA239 alert. Runs
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
        'Table 1-1). Exposed pad to VSS, in addition to pin 17. GP7 is spare; firmware enables '
        'a weak pull-up on it.',
        20,
        21,
    )
    sh.note(
        'The ADT7320 INT and CT outputs drive GP2 and GP3, the universal I/O expander '
        'interrupt GP4 and the I/O ADC data-ready GP5.',
        20,
        27,
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
        30,
        110,
    )
    # the removed SC18IS604 and 74LVC1G125 capacitors keep their numbers free
    kicadgen.retire_refs('C', 2)
    net_label(sh, 'EXPANDER_CS', spur(sh, expander, '5', 6), 0, to_parent=True)
    # one {SPI} stub on the right; CS sits below the bus, so nothing crosses it
    tip = pin_cell(expander, '19')
    spi_bus(
        sh,
        [
            (spur(sh, expander, pin, 2), net)
            for pin, net in (('19', 'SPI_SCK'), ('20', 'SPI_MOSI'), ('1', 'SPI_MISO'))
        ],
        tip[0] + 14,
        -1,
        [(tip[0] + 14, tip[1] - 8), (tip[0] + 18, tip[1] - 8)],
    )
    # RESET held high on a short stub, in the column of the address straps
    reset = spur(sh, expander, '4', 3)
    wire(sh, reset, (reset[0], reset[1] - 2))
    rail_symbol(sh, '+3V3', (reset[0], reset[1] - 2))
    # A1 and A0 share one ground symbol
    address_low, address_high = spur(sh, expander, '3', 3), spur(sh, expander, '2', 3)
    wire(sh, address_low, address_high)
    ground(sh, address_high)
    sh.junctions.append(address_high)
    for pin, net in (
        ('9', 'PGP_15V'),
        ('10', 'PGN_15V'),
        ('11', 'AMBIENT_INT'),
        ('12', 'AMBIENT_CT'),
        ('13', 'IO_EXP_INT_N'),
        ('14', 'IO_ADC_DRDY_N'),
        ('15', 'INA239_ALERT'),
    ):
        net_label(sh, net, spur(sh, expander, pin, 6), 180, is_global=True)
    sh.nc(expander, '16')
    if keeps_test_point('EXPANDER_INT'):
        int_end = spur(sh, expander, '7', 8)
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


# Last resistor number used on the board before the direct fan and pump drivers
# were added; their resistors take the numbers above it.
LAST_RESISTOR_BEFORE_FAN_DRIVERS = 171


# SP3422 I/O pins, in symbol order IO1-IO4 (pin 2 is GND)
SP3422_FP = 'cryocooler:Littelfuse_DFN-5_1.0x0.6mm_P0.35mm'


def esd_array(sh, taps, ground_at, lib='SP3422-04UTG', prefix='U', fp=None):
    """Multi-unit ESD clamp (default the SP3422-04UTG) drawn one unit per line: `taps` holds
    (column, row, above) for units A-D, each standing on its line (above it when
    `above`, else hanging below); unit E, the ground pin, sits at `ground_at`.
    Units B-E take named ids, so the shared id sequence moves as it did for the
    one-unit drawing.
    """
    fp = fp or SP3422_FP
    ref = next_ref(prefix)
    ground_pin = {'SP3422-04UTG': '2', 'ESD2CAN24DBZ': '3'}[lib]
    places = [
        ((column, row - 4 if above else row + 4), 180 if above else 0)
        for column, row, above in taps
    ]
    places.append((ground_at, 0))
    for unit, ((column, row), rot) in enumerate(places, start=1):
        def add():
            return sh.add(
                f'cryocooler:{lib}', ref, lib if lib != 'ESD2CAN24DBZ' else lib + 'R',
                column * 1.27, row * 1.27, rot=rot, unit=unit, auto=False, footprint=fp,
            )
        if unit == 1:
            first = add()
            continue
        with kicadgen.named_part_uuids(f'{sh.filename}/{ref}/{unit}'):
            part = add()
    drop_ground(sh, pin_cell(part, ground_pin), 2)
    return first


def fan_channel(sh, title, pwm_net, tach_net, row, index, shared):
    """One 4-pin fan channel, drawn left to right from `row`: GPIO -> BSS138
    open-drain PWM driver -> connector, and connector -> tach pull-up -> 4.7k ->
    GPIO, which limits a 12 V short on the connector to about 2 mA. The gate
    pull-up to +3V3 holds the PWM line low (0% drive) while the GPIO floats during
    boot and reset. `shared` holds the references of the parts both channels use:
    the BSS138DW ('fet'), the 4.7k tach array ('tach') and the 10k array ('pull').
    """
    first_resistor = LAST_RESISTOR_BEFORE_FAN_DRIVERS + index * 3
    net_label(sh, pwm_net, (28, row), 180, to_parent=True)
    with kicadgen.pinned_refs('R', first_resistor):
        vres(sh, '10k', 34, row - 6)
    rail_symbol(sh, '+3V3', (34, row - 6))
    wire(sh, (28, row), (38, row))
    with kicadgen.pinned_refs('R', first_resistor + 1):
        hres(sh, '1k', 41, row)
    wire(sh, (44, row), (46, row))
    driver = nfet_dual(sh, shared['fet'], index + 1, 50, row)
    _gate_pin, source_pin, drain_pin = DUAL_NFET_PINS[index + 1]
    ground(sh, spur(sh, driver, source_pin, 2))
    connector = sh.add(
        'Connector_Generic:Conn_01x04',
        next_ref('J'),
        title,
        120 * 1.27,
        (row + 8) * 1.27,
        rot=180,
        mirror=True,
        auto=False,
        footprint=X2510_4P,
    )
    pwm_pin, tach_pin = pin_cell(connector, '4'), pin_cell(connector, '3')
    drain = pin_cell(driver, drain_pin)
    wire(
        sh,
        drain,
        (drain[0], pwm_pin[1] - 10),
        (114, pwm_pin[1] - 10),
        (114, pwm_pin[1]),
        pwm_pin,
    )
    # array elements stand in for three discrete resistors, whose numbers retire
    kicadgen.retire_refs('R', 2)
    array_res(sh, shared['pull'], index + 1, '10k', 84, pwm_pin[1] - 16)
    rail_symbol(sh, '+3V3_COOL', (84, pwm_pin[1] - 16))
    # the pull-up stays on the connector side so the 4.7k does not form a
    # divider with it when the open-collector tach output pulls low
    wire(sh, tach_pin, (101, tach_pin[1]))
    array_res(sh, shared['tach'], 2 * index + 1, '4.7k', 106, tach_pin[1] - 6)
    rail_symbol(sh, '+3V3_COOL', (106, tach_pin[1] - 6))
    array_res(sh, shared['tach'], 2 * index + 2, '4.7k', 98, tach_pin[1], rot=90)
    wire(sh, (95, tach_pin[1]), (70, tach_pin[1]))
    net_label(sh, tach_net, (70, tach_pin[1]), 180, to_parent=True)
    plus = pin_cell(connector, '2')
    # jogs down so the +12V symbol stays clear of the tach wire above it
    # (all of it right of the tach series resistor, clear of its body)
    jog = (plus[0] - 14, plus[1] + 5)
    wire(sh, plus, (plus[0] - 10, plus[1]), (plus[0] - 10, jog[1]), jog)
    rail_symbol(sh, '+12V', jog)
    vcap(sh, '22uF/25V', plus[0] - 6, plus[1], fp=C1210)
    drop_ground(sh, (plus[0] - 6, plus[1] + 6), 0)
    ground(sh, spur(sh, connector, '1', 2))
    return tach_pin[1]


def build_cooling(sh):
    """Hand-laid: BSS138 PWM drivers on the left, fan and pump connectors on
    the right, flow sensor and NTC below.
    """
    sh.handwired = True
    sh.note(
        'Fan and pump: LEDC PWM at 25 kHz through one BSS138DW element each, because '
        'the PWM input can sit at 5.25 V (Intel 4-wire spec) and GPIOs are not 5 V '
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
    with rev4_refs('Q', 'RN'):
        shared = {'fet': next_ref('Q'), 'tach': next_ref('RN'), 'pull': next_ref('RN')}
    for heading, row in (('FAN', 46), ('PUMP', 82), ('FLOW SENSOR', 114), ('COOLANT NTC', 144)):
        sh.note(heading, 20 * 1.27, row * 1.27, 1.8)
    fan_tach = fan_channel(sh, 'FAN (4-pin PWM)', 'FAN_PWM', 'FAN_TACH', 60, 0, shared)
    pump_tach = fan_channel(sh, 'PUMP (4-pin PWM)', 'PUMP_PWM', 'PUMP_TACH', 92, 1, shared)
    # Alphacool ES flow sensor and NTC, drawn then moved 8 rows down
    marks = sheet_marks(sh)
    # pin 1 at the bottom, like the fan and pump headers, so GND has room; the
    # header family has no 3-pin part, so pin 4 is unused
    j_flow = sh.add(
        'Connector_Generic:Conn_01x04',
        next_ref('J'),
        'ALPHACOOL ES FLOW (pin 4 NC)',
        110 * 1.27,
        124 * 1.27,
        rot=180,
        mirror=True,
        auto=False,
        footprint=X2510_4P,
    )
    sh.nc(j_flow, '4')
    raw = pin_cell(j_flow, '3')
    wire(sh, raw, (raw[0] - 6, raw[1]))
    hres(sh, '4.7k', raw[0] - 9, raw[1])
    wire(sh, (raw[0] - 12, raw[1]), (raw[0] - 30, raw[1]))
    net_label(sh, 'FLOW_TACH', (raw[0] - 30, raw[1]), 180, to_parent=True)
    kicadgen.retire_refs('R', 1)
    array_res(sh, shared['pull'], 3, '10k', raw[0] - 20, raw[1] - 6)
    rail_symbol(sh, '+3V3_COOL', (raw[0] - 20, raw[1] - 6))
    # the array's fourth element is spare: both ends on the rail
    sh.note('SPARE 10k ELEMENT', 44 * 1.27, 132 * 1.27, 1.5)
    array_res(sh, shared['pull'], 4, '10k', 56, 136)
    rail_symbol(sh, '+3V3_COOL', (56, 136))
    wire(sh, (56, 136), (60, 136), (60, 142), (56, 142))
    plus_pin, gnd_pin = pin_cell(j_flow, '2'), pin_cell(j_flow, '1')
    # jogs down so the +12V symbol stays clear of the tach wire above it
    plus_jog = (plus_pin[0] - 12, plus_pin[1] + 5)
    wire(sh, plus_pin, (plus_pin[0] - 4, plus_pin[1]), (plus_pin[0] - 4, plus_jog[1]), plus_jog)
    rail_symbol(sh, '+12V', plus_jog)
    ground(sh, spur(sh, j_flow, '1', 2))
    j_ntc = conn(
        sh,
        'Connector_Generic:Conn_01x02',
        'ALPHACOOL ES NTC 10k',
        110 * 1.27,
        150 * 1.27,
        {},
        X2510_2P,
    )
    ntc = pin_cell(j_ntc, '1')
    wire(sh, ntc, (ntc[0] - 30, ntc[1]))
    net_label(sh, 'NTC_ADC', (ntc[0] - 30, ntc[1]), 180, to_parent=True)
    vres(sh, '10k', ntc[0] - 14, ntc[1] - 6)
    rail_symbol(sh, '+3V3_COOL', (ntc[0] - 14, ntc[1] - 6))
    vcap(sh, '100nF', ntc[0] - 22, ntc[1])
    drop_ground(sh, (ntc[0] - 22, ntc[1] + 6), 0)
    ground(sh, spur(sh, j_ntc, '2', 2))
    shift_since(sh, marks, 0, 8)
    # ESD clamp on the GPIO side of the tach resistors: J3-J5 carry 12 V beside the
    # tach pin, and a 5 V clamp on the connector side would not survive that short.
    # One unit on each line; the flow and NTC rows moved 8 down above
    sh.note('ESD CLAMP GROUND', 150 * 1.27, 112 * 1.27, 1.8)
    with rev3_refs('U'):
        esd_array(
            sh,
            (
                (76, fan_tach, False),
                (76, pump_tach, False),
                (raw[0] - 24, raw[1] + 8, False),
                (ntc[0] - 27, ntc[1] + 8, False),
            ),
            (180, 124),
        )


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
        'DRDY is not connected: firmware polls the conversion. The ESD '
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
    net_label(sh, 'ADS1220_CS', spur(sh, adc, '16', 12), 180, to_parent=True)
    spi_bus(
        sh,
        [
            (spur(sh, adc, pin, 2), net)
            for pin, net in (('15', 'SPI_SCK'), ('14', 'SPI_MOSI'), ('13', 'SPI_MISO'))
        ],
        22,
        1,
        [(22, 64), (18, 64)],
    )
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
    wire(sh, ain1, (78, ain1[1]), (78, 50), (93, 50))
    hres(sh, '1k', 96, 50)
    wire(sh, (99, 50), (140, 50), (156, 50), (156, sp_pin[1]), sp_pin)
    vcap(sh, '10nF', 82, 50)
    drop_ground(sh, (82, 56), 0)
    vcap(sh, '100nF', 92, 50)
    wire(sh, (92, 56), (92, 68))
    wire(sh, ain0, (80, ain0[1]), (80, 68), (93, 68))
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
    sh.note('PT1000 FRONT END', 40 * 1.27, 30 * 1.27, 1.8)
    sh.note('RTD ESD CLAMP GROUND', 136 * 1.27, 89 * 1.27, 1.8)
    # ESD clamp on the connector side of the 1k resistors, one unit on each line
    with rev3_refs('U'):
        esd_array(
            sh,
            ((140, 44, True), (140, 50, False), (140, 68, False), (140, 80, False)),
            (150, 100),
        )
    for net, row in (('RTD_1', 44), ('RTD_2', 50), ('RTD_3', 68), ('RTD_4', 80)):
        net_label(sh, net, (146, row), 0)


def build_imu(sh):
    """Hand-laid: J14 (Molex Micro-Lock Plus 2x4 cabled to the off-board Adafruit
    LSM6DSOX module) on the right, +3V3 / ground pins tied off beside it, each
    signal fanned out through a NUF6401MN filter channel to a global label on
    the left. Pins keep the RJ45's T568B numbering: 1-2 SCK/GND, 3-6 MOSI/MISO,
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
    # J14 stands level with the filter (centre row 84), so each signal runs
    # straight from its pin to its filter channel
    with kicadgen.pinned_refs('J', 13):
        header = sh.add(
            'cryocooler:Conn_02x04_IMU_Cable',
            next_ref('J'),
            '505448-0891',
            200 * 1.27,
            84 * 1.27,
            mirror=True,
            auto=False,
            footprint='cryocooler:Molex_Micro-Lock_Plus_505448-0891_2x04_P1.25mm_Horizontal',
        )
    tips = {
        number: pin_cell(header, number)
        for number in [str(n) for n in range(1, 9)]
    }
    column = tips['1'][0]
    # +3V3 on the top pin, the cable ground on the bottom one
    wire(sh, tips['4'], (tips['4'][0], tips['4'][1] - 2))
    rail_symbol(sh, '+3V3', (tips['4'][0], tips['4'][1] - 2))
    drop_ground(sh, tips['2'], 2)
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
    sh.note('IMU CABLE (J14) AND FILTER', (column - 44) * 1.27, 67 * 1.27, 1.8)
    with rev3_refs('U'):
        part = imu_filter(sh, column - 36, 84)
        # one six-channel part replaces the two NUF4001s (U36, U37): U37 retires
        kicadgen.retire_refs('U', 1)
    # the removed series resistors leave one number retired, as the old CS pull-up did
    kicadgen.retire_refs('R', 1)
    jack_pins = ('12', '11', '10', '9', '8', '7')
    module_pins = ('1', '2', '3', '4', '5', '6')
    # each J14 pin faces its filter channel on the same row
    taps = []
    for channel, (number, net) in enumerate(signals):
        target = pin_cell(part, jack_pins[channel])
        assert target[1] == tips[number][1], (number, target, tips[number])
        wire(sh, tips[number], target)
        if net.startswith('SPI_'):
            taps.append((spur(sh, part, module_pins[channel], 2), net))
        else:
            far = spur(sh, part, module_pins[channel], 12)
            net_label(sh, net, far, 180, to_parent=True)
    # member labels sit between the CS/INT flags and the filter; the bus runs
    # left of the flags
    spi_bus(sh, taps, 124, 1, [(124, 94), (120, 94)])


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


def build_display(sh):
    """Display sheet; the retired rev 2 to rev 4 display parts keep their numbers."""
    with high_refs('R'), high_refs('C'), high_refs('Q'):
        kicadgen.retire_refs('R', 4)
        kicadgen.retire_refs('C', 4)
        kicadgen.retire_refs('Q', 1)
    kicadgen.retire_refs('U', 1)
    kicadgen.retire_refs('TP', 1)
    display_link(sh)


# Screw terminals on the back of the Waveshare ESP32-S3-Touch-LCD-4.3B, left to
# right as printed on the board (Waveshare "What's On Board" back view, read
# 2026-11-15): L / H are CAN, B / A are RS485, COM is DI COM.
WAVESHARE_TERMINALS = (
    'VIN', 'GND', 'VOUT', 'GND', 'SDA', 'SCL', 'L', 'H',
    'B', 'A', 'DO0', 'DO1', 'COM', 'GND', 'DI0', 'DI1',
)


def waveshare_drawing(sh, column, row):
    """Back view of the off-board Waveshare touchscreen, about 3/4 scale and
    landscape: board outline with its top-left corner on cell (column, row) and
    the main parts placed by eye from Waveshare's picture (drawing only). The
    16-way terminal strip on the bottom edge is a real symbol, marked off-board,
    so the nets of the two cables show on its pins. Returns that part.
    """
    def mm(cells):
        return cells * 1.27

    def box(left, top, right, bottom, text, text_left, text_top, size=1.2):
        sh.rectangle(mm(column + left), mm(row + top), mm(column + right), mm(row + bottom))
        sh.note(text, mm(column + text_left), mm(row + text_top), size)

    sh.note('OFF-BOARD: WAVESHARE ESP32-S3-Touch-LCD-4.3B, BACK VIEW', mm(column), mm(row - 8), 1.8)
    sh.note('own ESP32-S3 and firmware; 4.3 in, 800 x 480 touchscreen on the other side',
            mm(column), mm(row - 4), 1.5)
    sh.rectangle(mm(column), mm(row), mm(column + 66), mm(row + 44), 0.5)
    box(2, 3, 10, 13, 'SD card', 2.8, 8)
    box(12, 2, 25, 17, 'ESP32-S3', 14.5, 9, 1.5)
    box(0, 20, 5, 25, 'USB-C', 6, 22.5)
    box(2, 28, 5, 31, 'BOOT', 6, 29.5)
    box(2, 33, 5, 36, 'RESET', 6, 34.5)
    box(38, 20, 53, 23, 'LCD FPC', 42, 18.5)
    box(56, 17, 62, 23, 'RTC', 57.2, 20)
    terminals = sh.add(
        'Connector_Generic:Conn_01x16',
        'DS1',
        'TERMINALS',
        (column + 34) * 1.27,
        (row + 43) * 1.27,
        rot=90,
        auto=False,
    )
    terminals.off_board = True
    for index, name in enumerate(WAVESHARE_TERMINALS):
        pin_column = pin_cell(terminals, str(index + 1))[0]
        # neighbours alternate between two rows so the names never touch
        sh.note(name, mm(pin_column - 0.9), mm(row + 35 + 2.5 * (index % 2)), 1.0)
    sh.note('CAN', mm(pin_cell(terminals, '7')[0] - 0.5), mm(row + 32), 1.2)
    sh.note('RS485', mm(pin_cell(terminals, '9')[0] - 0.5), mm(row + 32), 1.2)
    return terminals


CAN_PHY_COLUMN = 130  # transceiver column: its bus pins end under 85 mm from J15
CAN_PHY_ROW = 78


def display_link(sh):
    """Hand-laid: the off-board Waveshare ESP32-S3-Touch-LCD-4.3B runs its own
    firmware. CAN transceiver on the left with the digital-output circuits below
    it; the connector sits beside the terminals it wires to on the back-view
    drawing of the display.
    """
    sh.handwired = True
    sh.note(
        'Waveshare ESP32-S3-Touch-LCD-4.3B (own ESP32-S3, 800 x 480, 7-36 V in, about '
        '2.3 W): telemetry and commands over CAN (its TJA1051T/3 on GPIO15 / GPIO16, '
        '120 R by switch).',
        20,
        15,
    )
    sh.note(
        'It is fed from VIN, ahead of the power switch, so it runs while this board is '
        'off. 120 R ends the bus at this board.',
        20,
        21,
    )
    sh.note(
        'TCAN3414 (SLLSFS8A): 3.3 V supply, STB and SHDN low = normal mode, TXD '
        'dominant time-out 1.2 ms min, bus pins high impedance when unpowered, +-58 V '
        'bus fault protection.',
        20,
        27,
    )
    sh.note(
        'Its two digital outputs press the power button and RESET through J15 pins 5 and 6: '
        'sheet pins PWR_BTN (to the Power Button sheet) and ESP_EN (to the ESP32).',
        20,
        33,
    )
    terminals = waveshare_drawing(sh, 240, 48)
    # the two cables land on the display's terminals with the same nets
    feed_pin = pin_cell(terminals, '1')
    vin = (feed_pin[0] - 6, feed_pin[1] + 2)
    wire(sh, feed_pin, (feed_pin[0], vin[1]), vin)
    rail_symbol(sh, 'VIN', vin)
    # the strip's reference sits outside the outline, left of the feed
    x, y = vin[0] * 1.27 - 18, (vin[1] + 3) * 1.27
    terminals.pinned_fields = {'Reference': (x, y), 'Value': (x, y + FIELD_LINE)}
    for pin in ('2', '14'):
        drop_ground(sh, pin_cell(terminals, pin), 3)
    # vertical labels; the first of each pair steps one pin left so the texts
    # are two pins apart
    for pin, net, step in (
        ('7', 'CAN_L', -2), ('8', 'CAN_H', 0),
        ('11', 'DISP_PWR_BTN', -2), ('12', 'DISP_RESET', 0),
    ):
        tip = pin_cell(terminals, pin)
        end = (tip[0] + step, tip[1] + 4)
        wire(sh, tip, (tip[0], tip[1] + 2), (end[0], tip[1] + 2), end)
        net_label(sh, net, end, 270)
    for pin in ('3', '4', '5', '6', '9', '10', '13', '15', '16'):
        sh.nc(terminals, pin)
    # on-board connector the cable plugs into, left of the display
    sh.note('ON-BOARD CONNECTOR', 186 * 1.27, 48 * 1.27, 1.8)
    link_cell = (206, 72)
    with kicadgen.pinned_refs('U', REV5_LAST['U'] + 2):
        phy = place_ic(
            sh,
            'cryocooler:TCAN3414DRBR',
            'TCAN3414DRBR',
            CAN_PHY_COLUMN,
            CAN_PHY_ROW,
            'Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm',
        )
    sh.note('CAN TRANSCEIVER', (CAN_PHY_COLUMN - 70) * 1.27, 48 * 1.27, 1.8)
    supply = pin_cell(phy, '3')
    wire(sh, supply, (supply[0], supply[1] - 4))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
    gnd_bus(sh, [pin_cell(phy, pin) for pin in ('2', '9')])
    # STB and SHDN low: normal mode whenever +3V3 is up
    standby, shutdown = pin_cell(phy, '8'), pin_cell(phy, '5')
    wire(sh, standby, (standby[0] - 6, standby[1]), (standby[0] - 6, shutdown[1]))
    wire(sh, shutdown, (standby[0] - 6, shutdown[1]))
    drop_ground(sh, (standby[0] - 6, shutdown[1]), 2)
    transmit = pin_cell(phy, '1')
    transmit_end = (transmit[0] - 22, transmit[1])
    wire(sh, transmit, transmit_end)
    net_label(sh, 'CAN_TX', transmit_end, 180, to_parent=True)
    with kicadgen.pinned_refs('R', REV5_LAST['R'] + 4):
        # recessive while GPIO17 floats at reset
        vres(sh, '10k', transmit[0] - 14, transmit[1] - 6)
        rail_symbol(sh, '+3V3', (transmit[0] - 14, transmit[1] - 6))
        receive = pin_cell(phy, '4')
        receive_end = (receive[0] - 22, receive[1])
        wire(sh, receive, receive_end)
        net_label(sh, 'CAN_RX', receive_end, 180, to_parent=True)
        # the display cable ends in one 6-pin JST PH housing (pin 1 at the bottom)
        with kicadgen.pinned_refs('J', 14):
            link_ref = next_ref('J')
        link = sh.add(
            'Connector_Generic:Conn_01x06', link_ref,
            'DISPLAY (GND / 12V / CAN H / L / BTN / RST)',
            link_cell[0] * 1.27, (link_cell[1] + 4) * 1.27, rot=180, mirror=True, auto=False,
            footprint=PH_V6,
        )
        drop_ground(sh, spur(sh, link, '1', 2), 2)
        net_label(sh, 'DISP_PWR_BTN', spur(sh, link, '5', 4), 180)
        net_label(sh, 'DISP_RESET', spur(sh, link, '6', 4), 180)
        # bus pair wired straight to J15 (CANL above CANH on both), terminated
        # here; CAN_H dips under the 120 R and rises again before J15
        low, high = pin_cell(phy, '6'), pin_cell(phy, '7')
        can_l, can_h = pin_cell(link, '4'), pin_cell(link, '3')
        assert (low[1], high[1]) == (can_l[1], can_h[1]), (low, high, can_l, can_h)
        end, dip, rise, clamp_column = low[0] + 8, low[1] + 6, can_h[0] - 16, can_h[0] - 36
        wire(sh, low, (end, low[1]), (clamp_column, low[1]), (can_l[0] - 14, low[1]), can_l)
        # turned so pin 1 stays on CAN_H, as it was
        res(sh, '120', '', '', pose=at(end, low[1] + 3, 180), fp=R1206)
        wire(
            sh, high, (high[0] + 4, high[1]), (high[0] + 4, dip), (end, dip),
            (clamp_column, dip), (rise, dip), (rise, high[1]), (can_h[0] - 14, high[1]), can_h,
        )
        # one label each where the cable to the display's terminals leaves
        net_label(sh, 'CAN_L', (can_l[0] - 14, low[1]), 0)
        net_label(sh, 'CAN_H', (can_h[0] - 14, high[1]), 0)
    with io_refs():
        # resettable fuse in the display feed, below the bus pair: a shorted cable
        # no longer takes F1
        feed = spur(sh, link, '2', 6)
        fuse_row = feed[1] + 16
        fuse = sh.add(
            'Device:Polyfuse', 'F2', 'MF-MSMF050/24X', (feed[0] - 8) * 1.27, fuse_row * 1.27,
            rot=90, auto=False, footprint='Fuse:Fuse_1812_4532Metric',
        )
        role(fuse, 'display_fuse')
        wire(sh, feed, (feed[0], fuse_row), pin_cell(fuse, '2'))
        left = pin_cell(fuse, '1')
        wire(sh, left, (left[0] - 8, left[1]))
        rail_symbol(sh, 'VIN', (left[0] - 8, left[1]))
        sh.note('CAN CLAMP GROUND (D101 SITS BESIDE J15 ON THE BOARD)', 130 * 1.27, 136 * 1.27, 1.8)
        clamp = esd_array(
            sh, ((clamp_column, dip, False), (clamp_column, low[1], True)), (160, 148),
            lib='ESD2CAN24DBZ', prefix='D', fp='Package_TO_SOT_SMD:SOT-23',
        )
        role(clamp, 'can_clamp')
    with kicadgen.pinned_refs('C', REV5_LAST['C'] + 2):
        place_blocks(
            sh,
            [('TCAN3414 DECOUPLING CAPACITOR', '+3V3', ('100nF',))],
            40,
            156,
        )
    display_buttons(sh, 100, 124)


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
    sh.note('STATUS LED', 30 * 1.27, 64 * 1.27, 1.8)
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
    net_label(sh, 'STATUS_RGB', (a_pin[0] - 14, a_pin[1]), 180, to_parent=True)
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
# Universal I/O (rev 5): four software-configured channels, two pressure ports
# ═════════════════════════════════════════════════════════════════════════
IO_CHANNELS = 4
# Universal I/O parts take numbers above every earlier part (last used numbers)
IO_REFS = {'U': 99, 'R': 599, 'C': 399, 'D': 99, 'Q': 99, 'J': 29, 'JP': 9}
# expander bit of each per-channel signal (port A holds the odd channel of a pair)
IO_EXPANDER_BITS = (
    'OUT_EN', 'DIRECT', 'BURDEN', 'PULLUP', 'SENS_EN', 'AMP_FLT_N', 'SENS_FLT_N', 'BUF_OE_N',
)
# bit 7 of a slow channel's port has no buffer enable: these carry other signals
IO_SPARE_INPUTS = {3: 'rs485_irq', 4: 'hdr_int'}
# channel whose port bit 5 reads each output switch's fault flag: channel -> group
IO_DRIVER_FLAGS = {1: 'A'}
# bit 5 of the other ports carries the precision excitation enable and fault
IO_SPARE_FLAGS = {2: 'prec_exc_en', 3: 'prec_exc_flt'}
# routing: channel 1 DIRECT is on channel 4's spare bit 5 (expander 1 GPB5),
# and its own bit 1 (expander 0 GPA1) is left spare
IO_DIRECT_PORT = {1: 4}
# ADS124S08 pins: AIN0-3 read the channels, AIN4 / AIN5 the pressure ports
ADC_CHANNEL_PINS = ('7', '6', '5', '4')
ADC_PRESSURE_PINS = ('3', '2')
ADC_SPARE_PINS = ('32', '31')
PRESSURE_PORTS = {1: '100 psi', 2: '30 psi'}
# TSB582 DFN8 (ST DS13378 Fig. 1): each section's (IN+, IN-, OUT) pins; unit 3 holds
# VCC- (4), VCC+ (8) and the exposed pad (9)
DRIVER_OPAMP_PINS = {1: ('3', '2', '1'), 2: ('5', '6', '7')}
TVS1800_FP = 'Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm'
FEMTOFET_FP = 'cryocooler:Texas_FemtoFET_F4_1.0x0.6mm'
BUFFER_FP = 'Package_SON:Texas_USON-6_1x1.45mm_P0.5mm_SMD'


def io_refs():
    """Numbers parts created inside the block from the universal I/O ranges."""
    return ranged_refs(IO_REFS, tuple(IO_REFS))


def role(part, key, **fields):
    """Sets a part's description from a part_descriptions.IO_PART_ROLES template."""
    import part_descriptions

    part_descriptions.DESCRIPTIONS[part.ref] = part_descriptions.IO_PART_ROLES[key].format(
        **fields
    )
    return part


def io_label(sh, key, cell, angle=0, is_global=True, to_parent=False, **fields):
    """Net label named and described from a part_descriptions.IO_NET_ROLES template."""
    import part_descriptions

    name, text = part_descriptions.IO_NET_ROLES[key]
    net = name.format(**fields)
    part_descriptions.NET_DESCRIPTIONS[net] = text.format(**fields)
    net_label(sh, net, cell, angle, is_global=is_global, to_parent=to_parent)
    return net


def taps(sh):
    """Cells on a sheet's control lines where their pull resistors hang, noted
    while the lines are drawn; the resistors are created later, in the order the
    board's references follow."""
    return sh.__dict__.setdefault('taps', {})


def pull_up_at(sh, value, cell, part_key, rail='+3V3', **fields):
    """Pull-up standing above a line: rail on top, pin 2 on the line at `cell`."""
    role(vres(sh, value, cell[0], cell[1] - 6), part_key, **fields)
    rail_symbol(sh, rail, (cell[0], cell[1] - 6))


def pull_down_at(sh, value, cell, part_key, small=False, **fields):
    """Pull-down hanging below a line: pin 1 on the line at `cell`, ground under
    it. small draws the short symbol, for lines only eight cells apart."""
    role(vres(sh, value, cell[0], cell[1], small=small), part_key, **fields)
    drop_ground(sh, (cell[0], cell[1] + (4 if small else 6)), 0)


def select_line(sh, part, pin, key, **fields):
    """A switch's select input: a line out to its sheet-pin label on the left,
    with room for the pull-down that hangs on it (taps)."""
    tip = pin_cell(part, pin)
    end = (tip[0] - 24, tip[1])
    wire(sh, tip, end)
    io_label(sh, key, end, 180, **fields)
    taps(sh)[(key, fields.get('n'))] = (tip[0] - 8, tip[1])


# Column of the output gate's series resistor on its select line, and that
# line's row (pin 6 of the gate at (60, 76)).
GATE_SERIES, GATE_SELECT_ROW = 27, 74


def io_output_gate(sh, n, gpio):
    """Fast channel only: the ESP32 pin switches the output driver's input between
    the DAC level and ground (PWM at the configured level).
    """
    sh.note(f'OUTPUT GATE (GPIO{gpio})', 20 * 1.27, 40 * 1.27, 1.8)
    gate = role(
        place_ic(sh, 'cryocooler:SN74LVC1G3157DSF', 'SN74LVC1G3157DSFR', 60, 76,
                 'cryocooler:Texas_DSF0006A_X2SON-6_1x1mm_P0.35mm'),
        'gate', n=n, gpio=gpio,
    )
    out = pin_cell(gate, '4')
    wire(sh, out, (out[0] + 12, out[1]))
    io_label(sh, 'level', (out[0] + 12, out[1]), 0, n=n)
    # the DAC level steps up on its way in, leaving the select line's row to
    # the series resistor that io_fast_path() draws on it
    level_in, select = pin_cell(gate, '1'), pin_cell(gate, '6')
    wire(sh, level_in, (level_in[0] - 2, level_in[1]), (level_in[0] - 2, 64), (24, 64))
    io_label(sh, 'dac', (24, 64), 180, n=n)
    wire(sh, select, (GATE_SERIES + 3, select[1]))
    io_label(sh, 'gate', (GATE_SERIES + 4, select[1]), 0, is_global=False, n=n)
    low = pin_cell(gate, '3')
    wire(sh, low, (low[0] - 2, low[1]))
    drop_ground(sh, (low[0] - 2, low[1]), 2)
    supply = pin_cell(gate, '5')
    wire(sh, supply, (supply[0], supply[1] - 4))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
    drop_ground(sh, pin_cell(gate, '2'), 2)


def io_measurement(sh, n):
    """Pin -> 100k -> ADC input, with the 20k divider leg (switched to ground on
    the range switch sheet) and the switched 120 R loop burden.
    """
    sh.note('MEASUREMENT', 20 * 1.27, 104 * 1.27, 1.8)
    io_label(sh, 'pin', (30, 116), 180, n=n)
    wire(sh, (30, 116), (40, 116), (47, 116))
    role(hres(sh, '100k', 50, 116), 'divider_top', n=n)
    wire(sh, (53, 116), (58, 116), (70, 116), (78, 116))
    io_label(sh, 'adc', (78, 116), 0, n=n)
    role(vcap(sh, '100nF', 58, 116), 'adc_filter', n=n)
    drop_ground(sh, (58, 122), 2)
    role(vres(sh, '20k', 70, 116), 'divider_bottom', n=n)
    wire(sh, (70, 122), (70, 126), (78, 126))
    io_label(sh, 'div', (78, 126), 0, n=n)
    wire(sh, (40, 116), (40, 122))
    role(vres(sh, '120', 40, 122, fp=R2512), 'burden', n=n)
    switch = sh.add(
        'Transistor_FET:BSS138', next_ref('Q'), 'CSD17381F4', 42 * 1.27, 134 * 1.27,
        auto=False, footprint=FEMTOFET_FP, mirror=True,
    )
    role(switch, 'burden_fet', n=n)
    wire(sh, (40, 128), pin_cell(switch, '3'))
    drop_ground(sh, pin_cell(switch, '2'), 2)
    # gate on the right: the left of the burden leg stays free for the pin
    # line's drop to the fast path
    gate = pin_cell(switch, '1')
    wire(sh, gate, (gate[0] + 10, gate[1]))
    io_label(sh, 'burden', (gate[0] + 10, gate[1]), 0, n=n)
    taps(sh)['burden'] = (gate[0] + 5, gate[1])


def io_fast_path(sh, n, gpio):
    """Fast channel only: the pin, clamped to 3.3 V behind 1 M, through a tri-state
    buffer back to the ESP32 pin; and that pin's 1 k feed to the output gate.
    """
    sh.note(f'FAST PATH (GPIO{gpio})', 40 * 1.27, 152 * 1.27, 1.8)
    # the pin comes down from the measurement line above
    wire(sh, (34, 116), (34, 170), (37, 170))
    role(hres(sh, '1M', 40, 170), 'fast_series', n=n, gpio=gpio)
    buffer = role(
        place_ic(sh, 'cryocooler:SN74LVC1G125DRY', 'SN74LVC1G125DRYR', 74, 172, BUFFER_FP),
        'fast_buffer', n=n, gpio=gpio,
    )
    data_in = pin_cell(buffer, '2')
    wire(sh, (43, 170), (48, 170), (50, 170), (data_in[0], 170), data_in)
    io_label(sh, 'logic', (50, 170), 0, is_global=False, n=n)
    clamp = sh.add(
        'Device:D', next_ref('D'), '1N4148W', 48 * 1.27, 164 * 1.27, rot=270, auto=False,
        footprint='Diode_SMD:D_SOD-123',
    )
    role(clamp, 'fast_clamp', n=n, gpio=gpio)
    wire(sh, pin_cell(clamp, '2'), (48, 170))
    top = pin_cell(clamp, '1')
    wire(sh, top, (top[0], top[1] - 2))
    rail_symbol(sh, '+3V3', (top[0], top[1] - 2))
    sh.nc(buffer, '5')
    data_out = pin_cell(buffer, '4')
    wire(sh, data_out, (data_out[0] + 1, data_out[1]), (data_out[0] + 11, data_out[1]))
    io_label(sh, 'buf', (data_out[0] + 1, data_out[1]), 0, is_global=False, n=n)
    role(hres(sh, '1k', data_out[0] + 14, data_out[1]), 'fast_out', n=n, gpio=gpio)
    wire(sh, (data_out[0] + 17, data_out[1]), (data_out[0] + 20, data_out[1]))
    net_label(sh, f'AUX_IO{gpio}', (data_out[0] + 20, data_out[1]), 0, is_global=True)
    supply = pin_cell(buffer, '6')
    wire(sh, supply, (supply[0], supply[1] - 3))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 3))
    drop_ground(sh, pin_cell(buffer, '3'), 2)
    enable = pin_cell(buffer, '1')
    wire(sh, enable, (enable[0], enable[1] + 8), (enable[0] - 22, enable[1] + 8))
    io_label(sh, 'buf_oe', (enable[0] - 22, enable[1] + 8), 180, n=n)
    taps(sh)['buf_oe'] = (enable[0] - 12, enable[1] + 8)
    # the ESP32 pin's 1 k feed to the output gate, drawn at the gate's select pin
    role(hres(sh, '1k', GATE_SERIES, GATE_SELECT_ROW), 'gate_series', n=n, gpio=gpio)
    wire(sh, (GATE_SERIES - 3, GATE_SELECT_ROW), (GATE_SERIES - 7, GATE_SELECT_ROW))
    net_label(sh, f'AUX_IO{gpio}', (GATE_SERIES - 7, GATE_SELECT_ROW), 180, is_global=True)


def io_sensor_supply(sh, n):
    """5 V or 12 V (one jumper fitted) -> TPS26625 -> connector pin 1, and the
    3-pin connector with its two surge clamps.
    """
    sh.note('SENSOR SUPPLY AND CONNECTOR', 164 * 1.27, 34 * 1.27, 1.8)
    fuse = role(
        place_ic(sh, 'cryocooler:TPS26625DRC', 'TPS26625DRCR', 215, 60,
                 'Package_SON:Texas_DRC0010J'),
        'sensor_switch', n=n,
    )
    wire(sh, pin_cell(fuse, '1'), (199, 54), (186, 54), (181, 54))
    for value, rail, row, lib, key in (
        (f'IO{n} 5V', '+5V', 54, 'Jumper:Jumper_2_Bridged', 'jumper_5v'),
        (f'IO{n} 12V', '+12V', 44, 'Jumper:Jumper_2_Open', 'jumper_12v'),
    ):
        jumper = sh.add(
            lib, next_ref('JP'), value, 177 * 1.27, row * 1.27, auto=False,
            footprint=SWITCH_HEADER,
        )
        role(jumper, key, n=n)
        jumper.dnp = lib.endswith('Open')
        rail_symbol(sh, rail, (169, row))
        wire(sh, (169, row), pin_cell(jumper, '1'))
    wire(sh, (181, 44), (181, 54))
    role(vres(sh, '1M', 199, 54), 'uvlo', n=n)
    wire(sh, (199, 60), pin_cell(fuse, '2'))
    role(vcap(sh, '1uF/50V', 186, 54), 'sensor_in_cap', n=n)
    drop_ground(sh, (186, 60), 2)
    wire(sh, pin_cell(fuse, '4'), (197, 62), (197, 66), (183, 66))
    io_label(sh, 'sens_en', (183, 66), 180, n=n)
    gnd_bus(sh, [pin_cell(fuse, pin) for pin in ('5', '6', '11')])
    wire(sh, pin_cell(fuse, '3'), (201, 64), (201, 72), (211, 72))
    # the fault flag steps down past the current-limit resistor, so its
    # pull-up stands clear of the output line above
    wire(sh, pin_cell(fuse, '9'), (241, 56), (241, 72), (257, 72))
    io_label(sh, 'sens_flt', (257, 72), 0, n=n)
    sh.nc(fuse, '8')
    wire(sh, pin_cell(fuse, '7'), (231, 60))
    role(vres(sh, '53.6k', 231, 60), 'sensor_limit', n=n)
    drop_ground(sh, (231, 66), 2)
    header = conn(
        sh, 'Connector_Generic:Conn_01x04', f'IO{n} (V+ / IO / GND / NC)', 290 * 1.27,
        80 * 1.27, {'4': None}, X2510_4P,
    )
    role(header, 'connector', n=n)
    wire(sh, pin_cell(fuse, '10'), (257, 54), (275, 54), (275, 78), pin_cell(header, '1'))
    role(vcap(sh, '1uF/50V', 257, 54), 'sensor_out_cap', n=n)
    drop_ground(sh, (257, 60), 2)
    supply_clamp = role(
        place_ic(sh, 'cryocooler:TVS1800DRV', 'TVS1800DRVR', 285, 56, TVS1800_FP,
                 ref_prefix='D'),
        'supply_clamp', n=n,
    )
    wire(sh, (275, 54), pin_cell(supply_clamp, '4'))
    drop_ground(sh, pin_cell(supply_clamp, '1'), 2)
    wire(sh, pin_cell(header, '2'), (259, 80), (249, 80))
    io_label(sh, 'pin', (249, 80), 180, n=n)
    pin_clamp = role(
        place_ic(sh, 'cryocooler:TVS1800DRV', 'TVS1800DRVR', 265, 90, TVS1800_FP,
                 ref_prefix='D'),
        'pin_clamp', n=n,
    )
    wire(sh, (259, 80), pin_cell(pin_clamp, '4'))
    drop_ground(sh, pin_cell(pin_clamp, '1'), 2)
    wire(sh, pin_cell(header, '3'), (282, 82))
    drop_ground(sh, (282, 82), 2)


def build_io_channel(n):
    """Builder for the sheet of universal I/O channel n."""

    def build(sh):
        sh.handwired = True
        gpio = IO_FAST.get(n)
        sh.note(
            f'Universal I/O channel {n}: connector pin 1 = switched sensor supply, 2 = '
            'signal, 3 = GND. Output: DAC level x 4.83 from a TSB582 section through a '
            'switch (IO Output Drivers sheet), up to 100 mA, open while OUT_EN is low.',
            20, 15,
        )
        sh.note(
            'Input: the pin through 100k to the ADC; with the 20k leg grounded (default) '
            '15 V reads 2.5 V, with DIRECT high the range is 0-2.5 V. BURDEN adds 120 R for '
            '4-20 mA loops; PULLUP (range switch sheet) adds 10k to +3V3.',
            20, 21,
        )
        sh.note(
            'Every control line is pulled to its off level, so the channel is high '
            'impedance with the sensor supply off until firmware sets the expander.'
            + (f' GPIO{gpio} gates the DAC level (PWM) and reads the pin through the buffer.'
               if gpio else ''),
            20, 27,
        )
        with io_refs():
            if gpio:
                io_output_gate(sh, n, gpio)
            io_measurement(sh, n)
            if gpio:
                io_fast_path(sh, n, gpio)
            io_sensor_supply(sh, n)
            # every control line's pull to its off level hangs on the line itself
            pull_up_at(sh, '10k', (249, 72), 'pull_sens_flt', n=n)
            pull_down_at(sh, '22k', (192, 66), 'pull_sens_en', n=n)
            pull_down_at(sh, '100k', taps(sh)['burden'], 'pull_burden', n=n)
            blocks = []
            if gpio:
                pull_up_at(sh, '10k', taps(sh)['buf_oe'], 'pull_buf_oe', n=n)
                pull_down_at(sh, '100k', (44, GATE_SELECT_ROW), 'pull_gate', n=n, gpio=gpio)
                blocks.append(
                    ('GATE AND BUFFER DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF'))
                )
            first = kicadgen._ref_counters['C']
            place_blocks(sh, blocks, 164, 176, max_column=300)
            for part in sh.parts:
                if part.ref.startswith('C') and first < int(part.ref[1:]) :
                    role(part, 'decoupling', n=n)

    return build


def build_io_core(sh):
    """Hand-laid: the DAC that sets the four output levels and the ADC that reads
    the four pins and the two pressure ports.
    """
    sh.handwired = True
    sh.note(
        'DAC60508Z: 12-bit, outputs at zero after reset. On 3.3 V its 2.5 V reference needs '
        'the divider on with gain 2 (GAIN register), giving 0-2.5 V; until firmware writes '
        'that, the reference alarm holds every output at 0 V. SDI is latched on falling '
        'SCLK edges (SPI mode 1).',
        20, 15,
    )
    sh.note(
        'ADS124S08: SPI mode 1, AVDD 5 V, logic 3.3 V. AIN0-3 read channels 1-4 against '
        'AINCOM = ground with the internal 2.5 V reference and the PGA bypassed (a '
        'ground-referenced input is outside the PGA range).',
        20, 21,
    )
    sh.note(
        'AIN4 / AIN5 read the pressure ports against REFP0 / REFN0 (the 5 V excitation). '
        'AIN8-11 serve the precision ports. START and CLK low. DAC outputs 4-7 and '
        'AIN6 / AIN7 are not used.',
        20, 27,
    )
    sh.note(
        'Both release their data output when CS is high (DAC60508 section 8.5, ADS124S08 '
        'section 9.5.1), so they share SPI_MISO without a buffer.',
        20, 33,
    )
    with io_refs():
        dac = role(
            place_ic(sh, 'cryocooler:DAC60508ZRTE', 'DAC60508ZRTER', 80, 80,
                     'Package_DFN_QFN:Texas_RTE0016D_WQFN-16-1EP_3x3mm_P0.5mm_EP0.8x0.8mm'),
            'dac',
        )
        sh.note('OUTPUT LEVEL DAC', 30 * 1.27, 54 * 1.27, 1.8)
        spi_bus(
            sh,
            [(spur(sh, dac, pin, 2), net)
             for pin, net in (('13', 'SPI_SCK'), ('14', 'SPI_MOSI'), ('15', 'SPI_MISO'))],
            42, -1, [(42, 62), (38, 62)],
        )
        io_label(sh, 'dac_cs', spur(sh, dac, '12', 12), 180, is_global=False, to_parent=True)
        # spaced so each capacitor's text fits beside it
        reference = spur(sh, dac, '1', 10)
        wire(sh, reference, (reference[0] - 14, reference[1]))
        for index in range(2):
            column = reference[0] - 14 * index
            role(vcap(sh, '100nF', column, reference[1]), 'dac_ref')
            drop_ground(sh, (column, reference[1] + 6), 2)
        for index, pin in enumerate(('2', '3', '4', '5', '8', '9', '10', '11')):
            if index < IO_CHANNELS:
                io_label(sh, 'dac', spur(sh, dac, pin, 6), 0, n=index + 1)
            else:
                sh.nc(dac, pin)
        supply = [pin_cell(dac, '7'), pin_cell(dac, '16')]
        for cell in supply:
            wire(sh, cell, (cell[0], cell[1] - 3))
        wire(sh, (supply[0][0], supply[0][1] - 3), (supply[1][0], supply[1][1] - 3))
        wire(sh, (supply[0][0], supply[0][1] - 3), (supply[0][0], supply[0][1] - 5))
        rail_symbol(sh, '+3V3', (supply[0][0], supply[0][1] - 5))
        gnd_bus(sh, [pin_cell(dac, '6'), pin_cell(dac, '17')])

        sh.note('INPUT ADC', 150 * 1.27, 54 * 1.27, 1.8)
        adc = role(
            place_ic(sh, 'cryocooler:ADS124S08IRHB', 'ADS124S08IRHBR', 200, 90,
                     'Package_DFN_QFN:Texas_RHB0032M_VQFN-32-1EP_5x5mm_P0.5mm_EP2.1x2.1mm'),
            'adc',
        )
        for index, pin in enumerate(ADC_CHANNEL_PINS):
            io_label(sh, 'adc', spur(sh, adc, pin, 6), 180, n=index + 1)
        for index, pin in enumerate(ADC_PRESSURE_PINS):
            io_label(sh, 'press_adc', spur(sh, adc, pin, 6), 180, n=index + 1)
        for pin in ADC_SPARE_PINS:
            sh.nc(adc, pin)
        # AIN8-11 and the external reference pair serve the two precision ports
        for pin, key, port in (
            ('22', 'prec_p', 'A'), ('21', 'prec_n', 'A'), ('20', 'prec_p', 'B'),
            ('19', 'prec_n', 'B'), ('30', 'prec_refp', ''), ('29', 'prec_refn', ''),
        ):
            io_label(sh, key, spur(sh, adc, pin, 6), 180, p=port)
        sh.nc(adc, '25')
        drop_ground(sh, spur(sh, adc, '1', 4), 2)
        reset = spur(sh, adc, '18', 4)
        wire(sh, reset, (reset[0], reset[1] - 3))
        rail_symbol(sh, '+3V3', (reset[0], reset[1] - 3))
        spi_bus(
            sh,
            [(spur(sh, adc, pin, 2), net)
             for pin, net in (('11', 'SPI_SCK'), ('10', 'SPI_MOSI'), ('12', 'SPI_MISO'))],
            236, -1, [(236, 62), (240, 62)],
        )
        io_label(sh, 'adc_cs', spur(sh, adc, '9', 12), 0, is_global=False, to_parent=True)
        io_label(sh, 'adc_drdy', spur(sh, adc, '13', 12), 0)
        # reference capacitor REFOUT - REFCOM; REFCOM, CLK and START on one ground bar
        ref_out = spur(sh, adc, '23', 8)
        role(vcap(sh, '1uF', ref_out[0], ref_out[1]), 'adc_ref')
        bar = [spur(sh, adc, pin, 4) for pin in ('24', '17', '8')]
        bottom = bar[-1][1] + 4
        wire(sh, bar[0], (bar[0][0], bottom))
        wire(sh, (ref_out[0], ref_out[1] + 6), (ref_out[0], bottom), (bar[0][0], bottom))
        drop_ground(sh, (bar[0][0], bottom), 2)
        analog, digital, io = (pin_cell(adc, pin) for pin in ('26', '16', '15'))
        wire(sh, analog, (analog[0], analog[1] - 5))
        rail_symbol(sh, '+5V_IO', (analog[0], analog[1] - 5))
        wire(sh, digital, (digital[0], digital[1] - 2), (io[0], io[1] - 2), io)
        wire(sh, (io[0], io[1] - 2), (io[0], io[1] - 5))
        rail_symbol(sh, '+3V3', (io[0], io[1] - 5))
        gnd_bus(sh, [pin_cell(adc, pin) for pin in ('27', '28', '14', '33')])
        first = kicadgen._ref_counters['C']
        place_blocks(
            sh,
            [
                ('DAC60508 DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF', '1uF')),
                ('ADS124S08 AVDD DECOUPLING CAPACITORS', '+5V_IO', ('100nF', '1uF')),
                ('ADS124S08 DVDD / IOVDD DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF')),
            ],
            30, 150, max_column=300,
        )
        for part in sh.parts:
            if part.ref.startswith('C') and first < int(part.ref[1:]):
                role(part, 'core_decoupling')


def precision_port(sh, port, row):
    """One precision port: 4-pin header (excitation, IN+, IN-, GND), each input
    through 2.2 k and 10 nF to its ADC pin with 100 nF across the pair, and a
    surge clamp on both input pins.
    """
    sh.note(f'PRECISION PORT {port}', 20 * 1.27, (row - 14) * 1.27, 1.8)
    header = sh.add(
        'Connector_Generic:Conn_01x04', next_ref('J'), f'SENSOR {port} (EXC / IN+ / IN- / GND)',
        50 * 1.27, (row + 4) * 1.27, mirror=True, auto=False, footprint=X2510_4P,
    )
    role(header, 'prec_connector', p=port)
    # a plain label: the excitation's one sheet pin is at the switch
    io_label(sh, 'prec_exc', spur(sh, header, '1', 22), 0, is_global=False)
    drop_ground(sh, spur(sh, header, '4', 2), 2)
    # each input: header pin, surge clamp at the connector end, 2.2 k, 10 nF,
    # ADC. IN+ runs straight on from its pin; IN- steps down so the 100 nF fits
    # across the pair, and the clamps sit outside the pair
    top = pin_cell(header, '2')[1]
    for index, (pin, pin_key, adc_key, turn, clamp_row) in enumerate((
        ('2', 'prec_p_pin', 'prec_p', None, top - 16), ('3', 'prec_n_pin', 'prec_n', 86, top + 28),
    )):
        line = top + 16 * index
        start = spur(sh, header, pin, 4)
        io_label(sh, pin_key, start, 0, is_global=False, p=port)
        if turn:
            wire(sh, start, (turn, start[1]), (turn, line))
            start = (turn, line)
        wire(sh, start, (117, line))
        role(hres(sh, '2.2k', 120, line), 'prec_series', p=port)
        wire(sh, (123, line), (126, line), (134, line), (142, line))
        io_label(sh, adc_key, (142, line), 0, p=port)
        role(vcap(sh, '10nF', 134, line), 'prec_filter', p=port)
        drop_ground(sh, (134, line + 6), 2)
        clamp = role(
            place_ic(sh, 'cryocooler:TVS1800DRV', 'TVS1800DRVR', 100, clamp_row, TVS1800_FP,
                     ref_prefix='D'),
            'prec_clamp', p=port,
        )
        tap = spur(sh, clamp, '4', 4)
        wire(sh, tap, (tap[0], line))
        drop_ground(sh, pin_cell(clamp, '1'), 2)
    role(vcap(sh, '100nF', 126, top + 5), 'prec_diff_filter', p=port)
    wire(sh, (126, top), (126, top + 5))
    wire(sh, (126, top + 11), (126, top + 16))


def build_io_precision(sh):
    """Hand-laid: two precision sensor ports on the ADC's four spare inputs, their
    shared switched 5 V excitation, and its return to the ADC as a reference.
    """
    sh.handwired = True
    sh.note(
        'Two ports for sensors the universal channels suit badly: bridges (load cells, '
        'bare pressure sensors), RTDs, thermocouples, millivolt cells. Each has a '
        'differential pair straight into the ADS124S08 (port A: AIN8 / AIN9, port B: '
        'AIN10 / AIN11).',
        20, 15,
    )
    sh.note(
        'Gain, the 10 uA-2 mA current sources, the thermocouple bias and burn-out '
        'detection are ADC register settings. The 5 V excitation also feeds REFP0 / REFN0, '
        'so a bridge read against that reference ignores drift in the 5 V rail.',
        20, 21,
    )
    sh.note(
        'Inputs must stay between 0 V and 5 V. 2.2 k limits the current into the ADC to '
        '3 mA with 12 V on a pin (10 mA allowed), so a wiring mistake does no damage; the '
        'reading of every ADC input is disturbed while it lasts. Excitation is off until '
        'PREC_EXC_EN is high.',
        20, 27,
    )
    with io_refs():
        sh.note('EXCITATION (BOTH PORTS)', 20 * 1.27, 44 * 1.27, 1.8)
        fuse = role(
            place_ic(sh, 'cryocooler:TPS26625DRC', 'TPS26625DRCR', 70, 64,
                     'Package_SON:Texas_DRC0010J'),
            'prec_switch',
        )
        wire(sh, pin_cell(fuse, '1'), (54, 58), (46, 58), (38, 58))
        rail_symbol(sh, '+5V_IO', (38, 58))
        role(vres(sh, '1M', 54, 58), 'prec_uvlo')
        wire(sh, (54, 64), pin_cell(fuse, '2'))
        role(vcap(sh, '1uF', 42, 58), 'prec_in_cap')
        drop_ground(sh, (42, 64), 2)
        wire(sh, pin_cell(fuse, '4'), (52, 66), (52, 70), (38, 70))
        io_label(sh, 'prec_exc_en', (38, 70), 180)
        gnd_bus(sh, [pin_cell(fuse, pin) for pin in ('5', '6', '11')])
        wire(sh, pin_cell(fuse, '3'), (56, 68), (56, 76), (66, 76))
        wire(sh, pin_cell(fuse, '9'), (94, 60), (94, 74), (110, 74))
        io_label(sh, 'prec_exc_flt', (110, 74), 0)
        sh.nc(fuse, '8')
        wire(sh, pin_cell(fuse, '7'), (86, 64))
        role(vres(sh, '53.6k', 86, 64), 'prec_limit')
        drop_ground(sh, (86, 70), 2)
        # the switched excitation runs on past its clamp to the reference
        # network; the two ports and the pressure ports take it by label
        wire(sh, pin_cell(fuse, '10'), (112, 58), (167, 58))
        wire(sh, (122, 58), (122, 52), (126, 52))
        io_label(sh, 'prec_exc', (126, 52), 0)
        role(vcap(sh, '1uF', 112, 58), 'prec_out_cap')
        drop_ground(sh, (112, 64), 2)
        clamp = role(
            place_ic(sh, 'cryocooler:TVS1800DRV', 'TVS1800DRVR', 144, 74, TVS1800_FP,
                     ref_prefix='D'),
            'prec_exc_clamp',
        )
        tap = spur(sh, clamp, '4', 4)
        wire(sh, tap, (tap[0], 58))
        drop_ground(sh, pin_cell(clamp, '1'), 2)
        sh.note('EXCITATION AS THE ADC REFERENCE', 150 * 1.27, 44 * 1.27, 1.8)
        role(hres(sh, '1k', 170, 58), 'prec_ref_series')
        wire(sh, (173, 58), (180, 58), (188, 58))
        io_label(sh, 'prec_refp', (188, 58), 0)
        wire(sh, (164, 70), (167, 70))
        drop_ground(sh, (164, 70), 2)
        role(hres(sh, '1k', 170, 70), 'prec_ref_series')
        wire(sh, (173, 70), (180, 70), (188, 70))
        io_label(sh, 'prec_refn', (188, 70), 0)
        role(vcap(sh, '100nF', 180, 58), 'prec_ref_filter')
        wire(sh, (180, 64), (180, 70))
        precision_port(sh, 'A', 107)
        precision_port(sh, 'B', 176)
        pull_up_at(sh, '10k', (102, 74), 'pull_prec_flt')
        pull_down_at(sh, '22k', (47, 70), 'pull_prec_en')


def pressure_port(sh, n, row):
    """One pressure port: 4-pin header (5 V excitation, signal, GND, unused), the signal
    through 2.2 k and 10 nF to its ADC pin, a pull-down so an open port reads 0 V,
    and a surge clamp at the connector.
    """
    scale = PRESSURE_PORTS[n]
    sh.note(f'PRESSURE PORT {n} ({scale.upper()})', 20 * 1.27, (row - 14) * 1.27, 1.8)
    header = sh.add(
        'Connector_Generic:Conn_01x04', next_ref('J'), f'PRESSURE {n} (5V / SIG / GND / NC)',
        50 * 1.27, (row + 4) * 1.27, mirror=True, auto=False, footprint=X2510_4P,
    )
    sh.nc(header, '4')
    role(header, 'press_connector', n=n, scale=scale)
    io_label(sh, 'prec_exc', spur(sh, header, '1', 22), 0)
    start = spur(sh, header, '2', 4)
    io_label(sh, 'press_pin', start, 0, is_global=False, n=n)
    drop_ground(sh, spur(sh, header, '3', 2), 2)
    # the signal runs straight on from its header pin
    row = start[1]
    wire(sh, start, (117, row))
    role(hres(sh, '2.2k', 120, row), 'press_series', n=n)
    wire(sh, (123, row), (126, row), (138, row), (146, row))
    io_label(sh, 'press_adc', (146, row), 0, n=n)
    role(vres(sh, '100k', 126, row), 'press_pull', n=n)
    drop_ground(sh, (126, row + 6), 2)
    role(vcap(sh, '10nF', 138, row), 'press_filter', n=n)
    drop_ground(sh, (138, row + 6), 2)
    clamp = role(
        place_ic(sh, 'cryocooler:TVS1800DRV', 'TVS1800DRVR', 100, row - 16, TVS1800_FP,
                 ref_prefix='D'),
        'press_clamp', n=n,
    )
    tap = spur(sh, clamp, '4', 4)
    wire(sh, tap, (tap[0], row))
    drop_ground(sh, pin_cell(clamp, '1'), 2)


def build_io_pressure(sh):
    """Hand-laid: two ports for 5 V ratiometric pressure transmitters."""
    sh.handwired = True
    sh.note(
        'Two ports for 3-wire pressure transmitters with a 0.5-4.5 V output on a 5 V '
        'supply (port 1: 100 psi ahead of the nitrogen membrane, port 2: 30 psi in the '
        'dewar). Pin 1 is the switched 5 V excitation shared with the precision ports.',
        20, 15,
    )
    sh.note(
        'The ADC reads each signal against REFP0 / REFN0, which is that same excitation, '
        'so the reading does not move with the 5 V rail. PGA bypassed. With nothing '
        'plugged in the 100k pull-down gives 0 V, below the 0.5 V a working sensor sends.',
        20, 21,
    )
    with io_refs():
        for n in PRESSURE_PORTS:
            pressure_port(sh, n, 60 + 72 * (n - 1))


def driver_opamp(sh, ref, unit, column, row):
    """One unit of a TSB582 dual output driver."""
    return sh.add(
        'cryocooler:TSB582IQ2', ref, 'TSB582IQ2T', column * 1.27, row * 1.27, unit=unit,
        auto=False, footprint='Package_DFN_QFN:DFN-8-1EP_3x3mm_P0.65mm_EP1.55x2.4mm',
    )


def build_io_drivers(sh):
    """Hand-laid: the four output drivers as two dual op amps, each output through
    one section of a fault-protected switch to its channel pin.
    """
    sh.handwired = True
    sh.note(
        'Output drivers: each TSB582 section multiplies its channel level by 1 + 191k / '
        '49.9k = 4.83 (0-12 V from +12V). A TMUX7412F section joins it to the pin while '
        'OUT_EN is high. Feedback is taken ahead of the switch.',
        20, 15,
    )
    sh.note(
        'Open, the switch leaves only leakage on the pin. It also opens by itself when '
        'the pin is forced above +12V or below ground (FF goes low), so an outside source '
        'cannot feed the 12 V rail. Up to 100 mA per output: the switch rating (the op amp '
        'gives 150 mA min).',
        20, 21,
    )
    sh.note(
        'At 100 mA the pin sits about 1.5 V under the rail (0.55 V typ in the op amp, about '
        '1 V in the 8-11 ohm switch). The ADC reads every pin, so firmware can check it. '
        'Channels 1 and 2 take their level from the GPIO gate on their own sheet.',
        20, 27,
    )
    with io_refs():
        for half, group in enumerate('AB'[:IO_CHANNELS // 4]):
            column = 20 + 150 * half
            channels = range(4 * half + 1, 4 * half + 5)
            sh.note(f'CHANNELS {channels[0]}-{channels[-1]}', column * 1.27, 44 * 1.27, 1.8)
            amp_refs = (next_ref('U'), next_ref('U'))
            outputs = {}
            for index, n in enumerate(channels):
                row = 58 + 34 * index
                unit = index % 2 + 1
                plus, minus, out = DRIVER_OPAMP_PINS[unit]
                amp = driver_opamp(sh, amp_refs[index // 2], unit, column + 50, row)
                if unit == 1:
                    role(amp, 'amp', first=n, last=n + 1)
                level = pin_cell(amp, plus)
                wire(sh, level, (level[0] - 14, level[1]))
                io_label(sh, 'level' if n in IO_FAST else 'dac', (level[0] - 14, level[1]),
                         180, n=n)
                invert, drive = pin_cell(amp, minus), pin_cell(amp, out)
                node = (invert[0] - 4, invert[1])
                wire(sh, (node[0] - 4, node[1]), node, invert)
                role(hres(sh, '49.9k', node[0] - 7, node[1]), 'gain_low', n=n)
                drop_ground(sh, (node[0] - 10, node[1]), 2)
                centre = column + 50
                wire(sh, node, (node[0], row + 10), (centre - 6, row + 10), (centre - 3, row + 10))
                role(hres(sh, '191k', centre, row + 10), 'gain_high', n=n)
                wire(sh, (centre + 3, row + 10), (centre + 6, row + 10), (drive[0] + 4, row + 10),
                     (drive[0] + 4, drive[1]))
                wire(sh, (centre - 6, row + 10), (centre - 6, row + 16), (centre - 3, row + 16))
                role(hcap(sh, '2pF/C0G', centre, row + 16), 'gain_cap', n=n)
                wire(sh, (centre + 3, row + 16), (centre + 6, row + 16), (centre + 6, row + 10))
                wire(sh, drive, (drive[0] + 4, drive[1]), (drive[0] + 16, drive[1]))
                io_label(sh, 'drv', (drive[0] + 5, drive[1]), 0, is_global=False, n=n)
                outputs[n] = (drive[0] + 16, drive[1])
            for index, amp_ref in enumerate(amp_refs):
                power = driver_opamp(sh, amp_ref, 3, column + 160 + 16 * index, 62)
                supply = pin_cell(power, '8')
                wire(sh, supply, (supply[0], supply[1] - 2))
                rail_symbol(sh, '+12V', (supply[0], supply[1] - 2))
                gnd_bus(sh, [pin_cell(power, '4'), pin_cell(power, '9')])
            switch = role(
                place_ic(
                    sh, 'cryocooler:TMUX7412FRRP_DRV', 'TMUX7412FRRPR', column + 130, 132,
                    'Package_DFN_QFN:Texas_RUM0016A_WQFN-16-1EP_4x4mm_P0.65mm_EP2.6x2.6mm',
                ),
                'out_switch', first=channels[0], last=channels[-1],
            )
            for n, source, select, drain in zip(
                channels, ('1', '12', '9', '4'), ('15', '14', '7', '6'),
                ('16', '13', '8', '5'),
            ):
                # drains and selects face left, the pins and the fault flag right
                io_label(sh, 'pin', spur(sh, switch, source, 6), 0, n=n)
                select_line(sh, switch, select, 'out_en', n=n)
            fan(sh, [(None, outputs[n], pin_cell(switch, drain))
                     for n, drain in zip(channels, ('16', '13', '8', '5'))],
                outputs[channels[0]][0] + 4)
            flag = pin_cell(switch, '10')
            wire(sh, flag, (flag[0] + 26, flag[1]))
            io_label(sh, 'out_flt', (flag[0] + 26, flag[1]), 0, g=group)
            supply = pin_cell(switch, '11')
            wire(sh, supply, (supply[0], supply[1] - 4))
            rail_symbol(sh, '+12V', (supply[0], supply[1] - 4))
            gnd_bus(sh, [pin_cell(switch, pin) for pin in ('2', '3', '17')])
            for n in channels:
                pull_down_at(sh, '100k', taps(sh)[('out_en', n)], 'pull_out_en', small=True, n=n)
            pull_up_at(sh, '10k', (flag[0] + 20, flag[1]), 'pull_out_flt', g=group)
        first = kicadgen._ref_counters['C']
        place_blocks(
            sh,
            [
                ('TSB582 DECOUPLING', '+12V', ('100nF', '100nF', '10uF/25V')),
            ],
            84, 206, max_column=240,
        )
        place_blocks(
            sh, [('OUTPUT SWITCH DECOUPLING', '+12V', ('100nF',))], 258, 160,
            max_column=310,
        )
        for part in sh.parts:
            if part.ref.startswith('C') and first < int(part.ref[1:]):
                role(part, 'driver_decoupling')


def build_io_switches(sh):
    """Hand-laid: the range switch (divider legs to ground) and the pull-up
    switch of the four channels.
    """
    sh.handwired = True
    sh.note(
        'Range: TMUX1111 closes while its select is low, grounding the 20k divider leg '
        '(0-15 V range). DIRECT high opens it. The switch only ever sees the ADC-side '
        'voltage, never the pin.',
        20, 15,
    )
    sh.note(
        'Pull-up: TMUX7412F on +12 V joins the pin to 10k / +3V3 while PULLUP is high. Its '
        'source pins block in both directions and survive +-60 V, so a pin above 3.3 V '
        'is not loaded while the switch is open. FF (fault flag) is not used.',
        20, 21,
    )
    with io_refs():
        for index in range(IO_CHANNELS // 4):
            column = 70 + 150 * index
            channels = range(4 * index + 1, 4 * index + 5)
            sh.note(f'RANGE SWITCH, CHANNELS {channels[0]}-{channels[-1]}',
                    (column - 40) * 1.27, 36 * 1.27, 1.8)
            leg = role(
                place_ic(sh, 'cryocooler:TMUX1111RSV', 'TMUX1111RSVR', column, 70,
                         'Package_DFN_QFN:UQFN-16_1.8x2.6mm_P0.4mm'),
                'range_switch', first=channels[0], last=channels[-1],
            )
            for n, source, select in zip(channels, ('1', '12', '9', '4'),
                                         ('15', '14', '7', '6')):
                io_label(sh, 'div', spur(sh, leg, source, 6), 180, n=n)
                select_line(sh, leg, select, 'direct', n=n)
            drains = [spur(sh, leg, pin, 4) for pin in ('16', '13', '8', '5')]
            wire(sh, drains[0], (drains[0][0], drains[-1][1] + 6))
            drop_ground(sh, (drains[0][0], drains[-1][1] + 6), 2)
            sh.nc(leg, '2')
            sh.nc(leg, '10')
            supply = pin_cell(leg, '11')
            wire(sh, supply, (supply[0], supply[1] - 4))
            rail_symbol(sh, '+5V_IO', (supply[0], supply[1] - 4))
            drop_ground(sh, pin_cell(leg, '3'), 2)

            sh.note(f'PULL-UP SWITCH, CHANNELS {channels[0]}-{channels[-1]}',
                    (column - 40) * 1.27, 116 * 1.27, 1.8)
            pull = role(
                place_ic(
                    sh, 'cryocooler:TMUX7412FRRP', 'TMUX7412FRRPR', column, 152,
                    'Package_DFN_QFN:Texas_RUM0016A_WQFN-16-1EP_4x4mm_P0.65mm_EP2.6x2.6mm',
                ),
                'pull_switch', first=channels[0], last=channels[-1],
            )
            for n, source, select, drain in zip(
                channels, ('1', '12', '9', '4'), ('15', '14', '7', '6'),
                ('16', '13', '8', '5'),
            ):
                io_label(sh, 'pin', spur(sh, pull, source, 6), 180, n=n)
                select_line(sh, pull, select, 'pullup', n=n)
                end = spur(sh, pull, drain, 4)
                role(hres(sh, '10k', end[0] + 3, end[1]), 'pull_resistor', n=n)
                wire(sh, (end[0] + 6, end[1]), (end[0] + 16, end[1]))
            top = pin_cell(pull, '16')
            rail = (top[0] + 20, top[1])
            wire(sh, rail, (rail[0], pin_cell(pull, '5')[1]))
            wire(sh, rail, (rail[0], rail[1] - 3))
            rail_symbol(sh, '+3V3', (rail[0], rail[1] - 3))
            sh.nc(pull, '10')
            supply = pin_cell(pull, '11')
            wire(sh, supply, (supply[0], supply[1] - 4))
            rail_symbol(sh, '+12V', (supply[0], supply[1] - 4))
            gnd_bus(sh, [pin_cell(pull, pin) for pin in ('2', '3', '17')])
        # every select is pulled to its default on its own line
        for n in range(1, IO_CHANNELS + 1):
            pull_down_at(sh, '100k', taps(sh)[('direct', n)], 'pull_direct', small=True, n=n)
            pull_down_at(sh, '100k', taps(sh)[('pullup', n)], 'pull_pullup', small=True, n=n)
        first = kicadgen._ref_counters['C']
        place_blocks(
            sh,
            [
                ('TMUX1111 DECOUPLING CAPACITORS', '+5V_IO', ('100nF',)),
                ('TMUX7412F DECOUPLING CAPACITORS', '+12V', ('100nF',)),
            ],
            30, 206, max_column=300,
        )
        for part in sh.parts:
            if part.ref.startswith('C') and first < int(part.ref[1:]):
                role(part, 'switch_decoupling')


def build_io_expanders(sh):
    """Hand-laid: two MCP23S17 on one chip select, one port per channel."""
    sh.handwired = True
    sh.note(
        'Two MCP23S17 share IO_EXP_CS: hardware addresses 0 and 1 on A0 (A2 low on both, so '
        'one write of IOCON.HAEN reaches every device: errata DS80311A). Port A serves the '
        'odd channel of a pair, port B the even one.',
        20, 15,
    )
    sh.note(
        'Per port: bit 0 OUT_EN, 1 DIRECT (channel 1: on address 1 GPB5), 2 BURDEN, 3 PULLUP, '
        '4 SENS_EN (outputs), 5 OUT_FLT_N (channel 1; elsewhere a spare), 6 SENS_FLT_N (inputs),',
        20, 21,
    )
    sh.note(
        '7 BUF_OE_N (fast channels 1 and 2; the RS-485 and header interrupts on 3 and 4). All '
        'pins are inputs after reset, so the pull resistors on each line set the off state.',
        20, 27,
    )
    sh.note(
        'RESET on ESP_EN: an ESP32 reset also returns every channel to off.',
        20, 33,
    )
    sh.note(
        'INTA and INTB must be set open drain (IOCON.ODR) before interrupts are enabled: all '
        'four share IO_EXP_INT_N, pulled up at address 0.',
        20, 39,
    )
    with io_refs():
        for index in range(IO_CHANNELS // 2):
            column = 60 + 70 * index
            expander = role(
                place_ic(sh, 'cryocooler:MCP23S17-E/ML', 'MCP23S17-E/ML', column, 100,
                         'Package_DFN_QFN:QFN-28-1EP_6x6mm_P0.65mm_EP4.25x4.25mm'),
                'expander', a=2 * index + 1, b=2 * index + 2, address=index,
            )
            sh.note(f'ADDRESS {index}', (column - 30) * 1.27, 64 * 1.27, 1.8)
            spi_bus(
                sh,
                [(spur(sh, expander, pin, 2), net)
                 for pin, net in (('8', 'SPI_SCK'), ('9', 'SPI_MOSI'), ('10', 'SPI_MISO'))],
                column - 26, -1, [(column - 26, 70), (column - 30, 70)],
            )
            # the two expanders are 89 mm apart, so each has its own entry of
            # the one chip select that comes down from the parent
            io_label(sh, 'exp_cs', spur(sh, expander, '7', 6), 180, is_global=False,
                     to_parent=True)
            net_label(sh, 'ESP_EN', spur(sh, expander, '14', 6), 180, is_global=True)
            for bit, pin in enumerate(('11', '12', '13')):
                if index >> bit & 1:
                    # a high bit stands in the same column as the grounded ones
                    end = spur(sh, expander, pin, 4)
                    wire(sh, end, (end[0], end[1] - 2))
                    rail_symbol(sh, '+3V3', (end[0], end[1] - 2))
                else:
                    drop_ground(sh, spur(sh, expander, pin, 4), 2)
            first_int, second_int = spur(sh, expander, '16', 4), spur(sh, expander, '15', 4)
            # the shared interrupt's pull-up sits on address 0's wire
            reach = 4 if index else 16
            wire(sh, first_int, second_int, (second_int[0] - reach, second_int[1]))
            io_label(sh, 'exp_int', (second_int[0] - reach, second_int[1]), 180)
            if not index:
                column, top = second_int[0] - 10, second_int[1] - 6
                role(vres(sh, '10k', column, top), 'pull_exp_int')
                rail_symbol(sh, '+3V3', (column, top))
            pins = ('17', '18', '19', '20', '21', '22', '23', '24',
                    '25', '26', '27', '28', '1', '2', '3', '4')
            keys = ('out_en', 'direct', 'burden', 'pullup', 'sens_en', 'amp_flt',
                    'sens_flt', 'buf_oe')
            for position, pin in enumerate(pins):
                n = 2 * index + 1 + position // 8
                key = keys[position % 8]
                if key == 'buf_oe' and n in IO_SPARE_INPUTS:
                    io_label(sh, IO_SPARE_INPUTS[n], spur(sh, expander, pin, 4), 0)
                    continue
                if key == 'buf_oe' and n not in IO_FAST:
                    sh.nc(expander, pin)
                    continue
                if key == 'direct' and n in IO_DIRECT_PORT:
                    sh.nc(expander, pin)
                    continue
                moved = [c for c, port in IO_DIRECT_PORT.items() if port == n]
                if key == 'amp_flt' and moved:
                    io_label(sh, 'direct', spur(sh, expander, pin, 4), 0, n=moved[0])
                    continue
                if key == 'amp_flt':
                    # one flag per output switch (four channels): on the first channel
                    if n in IO_DRIVER_FLAGS:
                        io_label(sh, 'out_flt', spur(sh, expander, pin, 4), 0,
                                 g=IO_DRIVER_FLAGS[n])
                    elif n in IO_SPARE_FLAGS:
                        io_label(sh, IO_SPARE_FLAGS[n], spur(sh, expander, pin, 4), 0)
                    else:
                        sh.nc(expander, pin)
                    continue
                io_label(sh, key, spur(sh, expander, pin, 4), 0, n=n)
            supply = pin_cell(expander, '5')
            wire(sh, supply, (supply[0], supply[1] - 4))
            rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
            gnd_bus(sh, [pin_cell(expander, '6'), pin_cell(expander, '29')])
        first = kicadgen._ref_counters['C']
        place_blocks(
            sh,
            [('MCP23S17 DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF'))],
            100, 154, max_column=300,
        )
        for part in sh.parts:
            if part.ref.startswith('C') and first < int(part.ref[1:]):
                role(part, 'expander_decoupling')


def pin_offset(lib_id, pin):
    """Cell offset of a symbol's pin from its centre (unrotated)."""
    for number, _name, x, y, *_rest in sexpr.pins(kicadgen.get_symbol(lib_id)):
        if number == pin:
            return (round(x / 1.27), round(-y / 1.27))
    raise KeyError(pin)


def expansion_rs485(sh):
    """SC16IS750 SPI-UART bridge -> THVD2410 -> 3-pin header (A, B, GND)."""
    sh.note('RS-485 / MODBUS PORT', 20 * 1.27, 54 * 1.27, 1.8)
    bridge = role(
        place_ic(sh, 'cryocooler:SC16IS750IBS', 'SC16IS750IBS', 82, 84,
                 'Package_DFN_QFN:HVQFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm'),
        'uart',
    )
    spi_bus(
        sh,
        [(spur(sh, bridge, pin, 2), net)
         for pin, net in (('9', 'SPI_SCK'), ('7', 'SPI_MOSI'), ('8', 'SPI_MISO'))],
        42, -1, [(42, 60), (38, 60)],
    )
    io_label(sh, 'rs485_cs', spur(sh, bridge, '6', 12), 180, is_global=False, to_parent=True)
    net_label(sh, 'ESP_EN', spur(sh, bridge, '1', 12), 180, is_global=True)
    # the interrupt runs past the labels above it, so its pull-up has room
    interrupt = pin_cell(bridge, '11')
    wire(sh, interrupt, (EXP_IRQ_END, interrupt[1]))
    io_label(sh, 'rs485_irq', (EXP_IRQ_END, interrupt[1]), 180)
    drop_ground(sh, spur(sh, bridge, '5', 4), 2)
    for pin in ('3', '12', '13', '14', '15', '17', '18', '19', '20'):
        sh.nc(bridge, pin)
    drop_ground(sh, spur(sh, bridge, '22', 4), 2)
    supply = pin_cell(bridge, '4')
    wire(sh, supply, (supply[0], supply[1] - 4))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
    gnd_bus(sh, [pin_cell(bridge, pin) for pin in ('16', '10', '25')])
    receive, transmit, direction = (pin_cell(bridge, pin) for pin in ('24', '23', '21'))
    left = receive[0] + 40
    offset = pin_offset('cryocooler:THVD2410DRB', '1')
    phy = role(
        place_ic(sh, 'cryocooler:THVD2410DRB', 'THVD2410DRBR', left - offset[0],
                 receive[1] - offset[1], 'Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm'),
        'rs485_phy',
    )
    wire(sh, receive, (receive[0] + 20, receive[1]), pin_cell(phy, '1'))
    # R is high impedance while the driver is on: hold RX at the idle (high) level
    role(vres(sh, '10k', receive[0] + 20, receive[1] - 6), 'rs485_rx_pull')
    rail_symbol(sh, '+3V3', (receive[0] + 20, receive[1] - 6))
    wire(sh, transmit, pin_cell(phy, '4'))
    # RTS is high (inactive) after reset: the FET inverts it, so DE is low (receive)
    # until the UART sends
    enable, receive_enable = pin_cell(phy, '3'), pin_cell(phy, '2')
    node = (enable[0] - 4, receive_enable[1])
    wire(sh, enable, (node[0], enable[1]), node, receive_enable)
    drain = (node[0], node[1] + 12)
    wire(sh, node, drain)
    inverter = sh.add(
        'Transistor_FET:BSS138', next_ref('Q'), 'CSD17381F4', (drain[0] - 2) * 1.27,
        (drain[1] + 4) * 1.27, auto=False, footprint=FEMTOFET_FP,
    )
    role(inverter, 'rs485_inverter')
    drop_ground(sh, pin_cell(inverter, '2'), 2)
    gate = pin_cell(inverter, '1')
    wire(sh, direction, (direction[0] + 2, direction[1]), (direction[0] + 18, direction[1]),
         (direction[0] + 18, gate[1]), gate)
    io_label(sh, 'rs485_rts', (direction[0] + 2, direction[1]), 0, is_global=False)
    # the pull-up stands above a stub off the drain node
    rail_symbol(sh, '+3V3', (drain[0] - 6, drain[1] - 6))
    role(vres(sh, '10k', drain[0] - 6, drain[1] - 6), 'rs485_de_pull')
    wire(sh, (drain[0] - 6, drain[1]), drain)
    supply = pin_cell(phy, '8')
    wire(sh, supply, (supply[0], supply[1] - 4))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 4))
    gnd_bus(sh, [pin_cell(phy, '5'), pin_cell(phy, '9')])
    # bus pair: A up and over, B down and under, the switched 120 R between them
    line_a, line_b = pin_cell(phy, '6'), pin_cell(phy, '7')
    right, top, bottom = line_a[0], line_a[1] - 8, line_b[1] + 10
    header = conn(
        sh, 'Connector_Generic:Conn_01x04', 'RS-485 (A / B / GND / NC)', (right + 40) * 1.27,
        (line_a[1] + 2) * 1.27, {'4': None}, PH_V4,
    )
    role(header, 'rs485_connector')
    wire(sh, line_a, (right + 6, line_a[1]), (right + 6, top), (right + 16, top),
         (right + 32, top), (right + 32, line_a[1]), pin_cell(header, '1'))
    wire(sh, line_b, (right + 4, line_b[1]), (right + 4, bottom), (right + 16, bottom),
         (right + 28, bottom), (right + 28, line_b[1]), pin_cell(header, '2'))
    role(vres(sh, '120', right + 16, top, fp=R1206), 'rs485_termination')
    jumper = sh.add(
        'Jumper:Jumper_2_Open', next_ref('JP'), 'RS485 TERM', (right + 16) * 1.27,
        (top + 14) * 1.27, rot=90, auto=False, footprint=SWITCH_HEADER,
    )
    jumper.dnp = True
    role(jumper, 'rs485_term_jumper')
    ends = sorted((pin_cell(jumper, '1'), pin_cell(jumper, '2')), key=lambda cell: cell[1])
    wire(sh, (right + 16, top + 6), ends[0])
    wire(sh, ends[1], (right + 16, bottom))
    ground_pin = pin_cell(header, '3')
    wire(sh, ground_pin, (ground_pin[0] - 2, ground_pin[1]))
    drop_ground(sh, (ground_pin[0] - 2, ground_pin[1]), 2)
    # UART clock, wired straight into XTAL1. The net is named globally on the
    # board, so it keeps one global label as its name tag
    sh.note('UART CLOCK', 12 * 1.27, 92 * 1.27, 1.8)
    clock = role(
        place_ic(sh, 'cryocooler:ECS-2520MV', 'ECS-2520MV-160-BN-TR', 34, 106,
                 'Oscillator:Oscillator_SMD_ECS_2520MV-xxx-xx-4Pin_2.5x2.0mm'),
        'uart_clock',
    )
    enable, supply = pin_cell(clock, '1'), pin_cell(clock, '4')
    wire(sh, enable, (enable[0], enable[1] - 3), (supply[0], supply[1] - 3), supply)
    wire(sh, (supply[0], supply[1] - 3), (supply[0], supply[1] - 5))
    rail_symbol(sh, '+3V3', (supply[0], supply[1] - 5))
    drop_ground(sh, pin_cell(clock, '2'), 2)
    out, crystal = pin_cell(clock, '3'), pin_cell(bridge, '2')
    wire(sh, out, (52, out[1]), (52, crystal[1]), crystal)
    wire(sh, (52, out[1]), (55, out[1]))
    io_label(sh, 'uart_clk', (55, out[1]), 0, is_global=False)
    return interrupt


# Row of the SPI expansion header's pin 1, the column where the interrupt
# from the RS-485 bridge ends in its label, and the column of the pull-ups on
# the two interrupt lines.
EXP_HEADER_ROW = 142
EXP_IRQ_END = 30


def expansion_header(sh):
    """10-pin JST PH header with the SPI bus, two chip selects, an interrupt line and
    both logic supplies. Each chip select opens one buffer onto SPI_MISO. The header
    is on the right; its lines fan out to the series resistors and the two buffers.
    Returns the cells where the interrupt's pull-up and MISO's pull-down hang.
    """
    top = EXP_HEADER_ROW
    clock_row, data_row, return_row = top - 26, top - 18, top - 10
    select_rows = (top + 20, top + 46)
    sh.note('SPI EXPANSION HEADER', 196 * 1.27, (top - 42) * 1.27, 1.8)
    sh.note('100 R in series with every line the board drives', 196 * 1.27,
            (top - 38) * 1.27, 1.5)
    gates = []
    for index, row in enumerate((top + 8, top + 34)):
        gate = role(
            place_ic(sh, 'cryocooler:SN74LVC1G125DRY', 'SN74LVC1G125DRYR', 216, row, BUFFER_FP),
            'exp_miso_gate', which='AB'[index],
        )
        sh.nc(gate, '5')
        supply = pin_cell(gate, '6')
        wire(sh, supply, (supply[0], supply[1] - 3))
        rail_symbol(sh, '+3V3', (supply[0], supply[1] - 3))
        drop_ground(sh, pin_cell(gate, '3'), 2)
        spi_bus(sh, [(spur(sh, gate, '4', 2), 'SPI_MISO')], 242, -1,
                [(242, row - 8), (246, row - 8)])
        gates.append(gate)
    for key, row in (('exp_sck', clock_row), ('exp_mosi', data_row)):
        role(hres(sh, '100', 262, row), 'exp_series')
        io_label(sh, key, (267, row), 0, is_global=False)
    spi_bus(sh, [((259, clock_row), 'SPI_SCK'), ((259, data_row), 'SPI_MOSI')], 240, -1,
            [(240, top - 32), (236, top - 32)], label_at=3)
    for gate, key, enable, row in zip(gates, ('exp_csa', 'exp_csb'),
                                      ('exp_cs_a', 'exp_cs_b'), select_rows):
        io_label(sh, enable, (202, row), 180, is_global=False, to_parent=True)
        wire(sh, (202, row), (259, row))
        role(hres(sh, '100', 262, row), 'exp_series')
        io_label(sh, key, (267, row), 0, is_global=False)
        enable_pin = pin_cell(gate, '1')
        wire(sh, enable_pin, (enable_pin[0], row))
    header = conn(
        sh, 'Connector_Generic:Conn_01x10', 'SPI EXPANSION', 304 * 1.27, (top + 8) * 1.27,
        {}, PH_V10,
    )
    role(header, 'exp_header')
    for pin, rail, length in (('1', '+3V3', 4), ('2', '+5V', 12)):
        end = spur(sh, header, pin, length)
        wire(sh, end, (end[0], end[1] - 3))
        rail_symbol(sh, rail, (end[0], end[1] - 3))
    # each line turns off the header one column further left than the one above
    # (below, for the chip selects), so none crosses another
    for pin, column, row in (('3', 282, clock_row), ('4', 278, data_row),
                             ('7', 288, select_rows[0]), ('8', 292, select_rows[1])):
        tip = pin_cell(header, pin)
        wire(sh, tip, (column, tip[1]), (column, row), (265, row))
    # MISO from the cable runs over the top and down the left to both buffers
    tip = pin_cell(header, '5')
    inputs = [pin_cell(gate, '2') for gate in gates]
    wire(sh, tip, (274, tip[1]), (274, return_row), (184, return_row),
         (184, inputs[1][1]), inputs[1])
    wire(sh, (184, inputs[0][1]), inputs[0])
    io_label(sh, 'exp_miso', (250, return_row), 0, is_global=False)
    foot = (184, inputs[1][1] + 2)
    wire(sh, (184, inputs[1][1]), foot)
    interrupt = pin_cell(header, '6')
    wire(sh, interrupt, (258, interrupt[1]))
    io_label(sh, 'hdr_int', (258, interrupt[1]), 180)
    upper, lower = (spur(sh, header, pin, 4) for pin in ('9', '10'))
    wire(sh, upper, lower)
    drop_ground(sh, lower, 2)
    return (266, interrupt[1]), foot


# last references before the rev 6 AUX header, so it shifts no other part
REV6_AUX_AFTER = {'R': 691, 'U': 122, 'J': 39}


def expansion_aux(sh):
    """5-pin header with GPIO11 and GPIO13 and both logic supplies. Each line has
    100 R in series, an ESD clamp on the cable side and an unfitted pull-up, so
    firmware can use the pair as a UART, I2C, 1-Wire, touch or plain GPIO.
    """
    sh.note('AUX HEADER: GPIO11 AND GPIO13', 60 * 1.27, 124 * 1.27, 1.8)
    sh.note('UART, I2C, 1-Wire, touch or GPIO', 60 * 1.27, 128 * 1.27, 1.5)
    rows = {11: 142, 13: 166}
    for gpio, row in rows.items():
        net_label(sh, f'AUX_IO{gpio}', (66, row), 180, is_global=True)
        wire(sh, (66, row), (72, row))
        role(hres(sh, '100', 75, row), 'aux_series', gpio=gpio)
        net_label(sh, f'AUX{gpio}_HDR', (108, row), 0)
        clamp = sh.add(
            'cryocooler:TPD1E05U06DPYR', next_ref('U'), 'TPD1E05U06DPYR', 90 * 1.27,
            (row + 6) * 1.27, auto=False, footprint='Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm',
        )
        role(clamp, 'aux_clamp', gpio=gpio)
        wire(sh, (84, row), pin_cell(clamp, '1'))
        drop_ground(sh, pin_cell(clamp, '2'), 2)
        pull = role(vres(sh, '4.7k', 102, row - 6), 'aux_pull', gpio=gpio)
        pull.dnp = True
        rail_symbol(sh, '+3V3', (102, row - 6))
    header = conn(
        sh, 'Connector_Generic:Conn_01x05', 'AUX (5V / 3V3 / IO11 / IO13 / GND)', 150 * 1.27,
        152 * 1.27, {}, PH_V5,
    )
    role(header, 'aux_header')
    for pin, rail, length in (('1', '+5V', 4), ('2', '+3V3', 12)):
        end = spur(sh, header, pin, length)
        wire(sh, end, (end[0], end[1] - 3))
        rail_symbol(sh, rail, (end[0], end[1] - 3))
    # both lines run straight to the header and turn onto their pins
    for pin, gpio, column in (('3', 11, 128), ('4', 13, 132)):
        tip = pin_cell(header, pin)
        wire(sh, (78, rows[gpio]), (column, rows[gpio]), (column, tip[1]), tip)
    drop_ground(sh, spur(sh, header, '5', 4), 2)


def build_expansion(sh):
    """Hand-laid: the RS-485 port on the left, the SPI expansion header on the
    right. The AUX header has its own sheet (build_aux_header)."""
    sh.handwired = True
    sh.note(
        'RS-485: SC16IS750 (SPI mode 0 only, 4 MHz max) with the same 16 MHz oscillator as '
        'the signal generator: 9600, 19200 and 38400 baud are 0.16 % off; 57600 (2.1 %) and '
        '115200 (3.5 %) are not usable. Direction: EFCR.RTSCON = 1, RTSINVER = 0.',
        20, 15,
    )
    sh.note(
        'RTS goes low while sending, and the FET turns that into DE high. After reset RTS '
        'is high, so the driver is off. CTS and the bridge GPIOs are unused.',
        20, 21,
    )
    sh.note(
        'THVD2410: fail-safe receiver, +-70 V bus fault, +-12 kV IEC ESD, so no bias '
        'resistors and no extra clamp. Fit the jumper to end the bus with 120 R here.',
        20, 27,
    )
    sh.note(
        'SPI expansion header: 1 +3V3, 2 +5V, 3 SCK, 4 MOSI, 5 MISO, 6 INT (active low, to '
        'the I/O expander), 7 CS A, 8 CS B, 9 and 10 GND. MISO reaches the bus only while '
        'a chip select is low.',
        20, 33,
    )
    with io_refs():
        bridge_interrupt = expansion_rs485(sh)
        header_interrupt, miso_foot = expansion_header(sh)
        # each pull hangs on the wire it biases
        for value, cell, key in (('1k', (EXP_IRQ_END + 6, bridge_interrupt[1]), 'pull_rs485_irq'),
                                 ('10k', header_interrupt, 'pull_exp_hdr_int')):
            role(vres(sh, value, cell[0], cell[1] - 6), key)
            rail_symbol(sh, '+3V3', (cell[0], cell[1] - 6))
        role(vres(sh, '100k', miso_foot[0], miso_foot[1]), 'pull_exp_miso')
        drop_ground(sh, (miso_foot[0], miso_foot[1] + 6), 0)
        first = kicadgen._ref_counters['C']
        place_blocks(
            sh,
            [
                ('SC16IS750 AND CLOCK DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF')),
                ('THVD2410 DECOUPLING CAPACITOR', '+3V3', ('100nF',)),
                ('MISO BUFFER DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF')),
            ],
            30, 204, max_column=300,
        )
        for part in sh.parts:
            if part.ref.startswith('C') and first < int(part.ref[1:]):
                role(part, 'expansion_decoupling')


def build_aux_header(sh):
    """Hand-laid: the 5-pin AUX header with GPIO11 and GPIO13. Split off the
    Expansion sheet, which was over 30 parts; built straight after it so the
    parts keep their numbers."""
    sh.handwired = True
    sh.note(
        'AUX header: 1 +5V, 2 +3V3, 3 GPIO11, 4 GPIO13, 5 GND. Both pins are touch '
        '(T11, T13) and ADC2 inputs; ADC2 is not usable while WiFi is on.',
        20, 15,
    )
    marks = sheet_marks(sh)
    with kicadgen.pinned_refs('R', REV6_AUX_AFTER['R']), kicadgen.pinned_refs(
        'U', REV6_AUX_AFTER['U']
    ), kicadgen.pinned_refs('J', REV6_AUX_AFTER['J']):
        expansion_aux(sh)
    # drawn where it stood on the Expansion sheet; move it to the top left
    shift_since(sh, marks, -30, -84)


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
    ('ISO3', '+3V3', '+3V3_ISO', 'ISOLATED SUPPLY +3V3 IN (ISOW7841)'),
    ('COOL', '+3V3', '+3V3_COOL', 'WATER COOLING +3V3 (FAN, PUMP, FLOW, NTC)'),
    ('CH', '+3V3', '+3V3_CH', 'COLD HEAD +3V3 (ADS1220 RTD ADC)'),
    ('IO', '+5V', '+5V_IO', 'UNIVERSAL I/O ANALOG +5V (ADC, RANGE SWITCHES, EXCITATION)'),
)
kicadgen.POWER_SYMBOLS.update({spec[2]: spec[1] for spec in SWITCHES})
# The ADS1220 reference is ratiometric but its supply is shared with the buck, so
# the cold head feed gets a ferrite ahead of its jumper.
BEAD_AHEAD_OF_JUMPER = {'CH', 'IO'}


def supply_block(sh, spec, column, row):
    """Main rail -> jumper -> switched rail, with a PWR_FLAG on the switched rail."""
    key, main, switched, title = spec
    # a bead's text stands above the rail, so its heading sits higher
    heading = row - (8 if key in BEAD_AHEAD_OF_JUMPER else 6)
    sh.note(title, column * 1.27, heading * 1.27, 1.6)
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


def fan(sh, links, first):
    """Wires between two columns of pins that stand in the same order top to
    bottom: (net, left cell, right cell). Each wire takes its own riser from
    column `first`, two cells apart, lower wires turning first on the way down
    and upper ones first on the way up, so none crosses another. A named link
    carries its net label where it leaves the left pin.
    """
    down = sorted((l for l in links if l[2][1] > l[1][1]), key=lambda l: -l[1][1])
    up = sorted((l for l in links if l[2][1] < l[1][1]), key=lambda l: l[1][1])
    for group in (down, up):
        for slot, (_net, start, end) in enumerate(group):
            riser = first + 2 * slot
            wire(sh, start, (riser, start[1]), (riser, end[1]), end)
    for net, start, end in links:
        if start[1] == end[1]:
            wire(sh, start, end)
        if net:
            net_label(sh, net, (start[0] + 1, start[1]), 0)


def build_io(sh):
    """Parent of the universal I/O sheets (IO_BLOCKS): neighbouring columns are
    wired, far ones joined by net labels, and five nets go on to the root.
    """
    sh.handwired = True
    sh.note(
        'Universal I/O: four configurable channels (IO Channel 1 to 4) with their DAC '
        'and ADC, output drivers, range and pull-up switches and port expanders, plus '
        'the precision and pressure ports.',
        20,
        15,
    )
    sh.note(
        'Columns that stand next to each other are wired. A net between columns that '
        'are not neighbours carries the same net label at both ends.',
        20,
        21,
    )

    def pin(stem, net):
        return sheet_pin_cell(stem, net)

    def right_edge(stem):
        return IO_BLOCKS[stem][0][0] + BOX_SIZE[0]

    wired = set()

    def wires(source, target, nets, first):
        fan(sh, [(net, pin(source, net), pin(target, net)) for net in nets], first)
        wired.update((stem, net) for stem in (source, target) for net in nets)

    for column, heading in (
        ('io_expanders', 'CONTROL'), ('io_switches', 'RANGE'), ('io_ch1', 'CHANNELS'),
        ('io_drivers', 'OUTPUTS AND PORTS'), ('io_core', 'CONVERSION'),
    ):
        sh.note(heading, IO_BLOCKS[column][0][0] * 1.27, 28 * 1.27, 1.8)
    channels = list(IO_CHANNELS_ON_PAGE)
    # risers start past the labelled pins' stubs on the left block's edge
    # port expanders -> range and pull-up switches
    wires('io_expanders', 'io_switches', IO_SWITCH_LINES, right_edge('io_expanders') + 20)
    # switches -> channels: the connector pin and the divider tap. The pin
    # also reaches the drivers, too far for a wire: a label there.
    fan(sh, [(net, pin('io_switches', net), pin(f'io_ch{n}', net))
             for n in channels for net in (f'IO{n}_PIN', f'IO{n}_DIV')],
        right_edge('io_switches') + 18)
    wired.update((stem, net) for n in channels for stem in ('io_switches', f'io_ch{n}')
                 for net in (f'IO{n}_PIN', f'IO{n}_DIV'))
    # level shifter outputs of the fast channels -> drivers
    fan(sh, [(f'IO{n}_LEVEL', pin(f'io_ch{n}', f'IO{n}_LEVEL'), pin('io_drivers', f'IO{n}_LEVEL'))
             for n in IO_FAST], right_edge('io_ch1') + 20)
    wired.update((stem, f'IO{n}_LEVEL') for n in IO_FAST for stem in (f'io_ch{n}', 'io_drivers'))
    # drivers and analog ports -> DAC and ADC
    analog = [('io_drivers', net) for net in ('IO3_DAC', 'IO4_DAC')]
    analog += [('io_precision', net) for net in IO_PRECISION_INPUTS]
    analog += [('io_pressure', net) for net in ('PRESS1_ADC', 'PRESS2_ADC')]
    fan(sh, [(net, pin(stem, net), pin('io_core', net)) for stem, net in analog],
        right_edge('io_drivers') + 18)
    wired.update(analog)
    wired.update(('io_core', net) for _stem, net in analog)
    # excitation: precision ports down to the pressure ports
    start, end = pin('io_precision', 'PREC_EXC'), pin('io_pressure', 'PREC_EXC')
    wire(sh, start, (start[0] - 6, start[1]), (start[0] - 6, end[1]), end)
    net_label(sh, 'PREC_EXC', (start[0] - 6, end[1] - 2), 90)
    wired.update((stem, 'PREC_EXC') for stem in ('io_precision', 'io_pressure'))
    # everything else: a net label at the pin, or a hierarchical label for the
    # nets that go on to the root
    for stem, (_cell, left, right) in IO_BLOCKS.items():
        for side, nets in ((-1, left), (1, right)):
            for net in nets:
                if (stem, net) in wired:
                    continue
                tip = pin(stem, net)
                if net in IO_TO_ROOT:
                    end = (tip[0] + 2 * side, tip[1])
                    wire(sh, tip, end)
                    net_label(sh, net, end, 0 if side == 1 else 180, to_parent=True)
                else:
                    end_label(sh, net, tip, side)


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


def build_ambient(sh):
    """Hand-laid: ADT7320 SPI temperature sensor for the ambient reading."""
    sh.handwired = True
    sh.note(
        'ADT7320: SPI mode 3 (SCLK idles high), MSB first, on the main bus (CS from the '
        'decoder). DOUT is released within 80 ns of CS rising (datasheet Table 2, t7), so '
        'it shares SPI_MISO without a buffer. Pins 5-8 and 13-16 are not bonded: left '
        'open. Exposed pad to GND.',
        20,
        15,
    )
    sh.note(
        'INT and CT are open drain and need 10 k pull-ups; they go to expander GP2 and GP3. '
        'Place this part far from anything that warms the board.',
        20,
        21,
    )
    with kicadgen.pinned_refs('U', REV5_LAST['U']):
        sensor = place_ic(
            sh,
            'cryocooler:ADT7320UCPZ',
            'ADT7320UCPZ',
            80,
            70,
            'Package_DFN_QFN:UQFN-16-1EP_4x4mm_P0.65mm_EP2.6x2.6mm',
        )
    vdd = pin_cell(sensor, '12')
    wire(sh, vdd, (vdd[0], vdd[1] - 6))
    rail_symbol(sh, '+3V3', (vdd[0], vdd[1] - 6))
    gnd_bus(sh, [pin_cell(sensor, '11'), pin_cell(sensor, '17')])
    with kicadgen.pinned_refs('C', REV5_LAST['C']):
        place_blocks(
            sh,
            [('ADT7320 DECOUPLING CAPACITOR', '+3V3', ('100nF',))],
            150,
            100,
        )
    net_label(sh, 'AMBIENT_CS', spur(sh, sensor, '4', 12), 180, to_parent=True)
    spi_bus(
        sh,
        [
            (spur(sh, sensor, pin, 2), net)
            for pin, net in (('1', 'SPI_SCK'), ('3', 'SPI_MOSI'))
        ],
        42,
        -1,
        [(42, 56), (38, 56)],
    )
    spi_bus(sh, [(spur(sh, sensor, '2', 2), 'SPI_MISO')], 108, -1, [(108, 54), (112, 54)])
    # open-drain outputs: each pull-up stands above its own line, the lower
    # line's further out, past the upper line's label
    lines = sorted(
        ((pin_cell(sensor, pin), net) for pin, net in (('9', 'AMBIENT_INT'), ('10', 'AMBIENT_CT'))),
        key=lambda item: item[0][1],
    )
    reach = {net: 34 + 24 * index for index, (_tip, net) in enumerate(lines)}
    for index, net in enumerate(('AMBIENT_INT', 'AMBIENT_CT')):
        tip = next(cell for cell, name in lines if name == net)
        end = (tip[0] + reach[net], tip[1])
        wire(sh, tip, end)
        net_label(sh, net, end, 0, is_global=True)
        with kicadgen.pinned_refs('R', REV5_LAST['R'] + index):
            vres(sh, '10k', end[0] - 6, tip[1] - 6)
        rail_symbol(sh, '+3V3', (end[0] - 6, tip[1] - 6))


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
    ('Regulators +-15V', 'ldo_15v', build_ldo_15v, 'A3'),
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
    ('Ambient Temp', 'ambient', build_ambient, 'A3'),
]
SHEETS += [
    ('Universal IO', 'io', build_io, 'A2'),
    ('IO DAC and ADC', 'io_core', build_io_core, 'A3'),
    ('IO Output Drivers', 'io_drivers', build_io_drivers, 'A3'),
    ('IO Range and Pull-up', 'io_switches', build_io_switches, 'A3'),
    ('IO Expanders', 'io_expanders', build_io_expanders, 'A3'),
    ('IO Precision Ports', 'io_precision', build_io_precision, 'A3'),
    ('IO Pressure Ports', 'io_pressure', build_io_pressure, 'A3'),
    ('Expansion', 'expansion', build_expansion, 'A3'),
    ('AUX Header', 'aux_header', build_aux_header, 'A3'),
]
SHEETS += [
    (f'IO Channel {n}', f'io_ch{n}', build_io_channel(n), 'A3')
    for n in range(1, IO_CHANNELS + 1)
]


# Reference/Value positions in mm that the user set by hand in KiCad (b8e851e),
# keyed by sheet file, final reference and unit; text layout keeps them.
PINNED_FIELDS = {
    # below the connector: beside it the long value runs into the display outline
    ('display.kicad_sch', 'J15', 1): ((236.22, 110.49), (236.22, 112.59)),
    # the fast channels' buffer: text left of the VCC riser
    ('io_ch1.kicad_sch', 'U116', 1): ((72.39, 207.9), (72.39, 210.0)),
    ('io_ch2.kicad_sch', 'U119', 1): ((72.39, 207.9), (72.39, 210.0)),
    # NTC clamp unit: text on its left, clear of C23
    ('cooling.kicad_sch', 'U33', 4): ((82.43, 204.69), (82.43, 206.79)),
    # above the DIN wire and clear of the LED body
    ('indicators.kicad_sch', 'D13', 1): ((105.16, 120.65), (105.16, 122.75)),
    ('power_input.kicad_sch', 'C65', 1): ((93.218, 80.772), (93.218, 82.872)),
    ('power_input.kicad_sch', 'C67', 1): ((118.872, 79.756), (118.872, 81.856)),
    ('signal_gen.kicad_sch', 'U3', 1): ((35.56, 91.44), (35.56, 93.54)),
    ('signal_gen.kicad_sch', 'TP47', 1): ((162.56, 62.67), (162.56, 64.77)),
    ('signal_gen.kicad_sch', 'U5', 1): ((141.224, 66.294), (141.224, 68.394)),
    ('signal_gen.kicad_sch', 'U5', 2): ((293.624, 65.464), (293.624, 67.564)),
    ('signal_gen.kicad_sch', 'R36', 1): ((131.318, 100.838), (131.318, 102.938)),
    ('amp_control.kicad_sch', 'R28', 1): ((43.18, 79.76), (43.18, 81.86)),
    # clear of the +3V3 wire that rises from pin 18
    ('gpio_expander.kicad_sch', 'U25', 1): ((82.0, 63.5), (82.0, 65.6)),
    # left of the resistor: the DE riser is close on its right
    ('expansion.kicad_sch', 'R641', 1): ((151.5, 106.9), (151.5, 109.0)),
    # beside the clock, right of its ground symbol
    ('expansion.kicad_sch', 'U112', 1): ((50.8, 143.5), (50.8, 145.6)),
    # clear of the +3V3 wire that rises from pin 5
    ('io_expanders.kicad_sch', 'U107', 1): ((55.88, 93.96), (55.88, 96.06)),
    ('io_expanders.kicad_sch', 'U108', 1): ((144.78, 93.96), (144.78, 96.06)),
    # U4 and C15 share a tight corner: each name is pinned beside its own part
    ('signal_gen.kicad_sch', 'U4', 1): ((68.0, 61.0), (68.0, 63.1)),
    ('signal_gen.kicad_sch', 'C15', 1): ((62.5, 41.3), (62.5, 43.4)),
    # left of pin 13, so the ISO_5V name above it stands alone
    ('amp_current.kicad_sch', 'U18', 1): ((172.0, 55.86), (172.0, 57.96)),
    # clear of the +3V3_ISO wire that rises from pin 1
    ('amp_current.kicad_sch', 'U17', 1): ((112.0, 55.86), (112.0, 57.96)),
    # clear of the +3V3_SG wire that rises from pin 6
    ('signal_gen.kicad_sch', 'U6', 1): ((227.33, 66.02), (227.33, 68.12)),
}


# Net class colours: (name, schematic RGB, PCB RGB, legend text, patterns, class
# whose copper rules a new class copies). Power rails follow the ATX supply wire
# colours (3.3 V orange, 5 V red, 12 V yellow, negative blue, standby-style
# isolated 5 V purple); the schematic shades are darker for the light sheet.
# Signals stay the default colour so colour means power; Ground is grey on the
# PCB only. Power (3.3 V), Power12V and Usb come from gen_pcb.py; the power
# classes split off Power copy its rules and the rest copy Default's, so the
# board is unchanged. Patterns are KiCad wildcards on the full net name; a
# pattern listed here is moved out of any other class.
NET_CLASSES = [
    ('Power', (215, 110, 0), (255, 140, 0), '3.3 V rails (orange)', [], None),
    (
        'Power5V',
        (200, 0, 0),
        (255, 40, 40),
        '5 V rails and USB VBUS (red)',
        ['+5V', '+5V_OR', '+5V_PS15', '+5V_IO', 'USB_VBUS'],
        'Power',
    ),
    ('Power12V', (175, 140, 0), (255, 220, 0), '12 V input (yellow)', [], None),
    (
        'PowerAnalogPos',
        (130, 0, 0),
        (190, 40, 40),
        '+15 V and +16.5 V analog rails (dark red)',
        ['+15V', '+16V5'],
        'Power',
    ),
    (
        'PowerAnalogNeg',
        (0, 60, 200),
        (60, 120, 255),
        '-15 V and -16.5 V analog rails (blue)',
        ['-15V', '-16V5'],
        'Power',
    ),
    (
        'PowerIso',
        (130, 0, 170),
        (190, 90, 255),
        'Isolated 5 V, ISOW7841 output (purple)',
        ['ISO_5V'],
        'Power',
    ),
    ('Usb', None, None, None, [], None),
    (
        'SPI',
        None,
        None,
        None,
        ['SPI_*', 'ACS_*', '*/ACS_*', '*_CS', 'AD9833_FSYNC', 'AD5453_SYNC', 'CS_ADDR_?',
         'CS_EN_N'],
        'Default',
    ),
    (
        'Analog',
        None,
        None,
        None,
        ['SIG_SINE', 'DDS_SINE', 'NTC_ADC', '*/RTD_?'],
        'Default',
    ),
    (
        'Control',
        None,
        None,
        None,
        ['*_PWM', '*_TACH', 'AMP_REM_EN', 'COMP_RELAY_EN', 'PWR_KILL', 'AUX_IO*',
         '*/IO*_HDR', '*/IO*_SENSE',
         'PWR_INT', 'IMU_INT?', 'INA239_ALERT', 'CAN_TX', 'CAN_RX', 'PG_15V*',
         'PG?_15V', 'ESP_EN', 'ESP_BOOT', 'STATUS_RGB'],
        'Default',
    ),
    ('Ground', None, (110, 110, 110), None, ['GND', 'ISO_GND'],
     'Default'),
]
NO_COLOUR = 'rgba(0, 0, 0, 0.000)'


def rgba(color):
    return 'rgba({}, {}, {}, 1.000)'.format(*color) if color else NO_COLOUR


# File names of the child sheets (all in sheets/): a block on one of them
# names its own child without the folder.
SHEET_FILES = {name + '.kicad_sch' for _, name, _, _ in SHEETS}


def class_patterns(patterns):
    """A class's patterns, plus the /NAME form of each signal pattern: a net
    named by a net label on the root carries the root path."""
    local = [
        p for p in patterns
        if p[0] != '*' and any(fnmatch.fnmatchcase(net, p) for net in ROOT_LOCAL)
    ]
    return list(patterns) + ['/' + p for p in local]


def set_net_classes(project):
    """Create, colour and assign the classes in NET_CLASSES."""
    settings = project['net_settings']
    classes = {item['name']: item for item in settings['classes']}
    owned = {entry[0] for entry in NET_CLASSES if entry[4]}
    claimed = {pattern for entry in NET_CLASSES for pattern in class_patterns(entry[4])}
    settings['netclass_patterns'] = [
        item
        for item in settings['netclass_patterns']
        if item['netclass'] not in owned and item['pattern'] not in claimed
    ]
    for name, sch_color, pcb_color, _, patterns, rules in NET_CLASSES:
        if name not in classes:
            item = dict(classes[rules], name=name, priority=-1)
            settings['classes'].append(item)
            classes[name] = item
        classes[name]['schematic_color'] = rgba(sch_color)
        classes[name]['pcb_color'] = rgba(pcb_color)
        settings['netclass_patterns'] += [
            {'netclass': name, 'pattern': pattern} for pattern in class_patterns(patterns)
        ]


def colour_legend(sh, x, y):
    """One line per schematic-coloured net class, in its wire colour."""
    shown = [(text, color) for _, color, _, text, _, _ in NET_CLASSES if color]
    sh.note('POWER WIRE COLOURS (ATX SUPPLY CODE)', x, y)
    for index, (text, color) in enumerate(shown):
        sh.note(text, x, y + 4 + index * 3, 1.5, color)
    sh.note('Signals and grounds: default colour', x, y + 4 + len(shown) * 3, 1.5)


# Parts whose reference and value the automatic placer puts beside a neighbour:
# sheet file -> {side of the part its text goes on: references}. The position
# follows the part, so it survives a move. 'below>4' is below, 4 mm to the right;
# 'above@3.5' sets the distance from the part's centre line in mm.
FIELD_SIDES = {
    'cryocooler.kicad_sch': {'above': 'R23', 'above>-1': 'R24', 'left': 'C63'},
    'power_button.kicad_sch': {'right': 'C84 C41', 'left': 'D100 R56', 'below': 'R7', 'below@3.5': 'JP10'},
    'system_current.kicad_sch': {'below': 'R80', 'right': 'C68'},
    'cooling.kicad_sch': {'left': 'R15 R16'},
    'io_precision.kicad_sch': {'right': 'R627', 'left': 'R626 C428 C431 C423'},
    'io_drivers.kicad_sch': {
        'below>4': 'R600 R602 R604 R606', 'above': 'R601 R603 R605 R607',
    },
    'io_switches.kicad_sch': {'above': 'R614 R615 R616'},
    'io_pressure.kicad_sch': {'right': 'R637 R639'},
    'io_ch1.kicad_sch': {'below': 'R653', 'right': 'R657 C439', 'left': 'R656 R662 D109 C440', 'above@3.5': 'JP12'},
    'io_ch2.kicad_sch': {'below': 'R666', 'right': 'R670 C444', 'left': 'R669 R675 D112 C445', 'above@3.5': 'JP14'},
    'io_ch3.kicad_sch': {'right': 'R680 C449', 'left': 'R679 C450', 'above@3.5': 'JP16'},
    'io_ch4.kicad_sch': {'right': 'R688 C452', 'left': 'R687 C453', 'above@3.5': 'JP18'},
    'ldo_15v.kicad_sch': {'right': 'C59 C60 C57 C58', 'left': 'R76 R77'},
    'rails_15v.kicad_sch': {'above@3.5': 'D4 D5'},
    'compressor_relay.kicad_sch': {'right': 'D14'},
    'cold_head.kicad_sch': {'left': 'R62', 'right': 'C70'},
    'indicators.kicad_sch': {'left': 'R10'},
    'display.kicad_sch': {'above': 'F2', 'below': 'R517 R518'},
    'rails_logic.kicad_sch': {'left': 'C3', 'right': 'C5 C30 C87'},
    'supply_switches.kicad_sch': {'above@4.5': 'FB3 FB4', 'below@3.5': 'JP1 JP2 JP3 JP4 JP5 JP6'},
}
FIELD_LINE = 2.1  # mm between a part's reference line and its value line


def side_fields(part, side):
    """Reference and value positions (left end of each text line, mm) on one
    side of a part: beside it at 3 mm from its centre, or above / below it."""
    side, _, shift = side.partition('>')
    side, _, distance = side.partition('@')
    width = max(textlayout.text_width(part.ref), textlayout.text_width(part.value))
    upright = int(part.rot) % 180 == 0  # a resistor or capacitor standing vertically
    reach = float(distance) if distance else (5.4 if upright else 2.6)
    if side in ('left', 'right'):
        x = part.x + 3.0 if side == 'right' else part.x - 3.0 - width
        top = part.y - FIELD_LINE / 2
    else:
        x = part.x - width / 2
        top = part.y + reach if side == 'below' else part.y - reach - FIELD_LINE
    x += float(shift or 0)
    return (x, top), (x, top + FIELD_LINE)


def pin_fields(sheets):
    """Attach PINNED_FIELDS and FIELD_SIDES to their parts (after the final
    references)."""
    for sheet in sheets:
        sides = {
            ref: side
            for side, refs in FIELD_SIDES.get(sheet.filename, {}).items()
            for ref in refs.split()
        }
        for part in sheet.parts:
            pinned = PINNED_FIELDS.get((sheet.filename, part.ref, part.unit))
            if pinned is None and part.ref in sides:
                pinned = side_fields(part, sides.pop(part.ref))
            if pinned:
                part.pinned_fields = dict(zip(('Reference', 'Value'), pinned))
        missing = sorted(set(sides) - {part.ref for part in sheet.parts})
        if missing:
            sys.exit(f'FIELD_SIDES: {sheet.filename} has no {" ".join(missing)}')

def sheet_symbol(parent, child, index):
    """A child sheet's block on its parent's page. KiCad reads the file name
    relative to the parent's own file, and the instance path is the parent's.
    """
    stem = child.filename.removesuffix('.kicad_sch')
    file_name = child.filename if parent.filename in SHEET_FILES else 'sheets/' + child.filename
    x, y = (cell * 1.27 for cell in box_cell(stem))
    width, height = BOX_SIZE[0] * 1.27, BOX_HEIGHT.get(stem, BOX_SIZE[1]) * 1.27
    pins = ''
    for net, (edge, _down) in SHEET_PINS.get(stem, {}).items():
        pin_x, pin_y = (cell * 1.27 for cell in sheet_pin_cell(stem, net))
        angle, justify = (0, 'right') if edge == 'right' else (180, 'left')
        pins += (
            f'\t\t(pin {q(net)} {label_shape(net, False, child.filename)} '
            f'(at {fmt(pin_x)} {fmt(pin_y)} {angle}) '
            f'(uuid {q(kicadgen.stable_uuid(f"sheetpin/{stem}/{net}"))}) '
            f'(effects (font (size 1.27 1.27)) (justify {justify})))\n'
        )
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
        f'\t\t(property "Sheetfile" {q(file_name)} (at '
        f'{fmt(x)} {fmt(y + height + 0.6)} 0) '
        f'(show_name no) (do_not_autoplace no) (effects (font (size 1.27 '
        f'1.27)) (justify left top)))\n'
        f'{pins}'
        f'\t\t(instances (project {q(PROJECT)} (path {q(parent.path)} '
        f'(page {q(str(index + 2))}))))\n\t)'
    )


def link_parts(sheets):
    """Writes each part's datasheet and product links into its properties."""
    import part_links

    unlinked = []
    for sheet in sheets:
        for part in sheet.parts:
            if part.ref.startswith('#'):
                continue
            footprint = part.footprint or kicadgen.symbol_prop(
                kicadgen.get_symbol(part.lib_id), 'Footprint'
            )
            if getattr(part, 'off_board', False):
                found = part_links.OFF_BOARD_LINKS.get(part.value, {})
            else:
                found = part_links.links(part.ref, part.value, footprint)
            if not found and not part.ref.startswith('TP'):
                unlinked.append(part.ref)
            part.props.update(found)
    print(f'part links: {len(unlinked)} parts without a part number:',
          ' '.join(unlinked))


def describe_parts(sheets):
    """Writes each part's role and each labelled net's meaning
    (part_descriptions.py) into the Description fields; returns the number of
    parts and labels without one plus stale entries.
    """
    import part_descriptions

    table = part_descriptions.DESCRIPTIONS
    refs = {
        part.ref
        for sheet in sheets
        for part in sheet.parts
        if not part.ref.startswith('#')
    }
    for sheet in sheets:
        for part in sheet.parts:
            if part.ref in table:
                part.props['Description'] = table[part.ref]
    missing = sorted(refs - table.keys())
    stale = sorted(table.keys() - refs)
    print(f'part descriptions: {len(missing)} parts without one:', ' '.join(missing))
    if stale:
        print('  descriptions for parts that no longer exist:', ' '.join(stale))
    nets = part_descriptions.NET_DESCRIPTIONS
    labels = {net for sheet in sheets for _kind, net, _at, _angle in sheet.labels}
    for sheet in sheets:
        sheet.label_descriptions = nets
    unnamed = sorted(labels - nets.keys())
    unused = sorted(nets.keys() - labels)
    print(f'label descriptions: {len(unnamed)} labels without one:', ' '.join(unnamed))
    if unused:
        print('  descriptions for labels that no longer exist:', ' '.join(unused))
    return len(missing) + len(stale) + len(unnamed) + len(unused)


def check_sheets(sheets):
    """Finalizes the sheets and runs the text overlap (including wires drawn
    across labels), 4-way junction and duplicate reference checks; returns the
    three counts.
    """
    import textlayout

    overlaps = 0
    junctions = 0
    for sheet in sheets:
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
        for problem in textlayout.wires_over_labels(sheet):
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
    for sheet in sheets:
        for part in sheet.parts:
            if part.ref.startswith('#'):
                continue
            owner = (sheet.title, part.lib_id, part.value)
            if owners.setdefault(part.ref, owner) != owner:
                duplicates += 1
                print(f'  duplicate reference {part.ref}: {owners[part.ref]} '
                      f'and {owner}')
    print(f'duplicate reference check: {duplicates} found')
    return overlaps, junctions, duplicates


def main():
    kicadgen.reset_uuids()
    root_uuid = ROOT_UUID
    root = Sheet('Cryocooler Controller', 'cryocooler.kicad_sch', 'A2')
    root.uid = root_uuid
    root.path = '/' + root_uuid
    build_mcu(root)
    children, by_stem = [], {}
    on_root = [name for _, name, _, _ in SHEETS if name not in NESTED_SHEETS]
    if sorted(on_root) != sorted(stem for stem in BLOCK_ORDER if stem):
        sys.exit('BLOCK_ORDER must list every sheet that is not in NESTED_SHEETS, once')
    for index, (title, name, builder, paper) in enumerate(SHEETS):
        parent = root
        if name in NESTED_SHEETS:
            if NESTED_SHEETS[name][0] not in by_stem:
                sys.exit(f'{name}: its parent sheet must come before it in SHEETS')
            parent = by_stem[NESTED_SHEETS[name][0]]
        child = Sheet(title, name + '.kicad_sch', paper)
        child.uid = kicadgen.stable_uuid('sheet/' + name)
        child.path = f'{parent.path}/{child.uid}'
        builder(child)
        children.append(child)
        by_stem[name] = child
        parent.sheet_symbols.append(sheet_symbol(parent, child, index))
    # final references; the builders keep allocating their own numbers
    for sheet in [root] + children:
        for part in sheet.parts:
            part.ref = REF_MAP.get(part.ref, part.ref)

    link_parts([root] + children)
    undescribed = describe_parts([root] + children)
    pin_fields([root] + children)
    overlaps, junctions, duplicates = check_sheets([root] + children)
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
    project['schematic']['bus_aliases'] = BUS_ALIASES
    set_net_classes(project)
    project_file.write_text(json.dumps(project, indent=2) + '\n')
    print('wrote', 1 + len(children), 'sheets')
    if duplicates:
        sys.exit(1)
    print(f'4-way junction check: {junctions} found')
    if overlaps or junctions or undescribed:
        sys.exit(1)


if __name__ == '__main__':
    main()
