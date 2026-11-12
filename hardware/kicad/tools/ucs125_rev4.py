"""Brings the routed UCS 125-87 rev 3 board to the rev 4 schematic, keeping every
placement and track the change does not touch.

`place` syncs the footprints and pad nets to the netlist, sets the wall parts
(EDGE_PARTS) and fixed spots (SPOTS), finds free spots for the small new parts
(SEARCH) and removes copper under every new pad. Route the open connections
afterwards with gridroute.py, then run the usual repair loop.

`labels` runs after routing: it hides the new parts' reference texts, prints each
header's function and reference beside its friction wall, and drops or moves the
silk labels of parts that left or moved.

Usage (KiCad's python):
    ucs125_rev4.py plan board.kicad_pcb     (dry run: prints the spots and conflicts)
    ucs125_rev4.py place board.kicad_pcb    (edits in place, once)
    ucs125_rev4.py labels board.kicad_pcb   (edits in place)
"""
import math
import sys

import pcbnew

import pcbmodels
from pcbnetlist import load_netlist
from spi_expander_board import clear_copper_under, load_footprint
from ucs125_board import HEIGHT, WIDTH, sync_parts

MM = pcbnew.FromMM
KEEP = []  # removed items stay referenced until the board is saved
OVERHANG = 3.0  # mating end past the board edge, as J11 and J12
PART_GAP = 0.1
COPPER_GAP = 0.15

# Wall parts: ref -> (edge, bottom side, centre along the edge, mating end past it)
EDGE_PARTS = {
    'J1': ('top', False, 17.07, OVERHANG),
    # body front on the edge, as it sat on the right wall: the actuator reaches 2.7 past
    'SW3': ('top', False, 86.2, 2.7),
    # general-purpose I/O block on the right wall, IO13 at the top
    'J20': ('right', True, 19.06, OVERHANG),
    'J16': ('right', False, 23.66, OVERHANG),
    'J17': ('right', True, 27.33, OVERHANG),
    'J18': ('right', False, 31.93, OVERHANG),
    'J19': ('right', True, 35.60, OVERHANG),
    'J5': ('bottom', True, 35.3, OVERHANG),
    'J13': ('bottom', True, 55.9, OVERHANG),
    # between J10 and J8, back to back with J4, so the RTD header stays put
    'J6': ('bottom', True, 77.4, OVERHANG),
    'J3': ('bottom', False, 61.5, OVERHANG),
    'J4': ('bottom', False, 74.85, OVERHANG),
}
EDGE_NORMALS = {'top': (0, -1), 'bottom': (0, 1), 'left': (-1, 0), 'right': (1, 0)}

# Fixed spots: ref -> (x, y, rotation, bottom side). The amplifier REM switch FETs
# take the spots of the old fan and pump drivers, which makes room for J6.
SPOTS = {
    'Q21': (70.0, 44.0, 0, True),
    'Q6': (76.0, 44.0, 0, True),
    # I/O block. Back side, a row below the board ID: the series array and the two
    # divider arrays going inboard, 1.5 mm apart and facing each other pin for pin.
    'RN3': (86.75, 27.4, 180, True),
    'RN4': (83.75, 27.4, 180, True),
    'RN5': (80.75, 27.4, 180, True),
    # One clamp per header in the strip between RN3 and the header pads, GND pad
    # towards a header GND pad where one is near (IO13's, U46, finds its own spot)
    'U45': (88.3, 25.6, 90, True),
    'U47': (88.3, 27.33, 270, True),
    'U48': (88.3, 29.75, 90, True),
    'U49': (88.3, 35.85, 270, True),
    # LED drivers, back side, where the front has no pads so vias can reach the LEDs.
    # Each has its decoupling capacitor at pin 3; IO13's divider sits at U44 pin 4.
    'U43': (85.3, 33.3, 0, True),
    'C303': (82.7, 32.4, 180, True),
    'U44': (85.4, 19.9, 0, True),
    'C304': (82.8, 19.9, 180, True),
    'R504': (82.8, 18.75, 180, True),
    'R503': (83.8, 17.3, 270, True),
    # front: one LED beside each header, its 3.3k just below it (IO12's to the right)
    'D85': (87.7, 19.1, 0, False),
    'D81': (87.7, 23.7, 0, False),
    'D82': (87.7, 27.3, 0, False),
    'D83': (87.7, 31.5, 0, False),
    'D84': (87.7, 35.5, 0, False),
    'R510': (87.5, 20.65, 270, False),
    'R506': (87.5, 25.25, 270, False),
    'R507': (87.5, 28.85, 270, False),
    'R508': (87.5, 33.05, 270, False),
    'R509': (88.8, 36.75, 180, False),
}

