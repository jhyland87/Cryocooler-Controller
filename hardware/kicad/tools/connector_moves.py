"""Moves connectors on the routed UCS 145-125 board: J1 (USB) to the top edge, J2
(12 V) to the bottom of the left wall, J4 beside J3, and swaps J8, J11, J12 for
the Phoenix 1821698 and TE 2305908 SMT headers. Draws the current-path copper and
the J1 fan-out (the old fan-out turned 90 degrees); everything else that moved is
ripped for `gridroute.py`. Then run `gen_pcb.py link` and `finish`, and `silk_fix.py`.

Usage: connector_moves.py board.kicad_pcb (edits in place)
"""
import math
import sys

import pcbnew

import pcbmodels
import ripup
from fan_headers import KEEP, LIB, MM

RAW_NET = 'Net-(F1-Pad1)'
J11_PLUS = 'Net-(J11-Pin_1)'
J12_PLUS = 'Net-(J12-Pin_1)'
USB_D_PLUS = 'Net-(J1-D+-PadA6)'
USB_D_MINUS = 'Net-(J1-D--PadA7)'
USB_CC1 = 'Net-(J1-CC1)'
USB_CC2 = 'Net-(J1-CC2)'
USB_HOST_NETS = {'Net-(U1-USB_D-)', 'Net-(U1-USB_D+)'}

# reference -> (footprint, x, y)
SWAPS = {
    'J8': ('PhoenixContact_MC_0,5_2-G-2,54_SMD_1x02_P2.54mm_Horizontal', 6.35, 72.4),
    'J11': ('TE_2305908-2_1x02_P5.00mm_Horizontal_SMD', 11.25, 21.0),
    'J12': ('TE_2305908-3_1x03_P5.00mm_Horizontal_SMD', 11.25, 33.5),
}
# reference -> (x, y, orientation or None to keep it)
MOVES = {
    'J2': (0.0, 85.5, None),
    'J9': (0.0, 63.0, None),
    'Q21': (18.0, 79.5, None),
    'TP17': (18.45, 31.355, None),
    'J4': (92.2, 86.6, 0.0),
    'U10': (96.0, 82.5, None),
    'TP30': (91.7, 84.0, None),
    'TP16': (104.2, 85.8, None),
    'R5': (100.5, 92.5, 90.0),
    'R61': (98.0, 92.5, 90.0),
    'C62': (95.24, 93.5, 90.0),
    'TP15': (45.0, 10.6, None),
    'R42': (47.85, 10.95, None),
    'C50': (55.2, 9.9, 180.0),
    'Q25': (50.9, 10.65, None),
}
OLD_J1 = (116.325, 14.0)
NEW_J1 = (54.3, 3.675)
USB_RIGID = ('J1', 'R30', 'R31')  # turned with J1
U2_SPOT = (54.3, 4.0)
U2_PIN1 = (53.16, 4.95)

# (x0, y0, x1, y1), nets ripped inside it
WINDOWS = (
    ((0.0, 47.5, 22.5, 92.5), {RAW_NET, 'SIG_SINE', '/Amp Control/AMP_REM', 'Net-(Q21-D)', 'PG_15V'}),
    ((90.5, 72.0, 120.0, 100.0), {
        '+12V', '+3V3_COOL', 'SDA', 'SCL', 'Net-(J4-Pin_3)', 'Net-(J4-Pin_4)', 'Net-(J3-Pin_3)',
        'Net-(J3-Pin_4)', 'Net-(U10-ADDR_SEL)', 'Net-(U10-CLK)', 'FAN_ALERT'}),
    ((45.0, 0.0, 60.0, 12.0), {'/Display/DISP_BL_K', 'DISP_BL_EN', 'GND'}),
)
FAN_GROUND_BOX = (92.5, 82.0, 99.0, 88.0)  # old U10 pad vias

