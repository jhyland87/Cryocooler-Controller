"""Swaps the USB and display connectors on the top edge and turns J15 so its
opening faces into the board. J1 takes U2, R3, R4, C5 with it; J15 takes U27 and
its local parts. Local copper moves rigidly; the rest is ripped for gridroute.py.

Usage: swap_usb_display.py board.kicad_pcb (edits in place), then gridroute.py,
then swap_usb_display.py board.kicad_pcb finish, the silk steps, and
swap_usb_display.py board.kicad_pcb silk
"""
import sys

import pcbnew

MM = pcbnew.FromMM
USB_SHIFT = -21.8
TOUCH_SHIFT = 20.0
USB_PARTS = ('J1', 'U2', 'R3', 'R4', 'C5')
TOUCH_PARTS = ('U27', 'C123', 'C124', 'R168', 'TP42')
J15_SPOT = (53.2, 4.0, 0)

USB_BOX = (48.5, -1.0, 59.7, 11.0)
TOUCH_BOX = (27.5, 2.0, 38.4, 11.7)
USB_LOCAL_NETS = {
    'Net-(J1-CC1)', 'Net-(J1-CC2)', 'Net-(J1-D+-PadA6)', 'Net-(J1-D--PadA7)',
    'USB_VBUS', 'GND',
}
TOUCH_LOCAL_NETS = {'+3V3', 'GND', '/Display/TOUCH_IRQ'}
# copper wholly inside goes; far-end copper stays for the router to join
RIP_BOX = (26.0, -1.0, 60.0, 16.5)
PLANE_BOX = (26.0, -1.0, 60.0, 12.0)
PLANE_NETS = {'GND', '+3V3'}
RIP_NETS = {
    'Net-(J1-CC1)', 'Net-(J1-CC2)', 'Net-(J1-D+-PadA6)', 'Net-(J1-D--PadA7)', 'USB_VBUS',
    'SPI_MISO', 'SPI_MOSI', 'SPI_SCK', 'TOUCH_CS', 'DISP_CS', 'DISP_DC',
    '/Display/TOUCH_XP', '/Display/TOUCH_YP', '/Display/TOUCH_XN', '/Display/TOUCH_YN',
    '/Display/DISP_BL_A', '/Display/DISP_BL_K', 'Net-(U1-USB_D+)', 'Net-(U1-USB_D-)',
}
# these run through the new J1 spot, so whole segments go
OVERLAP_BOX = {'SPI_MISO': RIP_BOX, 'USB_VBUS': (48.0, 10.0, 58.0, 41.0)}
# R169 and the y 10.9 run stay; only the old west link goes
RST_RIP_BOX = (26.0, -1.0, 41.72, 12.0)
# west stub of the y 12.15 run
TOUCH_CS_RIP_BOX = (26.0, -1.0, 56.5, 12.4)
# clear of J15 pin 1: the moved GND via and the two tracks that met it
OLD_GND_VIA = (50.14, 3.22)
NEW_GND_VIA = (49.14, 3.4)
KEEP = []


def inside(item, box):
    x0, y0, x1, y1 = box
    bounds = item.GetBoundingBox()
    return (bounds.GetLeft() / 1e6 >= x0 and bounds.GetRight() / 1e6 <= x1
            and bounds.GetTop() / 1e6 >= y0 and bounds.GetBottom() / 1e6 <= y1)


def overlaps(item, box):
    x0, y0, x1, y1 = box
    bounds = item.GetBoundingBox()
    return not (bounds.GetRight() / 1e6 < x0 or bounds.GetLeft() / 1e6 > x1
                or bounds.GetBottom() / 1e6 < y0 or bounds.GetTop() / 1e6 > y1)


def rigid_items(board, box, nets, back_only):
    """Tracks and vias wholly inside box on the given nets."""
    items = []
    for item in board.GetTracks():
        if item.GetNetname() not in nets or not inside(item, box):
            continue
        if back_only and item.Type() != pcbnew.PCB_VIA_T and item.GetLayer() != pcbnew.B_Cu:
            continue
        items.append(item)
    return items


