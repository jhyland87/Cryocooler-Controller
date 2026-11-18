"""Places rev 5 on the Phoenix UCS 145-125 board (120 x 100 mm, drawing 2203448).

Reuses the placer in ucs125_board.py with this board's outline, floorplan and
anchors. Starts from an existing board so footprints and 3D models carry over,
syncs the parts to the rev 5 netlist, strips all copper and places every part.
Routing runs on the placed board, with the high-current copper laid first.

Usage (KiCad's python):
    rev5_board.py place in.kicad_pcb out.kicad_pcb
    rev5_board.py preroute in.kicad_pcb out.kicad_pcb    planes and locked copper only
    rev5_board.py route in.kicad_pcb out.kicad_pcb [rounds]
    rev5_board.py reroute in.kicad_pcb out.kicad_pcb drc.json
    rev5_board.py labels board.kicad_pcb   (0.8 mm silk part labels)
    rev5_board.py sections board.kicad_pcb   (section lines and names, after labels)
    rev5_board.py pins board.kicad_pcb   (connector pin names, before labels)
    rev5_board.py revmark board.kicad_pcb   (REV5 on the back, until the board ID is stamped)
    rev5_board.py finish board.kicad_pcb
"""
import math
import re
import sys

import pcbnew

import ucs125_board as base
from pcbnetlist import load_netlist
from pcbplace import Rect

MM = pcbnew.FromMM

# ─── outline (drawing 2203448), as gen_pcb.py ───
base.WIDTH, base.HEIGHT = 120.0, 100.0
# The 120 x 100 board has room: a 0.7 mm ring round every IC so each pin has a way
# out (0.2 mm on the front boxed in 14 fine-pitch pins), and wider part gaps.
# A 1 mm ring with 0.3 mm gaps left two parts without a spot.
base.FANOUT_RING = {'top': 0.7, 'bottom': 0.7}
base.PART_GAP = 0.2
base.BACK_PART_GAP = 0.3
base.HOLES = [(4.2, 4.2), (115.8, 4.2), (4.2, 95.8), (115.8, 95.8)]
base.U1_SPOT = (84.0, 12.75)
base.NOTCH = Rect(74.5, 0.0, 93.5, 6.0)
base.ANTENNA_KEEPOUTS = [Rect(60.0, 0.0, 74.5, 6.75), Rect(93.5, 0.0, 108.0, 6.75)]

