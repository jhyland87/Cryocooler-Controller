"""Draws and locks rev 7's high-current copper on a pre-routed board: the 12 V input path
(J2, F1, Q1, shunt R78, the fuses F3 / F4 and the fan and pump pins) and the amplifier current path (J12, U18, J11).

Each net gets wide round-ended tracks that fill its corridor (CORRIDORS in rev7_board.py)
on both outer layers, joined by same-net vias. Every track is checked to lie
inside the corridors of its layer (plus the net's own pads). rev7_board.py calls
draw(board, CORRIDORS) in its pre-route, before the plane ties take the room.
"""
import math

import pcbnew

VIA = (0.7, 0.35)  # size and drill; IPC-2221 inner-layer k, 25 um barrel, 10 C rise: about 1 A each
F, B, I1, I2 = pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu
# corridor sides that count for each layer ('all' is every copper layer)
LAYER_SIDE = {F: ('top', 'both', 'all'), B: ('bottom', 'both', 'all'), I1: ('all',), I2: ('all',)}
A12, VIN, VSW, V12 = 'Net-(F1-Pad1)', 'VIN', 'VSW', '+12V'
FAN, PUMP = '+12V_FAN', '+12V_PUMP'  # F3 / F4 to J3 pin 2 / J4 pin 2
IPM, IPP = 'Net-(J12-Pin_1)', 'Net-(J11-Pin_1)'
ISO = 'ISO_GND'  # amplifier return, J11 pin 2 to J12 pin 2
TOLERANCE = 0.005


# (net, layer, start, end, width). A short track makes a disc. Each track is as wide as its corridor and
# the copper around it allow (fitted to the routed r8 board). The 12 V path first, then IPM (J12 pin 1 to
# U18 pins 5-8) and IPP (J11 pin 1 to U18 pins 1-4).
TRACKS = [
    (A12, F, (20.5, 106.0), (20.5, 102.8), 6.0),
    (A12, B, (20.5, 106.0), (20.5, 102.8), 6.0),
    (A12, F, (20.55, 98.55), (23.45, 98.55), 3.1),
    (A12, F, (20.85, 98.85), (20.85, 100.65), 3.7),
    (A12, B, (22.5, 98.5), (22.6, 98.5), 7.0),
    (VIN, F, (28.5, 98.5), (30.0, 98.5), 3.0),
    (VIN, F, (30.6, 98.075), (32.6, 98.075), 2.15),
    (VIN, B, (30.1, 98.5), (30.2, 98.5), 7.0),
    (VSW, F, (36.5, 98.1), (38.5, 98.1), 2.2),
    (VSW, B, (37.09, 98.4), (37.11, 98.4), 6.4),
    (V12, F, (41.8, 98.7), (43.8, 98.7), 2.6),
    (V12, B, (44.4, 98.5), (44.5, 98.5), 7.0),
    (V12, F, (43.8, 98.88), (46.85, 98.88), 2.24),
    (FAN, F, (41.65, 104.5), (41.65, 106.2), 0.8),   # fuse vias to J3 pin 2: 0.5 A x 1.25
    (PUMP, B, (46.7, 104.3), (46.7, 106.1), 1.8),    # F4 pad 1 to J4 pin 2: 2 A x 1.25
    (IPM, F, (15.25, 49.25), (15.25, 51.65), 6.5),
    (IPM, B, (15.25, 49.25), (15.25, 51.65), 6.5),
    (IPM, F, (15.265, 52.06), (15.285, 52.06), 6.4),
    (IPM, B, (15.1, 51.96), (15.45, 51.96), 6.0),
    (IPP, B, (13.275, 58.09), (15.275, 58.09), 5.95),
    (IPP, B, (12.5, 60.0), (14.0, 60.0), 8.9),
    (IPP, B, (10.64, 61.9), (10.66, 61.9), 5.2),
    (IPP, F, (12.45, 60.05), (14.05, 60.05), 8.9),
]

# ISO_GND return along the island edge, 1.25 mm from the line copper and 0.35 mm from the board edge, on all four
# layers. F.Cu stops at x 4.7 (the J11 pin 1 pad is F.Cu only), the others at 6.7; the B.Cu and inner spines
# end 3.175 mm above the island edge (round end). Each layer: spine, link to J11 pin 2, link to J12 pin 2.
for _layer, _x, _width, _y in ((F, 2.525, 4.35, 68.5), (B, 3.525, 6.35, 67.725), (I1, 3.525, 6.35, 67.725),
                               (I2, 3.525, 6.35, 67.725)):
    TRACKS += [(ISO, _layer, (_x, 40.5), (_x, _y), _width),
               (ISO, _layer, (2.75, 68.5), (9.5, 68.5), 4.8),
               (ISO, _layer, (3.35, 40.5), (12.375, 40.5), 6.0)]