C5_VBUS_PAD = (56.15, 9.9)
# (net, points, width, layer)
F = pcbnew.F_Cu
B = pcbnew.B_Cu
IN2 = pcbnew.In2_Cu
TRACKS = (
    # raw 12 V from J2 up the wall to F1
    (RAW_NET, ((5.0, 80.0), (11.2, 80.0)), 2.0, F),
    (RAW_NET, ((11.2, 80.0), (9.5, 78.0), (9.5, 52.0), (11.5, 49.95), (19.0, 49.95)), 2.0, F),
    ('GND', ((5.0, 91.0), (11.2, 91.0)), 2.0, F),
    # amplifier current: J11 + to U18 pins 1-4, U18 pins 5-8 to J12 +, J11 - to J12 -
    (J11_PLUS, ((10.5, 20.5), (10.5, 11.5), (14.05, 11.5)), 2.0, F),
    (J11_PLUS, ((14.05, 10.4), (14.05, 12.57)), 2.0, F),
    (J12_PLUS, ((11.25, 33.5), (15.4, 33.5), (15.4, 19.6), (14.05, 18.25), (14.05, 15.43)), 2.0, F),
    ('ISO_GND', ((8.5, 26.0), (7.0, 26.0), (7.0, 38.5), (8.5, 38.5)), 2.0, F),
    ('SIG_SINE', ((25.59, 59.55), (21.6, 63.54), (20.85, 65.0), (20.85, 66.3), (15.6, 66.3),
                  (14.3, 66.7)), 0.25, F),
    # USB: protection part behind J1
    (USB_D_PLUS, ((53.29, 9.67), (53.29, 5.5), U2_PIN1), 0.2, B),
    (USB_D_MINUS, ((55.11, 6.28), (52.0, 3.17), (52.0, 3.05)), 0.2, IN2),
    (USB_D_MINUS, ((52.0, 3.05), (53.16, 3.05)), 0.2, B),
    ('Net-(U1-USB_D+)', ((55.44, 4.95), (56.1, 5.1), (57.05, 5.1)), 0.2, B),
    ('Net-(U1-USB_D-)', ((55.44, 3.05), (56.6, 2.85)), 0.2, B),
    ('USB_VBUS', ((55.44, 4.0), (56.6, 4.05)), 0.25, B),
    ('USB_VBUS', ((56.9, 10.35), C5_VBUS_PAD), 0.3, B),
    ('USB_VBUS', ((56.6, 4.05), (56.3, 5.0), (56.3, 6.5), (56.7, 7.0)), 0.2, F),
    ('GND', ((53.16, 4.0), (51.9, 4.4)), 0.25, B),
    (USB_CC2, ((52.55, 7.84), (52.55, 7.49)), 0.25, B),
    (USB_CC1, ((55.55, 7.36), (55.7, 8.4)), 0.2, F),
    (USB_CC1, ((55.56, 7.36), (55.7, 8.4)), 0.2, B),
)
# (net, x, y)
VIAS = (
    ('USB_VBUS', 56.6, 4.05), ('Net-(U1-USB_D+)', 57.05, 5.1), ('Net-(U1-USB_D-)', 56.6, 2.85),
    (USB_D_MINUS, 52.0, 3.05), ('GND', 51.9, 4.4), (USB_CC1, 55.7, 8.4),
    ('ISO_GND', 6.8, 28.0), ('ISO_GND', 6.8, 30.0), ('ISO_GND', 6.8, 32.0), ('ISO_GND', 6.8, 34.0),
    ('ISO_GND', 6.8, 36.0),
    ('GND', 7.2, 43.0), ('GND', 7.2, 44.2), ('GND', 6.0, 43.6),
    ('GND', 2.5, 89.4), ('GND', 2.5, 91.0), ('GND', 13.05, 90.9), ('GND', 2.9, 68.6),
    ('GND', 7.2, 76.8),
)
CLEARANCE = 0.2


def point_mm(point):
    return point.x / 1e6, point.y / 1e6


def turned(point):
    """A point of the old J1 cluster after the 90 degree turn to the top edge."""
    delta_x, delta_y = point[0] - OLD_J1[0], point[1] - OLD_J1[1]
    return NEW_J1[0] + delta_y, NEW_J1[1] - delta_x


