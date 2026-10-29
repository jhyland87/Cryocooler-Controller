"""Generates cryocooler.kicad_pcb from the schematic netlist.

Run with KiCad's bundled python (it provides `pcbnew`):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
    \
        hardware/kicad/tools/gen_pcb.py

Stage 1 (this file): board outline, footprints with nets, anchor placement from
PLACEMENT, automatic placement of every resistor/capacitor next to the pin it
serves, keep-outs and mounting holes.
"""

import collections
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

from pcbnetlist import KICAD_DIR, load_netlist
import export_fab
import pcbfloorplan
import pcbmodels
from pcbplace import Occupancy, Rect, placed_rect, ring_offsets, rotate_point

# Phoenix Contact UCS 145-125 housing PCB (drawing 2203447): 120 x 100 mm,
# 31 mm clearance above the board and 10 mm below
BOARD_WIDTH = 120.0
BOARD_HEIGHT = 100.0
EDGE_MARGIN = 0.8
PASSIVE_GAP = 0.2
# JLCPCB needs 0.2 mm drills on 0.45 mm pads or larger, else a paid 4-wire test.
VIA_IN_PAD_DIAMETER = 0.45
HOLE_TO_HOLE = 0.25  # board rule (min_hole_to_hole), drill edge to drill edge
STOCK_FOOTPRINTS = Path(
    '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
)

GROUND_NETS = {'GND', 'ISO_GND'}
# switched supply nets (one jumper each) -> module box they belong to
SWITCHED_NETS = {
    '+3V3_SG': 'SIGNAL GENERATOR',
    '+5V_PS15': 'RAILS ±15V',
    '+5V_ISO': 'AMP CURRENT (ISOLATED)',
    '+3V3_COOL': 'WATER COOLING',
    '+3V3_CH': 'COLD HEAD',
}
# sections too full for their test points: these sit in the nearest free
# spot of another box instead (none at the moment)
TEST_POINTS_OUTSIDE = set()
# how far (mm, from the pad it serves) a test point may go before the last
# placement pass
TEST_POINT_REACH = 8.0
TEST_POINT_OVERFLOW = None
POWER_NETS = GROUND_NETS | set(SWITCHED_NETS) | {
    '+3V3',
    '+5V',
    '+12V',
    'VIN',
    'VSW',
    'ISO_3V3',
    '+15V',
    '-15V',
    '+16V5',
    '-16V5',
    'USB_VBUS',
}

# ref -> (x, y, rotation[, 'B']): the parts placed by hand, on the top side
# unless marked 'B' (bottom). Everything else (passives, test points, small
# transistors / diodes / logic, LEDs, jumpers) is placed beside the pad it
# serves by place_passives(). Edge connectors face the housing side walls.
PLACEMENT = {
    # MCU: ESP32 antenna over the routed notch in the top edge, USB-C on the
    # right wall
    'U1': (84.0, 12.75, 0),
    'J1': (116.325, 13.1, 90),
    'SW1': (66.5, 11.0, 0),
    'SW2': (66.5, 18.5, 0),
    # amplifier current, isolated side on the left (barrier at x = 25.25)
    'J11': (10.0, 11.7, 270),
    'J12': (10.0, 25.4, 270),
    'U18': (18.8, 14.0, 0),
    'U17': (26.0, 25.3, 180),
    'PS1': (26.0, 33.2, 0),
    # amplifier control terminals on the top wall
    'J9': (40.5, 8.0, 180),
    'J8': (51.3, 8.0, 180),
    # signal generator: oscillator, DDS and DAC, op-amps below them
    'U3': (38.5, 23.5, 0),
    'U4': (46.5, 23.5, 0),
    'U7': (53.5, 23.5, 90),
    'U5': (38.5, 35.0, 90),
    'U6': (45.5, 35.0, 90),
    'U9': (52.5, 35.0, 90),
    # 5 V buck and 3.3 V LDO, below the 12 V input
    'L1': (7.5, 73.0, 0),
    'U16': (17.0, 73.0, 0),
    'U15': (12.5, 79.0, 0),
    # 12 V input on the left wall
    'J2': (10.0, 46.0, 270),
    'F1': (19.2, 46.0, 90),
    'D1': (19.2, 55.0, 90),
    'C6': (7.5, 60.5, 0),
    # power button: switch MOSFET, panel connector and button on the bottom wall
    'Q1': (35.0, 66.5, 0),
    'SW3': (30.0, 96.3, 0),
    # JST PH headers: mating face 0.6 mm inside the bottom edge (copper
    # edge clearance for their fitting nails)
    'J7': (38.80, 95.00, 0),
    'U11': (30.0, 80.0, 0),
    'U13': (37.0, 80.0, 0),
    'J13': (49.00, 95.00, 0),
    # system current: 12 V bulk capacitor and INA239
    'C71': (50.0, 66.0, 0),
    'U23': (51.0, 76.0, 0),
    # +-15 V rails: ADP5071 and its inductors in a row, LT3097 after them
    'U20': (63.5, 55.0, 0),
    'L2': (73.0, 55.0, 0),
    'L3': (83.0, 55.0, 0),
    'D5': (68.0, 61.5, 0),
    'D6': (76.0, 61.5, 0),
    'U21': (92.0, 55.0, 0),
    # cold head and IMU on the right wall
    'U14': (104.50, 60.00, 90),
    'J10': (111.35, 59.00, 90),
    'J14': (114.7, 30.0, 270),
    # water cooling: pump on the right wall, NTC / flow / fan on the bottom
    'J4': (110.8, 85.0, 90),
    'J3': (80.50, 90.80, 0),
    'J5': (68.50, 90.80, 0),
    'J6': (60.80, 95.00, 0),
    'U10': (100.0, 88.0, 0),
    'U25': (74.0, 75.0, 0),
}

# ISO_GND island (top-left corner, left of the barrier); keep-out bands keep
# GND copper away from it.
ISO_REGION = Rect(0.0, 0.0, 25.25, 36.0)
ISO_NETS = {'ISO_GND', 'ISO_3V3'}

# Same-net pad chains on 0.5 mm pitch parts, joined by locked F.Cu stubs before
# routing (the 0.3 mm power tracks do not fit between the pads): consecutive
# pads of each chain, plus the exposed-pad links.
PAD_BRIDGES = {
    'U21': (
        ('1', '2', '3'),  # INP, INP, ENP/UVP
        ('6', '7', '8'),  # INN, INN, ENN/UVN
        ('7', '24'),  # INN to its exposed pad
        ('14', '15', '16'),  # OUTSN, OUTN, OUTN
        ('20', '21', '22'),  # OUTSP, OUTP, OUTP
        ('19', '23'),  # GND to its exposed pad
    ),
}
BRIDGE_WIDTH = 0.2

# GND pads that get a locked via-in-pad before routing (fine-pitch LGA)
FINE_PITCH_GROUND_PADS = {
    'U23': {'7'},
    'U4': {'4', '9'},
    'U21': {'5', '11', '13', '19'},
    'U20': {'1', '4', '6', '15', '21'},
    'U25': {'13'},
    'U11': {'4'},
}
# GND pads of placed passives that are boxed in by their own signal track and
# would otherwise get a via-in-pad after routing, on top of an inner track
LATE_GROUND_PADS = {'C30': {'2'}, 'C74': {'2'}, 'U24': {'3'}}
MIN_TRACK_WIDTH = 0.15

# Anchors for ground test points (ground nets have no natural neighbour pad):
# the k-th TP on GND sits beside the k-th entry; ISO_GND beside the isolator.
GND_TP_ANCHORS = [('J2', '2'), ('U3', '2'), ('U16', '1')]
ISO_GND_TP_ANCHOR = ('U17', '9')
ISO_BAND = 1.5
# ESP32 antenna: the board is cut away under it (routed notch in the top
# edge) and the strip beside the notch, within the module's 15 mm keep-out,
# carries no copper and no parts.
ANTENNA_NOTCH = Rect(74.5, 0.0, 93.5, 6.0)
ANTENNA_KEEPOUTS = [Rect(60.0, 0.0, 74.5, 6.75), Rect(93.5, 0.0, 108.0, 6.75)]
# housing restricted areas (no parts, no copper, no solder mask): a 4.45 mm
# corner square and a 6 mm ring round each mounting hole
CORNER_SQUARE = 4.45
HOLE_RING_RADIUS = 3.0
CORNER_KEEPOUT = 7.4  # square that holds both, for part placement
FREEROUTING_JAR = Path(sys.argv[2]) if len(sys.argv) > 2 else None
MAX_PASSES = '12'
JAVA = (
    '/Library/Java/JavaVirtualMachines/temurin-25.jdk/Contents/Home/bin/java'
)

# Local rect overrides (the ESP32 courtyard includes a large antenna keep-out).
# ─── silkscreen ───
# Labels beside the buttons and indicator LEDs (ref -> text), placed on the
# first free side of the part.
SILK_LABELS = {
    'SW1': 'RESET',
    'SW2': 'BOOT',
    'SW3': 'POWER',
    'J7': 'PANEL',
    'D2': 'FAN FAULT',
    'D3': 'POWER',
    'D4': 'AMP REM',
    'D7': 'ALERT',
    'D8': '3V3',
    'D9': 'READY',
    'D10': 'FAULT',
    'D11': 'STATUS',
    'D12': 'COMP RLY',
    'D14': '5V',
    'D15': '+15V',
    'D16': '-15V',
    'D17': 'ISO 3V3',
    'D24': '+15V PG',
    'D25': '-15V PG',
    # board inputs and outputs, beside each connector
    'J1': 'USB-C 5V',
    'J2': '12V IN',
    'J3': 'FAN 12V',
    'J4': 'PUMP 12V',
    'J5': 'FLOW',
    'J6': 'NTC',
    'J8': 'AMP REM OUT',
    'J9': 'AMP SIG OUT',
    'J10': 'PT1000',
    'J11': 'FROM AMP',
    'J12': 'TO CRYOCOOLER',
    'J13': 'RELAY 12V OUT',
    'J14': 'IMU',
}
# shorter forms of part labels, for parts with little room beside them
SILK_LABEL_SHORT = {
    'J8': ('REM OUT',),
    'J12': ('TO CRYO',),
    'J13': ('RELAY OUT',),
}
# Connector pin labels (pin 1 first): what each terminal is for, printed
# beside the pads on the side facing the board interior.
PIN_LABELS = {
    'J2': ['+12V', 'GND'],
    'J3': ['GND', '+12V', 'TACH', 'PWM'],
    'J4': ['GND', '+12V', 'TACH', 'PWM'],
    'J5': ['GND', '+12V', 'TACH'],
    'J6': ['NTC', 'GND'],
    'J7': ['BTN', 'GND'],
    'J8': ['REM', 'GND'],
    'J9': ['SIG', 'GND'],
    # M12 A-coded: pins sit in a square under the body, so name the pins
    'J10': ['1 F+', '2 S+', '3 S-', '4 F-'],
    'J11': ['+', '-'],
    'J12': ['+', '-'],
    'J13': ['+12V', 'GND'],
    # the module's own pad names, top to bottom
    'J14': ['VIN', 'GND', 'SCL', 'SDA', 'DO', 'CS', 'I1', 'I2'],
}
# what each supply jumper switches (JP1 ... JP5, in schematic order)
JUMPER_LABELS = ('SG 3V3', '±15V EN', 'ISO PS', 'WATER EN', 'HEAD EN')
SILK_LABELS.update(
    {f'JP{index}': text for index, text in enumerate(JUMPER_LABELS, start=1)}
)
SILK_TEXT_SIZE = 0.8
# part numbers printed under the IC bodies as a placement aid: font sizes to
# try (largest first) and the refs that get one (modules and oversize parts skip)
IC_LABEL_SIZES = (0.9, 0.8)  # 0.8 mm is the silkscreen minimum
IC_LABEL_SKIP = ('U1',)
IC_LABEL_STEP = 0.25
# shorter text for parts whose full value will not fit under the body
IC_LABEL_TEXT = {
    'U3': 'SG-8002CA',
    'U7': 'MCP4921',
    'U18': 'ACS37800',
    'PS1': 'MIE1W0505',
}
SILK_TEXT_THICKNESS = 0.12
# free space between two section titles on the same line
TITLE_SPACING = 3.0
# Board ID block: same spot and format on every revision (back side, under
# the isolated section, where only the J11 / J12 pins come through)
BOARD_NAME = 'Cryocooler-Controller'
BOARD_ID_SIDE = 'B'
BOARD_ID_SPOT = (19.0, 2.4)
BOARD_ID_SIZE = 1.0
ESP32_PIN_TEXT_SIZE = 0.8
# solder mask colour written into the board stackup (renders and fab notes)
MASK_COLOUR = 'Blue'

# housing mounting holes: 4 x 3.2 mm on a 111.6 x 91.6 mm pattern, centred
HOLES = [(4.2, 4.2), (115.8, 4.2), (4.2, 95.8), (115.8, 95.8)]
LOCAL_RECT_OVERRIDES = {
    # the module body (its antenna courtyard is the notch and keep-outs)
    'RF_Module:ESP32-S3-WROOM-2': Rect(-9.75, -12.9, 9.75, 13.5),
    # the stock test point courtyard is 3.7 mm square around a 1.5 mm pad
    'TestPoint:TestPoint_Pad_D1.5mm': Rect(-1.15, -1.15, 1.15, 1.15),
}


_TEXT_SIZES = {}


def measure_text(text, size, thickness=0.15):
    """(width, height) in mm of an upright silkscreen text as pcbnew draws
    it.
    """
    key = (text, size, thickness)
    if key not in _TEXT_SIZES:
        item = pcbnew.PCB_TEXT(pcbnew.BOARD())
        item.SetText(text)
        item.SetTextSize(pcbnew.VECTOR2I(to_internal(size), to_internal(size)))
        item.SetTextThickness(to_internal(thickness))
        box = item.GetBoundingBox()
        _TEXT_SIZES[key] = (box.GetWidth() / 1e6, box.GetHeight() / 1e6)
    return _TEXT_SIZES[key]


def measure_label(text):
    """Printed width (mm) of a module label text."""
    return measure_text(text, pcbfloorplan.LABEL_SIZE, SILK_TEXT_THICKNESS + 0.03)[0]


pcbfloorplan.measure_label = measure_label


def corner_keepouts():
    """Part keep-outs over the housing's restricted corner areas."""
    size = CORNER_KEEPOUT
    return [
        Rect(0.0, 0.0, size, size),
        Rect(BOARD_WIDTH - size, 0.0, BOARD_WIDTH, size),
        Rect(0.0, BOARD_HEIGHT - size, size, BOARD_HEIGHT),
        Rect(BOARD_WIDTH - size, BOARD_HEIGHT - size, BOARD_WIDTH, BOARD_HEIGHT),
    ]


def restricted_outline(hole_x, hole_y, steps=32):
    """Polygon (mm points) of one restricted corner: the corner square joined
    with the ring round the hole, as drawn in the housing's PCB2D drawing.
    """
    corner_x = 0.0 if hole_x < BOARD_WIDTH / 2 else BOARD_WIDTH
    corner_y = 0.0 if hole_y < BOARD_HEIGHT / 2 else BOARD_HEIGHT
    sign_x = 1 if corner_x == 0.0 else -1
    sign_y = 1 if corner_y == 0.0 else -1
    # walk the circle from the edge parallel to x round to the edge parallel
    # to y, on the side away from the corner, then close along the square
    points = [(corner_x, corner_y), (corner_x + sign_x * CORNER_SQUARE, corner_y)]
    import math

    for step in range(steps + 1):
        angle = -math.pi / 2 + math.pi * 1.5 * step / steps
        offset_x = HOLE_RING_RADIUS * math.cos(angle)
        offset_y = HOLE_RING_RADIUS * math.sin(angle)
        points.append((hole_x + sign_x * offset_x, hole_y + sign_y * offset_y))
    points.append((corner_x, corner_y + sign_y * CORNER_SQUARE))
    return points


def footprint_path(footprint_id):
    library, name = footprint_id.split(':')
    if library == 'cryocooler':
        return str(KICAD_DIR / 'lib' / 'cryocooler.pretty'), name
    return str(STOCK_FOOTPRINTS / f'{library}.pretty'), name


def to_internal(value_mm):
    return pcbnew.FromMM(value_mm)


def short_net(name):
    return name.split('/')[-1]


