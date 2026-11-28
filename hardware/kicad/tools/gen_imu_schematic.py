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
    net_label,
    pin_cell,
    place_blocks,
    place_ic,
    rail_flag,
    rail_symbol,
    side_fields,
    spur,
    vcap,
    vres,
    wire,
    link_parts,
    check_sheets,
    check_geometry,
    describe_parts,
)
import gen_schematic
import part_descriptions

ROOT_DIR = gen_schematic.ROOT_DIR
IMU_DIR = ROOT_DIR / 'imu'
PROJECT = 'imu'
MICRO_LOCK = 'cryocooler:Molex_Micro-Lock_Plus_505448-0891_2x04_P1.25mm_Horizontal'
LGA14 = 'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y'

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

# J1 pin -> U1 pin for each signal
SIGNALS = {
    'IMU_INT2': ('8', '9'),
    'IMU_INT1': ('7', '4'),
    'SPI_MISO': ('6', '1'),
    'IMU_CS': ('5', '12'),
    'SPI_MOSI': ('3', '14'),
    'SPI_SCK': ('1', '13'),
}
LABEL_ROOM = 9  # cells of wire at J1 that carry the net labels
STEP = 7  # cells of wire each signal keeps to itself for its test point
PULL_UP_ROOM = 8  # extra cells in the CS step for R1


def build_connector(sh, column, row):
    """J1 on the left, pins facing right."""
    header = sh.add(
        'cryocooler:Conn_02x04_IMU_Cable',
        next_ref('J'),
        '505448-0891',
        column * 1.27,
        row * 1.27,
        auto=False,
        footprint=MICRO_LOCK,
    )
    return header


def build_supply(sh, header):
    """J1's supply pins: a rail from each runs left past the bulk capacitor
    and the supply's test point to a flag (J1 is passive, so the flags mark
    the rails as driven).
    """
    top, bottom = spur(sh, header, '4', 2), spur(sh, header, '2', 2)
    rail_symbol(sh, '+3V3', spur(sh, header, '4', 4))
    rail_symbol(sh, 'GND', spur(sh, header, '2', 4))
    column = top[0] - 14
    wire(sh, top, (column - 12, top[1]))
    wire(sh, bottom, (column - 12, bottom[1]))
    wire(sh, (column, top[1]), (column, top[1] + 4))
    beside(vcap(sh, '10uF', column, top[1] + 4), 'right')
    wire(sh, (column, top[1] + 10), (column, bottom[1]))
    rail_flag(sh, (column - 12, top[1]))
    rail_flag(sh, (column - 12, bottom[1]))
    return {'+3V3': (column - 6, top[1]), 'GND': (column - 6, bottom[1])}