def capture_fan_out(board):
    """Old J1 fan-out copper as data: the F.Cu routes and J1-side vias, and CC2."""
    segments, vias = [], []
    for item in board.GetTracks():
        name = item.GetNetname()
        if item.Type() == pcbnew.PCB_VIA_T:
            spot = point_mm(item.GetPosition())
            if name == USB_CC2 or (name in (USB_D_PLUS, USB_D_MINUS) and spot[0] > 110) or (
                    name == 'USB_VBUS' and spot[0] > 109):
                vias.append((name, *turned(spot)))
            continue
        layer = item.GetLayer()
        keep = name == USB_CC2 or (name in (USB_D_PLUS, USB_D_MINUS, USB_CC1) and layer == F)
        keep = keep or (name == 'USB_VBUS' and layer == F and point_mm(item.GetStart())[0] > 109
                        and point_mm(item.GetEnd())[0] > 109)
        if keep and name != USB_CC1:
            segments.append((name, turned(point_mm(item.GetStart())), turned(point_mm(item.GetEnd())),
                             item.GetWidth() / 1e6, layer))
    return segments, vias


def swap_headers(board):
    for reference, (name, x_mm, y_mm) in SWAPS.items():
        old = board.FindFootprintByReference(reference)
        nets = {pad.GetNumber(): pad.GetNetname() for pad in old.Pads()}
        new = pcbnew.FootprintLoad(LIB, name)
        new.SetReference(reference)
        new.SetValue(old.GetValue())
        new.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        board.Add(new)
        new.SetOrientationDegrees(old.GetOrientationDegrees())
        board.Remove(old)
        KEEP.append(old)
        for pad in new.Pads():
            if pad.GetNumber():
                pad.SetNet(board.FindNet(nets[pad.GetNumber()]))
        pcbmodels.attach_missing_models(new)


def move_parts(board):
    for reference, (x_mm, y_mm, angle) in MOVES.items():
        footprint = board.FindFootprintByReference(reference)
        footprint.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        if angle is not None:
            footprint.SetOrientationDegrees(angle)
    for reference in USB_RIGID:
        footprint = board.FindFootprintByReference(reference)
        old_angle = footprint.GetOrientationDegrees()
        footprint.SetPosition(pcbnew.VECTOR2I(*[MM(v) for v in turned(point_mm(footprint.GetPosition()))]))
        footprint.SetOrientationDegrees(old_angle + 90)
    # clear of Q25, and nearer the CC2 via
    board.FindFootprintByReference('R31').SetPosition(pcbnew.VECTOR2I(MM(52.55), MM(8.0)))
    protector = board.FindFootprintByReference('U2')
    protector.SetPosition(pcbnew.VECTOR2I(MM(U2_SPOT[0]), MM(U2_SPOT[1])))
    for angle in (0, 90, 180, 270):
        protector.SetOrientationDegrees(angle)
        pin = next(pad for pad in protector.Pads() if pad.GetNumber() == '1')
        spot = point_mm(pin.GetPosition())
        if abs(spot[0] - U2_PIN1[0]) < 0.1 and abs(spot[1] - U2_PIN1[1]) < 0.1:
            return
    raise RuntimeError('no U2 orientation puts pin 1 at the planned spot')


def in_box(point, box, margin=0.0):
    return (box[0] - margin < point[0] < box[2] + margin
            and box[1] - margin < point[1] < box[3] + margin)


def pad_boxes(board):
    """(box, pad) for every pad and hole of the parts that moved."""
    boxes = []
    for reference in (*SWAPS, *MOVES, *USB_RIGID, 'U2'):
        for pad in board.FindFootprintByReference(reference).Pads():
            box = pad.GetBoundingBox()
            boxes.append(((box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6,
                           box.GetBottom() / 1e6), pad))
    return boxes


def hits(item, boxes):
    """True when a track or via comes within clearance of a pad on its layer that it
    does not belong to."""
    name = item.GetNetname()
    if item.Type() == pcbnew.PCB_VIA_T:
        spot = point_mm(item.GetPosition())
        return any(pad.GetNetname() != name and in_box(spot, box, item.GetWidth() / 2e6 + CLEARANCE)
                   for box, pad in boxes)
    start, end = item.GetStart(), item.GetEnd()
    steps = max(2, int(item.GetLength() / 5e4))
    for box, pad in boxes:
        if pad.GetNetname() == name or not pad.IsOnLayer(item.GetLayer()):
            continue
        for step in range(steps + 1):
            spot = ((start.x + (end.x - start.x) * step / steps) / 1e6,
                    (start.y + (end.y - start.y) * step / steps) / 1e6)
            if in_box(spot, box, item.GetWidth() / 2e6 + CLEARANCE):
                return True
    return False


