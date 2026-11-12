"""Builds the IMU board, hardware/kicad/imu/imu.kicad_pcb: 18 x 18 mm, two layers.

J1 sits on the bottom edge and the M3 hole on the top edge, both on the centre
line, so a cable pull runs through the screw. U1 sits beside the hole. Layout
for U1 follows ST's guidance for LGA sensors (TN0018, as summarised in ST's
"How to optimize your PCB design for MEMS sensors"): no top-layer tracks or vias
under the part, equal-width stubs leaving each pad along its long axis, and the
top ground pour kept off its pads. The bottom layer may run under it.

Every part, track and via comes from the tables below, so a run rebuilds the
whole board and hand edits do not survive. The cable is wired pin for pin, so
two signal pairs cross (SCK/MOSI and INT1/INT2); MOSI, INT2, MISO and +3V3 take
the bottom layer for part of their run.
The front silk carries U1's axis glyph (DS12814 Figure 4), and the ground
stitching keeps clear of the labels in imu/mask_labels.json.

Run with KiCad's python (it provides pcbnew):
    $KPY hardware/kicad/tools/imu_board.py           # rebuild the board
    $KPY hardware/kicad/tools/imu_board.py boardid   # stamp the board ID, after review
Then apply the labels and check it:
    $KPY hardware/kicad/tools/mask_labels.py imu/imu.kicad_pcb imu/mask_labels.json
    kicad-cli pcb drc --schematic-parity --severity-all imu/imu.kicad_pcb
"""

import json
import math
import subprocess
import sys

import pcbnew

import gen_pcb
import mask_labels
import pcbmodels
from pcbnetlist import KICAD_DIR, load_netlist

IMU_DIR = KICAD_DIR / 'imu'
BOARD_PATH = IMU_DIR / 'imu.kicad_pcb'
SCHEMATIC = IMU_DIR / 'imu.kicad_sch'
SIZE = 18.0
CORNER_RADIUS = 1.0
SIGNAL = 0.2  # every U1 stub and signal track
POWER = 0.3
VIA = (0.6, 0.3)
HOLE = (9.0, 3.4)
HOLE_KEEPOUT = 3.0  # copper-free radius: an M3 pan head is 5.5-5.7 mm across
POUR_CLEARANCE = 0.2
STITCH_PITCH = 0.25  # candidate grid for ground stitching vias
STITCH_SPACING = 2.0
STITCH_CLEARANCE = 0.25
J1_MODEL = ('Micro_Lock_Plus-5054480891.step', (0.0, -0.5, 0.0))  # as on J14
BOARD_NAME = 'Cryocooler IMU'
BOARD_ID_SPOT = (9.0, 11.4)  # back silk, mirrored, between J1's pin-name rows
ID_LINE_PITCH = 1.5  # the main board's 1.44 leaves the 'y' of Cryocooler 0.14 mm from line 2
LABEL_FILE = IMU_DIR / 'mask_labels.json'
SILK_LINE = 0.15
GLYPH_TEXT = 0.7
# U1's axes (DS12814 Figure 4) as placed at 90 degrees: +X toward the hole,
# +Y toward the left edge, +Z out of the top face
AXIS_ORIGIN = (4.0, 2.0)
AXIS_X_TIP = (4.0, 0.5)
AXIS_Y_TIP = (1.6, 2.0)

# ref -> (x, y, rotation in degrees)
PLACEMENT = {
    'J1': (9.0, 12.85, 0),  # mating face 0.2 mm inside the bottom edge
    'U1': (15.2, 4.0, 90),
    'C1': (16.9, 1.7, 0),  # VDD
    'C2': (17.3, 6.75, 270),  # VDDIO
    'C3': (15.85, 16.85, 0),  # bulk
    'R1': (13.1, 1.9, 270),  # CS pull-up
    'R2': (15.6, 11.6, 0),
    'D1': (15.625, 13.5, 0),
    'TP1': (1.6, 14.4, 0),  # 3V3
    'TP2': (1.6, 16.6, 0),  # GND
    'TP3': (15.2, 9.2, 0),  # SCK
    'TP4': (1.6, 5.6, 0),  # MOSI
    'TP5': (1.6, 12.2, 0),  # MISO
    'TP6': (1.6, 3.4, 0),  # CS
    'TP7': (1.6, 7.8, 0),  # INT1
    'TP8': (1.6, 10.0, 0),  # INT2
}