class PcbBuilder:
    """Builds the board: footprints, nets, placement."""

    def __init__(self):
        self.parts, self.nets = load_netlist()
        self.board = pcbnew.BOARD()
        self.board.SetCopperLayerCount(4)
        self.footprints = {}
        self.local_rects = {}
        self.pad_local = {}
        self.centers = {}
        self.pad_net = collections.defaultdict(dict)
        self.net_pads = collections.defaultdict(list)
        # one occupancy map per board side; self.side picks the active one
        self.occ = {}
        for side in 'FB':
            occupancy = Occupancy(
                Rect(0, 0, BOARD_WIDTH, BOARD_HEIGHT), EDGE_MARGIN, PASSIVE_GAP
            )
            occupancy.keepouts += [ANTENNA_NOTCH, *ANTENNA_KEEPOUTS]
            occupancy.keepouts += corner_keepouts()
            self.occ[side] = occupancy
        self.side = 'F'
        self.side_of = {}
        self.net_items = {}
        self.module = {}
        self.bumps = {}
        self.box_lines = {}
        self.text_dims = {}
        self.pad_boxes = {}
        self.pockets = {}
        self.pin_pockets = {}
        self.require_pockets = True
        self.early_labels = {}
        self.label_pockets = {}
        for name, nodes in self.nets.items():
            for ref, pad in nodes:
                self.pad_net[ref][pad] = short_net(name)
                self.net_pads[short_net(name)].append((ref, pad))

    @property
    def occupancy(self):
        """Occupancy map of the side being worked on."""
        return self.occ[self.side]

    @property
    def silk_layer(self):
        return pcbnew.F_SilkS if self.side == 'F' else pcbnew.B_SilkS

    def local_rect(self, ref, side):
        """Footprint-local courtyard rect; KiCad mirrors local y on the back."""
        rect = self.local_rects[ref]
        if side == 'B':
            return Rect(rect.min_x, -rect.max_y, rect.max_x, -rect.min_y)
        return rect

    def block_other_side(self, ref, side):
        """Through-hole pins also occupy the opposite side."""
        boxes = [
            pad.GetBoundingBox()
            for pad in self.footprints[ref].Pads()
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        ]
        if not boxes:
            return
        other = 'B' if side == 'F' else 'F'
        self.occ[other].add(
            f'{ref}~tht',
            Rect(
                min(b.GetLeft() for b in boxes) / 1e6,
                min(b.GetTop() for b in boxes) / 1e6,
                max(b.GetRight() for b in boxes) / 1e6,
                max(b.GetBottom() for b in boxes) / 1e6,
            ).inflated(0.3),
        )

    def block_via(self, name, x, y, radius):
        """A pre-placed via blocks parts on both sides."""
        for occupancy in self.occ.values():
            occupancy.add(name, Rect(x - radius, y - radius, x + radius, y + radius))

    def load_footprints(self):
        for ref, part in self.parts.items():
            path, name = footprint_path(part['footprint'])
            footprint = pcbnew.FootprintLoad(path, name)
            if footprint is None:
                raise RuntimeError(f'missing footprint {part["footprint"]}')
            pcbmodels.attach_missing_models(footprint)
            footprint.SetReference(ref)
            pcbmodels.apply_connector_colour(footprint)
            footprint.SetValue(part['value'])
            # library link and symbol fields as the schematic has them, so
            # the board matches the schematic in a parity check
            footprint.SetFPIDAsString(part['footprint'])
            for name, text in part.get('fields', {}).items():
                footprint.SetField(name, text)
                footprint.GetField(name).SetVisible(False)
            footprint.Reference().SetTextSize(
                pcbnew.VECTOR2I(to_internal(0.8), to_internal(0.8))
            )
            footprint.Reference().SetTextThickness(to_internal(0.15))
            text_box = footprint.Reference().GetBoundingBox()
            self.text_dims[ref] = (
                text_box.GetWidth() / 1e6 + 0.2,
                text_box.GetHeight() / 1e6 + 0.2,
            )
            footprint.Value().SetVisible(False)
            self.footprints[ref] = footprint
            # on the board from the start: Flip() needs a parent board
            self.board.Add(footprint)
            courtyard = footprint.GetCourtyard(pcbnew.F_CrtYd).BBox()
            local = Rect(
                courtyard.GetX() / 1e6,
                courtyard.GetY() / 1e6,
                (courtyard.GetX() + courtyard.GetWidth()) / 1e6,
                (courtyard.GetY() + courtyard.GetHeight()) / 1e6,
            )
            self.local_rects[ref] = LOCAL_RECT_OVERRIDES.get(
                part['footprint'], local
            )
            self.pad_local[ref] = {}
            for pad in footprint.Pads():
                position = pad.GetPosition()
                self.pad_local[ref].setdefault(pad.GetNumber(), []).append(
                    (position.x / 1e6, position.y / 1e6)
                )
                net_name = self.pad_net[ref].get(pad.GetNumber())
                if net_name is not None:
                    pad.SetNet(self.net_item(self.full_net(net_name)))

    def full_net(self, short):
        for name in self.nets:
            if short_net(name) == short:
                return name
        raise KeyError(short)

    def net_item(self, name):
        item = self.net_items.get(name)
        if item is None:
            item = self.board.FindNet(name)
        if item is None:
            item = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(item)
            self.net_items[name] = item
        return item

    def pad_position(self, ref, pad, index=0):
        center_x, center_y, angle = self.centers[ref]
        local_x, local_y = self.pad_local[ref][pad][index]
        if self.side_of.get(ref, self.side) == 'B':
            local_y = -local_y
        rotated_x, rotated_y = rotate_point(local_x, local_y, angle)
        return center_x + rotated_x, center_y + rotated_y

    def place(self, ref, center_x, center_y, angle):
        """Places a part on the active side (flipped onto the back for 'B')."""
        footprint = self.footprints[ref]
        side = self.side
        if (side == 'B') != footprint.IsFlipped():
            footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        footprint.SetPosition(
            pcbnew.VECTOR2I(to_internal(center_x), to_internal(center_y))
        )
        footprint.SetOrientationDegrees(angle)
        self.centers[ref] = (center_x, center_y, angle)
        self.side_of[ref] = side
        self.occupancy.add(
            ref,
            placed_rect(self.local_rect(ref, side), center_x, center_y, angle),
        )
        self.block_other_side(ref, side)

    def is_passive(self, ref):
        """Every part not placed by hand (PLACEMENT) is placed beside the pad
        it serves.
        """
        return ref not in PLACEMENT

    def preferred_side(self, ref, target=None):
        """LEDs (seen from the top), jumpers and tall electrolytics go on the
        top, test points on the side of the IC they test; everything else
        starts on the side of the part it serves (10 mm clearance below).
        """
        footprint = self.parts[ref]['footprint']
        if ref.startswith('JP') or 'LED' in footprint or 'CP_Elec' in footprint:
            return 'F'
        if ref.startswith('TP') and target is not None:
            return self.test_point_side(ref, target)
        if target is not None and target[0] in self.side_of:
            return self.side_of[target[0]]
        return 'F'

    def test_point_side(self, ref, target):
        """Side of the part a test point tests, so both are probed from the
        same side.
        """
        return self.side_of.get(self.tested_part(ref, target[0]), 'F')

    def tested_part(self, ref, near):
        """The part a test point tests: the placed IC (not a passive) on its
        net nearest to `near`, else `near` itself.
        """
        net = self.pad_net[ref].get('1')
        if net in GROUND_NETS or near not in self.centers:
            return near
        ics = [
            other
            for other, _ in self.net_pads.get(net, [])
            if other in self.centers and not other.startswith(('R', 'C', 'L', 'TP', 'JP'))
        ]
        if not ics:
            return near
        # the hand-placed ICs are what the test points are for
        ics = [other for other in ics if other in PLACEMENT] or ics
        near_x, near_y, _ = self.centers[near]
        return min(
            ics,
            key=lambda other: (self.centers[other][0] - near_x) ** 2
            + (self.centers[other][1] - near_y) ** 2,
        )

    def iso_side_passives(self):
        """Passives of the Amp Current sheet that sit on the isolated side:
        those touching ISO_GND / ISO_3V3, plus passives chained to them
        through signal nets (the ACS37800 divider).
        """
        if getattr(self, '_iso_refs', None) is not None:
            return self._iso_refs
        candidates = [
            ref
            for ref in self.parts
            if ref[0] in 'RC' and self.parts[ref]['sheet'] == 'Amp Current'
        ]

        def nets_of(ref):
            return {self.pad_net[ref].get(pad) for pad in self.pad_local[ref]}

        iso = {ref for ref in candidates if nets_of(ref) & ISO_NETS}
        changed = True
        while changed:
            changed = False
            signal_nets = set()
            for ref in iso:
                signal_nets |= nets_of(ref) - POWER_NETS - {None}
            for ref in candidates:
                if ref not in iso and nets_of(ref) & signal_nets:
                    iso.add(ref)
                    changed = True
        self._iso_refs = iso
        return iso

    def is_iso_side(self, ref):
        """True for parts on the isolated (ISO_GND) side of the barrier."""
        if ref in self.iso_side_passives():
            return True
        if ref[0] in 'RC' and self.parts[ref]['sheet'] == 'Amp Current':
            return False
        if not (ref.startswith('TP') or self.parts[ref]['sheet'] == 'Debug'):
            return False
        return any(
            self.pad_net[ref].get(pad) in ISO_NETS
            for pad in self.pad_local[ref]
        )

    def part_module(self, ref):
        """Module box of a part: its sheet's module, else the module of the
        switched supply net it sits on (jumpers and their LEDs), else None.
        """
        module = pcbfloorplan.module_of_sheet(self.parts[ref]['sheet'])
        if module is not None:
            return module
        for pad in self.pad_local[ref]:
            switched = SWITCHED_NETS.get(self.pad_net[ref].get(pad))
            if switched is not None:
                return switched
        return None

    def place_anchors(self):
        for ref, (center_x, center_y, angle, *side) in PLACEMENT.items():
            if ref not in self.footprints:
                raise KeyError(f'PLACEMENT names unknown ref {ref}')
            self.side = side[0] if side else 'F'
            self.place(ref, center_x, center_y, angle)
            self.module[ref] = self.part_module(ref)
        self.side = 'F'
        for index, (hole_x, hole_y) in enumerate(HOLES):
            for occupancy in self.occ.values():
                occupancy.add(
                    f'hole{index}',
                    Rect(hole_x - 3.4, hole_y - 3.4, hole_x + 3.4, hole_y + 3.4),
                )

    def add_track(self, net, layer, points, width, locked=True):
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(self.board)
            track.SetLayer(layer)
            track.SetWidth(to_internal(width))
            track.SetStart(
                pcbnew.VECTOR2I(to_internal(start[0]), to_internal(start[1]))
            )
            track.SetEnd(
                pcbnew.VECTOR2I(to_internal(end[0]), to_internal(end[1]))
            )
            track.SetNet(self.net_item(self.full_net(net)))
            track.SetLocked(locked)
            self.board.Add(track)

    def pre_route_current_path(self, width=2.0):
        """Wide locked traces for the amplifier current path J11 -> U18 pins
        1-4 / 5-8 -> J12.
        """
        for connector, net, pins, end_cap in (
            ('J11', 'Net-(J11-Pin_1)', ('1', '2', '3', '4'), 'down'),
            ('J12', 'Net-(J12-Pin_1)', ('5', '6', '7', '8'), 'up'),
        ):
            start_x, start_y = self.pad_position(connector, '1')
            pad_points = [self.pad_position('U18', pin) for pin in pins]
            column_x = sum(point[0] for point in pad_points) / len(pad_points)
            top = min(point[1] for point in pad_points)
            bottom = max(point[1] for point in pad_points)
            end_y = bottom - 0.8 if end_cap == 'down' else top + 0.8
            self.add_track(
                net,
                pcbnew.F_Cu,
                [(start_x, start_y), (column_x, start_y), (column_x, end_y)],
                width,
            )
            margin = width / 2 + 0.6
            self.occupancy.add(
                f'{connector}_current_a',
                Rect(
                    min(start_x, column_x) - margin,
                    start_y - margin,
                    max(start_x, column_x) + margin,
                    start_y + margin,
                ),
            )
            self.occupancy.add(
                f'{connector}_current_b',
                Rect(
                    column_x - margin,
                    min(start_y, end_y) - margin,
                    column_x + margin,
                    max(start_y, end_y) + margin,
                ),
            )

    def add_outline_and_keepouts(self):
        notch = ANTENNA_NOTCH
        corners = [
            (0, 0),
            (notch.min_x, 0),
            (notch.min_x, notch.max_y),
            (notch.max_x, notch.max_y),
            (notch.max_x, 0),
            (BOARD_WIDTH, 0),
            (BOARD_WIDTH, BOARD_HEIGHT),
            (0, BOARD_HEIGHT),
        ]
        for index, (start_x, start_y) in enumerate(corners):
            end_x, end_y = corners[(index + 1) % len(corners)]
            segment = pcbnew.PCB_SHAPE(self.board)
            segment.SetShape(pcbnew.SHAPE_T_SEGMENT)
            segment.SetLayer(pcbnew.Edge_Cuts)
            segment.SetWidth(to_internal(0.1))
            segment.SetStart(
                pcbnew.VECTOR2I(to_internal(start_x), to_internal(start_y))
            )
            segment.SetEnd(
                pcbnew.VECTOR2I(to_internal(end_x), to_internal(end_y))
            )
            self.board.Add(segment)

    # ─── passive placement ───

    def candidate_targets(self, ref, pad):
        """Placed pads (other than ref's) that this passive pin should sit next
        to.
        """
        net = self.pad_net[ref].get(pad)
        if ref.startswith('JP') and net not in SWITCHED_NETS:
            return []
        if ref.startswith('TP') and net in GROUND_NETS:
            return [self.ground_tp_anchor(ref, net)]
        if net is None or net in GROUND_NETS:
            return []
        sheet = self.parts[ref]['sheet']
        found = []
        for other_ref, other_pad in self.net_pads[net]:
            if other_ref == ref or other_ref not in self.centers:
                continue
            is_passive = self.is_passive(other_ref)
            if net in POWER_NETS and (
                is_passive or self.parts[other_ref]['sheet'] != sheet
            ):
                continue
            found.append((other_ref, other_pad))
        if not found and net in POWER_NETS:
            found = [
                (r, p)
                for r, p in self.net_pads[net]
                if r != ref and r in self.centers and not self.is_passive(r)
            ]
        return found

    def ground_tp_anchor(self, ref, net):
        if net == 'ISO_GND':
            return ISO_GND_TP_ANCHOR
        ground_tps = sorted(
            (
                r
                for r in self.parts
                if r.startswith('TP')
                and self.pad_net[r].get('1') == 'GND'
            ),
            key=lambda r: int(r[2:]),
        )
        return GND_TP_ANCHORS[ground_tps.index(ref) % len(GND_TP_ANCHORS)]

    # ─── label pockets ───

    def find_pocket(self, part_rect, module, width, height, gap=0.15):
        """Free spot for a label box of the given size right beside a part
        rectangle (inside the module box); returns (x, y, turned, rect) or
        None. Labels beside the long sides are tried upright, then turned.
        """
        center_x = (part_rect.min_x + part_rect.max_x) / 2
        center_y = (part_rect.min_y + part_rect.max_y) / 2
        obstacles = self.pocket_obstacles(part_rect.inflated(max(width, height) + 2.5))
        for turned in (False, True):
            box_w, box_h = (height, width) if turned else (width, height)
            for shift in (0.0, 0.6, -0.6, 1.2, -1.2, 1.8, -1.8):
                for spot_x, spot_y in (
                    (center_x + shift, part_rect.min_y - gap - box_h / 2),
                    (center_x + shift, part_rect.max_y + gap + box_h / 2),
                    (part_rect.min_x - gap - box_w / 2, center_y + shift),
                    (part_rect.max_x + gap + box_w / 2, center_y + shift),
                ):
                    rect = Rect(
                        spot_x - box_w / 2,
                        spot_y - box_h / 2,
                        spot_x + box_w / 2,
                        spot_y + box_h / 2,
                    )
                    if not self.inside_a_box(rect, module):
                        continue
                    if not rect.inside(self.occupancy.board_rect):
                        continue
                    if any(rect.overlaps(k) for k in self.occupancy.keepouts):
                        continue
                    if any(rect.overlaps(other) for other in obstacles):
                        continue
                    return spot_x, spot_y, turned, rect
        return None

    def inside_a_box(self, rect, module=None):
        """True if a text box lies inside the given module's box, or with no
        module inside any one box (so it never crosses a section line).
        """
        if module:
            return pcbfloorplan.text_inside(module, rect, self.side)
        return any(
            pcbfloorplan.text_inside(name, rect, self.side)
            for name in pcbfloorplan.modules(self.side)
        )

    def pocket_obstacles(self, around=None):
        """Boxes a label pocket must keep off: other pockets, silk, holes,
        the candidate being tested, and for placed parts only their pad
        boxes (the courtyard margin around them is free for text). With
        `around`, only the boxes near that rect.
        """
        boxes = []
        rects = self.occupancy.rects
        names = rects.near(around) if around is not None else list(rects)
        for name in names:
            rect = rects[name]
            if name.startswith('txt_pin'):
                boxes.append(rect.inflated(0.25))
            elif name.startswith(('txt_', 'silk_', 'hole', 'candidate')):
                boxes.append(rect.inflated(0.05))
            elif name in PLACEMENT and name in self.centers:
                # big parts keep their whole body clear (the ESP32 its pads)
                boxes.append(self.body_rect(name) if name == 'U1' else self.part_extent(name))
            elif name in self.centers:
                outline = self.silk_extent(name)
                if outline is not None:
                    boxes.append(outline.inflated(0.1))
                pad_box = self.pad_boxes.get(name)
                if pad_box is None:
                    boxes_for_part = [
                        pad.GetBoundingBox()
                        for pad in self.footprints[name].Pads()
                    ]
                    pad_box = Rect(
                        min(b.GetLeft() for b in boxes_for_part) / 1e6,
                        min(b.GetTop() for b in boxes_for_part) / 1e6,
                        max(b.GetRight() for b in boxes_for_part) / 1e6,
                        max(b.GetBottom() for b in boxes_for_part) / 1e6,
                    )
                    self.pad_boxes[name] = pad_box
                boxes.append(pad_box.inflated(0.1))
            else:
                boxes.append(rect)
        return boxes

    def silk_extent(self, ref):
        """Box around a placed part's own silkscreen outline, or None."""
        cache = self.__dict__.setdefault('_silk_extents', {})
        if ref not in cache:
            boxes = [
                item.GetBoundingBox()
                for item in self.footprints[ref].GraphicalItems()
                if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)
            ]
            cache[ref] = Rect(
                min(b.GetLeft() for b in boxes) / 1e6,
                min(b.GetTop() for b in boxes) / 1e6,
                max(b.GetRight() for b in boxes) / 1e6,
                max(b.GetBottom() for b in boxes) / 1e6,
            ) if boxes else None
        return cache[ref]

    def part_extent(self, ref):
        """A placed part's courtyard grown to cover its silkscreen outline
        (text beside it keeps off both).
        """
        rect = self.occ[self.side_of[ref]].rects[ref]
        outline = self.silk_extent(ref)
        if outline is None:
            return rect
        return Rect(
            min(rect.min_x, outline.min_x), min(rect.min_y, outline.min_y),
            max(rect.max_x, outline.max_x), max(rect.max_y, outline.max_y),
        )

    def label_size(self, ref):
        """Box size of the part label (SILK_LABELS) for a ref, or None."""
        if ref not in SILK_LABELS:
            return None
        box = self.text_rect(SILK_LABELS[ref], 0, 0, SILK_TEXT_SIZE)
        return box.max_x - box.min_x, box.max_y - box.min_y

    def reserve_pockets(self, ref, part_rect, module):
        """Reserves room for the part label (if the part has one) and the
        reference text beside a part, the label first; returns False if
        either has no room (what did fit stays reserved).
        """
        ok = True
        for kind, size in (
            ('label', None if ref in self.label_pockets else self.label_size(ref)),
            ('ref', self.text_dims[ref]),
        ):
            if size is None:
                continue
            pocket = self.find_pocket(part_rect, module, *size)
            if pocket is None:
                ok = False
                continue
            spot_x, spot_y, turned, rect = pocket
            self.occupancy.add(f'txt_{kind}_{ref}', rect)
            (self.pockets if kind == 'ref' else self.label_pockets)[ref] = (
                spot_x, spot_y, turned,
            )
        return ok

    def pin_label_boxes(self, ref, side, body=None):
        """Label boxes for a connector's pins on one side of its body:
        [(text, centre x, centre y, turned, rect)], or None if any is off the
        board.
        """
        footprint = self.footprints[ref]
        pads = {
            int(pad.GetNumber()): (
                pad.GetPosition().x / 1e6,
                pad.GetPosition().y / 1e6,
            )
            for pad in footprint.Pads()
            if pad.GetNumber().isdigit()
        }
        if body is None:
            body = self.part_extent(ref)
        column = side in ('left', 'right')
        # pads in line across the label strip (a 2-row header) share one label
        groups = {}
        for number, text in enumerate(PIN_LABELS[ref], start=1):
            pad_x, pad_y = pads[number]
            key = round(pad_y if column else pad_x, 1)
            groups.setdefault(key, (pad_x, pad_y, []))[2].append(text)
        labels = []
        for pad_x, pad_y, texts in groups.values():
            text = '/'.join(texts)
            base = self.text_rect(text, 0, 0, SILK_TEXT_SIZE)
            labels.append((pad_x, pad_y, text, 2 * base.max_x, 2 * base.max_y))
        # on a pitch finer than the text height every second label moves out
        # past its neighbours so the strip stays readable
        keys = sorted(round(y if column else x, 3) for x, y, *_ in labels)
        pitch = min((b - a for a, b in zip(keys, keys[1:])), default=99.0)
        labels.sort(key=lambda label: label[1] if column else label[0])
        pushes = [0.0] * len(labels)
        if labels and pitch < max(label[4] for label in labels) + 0.15:
            # push whichever alternate set keeps the strip shortest
            options = []
            for parity in (0, 1):
                near = [l[3] for i, l in enumerate(labels) if i % 2 != parity]
                far = [l[3] for i, l in enumerate(labels) if i % 2 == parity]
                push = max(near, default=0.0) + 0.2
                options.append((push + max(far, default=0.0), parity, push))
            _, parity, push = min(options)
            pushes = [push if i % 2 == parity else 0.0 for i in range(len(labels))]
        boxes = []
        for index, (pad_x, pad_y, text, length, thickness) in enumerate(labels):
            push = pushes[index]
            if column:
                width, height = length, thickness
                center_y = pad_y
                center_x = (
                    body.max_x + 0.2 + push + width / 2
                    if side == 'right'
                    else body.min_x - 0.2 - push - width / 2
                )
            else:
                width, height = thickness, length
                center_x = pad_x
                center_y = (
                    body.max_y + 0.2 + push + height / 2
                    if side == 'down'
                    else body.min_y - 0.2 - push - height / 2
                )
            rect = Rect(
                center_x - width / 2,
                center_y - height / 2,
                center_x + width / 2,
                center_y + height / 2,
            )
            boxes.append((text, center_x, center_y, not column, rect))
        return boxes

    def reserve_pin_labels(self, ref):
        """Reserves a label beside every pad of a connector, on the side
        facing the board interior if it is free, else the other sides.
        """
        body = self.occupancy.rects[ref]
        centre_x = (body.min_x + body.max_x) / 2
        centre_y = (body.min_y + body.max_y) / 2
        pads = [pad.GetPosition() for pad in self.footprints[ref].Pads()]
        spread_x = max(p.x for p in pads) - min(p.x for p in pads)
        spread_y = max(p.y for p in pads) - min(p.y for p in pads)
        if spread_x < spread_y:
            sides = ['right', 'left'] if centre_x < BOARD_WIDTH / 2 else ['left', 'right']
        else:
            sides = ['up', 'down'] if centre_y > BOARD_HEIGHT / 2 else ['down', 'up']
        module = self.module_of_ref(ref)
        if self.try_pin_labels(ref, sides, None, module):
            return True
        # a through-hole connector's pins also show on the other side, where
        # the strip goes beside the pin row (in whichever box it falls)
        home = self.side
        self.side = 'B' if home == 'F' else 'F'
        placed = self.try_pin_labels(
            ref, ['up', 'down', 'right', 'left'], self.other_side_part(ref), None
        )
        self.side = home
        if placed:
            return True
        print('no room for the pin labels of', ref)
        return False

    def try_pin_labels(self, ref, sides, body, module):
        """Reserves the pin label strip on the first free side (active board
        side); returns False if none is free.
        """
        for side in sides:
            boxes = self.pin_label_boxes(ref, side, body)
            obstacles = self.pocket_obstacles()
            if all(
                rect.inside(self.occupancy.board_rect)
                and not any(rect.overlaps(k) for k in self.occupancy.keepouts)
                and self.inside_a_box(rect, module)
                and not any(rect.overlaps(o) for o in obstacles)
                for *_, rect in boxes
            ):
                for index, (_, _, _, _, rect) in enumerate(boxes):
                    self.occupancy.add(f'txt_pin_{ref}_{index}', rect)
                self.pin_pockets[ref] = (self.side, boxes)
                return True
        return False

    def add_pin_labels(self):
        """Prints the connector pin labels reserved above."""
        for ref, (side, labels) in self.pin_pockets.items():
            if side != self.side:
                continue
            for index, (text, spot_x, spot_y, turned, rect) in enumerate(labels):
                item = self.add_text(
                    text,
                    spot_x,
                    spot_y,
                    SILK_TEXT_SIZE,
                    thickness=SILK_TEXT_THICKNESS,
                )
                if turned:
                    item.SetTextAngleDegrees(90)
                self.occupancy.add(f'silk_pin_{ref}_{index}', rect)

    def reserve_module_labels(self):
        """Picks each module box's title spot now, so parts placed later keep
        clear of it.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 3.4) for hole_x, hole_y in HOLES]
        self.early_labels = {}
        for side in 'FB':
            self.side = side
            for module in pcbfloorplan.modules(side):
                # only border spots now; a title inside its box waits until
                # the parts are placed
                spot = self.module_label_spot(module, board_rect, holes, inside=False)
                self.early_labels[(module, side)] = spot
                if spot is not None:
                    self.occupancy.add(
                        f'silk_label_{module}',
                        self.title_box(spot),
                    )
        self.side = 'F'

    def reserve_connector_pin_labels(self):
        """Pin label strips go first: they must sit at their pads, while
        section titles can move along their borders.
        """
        for ref in PIN_LABELS:
            self.side = self.side_of[ref]
            self.reserve_pin_labels(ref)
        self.side = 'F'

    def reserve_connector_labels(self):
        """Reserves each connector's function label (an I/O label) right after
        its pin labels: beside the connector, else beside its pins on the
        other side; the short form is tried when the full one has no room.
        """
        missing = []
        for ref, full in SILK_LABELS.items():
            if not self.is_connector(ref) or ref not in PLACEMENT:
                continue
            home = self.side_of[ref]
            spot = None
            for side in (home, 'B' if home == 'F' else 'F'):
                self.side = side
                part = self.part_extent(ref) if side == home else self.other_side_part(ref)
                module = self.module.get(ref) if side == home else None
                for text in (full, *SILK_LABEL_SHORT.get(ref, ())):
                    box = self.text_rect(text, 0, 0, SILK_TEXT_SIZE)
                    pocket = self.find_pocket(
                        part, module, box.max_x - box.min_x, box.max_y - box.min_y
                    )
                    if pocket is not None:
                        spot = (*pocket, side, text)
                        break
                if spot is not None:
                    break
            if spot is None:
                missing.append(ref)
                continue
            spot_x, spot_y, turned, rect, side, text = spot
            self.occ[side].add(f'txt_label_{ref}', rect)
            self.label_pockets[ref] = (spot_x, spot_y, turned, side, text)
        self.side = 'F'
        print('connector labels with no room:', missing)

    def reserve_anchor_pockets(self):
        """Reserves label room beside every placed (non-passive) part before
        the passives crowd in.
        """
        missing = []
        for ref in PLACEMENT:
            self.side = self.side_of[ref]
            module = self.module.get(ref)
            part = self.part_extent(ref)
            if not self.reserve_pockets(ref, part, module):
                missing.append(ref)
        self.side = 'F'
        print('no label room beside:', missing)

    def place_passives(self):
        crowd = collections.Counter()
        pending = [ref for ref in self.parts if self.is_passive(ref)]
        tht = {ref: self.has_tht(ref) for ref in pending}
        offsets = ring_offsets(60.0, 0.5)
        unplaced = []
        while pending:
            progressed = False
            # through-hole parts first (they need room on both sides), then
            # big parts so small ones fill the gaps they leave (test points
            # rank by size too, so they and their labels sit close to the
            # part); the Power Good sheet last, it takes what is left
            pending.sort(
                key=lambda r: (
                    not tht[r],
                    self.parts[r]['sheet'] == 'Power Good',
                    -round(self.part_area(r)),
                    self.is_decoupling(r),
                    int(r.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
                )
            )
            for ref in list(pending):
                choice = self.pick_target(ref, crowd)
                if choice is None:
                    continue
                pad_index, target = choice
                if not self.place_either_side(ref, pad_index, target, offsets):
                    unplaced.append(ref)
                else:
                    crowd[target] += 1
                pending.remove(ref)
                progressed = True
                break
            if not progressed:
                unplaced.extend(pending)
                break
        # second pass for the parts that found no spot with room for their
        # labels: place them anyway, their labels are searched for afterwards.
        # The third pass may also take the room held for a placed passive's
        # reference text; that text then finds another spot or is hidden.
        self.require_pockets = False
        fine = ring_offsets(30.0, 0.25)  # finer steps find the last gaps
        for evict in (False, True):
            retry, unplaced = unplaced, []
            for ref in retry:
                choice = self.pick_target(ref, crowd)
                if choice is not None and self.place_either_side(
                    ref, choice[0], choice[1], fine if evict else offsets, evict
                ):
                    crowd[choice[1]] += 1
                else:
                    unplaced.append(ref)
        self.require_pockets = True
        return unplaced

    def place_either_side(self, ref, primary_pad, target, offsets, evict=False):
        """Tries the part's preferred side, then the other one. Debug-sheet
        parts (test points, rail LEDs) that find no room in the box of the
        part they serve then take the nearest free spot in any box.
        """
        first = self.preferred_side(ref, target)
        tries = [(first, False), ('B' if first == 'F' else 'F', False)]
        if 'LED' in self.parts[ref]['footprint']:
            # an indicator is only any use where it can be seen: the top
            tries = [('F', False)]
        if ref.startswith('TP'):
            # a test point stays on the side of the part it tests; in the
            # last pass it takes the nearest free spot in any box, so it
            # sits beside the part rather than far off in its own box
            tries = [(first, evict)]
        elif evict and self.parts[ref]['sheet'] == 'Debug':
            # any box is the last resort, after the passes that drop the
            # text spot have tried the part's own box
            tries += [(side, True) for side, _ in tries]
        for side, any_module in tries:
            self.side = side
            if self.place_near(
                ref, primary_pad, target, offsets, any_module, evict
            ):
                self.side = 'F'
                return True
        self.side = 'F'
        self.side_of.pop(ref, None)
        return False

    @staticmethod
    def is_connector(ref):
        """True for board connectors (J1, J2, ...), not jumpers (JP1, ...)."""
        return ref.startswith('J') and not ref.startswith('JP')

    def has_tht(self, ref):
        """True if the part has through-hole pads."""
        return any(
            pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            for pad in self.footprints[ref].Pads()
        )

    def part_area(self, ref):
        """Courtyard area of a part (mm²)."""
        rect = self.local_rects[ref]
        return (rect.max_x - rect.min_x) * (rect.max_y - rect.min_y)

    def is_decoupling(self, ref):
        nets = [self.pad_net[ref].get(pad) for pad in self.pad_local[ref]]
        return all(net in POWER_NETS for net in nets)

    def pick_target(self, ref, crowd):
        """Returns (pad number to bring close, (target ref, target pad)) or
        None if nothing placed yet.
        """
        best = None
        for pad in self.pad_local[ref]:
            targets = self.candidate_targets(ref, pad)
            if not targets:
                continue
            signal = self.pad_net[ref][pad] not in POWER_NETS
            for target in targets:
                crowd_penalty = crowd[target]
                key = (
                    0 if signal else 1,
                    crowd_penalty,
                    self.parts[target[0]]['sheet'] != self.parts[ref]['sheet'],
                )
                if best is None or key < best[0]:
                    best = (key, pad, target)
        if best is None:
            return None
        return best[1], best[2]

    def place_near(
        self, ref, primary_pad, target, offsets, any_module=False, evict=False
    ):
        target_x, target_y = self.pad_position(*target)
        other_pad = next(
            (pad for pad in self.pad_local[ref] if pad != primary_pad), None
        )
        other_net = self.pad_net[ref].get(other_pad)
        other_points = []
        if other_net is not None and other_net not in POWER_NETS:
            other_points = [
                self.pad_position(r, p)
                for r, p in self.net_pads[other_net]
                if r != ref and r in self.centers and r != target[0]
            ]
        local_rect = self.local_rect(ref, self.side)
        self.side_of[ref] = self.side  # pad_position mirrors for the back
        # a passive stays in its own module's box; debug parts (no module)
        # join the box of the part they sit beside
        module = self.part_module(ref) or self.module.get(target[0])
        if ref.startswith('TP') and module in TEST_POINTS_OUTSIDE:
            module = TEST_POINT_OVERFLOW
        # a part's centre lies inside the region that holds it: skip the
        # offsets outside every candidate region without testing angles
        bounds = (
            pcbfloorplan.regions(module, self.side)
            if module and not any_module
            else [self.occupancy.board_rect]
        )
        # a test point keeps close to its part until the last pass
        # (ground loops excepted: any ground will do)
        reach = None
        if (
            ref.startswith('TP')
            and not evict
            and self.pad_net[ref].get(primary_pad) not in GROUND_NETS
        ):
            reach = TEST_POINT_REACH
        best = None
        for offset_x, offset_y in offsets:
            distance = (offset_x**2 + offset_y**2) ** 0.5
            if best is not None and distance > best[0] + 1.5:
                break
            if reach is not None and distance > reach:
                break
            center_x, center_y = target_x + offset_x, target_y + offset_y
            if not any(
                r.min_x < center_x < r.max_x and r.min_y < center_y < r.max_y
                for r in bounds
            ):
                continue
            for angle in (0, 90, 180, 270):
                rect = placed_rect(local_rect, center_x, center_y, angle)
                if any_module:
                    module = next(
                        (
                            name
                            for name in pcbfloorplan.modules(self.side)
                            if pcbfloorplan.region_contains(name, rect, self.side)
                        ),
                        None,
                    )
                    if module is None:
                        continue
                elif module and not pcbfloorplan.region_contains(
                    module, rect, self.side
                ):
                    continue
                if not self.occupancy.is_free(rect, self.evictable(rect, evict)):
                    continue
                # through-hole pins come out on the other side too
                if self.has_tht(ref) and not self.occ[
                    'B' if self.side == 'F' else 'F'
                ].is_free(rect.inflated(-0.3)):
                    continue
                inside_iso = rect.inside(ISO_REGION.inflated(-0.3))
                touches_iso = rect.inflated(ISO_BAND).overlaps(ISO_REGION)
                iso_side = self.is_iso_side(ref)
                if iso_side != inside_iso or (not iso_side and touches_iso):
                    continue
                self.centers[ref] = (center_x, center_y, angle)
                primary = self.pad_position(ref, primary_pad)
                score = (
                    (primary[0] - target_x) ** 2 + (primary[1] - target_y) ** 2
                ) ** 0.5
                if other_points:
                    other = self.pad_position(ref, other_pad)
                    score += 0.2 * min(
                        ((other[0] - x) ** 2 + (other[1] - y) ** 2) ** 0.5
                        for x, y in other_points
                    )
                del self.centers[ref]
                if best is None or score < best[0]:
                    pockets = self.pockets_for(ref, rect, module)
                    if pockets is not None:
                        best = (score, center_x, center_y, angle, pockets, module)
        if best is None:
            return False
        placed = placed_rect(local_rect, best[1], best[2], best[3])
        for name in self.evictable(placed, evict):
            if placed.inflated(self.occupancy.gap).overlaps(self.occupancy.rects[name]):
                del self.occupancy.rects[name]
                self.pockets.pop(name.removeprefix('txt_ref_'), None)
        self.place(ref, best[1], best[2], best[3])
        self.module[ref] = best[5]
        for name, kind, spot, pocket_rect in best[4]:
            self.occupancy.add(name, pocket_rect)
            (self.pockets if kind == 'ref' else self.label_pockets)[ref] = spot
        return True

    def evictable(self, rect, evict):
        """Reference-text pockets of placed passives near rect that a part
        may take over (only when evict is set).
        """
        if not evict:
            return set()
        return {
            name
            for name in self.occupancy.rects.near(rect.inflated(self.occupancy.gap))
            if name.startswith('txt_ref_')
            and self.is_passive(name.removeprefix('txt_ref_'))
        }

    def pockets_for(self, ref, rect, module):
        """Pockets for a candidate position of a passive, or None if there is
        no room beside it for its label(s). The candidate itself is held in
        the occupancy while looking so the pockets stay clear of it.
        """
        found = []
        self.occupancy.add('candidate', rect)
        try:
            for kind, size in (
                ('ref', self.text_dims[ref]),
                ('label', self.label_size(ref)),
            ):
                if size is None:
                    continue
                pocket = self.find_pocket(rect, module, *size)
                if pocket is None:
                    if self.require_pockets:
                        return None
                    continue  # second pass: the label is searched for later
                spot_x, spot_y, turned, pocket_rect = pocket
                name = f'txt_{kind}_{ref}'
                found.append(
                    (name, kind, (spot_x, spot_y, turned), pocket_rect)
                )
                self.occupancy.add(name + '_tmp', pocket_rect)
        finally:
            del self.occupancy.rects['candidate']
            for tmp in [n for n in self.occupancy.rects if n.endswith('_tmp')]:
                del self.occupancy.rects[tmp]
        return found

    # ─── rules, zones, routing ───

    def add_net_classes(self):
        settings = self.board.GetDesignSettings()
        settings.m_MinClearance = to_internal(0.15)
        settings.m_TrackMinWidth = to_internal(0.15)
        settings.m_ViasMinSize = to_internal(VIA_IN_PAD_DIAMETER)
        settings.m_ViasMinAnnulus = to_internal(0.075)
        settings.m_MinThroughDrill = to_internal(0.2)
        settings.m_CopperEdgeClearance = to_internal(0.3)
        settings.m_HoleClearance = to_internal(0.15)
        net_settings = settings.m_NetSettings
        default = net_settings.GetDefaultNetclass()
        default.SetClearance(to_internal(0.15))
        default.SetTrackWidth(to_internal(0.25))
        default.SetViaDiameter(to_internal(0.6))
        default.SetViaDrill(to_internal(0.3))
        classes = {
            'Power': (
                0.3,
                0.6,
                0.3,
                [
                    '+3V3',
                    '+5V',
                    '+15V',
                    '-15V',
                    '+16V5',
                    '-16V5',
                    'ISO_3V3',
                    'USB_VBUS',
                    '+3V3_SG',
                    '+5V_PS15',
                    '+5V_ISO',
                    '+3V3_COOL',
                    '+3V3_CH',
                ],
            ),
            'Power12V': (
                0.8,
                0.7,
                0.35,
                ['VIN', 'VSW', '+12V', 'Net-(J2-Pin_1)'],
            ),
            'Usb': (
                0.2,
                0.6,
                0.3,
                [
                    'Net-(U1-USB_D+)',
                    'Net-(U1-USB_D-)',
                    'Net-(J1-D+-PadA6)',
                    'Net-(J1-D--PadA7)',
                ],
            ),
        }
        for name, (width, via_diameter, via_drill, nets) in classes.items():
            netclass = pcbnew.NETCLASS(name)
            netclass.SetClearance(to_internal(0.15))
            netclass.SetTrackWidth(to_internal(width))
            netclass.SetViaDiameter(to_internal(via_diameter))
            netclass.SetViaDrill(to_internal(via_drill))
            if name == 'Usb':
                netclass.SetDiffPairWidth(to_internal(0.2))
                netclass.SetDiffPairGap(to_internal(0.18))
            net_settings.SetNetclass(name, netclass)
            for net in nets:
                net_settings.SetNetclassPatternAssignment(
                    self.full_net(net), name
                )

    def add_zone(self, net, layer, rect, priority, clearance=0.3):
        zone = pcbnew.ZONE(self.board)
        zone.SetLayer(layer)
        zone.SetNet(self.net_item(self.full_net(net)))
        zone.SetAssignedPriority(priority)
        zone.SetLocalClearance(to_internal(clearance))
        zone.SetMinThickness(to_internal(0.2))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.SetPadConnection(
            pcbnew.ZONE_CONNECTION_FULL
            if net in GROUND_NETS
            else pcbnew.ZONE_CONNECTION_THERMAL
        )
        zone.SetThermalReliefGap(to_internal(0.3))
        zone.SetThermalReliefSpokeWidth(to_internal(0.4))
        self.set_outline(zone, rect)
        self.board.Add(zone)
        return zone

    def set_outline(self, zone, rect):
        outline = zone.Outline()
        outline.NewOutline()
        for corner_x, corner_y in (
            (rect.min_x, rect.min_y),
            (rect.max_x, rect.min_y),
            (rect.max_x, rect.max_y),
            (rect.min_x, rect.max_y),
        ):
            outline.Append(to_internal(corner_x), to_internal(corner_y))

    def add_keepout(self, rect, footprints=False, points=None, name=None):
        """No-copper rule area on every layer; `footprints` also keeps parts
        out. A named area is referred to by the rules in cryocooler.kicad_dru.
        """
        zone = pcbnew.ZONE(self.board)
        zone.SetIsRuleArea(True)
        if name is not None:
            zone.SetZoneName(name)
        zone.SetDoNotAllowZoneFills(True)
        zone.SetDoNotAllowTracks(True)
        zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowFootprints(footprints)
        zone.SetDoNotAllowPads(footprints)
        zone.SetLayerSet(pcbnew.LSET.AllCuMask())
        if points is None:
            self.set_outline(zone, rect)
        else:
            outline = zone.Outline()
            outline.NewOutline()
            for point_x, point_y in points:
                outline.Append(to_internal(point_x), to_internal(point_y))
        self.board.Add(zone)

    def add_restricted_corners(self):
        """Housing restricted areas: no copper, no parts (rule area) and no
        solder mask (mask opening on both sides).
        """
        for hole_x, hole_y in HOLES:
            points = restricted_outline(hole_x, hole_y)
            # parts are kept out by a rule in cryocooler.kicad_dru that lets
            # the mounting hole itself stay
            self.add_keepout(None, points=points, name='housing_corner')
            for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
                polygon = pcbnew.SHAPE_POLY_SET()
                outline = polygon.NewOutline()
                for point_x, point_y in points:
                    polygon.Append(
                        pcbnew.VECTOR2I(to_internal(point_x), to_internal(point_y)),
                        outline,
                    )
                shape = pcbnew.PCB_SHAPE(self.board)
                shape.SetShape(pcbnew.SHAPE_T_POLY)
                shape.SetLayer(layer)
                shape.SetFilled(True)
                shape.SetWidth(0)
                shape.SetPolyShape(polygon)
                self.board.Add(shape)

    def add_planes(self):
        board_rect = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT)
        region = ISO_REGION
        # isolation bands on every side of the ISO island that is not a
        # board edge
        top = max(region.min_y - ISO_BAND, 0.0)
        bottom = min(region.max_y + ISO_BAND, BOARD_HEIGHT)
        if region.max_x < BOARD_WIDTH:
            self.add_keepout(
                Rect(region.max_x, top, region.max_x + ISO_BAND, bottom)
            )
        if region.min_y > 0:
            self.add_keepout(
                Rect(0.0, region.min_y - ISO_BAND, region.max_x, region.min_y)
            )
        if region.max_y < BOARD_HEIGHT:
            self.add_keepout(
                Rect(0.0, region.max_y, region.max_x, region.max_y + ISO_BAND)
            )
        # parts are kept out by a rule in cryocooler.kicad_dru that lets the
        # ESP32 (whose antenna courtyard reaches here) stay
        for keepout in ANTENNA_KEEPOUTS:
            self.add_keepout(keepout, name='antenna_keepout')
        self.add_restricted_corners()
        self.add_zone('GND', pcbnew.In1_Cu, board_rect, 1)
        self.add_zone('ISO_GND', pcbnew.In1_Cu, region, 2)

    def add_outer_pours(self):
        """GND / ISO_GND pours on the outer layers, added after routing."""
        board_rect = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT)
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            self.add_zone('GND', layer, board_rect, 1)
            self.add_zone('ISO_GND', layer, ISO_REGION, 2)

    def add_inner_power_planes(self):
        """In2 pours go on after routing so the router can use In2 as a signal
        layer.
        """
        board_rect = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT)
        self.add_zone('+3V3', pcbnew.In2_Cu, board_rect, 1)
        self.add_zone('ISO_GND', pcbnew.In2_Cu, ISO_REGION, 2)

    def add_mounting_holes(self):
        for index, (hole_x, hole_y) in enumerate(HOLES, start=1):
            footprint = pcbnew.FootprintLoad(
                str(STOCK_FOOTPRINTS / 'MountingHole.pretty'),
                'MountingHole_3.2mm_M3',
            )
            # board-only: the holes have no schematic symbol
            footprint.SetReference(f'H{index}')
            footprint.SetBoardOnly(True)
            footprint.Reference().SetVisible(False)
            footprint.Value().SetVisible(False)
            footprint.SetPosition(
                pcbnew.VECTOR2I(to_internal(hole_x), to_internal(hole_y))
            )
            self.board.Add(footprint)

    def fill_zones(self):
        filler = pcbnew.ZONE_FILLER(self.board)
        filler.Fill(self.board.Zones())

    def stitch_ground(self, pitch=4.0, clearance=0.55):
        """Adds GND / ISO_GND stitching vias on a grid wherever the spot is
        clear of other copper.
        """
        self.fill_zones()
        obstacles = []
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                box = pad.GetBoundingBox()
                obstacles.append(
                    (
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                        None,
                    )
                )
        for track in self.board.GetTracks():
            half = track.GetWidth() / 2e6
            if track.Type() == pcbnew.PCB_VIA_T:
                position = track.GetPosition()
                obstacles.append(
                    (
                        position.x / 1e6 - half,
                        position.y / 1e6 - half,
                        position.x / 1e6 + half,
                        position.y / 1e6 + half,
                        None,
                    )
                )
            else:
                start, end = track.GetStart(), track.GetEnd()
                obstacles.append(
                    (
                        min(start.x, end.x) / 1e6 - half,
                        min(start.y, end.y) / 1e6 - half,
                        max(start.x, end.x) / 1e6 + half,
                        max(start.y, end.y) / 1e6 + half,
                        (
                            start.x / 1e6,
                            start.y / 1e6,
                            end.x / 1e6,
                            end.y / 1e6,
                            half,
                        ),
                    )
                )
        zones = {}
        for zone in self.board.Zones():
            if not zone.GetIsRuleArea() and zone.GetNetname() in GROUND_NETS:
                zones[(zone.GetNetname(), zone.GetLayer())] = zone
        via_radius = 0.3
        added = 0
        grid_y = pitch
        while grid_y < BOARD_HEIGHT - 2:
            grid_x = pitch
            while grid_x < BOARD_WIDTH - 2:
                grid_x += pitch
                inside_iso = (
                    ISO_REGION.min_x <= grid_x <= ISO_REGION.max_x
                    and ISO_REGION.min_y <= grid_y <= ISO_REGION.max_y
                )
                net = 'ISO_GND' if inside_iso else 'GND'
                point = pcbnew.VECTOR2I(
                    to_internal(grid_x), to_internal(grid_y)
                )
                needed = (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu)
                if not all(
                    zones.get((net, layer)) is not None
                    and zones[(net, layer)].HitTestFilledArea(layer, point)
                    for layer in needed
                ):
                    continue
                if any(
                    self.point_blocked(
                        grid_x, grid_y, via_radius + clearance, obstacle
                    )
                    for obstacle in obstacles
                ):
                    continue
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(point)
                via.SetWidth(to_internal(0.6))
                via.SetDrill(to_internal(0.3))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(self.full_net(net)))
                self.board.Add(via)
                obstacles.append(
                    (
                        grid_x - via_radius,
                        grid_y - via_radius,
                        grid_x + via_radius,
                        grid_y + via_radius,
                        None,
                    )
                )
                added += 1
            grid_y += pitch
        return added

    def obstacle_list(self):
        obstacles = []
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                box = pad.GetBoundingBox()
                obstacles.append(
                    (
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                        None,
                    )
                )
        for track in self.board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                position = track.GetPosition()
                obstacles.append(
                    (
                        position.x / 1e6 - 0.3,
                        position.y / 1e6 - 0.3,
                        position.x / 1e6 + 0.3,
                        position.y / 1e6 + 0.3,
                        None,
                    )
                )
                continue
            half = track.GetWidth() / 2e6
            start, end = track.GetStart(), track.GetEnd()
            obstacles.append(
                (
                    min(start.x, end.x) / 1e6 - half,
                    min(start.y, end.y) / 1e6 - half,
                    max(start.x, end.x) / 1e6 + half,
                    max(start.y, end.y) / 1e6 + half,
                    (
                        start.x / 1e6,
                        start.y / 1e6,
                        end.x / 1e6,
                        end.y / 1e6,
                        half,
                    ),
                )
            )
        return obstacles

    def connect_pour_islands(self, clearance=0.4, via_diameter=0.6):
        """Adds a via to every outer-layer GND/ISO_GND pour fragment that has
        none.
        """
        self.fill_zones()
        added = 0
        for zone in list(self.board.Zones()):
            if zone.GetIsRuleArea() or zone.GetNetname() not in GROUND_NETS:
                continue
            layer = zone.GetLayer()
            if layer not in (pcbnew.F_Cu, pcbnew.B_Cu):
                continue
            filled = zone.GetFilledPolysList(layer)
            vias = [
                t
                for t in self.board.GetTracks()
                if t.Type() == pcbnew.PCB_VIA_T
                and t.GetNetname() == zone.GetNetname()
            ]
            for index in range(filled.OutlineCount()):
                if any(
                    filled.Contains(via.GetPosition(), index) for via in vias
                ):
                    continue
                box = filled.Outline(index).BBox()
                obstacles = self.obstacle_list()
                placed = False
                step = 0.25
                position_y = box.GetTop() / 1e6
                while position_y < box.GetBottom() / 1e6 and not placed:
                    position_x = box.GetLeft() / 1e6
                    while position_x < box.GetRight() / 1e6 and not placed:
                        point = pcbnew.VECTOR2I(
                            to_internal(position_x), to_internal(position_y)
                        )
                        if filled.Contains(point, index) and not any(
                            self.point_blocked(
                                position_x,
                                position_y,
                                via_diameter / 2 + clearance,
                                obstacle,
                            )
                            for obstacle in obstacles
                        ):
                            via = pcbnew.PCB_VIA(self.board)
                            via.SetPosition(point)
                            via.SetWidth(to_internal(via_diameter))
                            via.SetDrill(to_internal(0.3))
                            via.SetViaType(pcbnew.VIATYPE_THROUGH)
                            via.SetNet(self.net_item(zone.GetNetname()))
                            self.board.Add(via)
                            added += 1
                            placed = True
                        position_x += step
                    position_y += step
        return added

    def escape_ground_pads(self, via_diameter=0.5, clearance=0.2):
        """Gives each GND/ISO_GND SMD pad that sits in a via-less pour fragment
        its own via + stub.
        """
        self.fill_zones()
        added = 0
        vias = [
            item
            for item in self.board.GetTracks()
            if item.Type() == pcbnew.PCB_VIA_T
            and item.GetNetname() in GROUND_NETS
        ]
        for zone in list(self.board.Zones()):
            if (
                zone.GetIsRuleArea()
                or zone.GetNetname() not in GROUND_NETS
                or zone.GetLayer() != pcbnew.F_Cu
            ):
                continue
            filled = zone.GetFilledPolysList(pcbnew.F_Cu)
            for index in range(filled.OutlineCount()):
                if any(
                    filled.Contains(via.GetPosition(), index) for via in vias
                ):
                    continue
                for footprint in self.board.GetFootprints():
                    for pad in footprint.Pads():
                        if (
                            pad.GetNetname() != zone.GetNetname()
                            or not filled.Contains(pad.GetPosition(), index)
                        ):
                            continue
                        if pad.HasHole():
                            continue
                        added += self.add_escape_via(
                            pad, zone.GetNetname(), via_diameter, clearance
                        )
        added += self.escape_uncovered_ground_pads(
            via_diameter, clearance
        )
        return added

    def escape_uncovered_ground_pads(self, via_diameter, clearance):
        """Escape via for GND/ISO_GND SMD pads that no pour fragment reaches
        (boxed in by tracks), which the fragment scan above never sees.
        """
        added = 0
        zones = {
            zone.GetNetname(): zone
            for zone in self.board.Zones()
            if not zone.GetIsRuleArea()
            and zone.GetNetname() in GROUND_NETS
            and zone.GetLayer() == pcbnew.F_Cu
        }
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                net = pad.GetNetname()
                zone = zones.get(net)
                if (
                    zone is None
                    or pad.HasHole()
                    or not pad.IsOnLayer(pcbnew.F_Cu)
                ):
                    continue
                filled = zone.GetFilledPolysList(pcbnew.F_Cu)
                if any(
                    filled.Contains(pad.GetPosition(), index)
                    for index in range(filled.OutlineCount())
                ):
                    continue
                if any(
                    via.GetNetname() == net
                    and via.GetPosition() == pad.GetPosition()
                    for via in self.board.GetTracks()
                    if via.Type() == pcbnew.PCB_VIA_T
                ):
                    continue
                added += self.add_escape_via(
                    pad, net, via_diameter, clearance
                )
        return added

    def add_escape_via(self, pad, net, via_diameter, clearance):
        center = pad.GetPosition()
        center_x, center_y = center.x / 1e6, center.y / 1e6
        # drop only the pad itself and tracks that touch it; a diagonal
        # track's bounding box can cover the pad without being connected
        obstacles = [
            o
            for o in self.obstacle_list()
            if not (
                o[0] <= center_x <= o[2]
                and o[1] <= center_y <= o[3]
                and (o[4] is None or self.point_blocked(center_x, center_y, 0.05, o))
            )
        ]
        for distance in (0.9, 1.1, 1.4, 1.8, 2.4, 3.0, 4.0):
            for direction_x, direction_y in (
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (0.7, 0.7),
                (-0.7, 0.7),
                (0.7, -0.7),
                (-0.7, -0.7),
                (0.92, 0.38),
                (0.38, 0.92),
                (-0.38, 0.92),
                (-0.92, 0.38),
                (0.92, -0.38),
                (0.38, -0.92),
                (-0.38, -0.92),
                (-0.92, -0.38),
            ):
                via_x, via_y = (
                    center_x + distance * direction_x,
                    center_y + distance * direction_y,
                )
                if any(
                    self.point_blocked(
                        via_x, via_y, via_diameter / 2 + clearance, o
                    )
                    for o in obstacles
                ):
                    continue
                # sample the whole stub every ~0.2 mm, starting just off the pad
                stub_length = distance
                count = max(3, int(stub_length / 0.2))
                samples = [
                    (
                        center_x + (via_x - center_x) * step / count,
                        center_y + (via_y - center_y) * step / count,
                    )
                    for step in range(1, count)
                ]
                if any(
                    self.point_blocked(sample_x, sample_y, 0.1 + clearance, o)
                    for sample_x, sample_y in samples
                    for o in obstacles
                ):
                    continue
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(
                    pcbnew.VECTOR2I(to_internal(via_x), to_internal(via_y))
                )
                via.SetWidth(to_internal(via_diameter))
                via.SetDrill(to_internal(0.3))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(net))
                self.board.Add(via)
                self.add_track(
                    net,
                    pcbnew.F_Cu,
                    [(center_x, center_y), (via_x, via_y)],
                    0.2,
                    locked=False,
                )
                return 1
        # no room for a stub: via-in-pad (order filled/capped vias for these,
        # see VIA_IN_PAD_REFS)
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(center)
        via.SetWidth(to_internal(VIA_IN_PAD_DIAMETER))
        via.SetDrill(to_internal(0.2))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetNet(self.net_item(net))
        self.board.Add(via)
        print(
            'via-in-pad:',
            pad.GetParentFootprint().GetReference(),
            pad.GetNumber(),
        )
        return 1

    @staticmethod
    def point_blocked(point_x, point_y, radius, obstacle):
        min_x, min_y, max_x, max_y, segment = obstacle
        if not (
            min_x - radius <= point_x <= max_x + radius
            and min_y - radius <= point_y <= max_y + radius
        ):
            return False
        if segment is None:
            return True
        start_x, start_y, end_x, end_y, half_width = segment
        delta_x, delta_y = end_x - start_x, end_y - start_y
        length_squared = delta_x * delta_x + delta_y * delta_y
        fraction = (
            0.0
            if length_squared == 0
            else max(
                0.0,
                min(
                    1.0,
                    (
                        (point_x - start_x) * delta_x
                        + (point_y - start_y) * delta_y
                    )
                    / length_squared,
                ),
            )
        )
        nearest_x, nearest_y = (
            start_x + fraction * delta_x,
            start_y + fraction * delta_y,
        )
        return (
            (point_x - nearest_x) ** 2 + (point_y - nearest_y) ** 2
        ) ** 0.5 <= radius + half_width

    def autoroute(self, work_dir, rounds=2):
        """Runs Freerouting; extra rounds re-route whatever the previous round
        left unconnected.
        """
        for round_index in range(rounds):
            dsn = work_dir / f'board{round_index}.dsn'
            ses = work_dir / f'board{round_index}.ses'
            if not pcbnew.ExportSpecctraDSN(self.board, str(dsn)):
                raise RuntimeError('DSN export failed')
            text = dsn.read_text()
            text = text.replace(
                '(layer In1.Cu\n      (type signal)',
                '(layer In1.Cu\n      (type power)',
            )
            dsn.write_text(text)
            subprocess.run(
                [
                    JAVA,
                    '-jar',
                    str(FREEROUTING_JAR),
                    '-de',
                    str(dsn),
                    '-do',
                    str(ses),
                    '-mp',
                    MAX_PASSES,
                    '-mt',
                    '1',
                ],
                check=False,
            )
            if not ses.exists() or ses.stat().st_size == 0:
                raise RuntimeError('Freerouting produced no session file')
            if not pcbnew.ImportSpecctraSES(self.board, str(ses)):
                raise RuntimeError('SES import failed')

    def pre_place_pad_bridges(self):
        """Locked 0.2 mm F.Cu stubs between same-net pads of PAD_BRIDGES, so
        the router sees one pad group per net instead of pads it cannot reach.
        """
        for ref, chains in PAD_BRIDGES.items():
            if ref not in self.footprints:
                continue
            for chain in chains:
                for first, second in zip(chain, chain[1:]):
                    net = self.pad_net[ref].get(first)
                    if net is None or net != self.pad_net[ref].get(second):
                        raise RuntimeError(
                            f'{ref} pads {first} and {second} are not on '
                            'one net'
                        )
                    start = self.pad_position(ref, first)
                    end = self.pad_position(ref, second)
                    # exposed pads are large: end the stub 0.5 mm inside them
                    if second in ('23', '24'):
                        end = (start[0] + (end[0] - start[0]) * 0.6, start[1])
                    track = pcbnew.PCB_TRACK(self.board)
                    track.SetStart(
                        pcbnew.VECTOR2I(
                            to_internal(start[0]), to_internal(start[1])
                        )
                    )
                    track.SetEnd(
                        pcbnew.VECTOR2I(
                            to_internal(end[0]), to_internal(end[1])
                        )
                    )
                    track.SetWidth(to_internal(BRIDGE_WIDTH))
                    track.SetLayer(
                        pcbnew.F_Cu if self.side_of.get(ref) == 'F' else pcbnew.B_Cu
                    )
                    track.SetNet(self.net_item(self.full_net(net)))
                    track.SetLocked(True)
                    self.board.Add(track)

    def widen_thin_tracks(self):
        """Freerouting squeezes a few stubs down to 0.125 mm; widen them to
        the board's minimum track width.
        """
        widened = 0
        for track in self.board.GetTracks():
            if (
                track.Type() == pcbnew.PCB_TRACE_T
                and track.GetWidth() < to_internal(MIN_TRACK_WIDTH)
            ):
                track.SetWidth(to_internal(MIN_TRACK_WIDTH))
                widened += 1
        return widened

    def pre_place_fine_pitch_ground_vias(self, table=None):
        """Locked 0.35 mm via-in-pad on the fine-pitch LGA/MSOP ground pads before
        autorouting. The LGA pads are 0.5 mm apart, so a router-placed via
        or an inner-layer track under them cannot be kept clear; 0.35 mm
        keeps 0.15 mm to the neighbouring pads (order filled/capped vias).
        """
        for ref, pads in (table or FINE_PITCH_GROUND_PADS).items():
            footprint = self.footprints.get(ref)
            if footprint is None:
                continue
            for pad in footprint.Pads():
                if pad.GetNumber() not in pads:
                    continue
                net = self.pad_net[ref].get(pad.GetNumber())
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(
                    pcbnew.VECTOR2I(
                        to_internal(
                            self.pad_position(ref, pad.GetNumber())[0]
                        ),
                        to_internal(
                            self.pad_position(ref, pad.GetNumber())[1]
                        ),
                    )
                )
                via.SetWidth(to_internal(VIA_IN_PAD_DIAMETER))
                via.SetDrill(to_internal(0.2))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(self.full_net(net)))
                via.SetLocked(True)
                self.board.Add(via)
                via_x, via_y = self.pad_position(ref, pad.GetNumber())
                # a part on the far side must not land on the via
                other = 'B' if self.side_of.get(ref) == 'F' else 'F'
                self.occ[other].add(
                    f'via_{ref}_{pad.GetNumber()}',
                    Rect(via_x - 0.45, via_y - 0.45, via_x + 0.45, via_y + 0.45),
                )


    def fanout_ground_pads(self, via_diameter=0.5, drill=0.3, width=0.3, clearance=0.2):
        """Before routing: a locked via beside every small SMD ground pad,
        joined by a short track, so the router always leaves each pad a way
        down to the ground plane (a pad it fences in with other nets' tracks
        would otherwise be left on a pour island). Returns the pads with no
        room for one.
        """
        radius = via_diameter / 2
        boxes = []
        holes = []
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                if not pad.GetNumber() and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    continue  # paste apertures (unnumbered non-plated holes stay)
                box = pad.GetBoundingBox()
                boxes.append((
                    Rect(box.GetLeft() / 1e6, box.GetTop() / 1e6,
                         box.GetRight() / 1e6, box.GetBottom() / 1e6),
                    pad.GetNetname(),
                    pad.IsOnLayer(pcbnew.F_Cu),
                    pad.IsOnLayer(pcbnew.B_Cu),
                ))
                if pad.GetDrillSize().x > 0:
                    # drilled pads (thermal vias too) count as holes
                    holes.append((
                        pad.GetPosition().x / 1e6,
                        pad.GetPosition().y / 1e6,
                        min(pad.GetDrillSize().x, pad.GetDrillSize().y) / 2e6,
                    ))
        vias = [
            (item.GetPosition().x / 1e6, item.GetPosition().y / 1e6, item.GetNetname())
            for item in self.board.GetTracks()
            if item.Type() == pcbnew.PCB_VIA_T
        ]
        board = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT).inflated(-(EDGE_MARGIN + radius))
        keepouts = self.occ['F'].keepouts + self.occ['B'].keepouts
        in_pad = {
            (ref, number)
            for table in (FINE_PITCH_GROUND_PADS, LATE_GROUND_PADS)
            for ref, numbers in table.items()
            for number in numbers
        }
        missing = []
        for ref, footprint in self.footprints.items():
            if ref not in self.centers:
                continue
            for pad in footprint.Pads():
                number = pad.GetNumber()
                net = self.pad_net[ref].get(number)
                if net not in GROUND_NETS or (ref, number) in in_pad:
                    continue
                if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                    continue  # through-hole pads reach the plane themselves
                size_x, size_y = pad.GetBoundingBox().GetWidth() / 1e6, pad.GetBoundingBox().GetHeight() / 1e6
                if size_x * size_y > 6.0:
                    continue  # big pads keep room for an escape via
                full = self.full_net(net)
                pad_x, pad_y = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
                if any(
                    other.GetDrillSize().x > 0 and pad.HitTest(other.GetPosition())
                    for other in footprint.Pads()
                ):
                    continue  # an exposed pad with its own thermal vias
                if any(math.dist((pad_x, pad_y), (vx, vy)) < 1.2 for vx, vy, vnet in vias if vnet == full):
                    continue
                front = pad.IsOnLayer(pcbnew.F_Cu)
                spot = None
                for reach in (0.35, 0.6, 0.9, 1.3):
                    for angle in range(0, 360, 45):
                        delta_x = math.cos(math.radians(angle))
                        delta_y = math.sin(math.radians(angle))
                        via_x = pad_x + delta_x * (size_x / 2 + radius + reach)
                        via_y = pad_y + delta_y * (size_y / 2 + radius + reach)
                        if self.ground_via_spot_ok(
                            via_x, via_y, pad_x, pad_y, full, front, radius, width,
                            clearance, boxes, vias, board, keepouts,
                        ) and all(
                            math.dist((via_x, via_y), (hole_x, hole_y))
                            - drill / 2 - hole_radius >= HOLE_TO_HOLE
                            for hole_x, hole_y, hole_radius in holes
                        ):
                            spot = (via_x, via_y)
                            break
                    if spot:
                        break
                if spot is None:
                    missing.append(f'{ref}.{number}')
                    continue
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(pcbnew.VECTOR2I(to_internal(spot[0]), to_internal(spot[1])))
                via.SetWidth(to_internal(via_diameter))
                via.SetDrill(to_internal(drill))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(full))
                via.SetLocked(True)
                self.board.Add(via)
                layer = pcbnew.F_Cu if front else pcbnew.B_Cu
                self.add_track(full, layer, [(pad_x, pad_y), spot], width)
                vias.append((spot[0], spot[1], full))
        return missing

    @staticmethod
    def ground_via_spot_ok(via_x, via_y, pad_x, pad_y, net, front, radius, width,
                           clearance, boxes, vias, board, keepouts):
        """True if a fan-out via fits at (via_x, via_y): on the board, out of
        the keep-outs and the isolation band, clear of other nets' pads (on
        both sides) and of other vias, with a clear track back to its pad.
        """
        if not (board.min_x <= via_x <= board.max_x and board.min_y <= via_y <= board.max_y):
            return False
        via_box = Rect(via_x - radius, via_y - radius, via_x + radius, via_y + radius)
        if any(via_box.overlaps(k) for k in keepouts):
            return False
        iso = net.endswith('ISO_GND')
        if iso != via_box.inside(ISO_REGION.inflated(-0.3)) or (
            not iso and via_box.inflated(ISO_BAND).overlaps(ISO_REGION)
        ):
            return False
        for vx, vy, _ in vias:
            if math.dist((via_x, via_y), (vx, vy)) < 2 * radius + clearance + 0.05:
                return False
        steps = 6
        track = [
            (pad_x + (via_x - pad_x) * k / steps, pad_y + (via_y - pad_y) * k / steps)
            for k in range(steps + 1)
        ]
        for rect, pad_net, on_front, on_back in boxes:
            if pad_net == net:
                continue
            if pcbfloorplan.rect_gap(via_box, rect) < clearance:
                return False
            if (on_front if front else on_back) and any(
                pcbfloorplan.rect_gap(
                    Rect(x - width / 2, y - width / 2, x + width / 2, y + width / 2), rect
                ) < clearance
                for x, y in track
            ):
                return False
        return True

    # ─── silkscreen ───

    def silk_free(self, rect):
        """True if a text box fits inside the board, clear of every placed
        footprint, hole and keep-out.
        """
        if not rect.inside(self.occupancy.board_rect):
            return False
        if any(rect.overlaps(keepout) for keepout in self.occupancy.keepouts):
            return False
        if any(
            rect.overlaps(text.inflated(0.1)) for text in self.footprint_texts()
        ):
            return False
        return not any(
            rect.overlaps(other.inflated(0.15))
            for other in self.occupancy.rects.values()
        )

    def footprint_texts(self):
        """Boxes of the visible reference / value texts, so labels keep clear
        of them (cached after the first call).
        """
        cache = self.__dict__.setdefault('_text_boxes', {})
        if self.side not in cache:
            boxes = []
            for footprint in self.board.GetFootprints():
                for item in (footprint.Reference(), footprint.Value()):
                    if not item.IsVisible() or item.GetLayer() != self.silk_layer:
                        continue
                    box = item.GetBoundingBox()
                    boxes.append(
                        Rect(
                            box.GetLeft() / 1e6,
                            box.GetTop() / 1e6,
                            box.GetRight() / 1e6,
                            box.GetBottom() / 1e6,
                        )
                    )
            cache[self.side] = boxes
        return cache[self.side]

    def add_text(
        self,
        text,
        x,
        y,
        size,
        layer=None,
        mirrored=False,
        thickness=None,
        justify='center',
    ):
        item = pcbnew.PCB_TEXT(self.board)
        item.SetText(text)
        if layer is None:
            layer = self.silk_layer
            mirrored = mirrored or self.side == 'B'
        item.SetLayer(layer)
        item.SetPosition(pcbnew.VECTOR2I(to_internal(x), to_internal(y)))
        item.SetTextSize(pcbnew.VECTOR2I(to_internal(size), to_internal(size)))
        item.SetTextThickness(
            to_internal(thickness if thickness else max(0.12, size * 0.15))
        )
        item.SetHorizJustify(
            {
                'center': pcbnew.GR_TEXT_H_ALIGN_CENTER,
                'left': pcbnew.GR_TEXT_H_ALIGN_LEFT,
            }[justify]
        )
        item.SetMirrored(mirrored)
        self.board.Add(item)
        return item

    def text_rect(self, text, center_x, center_y, size):
        """Box of an upright text centred on a point, as pcbnew draws it."""
        width, height = measure_text(text, size)
        half_width = width / 2 + 0.1
        half_height = height / 2 + 0.05
        return Rect(
            center_x - half_width,
            center_y - half_height,
            center_x + half_width,
            center_y + half_height,
        )

    def add_part_labels(self):
        """Little labels next to the buttons and LEDs: the best free spot
        within 3.5 mm of the part, preferring one inside its module box and
        close to the part.
        """
        obstacles = self.silk_obstacles() + [
            rect
            for name, rect in self.occupancy.rects.items()
            if name.startswith('txt_label_')
        ]
        courtyards = self.keep_out_courtyards()
        inner = self.occupancy.board_rect.inflated(EDGE_MARGIN - 0.45)
        texts = [
            self.text_box(footprint.Reference())
            for footprint in self.footprints.values()
            if footprint.Reference().IsVisible()
            and footprint.Reference().GetLayer() == self.silk_layer
        ]
        deferred = self.__dict__.setdefault('deferred_labels', {})
        other = 'B' if self.side == 'F' else 'F'
        # labels reserved early, possibly on the other side of their part
        for ref, (spot_x, spot_y, turned, *where) in self.label_pockets.items():
            side, text = where if where else (self.side_of.get(ref), SILK_LABELS[ref])
            if side != self.side or ref not in self.centers:
                continue
            item = self.add_text(
                text, spot_x, spot_y, SILK_TEXT_SIZE, thickness=SILK_TEXT_THICKNESS
            )
            if turned:
                item.SetTextAngleDegrees(90)
        jobs = [
            (ref, text, True)
            for ref, text in SILK_LABELS.items()
            if ref in self.centers
            and self.side_of.get(ref) == self.side
            and ref not in self.label_pockets
        ] + [(ref, SILK_LABELS[ref], False) for ref in deferred.pop(self.side, [])]
        for ref, text, own in jobs:
            # on the other side the label sits beside the pins, in any box
            part = self.body_rect(ref) if own else self.other_side_part(ref)
            center_x = (part.min_x + part.max_x) / 2
            center_y = (part.min_y + part.max_y) / 2
            module = self.module_of_ref(ref) if own else None
            best = None
            # the full label first, then its short form; a connector with no
            # room for both its reference and its label prints them together
            forms = [(form, False) for form in (text, *SILK_LABEL_SHORT.get(ref, ()))]
            reference = self.footprints[ref].Reference()
            own_box = None
            if self.is_connector(ref) and own and reference.IsVisible():
                own_box = self.text_box(reference)
                forms += [(f'{ref} {form}', True) for form, _ in list(forms)]
            for text, combined in forms:
                blocking = (
                    [t for t in texts if t != own_box] if combined else texts
                )
                base = self.text_rect(text, 0, 0, SILK_TEXT_SIZE)
                for gap in (0.3, 0.7, 1.2, 1.8, 2.5, 3.5, 5.0):
                    for turned in (False, True):
                        half_w, half_h = (
                            (base.max_y, base.max_x)
                            if turned
                            else (base.max_x, base.max_y)
                        )
                        for center in (
                            (part.max_x + gap + half_w, center_y),
                            (part.min_x - gap - half_w, center_y),
                            (center_x, part.min_y - gap - half_h),
                            (center_x, part.max_y + gap + half_h),
                            (part.max_x + gap + half_w, part.min_y - gap - half_h),
                            (part.min_x - gap - half_w, part.min_y - gap - half_h),
                            (part.max_x + gap + half_w, part.max_y + gap + half_h),
                            (part.min_x - gap - half_w, part.max_y + gap + half_h),
                        ):
                            rect = Rect(
                                center[0] - half_w,
                                center[1] - half_h,
                                center[0] + half_w,
                                center[1] + half_h,
                            )
                            if (
                                not rect.inside(inner)
                                or any(rect.overlaps(t) for t in blocking)
                                or any(
                                    rect.overlaps(c)
                                    for owner, c in courtyards.items()
                                    if owner != ref
                                )
                                or any(rect.overlaps(o) for o in obstacles)
                                or any(
                                    rect.overlaps(k)
                                    for k in self.occupancy.keepouts
                                )
                            ):
                                continue
                            level = (
                                pcbfloorplan.text_level(module, rect, self.side)
                                if module is not None
                                else 0
                            )
                            score = (
                                2 if level == 2 else 0,
                                level,
                                pcbfloorplan.rect_gap(rect, part),
                            )
                            if best is None or score < best[0]:
                                best = (score, center, rect, turned, text, combined)
                    if best is not None and best[0][0] == 0:
                        break
                if best is not None:
                    break
            if best is None:
                if own and ref.startswith('J'):
                    deferred.setdefault(other, []).append(ref)
                else:
                    print('silk label not placed:', ref, text)
                continue
            if best[0][0] > 0:
                print('silk label sits outside its box:', ref, text)
            _, center, rect, turned, text, combined = best
            if combined:
                reference.SetVisible(False)
            if best[0][1] == 1:
                self.bumps.setdefault((module, self.side), []).append(rect)
            item = self.add_text(
                text, *center, SILK_TEXT_SIZE, thickness=SILK_TEXT_THICKNESS
            )
            if turned:
                item.SetTextAngleDegrees(90)
            self.occupancy.add(f'silk_{ref}', rect)
            obstacles.append(rect)

    def check_floorplan(self):
        """Returns messages for parts outside their module's box and for
        boxes closer together than the minimum gap.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        problems = pcbfloorplan.check_regions(board_rect, 'F')
        problems += pcbfloorplan.check_regions(board_rect, 'B')
        for ref, module in self.module.items():
            if module is None:
                continue
            side = self.side_of[ref]
            center_x, center_y, angle = self.centers[ref]
            rect = placed_rect(self.local_rect(ref, side), center_x, center_y, angle)
            if not pcbfloorplan.region_contains(module, rect, side):
                problems.append(f'{ref} ({side}) is outside the {module} box')
        return problems

    @staticmethod
    def title_box(spot):
        """Box a section title takes: (text, left_x, line_y) on a horizontal
        border, (text, line_x, top_y, 'v') running up a vertical one.
        """
        text, start_x, start_y, *vertical = spot
        width = pcbfloorplan.label_width(text)
        if vertical:
            return Rect(start_x - 0.9, start_y, start_x + 0.9, start_y + width)
        return Rect(start_x, start_y - 0.9, start_x + width, start_y + 0.9)

    def module_label_spot(self, module, board_rect, holes, inside=True):
        """First (text, left_x, line_y) on a drawn border that clears every
        part, hole and earlier label, or None.
        """
        plain = pcbfloorplan.outline_segments(
            module, board_rect, holes, side=self.side, keepouts=self.silk_keepouts()
        )
        gap = pcbfloorplan.LABEL_GAP
        for text in pcbfloorplan.label_texts(module):
            width = pcbfloorplan.label_width(text)
            for left_x, line_y in pcbfloorplan.label_candidates(
                module, text, board_rect, self.side
            ):
                if not pcbfloorplan.covered(
                    plain, line_y, left_x - gap, left_x + width + gap
                ):
                    continue
                if pcbfloorplan.text_hits_hole(left_x, line_y, width, holes):
                    continue
                box = Rect(left_x, line_y - 0.9, left_x + width, line_y + 0.9)
                if any(
                    box.overlaps(other)
                    for name, other in self.occupancy.rects.items()
                    if not name.startswith('silk_box')
                ):
                    continue
                # two titles in a row would read as one
                if any(
                    box.inflated(TITLE_SPACING).overlaps(other)
                    for name, other in self.occupancy.rects.items()
                    if name.startswith('silk_label_')
                ):
                    continue
                if any(box.overlaps(k) for k in self.occupancy.keepouts):
                    continue
                return text, left_x, line_y
        # then running up a vertical border
        drawable = board_rect.inflated(-0.4)
        for text in pcbfloorplan.label_texts(module):
            width = pcbfloorplan.label_width(text)
            for rect in pcbfloorplan.regions(module, self.side):
                for line_x in (rect.min_x, rect.max_x):
                    if not drawable.min_x <= line_x <= drawable.max_x:
                        continue
                    top_y = max(rect.min_y + 0.6, 1.5)
                    while top_y + width <= min(rect.max_y - 0.6, drawable.max_y):
                        spot = (text, line_x, top_y, 'v')
                        box = self.title_box(spot)
                        top_y += 0.25
                        if not pcbfloorplan.covered_vertical(
                            plain, line_x, box.min_y - 0.3, box.max_y + 0.3
                        ):
                            continue
                        if any(
                            (hole_x - min(max(hole_x, box.min_x), box.max_x)) ** 2
                            + (hole_y - min(max(hole_y, box.min_y), box.max_y)) ** 2
                            < (radius + pcbfloorplan.HOLE_CLEARANCE) ** 2
                            for hole_x, hole_y, radius in holes
                        ):
                            continue
                        if any(box.overlaps(k) for k in self.occupancy.keepouts):
                            continue
                        if any(
                            box.overlaps(other)
                            for name, other in self.occupancy.rects.items()
                            if not name.startswith('silk_box')
                        ):
                            continue
                        return spot
        if not inside:
            return None
        # no free border: inside the box, as high as there is room
        for text in pcbfloorplan.label_texts(module):
            width = pcbfloorplan.label_width(text)
            for rect in pcbfloorplan.regions(module, self.side):
                inner = rect.inflated(-0.3)
                rows = int((inner.max_y - inner.min_y - 2.0) / 0.5) + 1
                for line_y in (inner.min_y + 1.0 + 0.5 * row for row in range(rows)):
                    left_x = max(inner.min_x, EDGE_MARGIN + 0.2)
                    while left_x + width <= min(inner.max_x, BOARD_WIDTH - EDGE_MARGIN - 0.2):
                        box = Rect(left_x, line_y - 0.9, left_x + width, line_y + 0.9)
                        left_x += 0.5
                        if not box.inside(board_rect.inflated(-EDGE_MARGIN)):
                            continue
                        if pcbfloorplan.text_hits_hole(box.min_x, line_y, width, holes):
                            continue
                        if any(box.overlaps(k) for k in self.occupancy.keepouts):
                            continue
                        # a passive's reserved reference spot may give way
                        # (that reference moves or is hidden later)
                        evict = self.evictable(box, True)
                        kept = {
                            name: self.occupancy.rects.pop(name) for name in evict
                        }
                        # like a reference text: clear of pads, bodies and
                        # other text, courtyard margins are fine
                        blocked = any(
                            box.overlaps(other)
                            for other in self.pocket_obstacles(box.inflated(1.0))
                        ) or any(
                            box.overlaps(body)
                            for body in self.keep_out_courtyards().values()
                        )
                        for name, rect in kept.items():
                            self.occupancy.rects[name] = rect
                        if blocked:
                            continue
                        for name in evict:
                            if box.overlaps(self.occupancy.rects[name]):
                                del self.occupancy.rects[name]
                                self.pockets.pop(name.removeprefix('txt_ref_'), None)
                        return text, box.min_x, line_y
        return None

    def draw_module_lines(self, module, spot, board_rect, holes):
        """Draws the silk outline of one module (replacing any earlier one)
        and reserves the line areas.
        """
        for shape in self.box_lines.pop((module, self.side), []):
            self.board.Remove(shape)
            self._removed_shapes.append(shape)
        for name in [
            n for n in self.occupancy.rects if n.startswith(f'silk_box_{module}_')
        ]:
            del self.occupancy.rects[name]
        shapes = []
        # a border shared with a neighbour carries its label too
        labels = [
            label
            for (name, side), label in self.box_labels.items()
            if side == self.side and label is not None
        ]
        for index, (start, end) in enumerate(
            pcbfloorplan.outline_segments(
                module, board_rect, holes, labels, self.side, self.silk_keepouts()
            )
        ):
            line = pcbnew.PCB_SHAPE(self.board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(self.silk_layer)
            line.SetWidth(to_internal(pcbfloorplan.LINE_WIDTH))
            line.SetStart(
                pcbnew.VECTOR2I(to_internal(start[0]), to_internal(start[1]))
            )
            line.SetEnd(
                pcbnew.VECTOR2I(to_internal(end[0]), to_internal(end[1]))
            )
            self.board.Add(line)
            shapes.append(line)
            self.occupancy.add(
                f'silk_box_{module}_{index}',
                Rect(
                    min(start[0], end[0]) - 0.1,
                    min(start[1], end[1]) - 0.1,
                    max(start[0], end[0]) + 0.1,
                    max(start[1], end[1]) + 0.1,
                ),
            )
        self.box_lines[(module, self.side)] = shapes

    def add_module_boxes(self):
        """Draws each module's outline and label on the front silkscreen and
        reserves the line and label areas so other silk keeps clear.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 3.4) for hole_x, hole_y in HOLES]
        self._removed_shapes = getattr(self, '_removed_shapes', [])
        self.box_labels = getattr(self, 'box_labels', {})
        names = pcbfloorplan.modules(self.side)
        for module in names:
            spot = self.early_labels.get((module, self.side))
            if spot is None:
                spot = self.module_label_spot(module, board_rect, holes)
            if spot is None:
                print('no free border for the label of', module, self.side)
            self.box_labels[(module, self.side)] = spot
        for module in names:
            spot = self.box_labels[(module, self.side)]
            self.draw_module_lines(module, spot, board_rect, holes)
            if spot is None:
                continue
            text = spot[0]
            slot = self.title_box(spot)
            # centred: a left-justified text grows the other way when mirrored
            item = self.add_text(
                text,
                (slot.min_x + slot.max_x) / 2,
                (slot.min_y + slot.max_y) / 2,
                pcbfloorplan.LABEL_SIZE,
                thickness=SILK_TEXT_THICKNESS + 0.03,
            )
            if len(spot) > 3:
                item.SetTextAngleDegrees(90)
            if not self.text_box(item).inside(slot.inflated(0.05)):
                print('module label wider than its slot:', text, self.side)
            self.occupancy.add(f'silk_label_{module}', slot)

    def bulge_module_boxes(self):
        """Redraws the outline of every module whose labels did not fit
        inside it so the line goes around them.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 3.4) for hole_x, hole_y in HOLES]
        for (module, side), rects in self.bumps.items():
            if side != self.side:
                continue
            pcbfloorplan.EXTRA_REGIONS[(module, side)] = [
                pcbfloorplan.bump_rect(rect) for rect in rects
            ]
            self.draw_module_lines(
                module, self.box_labels.get((module, side)), board_rect, holes
            )
        print(
            'module outlines bulged around labels:',
            {m: len(r) for m, r in self.bumps.items()},
        )

    def text_box(self, item):
        """Box around the ink of a text (what prints; the text's own
        bounding box adds line spacing above and below).
        """
        polygon = pcbnew.SHAPE_POLY_SET()
        item.TransformTextToPolySet(polygon, 0, to_internal(0.005), pcbnew.ERROR_INSIDE)
        box = polygon.BBox() if polygon.OutlineCount() else item.GetBoundingBox()
        return Rect(
            box.GetLeft() / 1e6,
            box.GetTop() / 1e6,
            box.GetRight() / 1e6,
            box.GetBottom() / 1e6,
        )

    def silk_obstacles(self):
        """Boxes that reference text must not cover: every pad, every
        footprint silk graphic, the module box lines and labels, and the
        mounting holes (as squares).
        """
        boxes = []
        copper = pcbnew.F_Cu if self.side == 'F' else pcbnew.B_Cu
        for footprint in self.footprints.values():
            for pad in footprint.Pads():
                if not pad.IsOnLayer(copper):
                    continue
                box = pad.GetBoundingBox()
                boxes.append(
                    Rect(
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                    ).inflated(0.05)
                )
            for graphic in footprint.GraphicalItems():
                if graphic.GetLayer() != self.silk_layer:
                    continue
                box = graphic.GetBoundingBox()
                boxes.append(
                    Rect(
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                    ).inflated(0.05)
                )
        for name, rect in self.occupancy.rects.items():
            if name.startswith('silk_pin'):
                # keep other labels (and the connector's own reference) off
                # the pin label strip
                boxes.append(rect.inflated(0.25))
            elif name.startswith('silk_'):
                boxes.append(rect)
        for hole_x, hole_y in HOLES:
            boxes.append(
                Rect(hole_x - 3.2, hole_y - 3.2, hole_x + 3.2, hole_y + 3.2)
            )
        boxes += self.silk_keepouts()
        return boxes

    def silk_keepouts(self):
        """Areas silkscreen stays out of: the antenna notch and its strip, and
        the housing's restricted corners (no mask there to print on).
        """
        return [ANTENNA_NOTCH, *ANTENNA_KEEPOUTS, *corner_keepouts()]

    def other_side_part(self, ref):
        """What shows of a part on the side it is not mounted on: its
        through-hole pins, else its pad area (labels go beside it).
        """
        pins = self.occupancy.rects.get(f'{ref}~tht')
        return pins if pins is not None else self.body_rect(ref)

    def keep_out_courtyards(self):
        """Courtyards of the big placed parts, by owner: another part's label
        inside one reads as that part's label. The ESP32 counts by its pads
        (its pin names fill the body; the antenna area is exempt).
        """
        boxes = {
            ref: rect
            for ref, rect in self.occupancy.rects.items()
            if ref in PLACEMENT and ref != 'U1' and self.side_of.get(ref) == self.side
        }
        if self.side_of.get('U1') == self.side:
            boxes['U1'] = self.body_rect('U1')
        return boxes

    def module_of_ref(self, ref):
        """Module box a part belongs to (debug parts: the box they sit in)."""
        module = self.module.get(ref)
        if module is not None:
            return module
        center_x, center_y, _ = self.centers[ref]
        side = self.side_of.get(ref, 'F')
        for name in pcbfloorplan.modules(side):
            if any(
                r.min_x <= center_x <= r.max_x and r.min_y <= center_y <= r.max_y
                for r in pcbfloorplan.regions(name, side)
            ):
                self.module[ref] = name
                return name
        return None

    def body_rect(self, ref):
        """Box around a part's pads: what a reader sees as "the part" (the
        courtyard is bigger and overlaps neighbours).
        """
        cache = self.__dict__.setdefault('_body_rects', {})
        if ref not in cache:
            boxes = [pad.GetBoundingBox() for pad in self.footprints[ref].Pads()]
            if not boxes:
                cache[ref] = self.occupancy.rects[ref]
            else:
                cache[ref] = Rect(
                    min(b.GetLeft() for b in boxes) / 1e6,
                    min(b.GetTop() for b in boxes) / 1e6,
                    max(b.GetRight() for b in boxes) / 1e6,
                    max(b.GetBottom() for b in boxes) / 1e6,
                )
        return cache[ref]

    def label_score(self, ref, rect, neighbours, module):
        """Ranks a label box for `ref` (lower is better): ambiguous (another
        part's pads as close or closer) or out of reach of its module box
        first, then needing an outline bulge, then distance to the part.
        """
        level = (
            pcbfloorplan.text_level(module, rect, self.side)
            if module is not None
            else 0
        )
        own = pcbfloorplan.rect_gap(rect, self.body_rect(ref))
        ambiguous = int(
            any(
                pcbfloorplan.rect_gap(rect, other) <= own
                for other in neighbours
            )
        )
        return (ambiguous + (2 if level == 2 else 0), level, own)

    def neighbour_rects(self, ref, reach=6.0):
        """Bodies of the parts near ref that its reference could be taken
        for. "TP.." can only be read as a test point, so a test point's
        reference only has to be nearer to it than to other test points.
        """
        part = self.body_rect(ref).inflated(reach)
        return [
            self.body_rect(name)
            for name in self.footprints
            if name != ref
            and self.side_of.get(name) == self.side
            and (not ref.startswith('TP') or name.startswith('TP'))
            and self.body_rect(name).overlaps(part)
        ]

    def place_reference_texts(self):
        """Keeps every reference designator beside its own part: inside the
        part's module box, nearer to that part than to any other, and off
        pads, other silk, the box lines and the board edge. Texts that fail
        move to the nearest spot that qualifies (rotating 90 degrees if that
        helps).
        """
        obstacles = self.silk_obstacles()
        courtyards = self.keep_out_courtyards()
        inner = self.occupancy.board_rect.inflated(EDGE_MARGIN - 0.45)
        finished = {}
        moved = 0
        stuck = []
        weak = []
        # spots reserved for texts not printed yet (references, part labels)
        reserved = [
            (name, rect)
            for name, rect in self.occupancy.rects.items()
            if name.startswith(('txt_ref_', 'txt_label_'))
        ]
        order = sorted(
            self.footprints,
            key=lambda r: (
                not self.is_passive(r),
                int(r.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ') or 0),
            ),
        )

        def clear(rect, near, own):
            if not rect.inside(inner):
                return False
            if any(rect.overlaps(other) for other in finished.values()):
                return False
            if any(
                rect.overlaps(spot)
                for name, spot in reserved
                if name != f'txt_ref_{own}'
                and name.removeprefix('txt_ref_') not in finished
            ):
                return False
            if any(
                rect.overlaps(courtyard)
                for owner, courtyard in courtyards.items()
                if owner != own
            ):
                return False
            return not any(
                rect.overlaps(obstacle)
                for obstacle in near
                if obstacle.min_x < rect.max_x + 0.1
                and obstacle.max_x > rect.min_x - 0.1
            )

        deferred = self.__dict__.setdefault('deferred_refs', {})
        other = 'B' if self.side == 'F' else 'F'
        moved_over = deferred.pop(self.side, [])
        for ref in moved_over:
            # a connector reference with no room on its own side goes beside
            # its pins on this one
            item = self.footprints[ref].Reference()
            item.SetLayer(self.silk_layer)
            item.SetMirrored(self.side == 'B')
            item.SetVisible(True)
            part = self.other_side_part(ref)
            item.SetPosition(
                pcbnew.VECTOR2I(
                    to_internal((part.min_x + part.max_x) / 2),
                    to_internal(part.min_y - 1.0),
                )
            )
        for ref in order:
            footprint = self.footprints[ref]
            item = footprint.Reference()
            own_side = self.side_of.get(ref) == self.side
            if not item.IsVisible() or not (own_side or ref in moved_over):
                continue
            module = self.module_of_ref(ref) if own_side else None
            if own_side and ref in self.pockets:
                spot_x, spot_y, turned = self.pockets[ref]
                item.SetTextAngleDegrees(90 if turned else 0)
                item.SetPosition(
                    pcbnew.VECTOR2I(to_internal(spot_x), to_internal(spot_y))
                )
                finished[ref] = self.text_box(item)
                moved += 1
                continue
            neighbours = self.neighbour_rects(ref)
            box = self.text_box(item)
            part = self.occupancy.rects[ref] if own_side else self.other_side_part(ref)
            # every spot tried lies within 8 mm of the part or its text
            window = Rect(
                min(box.min_x, part.min_x) - 8.0,
                min(box.min_y, part.min_y) - 8.0,
                max(box.max_x, part.max_x) + 8.0,
                max(box.max_y, part.max_y) + 8.0,
            )
            near = [obstacle for obstacle in obstacles if obstacle.overlaps(window)]
            width = box.max_x - box.min_x
            height = box.max_y - box.min_y
            center_x = (part.min_x + part.max_x) / 2
            center_y = (part.min_y + part.max_y) / 2
            angle = item.GetTextAngleDegrees()
            best = None
            if clear(box, near, ref):
                best = (
                    self.label_score(ref, box, neighbours, module),
                    box.min_x + width / 2,
                    box.min_y + height / 2,
                    box,
                    False,
                )
            if best is None or best[0][0] > 0:
                # a test point's reference may sit a little further out
                gaps = (0.0, 0.2, 0.4, 0.7, 1.0, 1.4, 2.0, 2.8)
                if ref.startswith('TP'):
                    gaps += (3.6, 4.5)
                for gap in gaps:
                    for turned in (False, True):
                        text_w, text_h = (
                            (height, width) if turned else (width, height)
                        )
                        spots = []
                        for shift in (0.0, 0.6, -0.6, 1.2, -1.2, 1.8, -1.8, 2.6, -2.6):
                            spots.append(
                                (center_x + shift, part.min_y - gap - text_h / 2)
                            )
                            spots.append(
                                (center_x + shift, part.max_y + gap + text_h / 2)
                            )
                            spots.append(
                                (part.min_x - gap - text_w / 2, center_y + shift)
                            )
                            spots.append(
                                (part.max_x + gap + text_w / 2, center_y + shift)
                            )
                        for spot_x, spot_y in spots:
                            rect = Rect(
                                spot_x - text_w / 2,
                                spot_y - text_h / 2,
                                spot_x + text_w / 2,
                                spot_y + text_h / 2,
                            )
                            if not clear(rect, near, ref):
                                continue
                            score = self.label_score(
                                ref, rect, neighbours, module
                            )
                            if best is None or score < best[0]:
                                best = (score, spot_x, spot_y, rect, turned)
                    if best is not None and best[0][0] == 0:
                        break
            if best is None or (best[0][0] > 0 and self.is_passive(ref)):
                # no readable spot of its own: off the silkscreen (the Fab
                # layer still carries it); a connector tries the other side
                item.SetVisible(False)
                if own_side and self.is_connector(ref):
                    deferred.setdefault(other, []).append(ref)
                else:
                    stuck.append(ref)
                continue
            if best[0][0] > 0:
                weak.append(ref)
            if best[0][1] == 1 and module is not None:
                self.bumps.setdefault((module, self.side), []).append(best[3])
            _, spot_x, spot_y, rect, turned = best
            if rect is box and not turned:
                finished[ref] = box
                continue
            if turned:
                item.SetTextAngleDegrees((angle + 90) % 180)
            item.SetPosition(
                pcbnew.VECTOR2I(to_internal(spot_x), to_internal(spot_y))
            )
            finished[ref] = rect
            moved += 1
        print('reference texts moved:', moved, f'hidden ({len(stuck)}):', stuck)
        print('reference texts still ambiguous or outside their box:', weak)

    def adopt_board(self):
        """Takes footprints, courtyards and silk graphics from an already
        built (possibly routed) board so the silkscreen steps can run on it
        without placing or routing again.
        """
        self.footprints = {
            fp.GetReference(): fp
            for fp in self.board.GetFootprints()
            if fp.GetReference() and not fp.IsBoardOnly()  # not the holes
        }
        for ref, footprint in self.footprints.items():
            position = footprint.GetPosition()
            self.centers[ref] = (
                position.x / 1e6,
                position.y / 1e6,
                footprint.GetOrientationDegrees(),
            )
            self.side = 'B' if footprint.IsFlipped() else 'F'
            self.side_of[ref] = self.side
            override = LOCAL_RECT_OVERRIDES.get(
                self.parts.get(ref, {}).get('footprint')
            )
            if override is not None:
                x_pos, y_pos, angle = self.centers[ref]
                self.occupancy.add(
                    ref, placed_rect(override, x_pos, y_pos, angle)
                )
                continue
            box = footprint.GetCourtyard(
                pcbnew.B_CrtYd if self.side == 'B' else pcbnew.F_CrtYd
            ).BBox()
            if box.GetWidth() == 0:
                box = footprint.GetBoundingBox(False, False)
            self.occupancy.add(
                ref,
                Rect(
                    box.GetLeft() / 1e6,
                    box.GetTop() / 1e6,
                    box.GetRight() / 1e6,
                    box.GetBottom() / 1e6,
                ),
            )
        self.side = 'F'
        for index, (hole_x, hole_y) in enumerate(HOLES):
            for occupancy in self.occ.values():
                occupancy.add(
                    f'hole{index}',
                    Rect(hole_x - 3.4, hole_y - 3.4, hole_x + 3.4, hole_y + 3.4),
                )

    @staticmethod
    def ic_label_variants(text):
        """The part number as one line, and as two lines split at the hyphen
        (or letter/digit boundary) nearest the middle."""
        variants = [text]
        cuts = [
            index
            for index in range(2, len(text) - 1)
            if text[index - 1] == '-'
            or text[index].isdigit() != text[index - 1].isdigit()
        ]
        if cuts:
            cut = min(cuts, key=lambda index: abs(index - len(text) / 2))
            variants.append(text[:cut] + '\n' + text[cut:])
        return variants

    @staticmethod
    def ic_label_text(footprint):
        """Text printed for an IC: its value, or the shorter override."""
        return IC_LABEL_TEXT.get(footprint.GetReference(), footprint.GetValue())

    def ic_label_obstacles(self, footprint):
        """Boxes an IC part number must stay off: the part's pads and silk
        graphics, plus every visible reference / value text on the board.
        """
        boxes = []
        for pad in footprint.Pads():
            box = pad.GetBoundingBox()
            boxes.append(
                Rect(
                    box.GetLeft() / 1e6 - 0.2,
                    box.GetTop() / 1e6 - 0.2,
                    box.GetRight() / 1e6 + 0.2,
                    box.GetBottom() / 1e6 + 0.2,
                )
            )
        for item in footprint.GraphicalItems():
            if item.GetLayer() != self.silk_layer:
                continue
            box = item.GetBoundingBox()
            boxes.append(
                Rect(
                    box.GetLeft() / 1e6 - 0.15,
                    box.GetTop() / 1e6 - 0.15,
                    box.GetRight() / 1e6 + 0.15,
                    box.GetBottom() / 1e6 + 0.15,
                )
            )
        boxes.extend(self.footprint_texts())
        return boxes

    def ic_body_rect(self, footprint):
        """Package body from the footprint's fab outline (falls back to the
        pad box)."""
        boxes = [
            item.GetBoundingBox()
            for item in footprint.GraphicalItems()
            if item.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab)
            and not isinstance(item, pcbnew.PCB_TEXT)
        ]
        if not boxes:
            boxes = [pad.GetBoundingBox() for pad in footprint.Pads()]
        return Rect(
            min(box.GetLeft() for box in boxes) / 1e6,
            min(box.GetTop() for box in boxes) / 1e6,
            max(box.GetRight() for box in boxes) / 1e6,
            max(box.GetBottom() for box in boxes) / 1e6,
        )

    def fit_ic_label(self, footprint):
        """Finds the largest part-number text that fits between the part's
        pads inside its body, nearest the body centre. Returns
        (text, size, angle, x, y) or None.
        """
        body = self.ic_body_rect(footprint)
        obstacles = self.ic_label_obstacles(footprint)
        center_x = (body.min_x + body.max_x) / 2
        center_y = (body.min_y + body.max_y) / 2
        for size in IC_LABEL_SIZES:
            for variant in self.ic_label_variants(
                IC_LABEL_TEXT.get(footprint.GetReference(), footprint.GetValue())
            ):
                for angle in (0, 90):
                    # measured on a text that is never added to the board
                    probe = pcbnew.PCB_TEXT(self.board)
                    probe.SetText(variant)
                    probe.SetLayer(self.silk_layer)
                    probe.SetTextSize(
                        pcbnew.VECTOR2I(to_internal(size), to_internal(size))
                    )
                    probe.SetTextThickness(to_internal(SILK_TEXT_THICKNESS))
                    probe.SetTextAngleDegrees(angle)
                    extent = self.text_box(probe)
                    half_width = (extent.max_x - extent.min_x) / 2
                    half_height = (extent.max_y - extent.min_y) / 2
                    reach_x = (body.max_x - body.min_x) / 2 - half_width - 0.1
                    reach_y = (body.max_y - body.min_y) / 2 - half_height - 0.1
                    if reach_x < 0 or reach_y < 0:
                        continue
                    steps_x = int(reach_x / IC_LABEL_STEP)
                    steps_y = int(reach_y / IC_LABEL_STEP)
                    spots = sorted(
                        (
                            (step_x * IC_LABEL_STEP) ** 2
                            + (step_y * IC_LABEL_STEP) ** 2,
                            center_x + step_x * IC_LABEL_STEP,
                            center_y + step_y * IC_LABEL_STEP,
                        )
                        for step_x in range(-steps_x, steps_x + 1)
                        for step_y in range(-steps_y, steps_y + 1)
                    )
                    for _, spot_x, spot_y in spots:
                        rect = Rect(
                            spot_x - half_width,
                            spot_y - half_height,
                            spot_x + half_width,
                            spot_y + half_height,
                        )
                        if not any(rect.overlaps(other) for other in obstacles):
                            return variant, size, angle, spot_x, spot_y
        return None

    def add_ic_labels(self):
        """Prints each IC's part number on the silkscreen inside its body,
        between the pads, so the soldered part covers it. Returns
        (placed refs, skipped refs).
        """
        placed = []
        skipped = []
        for ref, footprint in sorted(self.footprints.items()):
            if not ref.startswith(('U', 'PS')) or ref in IC_LABEL_SKIP:
                continue
            if self.side_of.get(ref) != self.side:
                continue
            fit = None
            if self.side_of.get(ref) == self.side:
                fit = self.fit_ic_label(footprint)
            if fit is None:
                skipped.append(ref)
                continue
            variant, size, angle, spot_x, spot_y = fit
            item = self.add_text(
                variant, spot_x, spot_y, size, thickness=SILK_TEXT_THICKNESS
            )
            item.SetTextAngleDegrees(angle)
            placed.append(ref)
        return placed, skipped

    def remove_ic_labels(self):
        """Removes earlier IC part-number texts (silk text equal to a part's
        value, centred inside its body) so add_ic_labels can run again."""
        removed = 0
        for item in list(self.board.GetDrawings()):
            if (
                not isinstance(item, pcbnew.PCB_TEXT)
                or item.GetLayer() != pcbnew.F_SilkS
            ):
                continue
            position = item.GetPosition()
            for ref, footprint in self.footprints.items():
                if not ref.startswith(('U', 'PS')):
                    continue
                body = self.ic_body_rect(footprint)
                if (
                    item.GetText().replace('\n', '').replace('-', '')
                    == self.ic_label_text(footprint).replace('-', '')
                    and body.min_x <= position.x / 1e6 <= body.max_x
                    and body.min_y <= position.y / 1e6 <= body.max_y
                ):
                    self.board.Remove(item)
                    self._removed_ic_labels = getattr(
                        self, '_removed_ic_labels', []
                    ) + [item]
                    removed += 1
                    break
        return removed

    def add_silkscreen(self):
        for side in 'FB':
            self.side = side
            self.add_module_boxes()
            if side == 'F' and not self.pin_pockets:
                # silk-only runs on an existing board: find the spots now
                for ref in PIN_LABELS:
                    self.side = self.side_of[ref]
                    self.reserve_pin_labels(ref)
                self.side = side
            self.add_pin_labels()
            if side == 'F':
                self.add_esp32_pin_names()
            if side == BOARD_ID_SIDE:
                self.add_board_id()
            self.place_reference_texts()
            self.add_part_labels()
            placed, skipped = self.add_ic_labels()
            print(side, 'IC part numbers placed:', placed, 'skipped:', skipped)
            print(side, 'pin 1 marks missing:', self.add_pin1_marks())
            self.bulge_module_boxes()
        self.side = 'F'
        for side, refs in getattr(self, 'deferred_labels', {}).items():
            print('silk labels not placed (other side full):', refs)
        print('references hidden by the overlap pass:', self.hide_overlapping_references())

    def test_point_problems(self, reach=8.0):
        """Test points on the other side from the nearest part on their net,
        or more than `reach` mm from it (AGENTS.md: same side, close by).
        """
        problems = []
        for ref in self.parts:
            if not ref.startswith('TP') or ref not in self.centers:
                continue
            net = self.pad_net[ref].get('1')
            if net in GROUND_NETS:
                # ground loops go through the board: reachable from both sides
                continue
            here = self.occ[self.side_of[ref]].rects[ref]
            on_net = [
                other
                for other, _ in self.net_pads[net]
                if other in self.centers and not other.startswith('TP')
            ]
            if not on_net:
                continue
            gaps = {
                other: pcbfloorplan.rect_gap(here, self.occ[self.side_of[other]].rects[other])
                for other in on_net
            }
            nearest = min(gaps, key=gaps.get)
            tested = self.tested_part(ref, nearest)
            if self.side_of[tested] != self.side_of[ref]:
                problems.append(f'{ref} is on the other side from {tested}')
            elif gaps[nearest] > reach:
                problems.append(f'{ref} is {gaps[nearest]:.1f} mm from {nearest}')
        return problems

    def silk_lines(self, layer):
        """Line work printed on a silkscreen layer: footprint outlines and
        the section box lines, as [(start, end, half width)] for segments
        and [(Rect, 0)] boxes for the other shapes.
        """
        items = [
            item
            for footprint in self.footprints.values()
            for item in footprint.GraphicalItems()
        ] + list(self.board.GetDrawings())
        lines = []
        for item in items:
            if item.Type() != pcbnew.PCB_SHAPE_T or item.GetLayer() != layer:
                continue
            if item.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                start, end = item.GetStart(), item.GetEnd()
                lines.append((
                    (start.x / 1e6, start.y / 1e6),
                    (end.x / 1e6, end.y / 1e6),
                    item.GetWidth() / 2e6,
                ))
            else:
                box = item.GetBoundingBox()
                lines.append((
                    Rect(box.GetLeft() / 1e6, box.GetTop() / 1e6,
                         box.GetRight() / 1e6, box.GetBottom() / 1e6),
                    None,
                    0.0,
                ))
        return lines

    @staticmethod
    def rect_hits_line(rect, line):
        """True if a box touches one silk line from silk_lines()."""
        start, end, half = line
        if end is None:
            return rect.overlaps(start)
        grown = rect.inflated(half)
        # clip the segment to the box (Liang-Barsky)
        delta_x, delta_y = end[0] - start[0], end[1] - start[1]
        low, high = 0.0, 1.0
        for step, distance in (
            (-delta_x, start[0] - grown.min_x),
            (delta_x, grown.max_x - start[0]),
            (-delta_y, start[1] - grown.min_y),
            (delta_y, grown.max_y - start[1]),
        ):
            if step == 0:
                if distance < 0:
                    return False
                continue
            ratio = distance / step
            if step < 0:
                low = max(low, ratio)
            else:
                high = min(high, ratio)
            if low > high:
                return False
        return True

    def silk_texts(self):
        """[(name, item, owner)] of every printed silkscreen text; owner is
        the ref for a reference designator, else None.
        """
        texts = []
        for drawing in self.board.GetDrawings():
            if isinstance(drawing, pcbnew.PCB_TEXT) and drawing.GetLayer() in (
                pcbnew.F_SilkS, pcbnew.B_SilkS
            ):
                texts.append((drawing.GetText(), drawing, None))
        for ref, footprint in self.footprints.items():
            if ref in self.centers and footprint.Reference().IsVisible():
                texts.append((ref, footprint.Reference(), ref))
        return texts

    def hide_overlapping_references(self):
        """Last pass: a part reference that still overlaps another text is
        taken off the silkscreen (connector references stay and are
        reported by the check). Returns the hidden refs.
        """
        hidden = []
        changed = True
        while changed:
            changed = False
            texts = self.silk_texts()
            boxes = [
                (owner, item.GetLayer(), self.text_box(item).inflated(-0.05))
                for _, item, owner in texts
            ]
            for index, (owner, layer, box) in enumerate(boxes):
                for other, other_layer, other_box in boxes[index + 1 :]:
                    if layer != other_layer or not box.overlaps(other_box):
                        continue
                    victim = next(
                        (
                            ref
                            for ref in (other, owner)
                            if ref is not None and not self.is_connector(ref)
                        ),
                        None,
                    )
                    if victim is None:
                        continue
                    self.footprints[victim].Reference().SetVisible(False)
                    hidden.append(victim)
                    changed = True
                    break
                if changed:
                    break
        return hidden

    def silk_problems(self):
        """Silkscreen texts that overlap another text, a pad, a part outline,
        a section line or a pin-1 dot on the same side, or that leave the
        board (edge, antenna notch, restricted corners).
        """
        texts = [(name, item) for name, item, _ in self.silk_texts()]
        board = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT).inflated(-0.2)
        off_board = [ANTENNA_NOTCH, *corner_keepouts()]
        boxes = [
            (name.replace('\n', ' '), item.GetLayer(), self.text_box(item).inflated(-0.05))
            for name, item in texts
        ]
        pads = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
        for footprint in self.footprints.values():
            for pad in footprint.Pads():
                box = pad.GetBoundingBox()
                rect = Rect(
                    box.GetLeft() / 1e6, box.GetTop() / 1e6,
                    box.GetRight() / 1e6, box.GetBottom() / 1e6,
                )
                if pad.IsOnLayer(pcbnew.F_Cu):
                    pads[pcbnew.F_SilkS].append((footprint.GetReference(), rect))
                if pad.IsOnLayer(pcbnew.B_Cu):
                    pads[pcbnew.B_SilkS].append((footprint.GetReference(), rect))
        lines = {
            pcbnew.F_SilkS: self.silk_lines(pcbnew.F_SilkS),
            pcbnew.B_SilkS: self.silk_lines(pcbnew.B_SilkS),
        }
        problems = []
        for index, (name, layer, box) in enumerate(boxes):
            if not box.inside(board) or any(box.overlaps(k) for k in off_board):
                problems.append(f'{name} leaves the board')
            if any(self.rect_hits_line(box, line) for line in lines[layer]):
                problems.append(f'{name} touches a silk line')
            hit = next((ref for ref, pad in pads[layer] if box.overlaps(pad)), None)
            if hit is not None:
                problems.append(f'{name} covers a pad of {hit}')
            for other, other_layer, other_box in boxes[index + 1 :]:
                if layer == other_layer and box.overlaps(other_box):
                    problems.append(f'{name} overlaps {other}')
        return problems

    def board_id_lines(self):
        """[(text, x, y)] of the board ID block: board name, then the short
        git revision the fab files come from.
        """
        try:
            revision = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=KICAD_DIR, capture_output=True, text=True, check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            revision = 'unknown'
        spot_x, spot_y = BOARD_ID_SPOT
        texts = (BOARD_NAME, f'UCS 145-125  rev {revision}')
        return [
            (text, spot_x, spot_y + index * BOARD_ID_SIZE * 1.6)
            for index, text in enumerate(texts)
        ]

    def reserve_board_id(self):
        """Holds the board ID area free before any part or label is placed."""
        for index, (text, spot_x, spot_y) in enumerate(self.board_id_lines()):
            self.occ[BOARD_ID_SIDE].add(
                f'silk_id_{index}',
                self.text_rect(text, spot_x, spot_y, BOARD_ID_SIZE).inflated(0.3),
            )

    def add_board_id(self):
        """Prints the board ID block in its reserved spot, the same on every
        revision.
        """
        for text, spot_x, spot_y in self.board_id_lines():
            self.add_text(text, spot_x, spot_y, BOARD_ID_SIZE, thickness=0.15)

    def add_esp32_pin_names(self):
        """Prints the ESP32 pin names at the spots reserved for them."""
        if getattr(self, 'esp32_names', None) is None:
            self.reserve_esp32_pin_names()  # silk-only run on a placed board
        for name, spot_x, spot_y, justify, angle in self.esp32_names:
            self.board.Add(self.esp32_name_item(name, spot_x, spot_y, justify, angle))

    def esp32_name_item(self, name, spot_x, spot_y, justify, angle):
        item = pcbnew.PCB_TEXT(self.board)
        item.SetText(name)
        item.SetLayer(pcbnew.F_SilkS)
        size = to_internal(ESP32_PIN_TEXT_SIZE)
        item.SetTextSize(pcbnew.VECTOR2I(size, size))
        item.SetTextThickness(to_internal(0.1))
        item.SetHorizJustify(justify)
        item.SetTextAngleDegrees(angle)
        item.SetPosition(pcbnew.VECTOR2I(to_internal(spot_x), to_internal(spot_y)))
        return item

    def reserve_esp32_pin_names(self):
        """Picks a spot for each ESP32 pin's name beside its pad, before the
        passives are placed: inside the module outline (side columns read
        across, bottom row turned), else just outside it past the pad. A
        name with room in neither spot is left out and reported.
        """
        self.esp32_names = []
        footprint = self.footprints.get('U1')
        if footprint is None:
            return
        home = self.side
        self.side = 'F'
        names = self.parts['U1'].get('pins', {})
        center_x, _, _ = self.centers['U1']
        lines = self.silk_lines(pcbnew.F_SilkS)
        pads = [
            Rect(b.GetLeft() / 1e6, b.GetTop() / 1e6, b.GetRight() / 1e6, b.GetBottom() / 1e6)
            for other in self.footprints.values()
            for pad in other.Pads()
            if pad.IsOnLayer(pcbnew.F_Cu)
            for b in [pad.GetBoundingBox()]
        ]
        taken = []
        skipped = []
        for pad in sorted(footprint.Pads(), key=lambda p: int(p.GetNumber())):
            number = pad.GetNumber()
            # the netlist suffixes repeated pin names with the pin number
            name = names.get(number, '').removesuffix(f'_{number}')
            if not name or number == '41':  # centre ground pad
                continue
            pad_x = pad.GetPosition().x / 1e6
            pad_y = pad.GetPosition().y / 1e6
            box = pad.GetBoundingBox()
            width = (box.GetRight() - box.GetLeft()) / 1e6
            height = (box.GetBottom() - box.GetTop()) / 1e6
            left = pcbnew.GR_TEXT_H_ALIGN_LEFT
            right = pcbnew.GR_TEXT_H_ALIGN_RIGHT
            if width >= height:  # side column
                inward = 1 if pad_x < center_x else -1
                reach = width / 2 + 0.25
                spots = [  # (x, y, justify, angle, outside)
                    (pad_x + inward * reach, pad_y, left if inward > 0 else right, 0, False),
                    (pad_x - inward * reach, pad_y, right if inward > 0 else left, 0, True),
                ]
            else:  # bottom row, turned
                reach = height / 2 + 0.25
                spots = [
                    (pad_x, pad_y - reach, left, 90, False),
                    (pad_x, pad_y + reach, right, 90, True),
                ]
            for spot_x, spot_y, justify, angle, outside in spots:
                item = self.esp32_name_item(name, spot_x, spot_y, justify, angle)
                rect = self.text_box(item).inflated(0.05)
                if any(rect.overlaps(other) for other in taken):
                    continue
                if outside and (
                    not rect.inside(self.occupancy.board_rect)
                    or any(rect.overlaps(other) for other in pads)
                    or any(rect.overlaps(other) for other in self.pocket_obstacles(rect))
                    or any(self.rect_hits_line(rect, line) for line in lines)
                    or any(rect.overlaps(k) for k in self.silk_keepouts())
                ):
                    continue
                taken.append(rect)
                # parts, labels and references placed later keep clear
                self.occ['F'].add(f'silk_esp32_{number}', rect)
                self.esp32_names.append((name, spot_x, spot_y, justify, angle))
                break
            else:
                skipped.append(name)
        self.side = home
        print('ESP32 pin names left out (no room):', skipped)

    def has_own_pin1_mark(self, footprint, pad_x, pad_y, reach=3.0):
        """True if the footprint's own silkscreen already marks pin 1 near
        the pin: a small filled shape (the stock triangle or dot) or a small
        closed outline of short lines (the connectors' drawn triangle).
        """
        segments = []
        for item in footprint.GraphicalItems():
            if item.Type() != pcbnew.PCB_SHAPE_T:
                continue
            if item.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                continue
            box = item.GetBoundingBox()
            centre = box.GetCenter()
            if math.dist((centre.x / 1e6, centre.y / 1e6), (pad_x, pad_y)) > reach:
                continue
            if max(box.GetWidth(), box.GetHeight()) / 1e6 > 1.5:
                continue
            if item.GetShape() in (pcbnew.SHAPE_T_POLY, pcbnew.SHAPE_T_CIRCLE):
                return True
            if item.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                segments.append(tuple(
                    (round(end.x / 1e4), round(end.y / 1e4))
                    for end in (item.GetStart(), item.GetEnd())
                ))
        # a closed loop of three or more short lines among them
        while segments:
            loop = [segments.pop()]
            grown = True
            while grown:
                grown = False
                corners = {end for segment in loop for end in segment}
                for segment in list(segments):
                    if segment[0] in corners or segment[1] in corners:
                        loop.append(segment)
                        segments.remove(segment)
                        grown = True
            ends = collections.Counter(end for segment in loop for end in segment)
            if len(loop) >= 3 and all(count == 2 for count in ends.values()):
                return True
        return False

    def add_pin1_marks(self):
        """A small dot beside pin 1 of every IC, oscillator and connector on
        the active side, in the first spot clear of copper; returns the parts
        that had no room.
        """
        copper = pcbnew.F_Cu if self.side == 'F' else pcbnew.B_Cu
        pads = []
        for footprint in self.footprints.values():
            for pad in footprint.Pads():
                if pad.IsOnLayer(copper):
                    box = pad.GetBoundingBox()
                    pads.append(Rect(
                        box.GetLeft() / 1e6, box.GetTop() / 1e6,
                        box.GetRight() / 1e6, box.GetBottom() / 1e6,
                    ).inflated(0.2))
        missing = []
        radius = 0.3
        lines = self.silk_lines(self.silk_layer)
        texts = [
            self.text_box(item)
            for _, item, _ in self.silk_texts()
            if item.GetLayer() == self.silk_layer
        ]
        for ref, footprint in sorted(self.footprints.items()):
            if self.side_of.get(ref) != self.side or not ref.startswith(
                ('U', 'J', 'PS')
            ):
                continue
            first = [pad for pad in footprint.Pads() if pad.GetNumber() in ('1', 'A1')]
            if not first:
                continue
            pad = first[0]
            box = pad.GetBoundingBox()
            pad_x, pad_y = pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6
            if self.has_own_pin1_mark(footprint, pad_x, pad_y):
                continue
            half_w = (box.GetRight() - box.GetLeft()) / 2e6
            half_h = (box.GetBottom() - box.GetTop()) / 2e6
            center_x, center_y, _ = self.centers[ref]
            placed = False
            reach_x = half_w + radius + 0.35
            reach_y = half_h + radius + 0.35
            away_x = 1 if pad_x >= center_x else -1
            away_y = 1 if pad_y >= center_y else -1
            for dot_x, dot_y in (
                (pad_x + away_x * reach_x, pad_y),
                (pad_x, pad_y + away_y * reach_y),
                (pad_x + away_x * reach_x, pad_y + away_y * reach_y),
                (pad_x - away_x * reach_x, pad_y),
                (pad_x, pad_y - away_y * reach_y),
            ):
                dot = Rect(dot_x - radius, dot_y - radius, dot_x + radius, dot_y + radius)
                if not dot.inside(self.occupancy.board_rect) or any(
                    dot.overlaps(other) for other in pads
                ):
                    continue
                if any(dot.overlaps(k) for k in self.silk_keepouts()):
                    continue
                if any(self.rect_hits_line(dot.inflated(0.1), line) for line in lines):
                    continue
                if any(dot.overlaps(text) for text in texts):
                    continue
                shape = pcbnew.PCB_SHAPE(self.board)
                shape.SetShape(pcbnew.SHAPE_T_CIRCLE)
                shape.SetLayer(self.silk_layer)
                shape.SetFilled(True)
                shape.SetWidth(to_internal(0.1))
                shape.SetCenter(pcbnew.VECTOR2I(to_internal(dot_x), to_internal(dot_y)))
                shape.SetEnd(
                    pcbnew.VECTOR2I(to_internal(dot_x + radius - 0.05), to_internal(dot_y))
                )
                self.board.Add(shape)
                lines.append((dot, None, 0.0))
                placed = True
                break
            if not placed:
                missing.append(ref)
        return missing

    def build(self):
        self.load_footprints()
        self.place_anchors()
        self.reserve_board_id()
        self.reserve_connector_pin_labels()
        self.reserve_esp32_pin_names()
        self.reserve_connector_labels()
        self.reserve_module_labels()
        self.reserve_anchor_pockets()
        self.pre_route_current_path()
        self.pre_place_fine_pitch_ground_vias()
        self.pre_place_pad_bridges()
        unplaced = self.place_passives()
        self.pre_place_fine_pitch_ground_vias(LATE_GROUND_PADS)
        print('ground pads with no fan-out via:', self.fanout_ground_pads())
        self.add_outline_and_keepouts()
        self.add_net_classes()
        self.add_mounting_holes()
        self.add_planes()
        self.add_silkscreen()
        return unplaced


