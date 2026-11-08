"""Moves rev 3 onto the Phoenix UCS 125-87 board (100 x 62 mm, drawing 2203445).

Starts from the routed UCS 145-125 rev 3 board, so every footprint, 3D model and
hand-made land pattern carries over. It drops the parts the schematic retired,
adds new ones, syncs pad nets, removes all copper, zones and board drawings, draws
the new outline (ESP32 antenna notch, restricted corners), hides the reference
texts and places every part on both sides. `route` adds the ISO moat, the In1 planes and the\nlocked current paths, runs Freerouting and pours the copper.

Usage (KiCad's python):
    ucs125_board.py place in.kicad_pcb out.kicad_pcb
    ucs125_board.py preroute|route placed.kicad_pcb out.kicad_pcb [rounds]
    ucs125_board.py finish routed.kicad_pcb
    ucs125_board.py reroute finished.kicad_pcb out.kicad_pcb drc.json   (one more round, keeps copper)
    ucs125_board.py boardid board.kicad_pcb x y
    ucs125_board.py labels board.kicad_pcb   (after finish and boardid)
"""
import math
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

import pcbmodels
from pcbnetlist import KICAD_DIR, load_netlist
from pcbplace import Rect, placed_rect, ring_offsets, rotate_point
from spi_expander_board import load_footprint

MM = pcbnew.FromMM
KEEP = []  # removed items stay referenced until the board is saved

# ─── outline (drawing 2203445) ───
WIDTH, HEIGHT = 100.0, 62.0
HOLES = [(4.2, 4.2), (95.8, 4.2), (4.2, 57.8), (95.8, 57.8)]
CORNER_SQUARE = 4.45
RING_RADIUS = 3.0
EDGE_GAP = 0.3  # courtyard to board edge, except a connector's mating side
PART_GAP = 0.15  # between courtyards (they already carry 0.25 mm margins)
# the back has room to spare: wider gaps there, and a ring round each IC for
# its tracks and vias to escape
BACK_PART_GAP = 0.3
FANOUT_RING = {'top': 0.2, 'bottom': 0.6}
HOLE_MARGIN = 0.25
HOLE_COURTYARD = 3.5  # MountingHole_3.2mm_M3 courtyard radius

# ESP32 on the top edge, antenna over a routed notch; no copper or parts in the
# strips beside it (the module's 15 mm keep-out), as on the 145-125 board
U1_SPOT = (50.0, 13.0)
NOTCH = Rect(U1_SPOT[0] - 9.5, 0.0, U1_SPOT[0] + 9.5, 6.0)
ANTENNA_KEEPOUTS = [
    Rect(NOTCH.min_x - 14.5, 0.0, NOTCH.min_x, 6.75),
    Rect(NOTCH.max_x, 0.0, NOTCH.max_x + 14.5, 6.75),
]