# Zones (x0, y0, x1, y1) with room for the small parts
IO_UPPER = (79.5, 14.9, 88.66, 22.3)  # back, above the board ID
GATES = (28.95, 20.7, 36.5, 26.6)  # back, beside U17's logic side, where ACS_CS runs
FAN_STRIP = (54.5, 47.0, 82.4, 50.6)  # front, the old header pin row
REM_PARTS = (68.0, 42.2, 81.6, 50.65)  # back, where Q26 / Q27 sat
LED_COLUMN = (81.6, 46.5, 92.0, 54.25)  # back, behind the status LED column
BUTTON = (82.5, 4.6, 92.0, 9.9)  # back, under SW3

# Small parts find their own spot, in this order:
# ref -> (bottom side, zone, target x y[, gap to other parts]).
SEARCH = {
    # the power button's clamp follows SW3
    'U34': (True, BUTTON, (88.2, 5.4)),
    # IO13 (J20): clamp and 100 R at the header
    'U46': (True, IO_UPPER, (88.0, 16.4), 0.4),
    'R505': (True, IO_UPPER, (87.9, 21.9), 0.4),
    # the BOOT capacitor steps aside for the tracks between the arrays and the op amp
    'C14': (True, (78.5, 29.4, 82.0, 32.7), (81.0, 30.9), 0.2),
    # ACS37800 bus gates at U17's logic pins
    'U41': (True, GATES, (30.6, 24.6), 0.3),
    'U42': (True, GATES, (33.4, 21.8), 0.3),
    'R501': (True, GATES, (30.0, 22.8), 0.3),
    'R502': (True, GATES, (34.0, 24.6), 0.3),
    'C301': (True, GATES, (30.6, 26.0), 0.3),
    'C302': (True, GATES, (34.0, 22.6), 0.3),
    # fan and pump: dual FET and arrays between the two headers
    'Q61': (False, FAN_STRIP, (72.0, 48.8)),
    'RN1': (False, FAN_STRIP, (69.4, 48.8)),
    'RN2': (False, FAN_STRIP, (66.5, 48.8)),
    # J6 takes R84's place: it stays beside D12, whose green die it feeds
    'R84': (True, LED_COLUMN, (84.0, 53.5)),
    # the amplifier REM switch's pull-up follows its FETs
    'R404': (True, REM_PARTS, (78.6, 46.4)),
}

# All copper of these nets goes: their far ends changed, or the net left the schematic
RIP_NETS = (
    'ACS_MOSI', 'ACS_SCK', 'ACS_MISO', 'Net-(J7-Pin_1)', 'Net-(Q26-G)', 'Net-(Q27-G)',
    # J6 and J19 sit on these two RTD runs: route them afresh, first
    '/Cold Head Temp/RTD_2', '/Cold Head Temp/RTD_3',
)
# A +3V3 run on the front crossed the spot the lower LED driver's vias and R508 need.
# The In2 pour carries +3V3 at both of its ends. (net, corner points)
RIP_RUNS = (('+3V3', ((83.52, 36.15), (87.51, 32.15), (90.27, 32.15), (91.0, 32.15))),)


def rect_of(items):
    """Bounding box (x0, y0, x1, y1) in mm of some board items; drawn shapes
    count to their centre line, not their stroke.
    """
    boxes = []
    for item in items:
        box = item.GetBoundingBox()
        half = item.GetWidth() // 2 if item.Type() == pcbnew.PCB_SHAPE_T else 0
        boxes.append((box.GetLeft() + half, box.GetTop() + half,
                      box.GetRight() - half, box.GetBottom() - half))
    return (
        min(box[0] for box in boxes) / 1e6,
        min(box[1] for box in boxes) / 1e6,
        max(box[2] for box in boxes) / 1e6,
        max(box[3] for box in boxes) / 1e6,
    )


def courtyard(footprint):
    layer = pcbnew.B_CrtYd if footprint.IsFlipped() else pcbnew.F_CrtYd
    lines = [item for item in footprint.GraphicalItems() if item.GetLayer() == layer]
    return rect_of(lines) if lines else rect_of([footprint])