# (net, layer, width, points)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
TRACKS = [
    # U1 left side: CS, SCK, MOSI fan down into the channel under the hole
    ('IMU_CS', F, SIGNAL, [(14.2875, 3.5), (12.55, 3.5), (12.55, 4.75), (10.6, 6.7), (8.375, 6.7), (8.375, 9.15)]),
    ('IMU_CS', F, SIGNAL, [(13.1, 2.41), (13.1, 3.5)]),
    ('IMU_CS', F, SIGNAL, [(8.375, 6.7), (6.2, 6.7), (5.4, 5.9), (5.4, 4.9), (4.9, 4.4), (2.4, 4.4), (1.6, 3.6)]),
    ('SPI_SCK', F, SIGNAL, [(14.2875, 4.0), (12.95, 4.0), (12.95, 5.15), (11.0, 7.1), (10.875, 7.1), (10.875, 9.15)]),
    ('SPI_SCK', F, SIGNAL, [(10.875, 9.15), (15.2, 9.15)]),
    ('SPI_MOSI', F, SIGNAL, [(14.2875, 4.5), (13.35, 4.5), (13.35, 5.55), (11.85, 7.05), (11.85, 7.75)]),
    ('SPI_MOSI', B, SIGNAL, [(11.85, 7.75), (11.75, 7.65), (4.05, 7.65), (3.1, 6.7), (1.6, 6.7)]),
    ('SPI_MOSI', F, SIGNAL, [(9.625, 7.65), (9.625, 9.15)]),
    ('SPI_MOSI', F, SIGNAL, [(1.6, 6.7), (1.6, 5.6)]),
    # U1 bottom: MISO and the ground pair down (clear of the U1 label), INT1
    # round the right of J1
    ('SPI_MISO', F, SIGNAL, [(14.45, 5.1625), (14.45, 5.75), (14.0, 6.2)]),
    ('SPI_MISO', B, SIGNAL, [(14.0, 6.2), (14.0, 9.275), (8.375, 14.9)]),
    ('SPI_MISO', F, SIGNAL, [(8.375, 14.9), (8.375, 16.55)]),
    ('SPI_MISO', B, SIGNAL, [(8.375, 14.9), (8.375, 15.9), (2.6, 15.9), (2.6, 13.8), (2.1, 13.3), (1.6, 13.3)]),
    ('SPI_MISO', F, SIGNAL, [(1.6, 13.3), (1.6, 12.2)]),
    ('GND', F, SIGNAL, [(14.95, 5.1625), (14.95, 6.0), (15.45, 6.0), (15.45, 5.1625)]),
    ('IMU_INT1', F, SIGNAL, [(15.95, 5.1625), (15.95, 9.85), (14.95, 10.85), (7.125, 10.85), (7.125, 9.15)]),
    ('IMU_INT1', F, SIGNAL, [(7.125, 8.7), (2.5, 8.7), (1.6, 7.8)]),
    # U1 right: the second ground pair, VDDIO to C2
    ('GND', F, SIGNAL, [(16.1125, 3.5), (16.95, 3.5)]),
    ('GND', F, SIGNAL, [(16.1125, 4.0), (16.95, 4.0)]),
    ('+3V3', F, SIGNAL, [(16.1125, 4.5), (17.3, 4.5), (17.3, 6.27)]),
    # U1 top: VDD to C1, INT2 straight up to its via
    ('+3V3', F, SIGNAL, [(15.95, 2.8375), (15.95, 2.02), (16.27, 1.7), (16.42, 1.7)]),
    ('+3V3', F, SIGNAL, [(16.42, 1.7), (16.42, 0.9)]),
    ('IMU_INT2', F, SIGNAL, [(15.45, 2.8375), (15.45, 1.4)]),
    ('IMU_INT2', B, SIGNAL, [(15.45, 1.4), (13.4, 3.45), (13.4, 8.6), (7.125, 14.875)]),
    ('IMU_INT2', F, SIGNAL, [(7.125, 14.875), (7.125, 16.55)]),
    ('IMU_INT2', B, SIGNAL, [(7.125, 14.875), (7.125, 11.6), (6.6, 11.1), (1.6, 11.1)]),
    ('IMU_INT2', F, SIGNAL, [(1.6, 11.1), (1.6, 10.0)]),
    # +3V3: C1 and R1 at the top, down the right edge to C2, on to J1 pin 4,
    # the LED and C3 at the bottom right, and TP1
    ('+3V3', F, SIGNAL, [(13.1, 1.39), (13.1, 0.65)]),
    ('+3V3', B, POWER, [(13.1, 0.65), (16.17, 0.65), (16.42, 0.9)]),
    ('+3V3', B, POWER, [(16.42, 0.9), (17.0, 0.9), (17.45, 1.35), (17.45, 5.15), (17.3, 5.3)]),
    ('+3V3', B, POWER, [(17.3, 5.3), (17.3, 7.225), (9.625, 14.9)]),
    ('+3V3', F, POWER, [(9.625, 14.9), (9.625, 16.55)]),
    ('+3V3', B, POWER, [(12.925, 11.6), (14.35, 11.6)]),
    ('+3V3', F, POWER, [(14.35, 11.6), (14.35, 16.85), (14.9, 16.85)]),
    ('+3V3', F, SIGNAL, [(14.35, 11.6), (15.09, 11.6)]),
    ('+3V3', B, POWER, [(9.625, 14.9), (9.625, 16.8), (2.5, 16.8), (1.6, 15.9), (1.6, 15.5)]),
    ('+3V3', F, SIGNAL, [(1.6, 15.5), (1.6, 14.4)]),
    # R2 to the LED, round the right of the R2 label
    ('Net-(D1-A)', F, SIGNAL, [(16.11, 11.6), (16.9, 11.6), (16.9, 13.5), (16.11, 13.5)]),
    # J1 pin 2 to the bottom pour
    ('GND', F, POWER, [(10.875, 14.9), (10.875, 16.55)]),
]

