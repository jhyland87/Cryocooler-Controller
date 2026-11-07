"""Finds every part with no printed label and adds a 0.7 mm silk one to `mask_labels.json`:
beside a part edge if it fits, otherwise further away with a silk arrow. Test points are
named by their value, everything else by its reference. Visible footprint fields shrink to
0.7 mm too. Prints the parts with no room. Run `mask_labels.py` afterwards.

Boxes are bounding rectangles, so run DRC on the result.

Usage: silk_label_missing.py board.kicad_pcb (KiCad's bundled Python; edits in place)
"""
import json
import math
import sys
from pathlib import Path

import pcbnew

LABEL_FILE = Path(__file__).with_name('mask_labels.json')
MM = pcbnew.FromMM
SIZE, STROKE = 0.7, 0.1
PAD_GAP, SILK_GAP, EDGE_GAP, VIA_GAP = 0.16, 0.16, 0.32, 0.1
SIDES = {'F': (pcbnew.F_SilkS, pcbnew.F_Mask, pcbnew.F_Fab),
         'B': (pcbnew.B_SilkS, pcbnew.B_Mask, pcbnew.B_Fab)}
MAX_ARROW = 9.0


def box(bounds):
    return (bounds.GetLeft() / 1e6, bounds.GetTop() / 1e6,
            bounds.GetRight() / 1e6, bounds.GetBottom() / 1e6)


def grow(rect, gap):
    return (rect[0] - gap, rect[1] - gap, rect[2] + gap, rect[3] + gap)


def overlaps(first, second):
    return first[0] < second[2] and second[0] < first[2] and (
        first[1] < second[3] and second[1] < first[3])


def part_body(footprint, side):
    """Pads and fab outline only: the courtyard doesn't need clearing."""
    rects = [box(pad.GetBoundingBox()) for pad in footprint.Pads()]
    rects += [box(item.GetBoundingBox()) for item in footprint.GraphicalItems()
              if item.GetLayer() == SIDES[side][2] and item.GetClass() != 'PCB_TEXT']
    if not rects:
        return None
    return (min(rect[0] for rect in rects), min(rect[1] for rect in rects),
            max(rect[2] for rect in rects), max(rect[3] for rect in rects))


def build_obstacles(board):
    obstacles = {'F': [], 'B': []}
    for footprint in board.GetFootprints():
        side = 'B' if footprint.IsFlipped() else 'F'
        other = 'F' if side == 'B' else 'B'
        for pad in footprint.Pads():
            rect = grow(box(pad.GetBoundingBox()), PAD_GAP)
            obstacles[side].append(rect)
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                obstacles[other].append(rect)
        body = part_body(footprint, side)
        if body:
            obstacles[side].append(grow(body, 0.05))
        for item in footprint.GraphicalItems():
            if item.GetLayer() == SIDES[side][0] and item.GetClass() != 'PCB_TEXT':
                obstacles[side].append(grow(box(item.GetBoundingBox()), SILK_GAP))
        for field in (footprint.Reference(), footprint.Value()):
            if field.IsVisible() and field.GetLayer() == SIDES[side][0]:
                obstacles[side].append(grow(box(field.GetBoundingBox()), SILK_GAP))
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T:
            rect = grow(box(track.GetBoundingBox()), VIA_GAP)
            obstacles['F'].append(rect)
            obstacles['B'].append(rect)
    for item in board.GetDrawings():
        layer = item.GetLayer()
        if layer == pcbnew.Edge_Cuts:
            rect = grow(box(item.GetBoundingBox()), EDGE_GAP)
            obstacles['F'].append(rect)
            obstacles['B'].append(rect)
        for side, (silk, mask, _fab) in SIDES.items():
            if layer in (silk, mask):
                obstacles[side].append(grow(box(item.GetBoundingBox()), SILK_GAP))
    return obstacles


def text_size(board, text):
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetTextSize(pcbnew.VECTOR2I_MM(SIZE, SIZE))
    item.SetTextThickness(MM(STROKE))
    bounds = item.GetBoundingBox()
    return bounds.GetWidth() / 1e6, bounds.GetHeight() / 1e6


def adjacent_spots(body, width, height):
    """Label centres beside each edge, centred first and then sliding along it."""
    center_x, center_y = (body[0] + body[2]) / 2, (body[1] + body[3]) / 2
    for gap in (0.08, 0.2, 0.35, 0.5):
        for slide in (0, 0.2, -0.2, 0.4, -0.4, 0.7, -0.7, 1.0, -1.0):
            yield center_x + slide, body[1] - gap - height / 2, 0
            yield center_x + slide, body[3] + gap + height / 2, 0
            yield body[0] - gap - height / 2, center_y + slide, 90
            yield body[2] + gap + height / 2, center_y + slide, 90
            yield body[0] - gap - width / 2, center_y + slide, 0
            yield body[2] + gap + width / 2, center_y + slide, 0
            yield center_x + slide, body[1] - gap - width / 2, 90
            yield center_x + slide, body[3] + gap + width / 2, 90


def label_rect(spot, width, height):
    pos_x, pos_y, angle = spot
    half_x, half_y = (width / 2, height / 2) if angle == 0 else (height / 2, width / 2)
    return (pos_x - half_x, pos_y - half_y, pos_x + half_x, pos_y + half_y)


