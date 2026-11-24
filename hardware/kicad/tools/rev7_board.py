"""Places and routes rev 7 on the Phoenix UCS 195-145 outline (drawing 2203442: 170 x 120 mm,
four 3.2 mm holes on 161.6 x 111.6 mm; antenna notch in the top edge).

The outline, the placer and the pre-route helpers are rev5_board.py's. Rev 7 against
rev 5: the schematic is rev 6's (in-board JST headers J15, J34, J35, J40-J42), and
two directives from the user: the power button SW3 is the topmost part on the right
wall, and the 12 V input J2 is the bottommost part on the left wall.

The board has no fixed section rectangles and draws no section outlines. After the wall
connectors, U1 and the 12 V and amplifier-current blocks are down, `plan()` places every
other IC (with the small parts that belong to it) so that pad density stays under a
target in every 5 mm cell while connected parts stay close; the rev 5 placer then puts
the small parts beside their ICs.

Usage (KiCad's python):
    rev7_board.py place in.kicad_pcb out.kicad_pcb
    rev7_board.py rules                      (net class widths and vias in cryocooler.kicad_pro)
    rev7_board.py preroute in out            (planes, ties, locked copper; no autorouter)
    rev7_board.py route in out [rounds]      (preroute, then Freerouting, then the pours)
    rev7_board.py reroute in out drc.json    (one more Freerouting round on a routed board)
    rev7_board.py finish board               (pours, stitching, refill)
"""
import json
import math
import os
import random
import re
import sys
from pathlib import Path

import pcbnew

import rev5_board as rev5
import ucs125_board as base
from pcbplace import Rect

# rev 5's outline, 50 mm wider and 20 mm taller: the left wall, notch and antenna are unchanged
base.WIDTH, base.HEIGHT = 170.0, 120.0
base.HOLES = [(4.2, 4.2), (165.8, 4.2), (4.2, 115.8), (165.8, 115.8)]