def should_rip(item):
    name = item.GetNetname()
    if name in (USB_CC1, USB_CC2, USB_D_PLUS, USB_D_MINUS, J11_PLUS, J12_PLUS) or name in USB_HOST_NETS:
        return True
    ends = ((point_mm(item.GetPosition()),) if item.Type() == pcbnew.PCB_VIA_T
            else (point_mm(item.GetStart()), point_mm(item.GetEnd())))
    if name == 'USB_VBUS' and any(end[0] > 62.0 for end in ends):
        return True
    if name == 'GND' and item.Type() == pcbnew.PCB_VIA_T and in_box(ends[0], FAN_GROUND_BOX):
        return True
    return any(name in nets and any(in_box(end, box) for end in ends) for box, nets in WINDOWS)


def segment_distance(point, start, end):
    """Distance (mm) from a point to a segment."""
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length_squared = delta_x * delta_x + delta_y * delta_y
    along = 0.0
    if length_squared > 0:
        along = ((point[0] - start[0]) * delta_x + (point[1] - start[1]) * delta_y) / length_squared
        along = max(0.0, min(1.0, along))
    return math.dist(point, (start[0] + along * delta_x, start[1] + along * delta_y))


def new_copper(segments, vias):
    """(net, start, end, width, layer or None for all) of everything drawn here."""
    copper = [(name, start, end, width, layer) for name, start, end, width, layer in segments]
    for name, points, width, layer in TRACKS:
        copper += [(name, start, end, width, layer) for start, end in zip(points, points[1:])]
    copper += [(name, (x_mm, y_mm), (x_mm, y_mm), 0.6, None) for name, x_mm, y_mm in (*vias, *VIAS)]
    return copper


def clashes(item, copper):
    """True when an old track or via of another net lies on the new copper. Left
    in place, a touching item would take on the new copper's net."""
    is_via = item.Type() == pcbnew.PCB_VIA_T
    if is_via:
        points = [point_mm(item.GetPosition())]
    else:
        start, end = point_mm(item.GetStart()), point_mm(item.GetEnd())
        count = max(1, int(math.dist(start, end) / 0.1))
        points = [(start[0] + (end[0] - start[0]) * step / count,
                   start[1] + (end[1] - start[1]) * step / count) for step in range(count + 1)]
    half_width = item.GetWidth() / 2e6
    for name, new_start, new_end, width, layer in copper:
        if name == item.GetNetname():
            continue
        if layer is not None and not is_via and item.GetLayer() != layer:
            continue
        reach = half_width + width / 2 + CLEARANCE
        if any(segment_distance(point, new_start, new_end) < reach for point in points):
            return True
    return False


def rip(board, copper):
    boxes = pad_boxes(board)
    touched = set()
    for item in list(board.GetTracks()):
        if should_rip(item) or hits(item, boxes) or clashes(item, copper):
            touched.add(item.GetNetname())
            board.Remove(item)
            KEEP.append(item)
    print('ripped nets:', sorted(touched))
    return touched


def add_track(board, name, start, end, width, layer):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    track.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    track.SetWidth(MM(width))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(name))
    board.Add(track)


def add_via(board, name, x_mm, y_mm):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
    via.SetWidth(MM(0.6))
    via.SetDrill(MM(0.3))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetNet(board.FindNet(name))
    board.Add(via)


def draw_copper(board, segments, vias):
    for name, start, end, width, layer in segments:
        add_track(board, name, start, end, width, layer)
    for name, points, width, layer in TRACKS:
        for start, end in zip(points, points[1:]):
            add_track(board, name, start, end, width, layer)
    for name, x_mm, y_mm in (*vias, *VIAS):
        add_via(board, name, x_mm, y_mm)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    segments, vias = capture_fan_out(board)
    swap_headers(board)
    move_parts(board)
    touched = rip(board, new_copper(segments, vias))
    ripup.prune(board, touched - {'GND', 'ISO_GND'})  # pour stubs would all look dangling
    draw_copper(board, segments, vias)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
