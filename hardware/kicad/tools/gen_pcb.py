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

BOARD_WIDTH = 130.0
BOARD_HEIGHT = 110.0
EDGE_MARGIN = 0.8
PASSIVE_GAP = 0.45
# JLCPCB needs 0.2 mm drills on 0.45 mm pads or larger, else a paid 4-wire test.
VIA_IN_PAD_DIAMETER = 0.45
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
    '+3V3_CH': 'COLD HEAD TEMP',
}
# sections too full for their test points: these sit in the nearest free
# spot of the roomy power box instead
TEST_POINTS_OUTSIDE = {'WATER COOLING', 'COLD HEAD TEMP'}
TEST_POINT_OVERFLOW = 'POWER INPUT & RAILS'
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

# ref -> (x, y, rotation); everything that is not a plain R/C is placed here.
PLACEMENT = {
    # ESP32 (antenna points at +x, hangs on the board edge) and USB
    'U1': (117.25, 19.5, 270),
    'J1': (96.0, 4.2, 180),
    'U2': (100.5, 13.0, 0),
    'SW1': (118.0, 3.6, 0),
    'SW2': (98.0, 29.5, 0),
    # signal generator (flow right to left towards J9)
    'J9': (5.6, 9.0, 270),
    'J8': (5.6, 22.0, 270),
    'U6': (24.0, 9.0, 0),
    'U5': (36.0, 8.0, 0),
    'U4': (47.0, 8.0, 0),
    'U3': (59.0, 8.0, 0),
    'U9': (36.0, 22.5, 0),
    'U7': (47.0, 22.5, 0),
    'U8': (57.0, 21.0, 0),
    'Q6': (18.0, 21.0, 0),
    'Q5': (18.0, 27.0, 0),
    'D4': (17.0, 32.6, 0),
    # isolation barrier (ISO side is left of x = 39.25)
    'J11': (5.6, 43.2, 270),
    'J12': (5.6, 55.0, 270),
    'U18': (26.0, 49.0, 0),
    'U17': (40.0, 44.5, 180),
    'PS1': (40.0, 58.0, 0),
    # +-15 V rails
    'U20': (64.0, 49.0, 0),
    'L2': (64.0, 38.3, 0),
    'D5': (73.0, 42.0, 0),
    'L3': (64.0, 60.5, 0),
    'D6': (74.0, 54.0, 0),
    'U21': (74.0, 34.5, 0),
    'U22': (80.5, 34.5, 0),
    # power input and button
    'J2': (5.6, 101, 270),
    'F1': (19.0, 105, 0),
    'D1': (19.0, 95.25, 0),
    'C6': (30.0, 104, 0),
    'Q1': (46.5, 102, 0),
    'U11': (17.0, 84, 0),
    'U12': (26.0, 88.5, 0),
    'U13': (7.0, 84, 0),
    'Q2': (34.0, 82.5, 0),
    'Q3': (39.0, 82.5, 0),
    'Q4': (37.0, 90, 0),
    'D3': (47.0, 86.25, 0),
    'J7': (56.0, 87, 0),
    'SW3': (46.0, 78, 0),
    # 5 V / 3.3 V rails and system current
    'U15': (64.5, 85.5, 0),
    'L1': (71.0, 86.25, 0),
    'U16': (79.0, 81, 0),
    'U23': (62.0, 102.5, 0),
    'R67': (62.5, 106.7, 0),
    'C71': (71.0, 105.1, 0),
    # cooling and cold head
    'J3': (83.3, 106, 0),
    'J4': (94.8, 106, 0),
    'J5': (106.3, 106, 0),
    'J6': (116.8, 106, 0),
    'J10': (126.0, 88.0, 90),
    'U10': (99.5, 94, 0),
    'U14': (113.0, 84.0, 0),
    'JP5': (113.5, 76.0, 0),
    # panel indicators and IMU cable header
    'J14': (119.4, 45.7, 270),
    'D9': (77.0, 13.0, 0),
    'D10': (81.0, 13.0, 0),
    'D11': (76.0, 6.0, 0),
    'D7': (56.0, 101.5, 90),
    'D8': (56.0, 106.5, 90),
    'U24': (76.0, 17.0, 0),
    'D2': (103.5, 98, 0),
    # SC18IS604 I2C bridge and its MISO gate, close to the EMC2303 (U10)
    'U25': (101.0, 67.5, 0),
    'U26': (101.0, 75.2, 0),
    # compressor relay driver (open area in the middle of the board)
    'J13': (96.0, 50.5, 0),
    'Q7': (89.0, 47.0, 0),
    'Q8': (89.0, 54.0, 0),
    'D12': (100.9, 43.4, 0),
    'D13': (100.9, 46.0, 0),
}

