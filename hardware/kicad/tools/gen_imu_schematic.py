"""Generates the IMU board project (hardware/kicad/imu/): one hand-laid sheet
and the project file.

The board carries an LSM6DSOX on the cable from J14 on the main board. J1 is
the same Molex Micro-Lock Plus 2x4 as J14 with the same pin map, so the cable
is wired pin to pin. Connections follow ST DS12814 (Table 1, Section 7).

Run: python3 hardware/kicad/tools/gen_imu_schematic.py
"""

import json
import sys

import kicadgen
from kicadgen import Sheet, next_ref
from gen_schematic import (
    TP_PAD,
    LED0402,
    drop_ground,
    gnd_bus,
    hres,
    net_label,
    pin_cell,
    place_blocks,
    place_ic,
    rail_flag,
    rail_symbol,
    spur,
    vres,
    wire,
    link_parts,
    check_sheets,
)
import gen_schematic

ROOT_DIR = gen_schematic.ROOT_DIR
IMU_DIR = ROOT_DIR / 'imu'
PROJECT = 'imu'
MICRO_LOCK = 'cryocooler:Molex_Micro-Lock_Plus_505448-0891_2x04_P1.25mm_Horizontal'
LGA14 = 'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y'

# J1 pin -> net, the J14 map on the main board
CABLE = {
    '1': 'SPI_SCK',
    '2': 'GND',
    '3': 'SPI_MOSI',
    '4': '+3V3',
    '5': 'IMU_CS',
    '6': 'SPI_MISO',
    '7': 'IMU_INT1',
    '8': 'IMU_INT2',
}
# test point name (printed on the board) -> net
TEST_POINTS = (
    ('3V3', '+3V3'),
    ('GND', 'GND'),
    ('SCK', 'SPI_SCK'),
    ('MOSI', 'SPI_MOSI'),
    ('MISO', 'SPI_MISO'),
    ('CS', 'IMU_CS'),
    ('INT1', 'IMU_INT1'),
    ('INT2', 'IMU_INT2'),
)

# global-label shapes from this board's side: the IMU reads the clock, data in
# and select, and drives data out and the interrupts
kicadgen.LABEL_DIRECTION.update({
    'SPI_SCK': 'in',
    'SPI_MOSI': 'in',
    'IMU_CS': 'in',
    'SPI_MISO': 'out',
    'IMU_INT1': 'out',
    'IMU_INT2': 'out',
})


def build_connector(sh, column, row):
    """J1 on the left, pins facing right: rails tied off, signals to labels."""
    header = sh.add(
        'cryocooler:Conn_02x04_Rails_At_Ends',
        next_ref('J'),
        '505448-0891',
        column * 1.27,
        row * 1.27,
        auto=False,
        footprint=MICRO_LOCK,
    )
    rail_symbol(sh, '+3V3', spur(sh, header, '4', 4))
    rail_symbol(sh, 'GND', spur(sh, header, '2', 4))
    for pin, net in CABLE.items():
        if net in ('+3V3', 'GND'):
            continue
        net_label(sh, net, spur(sh, header, pin, 4), 0, is_global=True)
    return header


