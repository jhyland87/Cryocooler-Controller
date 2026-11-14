"""Draws port callouts on a board's top and bottom renders: a label and an
arrow for every J connector and the other parts listed in PORTS, saying
what each is for.

export_fab.py runs this after it writes the renders (it needs Pillow):

    python3 hardware/kicad/tools/render_callouts.py BOARD.kicad_pcb

Board millimetres are mapped to pixels from a second, quick render of the bare
board (3D models stripped, transparent background) with the same camera.
"""

import math
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import export_fab
from sexpr import find_all, parse, sval

# What each part is for, by board: reference -> (name, detail). Every J
# connector needs an entry; other parts get a callout by being listed.
PORTS = {
    'cryocooler': {
        'J1': ('USB-C', 'ESP32 USB, 5 V in'),
        'J2': ('12 V in', '5.5 x 2.1 mm barrel jack'),
        'J3': ('Fan', '4-pin PWM'),
        'J4': ('Pump', '4-pin PWM'),
        'J5': ('Flow sensor', 'Alphacool ES'),
        'J6': ('Coolant NTC', 'Alphacool ES, 10k'),
        'J8': ('Amp remote', 'REM / GND'),
        'J9': ('Sine out', '3.5 mm, to amp input'),
        'J10': ('PT1000', 'cold-stage RTD, 4-wire'),
        'J11': ('Amp out', 'from amplifier, + / -'),
        'J12': ('Cryocooler', '+ / - / GND'),
        'J13': ('Compressor relay', '12 V / GND'),
        'J14': ('IMU', 'cable to IMU board'),
        'J15': ('Display', '14-pin FPC'),
        'J16': ('IO5', 'GPIO / GND'),
        'J17': ('IO7', 'GPIO / GND'),
        'J18': ('IO11', 'GPIO / GND'),
        'J19': ('IO12', 'GPIO / GND'),
        'J20': ('IO13', 'GPIO / GND'),
        'SW1': ('Reset button', 'ESP32 EN'),
        'SW2': ('Boot button', 'ESP32 download mode'),
        'SW3': ('Power button', 'on / off'),
        'U1': ('ESP32-S3', 'WROOM-2 module, WiFi'),
    },
}
# Parts that share one callout, by board: references -> (name, detail).
GROUPS = {
    'cryocooler': {
        ('D13', 'D7', 'D11', 'D12', 'D2', 'D3', 'D6'): (
            'Status LEDs',
            'state, power, +15 V, -15 V, amp, relay, alert',
        ),
    },
}
SCALE = 2  # drawn at twice the size, then reduced, to smooth the lines
NAME_SIZE = 40
DETAIL_SIZE = 30
PAD = 14  # inside the label box
GAP = 16 * SCALE  # between neighbouring labels, in drawing pixels
EDGE = 30  # label box to image edge
LINE = 5
ARROW = (30, 11)  # head length, half width
ACCENT = (222, 56, 28, 255)
INK = (24, 24, 28, 255)
MUTED = (84, 84, 96, 255)
PAPER = (255, 255, 255, 240)


def local_points(item):
    """Points of a graphic item or pad, in its parent's coordinates."""
    points = [
        (float(sval(node[1])), float(sval(node[2])))
        for key in ('start', 'end', 'mid', 'center', 'at')
        for node in find_all(item, key)
    ]
    for pts in find_all(item, 'pts'):
        points += [(float(xy[1]), float(xy[2])) for xy in find_all(pts, 'xy')]
    return points


def on_layer(item, layers):
    return any(sval(node[1]) in layers for node in find_all(item, 'layer'))


def bounds(points):
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def board_bounds(root):
    """Bounding box of the board outline in mm."""
    points = []
    for kind in ('gr_line', 'gr_rect', 'gr_arc', 'gr_poly'):
        for item in find_all(root, kind):
            if on_layer(item, ('Edge.Cuts',)):
                points += local_points(item)
    return bounds(points)