# ISO_GND island (left of the barrier); keep-out bands keep GND copper away
# from it.
ISO_REGION = Rect(0.0, 36.5, 39.25, 70.0)
ISO_NETS = {'ISO_GND', 'ISO_3V3'}

# GND pads that get a locked via-in-pad before routing (fine-pitch LGA)
FINE_PITCH_GROUND_PADS = {
    'U23': {'7'},
    'U4': {'4', '9'},
}

# Anchors for ground test points (ground nets have no natural neighbour pad):
# the k-th TP on GND sits beside the k-th entry; ISO_GND beside the isolator.
GND_TP_ANCHORS = [('Q5', '2'), ('U15', '4'), ('U6', '2')]
ISO_GND_TP_ANCHOR = ('U17', '9')
ISO_BAND = 1.5
ANTENNA_KEEPOUT = Rect(124.0, 0.0, BOARD_WIDTH, 43.5)
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
    'J10': ['F+', 'S+', 'S-', 'F-'],
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
SILK_TEXT_THICKNESS = 0.12
LOGO_FILE = KICAD_DIR / 'artwork' / 'cooler_trace.geojson'
LOGO_SOURCE_SIZE = (1658.0, 648.0)  # trace bitmap size in pixels
LOGO_CENTER = (65.0, 51.0)
LOGO_WIDTH = 80.0
TITLE_TEXT = 'STI Hybrid-98 Cryocooler Control Unit'
ALPHA_TEXT = 'ALPHA'