# Wall connectors: (ref, edge, side, start along the edge, overhang past it).
# Top: flow / NTC / relay, then fan / pump back to back above the +12V end of the
# shunt, USB beside the ESP32.
# Left: 12 V in at the top corner (the user does not want it on the top edge),
# cryocooler sensor cables (IMU front, PT1000 back), then the
# isolated cryocooler output and amplifier input. Bottom: display, then I/O 1-4 as
# two pairs back to back (odd channels on the front), clear of the isolator parts,
# then the two pressure ports back to back. Right: RS-485, amplifier signal and REM,
# the two precision ports back to back, power button.
IO_PAIR_START = 46.0
IO_PAIR_PITCH = 20.0
PRESSURE_START = 90.0
base.EDGE_PLAN = [
    ('J2', 'left', 'top', 5.0, 0.3),
    ('J5', 'top', 'top', 22.2, 0.08),
    ('J6', 'top', 'bottom', 22.2, 0.3),
    ('J13', 'top', 'bottom', 30.6, 0.3),
    ('J3', 'top', 'top', 35.8, 0.24),
    ('J4', 'top', 'bottom', 35.8, 0.24),
    ('J1', 'top', 'top', 53.5, 0.55),
    ('J14', 'left', 'top', 22.5, 0.05),
    ('J10', 'left', 'bottom', 22.5, -0.3),
    ('J12', 'left', 'top', 33.0, 3.29),
    ('J11', 'left', 'top', 72.0, 3.29),
    ('J15', 'bottom', 'top', 14.5, 0.24),
    ('J21', 'bottom', 'bottom', 14.5, 0.24),
    *[(f'J{35 + n}', 'bottom', 'top' if n % 2 else 'bottom',
       IO_PAIR_START + IO_PAIR_PITCH * ((n - 1) // 2), 0.24) for n in range(1, 5)],
    ('J32', 'bottom', 'top', PRESSURE_START, 0.24),
    ('J33', 'bottom', 'bottom', PRESSURE_START, 0.24),
    ('J34', 'right', 'top', 5.0, 0.24),
    ('J9', 'right', 'top', 21.4, 0.29),
    ('J8', 'right', 'top', 30.6, 0.29),
    ('J30', 'right', 'top', 41.5, 0.24),
    ('J31', 'right', 'bottom', 41.5, 0.24),
    ('SW3', 'right', 'top', 80.0, 3.0),
]
# footprint-local mating direction: +y unless listed
base.FACE_LOCAL = {'J12': (0, -1), 'J2': (0, -1)}

base.ANCHORS = {'U1': (*base.U1_SPOT, 0, 'top')}
# Preferred spots, nudged to the nearest free one: ref -> (x, y, rotation, side)
base.PREFERRED = {
    # ─── 12 V path in one line at y = 19.5: J2 -> F1 -> Q1 -> shunt, its +12V
    # end right under the fan and pump headers ───
    'F1': (26.5, 19.5, 0, 'top'),
    'Q1': (33.0, 19.5, 270, 'top'),
    'R78': (40.0, 19.5, 180, 'top'),
    'D1': (30.6, 25.2, 90, 'top'),
    'C65': (38.0, 31.0, 0, 'top'),
    'C66': (49.0, 27.5, 0, 'top'),
    'U11': (33.0, 25.5, 0, 'bottom'),
    'U23': (40.0, 24.5, 0, 'bottom'),
    # ─── logic rails ───
    'U15': (48.0, 38.0, 0, 'top'),
    'L1': (48.0, 44.0, 0, 'top'),
    'U16': (54.0, 38.5, 0, 'top'),
    'L4': (54.0, 50.0, 0, 'top'),
    'U28': (50.0, 52.0, 0, 'bottom'),
    # ─── MCU ───
    'SW1': (66.0, 12.0, 90, 'top'),
    'SW2': (66.0, 20.0, 90, 'top'),
    'U2': (57.0, 12.0, 0, 'bottom'),
    'U32': (70.0, 29.0, 0, 'bottom'),
    'U25': (60.0, 28.0, 0, 'bottom'),
    # ─── cryocooler sensors ───
    'U36': (15.0, 27.0, 0, 'top'),
    'U14': (17.0, 40.0, 0, 'bottom'),
    # ─── isolated amplifier monitor: U17 straddles the barrier at x = 34 ───
    'U18': (22.0, 62.0, 0, 'top'),
    'U17': (34.0, 76.0, 180, 'top'),
    # ─── +-15 V rails, signal generator ───
    'U20': (68.0, 45.0, 0, 'top'),
    'L2': (68.0, 37.6, 0, 'top'),
    'L3': (68.0, 52.4, 0, 'top'),
    'U21': (77.0, 40.0, 0, 'top'),
    'U22': (77.0, 50.0, 0, 'top'),
    'U3': (86.0, 41.0, 0, 'top'),
    'U4': (91.0, 41.0, 0, 'top'),
    'U5': (96.0, 42.0, 0, 'top'),
    'U6': (91.0, 49.0, 0, 'top'),
    # ─── universal I/O: expanders, DAC, ADC, drivers, switches ───
    'U107': (56.0, 62.0, 0, 'bottom'),
    'U108': (76.0, 62.0, 0, 'bottom'),
    'U100': (88.0, 61.0, 0, 'top'),
    'U101': (95.0, 62.0, 0, 'top'),
    'U102': (50.0, 66.0, 0, 'top'),
    'U103': (70.0, 66.0, 0, 'top'),
    'U104': (60.0, 62.0, 0, 'top'),
    'U105': (80.0, 66.0, 0, 'top'),
    'U106': (66.0, 68.0, 0, 'bottom'),
    # ─── precision ports, expansion, display, ambient ───
    'U109': (105.0, 52.0, 0, 'top'),
    'U110': (103.0, 11.0, 0, 'top'),
    'U111': (103.0, 16.0, 0, 'top'),
    'J35': (97.0, 30.0, 0, 'bottom'),
    'U52': (24.0, 92.0, 0, 'bottom'),
    'F2': (38.0, 92.0, 0, 'top'),
    'U50': (114.0, 71.0, 0, 'top'),
}
# 10 mm tall electrolytics: only the front has the height (31 mm above, 10 mm below)
base.FRONT_ONLY_REFS = {'C65', 'C66'}
base.SAME_SIDE_OWNERS = {'U15', 'U16', 'U20', 'U21', 'U22'}

# Isolated island: J12 pins 1 and 2 (pin 3 is board ground, above it), J11, U18
# and U17's isolated half. U17 straddles x = 34.
# stepped at the bottom so the display header's pads keep the band's distance
base.ISO_RECTS = [Rect(0.0, 49.2, 34.0, 83.5), Rect(0.0, 83.5, 12.5, 85.2)]
base.ISO_SEED_NETS = {'ISO_GND', 'ISO_5V'}
base.ISO_EXEMPT = {'U17', 'J12'}

# ─── floorplan: schematic sheet -> section, section -> rectangles ───
SECTION_OF_SHEET = {
    'cryocooler': 'MCU & USB',
    'Indicators': 'MCU & USB',
    'GPIO Expander': 'MCU & USB',
    'Power Input': 'POWER INPUT',
    'Power Button': 'POWER INPUT',
    'System Current': 'POWER INPUT',
    'Rails 5V 3V3': 'LOGIC RAILS',
    'Water Cooling': 'WATER COOLING & RELAY',
    'Compressor Relay': 'WATER COOLING & RELAY',
    'Amp Current': 'AMP CURRENT (ISOLATED)',
    'Amp Control': 'AMP CONTROL',
    'Signal Generator': 'SIGNAL GENERATOR',
    'Rails +-15V': 'RAILS ±15V',
    'Power Good': 'RAILS ±15V',
    'IMU': 'CRYOCOOLER SENSORS',
    'Cold Head Temp': 'CRYOCOOLER SENSORS',
    'Display': 'DISPLAY',
    'Expansion': 'EXPANSION',
    'Ambient Temp': 'AMBIENT',
    'IO Precision Ports': 'PRECISION PORTS',
    'IO Pressure Ports': 'PRESSURE PORTS',
    'IO DAC and ADC': 'UNIVERSAL I/O',
    'IO Output Drivers': 'UNIVERSAL I/O',
    'IO Range and Pull-up': 'UNIVERSAL I/O',
    'IO Expanders': 'UNIVERSAL I/O',
}
SECTIONS = {
    'POWER INPUT': [Rect(0, 0, 22.3, 22.4), Rect(22.3, 14.5, 54, 34), Rect(19, 22.4, 44, 47.5),
                    Rect(108, 78, 120, 93)],
    'WATER COOLING & RELAY': [Rect(22.3, 0, 54, 14.5)],
    'MCU & USB': [Rect(54, 0, 92, 34), Rect(92, 0, 100, 22)],
    'EXPANSION': [Rect(100, 0, 120, 21.4), Rect(90, 22, 104, 42)],
    'AMP CONTROL': [Rect(100, 21.4, 120, 41)],
    'PRECISION PORTS': [Rect(100, 41, 120, 65)],
    'AMBIENT': [Rect(108, 65, 120, 78)],
    'CRYOCOOLER SENSORS': [Rect(0, 22.4, 19, 47.5)],
    'AMP CURRENT (ISOLATED)': [Rect(0, 47.5, 44, 86.7)],
    'LOGIC RAILS': [Rect(44, 34, 58, 57)],
    'RAILS ±15V': [Rect(58, 34, 82, 57)],
    'SIGNAL GENERATOR': [Rect(82, 34, 92, 57), Rect(92, 37, 100, 57)],
    'DISPLAY': [Rect(0, 86.7, 44, 100)],
    'UNIVERSAL I/O': [Rect(44, 57, 100, 72)],
    'PRESSURE PORTS': [Rect(86, 72, 108, 100)],
}
# universal I/O channel cells: each back-to-back pair of channels shares the strip
# behind its connectors, named here by the pair's front connector
CHANNEL_CONNECTORS = {f'IO Channel {n}': f'J{35 + n - (n - 1) % 2}' for n in range(1, 5)}
CHANNEL_DEPTH = 30.0


def section_rects(layout, parts, ref):
    """Rectangles a part has to stay inside, or None if it may go anywhere."""
    sheet = parts[ref]['sheet']
    connector = CHANNEL_CONNECTORS.get(sheet)
    if connector is not None and connector in layout.spots:
        start = layout.courtyard(connector).min_x
        return [Rect(start, base.HEIGHT - CHANNEL_DEPTH, start + IO_PAIR_PITCH, base.HEIGHT)]
    section = SECTION_OF_SHEET.get(sheet)
    return SECTIONS.get(section)


def inside_any(box, rects, tolerance=0.05):
    """True if all four corners of `box` lie in the union of `rects`."""
    corners = [(box.min_x, box.min_y), (box.max_x, box.min_y), (box.min_x, box.max_y),
               (box.max_x, box.max_y)]
    return all(
        any(rect.min_x - tolerance <= x <= rect.max_x + tolerance
            and rect.min_y - tolerance <= y <= rect.max_y + tolerance for rect in rects)
        for x, y in corners
    )


class SectionLayout(base.Layout):
    """Layout that also keeps each part inside its schematic section."""

    def __init__(self, board, parts):
        super().__init__(board)
        self.parts = parts
        self.enforce_sections = True
        self.limits = {}

    def margin(self, ref, side):
        # wall connectors pack edge to edge: their courtyards carry the clearance
        if ref.startswith(('J', 'SW')) and ref != 'J35':
            return 0.0
        # every multi-pin part gets the escape ring, not only the U references
        if len(self.geometry[ref].pad_centers) >= 5 and not ref.startswith('U'):
            return super().margin(ref, side) + base.FANOUT_RING[side]
        return super().margin(ref, side)

    def problem(self, ref, spot, ignore=()):
        # the section test is the cheapest, so it goes first
        if self.enforce_sections and ref not in self.edge_side:
            if ref not in self.limits:
                self.limits[ref] = section_rects(self, self.parts, ref)
            rects = self.limits[ref]
            if rects is not None and not inside_any(self.courtyard(ref, spot), rects):
                return 'section'
        return super().problem(ref, spot, ignore)

    def take(self, ref):
        """Lifts a placed part off the board again."""
        for cell in cells_of(self.cache.pop(ref)[1]):
            self.grid[cell].discard(ref)
        del self.spots[ref]


cells_of = base.cells
STRICT_SHEETS = [True]
# I/O channel pairs laid out once and copied: master pair -> pairs that copy it. A
# part that does not fit is nudged and reported. Empty on rev 5: channels 1-2 have
# the PWM gate and buffer that 3-4 lack, so the two pairs are not the same circuit.
PAIR_COPIES = {}


def ref_key(ref):
    prefix = ref.rstrip('0123456789')
    return prefix, int(ref[len(prefix):])


def replicate_channels(layout, parts):
    """Moves each copy pair's parts to the master pair's spots, shifted by the
    distance between their connectors. Returns the refs that did not fit there."""
    def channel(number):
        return sorted((ref for ref, part in parts.items() if part['sheet'] == f'IO Channel {number}'), key=ref_key)

    misfits = []
    for master, copies in PAIR_COPIES.items():
        origin = layout.spots[f'J{35 + master[0]}']
        for pair in copies:
            connector = layout.spots[f'J{35 + pair[0]}']
            shift = (connector[0] - origin[0], connector[1] - origin[1])
            twins = [(source, ref) for from_channel, to_channel in zip(master, pair)
                     for source, ref in zip(channel(from_channel), channel(to_channel)) if not ref.startswith('J')]
            before = {ref: layout.spots[ref] for _source, ref in twins}
            for ref in before:
                layout.take(ref)
            for source, ref in twins:
                x, y, angle, side = layout.spots[source]
                spot = (x + shift[0], y + shift[1], angle, side)
                if layout.problem(ref, spot) is not None:
                    misfits.append(ref)
                    spot = layout.nudge(ref, spot, [side]) or layout.nudge(ref, before[ref], ['top', 'bottom'])
                layout.put(ref, spot)
    return misfits



def is_supply(net):
    name = net.split('/')[-1]
    return name.startswith(('+', '-', 'VIN', 'VSW', 'ISO_5V', 'USB_VBUS'))


def choose_target(layout, ref, parts, nets, pad_nets, auto, load):
    """(my pad, target ref, target pad) this part should sit beside: a placed
    part of its own sheet on a signal net first, so each section fills from its
    own anchors. While STRICT_SHEETS is set, a part whose same-sheet neighbours
    are not placed yet waits for them.
    """
    my_sheet = parts[ref]['sheet']
    pads = pad_nets.get(ref, {})
    waiting = False
    for same_sheet in (True, False):
        best = None
        for number, net in sorted(pads.items()):
            if net.startswith('unconnected'):
                continue
            ground = net.split('/')[-1] in base.GROUND_NETS
            others = [(other, pad) for other, pad in nets[net] if other != ref]
            if same_sheet:
                others = [node for node in others if parts[node[0]]['sheet'] == my_sheet]
                if not ground and any(node[0] not in layout.spots for node in others):
                    waiting = True
            placed = [node for node in others if node[0] in layout.spots]
            if not placed:
                continue
            other, pad = min(placed, key=lambda node: (node[0] in auto, load.get(node, 0), node))
            rank = (ground, is_supply(net), len(nets[net]), number, other, pad)
            if best is None or rank < best:
                best = rank
        if best is not None and not (same_sheet and best[0] and waiting):
            return best[3:]
        if same_sheet and waiting and STRICT_SHEETS[0]:
            return None
    return None


base.choose_target = choose_target


# ─── locked high-current copper ───
POWER_WIDTH = 3.0
AMP_WIDTH = 2.0


def current_paths(pad):
    """Locked copper for the 10 A input path and the amplifier current path, from
    the pad positions `pad(ref, number)` gives: (tracks, vias), tracks as (net,
    layer name, points, width) and vias as (net, x, y).
    """
    tracks, vias = [], []
    # 12 V: J2 pins 3 / 4 -> F1 -> Q1 source -> Q1 drain -> shunt -> fan and pump pin 2
    pin3, pin4 = pad('J2', '3'), pad('J2', '4')
    near, far = sorted((pin3, pin4), key=lambda point: abs(point[1] - pad('F1', '1')[1]))
    fuse_in, fuse_out = pad('F1', '1'), pad('F1', '2')
    tracks.append(('Net-(F1-Pad1)', 'F', [far, near, (near[0], fuse_in[1]), fuse_in], POWER_WIDTH))
    tracks.append(('Net-(F1-Pad1)', 'B', [far, near, (near[0], fuse_in[1]), fuse_in], POWER_WIDTH))
    for offset in (-0.8, 0.8):
        vias.append(('Net-(F1-Pad1)', fuse_in[0] - 0.2, fuse_in[1] + offset))
    sources = [pad('Q1', number) for number in '123']
    source = (sum(point[0] for point in sources) / 3, sum(point[1] for point in sources) / 3)
    tracks.append(('VIN', 'F', [fuse_out, (source[0] - 1.2, source[1])], 2.4))
    tracks.append(('VIN', 'F', [(source[0] - 1.2, source[1]), (source[0] - 0.3, source[1])], 1.5))
    drain, shunt_in, shunt_out = pad('Q1', '5'), pad('R78', '4'), pad('R78', '1')
    tracks.append(('VSW', 'F', [drain, shunt_in], 2.0))
    fan, pump = pad('J3', '2'), pad('J4', '2')
    # front leg: out past the shunt's sense pad, up, back in under the fan pin
    clear, level = shunt_out[0] + 2.6, fan[1] + 3.9
    tracks.append(('+12V', 'F', [shunt_out, (clear, shunt_out[1]), (clear, level), (fan[0], level)], 1.6))
    tracks.append(('+12V', 'F', [(fan[0], level), fan], 1.1))
    for offset_x in (-0.7, 0.7):
        for offset_y in (-0.35, 0.75):
            vias.append(('+12V', shunt_out[0] + offset_x, shunt_out[1] + offset_y))
    # back leg straight to the pump pin, which sits under the fan pin: vias join them
    tracks.append(('+12V', 'B', [shunt_out, (pump[0], shunt_out[1]), (pump[0], pump[1] + 2.6)], 2.0))
    tracks.append(('+12V', 'B', [(pump[0], pump[1] + 2.6), pump], 1.1))
    for offset_y in (-1.2, 0.0, 1.2):
        vias.append(('+12V', (fan[0] + pump[0]) / 2, fan[1] + offset_y))
    # amplifier current: IP- (U18 pins 5-8) on the front to J12 pin 1; IP+ (pins
    # 1-4) through a via bar outside U18 and down the back to J11 pin 1, so no
    # copper sits under the isolation package
    minus, plus = 'Net-(J12-Pin_1)', 'Net-(J11-Pin_1)'
    column = pad('U18', '1')[0]
    top = [pad('U18', number)[1] for number in '1234']
    bottom = [pad('U18', number)[1] for number in '5678']
    out_pin, in_pin = pad('J12', '1'), pad('J11', '1')
    lane = column - 4.35
    middle = (bottom[0] + bottom[-1]) / 2
    tracks.append((minus, 'F', [(column, bottom[0] + 0.6), (column, bottom[-1])], 1.4))
    tracks.append((minus, 'F', [(column, middle), (lane, middle), (lane, out_pin[1] + 1.1), out_pin], AMP_WIDTH))
    bar = column - 1.85
    tracks.append((plus, 'F', [(column, top[0]), (column, top[-1] - 0.6)], 1.4))
    tracks.append((plus, 'F', [(bar + 0.3, top[0]), (bar + 0.3, top[-1] - 0.6)], 1.2))
    bar_vias = [top[0] + index * (top[-1] - 0.6 - top[0]) / 3 for index in range(4)]
    for via_y in bar_vias:
        vias.append((plus, bar, via_y))
    turn = in_pin[1] - 4.3
    tracks.append((plus, 'B', [(bar, bar_vias[0]), (bar, turn - (bar - in_pin[0])), (in_pin[0], turn),
                               (in_pin[0], in_pin[1] - 1.2)], AMP_WIDTH))
    for offset_x in (-0.5, 0.5):
        for offset_y in (-2.2, -1.2):
            vias.append((plus, in_pin[0] + offset_x, in_pin[1] + offset_y))
    return tracks, vias


def reserve_current_paths(layout):
    """Keeps auto-placed parts off the locked copper (width plus clearance)."""
    tracks, vias = current_paths(lambda ref, number: layout.pad_position(ref, number))
    index = 0
    for _net, layer, points, width in tracks:
        reach = width / 2 + 0.35
        for start, end in zip(points, points[1:]):
            rect = Rect(min(start[0], end[0]) - reach, min(start[1], end[1]) - reach,
                        max(start[0], end[0]) + reach, max(start[1], end[1]) + reach)
            name = f'~current {index}'
            index += 1
            layout.cache[name] = ('top' if layer == 'F' else 'bottom', rect, [], [])
            for cell in base.cells(rect):
                layout.grid.setdefault(cell, set()).add(name)
    for _net, via_x, via_y in vias:
        for side in ('top', 'bottom'):
            rect = Rect(via_x - 0.6, via_y - 0.6, via_x + 0.6, via_y + 0.6)
            name = f'~current {index}'
            index += 1
            layout.cache[name] = (side, rect, [], [])
            for cell in base.cells(rect):
                layout.grid.setdefault(cell, set()).add(name)


def pre_route_current(board):
    """Lays the locked 12 V input path and the amplifier current path."""
    layers = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
    tracks, vias = current_paths(lambda ref, number: base.pad_xy(board, ref, number))
    for net, layer, points, width in tracks:
        base.add_track(board, net, layers[layer], points, width)
    for net, via_x, via_y in vias:
        base.add_via(board, net, via_x, via_y, 0.6, 0.3)


def ground_via_pads(board):
    """Exposed ground pads of the ICs (at least 0.9 mm both ways): each gets a
    locked via-in-pad to the In1 plane."""
    table = {}
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if not ref.startswith('U'):
            continue
        for pad in footprint.Pads():
            if (pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and pad.GetNetname().split('/')[-1] in base.GROUND_NETS
                    and min(pad.GetSizeX(), pad.GetSizeY()) >= MM(0.9)):
                table.setdefault(ref, set()).add(pad.GetNumber())
    return table


PLANE_NETS = {'GND', 'ISO_GND', '+3V3'}
PLANE_CLASS = 'PlaneTied'


def tie_plane_pads(board):
    """Every surface-mount GND, ISO_GND and +3V3 pad gets a stub and a via to its
    plane, so the autorouter is left with signals only."""
    import cs_decoder_finish as ties
    from cs_decoder_finish import tie_pad_to_ground

    areas = [zone.Outline() for zone in board.Zones() if zone.GetIsRuleArea()]
    edge = MM(0.6)

    def allowed(point):
        if not (edge <= point.x <= MM(base.WIDTH) - edge and edge <= point.y <= MM(base.HEIGHT) - edge):
            return False
        return not any(area.Contains(point, -1, MM(0.4)) for area in areas)

    via_clear, path_clear = ties.via_clear, ties.path_clear
    ties.via_clear = lambda copper, position: allowed(position) and via_clear(copper, position)
    ties.path_clear = lambda copper, points, layer: all(map(allowed, points)) and path_clear(copper, points, layer)
    for footprint in sorted(board.GetFootprints(), key=lambda part: part.GetReference()):
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNetname() not in PLANE_NETS:
                continue
            if pad.GetNumber() in base.GROUND_VIA_PADS.get(ref, ()):
                continue
            try:
                tie_pad_to_ground(board, ref, pad.GetNumber())
            except RuntimeError as error:
                print('not tied', ref, pad.GetNumber(), error)


def pre_route(board):
    base.GROUND_VIA_PADS = ground_via_pads(board)
    base_pre_route(board)
    tie_plane_pads(board)


def patch_dsn(text):
    """The plane nets are already tied, so they go in a class the router skips."""
    text = base_patch_dsn(text)
    for net in sorted(PLANE_NETS):
        text = re.sub(rf'(\(class \S+(?: \S+)*?) {re.escape(net)}(?=[ \n])', r'\1', text, count=1)
    rule = '(circuit\n        (use_via "Via[0-3]_600:300_um")\n      )\n      (rule\n        (width 300)\n        (clearance 150)\n      )'
    block = f'(class {PLANE_CLASS} {" ".join(sorted(PLANE_NETS))}\n      {rule}\n    )\n    '
    return text.replace('(class kicad_default', block + '(class kicad_default', 1)


base_patch_dsn = base.patch_dsn
base.patch_dsn = patch_dsn
base.ROUTER_ARGS = [f'--router.autorouter.ignore_net_classes={PLANE_CLASS}', '--router.fanout.enabled=false']


base_pre_route = base.pre_route
base.pre_route = pre_route
base.ISO_OUTLINE = [(0.0, 49.2), (34.0, 49.2), (34.0, 83.5), (12.5, 83.5), (12.5, 85.2), (0.0, 85.2)]
base.PAD_BRIDGES = {}
# part labels: function names printed with (or instead of) the reference
base.LED_LABELS = {}
# the dense I/O block needs a wider search than rev 4 did
base.PART_GAPS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0)
base.SHIFTS = (0.0, -0.5, 0.5, -1.0, 1.0, -1.5, 1.5, -2.0, 2.0, -2.5, 2.5)
base.LABEL_FUNCTIONS = {
    'J1': 'USB', 'J2': '12V IN', 'J3': 'FAN', 'J4': 'PUMP', 'J5': 'FLOW', 'J6': 'NTC',
    'J8': 'AMP REM', 'J9': 'SINE OUT', 'J10': 'RTD', 'J11': 'AMP OUT', 'J12': 'CRYO',
    'J13': 'RELAY', 'J14': 'IMU', 'J15': 'DISPLAY', 'J21': 'DISP 12V',
    'J30': 'SENSOR A', 'J31': 'SENSOR B', 'J32': 'PRESS 1', 'J33': 'PRESS 2',
    'J34': 'RS-485', 'J35': 'SPI EXP', 'J36': 'IO1', 'J37': 'IO2', 'J38': 'IO3', 'J39': 'IO4',
    'JP1': 'SG 3V3', 'JP2': 'PS15', 'JP3': 'ISO5', 'JP4': 'COOL', 'JP5': 'CH', 'JP6': 'IO',
    'JP10': 'AUTO ON', 'JP11': 'TERM',
    **{f'JP{12 + 2 * n}': f'IO{n + 1} 5V' for n in range(4)},
    **{f'JP{13 + 2 * n}': f'IO{n + 1} 12V' for n in range(4)},
    'SW1': 'RESET', 'SW2': 'BOOT', 'SW3': 'POWER',
    'D13': 'STATE', 'D7': 'PWR', 'D11': '+15V', 'D12': '-15V', 'D2': 'AMP', 'D3': 'COMP',
    'D6': 'ALERT', 'D10': 'ISO 5V',
}
base.pre_route_current = pre_route_current


def ratsnest(layout, nets):
    """(length mm, net) of each signal net's minimum spanning tree over its pads."""
    lengths = []
    for name, nodes in nets.items():
        short = name.split('/')[-1]
        if short in base.GROUND_NETS or short.startswith(('+', '-', 'VIN', 'VSW', 'unconnected')):
            continue
        points = [layout.pad_position(ref, pad) for ref, pad in nodes
                  if ref in layout.spots and pad in layout.geometry[ref].pad_centers]
        if len(points) < 2:
            continue
        joined, rest, total = [points[0]], points[1:], 0.0
        while rest:
            distance, index = min(
                (min(math.dist(point, other) for other in joined), index)
                for index, point in enumerate(rest)
            )
            total += distance
            joined.append(rest.pop(index))
        lengths.append((round(total, 1), short))
    return sorted(lengths, reverse=True)


def place(in_path, out_path):
    board = pcbnew.LoadBoard(in_path)
    parts, nets = load_netlist()
    removed, added = base.sync_parts(board, parts, nets)
    print('removed:', len(removed), '| added:', len(added))
    base.strip_board(board)
    base.draw_outline(board)
    holes = [fp for fp in board.GetFootprints() if not fp.GetReference()]
    for footprint, (hole_x, hole_y) in zip(holes, base.HOLES):
        footprint.SetPosition(pcbnew.VECTOR2I(MM(hole_x), MM(hole_y)))
    layout = SectionLayout(board, parts)
    print('isolated parts:', ' '.join(sorted(layout.iso_refs)))
    for ref, spot in base.ANCHORS.items():
        layout.put(ref, spot)
    for ref, edge, side, start, overhang in base.EDGE_PLAN:
        spot = layout.place_on_edge(ref, edge, side, start, overhang)
        if spot is None:
            print('NO ROOM on the', edge, 'edge for', ref)
            continue
        box = layout.courtyard(ref)
        print(f'{ref:4} {edge:6} {side:6} rot {spot[2]:3} x {box.min_x:6.2f}..{box.max_x:6.2f} '
              f'y {box.min_y:6.2f}..{box.max_y:6.2f}')
    for ref, spot in base.PREFERRED.items():
        free = layout.nudge(ref, spot, [spot[3]])
        if free is None:
            print('NO ROOM for', ref, '| at its anchor:', layout.problem(ref, spot), layout.courtyard(ref, spot))
            continue
        if math.hypot(free[0] - spot[0], free[1] - spot[1]) > 2.0:
            print(f'{ref} moved {free[0] - spot[0]:+.2f}, {free[1] - spot[1]:+.2f}')
        layout.put(ref, free)
    reserve_current_paths(layout)
    wall = {plan[0] for plan in base.EDGE_PLAN}
    auto = sorted(set(layout.footprints) - set(layout.spots) - wall)
    base.place_small_parts(layout, parts, nets, set(auto))
    # second pass without the section limit, so nothing is left off the board
    # parts still waiting for a same-sheet neighbour take any placed neighbour
    STRICT_SHEETS[0] = False
    waiting = set(layout.footprints) - set(layout.spots)
    base.place_small_parts(layout, parts, nets, waiting)
    left = sorted(set(layout.footprints) - set(layout.spots))
    if left:
        print('outside their section:', ' '.join(left))
        layout.enforce_sections = False
        base.place_small_parts(layout, parts, nets, set(left))
    unplaced = sorted(set(layout.footprints) - set(layout.spots))
    for index, ref in enumerate(unplaced):
        layout.footprints[ref].SetPosition(
            pcbnew.VECTOR2I(MM(130 + (index % 10) * 6), MM(5 + (index // 10) * 4)))
    layout.enforce_sections = False
    print('channel copies that had to move:', ' '.join(replicate_channels(layout, parts)))
    base.apply_spots(layout)
    print('prediction errors:', base.check_prediction(layout))
    print('unplaced:', len(unplaced), ' '.join(unplaced))
    print('outside section:', ' '.join(left))
    sides = [spot[3] for spot in layout.spots.values()]
    print('placed:', len(sides), 'top', sides.count('top'), 'bottom', sides.count('bottom'))
    print('longest signal nets (mm):', ratsnest(layout, nets)[:15])
    pcbnew.SaveBoard(out_path, board)


SECTION_GROUP = 'section outlines'
SECTION_STEP = 0.25
SECTION_MIN_RUN = 2.0
# where the full name finds no free spot in its section
SECTION_SHORT = {'SIGNAL GENERATOR': 'SIG GEN', 'WATER COOLING & RELAY': 'COOLING', 'EXPANSION': 'EXP',
                 'AMP CONTROL': 'AMP CTL', 'CRYOCOOLER SENSORS': 'SENSORS', 'RAILS ±15V': '±15V'}
# sections as printed: the floorplan plus the channel strip behind the I/O connectors
PRINTED_SECTIONS = {**SECTIONS, 'I/O CHANNELS': [Rect(44, 72, 86, 100)]}


def silk_obstacles(board):
    """One SilkMap per side holding pads, part bodies and existing silk."""
    sides = {'F': (pcbnew.F_SilkS, pcbnew.F_Cu, pcbnew.F_Fab, base.SilkMap()),
             'B': (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Fab, base.SilkMap())}
    for footprint in board.GetFootprints():
        own = 'B' if footprint.IsFlipped() else 'F'
        silk, _copper, fab, silk_map = sides[own]
        silk_map.add(base.body_rect(footprint, fab, silk).inflated(0.2))
        for silk, copper, _fab, silk_map in sides.values():
            for pad in footprint.Pads():
                if pad.IsOnLayer(copper):
                    silk_map.add(base.box_rect(pad.GetBoundingBox()).inflated(0.2))
    for drawing in board.GetDrawings():
        for silk, _copper, _fab, silk_map in sides.values():
            if drawing.GetLayer() == silk:
                silk_map.add(base.box_rect(drawing.GetBoundingBox()).inflated(0.2))
    return sides


def add_section_outlines(path):
    """Section border lines where they clear parts and text, and each section's
    name, on both silk layers. Replaces an earlier run."""
    board = pcbnew.LoadBoard(path)
    keep = []
    for group in list(board.Groups()):
        if group.GetName() == SECTION_GROUP:
            for item in list(group.GetItems()):
                keep.append(item)
                board.Remove(item)
            keep.append(group)
            board.Remove(group)
    sides = silk_obstacles(board)
    group = pcbnew.PCB_GROUP(board)
    group.SetName(SECTION_GROUP)
    board.Add(group)
    # border points on a grid; a point on two sections' borders is drawn once
    points = set()
    for rects in PRINTED_SECTIONS.values():
        for rect in rects:
            for index in range(int(round((rect.max_x - rect.min_x) / SECTION_STEP)) + 1):
                x = rect.min_x + index * SECTION_STEP
                points.update({(round(x, 2), rect.min_y, 'h'), (round(x, 2), rect.max_y, 'h')})
            for index in range(int(round((rect.max_y - rect.min_y) / SECTION_STEP)) + 1):
                y = rect.min_y + index * SECTION_STEP
                points.update({(rect.min_x, round(y, 2), 'v'), (rect.max_x, round(y, 2), 'v')})
    lines = names = 0
    missed = []
    for key, (silk, _copper, _fab, silk_map) in sides.items():
        free = set()
        for x, y, way in points:
            dot = Rect(x - 0.1, y - 0.1, x + 0.1, y + 0.1)
            if not base.outline_problem(dot.inflated(0.5)) and not silk_map.blocked(dot, SECTION_GROUP):
                free.add((x, y, way))
        runs = []
        for way, along, across in (('h', 0, 1), ('v', 1, 0)):
            rows = {}
            for point in free:
                if point[2] == way:
                    rows.setdefault(point[across], []).append(point[along])
            for fixed, values in rows.items():
                values.sort()
                start = previous = values[0]
                for value in values[1:] + [None]:
                    if value is None or value - previous > SECTION_STEP + 0.01:
                        if previous - start >= SECTION_MIN_RUN:
                            runs.append((way, fixed, start, previous))
                        start = value
                    previous = value
        for way, fixed, start, end in runs:
            line = pcbnew.PCB_SHAPE(board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(silk)
            line.SetWidth(MM(0.12))
            first, second = ((start, fixed), (end, fixed)) if way == 'h' else ((fixed, start), (fixed, end))
            line.SetStart(pcbnew.VECTOR2I(MM(first[0]), MM(first[1])))
            line.SetEnd(pcbnew.VECTOR2I(MM(second[0]), MM(second[1])))
            board.Add(line)
            group.AddItem(line)
            silk_map.add(Rect(min(first[0], second[0]) - 0.2, min(first[1], second[1]) - 0.2,
                              max(first[0], second[0]) + 0.2, max(first[1], second[1]) + 0.2))
            lines += 1
        for name, rects in PRINTED_SECTIONS.items():
            if not any(place_section_name(board, group, text, rects, silk, silk_map)
                       for text in (name, SECTION_SHORT.get(name, name))):
                missed.append(f'{name} ({key})')
            else:
                names += 1
    pcbnew.SaveBoard(path, board)
    print(f'section outlines: {lines} lines, {names} names, no room for:', ', '.join(missed) or 'none')


def place_section_name(board, group, name, rects, silk, silk_map):
    """First free spot for a section's name, top-left first, inside its own rectangles."""
    for height in (1.0, 0.8):
        for rect in rects:
            y = rect.min_y + 0.5 + height / 2
            while y < rect.max_y - 0.5:
                x = rect.min_x + 0.6
                while x < rect.max_x - 0.6:
                    label = pcbnew.PCB_TEXT(board)
                    label.SetText(name)
                    label.SetLayer(silk)
                    label.SetTextSize(pcbnew.VECTOR2I(MM(height * 0.9), MM(height)))
                    label.SetTextThickness(MM(0.15 if height == 1.0 else 0.12))
                    label.SetMirrored(silk == pcbnew.B_SilkS)
                    label.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if silk == pcbnew.F_SilkS
                                          else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
                    label.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
                    label.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                    box = base.box_rect(label.GetBoundingBox())
                    inside = (box.min_x >= rect.min_x + 0.4 and box.max_x <= rect.max_x - 0.4
                              and box.min_y >= rect.min_y + 0.4 and box.max_y <= rect.max_y - 0.4)
                    if inside and not base.outline_problem(box) and not silk_map.blocked(box.inflated(0.15), SECTION_GROUP):
                        board.Add(label)
                        group.AddItem(label)
                        silk_map.add(box.inflated(0.2))
                        return True
                    x += 0.5
                y += 0.5
    return False


PIN_NAME_GROUP = 'pin names'
FAN = {'1': 'GND', '2': '12V', '3': 'TACH', '4': 'PWM'}
SENSOR = {'1': 'EXC', '2': 'IN+', '3': 'IN-', '4': 'GND'}
PRESSURE = {'1': '5V', '2': 'SIG', '3': 'GND', '4': 'NC'}
CHANNEL = {'1': 'V+', '2': 'IO', '3': 'GND', '4': 'NC'}
# connector -> [(body sides to try: N/S/E/W on the board, {pad: name})]. Names run
# away from the body, in line with their pads. J1 and J14 are too fine to name.
PIN_NAMES = {
    'J2': [('SN', {'1': 'GND', '3': '12V'})],
    'J3': [('S', FAN)], 'J4': [('S', FAN)],
    'J5': [('S', {'1': 'GND', '2': '12V', '3': 'SIG', '4': 'NC'})],
    'J6': [('S', {'1': 'NTC', '2': 'GND'})],
    'J8': [('W', {'1': 'REM', '2': 'GND'})],
    'J9': [('NS', {'1': 'GND', '2': 'SIG'})],
    'J10': [('E', {'1': 'EXC', '2': 'S+', '3': 'S-', '4': 'RET'})],
    'J11': [('E', {'1': '+', '2': '-'})],
    'J12': [('E', {'1': '+', '2': '-', '3': 'GND'})],
    'J13': [('S', {'1': '12V', '2': 'GND'})],
    'J15': [('N', {'1': 'CANH', '2': 'CANL', '3': 'BTN', '4': 'RST'})],
    'J21': [('N', {'1': 'GND', '2': '12V'})],
    'J30': [('W', SENSOR)], 'J31': [('W', SENSOR)],
    'J32': [('N', PRESSURE)], 'J33': [('N', PRESSURE)],
    'J34': [('W', {'1': 'A', '2': 'B', '3': 'GND', '4': 'NC'})],
    # J35 pad 9 (GND, beside pad 10 GND) is left out: R514 sits where its name would go
    'J35': [('W', {'1': '3V3', '3': 'SCK', '5': 'MISO', '7': 'CSA'}),
            ('E', {'2': '5V', '4': 'MOSI', '6': 'INT', '8': 'CSB', '10': 'GND'})],
    **{f'J{36 + n}': [('N', CHANNEL)] for n in range(4)},
}
PIN_NAME_REACH = 2.0  # furthest a row of names may start from the body


def pin_name_row(board, footprint, silk, side, names, start):
    """The row's texts, each beginning `start` mm off the body's `side` edge."""
    body = base.box_rect(footprint.GetBoundingBox(False, False))
    row = []
    for pad in footprint.Pads():
        text = names.get(pad.GetNumber())
        if text is None:
            continue
        x, y = pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)
        probe = base.new_label(board, text, silk, 0, 0, False)
        size = base.box_rect(probe.GetBoundingBox())
        reach = start + (size.max_x - size.min_x) / 2
        spot = {'N': (x, body.min_y - reach), 'S': (x, body.max_y + reach),
                'W': (body.min_x - reach, y), 'E': (body.max_x + reach, y)}[side]
        row.append(base.new_label(board, text, silk, *spot, side in 'NS'))
    return row


def add_pin_names(path):
    """Connector pin names in 0.8 mm silk, one aligned row per connector side,
    at the nearest distance where the whole row is clear. Replaces an earlier run."""
    board = pcbnew.LoadBoard(path)
    keep = []
    for group in list(board.Groups()):
        if group.GetName() == PIN_NAME_GROUP:
            for item in list(group.GetItems()):
                keep.append(item)
                board.Remove(item)
            keep.append(group)
            board.Remove(group)
    sides = silk_obstacles(board)
    group = pcbnew.PCB_GROUP(board)
    group.SetName(PIN_NAME_GROUP)
    board.Add(group)
    placed, missed = 0, []
    for ref, rows in PIN_NAMES.items():
        footprint = board.FindFootprintByReference(ref)
        silk, _copper, _fab, silk_map = sides['B' if footprint.IsFlipped() else 'F']
        for tries, names in rows:
            starts = [0.3 + 0.25 * step for step in range(int(PIN_NAME_REACH / 0.25))]
            for side, start in ((side, start) for start in starts for side in tries):
                row = pin_name_row(board, footprint, silk, side, names, start)
                boxes = [base.box_rect(label.GetBoundingBox()) for label in row]
                if any(base.outline_problem(box) or silk_map.blocked(box.inflated(0.1), PIN_NAME_GROUP)
                       for box in boxes):
                    continue
                for label, box in zip(row, boxes):
                    board.Add(label)
                    group.AddItem(label)
                    silk_map.add(box.inflated(0.2))
                placed += len(row)
                break
            else:
                missed.append(f'{ref} ({tries})')
    pcbnew.SaveBoard(path, board)
    print(f'pin names: {placed} placed, no room for:', ', '.join(missed) or 'none')


REV_MARK = 'REV5'
REV_MARK_GROUP = 'board id'
REV_MARK_SPOT = (19.0, 2.4)  # where the board ID block goes on this outline


def add_rev_mark(path):
    """Prints REV_MARK in 1 mm back silk at the free spot nearest REV_MARK_SPOT.
    Stands in for the board ID block. Replaces an earlier run."""
    board = pcbnew.LoadBoard(path)
    keep = []
    for group in list(board.Groups()):
        if group.GetName() == REV_MARK_GROUP:
            for item in list(group.GetItems()):
                keep.append(item)
                board.Remove(item)
            keep.append(group)
            board.Remove(group)
    silk, _copper, _fab, silk_map = silk_obstacles(board)['B']
    spots = sorted(((x * 0.5, y * 0.5) for x in range(2, 239) for y in range(2, 199)),
                   key=lambda spot: math.dist(spot, REV_MARK_SPOT))
    for x, y in spots:
        label = pcbnew.PCB_TEXT(board)
        label.SetText(REV_MARK)
        label.SetLayer(silk)
        label.SetTextSize(pcbnew.VECTOR2I(MM(0.9), MM(1.0)))
        label.SetTextThickness(MM(0.15))
        label.SetMirrored(True)
        label.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        box = base.box_rect(label.GetBoundingBox())
        if base.outline_problem(box) or silk_map.blocked(box.inflated(0.15), REV_MARK_GROUP):
            continue
        group = pcbnew.PCB_GROUP(board)
        group.SetName(REV_MARK_GROUP)
        board.Add(group)
        board.Add(label)
        group.AddItem(label)
        pcbnew.SaveBoard(path, board)
        print(f'{REV_MARK} at', (x, y))
        return
    print(f'{REV_MARK}: no free spot on the back')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'place' and len(sys.argv) == 4:
        place(sys.argv[2], sys.argv[3])
    elif mode in ('preroute', 'route') and len(sys.argv) >= 4:
        rounds = 0 if mode == 'preroute' else int(sys.argv[4]) if len(sys.argv) > 4 else 2
        base.route(sys.argv[2], sys.argv[3], rounds)
    elif mode == 'reroute' and len(sys.argv) == 5:
        base.reroute(sys.argv[2], sys.argv[3], sys.argv[4])
    elif mode == 'finish' and len(sys.argv) == 3:
        base.finish(sys.argv[2])
    elif mode == 'labels' and len(sys.argv) == 3:
        base.add_part_labels(sys.argv[2])
    elif mode == 'sections' and len(sys.argv) == 3:
        add_section_outlines(sys.argv[2])
    elif mode == 'pins' and len(sys.argv) == 3:
        add_pin_names(sys.argv[2])
    elif mode == 'revmark' and len(sys.argv) == 3:
        add_rev_mark(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