# (net, x, y)
VIAS = [
    ('SPI_MOSI', 11.85, 7.75),
    ('SPI_MOSI', 9.625, 7.65),
    ('SPI_MOSI', 1.6, 6.7),
    ('SPI_MISO', 14.0, 6.2),
    ('SPI_MISO', 8.375, 14.9),
    ('SPI_MISO', 1.6, 13.3),
    ('IMU_INT2', 15.45, 1.4),
    ('IMU_INT2', 7.125, 14.875),
    ('IMU_INT2', 1.6, 11.1),
    ('+3V3', 13.1, 0.65),
    ('+3V3', 16.42, 0.9),
    ('+3V3', 17.3, 5.3),
    ('+3V3', 9.625, 14.9),
    ('+3V3', 14.35, 11.6),
    ('+3V3', 1.6, 15.5),
    ('GND', 10.875, 14.9),
    ('GND', 16.85, 2.75),  # the corner right of U1 (C1, pads 6 and 7)
]

KEEP = []  # SWIG frees items whose wrappers die before the save


def mm(value):
    return pcbnew.FromMM(value)


def point(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def new_board():
    """An empty board bound to imu.kicad_pro, so it carries the project rules."""
    BOARD_PATH.write_text('(kicad_pcb (version 20260206) (generator "imu_board"))\n')
    board = pcbnew.LoadBoard(str(BOARD_PATH))
    board.SetCopperLayerCount(2)
    return board


def add_outline(board):
    """18 x 18 mm with 1 mm corner radii."""
    r, s = CORNER_RADIUS, SIZE
    for start, end in (((r, 0), (s - r, 0)), ((s, r), (s, s - r)), ((s - r, s), (r, s)), ((0, s - r), (0, r))):
        line = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(point(*start))
        line.SetEnd(point(*end))
        add_edge(board, line)
    for cx, cy, sx, sy in ((r, r, 0, r), (s - r, r, s - r, 0), (s - r, s - r, s, s - r), (r, s - r, r, s)):
        arc = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        arc.SetCenter(point(cx, cy))
        arc.SetStart(point(sx, sy))
        arc.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        add_edge(board, arc)


def add_edge(board, shape):
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetWidth(mm(0.05))
    board.Add(shape)


def net_item(board, name):
    item = board.FindNet(name)
    if item is None:
        item = pcbnew.NETINFO_ITEM(board, name)
        board.Add(item)
    return item


def add_footprints(board, parts, nets):
    pad_nets = {(ref, pad): name for name, nodes in nets.items() for ref, pad in nodes}
    for ref, part in sorted(parts.items()):
        footprint = pcbnew.FootprintLoad(*gen_pcb.footprint_path(part['footprint']))
        if footprint is None:
            raise RuntimeError(f'missing footprint {part["footprint"]}')
        if ref == 'J1':
            set_model(footprint, *J1_MODEL)
        else:
            pcbmodels.attach_missing_models(footprint)
        gen_pcb.widen_silk(footprint)
        footprint.SetReference(ref)
        footprint.SetValue(part['value'])
        gen_pcb.link_to_symbol(footprint, part)
        footprint.Reference().SetVisible(False)  # labels come from mask_labels.json
        footprint.Value().SetVisible(False)
        board.Add(footprint)
        x, y, angle = PLACEMENT[ref]
        footprint.SetPosition(point(x, y))
        footprint.SetOrientationDegrees(angle)
        for pad in footprint.Pads():
            name = pad_nets.get((ref, pad.GetNumber()))
            if name is not None:
                pad.SetNet(net_item(board, name))
    hole = pcbnew.FootprintLoad(str(gen_pcb.STOCK_FOOTPRINTS / 'MountingHole.pretty'), 'MountingHole_3.2mm_M3')
    hole.SetReference('')
    hole.Reference().SetVisible(False)
    hole.Value().SetVisible(False)
    hole.SetBoardOnly(True)  # mechanical: not in the schematic
    hole.SetPosition(point(*HOLE))
    board.Add(hole)


def set_model(footprint, name, offset):
    while footprint.Models().size():
        footprint.Models().pop_back()
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = f'{pcbmodels.MODEL_URI}/{name}'
    model.m_Offset = pcbnew.VECTOR3D(*offset)
    model.m_Show = True
    footprint.Models().push_back(model)


def add_tracks(board):
    for net, layer, width, points in TRACKS:
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetLayer(layer)
            track.SetWidth(mm(width))
            track.SetStart(point(*start))
            track.SetEnd(point(*end))
            track.SetNet(board.FindNet(net))
            board.Add(track)
    for net, x, y in VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(x, y))
        via.SetWidth(mm(VIA[0]))
        via.SetDrill(mm(VIA[1]))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetNet(board.FindNet(net))
        board.Add(via)