def fab_box(footprint):
    layer = pcbnew.B_Fab if footprint.IsFlipped() else pcbnew.F_Fab
    return rect_of([
        item for item in footprint.GraphicalItems()
        if item.GetLayer() == layer and item.Type() == pcbnew.PCB_SHAPE_T
    ])


def holes(footprint):
    """(x, y, radius) of every drilled pad."""
    found = []
    for pad in footprint.Pads():
        drill = pad.GetDrillSize()
        if drill.x > 0:
            spot = pad.GetPosition()
            found.append((spot.x / 1e6, spot.y / 1e6, max(drill.x, drill.y) / 2e6))
    return found


def overlaps(first, second, gap=0.0):
    return (first[0] < second[2] + gap and second[0] < first[2] + gap
            and first[1] < second[3] + gap and second[1] < first[3] + gap)


def circle_in(rect, circle):
    x, y, radius = circle
    near_x = min(max(x, rect[0]), rect[2])
    near_y = min(max(y, rect[1]), rect[3])
    return math.hypot(x - near_x, y - near_y) < radius


def set_spot(footprint, x, y, rotation, bottom):
    if bottom != footprint.IsFlipped():
        footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    footprint.SetOrientationDegrees(rotation)
    footprint.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))


def edge_spot(footprint, edge, bottom, centre, overhang):
    """Puts a wall part's mating end `overhang` past its edge, centred at `centre`
    along it. The mating end is the fab outline's far side from the pads."""
    normal = EDGE_NORMALS[edge]
    for rotation in (0, 90, 180, 270):
        set_spot(footprint, 0, 0, rotation, bottom)
        pads = rect_of(list(footprint.Pads()))
        body = fab_box(footprint)
        reach = {
            (1, 0): body[2] - pads[2], (-1, 0): pads[0] - body[0],
            (0, 1): body[3] - pads[3], (0, -1): pads[1] - body[1],
        }
        if max(reach, key=reach.get) == normal:
            break
    if normal[0]:
        far = body[2] if normal[0] > 0 else body[0]
        wall = WIDTH if normal[0] > 0 else 0.0
        x = wall + normal[0] * overhang - far
        y = centre - (body[1] + body[3]) / 2
    else:
        far = body[3] if normal[1] > 0 else body[1]
        wall = HEIGHT if normal[1] > 0 else 0.0
        x = centre - (body[0] + body[2]) / 2
        y = wall + normal[1] * overhang - far
    set_spot(footprint, x, y, rotation, bottom)


class Occupancy:
    """Courtyards, holes and copper already on the board, for collision checks."""

    def __init__(self, board, skip=()):
        self.parts = {}
        for footprint in board.GetFootprints():
            ref = footprint.GetReference()
            if ref not in skip:
                self.add(footprint)
        # copper sampled every 0.1 mm into 1 mm cells: cell -> [(x, y, half width,
        # net, layer)], layer None for a via
        self.copper = {}
        for item in board.GetTracks():
            if item.Type() == pcbnew.PCB_VIA_T:
                spot = item.GetPosition()
                self.add_copper(spot.x / 1e6, spot.y / 1e6,
                                item.GetWidth(pcbnew.F_Cu) / 2e6, item.GetNetname(), None)
                continue
            start, end = item.GetStart(), item.GetEnd()
            steps = max(1, int(item.GetLength() / MM(0.1)))
            for step in range(steps + 1):
                self.add_copper(
                    (start.x + (end.x - start.x) * step / steps) / 1e6,
                    (start.y + (end.y - start.y) * step / steps) / 1e6,
                    item.GetWidth() / 2e6, item.GetNetname(), item.GetLayer(),
                )

    def add_copper(self, x, y, half, net, layer):
        self.copper.setdefault((int(x), int(y)), []).append((x, y, half, net, layer))

    def add(self, footprint):
        self.parts[footprint.GetReference()] = (
            footprint.IsFlipped(), courtyard(footprint), holes(footprint))

    def conflicts(self, footprint, inside_board=True, gap=0.0):
        """Parts whose courtyard (kept `gap` apart) or holes collide with this
        footprint."""
        return self.shape_conflicts(
            footprint.GetReference(), footprint.IsFlipped(), courtyard(footprint),
            holes(footprint), inside_board, gap)

    def shape_conflicts(self, ref, bottom, box, my_holes, inside_board=True, gap=0.0):
        found = []
        if inside_board and not (0.3 <= box[0] and box[2] <= WIDTH - 0.3
                                 and 0.3 <= box[1] and box[3] <= HEIGHT - 0.3):
            found.append('board edge')
        for other, (other_bottom, other_box, other_holes) in self.parts.items():
            if other == ref:
                continue
            if other_bottom == bottom and overlaps(box, other_box, gap):
                found.append(other)
            elif any(circle_in(box, hole) for hole in other_holes):
                found.append(other + ' hole')
            elif any(circle_in(other_box, hole) for hole in my_holes):
                found.append(other + ' under hole')
        return found

    def copper_under(self, footprint):
        """Nets of other tracks and vias that touch this footprint's pads."""
        return self.pads_copper(pad_shapes(footprint))

    def pads_copper(self, pads):
        """Nets of other copper touching pads given as (box, net, layers), where
        layers is None for a drilled pad."""
        nets = set()
        for box, pad_net, layers in pads:
            for column in range(int(box[0] - 1), int(box[2] + 1) + 1):
                for row in range(int(box[1] - 1), int(box[3] + 1) + 1):
                    for x, y, half, net, layer in self.copper.get((column, row), ()):
                        margin = half + COPPER_GAP
                        if net == pad_net or not (
                                box[0] - margin <= x <= box[2] + margin
                                and box[1] - margin <= y <= box[3] + margin):
                            continue
                        if layer is None or layers is None or layer in layers:
                            nets.add(net)
        return nets


