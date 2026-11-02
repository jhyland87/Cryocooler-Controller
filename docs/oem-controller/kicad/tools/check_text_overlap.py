"""
@file check_text_overlap.py
@brief Find text that overlaps text or lines, and wires that run through symbol bodies,
       in KiCad SVG exports.

KiCad plots every text as a `<g class="stroked-text">` group of line strokes, so the
real glyph extents are known. A text is reported when its glyph box (shrunk by a small
margin) overlaps another text's box or is crossed by any other stroke: a wire, symbol
outline, pin, label flag or the sheet frame. A wire (KiCad green) that passes through the
inside of a symbol body (its pale-yellow fill) is reported too.
Usage: python3 -I check_text_overlap.py SVG_DIR   (from `kicad-cli sch export svg`)
"""

import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = '{http://www.w3.org/2000/svg}'
MARGIN = 0.06  # fraction of the smaller box side ignored at each edge (stroke width, pin offsets)


def parse_transform(text, matrix):
    """Apply an SVG transform attribute (translate/scale/rotate) to a 2x3 matrix."""
    for name, args in re.findall(r'(\w+)\(([^)]*)\)', text or ''):
        values = [float(v) for v in re.split(r'[ ,]+', args.strip())]
        if name == 'translate':
            step = (1, 0, 0, 1, values[0], values[1] if len(values) > 1 else 0)
        elif name == 'scale':
            step = (values[0], 0, 0, values[-1], 0, 0)
        elif name == 'rotate':
            angle = math.radians(values[0])
            cos, sin = math.cos(angle), math.sin(angle)
            cx, cy = (values[1], values[2]) if len(values) == 3 else (0, 0)
            step = (cos, sin, -sin, cos, cx - cos * cx + sin * cy, cy - sin * cx - cos * cy)
        else:
            continue
        a, b, c, d, e, f = matrix
        a2, b2, c2, d2, e2, f2 = step
        matrix = (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2,
                  a * e2 + c * f2 + e, b * e2 + d * f2 + f)
    return matrix


def apply(matrix, x, y):
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def path_segments(element, matrix):
    """Line segments of an M/L path, a rect outline or a circle (as a polygon)."""
    tag = element.tag.replace(NS, '')
    points_list = []
    if tag == 'path':
        # M/L with optional commas and implicit line-tos after M; Z closes the subpath
        current = []
        tokens = re.findall(r'[MLZAmlza]|-?[\d.]+', element.get('d', ''))
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in 'Aa':
                # arc (inductor bumps): approximate with its bulge point and end point
                radius, sweep = float(tokens[index + 1]), int(float(tokens[index + 5]))
                end = (float(tokens[index + 6]), float(tokens[index + 7]))
                start = current[-1]
                mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
                dx, dy = end[0] - start[0], end[1] - start[1]
                length = math.hypot(dx, dy) or 1
                sign = 1 if sweep else -1
                current.append((mid[0] - sign * dy / length * radius, mid[1] + sign * dx / length * radius))
                current.append(end)
                index += 8
            elif token in 'Zz':
                if current:
                    current.append(current[0])
                index += 1
            elif token in 'MmLl':
                if token in 'Mm' and current:
                    points_list.append(current)
                    current = []
                index += 1
            else:
                current.append((float(token), float(tokens[index + 1])))
                index += 2
        if current:
            points_list.append(current)
    elif tag == 'rect':
        x, y = float(element.get('x', 0)), float(element.get('y', 0))
        w, h = float(element.get('width', 0)), float(element.get('height', 0))
        points_list.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)])
    elif tag == 'circle':
        cx, cy, r = (float(element.get(k, 0)) for k in ('cx', 'cy', 'r'))
        points_list.append([(cx + r * math.cos(t / 8 * math.pi), cy + r * math.sin(t / 8 * math.pi))
                            for t in range(17)])
    segments = []
    for points in points_list:
        mapped = [apply(matrix, x, y) for x, y in points]
        segments += list(zip(mapped, mapped[1:])) or [(mapped[0], mapped[0])]
    return segments


WIRE_COLOR = '#009600'
BODY_FILL = '#FFFFC2'


def style_value(style, key, inherited):
    """A CSS property from an inline style, falling back to the inherited value."""
    match = re.search(rf'(?<![-\w]){key}\s*:\s*([^;]+)', style or '')
    return inherited if not match else match.group(1).strip()