def polygon(points):
    shape = pcbnew.SHAPE_POLY_SET()
    shape.NewOutline()
    for x, y in points:
        shape.Append(mm(x), mm(y))
    return shape


def circle(cx, cy, radius, steps=48):
    """A polygon around the circle: its edges touch it, so nothing inside the
    polygon reaches into the circle.
    """
    outer = radius / math.cos(math.pi / steps)
    return [(cx + outer * math.cos(2 * math.pi * i / steps),
             cy + outer * math.sin(2 * math.pi * i / steps)) for i in range(steps)]


def rect(cx, cy, half_x, half_y):
    return [(cx - half_x, cy - half_y), (cx + half_x, cy - half_y),
            (cx + half_x, cy + half_y), (cx - half_x, cy + half_y)]


def add_rule_area(board, name, points, layers, tracks=True, vias=True, fills=True):
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetZoneName(name)
    zone.SetDoNotAllowTracks(tracks)
    zone.SetDoNotAllowVias(vias)
    zone.SetDoNotAllowZoneFills(fills)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    zone.SetLayerSet(layers)
    zone.Outline().Append(polygon(points))
    board.Add(zone)


def add_keepouts(board):
    """The screw head, and U1's top side: no copper between its pads, no pour on them."""
    add_rule_area(board, 'M3 screw head', circle(*HOLE, HOLE_KEEPOUT), pcbnew.LSET.AllCuMask())
    x, y, _ = PLACEMENT['U1']
    top = pcbnew.LSET()
    top.AddLayer(F)
    # between the pad rows (rotated 90: 2.5 mm across x, 3.0 mm along y)
    add_rule_area(board, 'U1 underside', rect(x, y, 0.55, 0.8), top, fills=True)
    # body plus 0.4 mm: the pour reaches the pads only through their stubs
    add_rule_area(board, 'U1 pour clearance', rect(x, y, 1.65, 1.9), top, tracks=False, vias=False)


def add_silk_line(board, start, end):
    line = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    line.SetStart(point(*start))
    line.SetEnd(point(*end))
    line.SetWidth(mm(SILK_LINE))
    line.SetLayer(pcbnew.F_SilkS)
    board.Add(line)
    return line