def write_stackup(path):
    """Writes the 4-layer stackup with the solder mask colour into the board
    file (pcbnew leaves the stackup out of a generated board).
    """
    text = path.read_text()
    if '(stackup' in text:
        return
    mask = f'(color "{MASK_COLOUR}")\n\t\t\t\t(thickness 0.01)'
    dielectric = (
        '(thickness 0.48)\n\t\t\t\t(material "FR4")\n\t\t\t\t(epsilon_r 4.5)'
        '\n\t\t\t\t(loss_tangent 0.02)'
    )
    layers = [
        ('F.SilkS', '(type "Top Silk Screen")'),
        ('F.Paste', '(type "Top Solder Paste")'),
        ('F.Mask', '(type "Top Solder Mask")\n\t\t\t\t' + mask),
        ('F.Cu', '(type "copper")\n\t\t\t\t(thickness 0.035)'),
        ('dielectric 1', '(type "core")\n\t\t\t\t' + dielectric),
        ('In1.Cu', '(type "copper")\n\t\t\t\t(thickness 0.035)'),
        ('dielectric 2', '(type "prepreg")\n\t\t\t\t' + dielectric),
        ('In2.Cu', '(type "copper")\n\t\t\t\t(thickness 0.035)'),
        ('dielectric 3', '(type "core")\n\t\t\t\t' + dielectric),
        ('B.Cu', '(type "copper")\n\t\t\t\t(thickness 0.035)'),
        ('B.Mask', '(type "Bottom Solder Mask")\n\t\t\t\t' + mask),
        ('B.Paste', '(type "Bottom Solder Paste")'),
        ('B.SilkS', '(type "Bottom Silk Screen")'),
    ]
    block = '\t\t(stackup\n' + ''.join(
        f'\t\t\t(layer "{name}"\n\t\t\t\t{body}\n\t\t\t)\n'
        for name, body in layers
    ) + '\t\t\t(copper_finish "None")\n\t\t\t(dielectric_constraints no)\n\t\t)\n'
    text = text.replace('\t(setup\n', '\t(setup\n' + block, 1)
    path.write_text(text)


