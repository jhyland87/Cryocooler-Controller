"""Module floorplan for gen_pcb.py: one labelled silkscreen box per schematic
module, and the placement constraint that keeps each module's parts inside it.

All lengths are millimetres (KiCad board coordinates, y grows downwards).
A region side that lies on or beyond the board edge is not drawn; the part
inset keeps parts clear of it.
"""

from pcbplace import Rect

# parts must sit this far inside a region edge; the silk line sits LINE_INSET
# inside it, leaving room for the label that straddles the line
PART_INSET = 0.5
# lines run on the region edge itself, so neighbouring sections share one
# wall (AGENTS.md PCB directives); regions within SHARED_WALL_GAP of each
# other are closed up to meet at the midpoint
LINE_INSET = 0.0
MIN_REGION_GAP = 0.0
SHARED_WALL_GAP = 1.0
LINE_WIDTH = 0.15
LABEL_SIZE = 1.0
LABEL_CHAR_WIDTH = 0.9
LABEL_GAP = 0.8
HOLE_CLEARANCE = 0.9
SEGMENT_STEP = 0.25

# schematic sheet -> module box; sheets mapped to the same name share a box.
# Debug parts (test points, rail LEDs) follow the part they sit beside.
MODULE_OF_SHEET = {
    'cryocooler': 'MCU & USB',
    'Indicators': 'INDICATORS',
    'Signal Generator': 'SIGNAL GENERATOR',
    'Amp Control': 'AMP CONTROL',
    'Amp Current': 'AMP CURRENT (ISOLATED)',
    'Rails +-15V': 'RAILS ±15V',
    'Compressor Relay': 'COMPRESSOR RELAY',
    'IMU': 'IMU CABLE',
    'Water Cooling I2C Bridge': 'WATER COOLING',
    'Water Cooling': 'WATER COOLING',
    'Cold Head Temp': 'COLD HEAD TEMP',
    'Rails 5V 3V3': 'POWER INPUT & RAILS',
    'System Current': 'POWER INPUT & RAILS',
    'Power Input': 'POWER INPUT & RAILS',
    'Power Button': 'POWER INPUT & RAILS',
    'Power Good': 'POWER GOOD',
    'Display': 'DISPLAY',
}

# The UCS 145-125 board (120 x 100 mm) uses both sides. Each module has one
# region set per side, keyed 'NAME@top' / 'NAME@bottom'; the top carries the
# connectors, the ESP32, tall parts, LEDs and the switching stages, the bottom
# the other ICs with most of the passives.
SIDE_SEPARATOR = '@'


def module_key(module, side):
    """Region key of a module on one board side."""
    return f'{module}{SIDE_SEPARATOR}{side}'


def split_key(key):
    """(module name, side) of a region key; plain names are top."""
    name, _, side = key.partition(SIDE_SEPARATOR)
    return name, side or 'top'

# module -> rectangles (overlap them by > 2 * LINE_INSET to build L shapes),
# the same on both sides. Corner squares (7.4 mm) and the antenna notch
# (x 74.5-93.5, y 0-6) stay free of parts through keep-outs in gen_pcb.py.
# Walls: left = amplifier (J11 / J12 / J9 / J8) and 12 V in, top = display
# FPC and ESP32 antenna, right = USB, IMU, PT1000, pump, bottom = panel
# button, relay, water cooling.
FLOORPLAN = {
    'AMP CURRENT (ISOLATED)': [
        Rect(-3, -3, 25.25, 40.5),
        Rect(19.5, 13, 33, 42),
        Rect(-3, 26, 13.5, 47.8),
    ],
    'DISPLAY': [Rect(25.25, -3, 60, 13)],
    'SIGNAL GENERATOR': [Rect(33, 13, 60, 58)],
    'MCU & USB': [Rect(60, -3, 100, 30), Rect(100, -3, 123, 21.5)],
    'IMU CABLE': [Rect(100, 21.5, 123, 42)],
    'INDICATORS': [Rect(60, 30, 100, 40)],
    'RAILS ±15V': [Rect(60, 40, 80, 72)],
    'POWER GOOD': [Rect(80, 40, 100, 72)],
    'COLD HEAD TEMP': [Rect(100, 42, 123, 64)],
    'AMP CONTROL': [Rect(-3, 62.5, 22, 85)],
    'POWER INPUT & RAILS': [
        Rect(13.5, 42, 33, 62.5),
        Rect(-3, 47.8, 13.5, 62.5),
        Rect(22, 62.5, 33, 103),
        Rect(-3, 85, 22, 103),
        Rect(33, 58, 60, 72),
        Rect(33, 72, 56, 82),
        Rect(33, 82, 44.2, 103),
    ],
    'COMPRESSOR RELAY': [Rect(44.2, 82, 56, 103)],
    'WATER COOLING': [Rect(56, 72, 100, 103), Rect(100, 64, 123, 103)],
}
MODULE_REGIONS = {
    module_key(module, side): [Rect(r.min_x, r.min_y, r.max_x, r.max_y) for r in rects]
    for side in ('top', 'bottom')
    for module, rects in FLOORPLAN.items()
}