def add_arrow(board, start, tip, length=0.45, half_width=0.2):
    """A silk line from `start` with a filled head at `tip` (axis-aligned)."""
    dx, dy = (tip[0] > start[0]) - (tip[0] < start[0]), (tip[1] > start[1]) - (tip[1] < start[1])
    base = (tip[0] - dx * length, tip[1] - dy * length)
    head = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    head.SetPolyPoints([point(*tip), point(base[0] - dy * half_width, base[1] - dx * half_width),
                        point(base[0] + dy * half_width, base[1] + dx * half_width)])
    head.SetFilled(True)
    head.SetWidth(0)
    head.SetLayer(pcbnew.F_SilkS)
    board.Add(head)
    return [add_silk_line(board, start, base), head]


def add_axis_glyph(board):
    """U1's sensing axes on the top silk: X and Y arrows from a circled dot (Z,
    out of the board). Returns the drawn items.
    """
    ox, oy = AXIS_ORIGIN
    ring = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
    ring.SetCenter(point(ox, oy))
    ring.SetEnd(point(ox + 0.25, oy))
    dot = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
    dot.SetCenter(point(ox, oy))
    dot.SetEnd(point(ox + 0.04, oy))
    dot.SetFilled(True)
    items = [ring, dot]
    for shape in items:
        shape.SetWidth(mm(SILK_LINE))
        shape.SetLayer(pcbnew.F_SilkS)
        board.Add(shape)
    items += add_arrow(board, (ox, oy - 0.25), AXIS_X_TIP)
    items += add_arrow(board, (ox - 0.25, oy), AXIS_Y_TIP)
    for letter, x, y in (('X', AXIS_X_TIP[0] + 0.65, AXIS_X_TIP[1] + 0.35),
                         ('Y', AXIS_Y_TIP[0] + 0.15, AXIS_Y_TIP[1] - 0.8),
                         ('Z', ox + 0.7, oy + 0.05)):
        text = pcbnew.PCB_TEXT(board)
        text.SetText(letter)
        text.SetLayer(pcbnew.F_SilkS)
        text.SetTextSize(pcbnew.VECTOR2I_MM(GLYPH_TEXT, GLYPH_TEXT))
        text.SetTextThickness(mm(0.1))
        text.SetPosition(point(x, y))
        text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        board.Add(text)
        items.append(text)
    return items


def label_outlines(board):
    """Ink outlines of the labels in LABEL_FILE, which the stitching keeps clear of."""
    if not LABEL_FILE.exists():
        return []
    outlines = []
    for label in json.loads(LABEL_FILE.read_text()):
        text = mask_labels.make_label(board, label)
        outline = pcbnew.SHAPE_POLY_SET()
        text.TransformTextToPolySet(outline, 0, mm(0.005), pcbnew.ERROR_INSIDE)
        outlines.append(outline)
        KEEP.append(text)
    return outlines