def pad_shapes(footprint):
    """(box, net, copper layers or None if drilled) of every pad."""
    layers = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
    return [
        (rect_of([pad]), pad.GetNetname(),
         None if pad.GetDrillSize().x > 0
         else [layer for layer in layers if pad.IsOnLayer(layer)])
        for pad in footprint.Pads()
    ]


def shifted(box, x, y):
    return (box[0] + x, box[1] + y, box[2] + x, box[3] + y)


def find_spot(footprint, bottom, zone, target, occupancy, gap=PART_GAP):
    """Nearest spot to `target` inside `zone` with no courtyard, hole or copper
    clash. The footprint's shape is read once per rotation, then slid numerically.
    """
    step = 0.1
    spots = [
        (zone[0] + column * step, zone[1] + row * step)
        for column in range(int((zone[2] - zone[0]) / step) + 1)
        for row in range(int((zone[3] - zone[1]) / step) + 1)
    ]
    spots.sort(key=lambda spot: math.hypot(spot[0] - target[0], spot[1] - target[1]))
    shapes = {}
    for rotation in (0, 90):
        set_spot(footprint, 0, 0, rotation, bottom)
        shapes[rotation] = (courtyard(footprint), holes(footprint), pad_shapes(footprint))
    ref = footprint.GetReference()
    for x, y in spots:
        for rotation, (yard, drilled, pads) in shapes.items():
            box = shifted(yard, x, y)
            if not (zone[0] <= box[0] and box[2] <= zone[2]
                    and zone[1] <= box[1] and box[3] <= zone[3]):
                continue
            moved_holes = [(hole[0] + x, hole[1] + y, hole[2]) for hole in drilled]
            if occupancy.shape_conflicts(ref, bottom, box, moved_holes, gap=gap):
                continue
            if occupancy.pads_copper(
                    [(shifted(pad_box, x, y), net, layers) for pad_box, net, layers in pads]):
                continue
            return x, y, rotation
    return None


def on_run(item, corners):
    """True for a track joining two neighbouring corners, or a via on an inner one."""
    def at(point, corner):
        return abs(pcbnew.ToMM(point.x) - corner[0]) < 0.02 and abs(pcbnew.ToMM(point.y) - corner[1]) < 0.02

    if item.Type() == pcbnew.PCB_VIA_T:
        return any(at(item.GetPosition(), corner) for corner in corners[1:-1])
    start, end = item.GetStart(), item.GetEnd()
    return any(
        (at(start, a) and at(end, b)) or (at(start, b) and at(end, a))
        for a, b in zip(corners, corners[1:])
    )


