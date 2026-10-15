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
from pcbplace import Occupancy, Rect, placed_rect, ring_offsets, rotate_point

BOARD_WIDTH = 130.0
BOARD_HEIGHT = 100.0
EDGE_MARGIN = 0.8
PASSIVE_GAP = 1.0
STOCK_FOOTPRINTS = Path(
    '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
)

GROUND_NETS = {'GND', 'ISO_GND'}
POWER_NETS = GROUND_NETS | {
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
    'SW2': (100.0, 33.0, 0),
    # signal generator (flow right to left towards J9)
    'J9': (5.6, 9.0, 270),
    'J8': (5.6, 22.0, 270),
    'U6': (24.0, 9.0, 0),
    'U5': (36.0, 8.0, 0),
    'U4': (47.0, 8.0, 0),
    'U3': (59.0, 8.0, 0),
    'U9': (36.0, 24.0, 0),
    'U7': (47.0, 24.0, 0),
    'U8': (57.0, 22.0, 0),
    'Q6': (18.0, 20.0, 0),
    'Q5': (18.0, 27.0, 0),
    'D4': (15.0, 34.0, 0),
    # isolation barrier (ISO side is left of x = 39.25)
    'J11': (5.6, 44.0, 270),
    'J12': (5.6, 57.0, 270),
    'U18': (26.0, 51.0, 0),
    'U17': (40.0, 45.0, 180),
    'PS1': (40.0, 60.0, 0),
    # +-15 V rails
    'U20': (64.0, 52.0, 0),
    'L2': (64.0, 40.0, 0),
    'D5': (73.0, 46.0, 0),
    'L3': (64.0, 63.0, 0),
    'D6': (74.0, 58.0, 0),
    'U21': (74.0, 36.0, 0),
    'U22': (82.0, 36.0, 0),
    # power input and button
    'J2': (5.6, 91.0, 270),
    'F1': (19.0, 95.0, 0),
    'D1': (19.0, 85.5, 0),
    'C6': (30.0, 94.0, 0),
    'Q1': (46.5, 92.0, 0),
    'U11': (17.0, 78.0, 0),
    'U12': (26.0, 81.0, 0),
    'U13': (7.0, 78.0, 0),
    'Q2': (34.0, 77.0, 0),
    'Q3': (40.0, 77.0, 0),
    'Q4': (37.0, 82.0, 0),
    'D3': (47.0, 77.0, 0),
    'J7': (56.0, 80.0, 0),
    'SW3': (48.0, 70.0, 0),
    # 5 V / 3.3 V rails and system current
    'U15': (70.0, 81.0, 0),
    'L1': (79.0, 81.0, 0),
    'U16': (88.0, 75.0, 0),
    'U23': (60.0, 90.0, 0),
    'R67': (60.0, 96.0, 0),
    'C71': (71.0, 93.0, 0),
    # cooling and cold head
    'J3': (80.0, 96.0, 0),
    'J4': (91.5, 96.0, 0),
    'J5': (103.0, 96.0, 0),
    'J6': (113.5, 96.0, 0),
    'J10': (126.0, 81.0, 90),
    'U10': (96.0, 85.0, 0),
    'U14': (112.0, 75.0, 0),
    # panel indicators and IMU
    'U19': (120.0, 52.0, 0),
    'D9': (84.0, 5.0, 0),
    'D10': (89.0, 5.0, 0),
    'D11': (76.0, 6.0, 0),
    'D7': (54.5, 87.5, 90),
    'D8': (54.5, 91.5, 90),
    'U24': (70.0, 14.0, 0),
    'D2': (104.0, 87.0, 0),
    # SC18IS604 I2C bridge and its MISO gate, close to the EMC2303 (U10)
    'U25': (100.0, 70.0, 0),
    'U26': (108.0, 70.0, 0),
    # compressor relay driver (open area in the middle of the board)
    'J13': (96.0, 55.0, 0),
    'Q7': (88.0, 51.0, 0),
    'Q8': (88.0, 58.0, 0),
    'D12': (103.0, 49.0, 0),
    'D13': (103.0, 62.0, 0),
}

# ISO_GND island (left of the barrier); keep-out bands keep GND copper away
# from it.
ISO_REGION = Rect(0.0, 36.5, 39.25, 70.0)
ISO_NETS = {'ISO_GND', 'ISO_3V3'}

# GND pads that get a locked via-in-pad before routing (fine-pitch LGA)
FINE_PITCH_GROUND_PADS = {
    'U19': {'2', '3', '6', '7'},
    'U23': {'7'},
    'U4': {'4', '9'},
}