# Joining vias (VIA, at least 0.8 mm apart), each inside the corridor on both layers. board_checks.py credits
# 1 A per via that sits in a track and in a track of the other layer; every track gets 1.25 x net_currents.
VIAS = [
    (A12, [
        (23.1, 97.5), (24.0, 97.5), (20.0, 98.0), (21.0, 98.0), (23.1, 98.5), (24.0, 98.5), (20.0, 99.0),
        (21.0, 99.0), (23.1, 99.5), (24.0, 99.5), (21.0, 99.85), (21.5, 100.5), (22.05, 101.1),
        (22.65, 101.65),
    ]),
    (VIN, [
        (30.1, 97.35), (30.9, 97.35), (28.0, 97.5), (28.95, 97.5), (31.65, 97.65), (29.6, 98.0),
        (30.4, 98.1), (31.15, 98.4), (31.95, 98.4), (28.0, 98.5), (28.95, 98.5), (29.85, 98.8),
        (30.6, 99.1), (31.55, 99.1), (28.0, 99.5), (28.95, 99.5),
    ]),
    (VSW, [
        (35.8, 97.35), (37.1, 97.35), (38.4, 97.4), (39.4, 97.4), (36.45, 97.85), (34.4, 98.0),
        (35.3, 98.0), (38.4, 98.3), (39.4, 98.3), (35.95, 98.5), (36.95, 98.5), (34.4, 99.0), (35.3, 99.0),
        (36.45, 99.15),
    ]),
    (V12, [
        (43.3, 97.9), (42.4, 98.7), (43.3, 98.7), (41.5, 98.75), (44.5, 98.8), (45.5, 98.8), (42.85, 99.4),
        (43.65, 99.45), (41.5, 99.55), (47.35, 99.6), (40.7, 99.65), (44.5, 99.7), (45.5, 99.7),
    ]),
    (FAN, [(41.9, 104.3), (42.9, 104.0)]),
    (IPM, [
        (13.2, 50.3), (14.4, 50.3), (15.6, 50.3), (13.2, 51.5), (14.4, 51.5), (15.6, 51.5), (13.2, 52.7),
        (14.4, 52.7), (15.6, 52.7), (13.2, 53.9), (14.4, 53.9), (15.6, 53.9),
    ]),
    (IPP, [
        (13.5, 57.3), (14.7, 57.3), (15.9, 57.3), (13.5, 58.5), (14.7, 58.5), (15.9, 58.5), (13.5, 59.7),
        (14.7, 59.7), (15.9, 59.7), (9.2, 59.75), (8.6, 60.35), (9.35, 60.65), (13.5, 60.9), (14.7, 60.9),
        (15.9, 60.9), (8.35, 61.15), (9.1, 61.45), (8.45, 61.95), (9.55, 62.15), (8.9, 62.65),
        (9.4, 63.3), (10.3, 63.3), (11.1, 63.3), (9.4, 64.2), (10.3, 64.2), (11.1, 64.2),
    ]),
    # ISO_GND: the J11 pin 2 pad, then the two corners where spine and links meet on every layer
    (ISO, [(x, y) for y in (68.3, 69.3) for x in (6.5, 7.3, 8.1, 8.9, 9.7, 10.5)]
     + [(x, y) for y in (67.0, 67.8, 68.6, 69.4, 70.2) for x in (0.9, 1.7, 2.5, 3.3, 4.1)]
     + [(x, y) for y in (40.7, 41.5, 42.3, 43.1) for x in (0.9, 1.7, 2.5, 3.3, 4.1)]),
]



def outline(start, end, width):
    """Points round a track, for checking it against the corridors."""
    radius = width / 2
    points = []
    for centre in (start, end):
        points += [(centre[0] + radius * math.cos(math.radians(a)), centre[1] + radius * math.sin(math.radians(a)))
                   for a in range(0, 360, 10)]
    length = math.dist(start, end)
    if length:
        nx, ny = (end[1] - start[1]) / length * radius, (start[0] - end[0]) / length * radius
        for k in range(1, 5):
            x, y = start[0] + (end[0] - start[0]) * k / 5, start[1] + (end[1] - start[1]) * k / 5
            points += [(x + nx, y + ny), (x - nx, y - ny)]
    return points


def allowed_boxes(board, corridors, net, layer):
    """Corridor rectangles for this layer, plus the net's own pads there."""
    boxes = [(r.min_x, r.min_y, r.max_x, r.max_y) for _name, side, r in corridors if side in LAYER_SIDE[layer]]
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetname() == net and pad.IsOnLayer(layer):
                box = pad.GetBoundingBox()
                boxes.append((box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6))
    return boxes


def inside(point, boxes):
    return any(x0 - TOLERANCE <= point[0] <= x1 + TOLERANCE and y0 - TOLERANCE <= point[1] <= y1 + TOLERANCE
               for x0, y0, x1, y1 in boxes)


def nm(value):
    return pcbnew.FromMM(value)


def draw(board, corridors):
    """Adds and locks TRACKS and VIAS; raises if a track leaves its corridors."""
    keep = list(board.GetTracks())
    for net, layer, start, end, width in TRACKS:
        boxes = allowed_boxes(board, corridors, net, layer)
        outside = [point for point in outline(start, end, width) if not inside(point, boxes)]
        if outside:
            raise RuntimeError(f'{net} track {start}-{end} w={width} leaves its corridor at {outside[0]}')
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(nm(start[0]), nm(start[1])))
        track.SetEnd(pcbnew.VECTOR2I(nm(end[0]), nm(end[1])))
        track.SetWidth(nm(width))
        track.SetLayer(layer)
        track.SetNet(board.FindNet(net))
        board.Add(track)
    for net, points in VIAS:
        for x, y in points:
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(nm(x), nm(y)))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetWidth(nm(VIA[0]))
            via.SetDrill(nm(VIA[1]))
            via.SetNet(board.FindNet(net))
            board.Add(via)
    count = 0
    for track in board.GetTracks():
        if track not in keep:
            track.SetLocked(True)
            count += 1
    print(f'locked current copper: {len(TRACKS)} tracks, {count - len(TRACKS)} vias')