def place(path, dry_run):
    board = pcbnew.LoadBoard(path)
    parts, nets = load_netlist()
    removed, added = sync_parts(board, parts, nets)
    print('removed', ' '.join(sorted(removed)))
    print('added or swapped', ' '.join(sorted(added)))
    ripped = 0
    for item in list(board.GetTracks()):
        if item.GetNetname() in RIP_NETS:
            KEEP.append(item)
            board.Remove(item)
            ripped += 1
    print('ripped', ripped, 'items of', ' '.join(RIP_NETS))
    for net, corners in RIP_RUNS:
        for item in list(board.GetTracks()):
            if item.GetNetname() == net and on_run(item, corners):
                KEEP.append(item)
                board.Remove(item)
    moved = set(EDGE_PARTS) | set(SPOTS) | set(SEARCH)
    unplaced = sorted(set(added) - moved)
    if unplaced:
        print('no spot planned for', ' '.join(unplaced))
        if not dry_run:
            raise SystemExit('placement is incomplete; nothing saved')
    occupancy = Occupancy(board, skip=moved)
    problems = 0
    for ref, (edge, bottom, centre, overhang) in EDGE_PARTS.items():
        footprint = board.FindFootprintByReference(ref)
        edge_spot(footprint, edge, bottom, centre, overhang)
        problems += report(footprint, occupancy, inside_board=False)
        occupancy.add(footprint)
    for ref, (x, y, rotation, bottom) in SPOTS.items():
        footprint = board.FindFootprintByReference(ref)
        set_spot(footprint, x, y, rotation, bottom)
        problems += report(footprint, occupancy)
        occupancy.add(footprint)
    for ref, (bottom, zone, target, *gap) in SEARCH.items():
        footprint = board.FindFootprintByReference(ref)
        spot = find_spot(footprint, bottom, zone, target, occupancy, *gap)
        if spot is None:
            print(f'{ref}: no free spot in {zone}')
            problems += 1
            continue
        set_spot(footprint, *spot, bottom)
        problems += report(footprint, occupancy)
        occupancy.add(footprint)
    print('problems:', problems)
    if dry_run:
        return problems
    if problems:
        raise SystemExit('placement has conflicts; nothing saved')
    for ref in sorted(moved):
        footprint = board.FindFootprintByReference(ref)
        pcbmodels.attach_missing_models(footprint)
        cleared = clear_copper_under(board, footprint)
        if cleared:
            print(f'{ref}: cleared copper of', ' '.join(sorted(cleared)))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    return 0


# Function printed beside each header's friction wall, where the board stays bare
HEADER_LABELS = {
    'J3': 'FAN', 'J4': 'PUMP', 'J5': 'FLOW', 'J6': 'NTC', 'J13': 'RELAY',
    'J16': 'IO5', 'J17': 'IO7', 'J18': 'IO11', 'J19': 'IO12', 'J20': 'IO13',
}
# Header labels: distance from the pin pads' centre line, and text height by length
LABEL_OUT = 6.95
LABEL_HEIGHTS = {3: 1.0, 4: 0.9}
# Silk labels of parts that left the board, or whose part moved away from them
STALE_LABELS = {
    'Q26', 'Q27', 'R3', 'R4', 'R5', 'R41', 'R42', 'R46', 'R47', 'BTN', 'J7', 'J7 BTN',
    'J3 FAN', 'J4 PUMP', 'J5 FLOW', 'J6 NTC', 'J13 RELAY', 'U34', 'Q21', 'Q6', 'R84', 'R404',
}
# Labels that follow their part or step aside for a new one:
# text -> new centre (x, y[, angle])
MOVED_LABELS = {
    'SW3 POWER': (77.2, 3.0), 'J1 USB': (11.0, 4.6), 'R24': (16.3, 7.9),
    'C67': (33.9, 27.0), 'J15 DISPLAY': (53.6, 57.3, 90), 'J10 RTD': (72.4, 51.5),
    'J8 AMP REM': (86.85, 59.9), 'Q24': (80.5, 32.05), 'R76': (83.1, 25.85),
    'SW2 BOOT': (86.0, 28.9, 90),
}
# Parts that were on the board before: their reference texts stay as they were
KEPT_PARTS = {'SW3', 'U34', 'Q21', 'Q6', 'R84', 'R404', 'C14'}


