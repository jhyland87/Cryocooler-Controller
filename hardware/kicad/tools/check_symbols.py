#!/usr/bin/env python3
"""Checks schematic symbols on every sheet: bodies must not overlap (pins are
ignored, so a symbol may sit on the end of another's pin), power symbols stay
unrotated, so grounds point down and supplies up, no wire touches a power symbol
except the one that feeds it, and no wire runs through another symbol's body.
Usage: check_symbols.py root.kicad_sch  Exits non-zero on any problem.
"""

import math
import re
import sys
from pathlib import Path

CLEARANCE_MM = 0.05


def parse(text):
    """Parses KiCad S-expressions into nested lists of strings."""
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+', text)
    stack, current = [], []
    for token in tokens:
        if token == '(':
            stack.append(current)
            current = []
        elif token == ')':
            parent = stack.pop()
            parent.append(current)
            current = parent
        else:
            current.append(token.strip('"') if token.startswith('"') else token)
    return current[0]


def children(node, name):
    return [item for item in node[1:] if isinstance(item, list) and item and item[0] == name]


def body_points(node, points):
    """Collects drawn-shape coordinates, skipping pins and text."""
    for item in node[1:]:
        if not isinstance(item, list) or not item:
            continue
        if item[0] in ('pin', 'property', 'text'):
            continue
        if item[0] in ('xy', 'start', 'end', 'mid', 'center'):
            points.append((float(item[1]), float(item[2])))
        if item[0] == 'circle':
            center = children(item, 'center')[0]
            radius = float(children(item, 'radius')[0][1])
            points.extend((float(center[1]) + dx, float(center[2]) + dy)
                          for dx, dy in ((radius, radius), (-radius, -radius)))
        body_points(item, points)


def library_boxes(tree):
    """Maps lib_id to the bounding box of its drawn body, in symbol coordinates."""
    boxes = {}
    for library in children(tree, 'lib_symbols'):
        for symbol in children(library, 'symbol'):
            points = []
            body_points(symbol, points)
            if points:
                xs, ys = zip(*points)
                boxes[symbol[1]] = (min(xs), min(ys), max(xs), max(ys))
    return boxes


def collect_pins(node, pins):
    for item in node[1:]:
        if not isinstance(item, list) or not item:
            continue
        if item[0] == 'pin':
            at = children(item, 'at')[0]
            pins.append((float(at[1]), float(at[2])))
        elif item[0] == 'symbol':
            collect_pins(item, pins)


def placed_point(local_x, local_y, x, y, angle, mirror):
    # Library Y points up, sheet Y points down
    if mirror == 'x':
        local_y = -local_y
    elif mirror == 'y':
        local_x = -local_x
    radians = math.radians(angle)
    return (x + local_x * math.cos(radians) - local_y * math.sin(radians),
            y - local_x * math.sin(radians) - local_y * math.cos(radians))


def pin_tips(tree, lib_id, x, y, angle, mirror):
    pins = []
    for library in children(tree, 'lib_symbols'):
        for symbol in children(library, 'symbol'):
            if symbol[1] == lib_id:
                collect_pins(symbol, pins)
    return [placed_point(px, py, x, y, angle, mirror) for px, py in pins]


def placed_box(box, x, y, angle, mirror):
    corners = [placed_point(local_x, local_y, x, y, angle, mirror)
               for local_x, local_y in ((box[0], box[1]), (box[2], box[3]),
                                        (box[0], box[3]), (box[2], box[1]))]
    xs, ys = zip(*corners)
    return min(xs), min(ys), max(xs), max(ys)


def turned_power_symbols(path):
    found = []
    for symbol in children(parse(path.read_text()), 'symbol'):
        at = children(symbol, 'at')[0]
        if children(symbol, 'lib_id')[0][1].startswith('power:') and float(at[3]) != 0:
            found.append((path.name, children(symbol, 'lib_id')[0][1], at[1], at[2], at[3]))
    return found


def segment_hits_box(start, end, box):
    x0, x1 = sorted((start[0], end[0]))
    y0, y1 = sorted((start[1], end[1]))
    return (x0 <= box[2] + CLEARANCE_MM and box[0] - CLEARANCE_MM <= x1
            and y0 <= box[3] + CLEARANCE_MM and box[1] - CLEARANCE_MM <= y1)