# Wall connectors: (ref, edge, side, start along the edge, overhang past it).
# Each slides along its edge from `start` to the first free spot. Overhangs are
# the courtyard's reach past the edge on the 145-125 board.
EDGE_PLAN = [
    ('J1', 'top', 'top', 15.0, 0.55),
    ('J12', 'left', 'top', 7.6, 3.29),
    ('J14', 'right', 'top', 7.6, 0.05),  # Micro-Lock Plus, face 0.2 inside the edge (pads 0.3 clear)
    ('SW3', 'right', 'top', 25.5, 3.0),
    ('J9', 'right', 'top', 37.6, 0.29),
    ('J11', 'bottom', 'top', 7.5, 3.29),
    ('J2', 'bottom', 'top', 20.1, 0.29),
    ('J5', 'bottom', 'bottom', 34.0, 0.08),
    ('J6', 'bottom', 'bottom', 34.0, 0.3),
    ('J7', 'bottom', 'bottom', 34.0, 0.3),
    ('J13', 'bottom', 'bottom', 34.0, 0.3),
    ('J3', 'bottom', 'top', 34.0, 0.24),
    ('J4', 'bottom', 'top', 34.0, 0.24),
    ('J10', 'bottom', 'bottom', 60.0, -0.3),  # SMD, clear of J3's pin row
    ('J8', 'bottom', 'bottom', 60.0, 0.29),
]
# outward normal of each edge
EDGE_NORMALS = {'top': (0, -1), 'bottom': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
# footprint-local mating direction (all point +y except J12's)
FACE_LOCAL = {'J12': (0, -1)}

# Fixed anchors: ref -> (x, y, rotation, side). U1 sits exactly here; every
# other entry is a preferred spot, nudged to the nearest free one.
ANCHORS = {
    'U1': (U1_SPOT[0], U1_SPOT[1], 0, 'top'),
}
PREFERRED = {
    # ─── left: USB, logic supplies, isolated amp current, power input ───
    'U2': (21.0, 12.0, 0, 'bottom'),
    'U28': (29.0, 14.0, 0, 'bottom'),
    # U17 at 270 on the back: isolated pins (11-20) face down to U18, so the
    # barrier runs across it at y 27.5
    'U18': (21.5, 40.5, 0, 'top'),
    'U17': (21.5, 27.5, 270, 'bottom'),
    'F1': (31.0, 44.5, 0, 'top'),
    'D1': (37.5, 41.5, 90, 'top'),
    'Q1': (34.0, 38.0, 0, 'top'),
    'C65': (34.0, 30.0, 0, 'top'),
    'C66': (34.0, 19.0, 0, 'top'),
    'U15': (22.0, 16.0, 0, 'top'),
    'L1': (22.0, 21.5, 0, 'top'),
    'L4': (28.5, 12.0, 0, 'top'),
    'U16': (28.5, 16.5, 0, 'top'),  # TPS62822: L4 right above its SW pin
    'R78': (31.0, 38.0, 0, 'bottom'),
    'U23': (36.0, 38.0, 0, 'bottom'),
    'SW1': (36.5, 11.0, 90, 'top'),
    # ─── under U1: signal chain (front) ───
    'U3': (43.0, 30.0, 0, 'top'),
    'U4': (43.5, 34.5, 0, 'top'),
    'U5': (49.0, 33.0, 0, 'top'),
    'D16': (49.0, 37.5, 0, 'top'),
    'U6': (54.5, 33.0, 0, 'top'),
    'R92': (47.5, 41.5, 0, 'top'),
    'R96': (54.0, 42.5, 0, 'top'),
    'J15': (46.0, 56.5, 0, 'top'),
    'TP14': (39.75, 51.0, 0, 'top'),  # GND loop by the signal chain
    # ─── right: +-15 V rails, power good, indicators ───
    # shifted right into the room the small J14 leaves, to open the middle
    'U20': (73.5, 18.0, 0, 'top'),
    'L2': (69.5, 11.0, 0, 'top'),
    'L3': (79.0, 11.0, 0, 'top'),
    'D4': (68.5, 17.5, 90, 'top'),
    'D5': (79.5, 18.0, 90, 'top'),
    'U21': (75.0, 28.0, 0, 'top'),
    'SW2': (83.5, 29.0, 90, 'top'),  # beside SW3, clear of the middle
    # ─── back: logic ICs near what they serve ───
    'U32': (50.0, 21.0, 0, 'bottom'),  # under U1, next to the GPIOs it decodes
    'U25': (64.0, 36.0, 0, 'bottom'),
    'U27': (44.0, 42.0, 0, 'bottom'),
    'U31': (50.0, 42.0, 0, 'bottom'),
    'U24': (60.0, 31.0, 0, 'bottom'),
    'U14': (85.0, 44.0, 0, 'bottom'),
    'U35': (88.0, 38.0, 0, 'bottom'),
    'U36': (88.0, 12.5, 90, 'bottom'),  # J14 filter, behind its pins
    'U33': (66.0, 43.0, 0, 'bottom'),
    'Q26': (70.0, 44.0, 0, 'bottom'),
    'Q27': (76.0, 44.0, 0, 'bottom'),
    'Q7': (56.0, 44.0, 0, 'bottom'),
    'Q8': (60.0, 44.0, 0, 'bottom'),
    'D14': (58.0, 40.0, 0, 'bottom'),
    'Q5': (84.0, 51.0, 0, 'bottom'),
    'Q6': (80.0, 51.0, 0, 'bottom'),
    'Q21': (76.0, 51.0, 0, 'bottom'),
    'U11': (40.0, 30.0, 0, 'bottom'),
    'U12': (40.0, 34.0, 0, 'bottom'),
    'Q41': (44.0, 30.0, 0, 'bottom'),
    'D17': (40.0, 38.0, 0, 'bottom'),
    'U34': (90.0, 31.0, 0, 'bottom'),
    'Q22': (74.0, 34.0, 0, 'bottom'),
    'Q23': (77.0, 34.0, 0, 'bottom'),
    'Q24': (80.0, 34.0, 0, 'bottom'),
    'Q42': (74.0, 38.0, 0, 'bottom'),
    'D15': (77.0, 38.0, 0, 'bottom'),
    'Q25': (40.0, 50.0, 0, 'bottom'),
}
# parts that must sit on the front (user: buttons, lights and test points)
FRONT_ONLY_REFS = {'R92', 'R96'}
# switching and LDO parts keep their passives on their own side
SAME_SIDE_OWNERS = {'U15', 'U16', 'U20', 'U21'}
GROUND_NETS = {'GND', 'ISO_GND'}

# Isolated island (U18 side of U17): ISO copper stays inside these rects on
# every layer; other copper keeps ISO_BAND away. U17 straddles the barrier.
ISO_RECTS = [
    Rect(0.0, 24.3, 14.0, 28.25),  # J12 pin 2, 2 mm clear of U17's pin 1
    Rect(0.0, 28.25, 28.5, 45.8),  # J12 pin 1, U17 isolated half, U18
    Rect(0.0, 45.8, 18.0, HEIGHT),  # J11
]
ISO_BAND = 1.5
ISO_SEED_NETS = {'ISO_GND', 'ISO_GND2', 'ISO_5V', 'VISOOUT'}
ISO_EXEMPT = {'U17', 'J12'}


def normal_angle(face, normal, bottom):
    """Rotation that turns a footprint's local mating direction to `normal`
    (a bottom part is mirrored in y first, as placed_rect does)."""
    face_x, face_y = face[0], (-face[1] if bottom else face[1])
    for angle in (0, 90, 180, 270):
        turned = rotate_point(face_x, face_y, angle)
        if abs(turned[0] - normal[0]) < 1e-6 and abs(turned[1] - normal[1]) < 1e-6:
            return angle
    raise ValueError((face, normal))


class Geometry:
    """Local (unrotated, top side) shapes of one footprint."""

    def __init__(self, footprint):
        copy = pcbnew.FOOTPRINT(footprint)
        KEEP.append(copy)
        if copy.IsFlipped():
            copy.Flip(copy.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        copy.SetOrientationDegrees(0)
        copy.SetPosition(pcbnew.VECTOR2I(0, 0))
        box = copy.GetCourtyard(pcbnew.F_CrtYd).BBox()
        if box.GetWidth() == 0:
            box = copy.GetBoundingBox(False)
        self.courtyard = Rect(
            box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6
        )
        self.holes = []
        self.pads = []
        self.pad_centers = {}
        for pad in copy.Pads():
            position = pad.GetPosition()
            pad_x, pad_y = position.x / 1e6, position.y / 1e6
            self.pad_centers.setdefault(pad.GetNumber(), []).append((pad_x, pad_y))
            drill = pad.GetDrillSizeX() / 1e6
            if drill > 0:
                radius = max(drill, pad.GetSizeX() / 1e6, pad.GetSizeY() / 1e6) / 2
                if drill < 0.5:
                    radius = drill / 2 + 0.15  # thermal via
                self.holes.append((pad_x, pad_y, radius))
            half_x, half_y = pad.GetSizeX() / 2e6, pad.GetSizeY() / 2e6
            if int(pad.GetOrientationDegrees()) % 180 == 90:
                half_x, half_y = half_y, half_x
            self.pads.append(Rect(pad_x - half_x, pad_y - half_y, pad_x + half_x, pad_y + half_y))
        # body outline from the maker-drawing envelope (model y is up, board y down)
        self.bodies = []
        envelope = pcbmodels.ENVELOPES.get(str(copy.GetFPID().GetLibItemName()))
        if envelope is not None and isinstance(envelope[1], list):
            for size_x, size_y, _height, center_x, center_y, _colour in envelope[1]:
                self.bodies.append(
                    Rect(center_x - size_x / 2, -center_y - size_y / 2,
                         center_x + size_x / 2, -center_y + size_y / 2)
                )
        if not self.bodies:
            self.bodies = [self.courtyard]


class Layout:
    """Placement state: where each part is and what it blocks on each side."""

    def __init__(self, board):
        self.board = board
        self.footprints = {fp.GetReference(): fp for fp in board.GetFootprints() if fp.GetReference()}
        self.geometry = {ref: Geometry(fp) for ref, fp in self.footprints.items()}
        self.spots = {}  # ref -> (x, y, angle, side)
        self.edge_side = {'U1': 'top'}  # connector ref -> edge its mating face crosses
        self.cache = {}  # ref -> (side, padded courtyard, holes, presence)
        self.grid = {}  # (column, row) of GRID_CELL -> refs whose courtyard touches it
        self.iso_refs = isolated_refs(self.footprints)

    # ─── shapes in board coordinates ───

    def rect(self, ref, local, spot=None):
        x, y, angle, side = spot or self.spots[ref]
        return placed_rect(local, x, y, angle, side == 'bottom')

    def courtyard(self, ref, spot=None):
        return self.rect(ref, self.geometry[ref].courtyard, spot)

    def holes(self, ref, spot=None):
        x, y, angle, side = spot or self.spots[ref]
        result = []
        for hole_x, hole_y, radius in self.geometry[ref].holes:
            local_y = -hole_y if side == 'bottom' else hole_y
            turned_x, turned_y = rotate_point(hole_x, local_y, angle)
            result.append((x + turned_x, y + turned_y, radius))
        return result

    def presence(self, ref, spot=None):
        """What a through pin poking up from the other side would hit: the
        body outline and the pads."""
        geometry = self.geometry[ref]
        return [self.rect(ref, local, spot) for local in geometry.bodies + geometry.pads]

    # ─── checks ───

    def outline_problem(self, ref, spot):
        box = self.courtyard(ref, spot)
        edge = self.edge_side.get(ref)
        limits = Rect(EDGE_GAP, EDGE_GAP, WIDTH - EDGE_GAP, HEIGHT - EDGE_GAP)
        if (edge != 'left' and box.min_x < limits.min_x) or (edge != 'right' and box.max_x > limits.max_x):
            return 'edge'
        if (edge != 'top' and box.min_y < limits.min_y) or (edge != 'bottom' and box.max_y > limits.max_y):
            return 'edge'
        for keepout in ANTENNA_KEEPOUTS + [NOTCH.inflated(EDGE_GAP)]:
            if box.overlaps(keepout):
                return 'antenna'
        return 'corner' if corner_problem(box) else None

    def shapes(self, ref, spot):
        """(padded courtyard, holes, presence) of a part at a spot."""
        return (
            self.courtyard(ref, spot).inflated(self.margin(ref, spot[3])),
            self.holes(ref, spot),
            self.presence(ref, spot),
        )

    def margin(self, ref, side):
        """Half the gap this part keeps from its neighbours on `side`."""
        if ref.startswith(('J', 'SW')):  # wall parts keep their packed spacing
            return PART_GAP / 2
        gap = (BACK_PART_GAP if side == 'bottom' else PART_GAP) / 2
        if ref.startswith('U') and len(self.geometry[ref].pad_centers) >= 6:
            return gap + FANOUT_RING[side]
        return gap

    def conflict(self, ref, spot, ignore=()):
        """First placed part this spot collides with, else None."""
        side = spot[3]
        box, my_holes, my_presence = self.shapes(ref, spot)
        reach = box.inflated(4.0)
        for other in self.near(box):
            if other == ref or other in ignore:
                continue
            other_side, other_box, other_holes, other_presence = self.cache[other]
            if other_side == side:
                if box.overlaps(other_box):
                    return other
                continue
            if not reach.overlaps(other_box):
                continue
            # other side: no through pin or peg inside a courtyard (KiCad's
            # pth/npth_inside_courtyard checks both sides)
            for hole_x, hole_y, radius in other_holes:
                if circle_hits(box, hole_x, hole_y, radius):
                    return other
            for hole_x, hole_y, radius in my_holes:
                if circle_hits(other_box, hole_x, hole_y, radius):
                    return other
        return None

    def iso_problem(self, ref, spot):
        """ISO parts keep their pads in the island; others keep pads ISO_BAND
        clear of it and their courtyard out of it."""
        if ref in ISO_EXEMPT:
            return None
        pads = [self.rect(ref, local, spot) for local in self.geometry[ref].pads]
        if ref in self.iso_refs:
            return None if all(inside_iso(pad) for pad in pads) else 'iso-out'
        if any(self.courtyard(ref, spot).overlaps(area) for area in ISO_RECTS):
            return 'iso-in'
        band = [area.inflated(ISO_BAND) for area in ISO_RECTS]
        return 'iso-band' if any(pad.overlaps(area) for pad in pads for area in band) else None

    def problem(self, ref, spot, ignore=()):
        return self.outline_problem(ref, spot) or self.iso_problem(ref, spot) or self.conflict(ref, spot, ignore)

    def put(self, ref, spot):
        self.spots[ref] = spot
        self.cache[ref] = (spot[3], *self.shapes(ref, spot))
        for cell in cells(self.cache[ref][1]):
            self.grid.setdefault(cell, set()).add(ref)

    def near(self, box):
        found = set()
        for cell in cells(box):
            found |= self.grid.get(cell, set())
        return sorted(found)

    def pad_position(self, ref, number, spot=None):
        x, y, angle, side = spot or self.spots[ref]
        pad_x, pad_y = self.geometry[ref].pad_centers[number][0]
        if side == 'bottom':
            pad_y = -pad_y
        turned_x, turned_y = rotate_point(pad_x, pad_y, angle)
        return x + turned_x, y + turned_y

    def nudge(self, ref, spot, sides, radius=20.0, step=0.25):
        """Nearest free spot to `spot` (any of `sides`, same rotation)."""
        x, y, angle, _side = spot
        for offset_x, offset_y in ring_offsets(radius, step):
            for side in sides:
                candidate = (x + offset_x, y + offset_y, angle, side)
                if self.problem(ref, candidate) is None:
                    return candidate
        return None

    # ─── wall connectors ───

    def edge_spot(self, ref, edge, side, along, overhang):
        """Spot whose courtyard starts at `along` on the edge and reaches
        `overhang` past it."""
        bottom = side == 'bottom'
        face = FACE_LOCAL.get(ref, (0, 1))
        angle = normal_angle(face, EDGE_NORMALS[edge], bottom)
        box = placed_rect(self.geometry[ref].courtyard, 0, 0, angle, bottom)
        if edge == 'left':
            return (-overhang - box.min_x, along - box.min_y, angle, side)
        if edge == 'right':
            return (WIDTH + overhang - box.max_x, along - box.min_y, angle, side)
        if edge == 'top':
            return (along - box.min_x, -overhang - box.min_y, angle, side)
        return (along - box.min_x, HEIGHT + overhang - box.max_y, angle, side)

    def place_on_edge(self, ref, edge, side, start, overhang, step=0.1, limit=100.0):
        self.edge_side[ref] = edge
        along = start
        while along < start + limit:
            spot = self.edge_spot(ref, edge, side, along, overhang)
            if self.problem(ref, spot) is None:
                self.put(ref, spot)
                return spot
            along += step
        return None


GRID_CELL = 2.0


def isolated_refs(footprints):
    """Parts with an isolated-side net: flood from the ISO supplies through
    every part except the isolator and the J12 wall connector."""
    nets = {ref: {pad.GetNetname() for pad in fp.Pads()} - {''} for ref, fp in footprints.items()}
    iso_nets = set(ISO_SEED_NETS)
    refs = set()
    while True:
        found = {ref for ref, pad_nets in nets.items() if ref not in ISO_EXEMPT and pad_nets & iso_nets}
        if found == refs:
            return refs
        refs = found
        for ref in refs:
            iso_nets |= nets[ref] - GROUND_NETS


def inside_iso(rect, step=0.25):
    """True if every sampled point of `rect` lies in one of ISO_RECTS."""
    columns = max(1, int((rect.max_x - rect.min_x) / step))
    rows = max(1, int((rect.max_y - rect.min_y) / step))
    for column in range(columns + 1):
        for row in range(rows + 1):
            x = rect.min_x + (rect.max_x - rect.min_x) * column / columns
            y = rect.min_y + (rect.max_y - rect.min_y) * row / rows
            if not any(area.min_x <= x <= area.max_x and area.min_y <= y <= area.max_y for area in ISO_RECTS):
                return False
    return True


def cells(box):
    for column in range(int(math.floor(box.min_x / GRID_CELL)), int(math.floor(box.max_x / GRID_CELL)) + 1):
        for row in range(int(math.floor(box.min_y / GRID_CELL)), int(math.floor(box.max_y / GRID_CELL)) + 1):
            yield column, row


def corner_problem(box):
    """True when `box` reaches a restricted corner square or hole ring."""
    for hole_x, hole_y in HOLES:
        corner = Rect(
            0 if hole_x < WIDTH / 2 else WIDTH - CORNER_SQUARE - EDGE_GAP,
            0 if hole_y < HEIGHT / 2 else HEIGHT - CORNER_SQUARE - EDGE_GAP,
            CORNER_SQUARE + EDGE_GAP if hole_x < WIDTH / 2 else WIDTH,
            CORNER_SQUARE + EDGE_GAP if hole_y < HEIGHT / 2 else HEIGHT,
        )
        if box.overlaps(corner) or circle_hits(box, hole_x, hole_y, max(RING_RADIUS + EDGE_GAP, HOLE_COURTYARD)):
            return True
    return False


def circle_hits(rect, center_x, center_y, radius):
    nearest_x = min(max(center_x, rect.min_x), rect.max_x)
    nearest_y = min(max(center_y, rect.min_y), rect.max_y)
    return (nearest_x - center_x) ** 2 + (nearest_y - center_y) ** 2 < radius**2


# ─── indicator LEDs: one labelled column on the front ───

LED_LABELS = {
    'D13': 'STATE', 'D7': 'PWR', 'D11': '+15V', 'D12': '-15V',
    'D2': 'AMP', 'D3': 'COMP', 'D6': 'ALERT', 'D10': 'ISO 5V',
}
LED_COLUMN = ['D13', 'D7', 'D11', 'D12', 'D2', 'D3', 'D6']
LED_BLOCK_SPOT = (85.0, 48.0)  # first LED centre: bottom right, clear of U25 and J8 pegs
LED_ISO_SPOT = (24.0, 30.0)  # D10 stays in the isolated island
LED_PITCH = 1.6
LABEL_HEIGHT = 0.8  # high-precision silk, as the part labels
LABEL_WIDTH = 0.7
LABEL_STROKE = 0.1


def make_label(board, text, x, y):
    """Left-justified, vertically centred front silk text at (x, y)."""
    label = pcbnew.PCB_TEXT(board)
    label.SetText(text)
    label.SetLayer(pcbnew.F_SilkS)
    label.SetTextSize(pcbnew.VECTOR2I(MM(LABEL_WIDTH), MM(LABEL_HEIGHT)))
    label.SetTextThickness(MM(LABEL_STROKE))
    label.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    label.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    label.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    return label


def label_rect(ref, spot, text):
    """Silk area of an LED's label (KiCad's own text box plus 0.15 mm),
    starting just past the part."""
    start = spot[0] + (1.8 if ref == 'D13' else 1.0)
    box = make_label(None, text, start, spot[1]).GetBoundingBox()
    return Rect(box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6).inflated(0.15)


def label_problem(layout, rect):
    if rect.max_x > WIDTH - EDGE_GAP or rect.max_y > HEIGHT - EDGE_GAP or rect.min_y < EDGE_GAP:
        return 'edge'
    if any(rect.overlaps(keepout) for keepout in ANTENNA_KEEPOUTS):
        return 'antenna'
    if corner_problem(rect):
        return 'corner'
    for other in layout.near(rect.inflated(4.0)):
        side, box, holes, _presence = layout.cache[other]
        if side == 'top' and box.overlaps(rect):
            return other
        # through pins and pegs of parts on either side
        if any(circle_hits(rect, hole_x, hole_y, radius) for hole_x, hole_y, radius in holes):
            return other
    return None


def reserve_label(layout, ref, rect):
    name = f'~label {ref}'
    layout.cache[name] = ('top', rect, [], [])
    for cell in cells(rect):
        layout.grid.setdefault(cell, set()).add(name)


def reserve_current_path(layout):
    """Keep back-side parts off the IP+ B.Cu run that pre_route_current lays
    from U18's via bar down to J11 pin 1 (2 mm copper plus clearance)."""
    column_x = layout.pad_position('U18', '1')[0]
    top_y = layout.pad_position('U18', '1')[1]
    j11_x, j11_y = layout.pad_position('J11', '1')
    j11_pad = next(pad for pad in layout.footprints['J11'].Pads() if pad.GetNumber() == '1')
    j11_top = j11_y - j11_pad.GetSizeY() / 2e6
    via_x = column_x - 1.85
    drop = j11_top + 1.0 - (via_x - j11_x)
    reach = CURRENT_WIDTH / 2 + 0.4
    corridors = [Rect(via_x - reach, top_y - reach, via_x + reach, drop),
                 Rect(j11_x - reach - 0.5, drop - reach, via_x + reach, j11_top + 2.0 + reach)]
    for index, rect in enumerate(corridors):
        name = f'~IP+ {index}'
        layout.cache[name] = ('bottom', rect, [], [])
        for cell in cells(rect):
            layout.grid.setdefault(cell, set()).add(name)


def column_spots(anchor):
    spots, y = [], anchor[1]
    for index, ref in enumerate(LED_COLUMN):
        if index:
            y += 2.6 if LED_COLUMN[index - 1] == 'D13' else LED_PITCH
        spots.append((ref, (anchor[0], y, 0, 'top')))
    return spots


def place_leds(layout):
    """The LED column at the first free anchor near LED_BLOCK_SPOT, then D10 in
    the island; each label's area is reserved so packing keeps it clear."""
    groups = [(LED_BLOCK_SPOT, column_spots), (LED_ISO_SPOT, lambda anchor: [('D10', (*anchor, 0, 'top'))])]
    for base, spots_at in groups:
        for offset_x, offset_y in ring_offsets(20.0, 0.25):
            spots = spots_at((base[0] + offset_x, base[1] + offset_y))
            labels = [label_rect(ref, spot, LED_LABELS[ref]) for ref, spot in spots]
            if any(layout.problem(ref, spot) for ref, spot in spots):
                continue
            if any(label_problem(layout, rect) for rect in labels):
                continue
            if any(first.overlaps(second) for first in labels for second in
                   [layout.shapes(ref, spot)[0] for ref, spot in spots]):
                continue
            for (ref, spot), rect in zip(spots, labels):
                layout.put(ref, spot)
                reserve_label(layout, ref, rect)
            print('LEDs', ' '.join(ref for ref, _ in spots), 'at', f'{spots[0][1][0]:.2f}, {spots[0][1][1]:.2f}')
            break
        else:
            print('NO ROOM for LEDs', ' '.join(ref for ref, _ in spots_at(base)))


def add_led_labels(board, layout):
    """Front silk label beside each LED placed by place_leds."""
    for item in list(board.GetDrawings()):
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetLayer() == pcbnew.F_SilkS and item.GetText() in LED_LABELS.values():
            board.Remove(item)
    for ref, text in LED_LABELS.items():
        spot = layout.spots.get(ref)
        if spot is None:
            continue
        board.Add(make_label(board, text, spot[0] + (1.8 if ref == 'D13' else 1.0), spot[1]))


# ─── automatic placement of the small parts ───

OTHER_SIDE_COST = 0.75  # mm-equivalent of a via to the other side


def allowed_sides(layout, ref, owner):
    name = str(layout.footprints[ref].GetFPID().GetLibItemName())
    if ref.startswith('TP') or 'LED' in name or ref in FRONT_ONLY_REFS:
        return ['top']
    if owner in SAME_SIDE_OWNERS:
        return [layout.spots[owner][3]]
    return ['top', 'bottom']


def choose_target(layout, ref, parts, nets, pad_nets, auto, load):
    """(my pad, target ref, target pad) this part should sit beside."""
    best = None
    my_sheet = parts[ref]['sheet']
    pads = pad_nets.get(ref, {})
    for ground_pass in (False, True):
        for number, net in sorted(pads.items()):
            if net.startswith('unconnected') or ((net in GROUND_NETS) != ground_pass):
                continue
            nodes = [(other, pad) for other, pad in nets[net] if other != ref and other in layout.spots]
            fixed = [node for node in nodes if node[0] not in auto]
            pool = fixed or nodes
            if not pool:
                continue
            same = [node for node in pool if parts[node[0]]['sheet'] == my_sheet] or pool
            other, pad = min(same, key=lambda node: (load.get(node, 0), node))
            rank = (len(nets[net]) + (0 if fixed else 100), number, other, pad)
            if best is None or rank < best:
                best = rank
        if best is not None:
            return best[1:]
    return None


def place_small_parts(layout, parts, nets, auto):
    pad_nets = {}
    for net, nodes in nets.items():
        for ref, pad in nodes:
            pad_nets.setdefault(ref, {})[pad] = net
    load = {}
    pending = sorted(auto, key=lambda ref: (re.sub(r'\d', '', ref), int(re.sub(r'\D', '', ref) or 0)))
    while pending:
        progress = False
        for ref in list(pending):
            target = choose_target(layout, ref, parts, nets, pad_nets, auto, load)
            if target is None:
                continue
            my_pad, owner, owner_pad = target
            if my_pad not in layout.geometry[ref].pad_centers:
                my_pad = next(iter(layout.geometry[ref].pad_centers))
            target_x, target_y = layout.pad_position(owner, owner_pad)
            best = None
            for side in allowed_sides(layout, ref, owner):
                penalty = 0.0 if side == layout.spots[owner][3] else OTHER_SIDE_COST
                for angle in (0, 90, 180, 270):
                    offset = layout.pad_position(ref, my_pad, (0.0, 0.0, angle, side))
                    ideal = (target_x - offset[0], target_y - offset[1], angle, side)
                    limit = 14.0 if best is None else best[0] - penalty
                    for step_x, step_y in RING_OFFSETS:
                        distance = math.hypot(step_x, step_y)
                        if distance > limit:
                            break
                        spot = (ideal[0] + step_x, ideal[1] + step_y, angle, side)
                        if layout.problem(ref, spot) is None:
                            if best is None or distance + penalty < best[0]:
                                best = (distance + penalty, spot)
                            break
            pending.remove(ref)
            progress = True
            if best is None:
                print('no spot for', ref, 'near', owner)
                continue
            layout.put(ref, best[1])
            load[(owner, owner_pad)] = load.get((owner, owner_pad), 0) + 1
        if not progress:
            print('no target for', ' '.join(pending))
            break


RING_OFFSETS = ring_offsets(14.0, 0.2)


# ─── board preparation ───


def sync_parts(board, parts, nets):
    """Drops footprints the schematic no longer has, adds new ones and sets
    every pad's net from the netlist."""
    on_board = {fp.GetReference(): fp for fp in board.GetFootprints()}
    removed = []
    for ref, footprint in on_board.items():
        if ref and ref not in parts:
            KEEP.append(footprint)
            board.Remove(footprint)
            removed.append(ref)
    added = []
    for ref, part in parts.items():
        footprint = on_board.get(ref)
        if footprint is not None and str(footprint.GetFPID().GetLibItemName()) == part['footprint'].split(':')[1]:
            footprint.SetValue(part['value'])
            continue
        if footprint is not None:  # the part changed package: swap the footprint
            KEEP.append(footprint)
            board.Remove(footprint)
        footprint = load_footprint(part['footprint'])
        if footprint is None:
            raise RuntimeError(f'no footprint {part["footprint"]} for {ref}')
        board.Add(footprint)
        footprint.SetReference(ref)
        footprint.SetValue(part['value'])
        pcbmodels.attach_missing_models(footprint)
        added.append(ref)
    pad_nets = {}
    for name, nodes in nets.items():
        for ref, pad in nodes:
            pad_nets[(ref, pad)] = name
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            name = pad_nets.get((ref, pad.GetNumber()))
            if name is None:
                pad.SetNetCode(0)
                continue
            item = board.FindNet(name)
            if item is None:
                item = pcbnew.NETINFO_ITEM(board, name)
                board.Add(item)
            pad.SetNet(item)
    return removed, added


def strip_board(board):
    """Removes copper, zones, board drawings and texts; hides footprint texts."""
    for item in list(board.GetTracks()) + list(board.Zones()) + list(board.GetDrawings()):
        KEEP.append(item)
        board.Remove(item)
    for footprint in board.GetFootprints():
        footprint.Reference().SetVisible(False)
        footprint.Value().SetVisible(False)
        for item in footprint.GraphicalItems():
            if isinstance(item, pcbnew.PCB_TEXT) and item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                item.SetVisible(False)


def add_segment(board, start, end, layer=pcbnew.Edge_Cuts, width=0.1):
    segment = pcbnew.PCB_SHAPE(board)
    segment.SetShape(pcbnew.SHAPE_T_SEGMENT)
    segment.SetLayer(layer)
    segment.SetWidth(MM(width))
    segment.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    segment.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    board.Add(segment)


def restricted_outline(hole_x, hole_y, steps=32):
    """Corner square joined with the ring round the hole (drawing 2203445)."""
    corner_x = 0.0 if hole_x < WIDTH / 2 else WIDTH
    corner_y = 0.0 if hole_y < HEIGHT / 2 else HEIGHT
    sign_x = 1 if corner_x == 0.0 else -1
    sign_y = 1 if corner_y == 0.0 else -1
    points = [(corner_x, corner_y), (corner_x + sign_x * CORNER_SQUARE, corner_y)]
    for step in range(steps + 1):
        angle = -math.pi / 2 + math.pi * 1.5 * step / steps
        points.append(
            (hole_x + sign_x * RING_RADIUS * math.cos(angle), hole_y + sign_y * RING_RADIUS * math.sin(angle))
        )
    points.append((corner_x, corner_y + sign_y * CORNER_SQUARE))
    return points


def rule_area(board, points, footprints=False):
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(footprints)
    zone.SetLayerSet(pcbnew.LSET.AllCuMask())
    outline = zone.Outline()
    outline.NewOutline()
    for point_x, point_y in points:
        outline.Append(MM(point_x), MM(point_y))
    board.Add(zone)


def rect_points(rect):
    return [(rect.min_x, rect.min_y), (rect.max_x, rect.min_y), (rect.max_x, rect.max_y), (rect.min_x, rect.max_y)]


def draw_outline(board):
    corners = [
        (0, 0), (NOTCH.min_x, 0), (NOTCH.min_x, NOTCH.max_y), (NOTCH.max_x, NOTCH.max_y),
        (NOTCH.max_x, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT),
    ]
    for index, start in enumerate(corners):
        add_segment(board, start, corners[(index + 1) % len(corners)])
    for hole_x, hole_y in HOLES:
        points = restricted_outline(hole_x, hole_y)
        rule_area(board, points)  # parts kept out by the placer; holes live here
        for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
            polygon = pcbnew.SHAPE_POLY_SET()
            outline = polygon.NewOutline()
            for point_x, point_y in points:
                polygon.Append(pcbnew.VECTOR2I(MM(point_x), MM(point_y)), outline)
            shape = pcbnew.PCB_SHAPE(board)
            shape.SetShape(pcbnew.SHAPE_T_POLY)
            shape.SetLayer(layer)
            shape.SetFilled(True)
            shape.SetWidth(0)
            shape.SetPolyShape(polygon)
            board.Add(shape)
    for keepout in ANTENNA_KEEPOUTS:
        rule_area(board, rect_points(keepout), footprints=True)


def board_id_lines():
    revision = subprocess.run(
        ['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=KICAD_DIR
    ).stdout.strip()
    return ('cryocooler', f'BETA rev {revision}')


def apply_spots(layout):
    for ref, (x, y, angle, side) in layout.spots.items():
        footprint = layout.footprints[ref]
        footprint.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        if (side == 'bottom') != footprint.IsFlipped():
            footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        footprint.SetOrientationDegrees(angle)


def check_prediction(layout):
    """The placement maths must match KiCad's own courtyards."""
    worst = []
    for ref, spot in layout.spots.items():
        footprint = layout.footprints[ref]
        layer = pcbnew.B_CrtYd if spot[3] == 'bottom' else pcbnew.F_CrtYd
        box = footprint.GetCourtyard(layer).BBox()
        if box.GetWidth() == 0:
            continue
        real = (box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6)
        guess = layout.courtyard(ref)
        error = max(abs(a - b) for a, b in zip(real, (guess.min_x, guess.min_y, guess.max_x, guess.max_y)))
        if error > 0.05:
            worst.append((ref, round(error, 2)))
    return worst


def place(in_path, out_path):
    board = pcbnew.LoadBoard(in_path)
    parts, nets = load_netlist()
    removed, added = sync_parts(board, parts, nets)
    print('removed:', ' '.join(sorted(removed)), '| added:', ' '.join(added))
    strip_board(board)
    draw_outline(board)
    holes = [fp for fp in board.GetFootprints() if not fp.GetReference()]
    for footprint, (hole_x, hole_y) in zip(holes, HOLES):
        footprint.SetPosition(pcbnew.VECTOR2I(MM(hole_x), MM(hole_y)))
    layout = Layout(board)
    print('isolated parts:', ' '.join(sorted(layout.iso_refs)))
    for ref, spot in ANCHORS.items():
        layout.put(ref, spot)  # U1 sits over the notch on purpose
    for ref, edge, side, start, overhang in EDGE_PLAN:
        spot = layout.place_on_edge(ref, edge, side, start, overhang)
        if spot is None:
            print('NO ROOM on the', edge, 'edge for', ref)
            continue
        box = layout.courtyard(ref)
        print(f'{ref:4} {edge:6} {side:6} rot {spot[2]:3} courtyard x {box.min_x:6.2f}..{box.max_x:6.2f} y {box.min_y:6.2f}..{box.max_y:6.2f}')
    for ref, spot in PREFERRED.items():
        free = layout.nudge(ref, spot, [spot[3]])
        if free is None:
            print('NO ROOM for', ref)
            continue
        if math.hypot(free[0] - spot[0], free[1] - spot[1]) > 1.0:
            print(f'{ref} moved {free[0] - spot[0]:+.2f}, {free[1] - spot[1]:+.2f}')
        layout.put(ref, free)
        if ref == 'U18':
            reserve_current_path(layout)
    place_leds(layout)
    auto = sorted(set(layout.footprints) - set(layout.spots) - {plan[0] for plan in EDGE_PLAN})
    place_small_parts(layout, parts, nets, set(auto))
    unplaced = sorted(set(layout.footprints) - set(layout.spots))
    # park the rest off the board until their placement step exists
    for index, ref in enumerate(unplaced):
        layout.footprints[ref].SetPosition(pcbnew.VECTOR2I(MM(110 + (index % 10) * 6), MM(5 + (index // 10) * 4)))
    apply_spots(layout)
    add_led_labels(board, layout)
    print('prediction errors:', check_prediction(layout))
    print('unplaced:', len(unplaced))
    pcbnew.SaveBoard(out_path, board)


# ─── routing ───

FREEROUTING_JAR = Path('/Applications/freerouting.app/Contents/app/freerouting-executable.jar')
JAVA_CANDIDATES = [
    Path('/Library/Java/JavaVirtualMachines/temurin-25.jdk/Contents/Home/bin/java'),
    Path('/opt/homebrew/opt/openjdk@17/bin/java'),
]
# ISO island outline (the union of ISO_RECTS)
ISO_OUTLINE = [
    (0.0, 24.3), (14.0, 24.3), (14.0, 28.25), (28.5, 28.25), (28.5, 45.8),
    (18.0, 45.8), (18.0, HEIGHT), (0.0, HEIGHT),
]
# same-net pad chains on U21 (LT3097, 0.5 mm pitch) joined by F.Cu stubs
PAD_BRIDGES = {'U21': (('1', '2', '3'), ('6', '7', '8'), ('7', '24'), ('14', '15', '16'),
                       ('20', '21', '22'), ('19', '23'))}
# 0.5 mm pitch ground pads and small exposed pads that get a locked via-in-pad
GROUND_VIA_PADS = {'U23': {'7'}, 'U4': {'11'}, 'U21': {'5', '11', '13', '19', '23'},
                   'U20': {'21'}, 'U25': {'21'}, 'U11': {'9'}}
SIGNAL_VIA_PADS = {}
CURRENT_WIDTH = 2.0


def polygon(points):
    shape = pcbnew.SHAPE_POLY_SET()
    shape.NewOutline()
    for point_x, point_y in points:
        shape.Append(MM(point_x), MM(point_y))
    return shape


def iso_band():
    """The 1.5 mm moat round the ISO island, clipped to the board."""
    band = polygon(ISO_OUTLINE)
    band.Inflate(MM(ISO_BAND), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, MM(0.01))
    band.BooleanSubtract(polygon(ISO_OUTLINE))
    band.BooleanIntersection(polygon([(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT)]))
    return band


def add_zone(board, net, layer, shape, priority):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(board.FindNet(net))
    zone.SetAssignedPriority(priority)
    zone.SetLocalClearance(MM(0.3))
    zone.SetMinThickness(MM(0.2))
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if net in GROUND_NETS else pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(MM(0.3))
    zone.SetThermalReliefSpokeWidth(MM(0.4))
    zone.Outline().Append(shape)
    board.Add(zone)


def add_track(board, net, layer, points, width):
    for start, end in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetLayer(layer)
        track.SetWidth(MM(width))
        track.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        track.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        track.SetNet(board.FindNet(net))
        track.SetLocked(True)
        board.Add(track)


def add_via(board, net, x, y, diameter, drill):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    via.SetWidth(MM(diameter))
    via.SetDrill(MM(drill))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetNet(board.FindNet(net))
    via.SetLocked(True)
    board.Add(via)


def pad_of(board, ref, number):
    for pad in board.FindFootprintByReference(ref).Pads():
        if pad.GetNumber() == number:
            return pad
    raise KeyError((ref, number))


def pad_xy(board, ref, number):
    position = pad_of(board, ref, number).GetPosition()
    return position.x / 1e6, position.y / 1e6


def pre_route(board):
    """Locked copper the router must not choose: U21 pad bridges, fine-pitch
    vias-in-pad and the amplifier current path through U18."""
    for ref, chains in PAD_BRIDGES.items():
        for chain in chains:
            for first, second in zip(chain, chain[1:]):
                net = pad_of(board, ref, first).GetNetname()
                if net != pad_of(board, ref, second).GetNetname():
                    print('bridge skipped, nets differ:', ref, first, second)
                    continue
                add_track(board, net, pcbnew.F_Cu if not board.FindFootprintByReference(ref).IsFlipped() else pcbnew.B_Cu,
                          [pad_xy(board, ref, first), pad_xy(board, ref, second)], 0.2)
    for table, ground in ((GROUND_VIA_PADS, True), (SIGNAL_VIA_PADS, False)):
        for ref, pads in table.items():
            for number in sorted(pads):
                try:
                    net = pad_of(board, ref, number).GetNetname()
                except KeyError:
                    print('via-in-pad skipped,', ref, 'has no pad', number)
                    continue
                if (net in GROUND_NETS) != ground:
                    print('via-in-pad skipped,', ref, number, 'is on', net)
                    continue
                via_x, via_y = pad_xy(board, ref, number)
                blocker = other_side_pad(board, ref, via_x, via_y, 0.225 + 0.15)
                if blocker:
                    print('via-in-pad skipped,', ref, number, 'is over', blocker)
                    continue
                add_via(board, net, via_x, via_y, 0.45, 0.2)
    pre_route_current(board)


def other_side_pad(board, ref, x, y, reach):
    """Name of a pad on the other side of the board within `reach` of (x, y)."""
    flipped = board.FindFootprintByReference(ref).IsFlipped()
    for footprint in board.GetFootprints():
        if footprint.IsFlipped() == flipped and footprint.GetReference() != ref:
            continue
        for pad in footprint.Pads():
            if footprint.GetReference() == ref and pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
                continue
            box = pad.GetBoundingBox()
            if (box.GetLeft() / 1e6 - reach <= x <= box.GetRight() / 1e6 + reach
                    and box.GetTop() / 1e6 - reach <= y <= box.GetBottom() / 1e6 + reach):
                return f'{footprint.GetReference() or "hole"} pad {pad.GetNumber()}'
    return None


def pre_route_current(board):
    """J12 pin 1 -> U18 pins 5-8 (IP-) on F.Cu; J11 pin 1 -> U18 pins 1-4 (IP+)
    on B.Cu with via groups at both ends, so the two never cross."""
    minus, plus = 'Net-(J12-Pin_1)', 'Net-(J11-Pin_1)'
    column_x = pad_xy(board, 'U18', '1')[0]
    top = [pad_xy(board, 'U18', pin)[1] for pin in '1234']
    bottom = [pad_xy(board, 'U18', pin)[1] for pin in '5678']
    j12_x, j12_y = pad_xy(board, 'J12', '1')
    j11_x, j11_y = pad_xy(board, 'J11', '1')
    j11_top = j11_y - pad_of(board, 'J11', '1').GetSizeY() / 2e6
    half = CURRENT_WIDTH / 2
    # IP-: along pins 5-8, left to x = 13, up past J12's ear, into pin 1
    lane_x = 13.0
    add_track(board, minus, pcbnew.F_Cu, [(column_x, bottom[0] + 0.6), (column_x, bottom[-1] - 0.25)], CURRENT_WIDTH)
    middle = (bottom[0] + bottom[-1]) / 2
    add_track(board, minus, pcbnew.F_Cu, [(column_x, middle), (lane_x, middle), (lane_x, j12_y + 1.07),
                                          (j12_x, j12_y + 0.45), (j12_x, j12_y)], CURRENT_WIDTH)
    # IP+: along pins 1-4, a bar to the left with four vias, B.Cu down to J11
    add_track(board, plus, pcbnew.F_Cu, [(column_x, top[0] + 0.25), (column_x, top[-1] - 0.6)], CURRENT_WIDTH)
    via_x = column_x - 1.85
    add_track(board, plus, pcbnew.F_Cu, [(via_x + 0.3, top[0] + 0.25), (via_x + 0.3, top[-1] - 0.6)], 1.2)
    via_ys = [top[0] + 0.3 + index * (top[-1] - top[0] - 0.6) / 3 for index in range(4)]
    for via_y in via_ys:
        add_via(board, plus, via_x, via_y, 0.6, 0.3)
    drop = j11_top + 1.0 - (via_x - j11_x)
    add_track(board, plus, pcbnew.B_Cu, [(via_x, via_ys[0]), (via_x, drop), (j11_x, j11_top + 1.0)], CURRENT_WIDTH)
    for offset_x in (-0.5, 0.5):
        for offset_y in (1.0, 2.0):
            add_via(board, plus, j11_x + offset_x, j11_top + offset_y, 0.6, 0.3)
    add_track(board, plus, pcbnew.B_Cu, [(j11_x, j11_top + 1.0), (j11_x, j11_top + 2.0)], CURRENT_WIDTH)


def run_freerouting(board, work_dir, rounds):
    import gen_pcb

    java = next(str(path) for path in JAVA_CANDIDATES if path.exists())
    for round_index in range(rounds):
        dsn = work_dir / f'board{round_index}.dsn'
        ses = work_dir / f'board{round_index}.ses'
        if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
            raise RuntimeError('DSN export failed')
        # In1 is the GND / ISO_GND plane: no signal routing on it
        dsn.write_text(dsn.read_text().replace('(layer In1.Cu\n      (type signal)', '(layer In1.Cu\n      (type power)'))
        subprocess.run(
            [java, '-jar', str(FREEROUTING_JAR), '-de', str(dsn), '-do', str(ses), '-mp', '20', '-mt', '0'],
            check=False,
            env=gen_pcb.freerouting_env(),
            timeout=gen_pcb.FREEROUTING_TIMEOUT,
        )
        if not ses.exists() or ses.stat().st_size == 0:
            raise RuntimeError('Freerouting produced no session file')
        if not pcbnew.ImportSpecctraSES(board, str(ses)):
            raise RuntimeError('SES import failed')


def board_shape():
    return polygon([(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT)])


def route(in_path, out_path, rounds):
    board = pcbnew.LoadBoard(in_path)
    for track in list(board.GetTracks()):
        KEEP.append(track)
        board.Remove(track)
    for zone in list(board.Zones()):
        if not zone.GetIsRuleArea() or zone.GetZoneName() == 'ISO moat':
            KEEP.append(zone)
            board.Remove(zone)
    moat = pcbnew.ZONE(board)
    moat.SetIsRuleArea(True)
    moat.SetDoNotAllowZoneFills(True)
    moat.SetDoNotAllowTracks(True)
    moat.SetDoNotAllowVias(True)
    moat.SetDoNotAllowPads(False)
    moat.SetDoNotAllowFootprints(False)
    moat.SetLayerSet(pcbnew.LSET.AllCuMask())
    moat.SetZoneName('ISO moat')
    moat.Outline().Append(iso_band())
    board.Add(moat)
    add_zone(board, 'GND', pcbnew.In1_Cu, board_shape(), 1)
    add_zone(board, 'ISO_GND', pcbnew.In1_Cu, polygon(ISO_OUTLINE), 2)
    pre_route(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    work_dir = Path(out_path).with_suffix('.route')
    work_dir.mkdir(exist_ok=True)
    pcbnew.SaveBoard(str(work_dir / 'pre_route.kicad_pcb'), board)
    run_freerouting(board, work_dir, rounds)
    add_pours(board)
    pcbnew.SaveBoard(out_path, board)


def reroute(in_path, out_path, drc_path):
    """One more Freerouting round on a finished board: keeps its tracks and vias,
    drops copper that DRC flagged as an error and the pours (the In1 planes stay),
    then pours again. Run finish and the repair tools afterwards."""
    import json
    board = pcbnew.LoadBoard(in_path)
    flagged = {item['uuid'] for violation in json.loads(Path(drc_path).read_text())['violations']
               if violation['severity'] == 'error' for item in violation['items']}
    for track in list(board.GetTracks()):
        if track.m_Uuid.AsString() in flagged:
            KEEP.append(track)
            board.Remove(track)
    for zone in list(board.Zones()):
        if zone.GetIsRuleArea() or zone.GetLayerSet().Contains(pcbnew.In1_Cu):
            continue
        KEEP.append(zone)
        board.Remove(zone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    work_dir = Path(out_path).with_suffix('.route')
    work_dir.mkdir(exist_ok=True)
    run_freerouting(board, work_dir, 1)
    add_pours(board)
    pcbnew.SaveBoard(out_path, board)


def add_pours(board):
    """Outer GND pours, In2 +3V3, ISO_GND on every layer of the island."""
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        add_zone(board, 'GND', layer, board_shape(), 1)
    add_zone(board, '+3V3', pcbnew.In2_Cu, board_shape(), 1)
    for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        add_zone(board, 'ISO_GND', layer, polygon(ISO_OUTLINE), 2)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def finish(path):
    """GND / ISO_GND stitching, pour-island and escape vias (gen_pcb's finish
    steps, pointed at this outline), then refill."""
    import gen_pcb

    gen_pcb.BOARD_WIDTH, gen_pcb.BOARD_HEIGHT, gen_pcb.HOLES = WIDTH, HEIGHT, HOLES
    builder = gen_pcb.PcbBuilder()
    builder.board = pcbnew.LoadBoard(path)
    for zone in builder.board.Zones():
        if not zone.GetIsRuleArea() and zone.GetNetname() in GROUND_NETS:
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    # stitch_ground picks ISO_GND inside ISO_REGION: run it once for each net
    gen_pcb.ISO_REGION = Rect(-1.0, -1.0, -1.0, -1.0)
    stitched = builder.stitch_ground()
    gen_pcb.ISO_REGION = Rect(0.0, 0.0, WIDTH, HEIGHT)
    stitched += builder.stitch_ground()
    print('stitching vias:', stitched)
    print('island vias:', builder.connect_pour_islands(), builder.connect_pour_islands(0.2, 0.5))
    print('escape vias:', builder.escape_ground_pads())
    builder.fill_zones()
    pcbnew.SaveBoard(path, builder.board)


def stamp_board_id(path, x, y):
    """Board ID block on the back silk: name and short commit, the rev 3
    font (1 x 0.9 mm, 0.15 mm stroke, mirrored), replacing any earlier one."""
    board = pcbnew.LoadBoard(path)
    for drawing in list(board.GetDrawings()):
        if drawing.Type() == pcbnew.PCB_TEXT_T and drawing.GetLayer() == pcbnew.B_SilkS:
            if drawing.GetText() == 'cryocooler' or drawing.GetText().startswith('BETA rev'):
                KEEP.append(drawing)
                board.Remove(drawing)
    for index, line in enumerate(board_id_lines()):
        text = pcbnew.PCB_TEXT(board)
        text.SetText(line)
        text.SetLayer(pcbnew.B_SilkS)
        text.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(0.9)))
        text.SetTextThickness(MM(0.15))
        text.SetMirrored(True)
        text.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y + index * 1.44)))
        board.Add(text)
    pcbnew.SaveBoard(path, board)


# ─── part labels: small reference text beside each part ───

PART_LABEL_HEIGHT = 0.8  # JLCPCB high-precision silkscreen minimum
PART_LABEL_WIDTH = 0.7
PART_LABEL_STROKE = 0.1
PART_LABEL_GROUP = 'part labels'
SILK_GAP = 0.1  # label to other silk, pads and part bodies
PART_GAPS = (0.25, 0.5, 0.75, 1.0)  # label to its own part
SHIFTS = (0.0, -0.5, 0.5, -1.0, 1.0, -1.5, 1.5)  # along the part's side
LABEL_FUNCTIONS = {
    'J1': 'USB', 'J2': '12V IN', 'J3': 'FAN', 'J4': 'PUMP', 'J5': 'FLOW', 'J6': 'NTC',
    'J7': 'BTN', 'J8': 'AMP REM', 'J9': 'SINE OUT', 'J10': 'RTD', 'J11': 'AMP OUT',
    'J12': 'CRYO', 'J13': 'RELAY', 'J14': 'IMU', 'J15': 'DISPLAY',
    'JP1': 'SG 3V3', 'JP2': 'PS15', 'JP3': 'ISO5', 'JP4': 'COOL', 'JP5': 'CH',
    'SW1': 'RESET', 'SW2': 'BOOT', 'SW3': 'POWER',
}
TEST_POINT_NAMES = {
    'TP9': '+15V', 'TP10': '-15V', 'TP11': '+16V5', 'TP12': '-16V5', 'TP14': 'GND',
    'TP37': 'DDS', 'TP38': 'SINE', 'TP47': 'U5 OUT',
}


def box_rect(box):
    return Rect(box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6)


def label_texts(ref):
    """Texts to try for a part, longest first."""
    if ref in TEST_POINT_NAMES:
        return [TEST_POINT_NAMES[ref]]
    if ref in LABEL_FUNCTIONS:
        return [f'{ref} {LABEL_FUNCTIONS[ref]}', LABEL_FUNCTIONS[ref], ref]
    return [ref]


def body_rect(footprint, fab_layer, silk_layer):
    """Pads, fab outline and silk outline: the part as it reads on the board."""
    rects = [box_rect(pad.GetBoundingBox()) for pad in footprint.Pads()]
    rects += [box_rect(item.GetBoundingBox()) for item in footprint.GraphicalItems()
              if item.GetLayer() in (fab_layer, silk_layer) and not isinstance(item, pcbnew.PCB_TEXT)]
    return Rect(min(r.min_x for r in rects), min(r.min_y for r in rects),
                max(r.max_x for r in rects), max(r.max_y for r in rects))


def rect_distance(first, second):
    gap_x = max(first.min_x - second.max_x, second.min_x - first.max_x, 0.0)
    gap_y = max(first.min_y - second.max_y, second.min_y - first.max_y, 0.0)
    return math.hypot(gap_x, gap_y)


class SilkMap:
    """Obstacles for one silk side, bucketed on a 2 mm grid."""

    def __init__(self):
        self.grid = {}

    def add(self, rect, owner=None):
        for cell in cells(rect):
            self.grid.setdefault(cell, []).append((rect, owner))

    def blocked(self, rect, own_ref):
        for cell in cells(rect):
            for other, owner in self.grid.get(cell, ()):
                if owner != own_ref and other.overlaps(rect):
                    return True
        return False


def outline_problem(rect):
    if rect.min_x < EDGE_GAP or rect.min_y < EDGE_GAP or rect.max_x > WIDTH - EDGE_GAP or rect.max_y > HEIGHT - EDGE_GAP:
        return True
    if rect.overlaps(NOTCH.inflated(EDGE_GAP)) or any(rect.overlaps(keepout) for keepout in ANTENNA_KEEPOUTS):
        return True
    corners = [Rect(0, 0, CORNER_SQUARE, CORNER_SQUARE), Rect(WIDTH - CORNER_SQUARE, 0, WIDTH, CORNER_SQUARE),
               Rect(0, HEIGHT - CORNER_SQUARE, CORNER_SQUARE, HEIGHT),
               Rect(WIDTH - CORNER_SQUARE, HEIGHT - CORNER_SQUARE, WIDTH, HEIGHT)]
    if any(rect.overlaps(corner) for corner in corners):
        return True
    return any(circle_hits(rect, hole_x, hole_y, RING_RADIUS + EDGE_GAP) for hole_x, hole_y in HOLES)


def new_label(board, text, layer, x, y, vertical):
    label = pcbnew.PCB_TEXT(board)
    label.SetText(text)
    label.SetLayer(layer)
    label.SetTextSize(pcbnew.VECTOR2I(MM(PART_LABEL_WIDTH), MM(PART_LABEL_HEIGHT)))
    label.SetTextThickness(MM(PART_LABEL_STROKE))
    label.SetMirrored(layer == pcbnew.B_SilkS)
    label.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    label.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    if vertical:
        label.SetTextAngle(pcbnew.EDA_ANGLE(90.0, pcbnew.DEGREES_T))
    label.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    return label


def label_candidates(body, width, height):
    """(x, y, vertical, gap) in rule order: above / below, beside, then vertical beside."""
    centre_x, centre_y = (body.min_x + body.max_x) / 2, (body.min_y + body.max_y) / 2
    for gap in PART_GAPS:
        for shift in SHIFTS:
            yield centre_x + shift, body.min_y - gap - height / 2, False, gap
            yield centre_x + shift, body.max_y + gap + height / 2, False, gap
    for gap in PART_GAPS:
        for shift in SHIFTS[:5]:
            yield body.min_x - gap - width / 2, centre_y + shift, False, gap
            yield body.max_x + gap + width / 2, centre_y + shift, False, gap
    for gap in PART_GAPS:
        for shift in SHIFTS:
            yield body.min_x - gap - height / 2, centre_y + shift, True, gap
            yield body.max_x + gap + height / 2, centre_y + shift, True, gap


def under_body_candidates(body):
    """Horizontal spots under a through-hole part, seen from its far side, centre first."""
    centre_x, centre_y = (body.min_x + body.max_x) / 2, (body.min_y + body.max_y) / 2
    spots = [(body.min_x + column * 0.25, body.min_y + row * 0.25)
             for column in range(int((body.max_x - body.min_x) / 0.25) + 1)
             for row in range(int((body.max_y - body.min_y) / 0.25) + 1)]
    spots.sort(key=lambda spot: math.hypot(spot[0] - centre_x, spot[1] - centre_y))
    for x, y in spots:
        yield x, y, False, 0.0


def closer_to_other(rect, ref, side, bodies):
    """True when another part on this side is as near the label as its own part.
    A test point's label names a net, so only other test points count against it."""
    own = rect_distance(rect, bodies[ref][1])
    if ref.startswith('TP'):
        bodies = {other: entry for other, entry in bodies.items() if other.startswith('TP')}
    reach = rect.inflated(own + 0.05)
    return any(other_side == side and other_ref != ref and reach.overlaps(other_body)
               and rect_distance(rect, other_body) <= own + 0.05
               for other_ref, (other_side, other_body) in bodies.items())


def add_part_labels(path):
    """Labels every part it can (reference, or function for connectors, switches
    and test points) in 0.8 mm silk on the part's own side, replacing earlier
    labels; LEDs keep their LED_LABELS. Silk may cross vias (filled and capped)."""
    board = pcbnew.LoadBoard(path)
    for group in list(board.Groups()):
        if group.GetName() == PART_LABEL_GROUP:
            for item in list(group.GetItems()):
                KEEP.append(item)
                board.Remove(item)
            KEEP.append(group)
            board.Remove(group)
    sides = {
        'F': (pcbnew.F_SilkS, pcbnew.F_Cu, pcbnew.F_Fab, SilkMap()),
        'B': (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Fab, SilkMap()),
    }
    footprints = list(board.GetFootprints())
    bodies = {}
    for footprint in footprints:
        ref = footprint.GetReference()
        side = 'B' if footprint.IsFlipped() else 'F'
        silk, copper, fab, silk_map = sides[side]
        bodies[ref] = (side, body_rect(footprint, fab, silk))
        silk_map.add(bodies[ref][1].inflated(SILK_GAP), ref)
        for key, (other_silk, other_copper, _fab, other_map) in sides.items():
            for pad in footprint.Pads():
                if pad.IsOnLayer(other_copper):
                    other_map.add(box_rect(pad.GetBoundingBox()).inflated(SILK_GAP))
            for item in footprint.GraphicalItems():
                if item.GetLayer() == other_silk:
                    other_map.add(box_rect(item.GetBoundingBox()).inflated(SILK_GAP))
            for field in (footprint.Reference(), footprint.Value()):
                if field.IsVisible() and field.GetLayer() == other_silk:
                    other_map.add(box_rect(field.GetBoundingBox()).inflated(SILK_GAP))
    for drawing in board.GetDrawings():
        for silk, _copper, _fab, silk_map in sides.values():
            if drawing.GetLayer() == silk:
                silk_map.add(box_rect(drawing.GetBoundingBox()).inflated(SILK_GAP))
    group = pcbnew.PCB_GROUP(board)
    group.SetName(PART_LABEL_GROUP)
    board.Add(group)
    placed, missed = 0, []
    def priority(footprint):  # named parts first, then small parts (they have the fewest spots)
        ref = footprint.GetReference()
        body = bodies[ref][1]
        tier = 0 if ref in TEST_POINT_NAMES or ref in LABEL_FUNCTIONS else 1 if ref.startswith('U') else 2
        return tier, (body.max_x - body.min_x) * (body.max_y - body.min_y)

    order = sorted(footprints, key=priority)
    for footprint in order:
        ref = footprint.GetReference()
        if not ref or ref.startswith(('#', 'H', 'MH', 'LOGO')) or ref in LED_LABELS:
            continue
        own_side, body = bodies[ref]
        # A through-hole connector reads from both sides: try the far side's silk last.
        label_sides = [own_side]
        if ref.startswith('J') and any(pad.HasHole() for pad in footprint.Pads()):
            label_sides.append('F' if own_side == 'B' else 'B')
        if not place_label(board, group, ref, body, label_sides, sides, bodies):
            missed.append(ref)
            continue
        placed += 1
    pcbnew.SaveBoard(path, board)
    print(f'part labels: {placed} placed, {len(missed)} without room:', ' '.join(sorted(missed)))


def place_label(board, group, ref, body, label_sides, sides, bodies):
    """First free spot for the part's label, by text then side then rule order."""
    for text in label_texts(ref):
        for side in label_sides:
            silk, _copper, _fab, silk_map = sides[side]
            probe = new_label(board, text, silk, 0, 0, False)
            size = box_rect(probe.GetBoundingBox())
            width, height = size.max_x - size.min_x, size.max_y - size.min_y
            far_side = side != label_sides[0]
            candidates = under_body_candidates(body) if far_side else label_candidates(body, width, height)
            for x, y, vertical, _gap in candidates:
                label = new_label(board, text, silk, x, y, vertical)
                rect = box_rect(label.GetBoundingBox())
                if outline_problem(rect) or silk_map.blocked(rect, ref):
                    continue
                if closer_to_other(rect, ref, side, bodies):
                    continue
                board.Add(label)
                group.AddItem(label)
                silk_map.add(rect.inflated(SILK_GAP))
                return True
    return False


def main():
    mode = sys.argv[1]
    if mode == 'place':
        place(sys.argv[2], sys.argv[3])
        return 0
    if mode == 'preroute':
        route(sys.argv[2], sys.argv[3], 0)
        return 0
    if mode == 'boardid':
        stamp_board_id(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
        return 0
    if mode == 'labels':
        add_part_labels(sys.argv[2])
        return 0
    if mode == 'finish':
        finish(sys.argv[2])
        return 0
    if mode == 'reroute':
        reroute(sys.argv[2], sys.argv[3], sys.argv[4])
        return 0
    if mode == 'route':
        route(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 2)
        return 0
    raise SystemExit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