def share_walls(regions):
    """Closes small gaps between same-side regions of different modules so
    their outlines coincide (one shared wall instead of two lines).
    """
    keys = list(regions)
    for index, first in enumerate(keys):
        for second in keys[index + 1 :]:
            if split_key(first)[1] != split_key(second)[1]:
                continue
            for rect_a in regions[first]:
                for rect_b in regions[second]:
                    overlap_y = min(rect_a.max_y, rect_b.max_y) - max(rect_a.min_y, rect_b.min_y)
                    overlap_x = min(rect_a.max_x, rect_b.max_x) - max(rect_a.min_x, rect_b.min_x)
                    if overlap_y > 0:
                        for left, right in ((rect_a, rect_b), (rect_b, rect_a)):
                            gap = right.min_x - left.max_x
                            if 0 < gap <= SHARED_WALL_GAP:
                                middle = (left.max_x + right.min_x) / 2
                                left.max_x = right.min_x = middle
                    if overlap_x > 0:
                        for upper, lower in ((rect_a, rect_b), (rect_b, rect_a)):
                            gap = lower.min_y - upper.max_y
                            if 0 < gap <= SHARED_WALL_GAP:
                                middle = (upper.max_y + lower.min_y) / 2
                                upper.max_y = lower.min_y = middle


share_walls(MODULE_REGIONS)


def module_of_sheet(sheet):
    """Returns the module box name of a schematic sheet, or None."""
    return MODULE_OF_SHEET.get(sheet)


# tighter part inset for the boxes that are very full
MODULE_PART_INSET = {}


def region_contains(module, rect):
    """True if a part rectangle fits inside one of the module's regions."""
    inset = MODULE_PART_INSET.get(module, PART_INSET)
    return any(
        rect.inside(region.inflated(-inset))
        for region in MODULE_REGIONS[module]
    )


def text_inside(module, rect):
    """True if a text box lies inside one of the module's regions, clear of
    the silk box line.
    """
    return any(
        rect.inside(region.inflated(-(LINE_INSET + 0.15)))
        for region in MODULE_REGIONS[module]
    )


def bump_rect(rect):
    """Region rectangle that wraps a label box with the silk line 0.3 mm
    outside it.
    """
    return rect.inflated(LINE_INSET + 0.3)


def bump_ok(module, rect):
    """True if the module's outline can bulge around a label box without
    coming within 1 mm (region to region) of another module's box.
    """
    bump = bump_rect(rect)
    side = split_key(module)[1]
    return all(
        rect_gap(bump, region) >= 1.0
        for name, regions in MODULE_REGIONS.items()
        if name != module and split_key(name)[1] == side
        for region in regions
    )


def text_level(module, rect):
    """0 if the label box is inside the module box, 1 if the outline can
    bulge around it, 2 if neither.
    """
    if text_inside(module, rect):
        return 0
    return 1 if bump_ok(module, rect) else 2


def rect_gap(first, second):
    """Distance between two rectangles (0 if they touch or overlap)."""
    delta_x = max(first.min_x - second.max_x, second.min_x - first.max_x, 0.0)
    delta_y = max(first.min_y - second.max_y, second.min_y - first.max_y, 0.0)
    return (delta_x**2 + delta_y**2) ** 0.5