HOLES = [(4.0, 35.7), (62.0, 30.0), (126.0, 58.0), (126.0, 95.0)]
LOCAL_RECT_OVERRIDES = {
    'RF_Module:ESP32-S3-WROOM-2': Rect(-9.2, -12.9, 9.2, 13.2),
    # the stock test point courtyard is 3.7 mm square around a 1.5 mm pad
    'TestPoint:TestPoint_Pad_D1.5mm': Rect(-1.15, -1.15, 1.15, 1.15),
}


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
        self.occupancy = Occupancy(
            Rect(0, 0, BOARD_WIDTH, BOARD_HEIGHT), EDGE_MARGIN, PASSIVE_GAP
        )
        self.occupancy.keepouts.append(ANTENNA_KEEPOUT)
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

    def load_footprints(self):
        for ref, part in self.parts.items():
            path, name = footprint_path(part['footprint'])
            footprint = pcbnew.FootprintLoad(path, name)
            if footprint is None:
                raise RuntimeError(f'missing footprint {part["footprint"]}')
            pcbmodels.attach_missing_models(footprint)
            footprint.SetReference(ref)
            footprint.SetValue(part['value'])
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
        rotated_x, rotated_y = rotate_point(local_x, local_y, angle)
        return center_x + rotated_x, center_y + rotated_y

    def place(self, ref, center_x, center_y, angle):
        footprint = self.footprints[ref]
        footprint.SetPosition(
            pcbnew.VECTOR2I(to_internal(center_x), to_internal(center_y))
        )
        footprint.SetOrientationDegrees(angle)
        self.centers[ref] = (center_x, center_y, angle)
        self.occupancy.add(
            ref, placed_rect(self.local_rects[ref], center_x, center_y, angle)
        )

    def is_passive(self, ref):
        """R, C, test points and the Debug sheet's LEDs are placed beside the
        pad they serve.
        """
        if ref in PLACEMENT:
            return False
        return (
            ref[0] in 'RC'
            or ref.startswith(('TP', 'JP'))
            or (
                ref[0] == 'D'
                and self.parts[ref]['sheet'] in ('Debug', 'Supply Switches')
            )
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
        for ref, (center_x, center_y, angle) in PLACEMENT.items():
            if ref not in self.footprints:
                raise KeyError(f'PLACEMENT names unknown ref {ref}')
            self.place(ref, center_x, center_y, angle)
            self.module[ref] = self.part_module(ref)
        for index, (hole_x, hole_y) in enumerate(HOLES):
            self.occupancy.add(
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
        corners = [
            (0, 0),
            (BOARD_WIDTH, 0),
            (BOARD_WIDTH, BOARD_HEIGHT),
            (0, BOARD_HEIGHT),
        ]
        for index, (start_x, start_y) in enumerate(corners):
            end_x, end_y = corners[(index + 1) % 4]
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
        obstacles = self.pocket_obstacles()
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
                    if module and not pcbfloorplan.text_inside(module, rect):
                        continue
                    if not rect.inside(self.occupancy.board_rect):
                        continue
                    if any(rect.overlaps(k) for k in self.occupancy.keepouts):
                        continue
                    if any(rect.overlaps(other) for other in obstacles):
                        continue
                    return spot_x, spot_y, turned, rect
        return None

    def pocket_obstacles(self):
        """Boxes a label pocket must keep off: other pockets, silk, holes,
        the candidate being tested, and for placed parts only their pad
        boxes (the courtyard margin around them is free for text).
        """
        boxes = []
        for name, rect in self.occupancy.rects.items():
            if name.startswith('txt_pin'):
                boxes.append(rect.inflated(0.25))
            elif name.startswith(('txt_', 'silk_', 'hole', 'candidate')):
                boxes.append(rect.inflated(0.05))
            elif name in self.centers:
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

    def label_size(self, ref):
        """Box size of the part label (SILK_LABELS) for a ref, or None."""
        if ref not in SILK_LABELS:
            return None
        box = self.text_rect(SILK_LABELS[ref], 0, 0, SILK_TEXT_SIZE)
        return box.max_x - box.min_x, box.max_y - box.min_y

    def reserve_pockets(self, ref, part_rect, module):
        """Reserves room for the reference text (and the part label, if the
        part has one) beside a part; returns False if either has no room.
        """
        taken = []
        ok = True
        for kind, size in (
            ('ref', self.text_dims[ref]),
            ('label', self.label_size(ref)),
        ):
            if size is None:
                continue
            pocket = self.find_pocket(part_rect, module, *size)
            if pocket is None:
                ok = False
                break
            spot_x, spot_y, turned, rect = pocket
            name = f'txt_{kind}_{ref}'
            self.occupancy.add(name, rect)
            taken.append((name, kind, (spot_x, spot_y, turned)))
        if not ok:
            for name, _, _ in taken:
                del self.occupancy.rects[name]
            return False
        for name, kind, spot in taken:
            (self.pockets if kind == 'ref' else self.label_pockets)[ref] = spot
        return True

    def pin_label_boxes(self, ref, side):
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
        }
        body = self.occupancy.rects[ref]
        column = side in ('left', 'right')
        boxes = []
        for number, text in enumerate(PIN_LABELS[ref], start=1):
            pad_x, pad_y = pads[number]
            base = self.text_rect(text, 0, 0, SILK_TEXT_SIZE)
            length, thickness = 2 * base.max_x, 2 * base.max_y
            if column:
                width, height = length, thickness
                center_y = pad_y
                center_x = (
                    body.max_x + 0.2 + width / 2
                    if side == 'right'
                    else body.min_x - 0.2 - width / 2
                )
            else:
                width, height = thickness, length
                center_x = pad_x
                center_y = (
                    body.max_y + 0.2 + height / 2
                    if side == 'down'
                    else body.min_y - 0.2 - height / 2
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
        for side in sides:
            boxes = self.pin_label_boxes(ref, side)
            obstacles = self.pocket_obstacles()
            if all(
                rect.inside(self.occupancy.board_rect)
                and (not module or pcbfloorplan.text_inside(module, rect))
                and not any(rect.overlaps(o) for o in obstacles)
                for *_, rect in boxes
            ):
                for index, (_, _, _, _, rect) in enumerate(boxes):
                    self.occupancy.add(f'txt_pin_{ref}_{index}', rect)
                self.pin_pockets[ref] = boxes
                return True
        print('no room for the pin labels of', ref)
        return False

    def add_pin_labels(self):
        """Prints the connector pin labels reserved above."""
        for ref, labels in self.pin_pockets.items():
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
        holes = [(hole_x, hole_y, 2.4) for hole_x, hole_y in HOLES]
        self.early_labels = {}
        for module in pcbfloorplan.MODULE_REGIONS:
            spot = self.module_label_spot(module, board_rect, holes)
            self.early_labels[module] = spot
            if spot is not None:
                text, left_x, line_y = spot
                width = pcbfloorplan.label_width(text)
                self.occupancy.add(
                    f'silk_label_{module}',
                    Rect(left_x, line_y - 0.5, left_x + width, line_y + 0.5),
                )

    def reserve_anchor_pockets(self):
        """Reserves label room beside every placed (non-passive) part before
        the passives crowd in.
        """
        for ref in PIN_LABELS:
            self.reserve_pin_labels(ref)
        missing = []
        for ref in PLACEMENT:
            module = self.module.get(ref)
            part = self.occupancy.rects[ref]
            if not self.reserve_pockets(ref, part, module):
                missing.append(ref)
        print('no label room beside:', missing)

    def place_passives(self):
        crowd = collections.Counter()
        pending = [ref for ref in self.parts if self.is_passive(ref)]
        offsets = ring_offsets(60.0, 0.5)
        unplaced = []
        while pending:
            progressed = False
            # signal-net passives first, then pure decoupling
            pending.sort(
                key=lambda r: (
                    self.is_decoupling(r),
                    int(r.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
                )
            )
            for ref in list(pending):
                choice = self.pick_target(ref, crowd)
                if choice is None:
                    continue
                pad_index, target = choice
                if not self.place_near(ref, pad_index, target, offsets):
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
        # labels: place them anyway, their labels are searched for afterwards
        retry, unplaced = unplaced, []
        self.require_pockets = False
        for ref in retry:
            choice = self.pick_target(ref, crowd)
            if choice is not None and self.place_near(
                ref, choice[0], choice[1], offsets
            ):
                crowd[choice[1]] += 1
            else:
                unplaced.append(ref)
        self.require_pockets = True
        return unplaced

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

    def place_near(self, ref, primary_pad, target, offsets):
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
        local_rect = self.local_rects[ref]
        # a passive stays in its own module's box; debug parts (no module)
        # join the box of the part they sit beside
        module = self.part_module(ref) or self.module.get(target[0])
        if ref.startswith('TP') and module in TEST_POINTS_OUTSIDE:
            module = TEST_POINT_OVERFLOW
        best = None
        for offset_x, offset_y in offsets:
            if (
                best is not None
                and (offset_x**2 + offset_y**2) ** 0.5 > best[0] + 1.5
            ):
                break
            for angle in (0, 90, 180, 270):
                center_x, center_y = target_x + offset_x, target_y + offset_y
                rect = placed_rect(local_rect, center_x, center_y, angle)
                if module and not pcbfloorplan.region_contains(module, rect):
                    continue
                if not self.occupancy.is_free(rect):
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
                        best = (score, center_x, center_y, angle, pockets)
        if best is None:
            return False
        self.place(ref, best[1], best[2], best[3])
        self.module[ref] = module
        for name, kind, spot, pocket_rect in best[4]:
            self.occupancy.add(name, pocket_rect)
            (self.pockets if kind == 'ref' else self.label_pockets)[ref] = spot
        return True

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

    def add_keepout(self, rect, footprints=False):
        zone = pcbnew.ZONE(self.board)
        zone.SetIsRuleArea(True)
        zone.SetDoNotAllowZoneFills(True)
        zone.SetDoNotAllowTracks(True)
        zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowFootprints(footprints)
        zone.SetDoNotAllowPads(False)
        zone.SetLayerSet(pcbnew.LSET.AllCuMask())
        self.set_outline(zone, rect)
        self.board.Add(zone)

    def add_planes(self):
        board_rect = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT)
        region = ISO_REGION
        # isolation bands: right side, top and bottom of the ISO island
        self.add_keepout(
            Rect(
                region.max_x,
                region.min_y - ISO_BAND,
                region.max_x + ISO_BAND,
                region.max_y + ISO_BAND,
            )
        )
        self.add_keepout(
            Rect(0.0, region.min_y - ISO_BAND, region.max_x, region.min_y)
        )
        self.add_keepout(
            Rect(0.0, region.max_y, region.max_x, region.max_y + ISO_BAND)
        )
        self.add_keepout(ANTENNA_KEEPOUT)
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
        for hole_x, hole_y in HOLES:
            footprint = pcbnew.FootprintLoad(
                str(STOCK_FOOTPRINTS / 'MountingHole.pretty'),
                'MountingHole_3.2mm_M3',
            )
            footprint.SetReference('')
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

    def pre_place_fine_pitch_ground_vias(self):
        """Locked 0.35 mm via-in-pad on the fine-pitch LGA/MSOP ground pads before
        autorouting. The LGA pads are 0.5 mm apart, so a router-placed via
        or an inner-layer track under them cannot be kept clear; 0.35 mm
        keeps 0.15 mm to the neighbouring pads (order filled/capped vias).
        """
        for ref, pads in FINE_PITCH_GROUND_PADS.items():
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
        if getattr(self, '_text_boxes', None) is None:
            boxes = []
            for footprint in self.board.GetFootprints():
                for item in (footprint.Reference(), footprint.Value()):
                    if not item.IsVisible():
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
            self._text_boxes = boxes
        return self._text_boxes

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
        item.SetLayer(layer if layer is not None else pcbnew.F_SilkS)
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
        half_width = len(text) * size * 0.45 + 0.2
        half_height = size * 0.6
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
        obstacles = self.silk_obstacles()
        courtyards = self.keep_out_courtyards()
        inner = self.occupancy.board_rect.inflated(EDGE_MARGIN - 0.45)
        texts = [
            self.text_box(footprint.Reference())
            for footprint in self.footprints.values()
            if footprint.Reference().IsVisible()
        ]
        for ref, text in SILK_LABELS.items():
            if ref not in self.centers or ref not in self.occupancy.rects:
                continue
            if ref in self.label_pockets:
                spot_x, spot_y, turned = self.label_pockets[ref]
                item = self.add_text(
                    text,
                    spot_x,
                    spot_y,
                    SILK_TEXT_SIZE,
                    thickness=SILK_TEXT_THICKNESS,
                )
                if turned:
                    item.SetTextAngleDegrees(90)
                continue
            part = self.body_rect(ref)
            center_x = (part.min_x + part.max_x) / 2
            center_y = (part.min_y + part.max_y) / 2
            module = self.module_of_ref(ref)
            base = self.text_rect(text, 0, 0, SILK_TEXT_SIZE)
            best = None
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
                            or any(rect.overlaps(t) for t in texts)
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
                            pcbfloorplan.text_level(module, rect)
                            if module is not None
                            else 0
                        )
                        score = (
                            2 if level == 2 else 0,
                            level,
                            pcbfloorplan.rect_gap(rect, part),
                        )
                        if best is None or score < best[0]:
                            best = (score, center, rect, turned)
                if best is not None and best[0][0] == 0:
                    break
            if best is None:
                print('silk label not placed:', ref, text)
                continue
            if best[0][0] > 0:
                print('silk label sits outside its box:', ref, text)
            _, center, rect, turned = best
            if best[0][1] == 1:
                self.bumps.setdefault(module, []).append(rect)
            item = self.add_text(
                text, *center, SILK_TEXT_SIZE, thickness=SILK_TEXT_THICKNESS
            )
            if turned:
                item.SetTextAngleDegrees(90)
            self.occupancy.add(f'silk_{ref}', rect)
            obstacles.append(rect)

    def add_logo(self):
        """Black-and-white trace of the cryocooler on the back silkscreen
        (mirrored so it reads correctly from the back) with the unit name
        below it.
        """
        geometry = json.loads(LOGO_FILE.read_text())
        features = geometry['features'] if 'features' in geometry else [geometry]
        source_w, source_h = LOGO_SOURCE_SIZE
        scale = LOGO_WIDTH / source_w
        center_x, center_y = LOGO_CENTER

        def to_board(point):
            # potrace's GeoJSON is y-up; the board is y-down. The back layer is
            # mirrored, so x runs the other way.
            x = center_x - (point[0] - source_w / 2) * scale
            y = center_y - (point[1] - source_h / 2) * scale
            return pcbnew.VECTOR2I(to_internal(x), to_internal(y))

        for feature in features:
            shape_geometry = feature['geometry']
            polygons = (
                shape_geometry['coordinates']
                if shape_geometry['type'] == 'MultiPolygon'
                else [shape_geometry['coordinates']]
            )
            for rings in polygons:
                polygon = pcbnew.SHAPE_POLY_SET()
                outline = polygon.NewOutline()
                for point in rings[0][:-1]:
                    polygon.Append(to_board(point), outline)
                for ring in rings[1:]:
                    hole = polygon.NewHole(outline)
                    for point in ring[:-1]:
                        polygon.Append(to_board(point), outline, hole)
                shape = pcbnew.PCB_SHAPE(self.board)
                shape.SetShape(pcbnew.SHAPE_T_POLY)
                shape.SetLayer(pcbnew.B_SilkS)
                shape.SetFilled(True)
                shape.SetWidth(0)
                shape.SetPolyShape(polygon)
                self.board.Add(shape)
        logo_height = LOGO_WIDTH * source_h / source_w
        title_y = center_y + logo_height / 2 + 4.0
        self.add_text(
            TITLE_TEXT, center_x, title_y, 2.0, pcbnew.B_SilkS, mirrored=True,
            thickness=0.3,
        )
        self.add_text(
            ALPHA_TEXT + ' DEV UNIT', center_x, title_y + 4.0, 2.0,
            pcbnew.B_SilkS, mirrored=True, thickness=0.3,
        )

    def add_alpha_mark(self):
        """Large ALPHA on the front silkscreen, in the free spot nearest the
        board centre.
        """
        size = 3.0
        half_w, half_h = len(ALPHA_TEXT) * size * 0.5 + 0.5, size * 0.7
        best = None
        for step_y in range(2, int(BOARD_HEIGHT) - 2):
            for step_x in range(2, int(BOARD_WIDTH) - 2):
                rect = Rect(
                    step_x - half_w, step_y - half_h,
                    step_x + half_w, step_y + half_h,
                )
                if not self.silk_free(rect):
                    continue
                distance = (step_x - 65.0) ** 2 + (step_y - 50.0) ** 2
                if best is None or distance < best[0]:
                    best = (distance, step_x, step_y, rect)
        if best is None:
            print('ALPHA mark: no free spot on the front')
            return
        _, mark_x, mark_y, rect = best
        self.add_text(ALPHA_TEXT, mark_x, mark_y, size, thickness=0.45)
        self.occupancy.add('silk_alpha', rect)

    def check_floorplan(self):
        """Returns messages for parts outside their module's box and for
        boxes closer together than the minimum gap.
        """
        problems = pcbfloorplan.check_regions(self.occupancy.board_rect.inflated(EDGE_MARGIN))
        for ref, module in self.module.items():
            if module is None:
                continue
            center_x, center_y, angle = self.centers[ref]
            rect = placed_rect(self.local_rects[ref], center_x, center_y, angle)
            if not pcbfloorplan.region_contains(module, rect):
                problems.append(f'{ref} is outside the {module} box')
        return problems

    def module_label_spot(self, module, board_rect, holes):
        """First (text, left_x, line_y) on a drawn border that clears every
        part, hole and earlier label, or None.
        """
        plain = pcbfloorplan.outline_segments(module, board_rect, holes)
        gap = pcbfloorplan.LABEL_GAP
        for text in pcbfloorplan.label_texts(module):
            width = pcbfloorplan.label_width(text)
            for left_x, line_y in pcbfloorplan.label_candidates(
                module, text, board_rect
            ):
                if not pcbfloorplan.covered(
                    plain, line_y, left_x - gap, left_x + width + gap
                ):
                    continue
                if pcbfloorplan.text_hits_hole(left_x, line_y, width, holes):
                    continue
                box = Rect(left_x, line_y - 0.5, left_x + width, line_y + 0.5)
                if any(
                    box.overlaps(other)
                    for name, other in self.occupancy.rects.items()
                    if not name.startswith('silk_box')
                ):
                    continue
                return text, left_x, line_y
        return None

    def draw_module_lines(self, module, spot, board_rect, holes):
        """Draws the silk outline of one module (replacing any earlier one)
        and reserves the line areas.
        """
        for shape in self.box_lines.pop(module, []):
            self.board.Remove(shape)
            self._removed_shapes.append(shape)
        for name in [
            n for n in self.occupancy.rects if n.startswith(f'silk_box_{module}_')
        ]:
            del self.occupancy.rects[name]
        shapes = []
        for index, (start, end) in enumerate(
            pcbfloorplan.outline_segments(module, board_rect, holes, spot)
        ):
            line = pcbnew.PCB_SHAPE(self.board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(pcbnew.F_SilkS)
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
        self.box_lines[module] = shapes

    def add_module_boxes(self):
        """Draws each module's outline and label on the front silkscreen and
        reserves the line and label areas so other silk keeps clear.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 2.4) for hole_x, hole_y in HOLES]
        self._removed_shapes = []
        self.box_labels = {}
        for module in pcbfloorplan.MODULE_REGIONS:
            spot = self.early_labels.get(module)
            if spot is None:
                spot = self.module_label_spot(module, board_rect, holes)
            if spot is None:
                print('no free border for the label of', module)
            self.box_labels[module] = spot
            self.draw_module_lines(module, spot, board_rect, holes)
            if spot is None:
                continue
            text, left_x, line_y = spot
            width = pcbfloorplan.label_width(text)
            self.add_text(
                text,
                left_x,
                line_y,
                pcbfloorplan.LABEL_SIZE,
                thickness=SILK_TEXT_THICKNESS + 0.03,
                justify='left',
            )
            self.occupancy.add(
                f'silk_label_{module}',
                Rect(left_x, line_y - 0.5, left_x + width, line_y + 0.5),
            )

    def bulge_module_boxes(self):
        """Redraws the outline of every module whose labels did not fit
        inside it so the line goes around them.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 2.4) for hole_x, hole_y in HOLES]
        for module, rects in self.bumps.items():
            pcbfloorplan.EXTRA_REGIONS[module] = [
                pcbfloorplan.bump_rect(rect) for rect in rects
            ]
            self.draw_module_lines(
                module, self.box_labels.get(module), board_rect, holes
            )
        print(
            'module outlines bulged around labels:',
            {m: len(r) for m, r in self.bumps.items()},
        )

    def text_box(self, item):
        box = item.GetBoundingBox()
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
        for footprint in self.footprints.values():
            for pad in footprint.Pads():
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
                if graphic.GetLayer() != pcbnew.F_SilkS:
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
                Rect(hole_x - 2.9, hole_y - 2.9, hole_x + 2.9, hole_y + 2.9)
            )
        return boxes

    def keep_out_courtyards(self):
        """Courtyards of the big placed parts, by owner: another part's label
        inside one reads as that part's label (the ESP32 antenna area is
        exempt).
        """
        return {
            ref: rect
            for ref, rect in self.occupancy.rects.items()
            if ref in PLACEMENT and ref != 'U1'
        }

    def module_of_ref(self, ref):
        """Module box a part belongs to (debug parts: the box they sit in)."""
        module = self.module.get(ref)
        if module is not None:
            return module
        center_x, center_y, _ = self.centers[ref]
        for name, rects in pcbfloorplan.MODULE_REGIONS.items():
            if any(
                r.min_x <= center_x <= r.max_x and r.min_y <= center_y <= r.max_y
                for r in rects
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
            pcbfloorplan.text_level(module, rect) if module is not None else 0
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
        part = self.body_rect(ref).inflated(reach)
        return [
            self.body_rect(name)
            for name in self.footprints
            if name != ref and self.body_rect(name).overlaps(part)
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

        for ref in order:
            footprint = self.footprints[ref]
            item = footprint.Reference()
            if not item.IsVisible() or ref not in self.occupancy.rects:
                continue
            module = self.module_of_ref(ref)
            if ref in self.pockets:
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
            near = [
                obstacle
                for obstacle in obstacles
                if obstacle.min_y < box.max_y + 8.0
                and obstacle.max_y > box.min_y - 8.0
                and obstacle.min_x < box.max_x + 8.0
                and obstacle.max_x > box.min_x - 8.0
            ]
            part = self.occupancy.rects[ref]
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
                for gap in (0.0, 0.2, 0.4, 0.7, 1.0, 1.4, 2.0, 2.8):
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
            if best is None:
                stuck.append(ref)
                finished[ref] = box
                continue
            if best[0][0] > 0:
                weak.append(ref)
            if best[0][1] == 1 and module is not None:
                self.bumps.setdefault(module, []).append(best[3])
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
        print('reference texts moved:', moved, 'no free spot:', stuck)
        print('reference texts still ambiguous or outside their box:', weak)

    def adopt_board(self):
        """Takes footprints, courtyards and silk graphics from an already
        built (possibly routed) board so the silkscreen steps can run on it
        without placing or routing again.
        """
        self.footprints = {
            fp.GetReference(): fp
            for fp in self.board.GetFootprints()
            if fp.GetReference()
        }
        for ref, footprint in self.footprints.items():
            position = footprint.GetPosition()
            self.centers[ref] = (
                position.x / 1e6,
                position.y / 1e6,
                footprint.GetOrientationDegrees(),
            )
            override = LOCAL_RECT_OVERRIDES.get(
                self.parts.get(ref, {}).get('footprint')
            )
            if override is not None:
                x_pos, y_pos, angle = self.centers[ref]
                self.occupancy.add(
                    ref, placed_rect(override, x_pos, y_pos, angle)
                )
                continue
            box = footprint.GetCourtyard(pcbnew.F_CrtYd).BBox()
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
        for index, (hole_x, hole_y) in enumerate(HOLES):
            self.occupancy.add(
                f'hole{index}',
                Rect(hole_x - 3.4, hole_y - 3.4, hole_x + 3.4, hole_y + 3.4),
            )

    def add_silkscreen(self):
        self.add_module_boxes()
        if not self.pin_pockets:
            # silk-only runs on an existing board: find the spots now
            for ref in PIN_LABELS:
                self.reserve_pin_labels(ref)
        self.add_pin_labels()
        self.place_reference_texts()
        self.add_part_labels()
        self.bulge_module_boxes()
        self.add_alpha_mark()
        self.add_logo()

    def build(self):
        self.load_footprints()
        self.place_anchors()
        self.reserve_module_labels()
        self.reserve_anchor_pockets()
        self.pre_route_current_path()
        self.pre_place_fine_pitch_ground_vias()
        unplaced = self.place_passives()
        for footprint in self.footprints.values():
            self.board.Add(footprint)
        self.add_outline_and_keepouts()
        self.add_net_classes()
        self.add_mounting_holes()
        self.add_planes()
        self.add_silkscreen()
        return unplaced


def patch_project_rules():
    """Writes the fine-pitch via limits into cryocooler.kicad_pro (pcbnew does
    not persist the annular-width minimum): 0.45 mm vias, 0.2 mm drills and a
    0.075 mm ring for the 0.5 mm pitch LGA/MSOP ground pads.
    """
    path = KICAD_DIR / 'cryocooler.kicad_pro'
    project = json.loads(path.read_text())
    rules = project['board']['design_settings']['rules']
    rules['min_via_annular_width'] = 0.075
    rules['min_via_diameter'] = VIA_IN_PAD_DIAMETER
    rules['min_through_hole_diameter'] = 0.2
    path.write_text(json.dumps(project, indent=2) + '\n')


def main():
    """Usage: gen_pcb.py [place|route|finish|texts] [freerouting.jar] —
    `route` also autoroutes and fills zones; `texts` redoes all silkscreen
    and adds 3D envelope models on the existing board.
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
        patch_project_rules()
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
        builder.add_silkscreen()
        pcbnew.SaveBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'), builder.board)
        return 0
    unplaced = builder.build()
    overlaps = [
        pair
        for pair in builder.occupancy.overlaps_report()
        if not any('_current_' in name for name in pair)
        and not any(name.startswith('silk_box') for name in pair)
        and not (
            any(name.startswith('txt_') for name in pair)
            and not all(name.startswith('txt_') for name in pair)
        )
    ]
    floorplan_problems = builder.check_floorplan()
    out_path = KICAD_DIR / 'cryocooler.kicad_pcb'
    print('unplaced:', unplaced)
    print('overlapping pairs:', overlaps)
    print('floorplan problems:', floorplan_problems)
    if mode == 'route':
        work_dir = Path(tempfile.mkdtemp(prefix='cryo_route_'))
        builder.autoroute(work_dir)
        print('routing files in', work_dir)
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
    patch_project_rules()
    print(f'wrote {out_path}; {len(builder.footprints)} footprints')
    return 1 if unplaced or overlaps or floorplan_problems else 0


if __name__ == '__main__':
    exit_code = main()
    # Gerbers, zip and renders follow every board write
    export_fab.export_fabrication()
    sys.exit(exit_code)