# Anchors for ground test points (ground nets have no natural neighbour pad):
# the k-th TP on GND sits beside the k-th entry; ISO_GND beside the isolator.
GND_TP_ANCHORS = [('U1', '1'), ('U15', '4'), ('U6', '2')]
ISO_GND_TP_ANCHOR = ('U17', '9')
ISO_BAND = 1.5
ANTENNA_KEEPOUT = Rect(124.0, 0.0, BOARD_WIDTH, 43.5)
FREEROUTING_JAR = Path(sys.argv[2]) if len(sys.argv) > 2 else None
MAX_PASSES = '12'
JAVA = (
    '/Library/Java/JavaVirtualMachines/temurin-25.jdk/Contents/Home/bin/java'
)

# Local rect overrides (the ESP32 courtyard includes a large antenna keep-out).
HOLES = [(4.0, 35.7), (62.0, 30.0), (126.0, 58.0), (126.0, 95.0)]
LOCAL_RECT_OVERRIDES = {
    'RF_Module:ESP32-S3-WROOM-2': Rect(-9.2, -12.9, 9.2, 13.2)
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
            footprint.SetReference(ref)
            footprint.SetValue(part['value'])
            footprint.Reference().SetTextSize(
                pcbnew.VECTOR2I(to_internal(0.8), to_internal(0.8))
            )
            footprint.Reference().SetTextThickness(to_internal(0.15))
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
            or ref.startswith('TP')
            or (ref[0] == 'D' and self.parts[ref]['sheet'] == 'Debug')
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

    def place_anchors(self):
        for ref, (center_x, center_y, angle) in PLACEMENT.items():
            if ref not in self.footprints:
                raise KeyError(f'PLACEMENT names unknown ref {ref}')
            self.place(ref, center_x, center_y, angle)
        for index, (hole_x, hole_y) in enumerate(HOLES):
            self.occupancy.add(
                f'hole{index}',
                Rect(hole_x - 2.4, hole_y - 2.4, hole_x + 2.4, hole_y + 2.4),
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

    def place_passives(self):
        crowd = collections.Counter()
        pending = [ref for ref in self.parts if self.is_passive(ref)]
        offsets = ring_offsets(40.0, 0.5)
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
                    best = (score, center_x, center_y, angle)
        if best is None:
            return False
        self.place(ref, best[1], best[2], best[3])
        return True

    # ─── rules, zones, routing ───

    def add_net_classes(self):
        settings = self.board.GetDesignSettings()
        settings.m_MinClearance = to_internal(0.15)
        settings.m_TrackMinWidth = to_internal(0.15)
        settings.m_ViasMinSize = to_internal(0.35)
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
        via.SetWidth(to_internal(0.35))
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
        """Locked 0.35 mm via-in-pad on the LSM6DSOX (U19) ground pads before
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
                via.SetWidth(to_internal(0.35))
                via.SetDrill(to_internal(0.2))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(self.full_net(net)))
                via.SetLocked(True)
                self.board.Add(via)

    def build(self):
        self.load_footprints()
        self.place_anchors()
        self.pre_route_current_path()
        self.pre_place_fine_pitch_ground_vias()
        unplaced = self.place_passives()
        for footprint in self.footprints.values():
            self.board.Add(footprint)
        self.add_outline_and_keepouts()
        self.add_net_classes()
        self.add_mounting_holes()
        self.add_planes()
        return unplaced


def patch_project_rules():
    """Writes the fine-pitch via limits into cryocooler.kicad_pro (pcbnew does
    not persist the annular-width minimum): 0.35 mm vias, 0.2 mm drills and a
    0.075 mm ring for the 0.5 mm pitch LGA/MSOP ground pads.
    """
    path = KICAD_DIR / 'cryocooler.kicad_pro'
    project = json.loads(path.read_text())
    rules = project['board']['design_settings']['rules']
    rules['min_via_annular_width'] = 0.075
    rules['min_via_diameter'] = 0.35
    rules['min_through_hole_diameter'] = 0.2
    path.write_text(json.dumps(project, indent=2) + '\n')


def main():
    """Usage: gen_pcb.py [place|route] [freerouting.jar] — `route` also
    autoroutes and fills zones.
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else 'place'
    builder = PcbBuilder()
    if mode == 'finish':
        # re-open the routed board, tidy zones, add stitching vias
        builder.board = pcbnew.LoadBoard(
            str(KICAD_DIR / 'cryocooler.kicad_pcb')
        )
        builder.board.GetDesignSettings().m_ViasMinSize = to_internal(0.35)
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
    unplaced = builder.build()
    overlaps = [
        pair
        for pair in builder.occupancy.overlaps_report()
        if not any('_current_' in name for name in pair)
    ]
    out_path = KICAD_DIR / 'cryocooler.kicad_pcb'
    print('unplaced:', unplaced)
    print('overlapping pairs:', overlaps)
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
    return 1 if unplaced or overlaps else 0


if __name__ == '__main__':
    sys.exit(main())