def port_boxes(root, layer, listed):
    """Courtyard box in mm (pads if there is no courtyard) of every J
    connector and listed part on one copper side:
    {reference: (x0, y0, x1, y1)}.
    """
    boxes = {}
    for footprint in find_all(root, 'footprint'):
        reference = next(
            sval(prop[2])
            for prop in find_all(footprint, 'property')
            if sval(prop[1]) == 'Reference'
        )
        if not re.fullmatch(r'J\d+', reference) and reference not in listed:
            continue
        if not on_layer(footprint, (layer,)):
            continue
        points = [
            point
            for kind in ('fp_line', 'fp_rect', 'fp_poly', 'fp_arc')
            for item in find_all(footprint, kind)
            if on_layer(item, ('F.CrtYd', 'B.CrtYd'))
            for point in local_points(item)
        ]
        if not points:
            points = [
                point
                for pad in find_all(footprint, 'pad')
                for point in local_points(pad)
            ]
        at = find_all(footprint, 'at')[0]
        angle = math.radians(float(sval(at[3])) if len(at) > 3 else 0)
        x0, y0 = float(sval(at[1])), float(sval(at[2]))
        boxes[reference] = bounds(
            [
                (
                    x0 + x * math.cos(angle) + y * math.sin(angle),
                    y0 - x * math.sin(angle) + y * math.cos(angle),
                )
                for x, y in points
            ]
        )
    return boxes


def board_pixels(board, side, size, extra):
    """Pixel box of the bare board in a render with this camera."""
    bare = re.sub(
        r'^(\t+)\(model .*?^\1\)\n',
        '',
        Path(board).read_text(),
        flags=re.S | re.M,
    )
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / Path(board).name
        copy.write_text(bare)
        image = Path(tmp) / 'bare.png'
        export_fab.render(
            copy, image, side, size, extra, 'basic', 'transparent'
        )
        with Image.open(image) as opened:
            return opened.getchannel('A').getbbox()


def spread(wanted, sizes, low, high):
    """Centres as near the wanted ones as the labels allow without touching
    each other or leaving low..high (wanted is sorted).
    """
    count = len(wanted)
    centres = list(wanted)
    for i in range(count):
        floor = low + sizes[i] / 2
        if i:
            floor = centres[i - 1] + (sizes[i - 1] + sizes[i]) / 2 + GAP
        centres[i] = max(centres[i], floor)
    for i in reversed(range(count)):
        ceiling = high - sizes[i] / 2
        if i < count - 1:
            ceiling = centres[i + 1] - (sizes[i + 1] + sizes[i]) / 2 - GAP
        centres[i] = min(centres[i], ceiling)
    if count and centres[0] - sizes[0] / 2 < low - 1:
        raise RuntimeError(
            'port labels do not fit along one edge: widen the render in '
            'export_fab.py or shorten the text in PORTS'
        )
    return centres


