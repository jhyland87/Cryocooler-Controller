"""Chooses a spot for every label a part owns and writes `mask_labels.json`.

The rule comes from the user's hand edits: centre a label on one edge of its part and run
it parallel to that edge, on the part's open side and the same side as similar parts
nearby, even if that means sitting a little farther away. Ranked best first: mask text
centred on an edge, slid along an edge, its previous mask spot, 1.0 mm silk centred on an
edge, its current silk spot, an arrow, hidden.

It starts from the previous labels and only moves one to a better free spot, shifting a
blocking label if that helps, so coverage can't get worse. Hand placements in LOCKED stay,
nudged only as far as needed to be legal. Labels with no owning part stay where they are.
Run from the system Python.

Usage: mask_label_plan.py board.json out.json previous_labels.json
"""
import json
import math
import re
import sys
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

PIXELS_PER_MM = 25
EDGE_MARGIN = 0.5
LABEL_STROKE = 0.1
SILK_CHAR = 0.92  # 1.0 mm tall, 0.9 mm wide silk with a 0.15 mm stroke
SILK_HEIGHT = 1.15
CHAR_RATIO = 1.0  # KiCad stroke font advance per mm of text width, wide letters included
CENTRED_LIMIT = 0.25  # off-centre by this much still reads as centred
MAX_GAP = {'small': 1.0, 'large': 1.6}
MAX_SLIDE = 5
MAX_SPOTS = 800
MAX_ARROW = 12
MAX_NUDGE = 0.5
PASSES = 3
SIDE_NAMES = ('top', 'left', 'bottom', 'right')
DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1), (.7071, .7071), (.7071, -.7071), (-.7071, .7071), (-.7071, -.7071)]
TIER_CENTRED, TIER_SLID, TIER_PREVIOUS, TIER_SILK, TIER_KEPT_SILK, TIER_ARROW, TIER_HIDDEN = range(7)
TIER_NAMES = ('mask centred', 'mask slid', 'previous mask', 'silk centred', 'kept silk', 'arrow', 'hidden')
# clearance a placed mask label and a placed silk label keep in each map
STAMP_GAPS = {'label': (.11, .16), 'silk': (.16, .12), 'arrow': (.24, .24)}
# (x, y, angle, size): the user's hand placements, plus J14 kept off the connector's silk
LOCKED = {
    'U18': (18.79, 7.37, 0, .7), 'U4': (46.68, 15.61, 0, .7), 'U5': (35.7, 30.98, 90, .7),
    'SW2': (62.3, 17.84, 90, .7), 'C39': (87.71, 37.23, 0, .5),
    'BOOT': (66.49, 14.55, 0, .7), 'RESET': (66.41, 7.3, 0, .7), 'SW1': (66.5, 13.285, 0, .7),
    'J14': (111.545, 40.415, 0, .7),
}
LOCKED_SILK = {'U32': (92.14, 29.39, 0)}
# hand-placed labels that may not exist on the board yet, with their part and side
NEW_LABELS = {'RESET': ('SW1', 'F')}


