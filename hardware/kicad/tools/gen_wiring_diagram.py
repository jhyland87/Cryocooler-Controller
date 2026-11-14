"""Draws the system wiring diagram (artwork/system-wiring.png): the board
with its off-board connectors at their real edge positions, the ZE500.1
amplifier, the cryocooler and the coolant loop.

    python3 hardware/kicad/tools/gen_wiring_diagram.py

Connector positions come from bom/cryocooler_cpl.csv and their names from
PORTS in render_callouts.py. The page layout and wire routes are set by hand
below, in pixels. The drawing is built as SVG and turned into a PNG by
rsvg-convert (brew install librsvg).
"""

import base64
import csv
import shutil
import subprocess
from html import escape
from pathlib import Path

from render_callouts import PORTS

KICAD_DIR = Path(__file__).resolve().parents[1]
CPL = KICAD_DIR / 'bom' / 'cryocooler_cpl.csv'
COOLER_PNG = KICAD_DIR / 'artwork' / 'cryocooler.png'
OUT = KICAD_DIR / 'artwork' / 'system-wiring.png'
PNG_WIDTH = 2920  # twice the page width, so small text stays sharp

BOARD_MM = (100.0, 62.0)
SCALE = 6  # px per board mm
BX, BY = 180, 200  # board top-left corner on the page
PAGE = (1460, 1200)
# J12 is through-hole, so it is not in the CPL: centre of its three pins (j12_643228_board.py).
J12_Y_MM = 39.45
# The GPIO headers are left off this diagram.
SKIPPED = {'J16', 'J17', 'J18', 'J19', 'J20'}

COLOURS = {
    'drive': '#c0392b',
    'sensor': '#7d3c98',
    'cooling': '#1f618d',
    'pipe': '#5dade2',
    'power': '#ca6f1e',
    'ui': '#566573',
}
# reference -> (board edge, half width in px, wire offset along the edge in px)
CONNECTORS = {
    'J1': ('top', 24, 0),
    'J2': ('bottom', 20, 0),
    'J3': ('bottom', 22, 14),
    'J4': ('bottom', 22, 0),
    'J5': ('bottom', 22, 0),
    'J6': ('bottom', 15, 0),
    'J8': ('bottom', 15, 0),
    'J9': ('right', 16, 0),
    'J10': ('bottom', 20, 0),
    'J11': ('bottom', 20, 0),
    'J12': ('left', 24, 0),
    'J13': ('bottom', 13, -5),
    'J14': ('right', 16, 0),
    'J15': ('bottom', 25, 0),
}
# reference -> (colour group, route as ('h', x) / ('v', y) moves from the connector)
WIRES = {
    'J1': ('ui', [('v', 156)]),
    'J2': ('power', [('v', 622), ('h', 262), ('v', 650)]),
    'J5': ('cooling', [('v', 634), ('h', 345), ('v', 850), ('h', 310), ('v', 900)]),
    'J15': ('ui', [('v', 650)]),
    'J13': ('power', [('v', 730)]),
    'J3': ('cooling', [('v', 850), ('h', 480), ('v', 900)]),
    'J10': ('sensor', [('v', 1050), ('h', 1263), ('v', 946)]),
    'J4': ('cooling', [('v', 872), ('h', 660), ('v', 900)]),
    'J6': ('cooling', [('v', 850), ('h', 790), ('v', 900)]),
    'J8': ('drive', [('v', 622), ('h', 760), ('v', 650)]),
    'J9': ('drive', [('h', 835), ('v', 650)]),
    'J14': ('sensor', [('h', 1000), ('v', 318), ('h', 1104)]),
    'J12': ('drive', [('h', 150), ('v', 84), ('h', 970), ('v', 611), ('h', 1099)]),
    'J11': ('drive', [('v', 612), ('h', 136), ('v', 1095), ('h', 900), ('v', 790)]),
}
# Coolant pipes: start point, then moves. Flow runs in the order drawn.
PIPES = [
    ((1172, 635), [('h', 988), ('v', 925), ('h', 840)]),  # Flow Out -> NTC
    ((740, 925), [('h', 710)]),  # NTC -> pump
    ((610, 925), [('h', 545)]),  # pump -> radiator
    ((415, 925), [('h', 370)]),  # radiator -> flow sensor
    ((250, 925), [('h', 220), ('v', 1010), ('h', 1006), ('v', 744), ('h', 1095)]),  # -> Flow In
]
# Flow direction arrows on the pipes: (x, y, heading in degrees, 0 = right).
ARROWS = [(1050, 635, 180), (868, 925, 180), (596, 925, 180), (700, 1010, 0), (1050, 744, 0)]
# name, detail, colour group, (x, y, width, height)
BOXES = [
    ('Host PC (optional)', 'USB-C: serial, flashing', 'ui', (202, 110, 160, 46)),
    ('Dashboard', 'http://cryocooler.local', 'ui', (395, 110, 170, 46)),
    ('12 V supply', 'barrel plug, 5 A fuse', 'power', (195, 650, 135, 50)),
    ('Touch display', '2.4" ST7789V, FPC', 'ui', (365, 650, 130, 50)),
    ('Relay / SSR', 'coil, 130 mA max', 'power', (412, 730, 118, 50)),
    ('Flow sensor', 'Alphacool ES', 'cooling', (250, 900, 120, 50)),
    ('Radiator + fan', '4-pin PWM', 'cooling', (415, 900, 130, 50)),
    ('Pump', '4-pin PWM', 'cooling', (610, 900, 100, 50)),
    ('Coolant NTC', '10 k', 'cooling', (740, 900, 100, 50)),
]
AMP = (730, 650, 225, 140)
# label, x, on the top or bottom face of the amplifier
AMP_TERMINALS = [
    ('REM / GND', 760, 'top'),
    ('LOW IN (RCA)', 835, 'top'),
    ('12V / GND', 910, 'top'),
    ('SPEAKER + / -', 900, 'bottom'),
]
COOLER = (1020, 150, 400, 796)
# colour group, legend text
LEGEND = [
    ('drive', 'Drive path'),
    ('sensor', 'Sensors'),
    ('cooling', 'Coolant control'),
    ('pipe', 'Coolant pipe'),
    ('power', 'Power'),
    ('ui', 'Host / UI'),
]