def move_gnd_via(board):
    """Replaces U27's moved GND via, which would touch J15 pin 1."""
    x, y = OLD_GND_VIA
    near = lambda point: abs(point.x / 1e6 - x) < 0.02 and abs(point.y / 1e6 - y) < 0.02
    gnd = board.FindNet('GND')
    for item in list(board.GetTracks()):
        if item.GetNetname() != 'GND':
            continue
        if item.Type() == pcbnew.PCB_VIA_T:
            if near(item.GetPosition()):
                item.SetPosition(pcbnew.VECTOR2I(MM(NEW_GND_VIA[0]), MM(NEW_GND_VIA[1])))
            continue
        if near(item.GetStart()) and near(item.GetEnd()):
            KEEP.append(item)
            board.Remove(item)
            continue
        if near(item.GetStart()):
            item.SetStart(pcbnew.VECTOR2I(MM(NEW_GND_VIA[0]), MM(NEW_GND_VIA[1])))
        if near(item.GetEnd()):
            item.SetEnd(pcbnew.VECTOR2I(MM(NEW_GND_VIA[0]), MM(NEW_GND_VIA[1])))
    assert gnd is not None


def add_track(board, net_name, points, width, layer):
    for start, end in zip(points, points[1:]):
        seg = pcbnew.PCB_TRACK(board)
        seg.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        seg.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        seg.SetWidth(MM(width))
        seg.SetLayer(layer)
        seg.SetNet(board.FindNet(net_name))
        board.Add(seg)


def add_via(board, net_name, spot):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(MM(spot[0]), MM(spot[1])))
    via.SetDrill(MM(0.2))
    via.SetWidth(pcbnew.F_Cu, MM(0.45))
    via.SetNet(board.FindNet(net_name))
    board.Add(via)


def touches(board_item, point, layer):
    if board_item.Type() == pcbnew.PCB_VIA_T:
        spot = board_item.GetPosition()
        return abs(spot.x - point.x) < 20000 and abs(spot.y - point.y) < 20000
    if board_item.GetLayer() != layer:
        return False
    return any(abs(end.x - point.x) < 20000 and abs(end.y - point.y) < 20000
               for end in (board_item.GetStart(), board_item.GetEnd()))


def distance_along(track, point):
    """Distance of point from track's start when it lies on the track, else None."""
    start, end = track.GetStart(), track.GetEnd()
    run_x, run_y = end.x - start.x, end.y - start.y
    length = (run_x ** 2 + run_y ** 2) ** 0.5
    if length == 0:
        return None
    off_x, off_y = point.x - start.x, point.y - start.y
    if abs(off_x * run_y - off_y * run_x) / length > 20000:
        return None
    along = (off_x * run_x + off_y * run_y) / length
    return along if -20000 <= along <= length + 20000 else None


def trim_tails(board, nets):
    """Removes track ends left dangling by the rip, back to the first real junction."""
    changed = True
    while changed:
        changed = False
        tracks = [t for t in board.GetTracks() if t.GetNetname() in nets]
        pads = [p for p in board.GetPads() if p.GetNetname() in nets]
        for track in tracks:
            if track.Type() == pcbnew.PCB_VIA_T:
                continue
            for free, other in ((track.GetStart(), track.GetEnd()), (track.GetEnd(), track.GetStart())):
                same_net = [t for t in tracks if t is not track and t.GetNetname() == track.GetNetname()]
                if any(touches(t, free, track.GetLayer()) for t in same_net):
                    continue
                if any(p.GetNetname() == track.GetNetname() and p.IsOnLayer(track.GetLayer())
                       and p.HitTest(free) for p in pads):
                    continue
                # a same-net end landing part way along keeps the track up to there
                joints = []
                for item in same_net:
                    points = [item.GetPosition()] if item.Type() == pcbnew.PCB_VIA_T else (
                        [item.GetStart(), item.GetEnd()] if item.GetLayer() == track.GetLayer() else [])
                    for point in points:
                        if distance_along(track, point) is not None:
                            joints.append(point)
                for pad in pads:
                    if (pad.GetNetname() == track.GetNetname() and pad.IsOnLayer(track.GetLayer())
                            and distance_along(track, pad.GetPosition()) is not None):
                        joints.append(pad.GetPosition())
                joints = [j for j in joints if abs(j.x - free.x) > 20000 or abs(j.y - free.y) > 20000]
                if not joints:
                    KEEP.append(track)
                    board.Remove(track)
                else:
                    nearest = min(joints, key=lambda j: (j.x - free.x) ** 2 + (j.y - free.y) ** 2)
                    if abs(nearest.x - other.x) < 20000 and abs(nearest.y - other.y) < 20000:
                        KEEP.append(track)
                        board.Remove(track)
                    elif free == track.GetStart():
                        track.SetStart(nearest)
                    else:
                        track.SetEnd(nearest)
                changed = True
                break
            if changed:
                break