def build_imu(sh, column, row):
    """LSM6DSOX in 4-wire SPI mode (DS12814 Mode 1)."""
    imu = place_ic(sh, 'cryocooler:LSM6DSOXTR', 'LSM6DSOXTR', column, row, LGA14)
    for pin, net in (
        ('12', 'IMU_CS'),
        ('13', 'SPI_SCK'),
        ('14', 'SPI_MOSI'),
        ('1', 'SPI_MISO'),
    ):
        net_label(sh, net, spur(sh, imu, pin, 12), 180, is_global=True)
    # CS pull-up: keeps the part deselected while the cable is unplugged
    cs = pin_cell(imu, '12')
    vres(sh, '10k', cs[0] - 6, cs[1] - 6)
    rail_symbol(sh, '+3V3', (cs[0] - 6, cs[1] - 6))
    # OCS_Aux and SDO_Aux: "leave unconnected", Mode 1
    sh.nc(imu, '10')
    sh.nc(imu, '11')
    for pin, net in (('4', 'IMU_INT1'), ('9', 'IMU_INT2')):
        net_label(sh, net, spur(sh, imu, pin, 3), 0, is_global=True)
    vdd, vddio = pin_cell(imu, '8'), pin_cell(imu, '5')
    bar = min(vdd[1], vddio[1]) - 4
    wire(sh, vdd, (vdd[0], bar), (vddio[0], bar), vddio)
    rail_symbol(sh, '+3V3', ((vdd[0] + vddio[0]) // 2, bar))
    # SDx and SCx: "connect to VDDIO or GND" in Mode 1
    gnd_bus(sh, [pin_cell(imu, '2'), pin_cell(imu, '3'), pin_cell(imu, '6')])
    return imu


def build_power_led(sh, column, row):
    """+3V3 -> 1.5k -> green LED -> ground (about 1 mA)."""
    sh.note('POWER LED', column * 1.27, (row - 8) * 1.27, 1.8)
    rail_symbol(sh, '+3V3', (column, row))
    wire(sh, (column, row), (column + 3, row))
    hres(sh, '1.5k', column + 6, row)
    wire(sh, (column + 9, row), (column + 11, row))
    led = sh.add(
        'Device:LED',
        next_ref('D'),
        'POWER',
        (column + 14) * 1.27,
        row * 1.27,
        rot=180,
        auto=False,
        footprint=LED0402,
    )
    drop_ground(sh, pin_cell(led, '1'), 2)
    return led


def build_test_points(sh, column, row, pitch=16):
    """One pad per cable net, each on a power symbol or global label."""
    sh.note('TEST POINTS', (column - 16) * 1.27, (row - 8) * 1.27, 1.8)
    for name, net in TEST_POINTS:
        if net == 'GND':
            test_point(sh, name, (column, row))
            wire(sh, (column, row), (column, row + 3))
            rail_symbol(sh, 'GND', (column, row + 3))
        else:
            if net == '+3V3':
                rail_symbol(sh, net, (column, row))
            else:
                net_label(sh, net, (column, row), 180, is_global=True)
            wire(sh, (column, row), (column, row + 3))
            test_point(sh, name, (column, row + 3), rot=180)
        column += pitch


def test_point(sh, name, cell, rot=0):
    return sh.add(
        'Connector:TestPoint',
        next_ref('TP'),
        name,
        cell[0] * 1.27,
        cell[1] * 1.27,
        rot=rot,
        auto=False,
        footprint=TP_PAD,
    )


def build(sh):
    sh.handwired = True
    sh.note(
        'IMU board: LSM6DSOX in 4-wire SPI mode (DS12814 Mode 1), cabled to J14 '
        'on the main board.',
        20,
        15,
    )
    sh.note(
        'J1 = J14 pin for pin (cable wired 1-1 ... 8-8): 1 SCK, 2 GND, 3 MOSI, '
        '4 +3V3, 5 CS, 6 MISO, 7 INT1, 8 INT2.',
        20,
        21,
    )
    sh.note(
        'No I2C. INT1 must be low or open at power-up (DS12814 Table 20).',
        20,
        27,
    )
    build_connector(sh, 40, 80)
    build_imu(sh, 125, 80)
    place_blocks(
        sh,
        [('DECOUPLING (C3 BULK AT J1)', '+3V3', ('100nF', '100nF', '10uF'))],
        165,
        52,
    )
    # the supplies enter on J1, a passive connector: flag them as driven at the
    # right end of the block's rails (last cap at column 165 + 6 + 2 * 12)
    for row in (52, 58):
        wire(sh, (195, row), (201, row))
        rail_flag(sh, (201, row))
    build_power_led(sh, 168, 92)
    build_test_points(sh, 36, 122)


def write_project(root_uuid):
    """imu.kicad_pro from the main project's: same rules and defaults, its own
    sheet list, the Default and Power net classes only.
    """
    project = json.loads((ROOT_DIR / 'cryocooler.kicad_pro').read_text())
    project['meta']['filename'] = f'{PROJECT}.kicad_pro'
    project['sheets'] = [[root_uuid, PROJECT]]
    project['schematic']['top_level_sheets'] = [
        {'filename': f'{PROJECT}.kicad_sch', 'name': PROJECT, 'uuid': root_uuid}
    ]
    project['pcbnew']['last_paths'] = {
        key: '' for key in project['pcbnew']['last_paths']
    }
    net_settings = project['net_settings']
    net_settings['classes'] = [
        net_class for net_class in net_settings['classes']
        if net_class['name'] in ('Default', 'Power')
    ]
    net_settings['netclass_patterns'] = [
        {'netclass': 'Power', 'pattern': '+3V3'},
        {'netclass': 'Power', 'pattern': 'GND'},
    ]
    project['board']['design_settings']['drc_exclusions'] = []
    (IMU_DIR / f'{PROJECT}.kicad_pro').write_text(
        json.dumps(project, indent=2) + '\n'
    )


def main():
    kicadgen.PROJECT = PROJECT
    kicadgen.UUID_NAMESPACE = 'imu-schematic'
    kicadgen.reset_uuids()
    root_uuid = kicadgen.stable_uuid('root')
    sheet = Sheet('Cryocooler IMU', f'{PROJECT}.kicad_sch', 'A4')
    sheet.uid = root_uuid
    sheet.path = '/' + root_uuid
    build(sheet)
    link_parts([sheet])
    overlaps, junctions, duplicates = check_sheets([sheet])
    IMU_DIR.mkdir(exist_ok=True)
    (IMU_DIR / f'{PROJECT}.kicad_sch').write_text(sheet.render(root_uuid))
    write_project(root_uuid)
    print('wrote', IMU_DIR / f'{PROJECT}.kicad_sch')
    print(f'4-way junction check: {junctions} found')
    if overlaps or junctions or duplicates:
        sys.exit(1)


if __name__ == '__main__':
    main()