def header_point(footprint, along, out):
    """Board position of a header-local point: `along` the pin row from pin 1,
    `out` towards the mating end."""
    numbered = [pad for pad in footprint.Pads() if pad.GetNumber()]
    tabs = [pad for pad in footprint.Pads() if not pad.GetNumber()]
    first = next(pad for pad in numbered if pad.GetNumber() == '1').GetPosition()
    second = next(pad for pad in numbered if pad.GetNumber() == '2').GetPosition()
    row = ((second.x - first.x) / 2.54, (second.y - first.y) / 2.54)

    def centre(pads):
        return (sum(pad.GetPosition().x for pad in pads) / len(pads),
                sum(pad.GetPosition().y for pad in pads) / len(pads))

    pins, holds = centre(numbered), centre(tabs)
    length = math.hypot(holds[0] - pins[0], holds[1] - pins[1])
    mate = ((holds[0] - pins[0]) / length, (holds[1] - pins[1]) / length)
    return (pcbnew.VECTOR2I(int(first.x + along * row[0] + out * MM(1) * mate[0]),
                            int(first.y + along * row[1] + out * MM(1) * mate[1])),
            90 if abs(mate[1]) > abs(mate[0]) else 0)


def style_text(text, footprint, spot, angle, height):
    bottom = footprint.IsFlipped()
    text.SetLayer(pcbnew.B_SilkS if bottom else pcbnew.F_SilkS)
    text.SetVisible(True)
    text.SetTextSize(pcbnew.VECTOR2I(MM(height), MM(height)))
    text.SetTextThickness(MM(0.15 if height >= 1.0 else 0.1))
    text.SetMirrored(bottom)
    text.SetKeepUpright(False)
    text.SetTextAngleDegrees(angle)
    text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    text.SetPosition(spot)


def label_header(footprint, function):
    """Function left of the friction wall, reference right of it, centred in the
    two bare strips between the body and the board edge (footprint y 5.04 .. 9.04)."""
    span = (len([pad for pad in footprint.Pads() if pad.GetNumber()]) - 1) * 2.54
    label = next((field for field in footprint.GetFields() if field.GetName() == 'Label'), None)
    if label is None:
        label = pcbnew.PCB_FIELD(footprint, pcbnew.FIELD_T_USER, 'Label')
        footprint.Add(label)
    label.SetText(function)
    spot, angle = header_point(footprint, -1.57, LABEL_OUT)
    style_text(label, footprint, spot, angle, LABEL_HEIGHTS.get(len(function), 0.8))
    spot, angle = header_point(footprint, span + 1.57, LABEL_OUT)
    style_text(footprint.Reference(), footprint, spot, angle, 0.8)


def labels(path):
    board = pcbnew.LoadBoard(path)
    planned = set(EDGE_PARTS) | set(SPOTS) | set(SEARCH)
    for ref in sorted(planned - KEPT_PARTS):
        footprint = board.FindFootprintByReference(ref)
        footprint.Reference().SetVisible(False)
        footprint.Value().SetVisible(False)
    for ref, function in HEADER_LABELS.items():
        label_header(board.FindFootprintByReference(ref), function)
    dropped = moved = 0
    for drawing in list(board.GetDrawings()):
        if drawing.Type() != pcbnew.PCB_TEXT_T:
            continue
        text = drawing.GetText()
        if text in STALE_LABELS:
            KEEP.append(drawing)
            board.Remove(drawing)
            dropped += 1
        elif text in MOVED_LABELS:
            x, y, *angle = MOVED_LABELS[text]
            drawing.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            if angle:
                drawing.SetTextAngleDegrees(angle[0])
            moved += 1
    print('labels dropped', dropped, 'moved', moved)
    pcbnew.SaveBoard(path, board)


def report(footprint, occupancy, inside_board=True):
    spot = footprint.GetPosition()
    conflicts = occupancy.conflicts(footprint, inside_board)
    box = courtyard(footprint)
    print(
        f'{footprint.GetReference():5s} {"B" if footprint.IsFlipped() else "F"} '
        f'({spot.x / 1e6:.3f}, {spot.y / 1e6:.3f}) rot {footprint.GetOrientationDegrees():.0f} '
        f'courtyard [{box[0]:.2f} {box[1]:.2f} {box[2]:.2f} {box[3]:.2f}]'
        + (f'  CONFLICT {" ".join(conflicts)}' if conflicts else '')
        + f'  copper: {" ".join(sorted(occupancy.copper_under(footprint))) or "-"}'
    )
    return bool(conflicts)


def main():
    mode, path = sys.argv[1:3]
    if mode == 'labels':
        labels(path)
        return 0
    if mode not in ('plan', 'place'):
        raise SystemExit(__doc__)
    return 1 if place(path, mode == 'plan') else 0


if __name__ == '__main__':
    sys.exit(main())