def wires_touching_power_symbols(path):
    tree = parse(path.read_text())
    boxes = library_boxes(tree)
    wires = []
    for wire in children(tree, 'wire'):
        points = children(children(wire, 'pts')[0], 'xy')
        wires.append(((float(points[0][1]), float(points[0][2])),
                      (float(points[1][1]), float(points[1][2]))))
    found = []
    for symbol in children(tree, 'symbol'):
        lib_id = children(symbol, 'lib_id')[0][1]
        if not lib_id.startswith('power:') or lib_id not in boxes:
            continue
        at = children(symbol, 'at')[0]
        pin = (float(at[1]), float(at[2]))
        box = placed_box(boxes[lib_id], pin[0], pin[1], float(at[3]), '')
        for start, end in wires:
            if pin in (start, end):
                continue
            if segment_hits_box(start, end, box):
                found.append((path.name, lib_id, 'touched by wire', start, end))
    return found


def wires_through_bodies(path):
    tree = parse(path.read_text())
    boxes = library_boxes(tree)
    wires = []
    for wire in children(tree, 'wire'):
        points = children(children(wire, 'pts')[0], 'xy')
        wires.append(((float(points[0][1]), float(points[0][2])),
                      (float(points[1][1]), float(points[1][2]))))
    found = []
    for symbol in children(tree, 'symbol'):
        lib_id = children(symbol, 'lib_id')[0][1]
        if lib_id.startswith('power:') or lib_id not in boxes:
            continue
        at = children(symbol, 'at')[0]
        mirror = children(symbol, 'mirror')
        box = placed_box(boxes[lib_id], float(at[1]), float(at[2]), float(at[3]),
                         mirror[0][1] if mirror else '')
        inner = (box[0] + 0.2, box[1] + 0.2, box[2] - 0.2, box[3] - 0.2)
        reference = next(p[2] for p in children(symbol, 'property') if p[1] == 'Reference')
        tips = pin_tips(tree, lib_id, float(at[1]), float(at[2]), float(at[3]),
                        mirror[0][1] if mirror else '')
        for start, end in wires:
            if not segment_hits_box(start, end, inner):
                continue
            # A wire ending on the symbol's own pin is fine, even inside its box
            if any(math.dist(point, tip) < 0.01 for point in (start, end) for tip in tips):
                continue
            found.append((path.name, reference, lib_id, 'crossed by wire', start, end))
    return found


def sheet_overlaps(path):
    tree = parse(path.read_text())
    boxes = library_boxes(tree)
    placed = []
    for symbol in children(tree, 'symbol'):
        lib_id = children(symbol, 'lib_id')[0][1]
        if lib_id not in boxes:
            continue
        at = children(symbol, 'at')[0]
        mirror = children(symbol, 'mirror')
        reference = next(p[2] for p in children(symbol, 'property') if p[1] == 'Reference')
        placed.append((reference, lib_id, placed_box(boxes[lib_id], float(at[1]), float(at[2]),
                                                     float(at[3]) if len(at) > 3 else 0.0,
                                                     mirror[0][1] if mirror else '')))
    found = []
    for index, (ref_a, lib_a, a) in enumerate(placed):
        for ref_b, lib_b, b in placed[index + 1:]:
            if (a[0] < b[2] - CLEARANCE_MM and b[0] < a[2] - CLEARANCE_MM
                    and a[1] < b[3] - CLEARANCE_MM and b[1] < a[3] - CLEARANCE_MM):
                found.append((path.name, ref_a, lib_a, ref_b, lib_b, round(a[0], 2), round(a[1], 2)))
    return found


def main():
    root = Path(sys.argv[1])
    paths = [root, *sorted((root.parent / 'sheets').glob('*.kicad_sch'))]
    overlaps = [overlap for path in paths for overlap in sheet_overlaps(path)]
    turned = [symbol for path in paths for symbol in turned_power_symbols(path)]
    touching = [hit for path in paths for hit in wires_touching_power_symbols(path)]
    crossed = [hit for path in paths for hit in wires_through_bodies(path)]
    for problem in overlaps + turned + touching + crossed:
        print(*problem)
    print(f'symbol overlap check: {len(overlaps)} overlaps')
    print(f'power symbol direction check: {len(turned)} turned')
    print(f'power symbol wire check: {len(touching)} touching')
    print(f'symbol body wire check: {len(crossed)} crossed')
    return 1 if overlaps or turned or touching or crossed else 0


if __name__ == '__main__':
    sys.exit(main())