def check_regions(board_rect):
    """Returns messages for regions that are too close to another module's
    region or stick out of the board by more than the edge allowance.
    """
    problems = []
    names = list(MODULE_REGIONS)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            if split_key(first)[1] != split_key(second)[1]:
                continue  # the two sides do not see each other
            for rect_a in MODULE_REGIONS[first]:
                for rect_b in MODULE_REGIONS[second]:
                    gap = rect_gap(rect_a, rect_b)
                    if gap < MIN_REGION_GAP - 1e-6:
                        problems.append(
                            f'regions {first} / {second} only {gap:.2f} mm apart'
                        )
    for name, rects in MODULE_REGIONS.items():
        for rect in rects:
            if not rect.inflated(-PART_INSET).overlaps(board_rect):
                problems.append(f'region {name} is off the board')
    return problems


# extra rectangles that bulge a module's outline around labels that had no
# room inside the box: module -> [Rect] (same meaning as MODULE_REGIONS)
EXTRA_REGIONS = {}


def _line_rects(module):
    return [
        region.inflated(-LINE_INSET)
        for region in MODULE_REGIONS[module] + EXTRA_REGIONS.get(module, [])
    ]


def _inside_strictly(point, rect, tolerance=1e-6):
    return (
        rect.min_x + tolerance < point[0] < rect.max_x - tolerance
        and rect.min_y + tolerance < point[1] < rect.max_y - tolerance
    )


def _breakpoints(values, low, high):
    return sorted({low, high, *[v for v in values if low < v < high]})


# shorter label texts to fall back on when the full name has no room
LABEL_ALTERNATIVES = {
    'AMP CONTROL': ['AMP CONTROL', 'AMP CTRL'],
    'COMPRESSOR RELAY': ['COMPRESSOR RELAY', 'COMP RELAY', 'RELAY'],
}


def label_texts(module):
    """Label texts to try for a module, longest first."""
    name = split_key(module)[0]
    return LABEL_ALTERNATIVES.get(name, [name])


def label_width(text):
    """Estimated width of a label text (mm)."""
    return len(text) * LABEL_CHAR_WIDTH * LABEL_SIZE + 0.4


def label_candidates(module, text, board_rect):
    """Yields (left_x, line_y) spots for the module's label on a horizontal
    border of one of its regions, top borders first, left to right.
    """
    drawable = board_rect.inflated(-0.4)
    width = label_width(text)
    rects = _line_rects(module)
    for side in ('top', 'bottom'):
        for rect in rects:
            line_y = rect.min_y if side == 'top' else rect.max_y
            if not drawable.min_y <= line_y <= drawable.max_y:
                continue
            left_x = max(rect.min_x + 1.5, 3.0)
            while left_x + width <= min(rect.max_x - 1.0, drawable.max_x):
                corners = (
                    (left_x, line_y - 0.6), (left_x + width, line_y - 0.6),
                    (left_x, line_y + 0.6), (left_x + width, line_y + 0.6),
                    (left_x + width / 2, line_y),
                )
                if not any(_avoided(module, corner) for corner in corners):
                    yield left_x, line_y
                left_x += 1.0


def covered(segments, line_y, start_x, end_x):
    """True if horizontal drawn segments at line_y span [start_x, end_x]."""
    spans = sorted(
        (min(a[0], b[0]), max(a[0], b[0]))
        for a, b in segments
        if abs(a[1] - line_y) < 1e-6 and abs(b[1] - line_y) < 1e-6
    )
    reach = start_x
    for low, high in spans:
        if low > reach + 1e-6:
            break
        reach = max(reach, high)
    return reach >= end_x - 1e-6


def text_hits_hole(left_x, line_y, width, holes):
    """True if the label box comes within the hole clearance of a hole."""
    for hole_x, hole_y, hole_radius in holes:
        nearest_x = min(max(hole_x, left_x), left_x + width)
        nearest_y = min(max(hole_y, line_y - 0.5), line_y + 0.5)
        distance = ((hole_x - nearest_x) ** 2 + (hole_y - nearest_y) ** 2) ** 0.5
        if distance < hole_radius + HOLE_CLEARANCE:
            return True
    return False