def add_stitching(board, glyph):
    """Ground vias on a STITCH_PITCH grid wherever one clears all other copper,
    the edge, the keep-outs, the labels and the axis glyph, at least
    STITCH_SPACING apart: the signal tracks cut both pours into pieces, and each
    piece needs a way to the other layer.
    """
    radius = VIA[0] / 2
    gnd = board.FindNet('GND').GetNetCode()
    obstacles = [item for item in list(board.GetTracks()) + [pad for fp in board.GetFootprints() for pad in fp.Pads()]
                 if item.GetNetCode() != gnd or item.Type() == pcbnew.PCB_PAD_T]
    blocked = [polygon(circle(*HOLE, HOLE_KEEPOUT + radius))]
    x, y, _ = PLACEMENT['U1']
    blocked.append(polygon(rect(x, y, 1.65 + radius, 1.9 + radius)))
    box = glyph[0].GetBoundingBox()
    for item in glyph[1:]:
        box.Merge(item.GetBoundingBox())
    clear = label_outlines(board) + [polygon([(box.GetLeft() / 1e6, box.GetTop() / 1e6),
                                              (box.GetRight() / 1e6, box.GetTop() / 1e6),
                                              (box.GetRight() / 1e6, box.GetBottom() / 1e6),
                                              (box.GetLeft() / 1e6, box.GetBottom() / 1e6)])]
    placed = [(via.GetPosition().x / 1e6, via.GetPosition().y / 1e6) for via in board.GetTracks()
              if via.Type() == pcbnew.PCB_VIA_T and via.GetNetCode() == gnd]
    edge = 0.3 + radius
    steps = int(SIZE / STITCH_PITCH)
    for i in range(steps + 1):
        for j in range(steps + 1):
            px, py = i * STITCH_PITCH, j * STITCH_PITCH
            if not edge <= px <= SIZE - edge or not edge <= py <= SIZE - edge:
                continue
            corner_x = min(max(px, CORNER_RADIUS), SIZE - CORNER_RADIUS)
            corner_y = min(max(py, CORNER_RADIUS), SIZE - CORNER_RADIUS)
            if (px - corner_x) ** 2 + (py - corner_y) ** 2 > (CORNER_RADIUS - edge) ** 2:
                continue
            if any((px - qx) ** 2 + (py - qy) ** 2 < STITCH_SPACING ** 2 for qx, qy in placed):
                continue
            centre = point(px, py)
            if any(shape.Collide(centre, mm(radius)) for shape in blocked):
                continue
            if any(shape.Collide(centre, mm(radius + STITCH_CLEARANCE)) for shape in clear):
                continue
            if any(item.GetEffectiveShape(layer).Collide(centre, mm(radius + STITCH_CLEARANCE))
                   for item in obstacles for layer in (F, B) if item.IsOnLayer(layer)):
                continue
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(centre)
            via.SetWidth(mm(VIA[0]))
            via.SetDrill(mm(VIA[1]))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetNet(board.FindNet('GND'))
            board.Add(via)
            placed.append((px, py))


def add_pours(board):
    for layer in (F, B):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(board.FindNet('GND'))
        zone.SetLocalClearance(mm(POUR_CLEARANCE))
        zone.SetMinThickness(mm(0.2))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        zone.Outline().Append(polygon([(0, 0), (SIZE, 0), (SIZE, SIZE), (0, SIZE)]))
        board.Add(zone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def save(board):
    pcbnew.SaveBoard(str(BOARD_PATH), board, True)  # True: leave imu.kicad_pro alone
    text = BOARD_PATH.read_text()
    text = text.replace('\t(setup\n', '\t(setup\n' + gen_pcb.stackup_block(2), 1)
    BOARD_PATH.write_text(text)


def build():
    pcbmodels.MODEL_URI = '${KIPRJMOD}/../lib/cryocooler.3dshapes'
    pcbmodels.PROJECT_DIR = IMU_DIR
    parts, nets = load_netlist(SCHEMATIC)
    board = new_board()
    add_outline(board)
    add_footprints(board, parts, nets)
    add_tracks(board)
    add_keepouts(board)
    glyph = add_axis_glyph(board)
    add_stitching(board, glyph)
    add_pours(board)
    save(board)
    print('wrote', BOARD_PATH)


def stamp_board_id():
    """Board ID block on the back silk: name and short commit, mirrored, replacing
    any earlier one (the main board's font: 1 x 0.9 mm, 0.15 mm stroke).
    """
    revision = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True,
                              text=True, cwd=KICAD_DIR, check=True).stdout.strip()
    board = pcbnew.LoadBoard(str(BOARD_PATH))
    for drawing in list(board.GetDrawings()):
        if drawing.Type() == pcbnew.PCB_TEXT_T and drawing.GetLayer() == pcbnew.B_SilkS:
            if drawing.GetText() == BOARD_NAME or drawing.GetText().startswith('BETA rev'):
                KEEP.append(drawing)
                board.Remove(drawing)
    x, y = BOARD_ID_SPOT
    for index, line in enumerate((BOARD_NAME, f'BETA rev {revision}')):
        text = pcbnew.PCB_TEXT(board)
        text.SetText(line)
        text.SetLayer(pcbnew.B_SilkS)
        text.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(0.9)))
        text.SetTextThickness(mm(0.15))
        text.SetMirrored(True)
        text.SetPosition(point(x, y + index * ID_LINE_PITCH))
        board.Add(text)
        KEEP.append(text)
    pcbnew.SaveBoard(str(BOARD_PATH), board, True)


if __name__ == '__main__':
    if sys.argv[1:] == ['boardid']:
        stamp_board_id()
    else:
        build()