# Wall connectors: (ref, edge, side, start along the edge, overhang past it).
# Left, top to bottom: IMU and PT1000 back to back, the isolated cryocooler output
# and amplifier input, then 12 V in. Right, top to bottom: power button, amplifier
# REM and signal, precision ports, pressure ports (pairs back to back). Top: USB.
# Bottom: 12 V in's neighbours (flow, NTC, relay, fan, pump), then I/O 1-4 as two
# back-to-back pairs.
IO_PAIR_START = 105.0
IO_PAIR_PITCH = 25.0
base.EDGE_PLAN = [
    ('J14', 'left', 'top', 7.8, 0.05),
    ('J10', 'left', 'bottom', 7.8, -0.3),
    ('J12', 'left', 'top', 21.0, 3.29),
    ('J11', 'left', 'top', 60.0, 3.29),
    ('J2', 'left', 'top', 100.7, 0.3),
    ('J1', 'top', 'top', 53.5, 0.55),
    ('J5', 'bottom', 'top', 22.2, 0.08),
    ('J6', 'bottom', 'bottom', 22.2, 0.3),
    ('J13', 'bottom', 'bottom', 30.6, 0.3),
    ('J3', 'bottom', 'top', 35.8, 0.24),
    ('J4', 'bottom', 'bottom', 35.8, 0.24),
    *[(f'J{35 + n}', 'bottom', 'top' if n % 2 else 'bottom',
       IO_PAIR_START + IO_PAIR_PITCH * ((n - 1) // 2), 0.24) for n in range(1, 5)],
    ('SW3', 'right', 'top', 7.8, 3.0),
    ('J9', 'right', 'top', 21.4, 0.29),
    ('J8', 'right', 'top', 30.6, 0.29),
    ('J30', 'right', 'top', 41.5, 0.24),
    ('J31', 'right', 'bottom', 41.5, 0.24),
    ('J32', 'right', 'top', 66.0, 0.24),
    ('J33', 'right', 'bottom', 66.0, 0.24),
]
# placement_view.py colours parts by sheet instead of drawing section boxes
PLACEMENT_VIEW_BY_SHEET = True

# in-board headers: placed like any part, with its spacing
INBOARD_CONNECTORS = {'J15', 'J34', 'J35', 'J40', 'J41', 'J42'}

# Isolated island: J12 pins 1 and 2 (pin 3 is board ground, above them), J11, U18
# and U17's isolated half. U17 straddles x = 30.
base.ISO_RECTS = [Rect(0.0, 37.2, 30.0, 71.0)]
# the outline of the pours and the moat is ISO_RECTS: it ends at x = 30 where U17 straddles it,
# so U17's logic-side pads (x 33.6-35.7) stay outside the moat, and at y = 71 where the
# placement already keeps other pads ISO_BAND away
base.ISO_OUTLINE = [(0.0, 37.2), (30.0, 37.2), (30.0, 71.0), (0.0, 71.0)]

# The 12 V input block sits in one row above the fan and pump headers (J2 -> F1 -> Q1 ->
# shunt, corridors below) and U18 sits on the back between J11 and J12, turned half a turn so
# its IP- pins (5-8) face J12 pin 1 and its IP+ pins (1-4) face J11 pin 1. The fan and pump
# fuses F3 and F4 stand on the back between the 12 V bar and the J3 / J4 pads (pad 2 on +12V
# up, pad 1 down). These stay where they are; everything else is planned. ref -> (x, y, rotation, side)
PINNED = {
    'F1': (26.0, 98.5, 0, 'top'),
    'Q1': (34.5, 98.5, 270, 'top'),
    'R78': (42.0, 98.5, 180, 'top'),
    'D1': (36.0, 94.0, 0, 'top'),
    'U11': (33.5, 92.9, 0, 'bottom'),
    'U23': (44.0, 93.0, 0, 'bottom'),
    'U18': (22.0, 55.0, 0, 'bottom'),
    'U17': (30.0, 52.0, 180, 'top'),
    'F3': (42.2, 101.65, 90, 'bottom'),
    'F4': (46.6, 101.65, 90, 'bottom'),
}
# 10 mm tall electrolytics: only the front has the height
base.FRONT_ONLY_REFS = {'C65', 'C66'}
base.SAME_SIDE_OWNERS = {'U15', 'U16', 'U20', 'U21', 'U22'}
rev5.section_rects = lambda layout, parts, ref: None


class Layout(rev5.SectionLayout):
    """rev 5's layout; the in-board connectors keep a normal part gap."""

    def margin(self, ref, side):
        if ref in INBOARD_CONNECTORS:
            return base.Layout.margin(self, ref, side)
        return super().margin(ref, side)

    def problem(self, ref, spot, ignore=()):
        return super().problem(ref, spot, ignore) or self.keep_clear(ref, spot) or self.fanout_problem(ref, spot)

    def fanout_rows(self, ref):
        """Staggered via rows a pin pitch p needs: the vias of one side sit at FANOUT_VIA_PITCH (0.45
        via + 0.15 clearance), so ceil(0.6 / p) rows; 0 for a part with no row of pads."""
        cache = self.__dict__.setdefault('rows_cache', {})
        if ref not in cache:
            centres = [c for pads in self.geometry[ref].pad_centers.values() for c in pads]
            pitches = [math.dist(a, b) for i, a in enumerate(centres) for b in centres[i + 1:]
                       if math.dist(a, b) > 0.05 and (abs(a[0] - b[0]) < 1e-6 or abs(a[1] - b[1]) < 1e-6)]
            cache[ref] = math.ceil(FANOUT_VIA_PITCH / min(pitches) - 1e-9) if pitches else 0
        return cache[ref]

    def fanout_ics(self):
        """ICs with at least 5 pads whose pin pitch needs more than one via row."""
        if not hasattr(self, 'rings'):
            self.rings = {ref for ref, geometry in self.geometry.items()
                          if ref.startswith('U') and len(geometry.pad_centers) >= 5 and self.fanout_rows(ref) > 1}
        return self.rings

    def fanout_ring(self, ref):
        """Width in mm of the ring round a fine-pitch IC that other parts stay out of, so every pin can
        leave on a track to a via: 0.5 mm from the pads, the via rows, and 0.3 mm for the tracks
        (0.15 + 0.15 clearance)."""
        return 0.5 + self.fanout_rows(ref) * FANOUT_VIA_PITCH + 0.3

    def ring_exempt(self, ref):
        """Parts whose place is fixed by a stronger rule: pinned parts, wall connectors, and the
        regulators' hot-loop and bound parts."""
        if not hasattr(self, 'exempt'):
            self.exempt = (set(PINNED) | {item[0] for item in base.EDGE_PLAN} | {item[0] for item in REGULATOR_PARTS}
                           | {ref for pair in BOUND for ref in pair} | {item[1] for item in REGULATOR_PARTS})
        return ref in self.exempt

    def fanout_problem(self, ref, spot):
        """A part may not sit in the fan-out ring of a fine-pitch IC, on either side (the vias go
        through); such an IC keeps the same distance from the other parts."""
        if self.ring_exempt(ref):
            return None
        box = self.courtyard(ref, spot)
        if ref in self.fanout_ics():
            ring = box.inflated(self.fanout_ring(ref))
            if any(other != ref and ring.overlaps(self.courtyard(other, self.spots[other]))
                   for other in self.near(ring) if other in self.spots):
                return 'fan-out'
        for owner in self.fanout_ics():
            if owner != ref and owner in self.spots and box.overlaps(
                    self.courtyard(owner, self.spots[owner]).inflated(self.fanout_ring(owner) - self.decoupling_credit(ref, owner))):
                return 'fan-out'
        return None

    def decoupling_credit(self, ref, owner):
        """A capacitor on a supply pin of `owner` may come DECOUPLING_CREDIT mm closer than the ring: the
        gate wants it within 5 mm of the pin, and a supply pin goes to a plane by a via of its own."""
        target = TARGETS.get(ref)
        if not ref.startswith('C') or target is None or target[1] != owner:
            return 0.0
        pad = next((p for p in self.footprints[owner].Pads() if p.GetNumber() == target[2]), None)
        return DECOUPLING_CREDIT if pad is not None and rev5.is_supply(pad.GetNetname()) else 0.0

    def exposed_pads(self):
        """{IC ref: local rectangle of its exposed pad}: the biggest pad, over 4 mm2 and twice the mean."""
        if not hasattr(self, 'exposed'):
            self.exposed = {}
            for ref, geometry in self.geometry.items():
                areas = [(rect.max_x - rect.min_x) * (rect.max_y - rect.min_y) for rect in geometry.pads]
                if len(areas) > 1 and max(areas) > 4.0 and max(areas) >= 2.0 * sum(areas) / len(areas):
                    self.exposed[ref] = geometry.pads[areas.index(max(areas))]
        return self.exposed

    def keep_clear(self, ref, spot):
        """For the small parts of KEEP_CLEAR_OWNERS: not behind any IC's exposed pad (its thermal vias
        need the room), and, on the other side from the IC they serve, not over the pad they serve
        (its escape would be under the part)."""
        target = TARGETS.get(ref)
        if target is None or target[1] not in KEEP_CLEAR_OWNERS:
            return None
        box = self.courtyard(ref, spot)
        for other, local in self.exposed_pads().items():
            if other in self.spots and self.spots[other][3] != spot[3] and box.overlaps(self.rect(other, local)):
                return 'behind-exposed-pad'
        my_pad, owner, owner_pad = target
        if self.spots[owner][3] != spot[3]:
            mine, theirs = self.pad_position(ref, my_pad, spot), self.pad_position(owner, owner_pad)
            if math.dist(mine, theirs) < STACK_CLEAR:
                return 'over-escape'
        return None


rev5.SectionLayout = Layout
# small parts served by these ICs are kept off the back of an exposed pad and, on the other side,
# STACK_CLEAR mm from the pad they serve (U105's parts moved with it, round 4)
KEEP_CLEAR_OWNERS = {'U101', 'U105'}
STACK_CLEAR = 1.2
DECOUPLING_CREDIT = 1.2
FANOUT_VIA_PITCH = 0.6
TARGETS = {}

# the gate wants every IC power pin within 5 mm of a capacitor
base.EDGE_GAP = 1.0
base.FANOUT_RING = {'top': 0.5, 'bottom': 0.6}
# ─── high-current corridors, reserved before any small part is placed ───
# (name, side, rectangle). Copper goes on the sides listed ('all': every copper layer); no part may sit in them.
CORRIDORS = [
    ('12 V bar', 'bottom', Rect(19.0, 95.0, 48.0, 102.0)),      # 7 mm B.Cu bar, J2 to the shunt
    ('12 V row', 'top', Rect(19.0, 97.0, 48.0, 100.0)),         # F.Cu: F1, Q1, R78 and the tracks between
    ('12 V link', 'both', Rect(17.5, 100.0, 23.5, 109.0)),       # J2 pins 3 and 4 up to the bar
    ('fan stub', 'both', Rect(40.2, 100.0, 42.2, 107.0)),        # shunt to the fan pin 2
    ('pump stub', 'both', Rect(45.8, 100.0, 47.8, 107.0)),       # shunt to the pump pin 2
    ('IP- (J12 pin 1 to U18 5-8)', 'both', Rect(12.0, 46.0, 18.5, 55.5)),
    ('IP+ (J11 pin 1 to U18 1-4)', 'both', Rect(8.0, 55.5, 18.5, 64.5)),
    # amplifier return, J11 pin 2 to J12 pin 2, all four layers: spine along the island edge, two links
    ('ISO_GND spine', 'all', Rect(0.3, 37.2, 6.75, 70.9)),
    ('ISO_GND link J11 pin 2', 'all', Rect(0.3, 66.1, 12.0, 70.9)),
    ('ISO_GND link J12 pin 2', 'all', Rect(0.3, 37.5, 15.4, 43.5)),
]


def reserve_corridors(layout):
    """Keeps auto-placed parts out of the corridors, on the sides that carry copper."""
    for index, (_name, side, rect) in enumerate(CORRIDORS):
        sides = {'top': ('top',), 'bottom': ('bottom',), 'both': ('top', 'bottom'), 'all': ('top', 'bottom')}
        for which in sides[side]:
            name = f'~corridor {index} {which}'
            layout.cache[name] = (which, rect, [], [])
            for cell in base.cells(rect):
                layout.grid.setdefault(cell, set()).add(name)


rev5.reserve_current_paths = reserve_corridors

# ─── density-driven placement ───
TARGET = 0.09       # pads per mm2, both sides together: the plan keeps every 5 mm cell under it
CELL = 5.0
FILL = 0.40         # share of its disk a cluster's courtyards may cover, both sides together
STEP = 3.0          # candidate spacing, mm
PENALTY = 6.0       # mm of wire one pad over a cell's capacity costs
CENTRE_PULL = 0.02  # keeps unconnected clusters from drifting to a corner
UNWEIGHTED = {'GND', 'ISO_GND', '+3V3', '+5V', '+12V', 'VIN', '+5V_OR'}
BIG_NET = 12
ANCHOR = re.compile(r'U\d+$')
# the bulk capacitors stay with the input TVS
BOUND = {('C65', 'D1'): 3.0, ('C66', 'D1'): 3.0, ('U15', 'U16'): 2.0}
# the switching parts of each regulator go beside it, in this order: (part, part it sits beside, dx, dy,
# rotation). The inductor and the output capacitor close the hot loop; the power mux U28 sits by C4.
REGULATOR_PARTS = [('L1', 'U15', 0.0, 5.5, 0), ('C4', 'L1', 0.0, 5.3, 90),
                   ('L4', 'U16', 0.0, 5.0, 0), ('C5', 'L4', 0.0, 5.3, 90),
                   ('U28', 'C4', 3.2, 1.5, 0), ('L2', 'U20', 0.0, -7.0, 0), ('L3', 'U20', 0.0, 7.0, 0)]
BIG_CAPS = {'C65', 'C66'}
PASSES = 6


def is_anchor(ref):
    return (bool(ANCHOR.match(ref)) and ref != 'U28') or ref in INBOARD_CONNECTORS or ref in ('SW1', 'SW2') or ref in BIG_CAPS


class Plan:
    """Clusters (an IC and the small parts that belong to it) with a size, links to the other
    clusters and the fixed parts, and a spot each, chosen so connected clusters are close and no
    5 mm cell takes more pads than TARGET allows."""

    def __init__(self, layout, parts, nets):
        self.layout = layout
        pad_nets = {}
        for net, nodes in nets.items():
            for ref, _pad in nodes:
                pad_nets.setdefault(ref, set()).add(net)
        members = {net: [ref for ref, _pad in nodes if ref in layout.footprints] for net, nodes in nets.items()}
        self.fixed = set(layout.spots)
        iso = layout.iso_refs
        self.nodes = sorted(ref for ref in parts if ref in layout.footprints and ref not in self.fixed
                            and ref not in iso and is_anchor(ref))
        anchors = set(self.nodes) | self.fixed
        owner = {}
        loose = [ref for ref in sorted(parts) if ref in layout.footprints and ref not in anchors and ref not in iso]
        for round_ in range(4):
            for ref in loose:
                if ref in owner:
                    continue
                found = {}
                for net in pad_nets.get(ref, ()):
                    if net in base.GROUND_NETS:
                        continue
                    group = members[net]
                    weight = 1.0 / max(1, len(group) - 1)
                    for other in group:
                        target = other if other in anchors else owner.get(other)
                        if other != ref and target is not None:
                            found[target] = found.get(target, 0.0) + weight
                if found:
                    owner[ref] = max(sorted(found), key=lambda target: found[target])
        size = {}
        for ref in sorted(self.fixed | set(self.nodes)):
            size[ref] = [self.pads(ref), self.area(ref)]
        extra = {ref: [0, 0.0] for ref in self.fixed}
        self.mass = {ref: list(size[ref]) for ref in self.nodes}
        for ref, target in owner.items():
            bucket = self.mass[target] if target in self.mass else extra[target]
            bucket[0] += self.pads(ref)
            bucket[1] += self.area(ref) if target in self.mass else 0.0
        self.extra = extra
        self.radius = {ref: min(14.0, max(2.5, math.sqrt(area / (FILL * math.pi)))) for ref, (_p, area) in self.mass.items()}
        node_of = {ref: ref for ref in anchors}
        node_of.update(owner)
        self.links = {ref: {} for ref in self.nodes}
        for net, group in sorted(members.items()):
            if net in UNWEIGHTED or net in base.GROUND_NETS or net.startswith('unconnected'):
                continue
            found = sorted({node_of[ref] for ref in group if ref in node_of})
            if len(found) < 2:
                continue
            weight = (1.0 if len(found) <= BIG_NET else 0.6) / (len(found) - 1)
            for first in found:
                for second in found:
                    if first != second and first in self.links:
                        self.links[first][second] = self.links[first].get(second, 0.0) + weight
        for (first, second), weight in BOUND.items():
            for one, other in ((first, second), (second, first)):
                if one in self.links:
                    self.links[one][other] = self.links[one].get(other, 0.0) + weight
        self.pos = {}
        for ref in self.fixed:
            box = layout.courtyard(ref)
            self.pos[ref] = ((box.min_x + box.max_x) / 2, (box.min_y + box.max_y) / 2)
        self.build_capacity()

    def pads(self, ref):
        return len(self.layout.geometry[ref].pad_centers)

    def area(self, ref):
        box = self.layout.courtyard(ref, (0.0, 0.0, 0, 'top'))
        return (box.max_x - box.min_x) * (box.max_y - box.min_y)

    def build_capacity(self):
        """Free area and pad capacity of each cell: the board less the fixed parts' courtyards, the
        isolated island and its band, the antenna, the corners and holes, the corridors."""
        layout = self.layout
        rects = [layout.courtyard(ref) for ref in layout.spots]
        rects += [area.inflated(base.ISO_BAND) for area in base.ISO_RECTS]
        rects += base.ANTENNA_KEEPOUTS + [base.NOTCH]
        rects += [rect for _name, _side, rect in CORRIDORS]
        self.columns, self.rows = int(base.WIDTH / CELL), int(base.HEIGHT / CELL)
        self.blocked = {}
        for column in range(int(base.WIDTH)):
            for row in range(int(base.HEIGHT)):
                x, y = column + 0.5, row + 0.5
                edge = x < 1.0 or y < 1.0 or x > base.WIDTH - 1.0 or y > base.HEIGHT - 1.0
                self.blocked[(column, row)] = (
                    edge or any(r.min_x <= x <= r.max_x and r.min_y <= y <= r.max_y for r in rects)
                    or any(math.hypot(x - hx, y - hy) < 3.5 for hx, hy in base.HOLES))
        self.free = {}
        for cell_x in range(self.columns):
            for cell_y in range(self.rows):
                count = sum(not self.blocked[(cell_x * 5 + i, cell_y * 5 + j)] for i in range(5) for j in range(5))
                self.free[(cell_x, cell_y)] = float(count)
        self.capacity = {cell: TARGET * area for cell, area in self.free.items()}
        self.load = {cell: 0.0 for cell in self.free}
        for ref, (pads, _area) in self.extra.items():
            if pads:
                self.spread(self.pos[ref], 10.0, pads, 1.0)

    def cells_near(self, x, y, radius):
        reach = radius + CELL * 0.35
        found = []
        for cell_x in range(max(0, int((x - reach) // CELL)), min(self.columns, int((x + reach) // CELL) + 1)):
            for cell_y in range(max(0, int((y - reach) // CELL)), min(self.rows, int((y + reach) // CELL) + 1)):
                if (cell_x, cell_y) in self.free and self.free[(cell_x, cell_y)] > 0 and math.hypot(
                        (cell_x + 0.5) * CELL - x, (cell_y + 0.5) * CELL - y) <= reach:
                    found.append((cell_x, cell_y))
        return found

    def spread(self, centre, radius, pads, sign):
        cells = self.cells_near(*centre, radius)
        for cell in cells:
            self.load[cell] += sign * pads / len(cells)

    def cost(self, ref, x, y, placed):
        radius = self.radius[ref]
        cells = self.cells_near(x, y, radius)
        wanted = math.pi * radius * radius
        if not cells or sum(self.free[cell] for cell in cells) < 0.85 * min(wanted, 25.0 * len(cells)):
            return None
        deposit = self.mass[ref][0] / len(cells)
        over = 0.0
        for cell in cells:
            before = max(0.0, self.load[cell] - self.capacity[cell])
            over += max(0.0, self.load[cell] + deposit - self.capacity[cell]) - before
        wire = sum(weight * math.hypot(x - self.pos[other][0], y - self.pos[other][1])
                   for other, weight in self.links[ref].items() if other in placed)
        wire += CENTRE_PULL * math.hypot(x - base.WIDTH / 2, y - base.HEIGHT / 2)
        return wire + PENALTY * over

    def best(self, ref, placed):
        best = None
        for x in [STEP * k for k in range(1, int(base.WIDTH / STEP))]:
            for y in [STEP * k for k in range(1, int(base.HEIGHT / STEP))]:
                if self.blocked[(int(x), int(y))]:
                    continue
                value = self.cost(ref, x, y, placed)
                if value is not None and (best is None or value < best[0]):
                    best = (value, (x, y))
        return best[1] if best else (base.WIDTH / 2, base.HEIGHT / 2)

    def solve(self):
        placed = set(self.fixed)
        todo = set(self.nodes)
        while todo:
            pick = max(sorted(todo), key=lambda ref: (sum(w for other, w in self.links[ref].items() if other in placed),
                                                      self.mass[ref][0]))
            self.pos[pick] = self.best(pick, placed)
            self.spread(self.pos[pick], self.radius[pick], self.mass[pick][0], 1.0)
            placed.add(pick)
            todo.discard(pick)
        order = sorted(self.nodes, key=lambda ref: -self.mass[ref][0])
        rng = random.Random(7)
        for _round in range(PASSES):
            rng.shuffle(order)
            for ref in order:
                self.spread(self.pos[ref], self.radius[ref], self.mass[ref][0], -1.0)
                self.pos[ref] = self.best(ref, placed)
                self.spread(self.pos[ref], self.radius[ref], self.mass[ref][0], 1.0)

    def spots(self):
        """(ref, spot) for every cluster, biggest first. A cluster goes on the side its cell has
        less of; tall parts, inductors, switches and headers stay on the front."""
        used = {'top': {}, 'bottom': {}}
        result = []
        for ref in sorted(self.nodes, key=lambda ref: -self.mass[ref][1]):
            x, y = self.pos[ref]
            cell = (int(x // CELL), int(y // CELL))
            front = (ref in base.FRONT_ONLY_REFS or ref.startswith(('L', 'SW', 'J'))
                     or used['top'].get(cell, 0.0) <= used['bottom'].get(cell, 0.0))
            side = 'top' if front else 'bottom'
            used[side][cell] = used[side].get(cell, 0.0) + self.mass[ref][1]
            box = self.layout.courtyard(ref, (0.0, 0.0, 0, side))
            result.append((ref, (x - (box.min_x + box.max_x) / 2, y - (box.min_y + box.max_y) / 2, 0, side)))
        return self.clear_of_exposed_pads(result)

    def has_exposed_pad(self, ref):
        """True for an IC whose biggest SMD pad is over 4 mm2 and twice the mean pad: the ground
        pad that needs thermal vias, which must not have another IC behind it."""
        areas = [pad.GetSizeX() * pad.GetSizeY() / 1e12 for pad in self.layout.footprints[ref].Pads()]
        return len(areas) > 1 and max(areas) > 4.0 and max(areas) >= 2.0 * sum(areas) / len(areas)

    def clear_of_exposed_pads(self, spots):
        """Moves an IC that sits behind the courtyard of an IC with an exposed pad to the nearest
        spot (0.5 mm steps, up to 12 mm) that does not."""
        layout = self.layout
        exposed = [(layout.courtyard(ref, spot), spot[3]) for ref, spot in spots if self.has_exposed_pad(ref)]
        fixed = []
        for ref, spot in spots:
            x, y, angle, side = spot
            if not self.has_exposed_pad(ref):
                def behind(at):
                    mine = layout.courtyard(ref, (*at, angle, side))
                    return (any(box.overlaps(mine) for box, other in exposed if other != side)
                            or (ref in layout.fanout_ics() and any(
                                layout.courtyard(other, spot_of).inflated(layout.fanout_ring(other)).overlaps(mine)
                                for other, spot_of in spots if other in layout.fanout_ics() and other != ref)))
                if behind((x, y)):
                    ring = sorted(((dx * 0.5, dy * 0.5) for dx in range(-24, 25) for dy in range(-24, 25)),
                                  key=lambda step: math.hypot(*step))
                    step = next((step for step in ring if not behind((x + step[0], y + step[1]))), None)
                    if step:
                        print(f'{ref} moved ({step[0]:+.1f}, {step[1]:+.1f}) off the back of an exposed pad')
                        spot = (x + step[0], y + step[1], angle, side)
            fixed.append((ref, spot))
        return fixed


class Preferred:
    """base.PREFERRED for the placer: the pinned parts, then the corridors are reserved, then the
    planned clusters. A generator, so the reservation happens between the two."""

    layout = None
    parts = None
    nets = None

    def items(self):
        yield from PINNED.items()
        reserve_corridors(self.layout)
        plan = Plan(self.layout, self.parts, self.nets)
        plan.solve()
        yield from plan.spots()
        for ref, beside, dx, dy, angle in REGULATOR_PARTS:
            x, y, _angle, side = self.layout.spots[beside]
            yield ref, (x + dx, y + dy, angle, side)


PREFERRED = Preferred()
base.PREFERRED = PREFERRED
place_layout = Layout.__init__


def remember(self, board, parts):
    place_layout(self, board, parts)
    PREFERRED.layout, PREFERRED.parts = self, parts


Layout.__init__ = remember
load_netlist = rev5.load_netlist


def remember_nets():
    parts, nets = load_netlist()
    PREFERRED.nets = nets
    return parts, nets


rev5.load_netlist = remember_nets

sheet_choose_target = rev5.choose_target


def choose_target(layout, ref, parts, nets, pad_nets, auto, load):
    found = pick_target(layout, ref, parts, nets, pad_nets, auto, load)
    if found is not None:
        TARGETS[ref] = found
    return found


def pick_target(layout, ref, parts, nets, pad_nets, auto, load):
    """rev 5's choice, except a decoupling capacitor goes to the IC of its sheet that
    has the fewest capacitors per power pin on that net so far."""
    pads = pad_nets.get(ref, {})
    ground = [number for number, net in pads.items() if net.split('/')[-1] in base.GROUND_NETS]
    supply = [number for number, net in pads.items() if rev5.is_supply(net)]
    if ref.startswith('C') and len(pads) == 2 and len(ground) == 1 and len(supply) == 1:
        net = pads[supply[0]]
        pins = [(other, pad) for other, pad in nets[net] if other.startswith('U') and other in layout.spots
                and parts[other]['sheet'] == parts[ref]['sheet']]
        if any(other not in layout.spots for other, _pad in nets[net]
               if other.startswith('U') and parts[other]['sheet'] == parts[ref]['sheet']) and rev5.STRICT_SHEETS[0]:
            return None  # wait until the sheet's ICs are down, so the capacitors can be shared out
        if pins:
            def caps_per_pin(owner):
                owned = [node for node in pins if node[0] == owner]
                return sum(load.get(node, 0) for node in owned) / len(owned)

            other, pad = min(pins, key=lambda node: (caps_per_pin(node[0]), load.get(node, 0), node))
            return supply[0], other, pad
    return sheet_choose_target(layout, ref, parts, nets, pad_nets, auto, load)


base.choose_target = choose_target

# ─── routing ───


def draw_current_paths(board):
    """The locked 12 V input and amplifier current copper, drawn before the ties so they
    leave it room (rev5's fixed geometry does not fit this placement)."""
    import rev7_current
    rev7_current.draw(board, CORRIDORS)


REMOVED = []               # removed items stay referenced (pcbnew frees them otherwise)
THERMAL_VIA = (0.6, 0.3)   # a 0.3 mm drill counts as one via in board_checks.py
THERMAL_SPACING = 0.8      # centre to centre, mm


def thermal_vias(board):
    """Fills each exposed ground pad with enough 0.6 / 0.3 mm vias to meet board_checks.py
    (the one 0.45 / 0.2 mm via pre-route gives it counts 0.44). A spot is skipped where
    another net's pad, on either side, is within 0.15 mm of the via. Prints each pad
    that stays short and what blocks it."""
    import board_checks as checks

    radius = THERMAL_VIA[0] / 2 + 0.15
    pads = [(f, p) for f in board.GetFootprints() for p in f.Pads()
            if p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu)]
    vias = [v for v in board.GetTracks() if v.GetClass() == 'PCB_VIA']
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if not ref.startswith('U') or len(list(footprint.Pads())) < 2:
            continue
        sized = [(checks.pad_area(p), p) for p in footprint.Pads()]
        area, pad = max(sized, key=lambda item: item[0])
        mean = sum(a for a, _p in sized) / len(sized)
        if (pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNetname() not in ('GND', 'ISO_GND')
                or area <= checks.PAD_MIN_AREA_MM2 or area < checks.PAD_EXPOSED_RATIO * mean):
            continue
        need = checks.required_vias(area)
        box = pad.GetBoundingBox()
        left, right, top, bottom = (value / 1e6 for value in (box.GetLeft(), box.GetRight(), box.GetTop(), box.GetBottom()))
        old = [v for v in vias if pad.HitTest(v.GetPosition())]
        have, chosen, picked = 0.0, [], []
        inset = THERMAL_VIA[0] / 2 + 0.15
        blockers = set()
        spots = []
        for i in range(int((right - left - 2 * inset) / 0.1 + 1e-6) + 1):
            for j in range(int((bottom - top - 2 * inset) / 0.1 + 1e-6) + 1):
                x, y = left + inset + i * 0.1, top + inset + j * 0.1
                near = [(f.GetReference(), q.GetNumber()) for f, q in pads
                        if q is not pad and q.GetNetname() != pad.GetNetname()
                        and (q.GetBoundingBox().GetLeft() / 1e6 - radius <= x <= q.GetBoundingBox().GetRight() / 1e6 + radius)
                        and (q.GetBoundingBox().GetTop() / 1e6 - radius <= y <= q.GetBoundingBox().GetBottom() / 1e6 + radius)]
                if near:
                    blockers.update(f'{r}.{n}' for r, n in near)
                    continue
                spots.append((x, y))
        while have < need - 1e-9 and spots:
            far = lambda spot: min([math.dist(spot, other) for other in chosen] or [99.0])
            centre = ((left + right) / 2, (top + bottom) / 2)
            # the pad's middle first, then the spot farthest from those chosen
            spot = min(spots, key=lambda spot: math.dist(spot, centre)) if not chosen else max(spots, key=far)
            if far(spot) < THERMAL_SPACING:
                break
            chosen.append(spot)
            spots.remove(spot)
            picked.append(spot)
            have += 1.0
        if picked:  # the single 0.45 / 0.2 mm via of pre-route is replaced
            for v in old:
                board.Remove(v)
                vias.remove(v)
                REMOVED.append(v)
            for spot in picked:
                base.add_via(board, pad.GetNetname(), spot[0], spot[1], *THERMAL_VIA)
        else:
            have = sum((v.GetDrillValue() / 1e6 / checks.PAD_REF_DRILL_MM) ** 2 for v in old)
        if have < need - 1e-9:
            print(f'thermal vias short: {ref} pad {pad.GetNumber()} has {have:.1f} of {need:g}; blocked by {sorted(blockers)}')


def rect_gap(point, box):
    return math.hypot(max(box[0] - point.x, point.x - box[2], 0), max(box[1] - point.y, point.y - box[3], 0))


def via_fits(copper, point):
    """A 0.45 mm via here keeps 0.1 mm from other nets' pads (via_in_pad_clearance for 0.2 mm holes) and
    0.15 mm from their tracks and vias."""
    import cs_decoder_finish as ties

    mm = pcbnew.FromMM
    vias, tracks, pads = copper
    return (all(rect_gap(point, box) >= mm(0.325) for box, _layers, _pth in pads)
            and all(math.dist((point.x, point.y), (where.x, where.y)) >= half + mm(0.375) for where, half in vias)
            and all(ties.segment_gap(point, a, b) >= half + mm(0.375) for _layer, a, b, half in tracks))


def path_fits(copper, points, layer):
    """A 0.2 mm track along `points` on `layer` keeps 0.15 mm from other nets' copper there."""
    import cs_decoder_finish as ties

    mm = pcbnew.FromMM
    vias, tracks, pads = copper
    for start, end in zip(points, points[1:]):
        steps = max(1, int(math.hypot(end.x - start.x, end.y - start.y) / mm(0.05)))
        for k in range(steps + 1):
            probe = pcbnew.VECTOR2I(start.x + (end.x - start.x) * k // steps, start.y + (end.y - start.y) * k // steps)
            if any(layer in layers and rect_gap(probe, box) < mm(0.25) for box, layers, _pth in pads):
                return False
            if any(math.dist((probe.x, probe.y), (where.x, where.y)) < half + mm(0.25) for where, half in vias):
                return False
            if any(track_layer == layer and ties.segment_gap(probe, a, b) < half + mm(0.25)
                   for track_layer, a, b, half in tracks):
                return False
    return True


def led_jumpers(board):
    """A four-pad LED (D2, D3, D7, D11, D12) has its two nets on the two diagonals of a 2 x 2 pad grid
    at 0.4 mm pitch, so one net cannot get out without crossing the other. One diagonal pair gets a
    via beside each pad and an In2 track between the two vias, all locked; the router then reaches the
    other pair. Of the four candidates (either diagonal, tracks toward the top or the bottom row) the
    first whose vias and tracks clear all other copper (0.15 mm; 0.1 mm via to pad) is drawn."""
    import cs_decoder_finish as ties

    mm = pcbnew.FromMM
    for footprint in board.GetFootprints():
        pads = [p for p in footprint.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.GetNumber()]
        if footprint.IsFlipped() or len(pads) != 4:
            continue
        xs, ys = sorted({round(p.GetPosition().x / 1e6, 3) for p in pads}), sorted({round(p.GetPosition().y / 1e6, 3) for p in pads})
        if len(xs) != 2 or len(ys) != 2 or abs(xs[1] - xs[0] - 0.4) > 0.01 or abs(ys[1] - ys[0] - 0.4) > 0.01:
            continue
        at = {(round(p.GetPosition().x / 1e6, 3), round(p.GetPosition().y / 1e6, 3)): p for p in pads}
        ref = footprint.GetReference()
        diagonals = [((xs[0], ys[0]), (xs[1], ys[1])), ((xs[1], ys[0]), (xs[0], ys[1]))]
        if any(at[a].GetNetname() != at[b].GetNetname() or not at[a].GetNetname() for a, b in diagonals) \
                or at[diagonals[0][0]].GetNetname() == at[diagonals[1][0]].GetNetname():
            continue
        for first, second in diagonals:
            for down in (False, True):
                sign = 1 if down else -1
                row = (ys[1] if down else ys[0])
                # the pad on the jumper's row leaves outward at 45 degrees, the other along its own row
                near, far = (first, second) if first[1] == row else (second, first)
                out = -1 if near[0] == xs[0] else 1
                via_near = (near[0] + out * 1.075, row + sign * 0.265)
                via_far = (xs[1] + 0.475 if out < 0 else xs[0] - 0.475, row + sign * 0.265)
                net = at[first].GetNetname()
                pts_near = [near, (near[0] + out * 0.265, row + sign * 0.265), via_near]
                pts_far = [far, (via_far[0], far[1]), via_far]
                center = pcbnew.VECTOR2I(mm(near[0]), mm(near[1]))
                copper = ties.nearby_copper(board, center, net, mm(6))
                vec = lambda p: pcbnew.VECTOR2I(mm(p[0]), mm(p[1]))
                if (via_fits(copper, vec(via_near)) and via_fits(copper, vec(via_far))
                        and path_fits(copper, [vec(p) for p in pts_near], pcbnew.F_Cu)
                        and path_fits(copper, [vec(p) for p in pts_far], pcbnew.F_Cu)
                        and path_fits(copper, [vec(via_near), vec(via_far)], pcbnew.In2_Cu)):
                    base.add_track(board, net, pcbnew.F_Cu, pts_near, 0.2)
                    base.add_track(board, net, pcbnew.F_Cu, pts_far, 0.2)
                    base.add_track(board, net, pcbnew.In2_Cu, [via_near, via_far], 0.2)
                    for x, y in (via_near, via_far):
                        base.add_via(board, net, x, y, 0.45, 0.2)
                    print(f'{ref} jumper: {net} via ({via_near[0]:.2f}, {via_near[1]:.2f}) to ({via_far[0]:.2f}, {via_far[1]:.2f})')
                    break
            else:
                continue
            break
        else:
            print(f'{ref} jumper: no candidate clears the copper around it')


def tie_plane_pads(board):
    """The locked current copper, then rev 5's plane ties, kept on their own side of the
    isolation barrier: an ISO_GND tie stays inside the island, every other tie outside
    its keep-out band."""
    import cs_decoder_finish as ties

    if os.environ.get('LOCKED', '1') != '0':
        draw_current_paths(board)
    thermal_vias(board)
    led_jumpers(board)

    def in_island(point, grow):
        x, y = pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)
        return any(rect.min_x - grow <= x <= rect.max_x + grow and rect.min_y - grow <= y <= rect.max_y + grow
                   for rect in base.ISO_RECTS)

    areas = [zone.Outline() for zone in board.Zones() if zone.GetIsRuleArea()]
    edge = rev5.MM(0.6)
    current = {'net': ''}

    def allowed(point):
        if not (edge <= point.x <= rev5.MM(base.WIDTH) - edge and edge <= point.y <= rev5.MM(base.HEIGHT) - edge):
            return False
        if any(area.Contains(point, -1, rev5.MM(0.4)) for area in areas):
            return False
        if current['net'] == 'ISO_GND':
            return in_island(point, -0.6)
        return not in_island(point, base.ISO_BAND + 0.4)

    via_clear, path_clear = ties.via_clear, ties.path_clear
    ties.via_clear = lambda copper, position: allowed(position) and via_clear(copper, position)
    ties.path_clear = lambda copper, points, layer: all(map(allowed, points)) and path_clear(copper, points, layer)
    try:
        for footprint in sorted(board.GetFootprints(), key=lambda part: part.GetReference()):
            ref = footprint.GetReference()
            for pad in footprint.Pads():
                if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNetname() not in rev5.PLANE_NETS:
                    continue
                if pad.GetNumber() in base.GROUND_VIA_PADS.get(ref, ()):
                    continue
                current['net'] = pad.GetNetname()
                try:
                    ties.tie_pad_to_ground(board, ref, pad.GetNumber())
                except RuntimeError as error:
                    print('not tied', ref, pad.GetNumber(), error)
    finally:
        ties.via_clear, ties.path_clear = via_clear, path_clear


# Nets whose copper rev7_current.py draws: the router skips them (the class rev 5 uses for
# the plane nets), so it adds nothing beside the locked copper. Their other pads, such as the
# R67 tap and the shunt sense pins, are joined by gridroute.py afterwards.
LOCKED_NETS = ['Net-(F1-Pad1)', 'VIN', 'VSW', 'Net-(J12-Pin_1)', 'Net-(J11-Pin_1)']
rev5_patch_dsn = base.patch_dsn


def patch_dsn(text):
    """rev 5's patch, then the locked nets move into the class the router skips."""
    text = rev5_patch_dsn(text)
    tokens = [f'"{net}"' if '(' in net else net for net in LOCKED_NETS]
    parts = re.split(r'(\n    \(class \S+)', text)
    for index in range(1, len(parts), 2):
        if parts[index].endswith(f' {rev5.PLANE_CLASS}'):
            continue
        header, sep, rest = parts[index + 1].partition('\n      (circuit')
        for token in tokens:
            header = re.sub(rf'(?<=\s){re.escape(token)}(?=\s|$)', '', header)
        parts[index + 1] = header + sep + rest
    return ''.join(parts).replace(f'(class {rev5.PLANE_CLASS}', f'(class {rev5.PLANE_CLASS} ' + ' '.join(tokens), 1)


base.patch_dsn = patch_dsn
# Freerouting necks tracks down to 0.11 mm at fine pads unless told not to
base.ROUTER_ARGS = [*base.ROUTER_ARGS, '--router.automatic_neckdown=false']
base_run_freerouting = base.run_freerouting
TIE_VIA = (0.45, 0.2)


def run_freerouting(board, work_dir, rounds):
    """Freerouting, then the plane-tie vias get their 0.2 mm drill back: the session
    import gives every via its net class's drill (0.3 mm on the supply classes)."""
    base_run_freerouting(board, work_dir, rounds)
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T and track.GetWidth(pcbnew.F_Cu) == rev5.MM(TIE_VIA[0]):
            track.SetDrill(rev5.MM(TIE_VIA[1]))


# Net classes the router sees: the rev 6 rules (0.15 mm tracks and clearance, 0.45 / 0.2 mm
# vias, Power12V 0.5 mm). Nothing is loosened.
SIGNAL_CLASSES = {'Default', 'Analog', 'Control', 'Ground', 'SPI'}
SIGNAL_RULES = {'clearance': 0.15, 'track_width': 0.15, 'via_diameter': 0.45, 'via_drill': 0.2}
CLASS_RULES = {'Power12V': {'track_width': 0.5}}


# Nudges after placement (mm): C420 clears U106 pad 11 so a +12V via fits beside its pad.
NUDGES = {'C420': (1.0, 0.0)}


def nudge_parts(path):
    """Moves each NUDGES part from where the placer put it, and saves."""
    board = pcbnew.LoadBoard(path)
    for ref, (dx, dy) in NUDGES.items():
        footprint = board.FindFootprintByReference(ref)
        spot = footprint.GetPosition()
        footprint.SetPosition(pcbnew.VECTOR2I(spot.x + pcbnew.FromMM(dx), spot.y + pcbnew.FromMM(dy)))
    board.Save(path)


def apply_rules():
    """Writes SIGNAL_RULES into the signal net classes of cryocooler.kicad_pro."""
    path = Path(__file__).resolve().parent.parent / 'cryocooler.kicad_pro'
    project = json.loads(path.read_text())
    changed = []
    for item in project['net_settings']['classes']:
        if item['name'] in SIGNAL_CLASSES:
            item.update(SIGNAL_RULES)
            changed.append(item['name'])
        if item['name'] in CLASS_RULES:
            item.update(CLASS_RULES[item['name']])
            changed.append(item['name'])
    path.write_text(json.dumps(project, indent=2) + '\n')
    print('rules set on:', ' '.join(sorted(changed)))


if __name__ == '__main__':
    mode = sys.argv[1:2]
    if mode == ['place'] and len(sys.argv) == 4:
        # placement reserves no copper
        rev5.current_paths = lambda pad: ([], [])
        rev5.place(sys.argv[2], sys.argv[3])
        nudge_parts(sys.argv[3])
    elif mode == ['rules'] and len(sys.argv) == 2:
        apply_rules()
    elif mode in (['preroute'], ['route'], ['reroute'], ['finish']):
        # LOCKED=0 leaves the locked current copper out
        rev5.current_paths = lambda pad: ([], [])
        rev5.tie_plane_pads = tie_plane_pads
        base.run_freerouting = run_freerouting
        rev5.main()
    else:
        sys.exit(__doc__)