def collect(svg_path):
    """Return (texts, segments, wires, bodies): texts as (label, box), the rest as segments/boxes."""
    root = ET.parse(svg_path).getroot()
    texts, segments, wires, bodies = [], [], [], []

    def walk(node, matrix, stroke, fill, text_owner):
        matrix = parse_transform(node.get('transform'), matrix)
        stroke = style_value(node.get('style'), 'stroke', stroke)
        fill = style_value(node.get('style'), 'fill', fill)
        if node.get('class') == 'stroked-text':
            desc = node.find(NS + 'desc')
            text_owner = {'label': desc.text if desc is not None else '?', 'segments': []}
            texts.append(text_owner)
        tag = node.tag.replace(NS, '')
        if tag in ('path', 'rect', 'circle'):
            shape = path_segments(node, matrix)
            if stroke != 'none':
                (text_owner['segments'] if text_owner else segments).extend(shape)
                if stroke.upper() == WIRE_COLOR.upper() and not text_owner:
                    wires.extend(shape)
            if fill.upper() == BODY_FILL.upper() and shape:
                xs = [x for seg in shape for x, _ in seg]
                ys = [y for seg in shape for _, y in seg]
                bodies.append((min(xs), min(ys), max(xs), max(ys)))
        for child in node:
            walk(child, matrix, stroke, fill, text_owner)

    walk(root, (1, 0, 0, 1, 0, 0), 'none', 'none', None)
    boxes, seen = [], set()
    for text in texts:
        xs = [x for seg in text['segments'] for x, _ in seg]
        ys = [y for seg in text['segments'] for _, y in seg]
        if not xs or not (text['label'] or '').strip():
            continue
        box = (min(xs), min(ys), max(xs), max(ys))
        # KiCad plots some texts twice at the same place; keep one copy
        key = (text['label'], tuple(round(v, 2) for v in box))
        if key not in seen:
            seen.add(key)
            boxes.append((text['label'], box))
    return boxes, segments, wires, bodies


def shrink(box):
    x0, y0, x1, y1 = box
    margin = max(min(x1 - x0, y1 - y0) * MARGIN, 0.05)
    return x0 + margin, y0 + margin, x1 - margin, y1 - margin


def segment_hits(seg, box):
    """Liang-Barsky clip: does the segment pass through the box interior?"""
    (x0, y0), (x1, y1) = seg
    bx0, by0, bx1, by1 = box
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - bx0), (dx, bx1 - x0), (-dy, y0 - by0), (dy, by1 - y0)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def check(svg_path):
    boxes, segments, wires, bodies = collect(svg_path)
    problems = []
    for body in bodies:
        inside = (body[0] + 0.3, body[1] + 0.3, body[2] - 0.3, body[3] - 0.3)
        if inside[0] < inside[2] and any(segment_hits(seg, inside) for seg in wires):
            problems.append(f'wire through symbol body at ({body[0]:.1f}, {body[1]:.1f}) mm')
    cell = 10.0
    grid = {}
    for seg in segments:
        (x0, y0), (x1, y1) = seg
        for gx in range(int(min(x0, x1) // cell), int(max(x0, x1) // cell) + 1):
            for gy in range(int(min(y0, y1) // cell), int(max(y0, y1) // cell) + 1):
                grid.setdefault((gx, gy), []).append(seg)
    inner = [(label, shrink(box)) for label, box in boxes]
    for label, box in inner:
        if box[0] >= box[2] or box[1] >= box[3]:
            continue
        nearby = {id(s): s for gx in range(int(box[0] // cell), int(box[2] // cell) + 1)
                  for gy in range(int(box[1] // cell), int(box[3] // cell) + 1)
                  for s in grid.get((gx, gy), [])}
        if any(segment_hits(seg, box) for seg in nearby.values()):
            problems.append(f'text on line: "{label}" at ({box[0]:.1f}, {box[1]:.1f}) mm')
    for index, (label_a, a) in enumerate(inner):
        for label_b, b in inner[index + 1:]:
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                problems.append(f'text overlap: "{label_a}" x "{label_b}" at ({a[0]:.1f}, {a[1]:.1f}) mm')
    return len(boxes), problems


def main():
    total = 0
    for svg_path in sorted(Path(sys.argv[1]).glob('*.svg')):
        count, problems = check(svg_path)
        total += len(problems)
        print(f'{svg_path.stem}: {count} texts, {len(problems)} problems')
        for problem in problems:
            print('  ' + problem)
    print(f'text overlap check: {total} problems')
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