def connector_positions():
    """Returns reference -> (x mm, y mm from the top edge, on the back side)."""
    spots = {'J12': (0.0, J12_Y_MM, False)}
    with CPL.open() as handle:
        for row in csv.DictReader(handle):
            x = float(row['Mid X'].rstrip('m'))
            y = -float(row['Mid Y'].rstrip('m'))
            spots[row['Designator']] = (x, y, row['Layer'] == 'Bottom')
    return spots


def trace(start, moves):
    points = [start]
    x, y = start
    for axis, value in moves:
        if axis == 'h':
            x = value
        else:
            y = value
        points.append((x, y))
    return points


def polyline(points, colour, width, dash=''):
    """A line with a white edge, so it reads as passing over what it crosses."""
    path = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
    common = f'points="{path}" fill="none" stroke-linejoin="round"'
    return (
        f'<polyline {common} stroke="#fff" stroke-width="{width + 5}"/>'
        f'<polyline {common} stroke="{colour}" stroke-width="{width}"{dash}/>'
    )


def text(x, y, body, size=13, anchor='middle', weight='normal', fill='#222', extra=''):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{fill}"{extra}>{escape(body)}</text>'
    )


def halo_text(x, y, body, **style):
    halo = ' stroke="#fff" stroke-width="4" paint-order="stroke" stroke-linejoin="round"'
    return text(x, y, body, extra=halo, **style)


def box(name, detail, colour, rect):
    x, y, w, h = rect
    # Optional equipment gets a dashed outline.
    dash = ' stroke-dasharray="6 4"' if 'optional' in name else ''
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#fff" '
        f'stroke="{colour}" stroke-width="2"{dash}/>'
        + text(x + w / 2, y + h / 2 - 3, name, size=15, weight='bold')
        + text(x + w / 2, y + h / 2 + 14, detail, size=12, fill='#555')
    )


def draw_connector(ref, spot):
    """Returns the SVG for one connector and the point its wire leaves from."""
    edge, half, offset = CONNECTORS[ref]
    x_mm, y_mm, back = spot
    label = f'{ref} · {PORTS["cryocooler"][ref][0]}'
    right, bottom = BX + BOARD_MM[0] * SCALE, BY + BOARD_MM[1] * SCALE
    # Back-side connectors are drawn dashed, just outside the edge.
    out = 20 if back else 0
    style = 'fill="#fff" stroke="#333" stroke-width="1.5"'
    if back:
        style += ' stroke-dasharray="4 3"'
    colour = '#666' if back else '#111'
    if edge in ('top', 'bottom'):
        cx = BX + x_mm * SCALE
        top = BY if edge == 'top' else bottom - 20 + out
        shape = f'<rect x="{cx - half:.1f}" y="{top}" width="{half * 2}" height="20" {style}/>'
        start = (cx + offset, top if edge == 'top' else top + 20)
        if edge == 'top':
            shape += text(cx, BY + 38, label, size=12, fill=colour)
        else:
            tx, ty = cx + offset + 4, bottom - 28
            turn = f' transform="rotate(-90 {tx:.1f} {ty})"'
            shape += text(tx, ty, label, size=12, anchor='start', fill=colour, extra=turn)
        return shape, start
    cy = BY + y_mm * SCALE
    left = BX - 12 if edge == 'left' else right - 20 + out
    shape = f'<rect x="{left}" y="{cy - half:.1f}" width="32" height="{half * 2}" {style}/>'
    if edge == 'left':
        shape += text(BX + 28, cy - 30, label, size=12, anchor='start', fill=colour)
        return shape, (left, cy)
    shape += text(right - 26, cy - 22, label, size=12, anchor='end', fill=colour)
    return shape, (left + 32, cy)