def line_clear(start, end, obstacles, ignore):
    steps = max(2, int(math.dist(start, end) / 0.08))
    for step in range(steps + 1):
        pos_x = start[0] + (end[0] - start[0]) * step / steps
        pos_y = start[1] + (end[1] - start[1]) * step / steps
        probe = (pos_x - 0.08, pos_y - 0.08, pos_x + 0.08, pos_y + 0.08)
        for rect in obstacles:
            if not overlaps(probe, ignore) and overlaps(probe, rect):
                return False
    return True


def arrow_spots(body, width, height):
    """Further spots on a grid, with a straight leader from a point just off the body."""
    center_x, center_y = (body[0] + body[2]) / 2, (body[1] + body[3]) / 2
    tips = [(center_x, body[1] - 0.2), (center_x, body[3] + 0.2),
            (body[0] - 0.2, center_y), (body[2] + 0.2, center_y),
            (body[0] - 0.15, body[1] - 0.15), (body[2] + 0.15, body[1] - 0.15),
            (body[0] - 0.15, body[3] + 0.15), (body[2] + 0.15, body[3] + 0.15)]
    spots = []
    steps = int(MAX_ARROW / 0.2)
    for step_x in range(-steps, steps + 1):
        for step_y in range(-steps, steps + 1):
            pos_x, pos_y = center_x + step_x * 0.2, center_y + step_y * 0.2
            for angle in (0, 90):
                half_x, half_y = (width / 2, height / 2) if angle == 0 else (height / 2, width / 2)
                for tip in tips:
                    # leader ends on the label's edge, on the side facing the tip
                    end_x = max(pos_x - half_x - 0.12, min(tip[0], pos_x + half_x + 0.12))
                    end_y = max(pos_y - half_y - 0.12, min(tip[1], pos_y + half_y + 0.12))
                    length = math.dist(tip, (end_x, end_y))
                    if 0.7 <= length <= MAX_ARROW:
                        spots.append((length, tip, (end_x, end_y), (pos_x, pos_y, angle)))
    spots.sort(key=lambda spot: spot[0])
    return spots


def main():
    path = sys.argv[1]
    labels = json.loads(LABEL_FILE.read_text())
    board = pcbnew.LoadBoard(path)
    named = {label.get('ref') for label in labels}
    near_texts = [(label['text'], label['side'], label['x'], label['y']) for label in labels]
    shrunk = 0
    wanted = []
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if not ref:
            continue
        side = 'B' if footprint.IsFlipped() else 'F'
        for field in (footprint.Reference(), footprint.Value()):
            if field.IsVisible() and field.GetLayer() == SIDES[side][0]:
                field.SetTextSize(pcbnew.VECTOR2I_MM(SIZE, SIZE))
                field.SetTextThickness(MM(STROKE))
                shrunk += 1
                named.add(ref)
        if ref in named:
            continue
        value = footprint.GetValue()
        is_test_point = ref.startswith('TP')
        text = value if is_test_point else ref
        center = (footprint.GetX() / 1e6, footprint.GetY() / 1e6)
        if is_test_point and any(
                name == value and name_side == side and math.dist(center, (pos_x, pos_y)) < 6
                for name, name_side, pos_x, pos_y in near_texts):
            continue  # already named by a board label
        wanted.append((footprint, ref, text, side, 'value' if is_test_point else 'ref'))
    obstacles = build_obstacles(board)
    print('fields shrunk', shrunk, 'to label', [item[1] for item in wanted])
    placed = []
    no_room = []
    for footprint, ref, text, side, kind in sorted(
            wanted, key=lambda item: text_size(board, item[2])[0], reverse=True):
        body = part_body(footprint, side)
        width, height = text_size(board, text)
        result = None
        for spot in adjacent_spots(body, width, height):
            rect = label_rect(spot, width, height)
            if not any(overlaps(rect, other) for other in obstacles[side]):
                result = (spot, rect, None)
                obstacles[side].append(grow(rect, SILK_GAP))
                break
        placed.append((ref, footprint, text, side, kind, result, body, width, height))
    final = []
    for ref, footprint, text, side, kind, result, body, width, height in placed:
        if result is None:
            for _length, tip, end, spot in arrow_spots(body, width, height):
                rect = label_rect(spot, width, height)
                if any(overlaps(rect, other) for other in obstacles[side]):
                    continue
                if not line_clear(tip, end, obstacles[side], grow(body, 0.25)):
                    continue
                result = (spot, rect, [list(tip), list(end)])
                obstacles[side].append(grow(rect, SILK_GAP))
                obstacles[side].append(grow((min(tip[0], end[0]), min(tip[1], end[1]),
                                             max(tip[0], end[0]), max(tip[1], end[1])), SILK_GAP))
                break
        if result is None:
            no_room.append(ref)
            continue
        spot, _rect, arrow = result
        label = {'kind': kind, 'text': text, 'side': side, 'x': round(spot[0], 3),
                 'y': round(spot[1], 3), 'angle': spot[2], 'size': SIZE, 'ref': ref, 'silk': True}
        if arrow:
            label['arrow'] = [[round(value, 3) for value in point] for point in arrow]
        final.append(label)
    labels.extend(final)
    LABEL_FILE.write_text(json.dumps(labels, indent=0, ensure_ascii=False))
    board.Save(path)
    print('added', len(final), 'with arrows', sum(1 for label in final if label.get('arrow')))
    print('arrows on', [label['ref'] for label in final if label.get('arrow')])
    print('no room', no_room)


if __name__ == '__main__':
    main()