def finish(path):
    """Hand fixes after gridroute: D+ past J1's NPTH peg, J15 pin 5, tails."""
    board = pcbnew.LoadBoard(path)
    for item in list(board.GetTracks()):
        if item.GetNetname() == 'Net-(U1-USB_D+)' and item.Type() != pcbnew.PCB_VIA_T \
                and inside(item, (33.6, 4.9, 36.36, 8.02)) and item.GetLayer() == pcbnew.B_Cu:
            KEEP.append(item)
            board.Remove(item)
    add_track(board, 'Net-(U1-USB_D+)',
              [(33.64, 4.95), (34.65, 5.96), (34.65, 6.9), (35.75, 8.0), (36.35, 8.0)],
              0.2, pcbnew.B_Cu)
    for item in list(board.GetTracks()):
        if item.GetNetname() != 'GND' or item.Type() == pcbnew.PCB_VIA_T:
            continue
        start, end = item.GetStart(), item.GetEnd()
        if {(round(start.x / 1e4), round(start.y / 1e4)), (round(end.x / 1e4), round(end.y / 1e4))} \
                == {(5049, 288), (4914, 340)}:
            KEEP.append(item)
            board.Remove(item)
    add_track(board, 'GND', [(50.49, 2.88), (49.97, 3.4), (49.14, 3.4)], 0.25, pcbnew.B_Cu)
    add_track(board, 'GND', [(52.0, 2.15), (52.0, 3.05), (51.95, 3.1)], 0.2, pcbnew.F_Cu)
    add_via(board, 'GND', (51.95, 3.1))
    # SPI_MOSI now arrives on B.Cu only
    for item in list(board.GetTracks()):
        if item.Type() == pcbnew.PCB_VIA_T and item.GetNetname() == 'SPI_MOSI':
            spot = item.GetPosition()
            if abs(spot.x / 1e6 - 47.05) < 0.1 and abs(spot.y / 1e6 - 18.5) < 0.1:
                KEEP.append(item)
                board.Remove(item)
    trim_tails(board, {'SPI_MOSI', 'SPI_MISO', 'SPI_SCK', 'USB_VBUS', 'Net-(U1-USB_D+)',
                       'Net-(U1-USB_D-)', 'DISP_CS', 'DISP_DC', 'TOUCH_CS', '+3V3'})
    # the new In2 routes split the +3V3 pour: bridge it under J15
    add_track(board, '+3V3', [(49.9, 8.7), (51.0, 7.6), (52.0, 7.6)], 0.3, pcbnew.F_Cu)
    add_via(board, '+3V3', (52.0, 7.6))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


def add_line(board, layer, start, end):
    line = pcbnew.PCB_SHAPE(board)
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    line.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    line.SetWidth(MM(0.15))
    line.SetLayer(layer)
    board.Add(line)


def text_at(board, text, layer, near_x):
    for item in board.GetDrawings():
        if (isinstance(item, pcbnew.PCB_TEXT) and item.GetText() == text and item.GetLayer() == layer
                and abs(item.GetBoundingBox().GetCenter().x / 1e6 - near_x) < 3):
            return item
    raise KeyError(text)