def draw_callouts(image_path, texts, boxes, flip, board_mm, board_px):
    """Draws a label in the margin and an arrow for every port.

    Args:
        texts: {key: (title, detail)}.
        boxes: {key: box in mm} of the parts to label on this side.
        flip: True for the bottom view, which mirrors x.
        board_mm, board_px: the board outline's box in mm and in pixels.
    """
    render = Image.open(image_path)
    width, height = (SCALE * v for v in render.size)
    left, top, right, bottom = (SCALE * v for v in board_px)
    mm_x0, mm_y0, mm_x1, mm_y1 = board_mm
    per_mm = (right - left) / (mm_x1 - mm_x0)

    def to_pixels(x, y):
        across = (x - mm_x0) * per_mm
        return (right - across if flip else left + across), (
            top + (y - mm_y0) * per_mm
        )

    name_font = ImageFont.load_default(NAME_SIZE * SCALE)
    detail_font = ImageFont.load_default(DETAIL_SIZE * SCALE)
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    pad, edge = PAD * SCALE, EDGE * SCALE

    # each port: its pixel box, the image side it is nearest, label size
    sides = {'left': [], 'right': [], 'top': [], 'bottom': []}
    for reference, box in boxes.items():
        xa, ya = to_pixels(box[0], box[1])
        xb, yb = to_pixels(box[2], box[3])
        x0, x1, y0, y1 = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        side = min(
            ('left', cx - left),
            ('right', right - cx),
            ('top', cy - top),
            ('bottom', bottom - cy),
            key=lambda entry: entry[1],
        )[0]
        title, detail = texts[reference]
        text_width = max(
            draw.textlength(title, name_font),
            draw.textlength(detail, detail_font),
        )
        size = (
            text_width + 2 * pad,
            (NAME_SIZE + DETAIL_SIZE) * SCALE * 1.25 + 2 * pad,
        )
        # arrow tip: halfway from the port's centre to its outer edge
        tip = {
            'left': ((x0 + cx) / 2, cy),
            'right': ((x1 + cx) / 2, cy),
            'top': (cx, (y0 + cy) / 2),
            'bottom': (cx, (y1 + cy) / 2),
        }[side]
        sides[side].append((tip, size, title, detail))

    for side, ports in sides.items():
        along = 1 if side in ('left', 'right') else 0  # axis labels spread on
        ports.sort(key=lambda port: port[0][along])
        centres = spread(
            [port[0][along] for port in ports],
            [port[1][along] for port in ports],
            edge,
            (height if along else width) - edge,
        )
        deepest = max((port[1][1 - along] for port in ports), default=0)
        for (tip, size, title, detail), centre in zip(ports, centres):
            # label box: inner edges of one side's labels line up
            if side == 'left':
                x0 = edge + deepest - size[0]
            elif side == 'right':
                x0 = width - edge - deepest
            else:
                x0 = centre - size[0] / 2
            if side == 'top':
                y0 = edge
            elif side == 'bottom':
                y0 = height - edge - size[1]
            else:
                y0 = centre - size[1] / 2
            x1, y1 = x0 + size[0], y0 + size[1]
            # leader from the label's inner edge to the tip
            reach = 2 * pad
            start = {
                'left': (x1, min(max(tip[1], y0 + reach), y1 - reach)),
                'right': (x0, min(max(tip[1], y0 + reach), y1 - reach)),
                'top': (min(max(tip[0], x0 + reach), x1 - reach), y1),
                'bottom': (min(max(tip[0], x0 + reach), x1 - reach), y0),
            }[side]
            length = math.dist(start, tip)
            ux, uy = (tip[0] - start[0]) / length, (tip[1] - start[1]) / length
            head, half = (SCALE * v for v in ARROW)
            neck = (tip[0] - ux * head, tip[1] - uy * head)
            draw.line([start, neck], fill=ACCENT, width=LINE * SCALE)
            draw.polygon(
                [
                    tip,
                    (neck[0] - uy * half, neck[1] + ux * half),
                    (neck[0] + uy * half, neck[1] - ux * half),
                ],
                fill=ACCENT,
            )
            draw.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=pad,
                fill=PAPER,
                outline=ACCENT,
                width=3 * SCALE,
            )
            draw.text((x0 + pad, y0 + pad), title, INK, name_font)
            draw.text(
                (x0 + pad, y0 + pad + NAME_SIZE * SCALE * 1.25),
                detail,
                MUTED,
                detail_font,
            )

    overlay = overlay.resize(render.size, Image.LANCZOS)
    mode = render.mode
    Image.alpha_composite(render.convert('RGBA'), overlay).convert(mode).save(
        image_path
    )


def add_callouts(board):
    """Draws the port callouts on a board's renders listed in
    export_fab.CALLOUT_RENDERS.
    """
    stem = Path(board).stem
    texts = PORTS[stem]
    groups = GROUPS.get(stem, {})
    listed = set(texts).union(*groups)
    root = parse(Path(board).read_text())
    renders = export_fab.RENDERS_BY_BOARD.get(stem, export_fab.RENDERS)
    found = set()
    for side, name, size, extra in renders:
        layer = export_fab.CALLOUT_RENDERS[stem].get(name)
        if layer is None:
            continue
        boxes = port_boxes(root, layer, listed)
        found |= set(boxes)
        missing = sorted(set(boxes) - listed)
        if missing:
            raise RuntimeError(
                f'no callout text for {", ".join(missing)}: add them to '
                'PORTS in render_callouts.py'
            )
        labels = {
            ref: (f'{ref}  {texts[ref][0]}', texts[ref][1])
            for ref in boxes
            if ref in texts
        }
        for references, label in groups.items():
            parts = [boxes.pop(ref) for ref in references if ref in boxes]
            if parts:
                boxes[references] = bounds(
                    [part[:2] for part in parts] + [part[2:] for part in parts]
                )
                labels[references] = label
        draw_callouts(
            export_fab.fab_dir(board) / name,
            labels,
            boxes,
            side == 'bottom',
            board_bounds(root),
            board_pixels(board, side, size, extra),
        )
    stale = sorted(listed - found)
    if stale:
        raise RuntimeError(
            f'render_callouts.py lists {", ".join(stale)}, which the board '
            'does not have'
        )


if __name__ == '__main__':
    add_callouts(Path(sys.argv[1]).resolve())