# areas where no box line or label may be drawn, per side ('top' /
# 'bottom'): board cut-outs and pads (with the silk-to-pad clearance); set
# by gen_pcb.py before the boxes are drawn
SILK_AVOID = {'top': [], 'bottom': []}


def _avoided(module, point):
    side = split_key(module)[1]
    return any(
        rect.min_x <= point[0] <= rect.max_x and rect.min_y <= point[1] <= rect.max_y
        for rect in SILK_AVOID.get(side, [])
    )


def outline_segments(module, board_rect, holes, label=None):
    """Silkscreen line segments tracing the union of the module's regions,
    clipped to the board, broken around the label (text, left_x, line_y)
    and around mounting holes.

    Returns a list of ((x0, y0), (x1, y1)).
    """
    rects = _line_rects(module)
    drawable = board_rect.inflated(-0.4)
    label_cut = None
    if label is not None:
        text, left_x, line_y = label
        label_cut = (
            line_y,
            left_x - LABEL_GAP,
            left_x + label_width(text) + LABEL_GAP,
        )
    raw = []
    for index, rect in enumerate(rects):
        others = [other for j, other in enumerate(rects) if j != index]
        sides = (
            ('h', rect.min_y, rect.min_x, rect.max_x),
            ('h', rect.max_y, rect.min_x, rect.max_x),
            ('v', rect.min_x, rect.min_y, rect.max_y),
            ('v', rect.max_x, rect.min_y, rect.max_y),
        )
        for orientation, fixed, start, end in sides:
            if orientation == 'h':
                cuts = [o.min_x for o in others] + [o.max_x for o in others]
            else:
                cuts = [o.min_y for o in others] + [o.max_y for o in others]
            points = _breakpoints(cuts, start, end)
            for low, high in zip(points, points[1:]):
                mid = (low + high) / 2
                point = (mid, fixed) if orientation == 'h' else (fixed, mid)
                if any(_inside_strictly(point, other) for other in others):
                    continue
                first_end = (low, fixed) if orientation == 'h' else (fixed, low)
                second_end = (
                    (high, fixed) if orientation == 'h' else (fixed, high)
                )
                raw.append((first_end, second_end))
    segments = []
    for first_end, second_end in raw:
        length = max(
            abs(second_end[0] - first_end[0]), abs(second_end[1] - first_end[1])
        )
        steps = max(1, int(round(length / SEGMENT_STEP)))
        run_start = None
        previous = None
        for step in range(steps):
            fraction = (step + 0.5) / steps
            point = (
                first_end[0] + (second_end[0] - first_end[0]) * fraction,
                first_end[1] + (second_end[1] - first_end[1]) * fraction,
            )
            keep = (
                not _avoided(module, point)
                and drawable.min_x <= point[0] <= drawable.max_x
                and drawable.min_y <= point[1] <= drawable.max_y
                and not any(
                    (point[0] - hole_x) ** 2 + (point[1] - hole_y) ** 2
                    < (hole_radius + HOLE_CLEARANCE) ** 2
                    for hole_x, hole_y, hole_radius in holes
                )
            )
            if keep and label_cut is not None:
                cut_y, cut_from, cut_to = label_cut
                if abs(point[1] - cut_y) < 1e-6 and cut_from < point[0] < cut_to:
                    keep = False
            begin = (
                first_end[0] + (second_end[0] - first_end[0]) * step / steps,
                first_end[1] + (second_end[1] - first_end[1]) * step / steps,
            )
            finish = (
                first_end[0] + (second_end[0] - first_end[0]) * (step + 1) / steps,
                first_end[1] + (second_end[1] - first_end[1]) * (step + 1) / steps,
            )
            if keep and run_start is None:
                run_start = begin
            if keep:
                previous = finish
            if not keep and run_start is not None:
                segments.append((run_start, previous))
                run_start = None
        if run_start is not None:
            segments.append((run_start, previous))
    return segments


def board_edge_rect(width, height):
    return Rect(0.0, 0.0, width, height)