def silk(path):
    """Moves the section wall to x 38 and the names and labels with their parts."""
    board = pcbnew.LoadBoard(path)
    for item in list(board.GetDrawings()):
        if not isinstance(item, pcbnew.PCB_SHAPE) or item.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        start, end = item.GetStart(), item.GetEnd()
        if abs(start.x / 1e6 - 47.5) < 0.05 and abs(end.x / 1e6 - 47.5) < 0.05 and end.y / 1e6 < 12.1 and start.y / 1e6 < 12.1:
            KEEP.append(item)
            board.Remove(item)
    add_line(board, pcbnew.F_SilkS, (38.0, 0.5), (38.0, 11.9))
    add_line(board, pcbnew.B_SilkS, (38.0, 0.5), (38.0, 13.0))
    # the old section name's gaps in the y 13 wall
    add_line(board, pcbnew.F_SilkS, (26.45, 13.0), (32.95, 13.0))
    add_line(board, pcbnew.B_SilkS, (26.45, 13.0), (33.35, 13.0))
    add_line(board, pcbnew.B_SilkS, (33.0, 13.0), (33.0, 14.2))
    # F wall east of SIGNAL GENERATOR: leave room for the section name
    for item in list(board.GetDrawings()):
        if (isinstance(item, pcbnew.PCB_SHAPE) and item.GetLayer() == pcbnew.F_SilkS
                and abs(item.GetStart().y / 1e6 - 13) < 0.05 and abs(item.GetEnd().y / 1e6 - 13) < 0.05
                and item.GetBoundingBox().GetLeft() / 1e6 > 49):
            KEEP.append(item)
            board.Remove(item)
    add_line(board, pcbnew.F_SilkS, (50.55, 13.0), (52.0, 13.0))
    add_line(board, pcbnew.F_SilkS, (58.45, 13.0), (60.0, 13.0))

    def place(item, x, y):
        center = item.GetBoundingBox().GetCenter()
        item.Move(pcbnew.VECTOR2I(MM(x) - center.x, MM(y) - center.y))

    place(text_at(board, 'DISPLAY', pcbnew.F_SilkS, 29.6), 55.2, 13.0)
    place(text_at(board, 'DISPLAY', pcbnew.B_SilkS, 30.2), 42.0, 1.4)
    place(text_at(board, 'DISPLAY', pcbnew.F_SilkS, 42.6), 53.2, 10.2)
    place(text_at(board, 'USB', pcbnew.F_SilkS, 54.3), 32.5, 9.9)
    board.Save(path)


def main():
    path = sys.argv[1]
    if sys.argv[2:] == ['finish']:
        finish(path)
        return
    if sys.argv[2:] == ['silk']:
        silk(path)
        return
    board = pcbnew.LoadBoard(path)

    usb_copper = rigid_items(board, USB_BOX, USB_LOCAL_NETS, back_only=False)
    touch_copper = rigid_items(board, TOUCH_BOX, TOUCH_LOCAL_NETS, back_only=True)
    moved = {id(item) for item in usb_copper + touch_copper}
    moved_uuids = {item.m_Uuid.AsString() for item in usb_copper + touch_copper}
    assert len(moved) == len(moved_uuids)

    for item in usb_copper:
        item.Move(pcbnew.VECTOR2I(MM(USB_SHIFT), 0))
    for item in touch_copper:
        item.Move(pcbnew.VECTOR2I(MM(TOUCH_SHIFT), 0))
    for ref in USB_PARTS:
        board.FindFootprintByReference(ref).Move(pcbnew.VECTOR2I(MM(USB_SHIFT), 0))
    for ref in TOUCH_PARTS:
        board.FindFootprintByReference(ref).Move(pcbnew.VECTOR2I(MM(TOUCH_SHIFT), 0))
    j15 = board.FindFootprintByReference('J15')
    j15.SetPosition(pcbnew.VECTOR2I(MM(J15_SPOT[0]), MM(J15_SPOT[1])))
    j15.SetOrientationDegrees(J15_SPOT[2])

    ripped = set()
    for item in list(board.GetTracks()):
        if item.m_Uuid.AsString() in moved_uuids:
            continue
        name = item.GetNetname()
        if name == 'DISP_RST':
            doomed = overlaps(item, RST_RIP_BOX)
        elif name == 'TOUCH_CS':
            doomed = overlaps(item, TOUCH_CS_RIP_BOX)
        elif name in PLANE_NETS:
            doomed = inside(item, PLANE_BOX)
        elif name in OVERLAP_BOX and overlaps(item, OVERLAP_BOX[name]):
            doomed = True
        else:
            doomed = name in RIP_NETS and inside(item, RIP_BOX)
        if doomed:
            ripped.add(name)
            KEEP.append(item)
            board.Remove(item)
    print('ripped:', sorted(ripped))

    move_gnd_via(board)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
