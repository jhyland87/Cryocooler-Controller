"""Module floorplan for gen_pcb.py: one labelled silkscreen box per schematic
module, and the placement constraint that keeps each module's parts inside it.

All lengths are millimetres (KiCad board coordinates, y grows downwards).
A region side that lies on or beyond the board edge is not drawn; the part
inset keeps parts clear of it.
"""

from pcbplace import Rect

# parts must sit this far inside a region edge. Neighbouring regions touch, so
# two modules share one silk line (LINE_INSET 0 puts the line on the region
# edge); the label straddles that line.
PART_INSET = 0.5
LINE_INSET = 0.0
# regions of different modules may touch but not overlap
MIN_REGION_GAP = 0.0
LINE_WIDTH = 0.15
LABEL_SIZE = 1.0
LABEL_CHAR_WIDTH = 0.9
LABEL_GAP = 0.8
HOLE_CLEARANCE = 0.9
SEGMENT_STEP = 0.25

# schematic sheet -> module box: one box per sheet. Debug parts (test points,
# rail LEDs) and the supply jumpers follow the part they sit beside.
MODULE_OF_SHEET = {
    'cryocooler': 'MCU & USB',
    'Indicators': 'INDICATORS',
    'Signal Generator': 'SIGNAL GENERATOR',
    'Amp Control': 'AMP CONTROL',
    'Amp Current': 'AMP CURRENT (ISOLATED)',
    'Rails +-15V': 'RAILS ±15V',
    'Power Good': 'POWER GOOD',
    'Compressor Relay': 'COMP RELAY',
    'IMU': 'IMU',
    'Water Cooling I2C Bridge': 'I2C BRIDGE',
    'Water Cooling': 'WATER COOLING',
    'Cold Head Temp': 'COLD HEAD',
    'Rails 5V 3V3': 'RAILS 5V/3V3',
    'System Current': 'SYSTEM CURRENT',
    'Power Input': 'POWER IN',
    'Power Button': 'POWER BUTTON',
}

# Board is 100 x 62 mm (Phoenix UCS 125-87 PCB). Top side: connectors, ICs,
# inductors, LEDs, buttons; module -> rectangles (overlapping rectangles of one
# module build L shapes).
MODULE_REGIONS = {
    'AMP CURRENT (ISOLATED)': [Rect(-3, -3, 33, 37)],
    'AMP CONTROL': [Rect(33, -3, 56, 13)],
    'SIGNAL GENERATOR': [Rect(33, 13, 56, 26), Rect(52, 21, 61.5, 26)],
    'RAILS 5V/3V3': [Rect(33, 26, 56, 37)],
    'MCU & USB': [
        Rect(56, -3, 89.9, 21),
        Rect(89.5, -3, 103, 20),
        Rect(70.2, -3, 89.9, 30),
    ],
    'IMU': [Rect(89.9, 20, 103, 31.5)],
    'INDICATORS': [Rect(61.5, 21, 70.2, 30.5), Rect(56, 26, 70.2, 30.5)],
    'RAILS ±15V': [Rect(56, 30.5, 84, 40.5), Rect(56, 40, 69, 48)],
    'COLD HEAD': [Rect(84, 31.5, 103, 40.5)],
    'POWER IN': [Rect(-3, 37, 22, 65)],
    'POWER BUTTON': [Rect(22, 37, 40.5, 49.7), Rect(22, 49.7, 39.5, 65)],
    'COMP RELAY': [Rect(39.5, 49.7, 47, 65), Rect(40.5, 48, 47, 49.7)],
    'SYSTEM CURRENT': [Rect(40.5, 37, 56, 48)],
    'POWER GOOD': [Rect(69, 40.5, 80, 48)],
    'WATER COOLING': [Rect(47, 48, 80, 65), Rect(80, 40.5, 103, 65)],
}