def build_imu(sh, column, row):
    """LSM6DSOX in 4-wire SPI mode (DS12814 Mode 1) with its supply and
    strap pins tied off.
    """
    imu = place_ic(sh, 'cryocooler:LSM6DSOXTR', 'LSM6DSOXTR', column, row, LGA14)
    # text at the top left corner, clear of the supply wires
    left, top = imu.bbox()[:2]
    imu.pinned_fields = {'Reference': (left - 5.08, top + 0.5), 'Value': (left - 5.08, top + 2.6)}
    # OCS_Aux and SDO_Aux: "leave unconnected", Mode 1
    sh.nc(imu, '10')
    sh.nc(imu, '11')
    vdd, vddio = pin_cell(imu, '8'), pin_cell(imu, '5')
    bar = min(vdd[1], vddio[1]) - 4
    wire(sh, vdd, (vdd[0], bar), (vddio[0], bar), vddio)
    rail_symbol(sh, '+3V3', ((vdd[0] + vddio[0]) // 2, bar))
    # SDx and SCx: "connect to VDDIO or GND" in Mode 1
    gnd_bus(sh, [pin_cell(imu, '2'), pin_cell(imu, '3'), pin_cell(imu, '6')])
    return imu


def wire_signals(sh, header, imu):
    """Wires each J1 pin to its U1 pin. The lines leave J1 together, then
    turn up one after another, top line first, so none crosses another and
    each has a stretch with clear space above it. Returns that stretch's
    middle cell per net, where its test point taps.
    """
    taps = {}
    turn = None
    for net, (cable_pin, imu_pin) in SIGNALS.items():
        start, end = pin_cell(header, cable_pin), pin_cell(imu, imu_pin)
        begin = start[0] + LABEL_ROOM if turn is None else turn
        turn = begin + STEP
        taps[net] = (begin + STEP // 2, start[1])
        if net == 'IMU_CS':
            # pull-up: keeps the part deselected while the cable is unplugged
            turn += PULL_UP_ROOM
            column = begin + STEP + 2
            vres(sh, '10k', column, start[1] - 8)
            rail_symbol(sh, '+3V3', (column, start[1] - 8))
            wire(sh, (column, start[1] - 2), (column, start[1]))
        if end[0] - turn < 2:
            sys.exit(f'{net}: U1 is too close for a stub at its pin')
        wire(sh, start, (turn, start[1]), (turn, end[1]), end)
        net_label(sh, net, (start[0] + 2, start[1]), 0)
    return taps


def build_power_led(sh, column, row):
    """+3V3 -> 1.5k -> green LED -> ground, top to bottom."""
    sh.note('POWER LED', (column - 6) * 1.27, (row - 10) * 1.27, 1.8)
    rail_symbol(sh, '+3V3', (column, row))
    vres(sh, '1.5k', column, row)
    led = sh.add(
        'Device:LED',
        next_ref('D'),
        'POWER',
        column * 1.27,
        (row + 11) * 1.27,
        rot=90,
        auto=False,
        footprint=LED0402,
    )
    beside(led, 'right')
    wire(sh, (column, row + 6), pin_cell(led, '2'))
    drop_ground(sh, pin_cell(led, '1'), 2)
    return led


def build_test_points(sh, taps):
    """One pad per cable net, each on a short stub above its own wire."""
    for name, net in TEST_POINTS:
        tap = taps[net]
        wire(sh, tap, (tap[0], tap[1] - 2))
        # text above the pad: beside it sits the next wire
        beside(test_point(sh, name, (tap[0], tap[1] - 2)), 'above@5.5')


def beside(part, side):
    """Fixes a part's reference and value on one side of it."""
    part.pinned_fields = dict(zip(('Reference', 'Value'), side_fields(part, side)))


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
    sh.note('IMU AND CABLE CONNECTOR', 26 * 1.27, 46 * 1.27, 1.8)
    header = build_connector(sh, 52, 88)
    imu = build_imu(sh, 138, 74)
    taps = wire_signals(sh, header, imu)
    place_blocks(
        sh, [('U1 DECOUPLING CAPACITORS', '+3V3', ('100nF', '100nF'))], 176, 54
    )
    taps.update(build_supply(sh, header))
    build_power_led(sh, 182, 80)
    build_test_points(sh, taps)


def write_project(root_uuid):
    """Updates imu.kicad_pro in place: its sheet list and the Power net class
    patterns. The board rules and net classes in it are this board's own.
    """
    path = IMU_DIR / f'{PROJECT}.kicad_pro'
    project = json.loads(path.read_text())
    project['sheets'] = [[root_uuid, PROJECT]]
    project['schematic']['top_level_sheets'] = [
        {'filename': f'{PROJECT}.kicad_sch', 'name': PROJECT, 'uuid': root_uuid}
    ]
    project['net_settings']['netclass_patterns'] = [
        {'netclass': 'Power', 'pattern': '+3V3'},
        {'netclass': 'Power', 'pattern': 'GND'},
    ]
    path.write_text(json.dumps(project, indent=2) + '\n')


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
    undescribed = describe_parts(
        [sheet],
        part_descriptions.IMU_DESCRIPTIONS,
        part_descriptions.IMU_NET_DESCRIPTIONS,
    )
    overlaps, junctions, duplicates = check_sheets([sheet])
    geometry = check_geometry([sheet])
    (IMU_DIR / f'{PROJECT}.kicad_sch').write_text(sheet.render(root_uuid))
    write_project(root_uuid)
    print('wrote', IMU_DIR / f'{PROJECT}.kicad_sch')
    print(f'4-way junction check: {junctions} found')
    if overlaps or junctions or duplicates or undescribed or geometry:
        sys.exit(1)


if __name__ == '__main__':
    main()