def draw_board(spots):
    w, h = BOARD_MM[0] * SCALE, BOARD_MM[1] * SCALE
    parts = [
        f'<rect x="{BX}" y="{BY}" width="{w}" height="{h}" rx="8" fill="#e8f1ec" '
        'stroke="#1e5631" stroke-width="2.5"/>',
        text(BX + w / 2, BY + 176, 'Cryocooler controller PCB', size=20, weight='bold', fill='#1e5631'),
        text(BX + w / 2, BY + 196, 'UCS 125-87, rev 4, 100 x 62 mm', size=13, fill='#1e5631'),
    ]
    # ESP32 module, antenna at the top edge.
    ux, uy = BX + spots['U1'][0] * SCALE, BY + 2
    parts.append(
        f'<rect x="{ux - 54}" y="{uy}" width="108" height="150" rx="3" fill="#fff" '
        'stroke="#333" stroke-width="1.5"/>'
        + text(ux, uy + 70, 'ESP32-S3', size=14, weight='bold')
        + text(ux, uy + 88, 'WiFi antenna', size=12, fill='#555')
    )
    sx = BX + spots['SW3'][0] * SCALE
    parts.append(
        f'<rect x="{sx - 12}" y="{BY - 6}" width="24" height="16" fill="#fff" stroke="#333" '
        'stroke-width="1.5"/>'
        + text(sx, BY + 28, 'SW3 · Power button', size=12)
    )
    return parts, (ux, BY)


def draw_amp():
    x, y, w, h = AMP
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#f2f2f2" '
        'stroke="#222" stroke-width="2.5"/>',
        text(x + w / 2, y + h / 2 - 8, 'AUDIOZERONE ZE500.1', size=16, weight='bold'),
        text(x + w / 2, y + h / 2 + 8, 'class-D amplifier', size=12, fill='#555'),
        # The GAIN trimpot sets how much output a full-scale sine gives.
        f'<circle cx="{x + 20}" cy="{y + 96}" r="8" fill="#fff" stroke="{COLOURS["drive"]}" stroke-width="2"/>',
        f'<line x1="{x + 20}" y1="{y + 96}" x2="{x + 25}" y2="{y + 90}" stroke="{COLOURS["drive"]}" stroke-width="2"/>',
        text(x + 34, y + 100, 'GAIN trimpot: sets 10 Vpp = 120 VAC', size=10.5, anchor='start', fill=COLOURS['drive']),
    ]
    for label, tx, face in AMP_TERMINALS:
        ty = y if face == 'top' else y + h - 12
        parts.append(f'<rect x="{tx - 9}" y="{ty}" width="18" height="12" fill="#222"/>')
        parts.append(text(tx, ty + 26 if face == 'top' else ty - 6, label, size=10.5))
    # The amplifier's own supply is not wired through the board.
    px = AMP_TERMINALS[2][1]
    parts.append(polyline([(px, y), (px, y - 26)], COLOURS['power'], 2.5))
    for row, line in enumerate(('Amp supply', '12 V DC (10-16 V)', 'not through the board')):
        parts.append(text(px - 8, y - 66 + row * 15, line, size=11.5, fill=COLOURS['power']))
    return parts


def draw_cooler():
    x, y, w, h = COOLER
    data = base64.b64encode(COOLER_PNG.read_bytes()).decode()
    return [
        f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="data:image/png;base64,{data}"/>',
        text(x + w / 2 + 20, y - 14, 'Cryocooler with cooling jacket', size=18, weight='bold'),
    ]


def draw_cooler_labels():
    """Drawn last, over the wires that end on the cooler."""
    return [
        f'<rect x="1104" y="310" width="24" height="15" fill="{COLOURS["sensor"]}" stroke="#fff"/>',
        halo_text(1060, 304, 'IMU board', size=13, weight='bold', fill=COLOURS['sensor']),
        halo_text(1090, 592, 'Power', size=15, weight='bold', fill=COLOURS['drive']),
        halo_text(1188, 640, 'Flow out', size=15, weight='bold', anchor='start'),
        halo_text(1112, 749, 'Flow in', size=15, weight='bold', anchor='start'),
        f'<circle cx="1263" cy="940" r="6" fill="{COLOURS["sensor"]}" stroke="#fff"/>',
        halo_text(1326, 936, 'PT1000 RTD', size=13, weight='bold', anchor='start', fill=COLOURS['sensor']),
        halo_text(1326, 952, 'cold tip', size=12, anchor='start', fill=COLOURS['sensor']),
    ]