# Bottom side: passives, test points and the ICs moved under their module.
# Modules missing here use their top regions. Under the right-angle
# connectors only their pin rows go through, so the bridge and power-good
# circuits sit there.
MODULE_REGIONS_BOTTOM = {
    'MCU & USB': [
        Rect(70.5, -3, 89.9, 25),
        Rect(89.5, -3, 103, 17),
        Rect(86, 25, 89.9, 30.5),
    ],
    'AMP CONTROL': [Rect(33, -3, 56, 14.5)],
    'SIGNAL GENERATOR': [Rect(33, 14.5, 56, 29), Rect(56, 6.75, 70.5, 21)],
    'RAILS 5V/3V3': [Rect(33, 29, 56, 37)],
    'IMU': [Rect(89.9, 17, 103, 30.5)],
    'INDICATORS': [Rect(56, 21, 70.5, 30.5)],
    'COLD HEAD': [Rect(84, 30.5, 103, 50)],
    'RAILS ±15V': [
        Rect(56, 30.5, 84, 40.5),
        Rect(70.5, 25, 86, 30.5),
        Rect(51, 40, 78, 48),
    ],
    'POWER IN': [Rect(-3, 37, 11, 65)],
    'POWER BUTTON': [Rect(11, 37, 27, 65)],
    'COMP RELAY': [Rect(27, 48, 43, 65)],
    'SYSTEM CURRENT': [Rect(27, 37, 51, 48), Rect(51, 37, 56, 40)],
    'I2C BRIDGE': [Rect(43, 48, 65.5, 65)],
    'POWER GOOD': [Rect(65.5, 48, 81, 65)],
    'WATER COOLING': [
        Rect(81, 50, 103, 65),
        Rect(78, 40.5, 84, 48),
        Rect(81, 48, 84, 50),
    ],
}


def regions(module, side='F'):
    """Rectangles of a module's box on one side ('F' top, 'B' bottom)."""
    if side == 'B':
        return MODULE_REGIONS_BOTTOM.get(module, MODULE_REGIONS.get(module, []))
    return MODULE_REGIONS.get(module, [])


def modules(side='F'):
    """Modules that have a box on the given side."""
    names = list(MODULE_REGIONS)
    if side == 'B':
        names += [m for m in MODULE_REGIONS_BOTTOM if m not in names]
    return names


def module_of_sheet(sheet):
    """Returns the module box name of a schematic sheet, or None."""
    return MODULE_OF_SHEET.get(sheet)


# part inset for the boxes that are very full
MODULE_PART_INSET = {
    'IMU': 0.15,
    'WATER COOLING': 0.3,
}


def region_contains(module, rect, side='F'):
    """True if a part rectangle fits inside one of the module's regions."""
    inset = MODULE_PART_INSET.get(module, PART_INSET)
    return any(
        rect.inside(region.inflated(-inset))
        for region in regions(module, side)
    )


def text_inside(module, rect, side='F'):
    """True if a text box lies inside one of the module's regions, clear of
    the silk box line.
    """
    return any(
        rect.inside(region.inflated(-(LINE_INSET + 0.15)))
        for region in regions(module, side)
    )


def bump_rect(rect):
    """Region rectangle that wraps a label box with the silk line 0.3 mm
    outside it.
    """
    return rect.inflated(LINE_INSET + 0.3)


def bump_ok(module, rect, side='F'):
    """True if the module's outline can bulge around a label box without
    coming within 1 mm (region to region) of another module's box.
    """
    bump = bump_rect(rect)
    return all(
        rect_gap(bump, region) >= 1.0
        for name in modules(side)
        if name != module
        for region in regions(name, side)
    )


def text_level(module, rect, side='F'):
    """0 if the label box is inside the module box, 1 if the outline can
    bulge around it, 2 if neither.
    """
    if text_inside(module, rect, side):
        return 0
    return 1 if bump_ok(module, rect, side) else 2


def rect_gap(first, second):
    """Distance between two rectangles (0 if they touch or overlap)."""
    delta_x = max(first.min_x - second.max_x, second.min_x - first.max_x, 0.0)
    delta_y = max(first.min_y - second.max_y, second.min_y - first.max_y, 0.0)
    return (delta_x**2 + delta_y**2) ** 0.5


def check_regions(board_rect, side='F'):
    """Returns messages for regions of different modules that overlap, or
    that stick out of the board by more than the edge allowance.
    """
    problems = []
    names = modules(side)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            for rect_a in regions(first, side):
                for rect_b in regions(second, side):
                    if rect_a.inflated(-1e-6).overlaps(rect_b.inflated(-1e-6)):
                        problems.append(
                            f'{side} regions {first} / {second} overlap'
                        )
    for name in names:
        for rect in regions(name, side):
            if not rect.inflated(-PART_INSET).overlaps(board_rect):
                problems.append(f'{side} region {name} is off the board')
    return problems


# extra rectangles that bulge a module's outline around labels that had no
# room inside the box: module -> [Rect] (same meaning as MODULE_REGIONS)
EXTRA_REGIONS = {}