def main():
    data = json.load(open(sys.argv[1]))
    previous = {(label['kind'], label['text'], label.get('ref')): label
                for label in json.load(open(sys.argv[3]))}
    left, top, right, bottom = data['edge']
    width, height = int((right - left) * PIXELS_PER_MM) + 1, int((bottom - top) * PIXELS_PER_MM) + 1

    def to_px(x_mm, y_mm):
        return (x_mm - left) * PIXELS_PER_MM, (y_mm - top) * PIXELS_PER_MM

    def raster(polygons):
        image = Image.new('1', (width, height))
        draw = ImageDraw.Draw(image)
        for polygon in polygons:
            if len(polygon) > 2:
                draw.polygon([to_px(*point) for point in polygon], fill=1)
        return np.array(image)

    def grow(mask, millimetres):
        radius = max(1, round(millimetres * PIXELS_PER_MM))
        grid = np.mgrid[-radius:radius + 1, -radius:radius + 1]
        return ndimage.binary_dilation(mask, (grid[0] ** 2 + grid[1] ** 2) <= radius * radius)

    def px_box(box):
        x0, y0 = to_px(box[0], box[1])
        x1, y1 = to_px(box[2], box[3])
        return int(x0), int(y0), math.ceil(x1), math.ceil(y1)

    # `static` holds what never moves, `used` counts placed labels so they can be taken back out
    static = {'label': {}, 'silk': {}, 'arrow': {}, 'lock': {}, 'loose': {}}
    used = {name: {side: np.zeros((height, width), np.int16) for side in 'FB'} for name in STAMP_GAPS}
    for side in 'FB':
        raw_pour = raster(data['pour'][side])
        pour = ndimage.binary_erosion(raw_pour, iterations=2)
        signal_image, ground_image = Image.new('1', (width, height)), Image.new('1', (width, height))
        for x_mm, y_mm, diameter, is_ground in data['vias']:
            image = ground_image if is_ground else signal_image
            ImageDraw.Draw(image).ellipse([*to_px(x_mm - diameter / 2, y_mm - diameter / 2), *to_px(x_mm + diameter / 2, y_mm + diameter / 2)], fill=1)
        ground_vias, signal_vias = np.array(ground_image), np.array(signal_image)
        vias = ground_vias | signal_vias
        silk, pads, body = raster(data['silk'][side]), raster(data['pads'][side]), raster(data['body'][side])
        inside = np.ones((height, width), bool)
        margin = int(EDGE_MARGIN * PIXELS_PER_MM)
        inside[:margin] = inside[-margin:] = False
        inside[:, :margin] = inside[:, -margin:] = False
        # a ground via under a ground-pour label is the same net: stay off it, but close is fine
        static['label'][side] = pour & inside & ~(grow(silk, .18) | grow(pads, .16) | grow(body, .16) | grow(signal_vias, .16) | grow(ground_vias, .06))
        static['silk'][side] = inside & ~(grow(silk, .12) | grow(pads, .16) | grow(body, .16) | grow(vias, .16))
        static['arrow'][side] = inside & ~(grow(silk, .3) | grow(pads, .27) | grow(body, .16) | grow(vias, .2))
        # hand placements may sit right against a part body, which isn't printed on the board
        static['lock'][side] = pour & inside & ~(grow(silk, .15) | grow(pads, .15) | grow(signal_vias, .15) | grow(ground_vias, .06))
        # previous labels passed DRC, and their estimated boxes run wider than the glyphs
        static['loose'][side] = raw_pour & ~(grow(silk, .08) | grow(pads, .08) | grow(signal_vias, .08))

    def free(name, side, box):
        x0, y0, x1, y1 = px_box(box)
        if x0 < 0 or y0 < 0 or x1 >= width or y1 >= height or not static[name][side][y0:y1, x0:x1].all():
            return False
        return name not in used or not used[name][side][y0:y1, x0:x1].any()

    def line_free(name, side, x0, y0, x1, y1):
        steps = int(math.hypot(x1 - x0, y1 - y0) * PIXELS_PER_MM) + 1
        for step in range(steps + 1):
            x_px, y_px = to_px(x0 + (x1 - x0) * step / steps, y0 + (y1 - y0) * step / steps)
            x_px, y_px = int(x_px), int(y_px)
            if not (0 <= x_px < width and 0 <= y_px < height) or not static[name][side][y_px, x_px] or used[name][side][y_px, x_px]:
                return False
        return True

    def apply(place, delta):
        """Adds (delta 1) or removes (delta -1) a placed label and its arrow from the used maps."""
        side, box, points = place['side'], place['box'], place.get('arrow') or []
        for name, gaps in STAMP_GAPS.items():
            gap = gaps[1 if place.get('silk') else 0]
            x0, y0, x1, y1 = px_box([box[0] - gap, box[1] - gap, box[2] + gap, box[3] + gap])
            used[name][side][max(0, y0):y1, max(0, x0):x1] += delta
            for start, end in zip(points, points[1:]):
                pad = max(gap, .16) + .15
                bx0, by0, bx1, by1 = px_box([min(start[0], end[0]) - pad, min(start[1], end[1]) - pad, max(start[0], end[0]) + pad, max(start[1], end[1]) + pad])
                bx0, by0 = max(0, bx0), max(0, by0)
                bx1, by1 = min(width, bx1), min(height, by1)
                image = Image.new('1', (bx1 - bx0, by1 - by0))
                first, second = to_px(*start), to_px(*end)
                ImageDraw.Draw(image).line([(first[0] - bx0, first[1] - by0), (second[0] - bx0, second[1] - by0)], fill=1,
                                           width=int((.15 + 2 * max(gap, .16)) * PIXELS_PER_MM))
                used[name][side][by0:by1, bx0:bx1] += delta * np.array(image).astype(np.int16)

    bodies = data['bodies']

    def box_gap(first, second):
        return max(first[0] - second[2], second[0] - first[2], first[1] - second[3], second[1] - first[3], 0)

    def point_gap(x_mm, y_mm, box):
        return math.hypot(max(box[0] - x_mm, x_mm - box[2], 0), max(box[1] - y_mm, y_mm - box[3], 0))

    def label_size(item):
        return .5 if item['kind'] == 'ref' and re.match(r'^[RCD]\d', item['text']) else .7

    def extent(text, size, silk=False):
        if silk:
            return len(text) * SILK_CHAR + .1, SILK_HEIGHT
        return len(text) * size * CHAR_RATIO + .12, size + LABEL_STROKE + .02

    def box_at(text, x_mm, y_mm, angle, size, silk=False):
        length, tall = extent(text, size, silk)
        box_w, box_h = (length, tall) if angle % 180 == 0 else (tall, length)
        return [x_mm - box_w / 2, y_mm - box_h / 2, x_mm + box_w / 2, y_mm + box_h / 2]

    def neighbours(side, reference):
        owner = bodies[side][reference]
        return [box for name, box in bodies[side].items() if name != reference
                and box_gap(box, [owner[0] - 4, owner[1] - 4, owner[2] + 4, owner[3] + 4]) == 0]

    def openness(side, owner, edge):
        """How much of the 1.5 mm strip beyond an edge is free for labels."""
        strips = {'top': [owner[0], owner[1] - 1.5, owner[2], owner[1]], 'bottom': [owner[0], owner[3], owner[2], owner[3] + 1.5],
                  'left': [owner[0] - 1.5, owner[1], owner[0], owner[3]], 'right': [owner[2], owner[1], owner[2] + 1.5, owner[3]]}
        x0, y0, x1, y1 = px_box(strips[edge])
        region = static['label'][side][max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
        return float(region.mean()) if region.size else 0.0

    def edge_spots(item, size, silk=False):
        """Returns every legal spot on an edge of the owning part, ignoring other labels."""
        side, reference = item['side'], item['ref']
        owner = bodies[side][reference]
        centre_x, centre_y = (owner[0] + owner[2]) / 2, (owner[1] + owner[3]) / 2
        kind = 'large' if max(owner[2] - owner[0], owner[3] - owner[1]) > 2.5 else 'small'
        nearby = neighbours(side, reference)
        wide = owner[2] - owner[0] >= owner[3] - owner[1]
        map_name = 'silk' if silk else 'label'
        spots = []
        for edge in SIDE_NAMES:
            along_x = edge in ('top', 'bottom')
            span = min(owner[2] - owner[0] if along_x else owner[3] - owner[1], MAX_SLIDE)
            # parallel to the edge; a small part's end may also take an in-line label
            options = [(0 if along_x else 90, 0.0)]
            if kind == 'small' and along_x != wide:
                options.append((0 if wide else 90, .3))
            open_score = 1.0 - openness(side, owner, edge)
            slides = [0.0, -.05, .05, -.1, .1, -.15, .15, -.2, .2, -.25, .25] if silk else sorted(
                {round(step * .05, 2) for step in range(-int(span * 20), int(span * 20) + 1)}, key=abs)
            for angle, penalty in options:
                length, tall = extent(item['text'], size, silk)
                box_w, box_h = (length, tall) if angle == 0 else (tall, length)
                for slide in slides:
                    for gap_steps in range(2, int(MAX_GAP[kind] / .05) + 1):
                        gap = gap_steps * .05
                        if edge == 'top':
                            x_mm, y_mm = centre_x + slide, owner[1] - gap - box_h / 2
                        elif edge == 'bottom':
                            x_mm, y_mm = centre_x + slide, owner[3] + gap + box_h / 2
                        elif edge == 'left':
                            x_mm, y_mm = owner[0] - gap - box_w / 2, centre_y + slide
                        else:
                            x_mm, y_mm = owner[2] + gap + box_w / 2, centre_y + slide
                        box = [x_mm - box_w / 2, y_mm - box_h / 2, x_mm + box_w / 2, y_mm + box_h / 2]
                        x0, y0, x1, y1 = px_box(box)
                        if x0 < 0 or y0 < 0 or x1 >= width or y1 >= height or not static[map_name][side][y0:y1, x0:x1].all():
                            continue
                        if any(box_gap(box, other) < box_gap(box, owner) + .05 for other in nearby):
                            continue
                        off_centre = abs(slide)
                        tier = TIER_SILK if silk else TIER_CENTRED if off_centre <= CENTRED_LIMIT else TIER_SLID
                        score = off_centre * 2 + gap * .6 + penalty + open_score
                        spots.append(dict(tier=tier, score=score, x=x_mm, y=y_mm, angle=angle, size=size, box=box, edge=edge, silk=silk, side=side))
        spots.sort(key=lambda spot: (spot['tier'], spot['score']))
        return spots[:MAX_SPOTS]

    def arrow_spot(item, size):
        """Finds the shortest arrow with at most one bend from the part to a clear label spot."""
        side, reference = item['side'], item['ref']
        owner = bodies[side][reference]
        length, tall = extent(item['text'], size)
        nearby = neighbours(side, reference)
        best = None

        def fit(end_x, end_y, dir_x, dir_y):
            for angle, (box_w, box_h) in ((0, (length, tall)), (90, (tall, length))):
                x_mm = end_x + (box_w / 2 + .25) * (1 if dir_x > .01 else -1 if dir_x < -.01 else 0)
                y_mm = end_y + (box_h / 2 + .25) * (1 if dir_y > .01 else -1 if dir_y < -.01 else 0)
                box = [x_mm - box_w / 2, y_mm - box_h / 2, x_mm + box_w / 2, y_mm + box_h / 2]
                if free('label', side, box):
                    return x_mm, y_mm, angle, box
            return None

        xs, ys = np.arange(owner[0], owner[2] + .01, .1), np.arange(owner[1], owner[3] + .01, .1)
        tips = [(x, owner[1] - .25) for x in xs] + [(x, owner[3] + .25) for x in xs]
        tips += [(owner[0] - .25, y) for y in ys] + [(owner[2] + .25, y) for y in ys]
        for tip_x, tip_y in tips:
            gap = point_gap(tip_x, tip_y, owner)
            if any(point_gap(tip_x, tip_y, other) < gap + .1 for other in nearby):
                continue
            for dir_x, dir_y in DIRECTIONS:
                if point_gap(tip_x + dir_x * .5, tip_y + dir_y * .5, owner) <= gap:
                    continue
                if not line_free('arrow', side, tip_x, tip_y, tip_x + dir_x * .5, tip_y + dir_y * .5):
                    continue
                if not line_free('arrow', side, tip_x + dir_x * .5 - dir_y * .2, tip_y + dir_y * .5 + dir_x * .2,
                                 tip_x + dir_x * .5 + dir_y * .2, tip_y + dir_y * .5 - dir_x * .2):
                    continue
                for first in np.arange(.8, MAX_ARROW + .01, .25):
                    if best and first >= best[0]:
                        break
                    end_x, end_y = tip_x + dir_x * first, tip_y + dir_y * first
                    if not line_free('arrow', side, tip_x + dir_x * (first - .3), tip_y + dir_y * (first - .3), end_x, end_y):
                        break
                    spot = fit(end_x, end_y, dir_x, dir_y)
                    if spot:
                        best = (first, [(tip_x, tip_y), (end_x, end_y)], spot)
                        break
                    for bend_x, bend_y in DIRECTIONS:
                        dot = bend_x * dir_x + bend_y * dir_y
                        if dot < -.01 or dot > .9:
                            continue
                        for second in np.arange(.5, MAX_ARROW - first + .01, .25):
                            if best and first + second + 1.5 >= best[0]:
                                break
                            far_x, far_y = end_x + bend_x * second, end_y + bend_y * second
                            start = max(0, second - .3)
                            if not line_free('arrow', side, end_x + bend_x * start, end_y + bend_y * start, far_x, far_y):
                                break
                            spot = fit(far_x, far_y, bend_x, bend_y)
                            if spot:
                                best = (first + second + 1.5, [(tip_x, tip_y), (end_x, end_y), (far_x, far_y)], spot)
                                break
        return best

    existing = {item['text'] for item in data['items']}
    for name, (reference, side) in NEW_LABELS.items():
        if name not in existing:
            x_mm, y_mm, angle, size = LOCKED[name]
            data['items'].append(dict(kind='board', text=name, side=side, x=x_mm, y=y_mm, angle=angle, ref=reference, visible=False, on_mask=True,
                                      box=box_at(name, x_mm, y_mm, angle, size)))

    movable, fixed = [], []
    seen = set()
    for item in data['items']:
        owned = item.get('ref') in bodies[item['side']]
        key = (item['kind'], item['text'], item.get('ref')) if owned else (item['text'], item['x'], item['y'])
        if key in seen:
            continue
        seen.add(key)
        (movable if owned else fixed).append(item)

    def record_for(item, place):
        record = dict(kind=item['kind'], text=item['text'], side=item['side'], x=round(float(place['x']), 3),
                      y=round(float(place['y']), 3), angle=place['angle'], size=place['size'])
        for key in ('ref', 'uuid'):
            if item.get(key):
                record[key] = item[key]
        if place.get('silk'):
            record['silk'] = True
        if place.get('arrow'):
            record['arrow'] = [[round(float(value), 3) for value in point] for point in place['arrow']]
        return record

    # ownerless labels keep their spot, and hold it against everything else
    output = []
    for item in fixed:
        record = {key: item[key] for key in ('kind', 'text', 'side', 'x', 'y', 'angle') if key in item}
        record['size'] = label_size(item)
        if item.get('uuid'):
            record['uuid'] = item['uuid']
        if item.get('on_mask'):
            output.append(record)
            apply(dict(side=item['side'], box=item['box']), 1)
        else:
            for name in static:
                x0, y0, x1, y1 = px_box([item['box'][0] - .2, item['box'][1] - .2, item['box'][2] + .2, item['box'][3] + .2])
                static[name][item['side']][y0:y1, x0:x1] = False

    placements = {}  # id(item) -> current place, absent when hidden
    locked = set()

    def nudged(item, x_mm, y_mm, angle, size, silk):
        """Returns the nearest legal place to a hand position, or None."""
        name = 'silk' if silk else 'lock'
        steps = sorted(((dx * .05, dy * .05) for dx in range(-10, 11) for dy in range(-10, 11)), key=lambda step: math.hypot(*step))
        for dx, dy in steps:
            if math.hypot(dx, dy) > MAX_NUDGE:
                break
            box = box_at(item['text'], x_mm + dx, y_mm + dy, angle, size, silk)
            if free(name, item['side'], box) and not used['label'][item['side']][px_box(box)[1]:px_box(box)[3], px_box(box)[0]:px_box(box)[2]].any():
                return dict(tier=TIER_SILK if silk else TIER_CENTRED, score=0, x=x_mm + dx, y=y_mm + dy, angle=angle, size=size,
                            box=box, silk=silk, side=item['side']), math.hypot(dx, dy)
        return None

    # hand placements go first, so everything else works around them
    for item in movable:
        name = item['text']
        hand = LOCKED_SILK.get(name) if item['kind'] in ('ref', 'board') else None
        is_silk = hand is not None
        if not hand and item['kind'] in ('ref', 'board', 'value') and name in LOCKED:
            hand = LOCKED[name]
        if not hand:
            continue
        x_mm, y_mm, angle = hand[:3]
        result = nudged(item, x_mm, y_mm, angle, 1.0 if is_silk else hand[3], is_silk)
        if not result:
            print('hand placement not legal, using the rule:', name, flush=True)
            continue
        place, moved = result
        placements[id(item)] = place
        apply(place, 1)
        locked.add(id(item))
        if moved:
            print(f'hand placement {name} nudged {moved:.2f} mm', flush=True)
    print('locked', len(locked), flush=True)

    # then the last legal layout, as the starting point
    start_tiers = Counter()
    homeless = []
    for item in movable:
        if id(item) in locked:
            continue
        side = item['side']
        old = previous.get((item['kind'], item['text'], item.get('ref')))
        was_silk = item['visible'] and not item.get('on_mask') and item['box'][2] - item['box'][0] > 0
        if old and not old.get('silk'):
            box = box_at(old['text'], old['x'], old['y'], old['angle'], old['size'])
            inner = [box[0] + .08, box[1] + .08, box[2] - .08, box[3] - .08]
            points = old.get('arrow')
            if free('loose', side, inner):
                place = dict(tier=TIER_ARROW if points else TIER_PREVIOUS, score=20.0 if points else 0.0, x=old['x'], y=old['y'],
                             angle=old['angle'], size=old['size'], box=box, silk=False, side=side, arrow=points)
                # a lock may have landed here
                if not any(placed['side'] == side and box_gap(placed['box'], box) < .05 for key, placed in placements.items() if key in locked):
                    placements[id(item)] = place
                    apply(place, 1)
                    start_tiers[place['tier']] += 1
                    continue
            homeless.append(item)
        elif was_silk:
            place = dict(tier=TIER_KEPT_SILK, score=0.0, x=item['x'], y=item['y'], angle=item['angle'], size=1.0, box=item['box'], silk=True, side=side, kept=True)
            placements[id(item)] = place
            apply(place, 1)
            start_tiers[TIER_KEPT_SILK] += 1
        else:
            homeless.append(item)
    print('start', {TIER_NAMES[tier]: count for tier, count in sorted(start_tiers.items())}, 'without a spot', [item['text'] for item in homeless], flush=True)

    # candidates, with similar neighbouring parts preferring the same side
    candidates = {}
    active = [item for item in movable if id(item) not in locked]
    for item in active:
        size = label_size(item)
        candidates[id(item)] = edge_spots(item, size)
    print('candidates ready', sum(len(spots) for spots in candidates.values()), flush=True)

    def part_type(item):
        return re.match(r'[A-Za-z]+', item['ref']).group(0)

    groups = []
    for item in active:
        if item['kind'] != 'ref':
            continue
        side, owner = item['side'], bodies[item['side']][item['ref']]
        size = (round(owner[2] - owner[0], 0), round(owner[3] - owner[1], 0))
        for group in groups:
            if group['side'] == side and group['type'] == part_type(item) and group['size'] == size \
                    and any(box_gap(owner, bodies[side][other['ref']]) < 6 for other in group['items']):
                group['items'].append(item)
                break
        else:
            groups.append({'side': side, 'type': part_type(item), 'size': size, 'items': [item]})
    for group in groups:
        if len(group['items']) < 2:
            continue
        votes = Counter()
        for item in group['items']:
            votes.update({spot['edge'] for spot in candidates[id(item)] if spot['score'] < 2.5})
        if not votes:
            continue
        favourite = votes.most_common(1)[0][0]
        for item in group['items']:
            for spot in candidates[id(item)]:
                if spot['edge'] != favourite:
                    spot['score'] += .8
            candidates[id(item)].sort(key=lambda spot: (spot['tier'], spot['score']))
    for item in active:
        candidates[id(item)] = candidates[id(item)] + edge_spots(item, 1.0, silk=True)

    def rank(place):
        return (place['tier'], place['score']) if place else (TIER_HIDDEN, 0.0)

    def is_free(place):
        name = 'silk' if place.get('silk') else 'label'
        return free(name, place['side'], place['box'])

    def best_free(item, limit):
        for spot in candidates[id(item)]:
            if rank(spot) >= limit:
                return None
            if is_free(spot):
                return spot
        return None

    def improve():
        moved = 0
        for item in sorted(active, key=lambda entry: rank(placements.get(id(entry))), reverse=True):
            current = placements.get(id(item))
            if current:
                apply(current, -1)
            spot = best_free(item, rank(current))
            if spot:
                placements[id(item)] = spot
                apply(spot, 1)
                moved += 1
            elif current:
                apply(current, 1)
        return moved

    def touches(place, box):
        """True when a placed label or its arrow sits inside the keep-out of `box`."""
        if place['side'] != box['side']:
            return False
        if box_gap(place['box'], box['box']) < .25:
            return True
        points = place.get('arrow') or []
        for start, end in zip(points, points[1:]):
            steps = int(math.hypot(end[0] - start[0], end[1] - start[1]) / .1) + 1
            for step in range(steps + 1):
                if point_gap(start[0] + (end[0] - start[0]) * step / steps, start[1] + (end[1] - start[1]) * step / steps, box['box']) < .35:
                    return True
        return False

    by_id = {id(item): item for item in active}

    def eject(item):
        """Takes a spot held by up to two other labels, if each has another spot no worse."""
        current = placements.get(id(item))
        limit = rank(current)
        for spot in candidates[id(item)][:300]:
            if rank(spot) >= limit:
                return False
            name = 'silk' if spot.get('silk') else 'label'
            x0, y0, x1, y1 = px_box(spot['box'])
            if x0 < 0 or y0 < 0 or x1 >= width or y1 >= height or not static[name][spot['side']][y0:y1, x0:x1].all():
                continue
            blockers = [key for key, place in placements.items() if key != id(item) and touches(place, spot)]
            if not blockers or len(blockers) > 2 or any(key in locked for key in blockers):
                continue
            if current:
                apply(current, -1)
            held = {key: placements[key] for key in blockers}
            for place in held.values():
                apply(place, -1)
            success = spot_applied = is_free(spot)
            moved = []
            if success:
                apply(spot, 1)
                for key, place in held.items():
                    # a blocker may settle for any edge spot, to get another label back on the board
                    other = best_free(by_id[key], (max(place['tier'], TIER_SLID) + 1, 0.0))
                    if not other:
                        success = False
                        break
                    apply(other, 1)
                    moved.append((key, other))
            if success:
                placements[id(item)] = spot
                placements.update(moved)
                return True
            for _, other in moved:
                apply(other, -1)
            if spot_applied:
                apply(spot, -1)
            for place in held.values():
                apply(place, 1)
            if current:
                apply(current, 1)
        return False

    def summary():
        counts = Counter(rank(placements.get(id(item)))[0] for item in active)
        return {TIER_NAMES[tier]: count for tier, count in sorted(counts.items())}

    for pass_number in range(PASSES):
        print('pass', pass_number, 'moved', improve(), summary(), flush=True)
    ejected = 0
    for item in sorted(active, key=lambda entry: rank(placements.get(id(entry))), reverse=True):
        if rank(placements.get(id(item)))[0] >= TIER_SILK and eject(item):
            ejected += 1
    print('ejected', ejected, summary(), flush=True)
    print('moved', improve(), summary(), flush=True)

    # an arrow only for what still has nothing, then shorten arrows that can go
    for item in sorted(active, key=lambda entry: entry['kind'] != 'ref'):
        if placements.get(id(item)):
            continue
        size = label_size(item)
        best = arrow_spot(item, size)
        if best:
            distance, points, (x_mm, y_mm, angle, box) = best
            place = dict(tier=TIER_ARROW, score=20.0 + distance, x=x_mm, y=y_mm, angle=angle, size=size, box=box, silk=False, side=item['side'], arrow=points)
            placements[id(item)] = place
            apply(place, 1)
    print('after arrows', summary(), flush=True)
    print('moved', improve(), summary(), flush=True)

    for item in movable:
        place = placements.get(id(item))
        if place and not place.get('kept'):
            output.append(record_for(item, place))
    hidden = sorted(item['text'] for item in movable if not placements.get(id(item)))
    stuck = sorted(item['text'] for item in movable if not placements.get(id(item)) and item['visible'] and not item.get('on_mask'))
    print('hidden', hidden)
    print('hidden but still printed on the board', stuck)
    print('arrows', [item['text'] for item in movable if placements.get(id(item), {}).get('arrow')])
    with open(sys.argv[2], 'w') as out:
        json.dump(output, out, indent=0, ensure_ascii=False)
    print('labels written', len(output))


if __name__ == '__main__':
    main()