def patch_project_rules():
    """Writes the fine-pitch via limits into cryocooler.kicad_pro (pcbnew does
    not persist the annular-width minimum): 0.45 mm vias, 0.2 mm drills and a
    0.075 mm ring for the 0.5 mm pitch LGA/MSOP ground pads, and the
    0.15 mm minimum track width the net classes route with.
    """
    path = KICAD_DIR / 'cryocooler.kicad_pro'
    project = json.loads(path.read_text())
    rules = project['board']['design_settings']['rules']
    rules['min_via_annular_width'] = 0.075
    rules['min_via_diameter'] = VIA_IN_PAD_DIAMETER
    rules['min_through_hole_diameter'] = 0.2
    rules['min_track_width'] = MIN_TRACK_WIDTH
    path.write_text(json.dumps(project, indent=2) + '\n')


def main():
    """Usage: gen_pcb.py [place|route|finish|texts|iclabels] [freerouting.jar] —
    `route` also autoroutes and fills zones; `texts` redoes all silkscreen
    and adds 3D envelope models on the existing board; `iclabels` only adds
    the IC part numbers under the IC bodies.
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else 'place'
    builder = PcbBuilder()
    if mode == 'finish':
        # re-open the routed board, tidy zones, add stitching vias
        builder.board = pcbnew.LoadBoard(
            str(KICAD_DIR / 'cryocooler.kicad_pcb')
        )
        builder.board.GetDesignSettings().m_ViasMinSize = to_internal(
            VIA_IN_PAD_DIAMETER
        )
        for zone in builder.board.Zones():
            if not zone.GetIsRuleArea() and zone.GetNetname() in GROUND_NETS:
                zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        print('stitching vias:', builder.stitch_ground())
        print(
            'island vias:',
            builder.connect_pour_islands(),
            builder.connect_pour_islands(0.2, 0.5),
        )
        print('escape vias:', builder.escape_ground_pads())
        builder.fill_zones()
        pcbnew.SaveBoard(
            str(KICAD_DIR / 'cryocooler.kicad_pcb'), builder.board
        )
        write_stackup(KICAD_DIR / 'cryocooler.kicad_pcb')
        patch_project_rules()
        return 0
    if mode == 'iclabels':
        # add only the IC part numbers on the existing board
        builder.board = pcbnew.LoadBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'))
        builder.adopt_board()
        print('old IC labels removed:', builder.remove_ic_labels())
        placed, skipped = builder.add_ic_labels()
        print('IC part numbers placed:', placed, 'skipped:', skipped)
        pcbnew.SaveBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'), builder.board)
        write_stackup(KICAD_DIR / 'cryocooler.kicad_pcb')
        return 0
    if mode == 'texts':
        # redo all silkscreen (module boxes, reference texts, part labels,
        # ALPHA, back logo) and the 3D envelope models on the routed board
        # without touching placement or tracks
        builder.board = pcbnew.LoadBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'))
        builder.adopt_board()
        # keep the removed items referenced: freeing them while the board is
        # still in use corrupts the footprint objects
        removed = []
        for drawing in list(builder.board.GetDrawings()):
            if drawing.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                builder.board.Remove(drawing)
                removed.append(drawing)
        added = [
            ref
            for ref, footprint in builder.footprints.items()
            if pcbmodels.attach_missing_models(footprint)
        ]
        print('3D envelope models added to:', added)
        coloured = [
            ref
            for ref, footprint in builder.footprints.items()
            if pcbmodels.apply_connector_colour(footprint)
        ]
        print('connector colours applied to:', coloured)
        builder.add_silkscreen()
        pcbnew.SaveBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'), builder.board)
        write_stackup(KICAD_DIR / 'cryocooler.kicad_pcb')
        return 0
    unplaced = builder.build()
    overlaps = [
        pair
        for pair in builder.occupancy.overlaps_report()
        if not any('_current_' in name for name in pair)
        and not any(name.startswith(('silk_box', 'silk_esp32')) for name in pair)
        # a part's own label may sit in its courtyard margin (the silkscreen
        # check keeps it off the pads and outline)
        and f'silk_{pair[0]}' != pair[1]
        and f'silk_{pair[1]}' != pair[0]
        and not (
            any(name.startswith('txt_') for name in pair)
            and not all(name.startswith('txt_') for name in pair)
        )
    ]
    floorplan_problems = builder.check_floorplan()
    silk_problems = builder.silk_problems()
    test_point_problems = builder.test_point_problems()
    out_path = KICAD_DIR / 'cryocooler.kicad_pcb'
    print('unplaced:', unplaced)
    print('overlapping pairs:', overlaps)
    print('floorplan problems:', floorplan_problems)
    print(f'silkscreen problems ({len(silk_problems)}):', silk_problems[:40])
    print(f'test point problems ({len(test_point_problems)}):', test_point_problems)
    if mode == 'route':
        work_dir = Path(tempfile.mkdtemp(prefix='cryo_route_'))
        builder.autoroute(work_dir)
        print('routing files in', work_dir)
        print('thin tracks widened:', builder.widen_thin_tracks())
        builder.add_inner_power_planes()
        builder.add_outer_pours()
    else:
        builder.add_inner_power_planes()
        builder.add_outer_pours()
    print('stitching vias:', builder.stitch_ground())
    print(
        'island vias:',
        builder.connect_pour_islands(),
        builder.connect_pour_islands(0.2, 0.5),
    )
    print('escape vias:', builder.escape_ground_pads())
    builder.fill_zones()
    pcbnew.SaveBoard(str(out_path), builder.board)
    write_stackup(out_path)
    patch_project_rules()
    print(f'wrote {out_path}; {len(builder.footprints)} footprints')
    if unplaced:
        print(f'ERROR: {len(unplaced)} parts are not on the board')
    failed = unplaced or overlaps or floorplan_problems or silk_problems
    return 1 if failed or test_point_problems else 0


if __name__ == '__main__':
    exit_code = main()
    # Gerbers, zip and renders follow every board write
    export_fab.export_fabrication()
    sys.exit(exit_code)