def _line_rects(module, side='F'):
    return [
        region.inflated(-LINE_INSET)
        for region in regions(module, side)
        + EXTRA_REGIONS.get((module, side), [])
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
    'AMP CURRENT (ISOLATED)': ['AMP CURRENT (ISOLATED)', 'AMP CURRENT (ISO)'],
    'SIGNAL GENERATOR': ['SIGNAL GENERATOR', 'SIGNAL GEN'],
    'SYSTEM CURRENT': ['SYSTEM CURRENT', 'SYS CURRENT', 'SYS I'],
    'POWER BUTTON': ['POWER BUTTON', 'PWR BUTTON', 'BUTTON'],
    'POWER IN': ['POWER IN', 'PWR IN'],
    'WATER COOLING': ['WATER COOLING', 'WATER COOL', 'WATER'],
    'COMP RELAY': ['COMP RELAY', 'RELAY'],
    'POWER GOOD': ['POWER GOOD', 'PWR GOOD', 'PGOOD'],
    'COLD HEAD': ['COLD HEAD', 'CH TEMP'],
}


def label_texts(module):
    """Label texts to try for a module, longest first."""
    return LABEL_ALTERNATIVES.get(module, [module])


# gen_pcb sets this to a function that measures a label text with pcbnew
measure_label = None


def label_width(text):
    """Width of a label text (mm): measured when gen_pcb provides a
    measurer, else estimated.
    """
    if measure_label is not None:
        return measure_label(text) + 0.4
    return len(text) * LABEL_CHAR_WIDTH * LABEL_SIZE + 0.4


def label_candidates(module, text, board_rect, side='F'):
    """Yields (left_x, line_y) spots for the module's label on a horizontal
    border of one of its regions, top borders first, left to right.
    """
    drawable = board_rect.inflated(-0.4)
    width = label_width(text)
    rects = _line_rects(module, side)
    for side in ('top', 'bottom'):
        for rect in rects:
            line_y = rect.min_y if side == 'top' else rect.max_y
            if not drawable.min_y <= line_y <= drawable.max_y:
                continue
            left_x = max(rect.min_x + 1.5, 3.0)
            while left_x + width <= min(rect.max_x - 1.0, drawable.max_x):
                yield left_x, line_y
                left_x += 1.0


def covered_vertical(segments, line_x, start_y, end_y):
    """True if vertical drawn segments at line_x span [start_y, end_y]."""
    flipped = [((a[1], a[0]), (b[1], b[0])) for a, b in segments]
    return covered(flipped, line_x, start_y, end_y)


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
        nearest_y = min(max(hole_y, line_y - 0.9), line_y + 0.9)
        distance = ((hole_x - nearest_x) ** 2 + (hole_y - nearest_y) ** 2) ** 0.5
        if distance < hole_radius + HOLE_CLEARANCE:
            return True
    return False


def outline_segments(module, board_rect, holes, labels=(), side='F',
                     keepouts=()):
    """Silkscreen line segments tracing the union of the module's regions,
    clipped to the board, broken around every module label on the side (a
    shared border carries its neighbour's label too), around mounting holes
    and out of keep-out rectangles. A label is (text, left_x, line_y) on a
    horizontal border or (text, line_x, top_y, 'v') running up a vertical one.

    Returns a list of ((x0, y0), (x1, y1)).
    """
    rects = _line_rects(module, side)
    drawable = board_rect.inflated(-0.4)
    label_cuts = []
    for text, start_x, start_y, *vertical in labels:
        length = label_width(text) + LABEL_GAP
        if vertical:
            label_cuts.append(('v', start_x, start_y - LABEL_GAP, start_y + length))
        else:
            label_cuts.append(('h', start_y, start_x - LABEL_GAP, start_x + length))
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
                drawable.min_x <= point[0] <= drawable.max_x
                and drawable.min_y <= point[1] <= drawable.max_y
                and not any(
                    (point[0] - hole_x) ** 2 + (point[1] - hole_y) ** 2
                    < (hole_radius + HOLE_CLEARANCE) ** 2
                    for hole_x, hole_y, hole_radius in holes
                )
            )
            if keep and any(
                (
                    abs(point[1] - fixed_at) < 1e-6 and cut_from < point[0] < cut_to
                    if kind == 'h'
                    else abs(point[0] - fixed_at) < 1e-6
                    and cut_from < point[1] < cut_to
                )
                for kind, fixed_at, cut_from, cut_to in label_cuts
            ):
                keep = False
            if keep and any(
                k.min_x < point[0] < k.max_x and k.min_y < point[1] < k.max_y
                for k in keepouts
            ):
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