def draw_arrow(x, y, heading):
    return (
        f'<polygon points="9,0 -6,-8 -6,8" fill="#1f618d" stroke="#fff" stroke-width="1" '
        f'transform="translate({x} {y}) rotate({heading})"/>'
    )


def draw_legend():
    parts = []
    y = PAGE[1] - 48
    for index, (group, label) in enumerate(LEGEND):
        x = 40 + index * 180
        width = 7 if group == 'pipe' else 3
        parts.append(
            f'<line x1="{x}" y1="{y}" x2="{x + 36}" y2="{y}" stroke="{COLOURS[group]}" '
            f'stroke-width="{width}"/>'
        )
        parts.append(text(x + 44, y + 4, label, anchor='start'))
    x = 40 + len(LEGEND) * 180
    parts.append(
        f'<rect x="{x}" y="{y - 8}" width="36" height="16" fill="#fff" stroke="#333" '
        'stroke-width="1.5" stroke-dasharray="4 3"/>'
    )
    parts.append(text(x + 44, y + 4, 'Connector on the back side', anchor='start'))
    note = (
        'Connector positions on the board are to scale. The coolant loop order is assumed. '
        'GPIO headers J16 to J20 are not shown.'
    )
    parts.append(text(40, y + 30, note, size=12, anchor='start', fill='#555'))
    return parts


def main():
    drawn = set(CONNECTORS)
    expected = {ref for ref in PORTS['cryocooler'] if ref.startswith('J')}
    if drawn | SKIPPED != expected or set(WIRES) != drawn:
        raise SystemExit(f'connector list out of step with PORTS: {sorted(expected ^ (drawn | SKIPPED))}')

    spots = connector_positions()
    board, antenna = draw_board(spots)
    connectors, starts = [], {}
    for ref in CONNECTORS:
        shape, starts[ref] = draw_connector(ref, spots[ref])
        connectors.append(shape)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAGE[0]} {PAGE[1]}" '
        'font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{PAGE[0]}" height="{PAGE[1]}" fill="#fff"/>',
        text(40, 42, 'Cryocooler system wiring', size=26, anchor='start', weight='bold'),
    ]
    svg += draw_cooler() + board
    for start, moves in PIPES:
        svg.append(polyline(trace(start, moves), COLOURS['pipe'], 7))
    svg += [draw_arrow(*arrow) for arrow in ARROWS]
    for ref, (group, moves) in WIRES.items():
        points = trace(starts[ref], moves)
        svg.append(polyline(points, COLOURS[group], 2.5))
        x, y = points[-1]
        svg.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{COLOURS[group]}"/>')
    dash = ' stroke-dasharray="3 5"'
    svg.append(polyline([antenna, (antenna[0], 156)], COLOURS['ui'], 2.5, dash))
    svg += connectors
    svg += [box(*item[:2], COLOURS[item[2]], item[3]) for item in BOXES]
    svg += draw_amp() + draw_cooler_labels()
    svg += [
        halo_text(
            560, 76,
            'J12 to cooler motor: 0-120 VAC (+ / - / GND), level proportional to the J9 sine: 0-10 Vpp = 0-100 %',
            fill=COLOURS['drive'],
        ),
        halo_text(528, 1116, 'Amplifier speaker output, measured by the ACS37800 on its way to J12', fill=COLOURS['drive']),
        halo_text(488, 182, 'over WiFi, when connected', size=12, anchor='start', fill=COLOURS['ui']),
        halo_text(846, 520, '60 Hz sine', anchor='start', fill=COLOURS['drive']),
        halo_text(846, 536, '0-10 Vpp = 0-100 %', size=12, anchor='start', fill=COLOURS['drive']),
        halo_text(846, 551, 'of the 120 VAC on J12', size=12, anchor='start', fill=COLOURS['drive']),
        halo_text(720, 640, 'switched 12 V', size=12, anchor='end', fill=COLOURS['drive']),
        halo_text(792, 270, '8-way: SPI, INT1/2, 3V3, GND', size=12, anchor='start', fill=COLOURS['sensor']),
        halo_text(1110, 1070, '4-wire: F+ S+ S- F-', size=12, fill=COLOURS['sensor']),
    ]
    svg += draw_legend()
    svg.append('</svg>')
    converter = shutil.which('rsvg-convert')
    if not converter:
        raise SystemExit('rsvg-convert not found: brew install librsvg')
    subprocess.run(
        [converter, '-w', str(PNG_WIDTH), '-o', str(OUT)],
        input='\n'.join(svg).encode(),
        check=True,
    )
    print(f'wrote {OUT.relative_to(KICAD_DIR.parents[1])}')


if __name__ == '__main__':
    main()
