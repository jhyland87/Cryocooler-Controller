"""Tidies the board after `cs_decoder_board.py`, `gridroute.py` and `octilinear.py`:
trims the CS traces' dead ends, ties the GND pads the routes cut off from the pour
to a via, moves the MCU / INDICATORS section line so the decoder sits in the MCU box,
and prints the part name on U32. Safe to re-run. Run before `narrow_silk.py`,
`label_owners.py`, `silk_fix.py`.

Usage: cs_decoder_finish.py board.kicad_pcb [--ground] (edits in place; --ground once)
"""
import math
import sys

import pcbnew

MM = pcbnew.FromMM
SECTION_LINE = ((70.75, 30.0), (100.0, 30.0))
SECTION_JOG_X = 86.7
SECTION_JOG_BOTTOM = 40.0
TEXT_HEIGHT, TEXT_WIDTH, TEXT_STROKE = 1.0, 0.9, 0.15
KEEP = []  # SWIG frees removed items when their wrappers die
TRIM_NETS = {
    'AD9833_FSYNC', 'MCP4921_CS', 'INA239_CS', 'EXPANDER_CS', 'DISP_CS', 'TOUCH_CS',
    'ADS1220_CS', 'IMU_CS', 'CS_ADDR_A', 'CS_ADDR_B', 'CS_ADDR_C', 'CS_EN_N',
}
R68_RAIL_STUB = (20.0, 50.0, 23.0, 53.2)
BIAS_RAIL = ((98.11, 33.2), (99.2, 33.2), (99.6, 33.6), (99.6, 35.2), (99.2, 35.6), (98.11, 35.6))
BIAS_RAIL_WIDTH = 0.3
GROUND_PADS = (('R183', '1'),)
REMOVED_PARTS = ('TP41',)  # user: silk room beside U24
# G2B is boxed in by CS_ADDR_B under the body: capped via in its pad, as on the
# other fine-pitch ground pads (fabrication/README.md)
# D10's cathode too: inner traces 0.9 mm apart leave no room beside it
VIAS_IN_PADS = (('D10', '1', 85.0, 32.26),)
# C132 leaves the decoder's fan-out: ground pad in open pour, supply pad beside TP45
C132_SPOT = (87.8, 37.6, 180)
C132_FEED_WIDTH = 0.3
VIA_DIAMETER, VIA_DRILL, STUB_WIDTH, CLEARANCE = 0.45, 0.2, 0.2, 0.16
SEARCH_STEPS = 30  # via search radius, in 0.1 mm steps


def on_item(point, item):
    """True when a point lies on a track's centre line, a via or within half a width."""
    if item.Type() == pcbnew.PCB_VIA_T:
        where = item.GetPosition()
        return math.hypot(where.x - point.x, where.y - point.y) <= item.GetWidth(pcbnew.F_Cu) / 2
    return segment_gap(point, item.GetStart(), item.GetEnd()) <= item.GetWidth() / 2


def on_pad(point, pad, layer):
    return pad.IsOnLayer(layer) and pad.GetBoundingBox().Contains(point)


def dead_item(board):
    """Next CS via on fewer than two layers, or track end touching nothing."""
    tracks = [t for t in board.GetTracks() if t.GetNetname() in TRIM_NETS]
    pads = [p for p in board.GetPads() if p.GetNetname() in TRIM_NETS]
    for item in tracks:
        net = item.GetNetname()
        others = [o for o in tracks if o.GetNetname() == net and o.m_Uuid.AsString() != item.m_Uuid.AsString()]
        own_pads = [p for p in pads if p.GetNetname() == net]
        if item.Type() == pcbnew.PCB_VIA_T:
            where = item.GetPosition()
            layers = {o.GetLayer() for o in others
                      if o.Type() != pcbnew.PCB_VIA_T and on_item(where, o)}
            if len(layers) < 2 and not any(p.GetBoundingBox().Contains(where) for p in own_pads):
                return item, None, others, own_pads
            continue
        for end_name, point in (('start', item.GetStart()), ('end', item.GetEnd())):
            joined = any(on_pad(point, p, item.GetLayer()) for p in own_pads) or any(
                on_item(point, o) for o in others
                if o.Type() == pcbnew.PCB_VIA_T or o.GetLayer() == item.GetLayer())
            if not joined:
                return item, end_name, others, own_pads
    return None


def trim_dead_ends(board):
    """Cuts CS track ends that reach nothing back to the nearest branch, because the
    router joined some old traces partway along. Vias on one layer only go too.
    """
    while True:
        found = dead_item(board)
        if found is None:
            return
        item, end_name, others, own_pads = found
        if end_name is None:
            print('removed via', item.GetNetname(), item.GetPosition().x / 1e6,
                  item.GetPosition().y / 1e6)
            KEEP.append(item)
            board.Remove(item)
            continue
        dead, keep = ((item.GetStart(), item.GetEnd()) if end_name == 'start'
                      else (item.GetEnd(), item.GetStart()))
        branches = []
        for other in others:
            if other.Type() == pcbnew.PCB_VIA_T:
                branches.append(other.GetPosition())
            elif other.GetLayer() == item.GetLayer():
                branches += [other.GetStart(), other.GetEnd()]
        branches = [q for q in branches
                    if segment_gap(q, dead, keep) < 1000
                    and math.hypot(q.x - keep.x, q.y - keep.y) > 4000]
        print('trimmed', item.GetNetname(), dead.x / 1e6, dead.y / 1e6)
        if not branches:
            KEEP.append(item)
            board.Remove(item)
            continue
        nearest = min(branches, key=lambda q: math.hypot(q.x - dead.x, q.y - dead.y))
        (item.SetStart if end_name == 'start' else item.SetEnd)(nearest)


def remove_r68_rail_stub(board):
    """The removed INA239 CS pull-up left a +3V3 stub: remove it up to its junction."""
    x0, y0, x1, y1 = R68_RAIL_STUB
    while True:
        tracks = [t for t in board.GetTracks() if t.GetNetname() == '+3V3']
        pads = [p for p in board.GetPads() if p.GetNetname() == '+3V3']
        for item in tracks:
            if item.Type() == pcbnew.PCB_VIA_T or not all(
                    x0 <= p.x / 1e6 <= x1 and y0 <= p.y / 1e6 <= y1
                    for p in (item.GetStart(), item.GetEnd())):
                continue
            own_id = item.m_Uuid.AsString()
            others = [o for o in tracks if o.m_Uuid.AsString() != own_id]
            dead = [p for p in (item.GetStart(), item.GetEnd())
                    if not any(on_item(p, o) for o in others)
                    and not any(on_pad(p, pad, item.GetLayer()) for pad in pads)]
            if dead:
                KEEP.append(item)
                board.Remove(item)
                break
        else:
            return


def segment_gap(point, start, end):
    """Distance in nm from a point to a segment."""
    dx, dy = end.x - start.x, end.y - start.y
    length = dx * dx + dy * dy
    ratio = 0.0 if not length else max(
        0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length))
    return math.hypot(point.x - start.x - ratio * dx, point.y - start.y - ratio * dy)


def nearby_copper(board, center, net, reach):
    """Other nets' copper near a point, as plain tuples, because walking the board
    through the bindings for every probe is far too slow.
    """
    vias, tracks, pads = [], [], []
    for item in board.GetTracks():
        if item.GetNetname() == net:
            continue
        if item.Type() == pcbnew.PCB_VIA_T:
            where = item.GetPosition()
            if math.hypot(where.x - center.x, where.y - center.y) < reach:
                vias.append((where, item.GetWidth(pcbnew.F_Cu) / 2))
        elif segment_gap(center, item.GetStart(), item.GetEnd()) < reach:
            tracks.append((item.GetLayer(), item.GetStart(), item.GetEnd(), item.GetWidth() / 2))
    for pad in board.GetPads():
        if pad.GetNetname() == net:
            continue
        where = pad.GetPosition()
        if math.hypot(where.x - center.x, where.y - center.y) < reach + MM(3):
            box = pad.GetBoundingBox()
            layers = {layer for layer in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(layer)}
            pads.append(((box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom()), layers,
                         pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH))
    return vias, tracks, pads


def in_box(point, box, margin):
    return (box[0] - margin <= point.x <= box[2] + margin
            and box[1] - margin <= point.y <= box[3] + margin)


def path_clear(copper, points, layer):
    """True when a track through `points` clears the copper on its layer."""
    vias, tracks, pads = copper
    margin = MM(STUB_WIDTH / 2 + CLEARANCE)
    for start, end in zip(points, points[1:]):
        steps = max(1, int(math.hypot(end.x - start.x, end.y - start.y) / MM(0.05)))
        for step in range(steps + 1):
            probe = pcbnew.VECTOR2I(start.x + (end.x - start.x) * step // steps,
                                    start.y + (end.y - start.y) * step // steps)
            if any(math.hypot(where.x - probe.x, where.y - probe.y) < margin + half
                   for where, half in vias):
                return False
            if any(track_layer == layer and segment_gap(probe, a, b) < margin + half
                   for track_layer, a, b, half in tracks):
                return False
            if any(layer in layers and in_box(probe, box, margin) for box, layers, _ in pads):
                return False
    return True


def via_clear(copper, position):
    """True when a through via here clears the copper on every layer."""
    vias, tracks, pads = copper
    radius = MM(VIA_DIAMETER / 2 + CLEARANCE)
    if any(math.hypot(where.x - position.x, where.y - position.y) < radius + half
           for where, half in vias):
        return False
    if any(segment_gap(position, a, b) < radius + half for _, a, b, half in tracks):
        return False
    return not any(in_box(position, box, radius) for box, _, _ in pads)


def doglegs(start, end):
    """The two 0/45/90 shapes between two points (one if they are already in line)."""
    dx, dy = end.x - start.x, end.y - start.y
    run = min(abs(dx), abs(dy))
    diagonal = (int(math.copysign(run, dx)), int(math.copysign(run, dy)))
    first = pcbnew.VECTOR2I(start.x + diagonal[0], start.y + diagonal[1])
    second = pcbnew.VECTOR2I(end.x - diagonal[0], end.y - diagonal[1])
    return ([start, first, end], [start, second, end])


def add_track(board, points, net, layer):
    for start, end in zip(points, points[1:]):
        if start.x == end.x and start.y == end.y:
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(start)
        track.SetEnd(end)
        track.SetWidth(MM(STUB_WIDTH))
        track.SetLayer(layer)
        track.SetNet(net)
        board.Add(track)


def move_c132(board):
    x, y, rotation = C132_SPOT
    footprint = board.FindFootprintByReference('C132')
    footprint.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    footprint.SetOrientationDegrees(rotation)
    supply = next(p for p in footprint.Pads() if p.GetNumber() == '1')
    test_point = board.FindFootprintByReference('TP45')
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(supply.GetPosition())
    track.SetEnd(test_point.GetPosition())
    track.SetWidth(MM(C132_FEED_WIDTH))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(supply.GetNet())
    board.Add(track)


def move_bias_rail(board):
    """Moves the +3V3 loop feeding R182 and R181 clear of R183, so its ground pad
    has room for a via.
    """
    feed = next(p for p in board.FindFootprintByReference('R182').Pads() if p.GetNumber() == '1')
    for item in list(board.GetTracks()):
        if item.Type() == pcbnew.PCB_VIA_T or item.GetNetname() != '+3V3':
            continue
        ends = (item.GetStart(), item.GetEnd())
        if all(MM(98.0) <= end.x <= MM(99.0) and MM(33.1) <= end.y <= MM(35.7) for end in ends):
            KEEP.append(item)
            board.Remove(item)
    points = [pcbnew.VECTOR2I(MM(x), MM(y)) for x, y in BIAS_RAIL]
    for start, end in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(start)
        track.SetEnd(end)
        track.SetWidth(MM(BIAS_RAIL_WIDTH))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(feed.GetNet())
        board.Add(track)


def tie_pad_to_ground(board, ref, number):
    """Joins a pad the routes cut off from the pour to the nearest GND via it can
    reach at 0/45/90, or to a new via beside it.
    """
    footprint = board.FindFootprintByReference(ref)
    pad = next(p for p in footprint.Pads() if p.GetNumber() == number)
    start = pad.GetPosition()
    layer = pcbnew.B_Cu if footprint.IsFlipped() else pcbnew.F_Cu
    name = pad.GetNetname()
    copper = nearby_copper(board, start, name, MM(5))
    box = pad.GetBoundingBox()
    own_box = (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())
    nearby = [v.GetPosition() for v in board.GetTracks()
              if v.Type() == pcbnew.PCB_VIA_T and v.GetNetname() == name
              and math.hypot(v.GetPosition().x - start.x, v.GetPosition().y - start.y) < MM(3.5)]
    for target in sorted(nearby, key=lambda q: math.hypot(q.x - start.x, q.y - start.y)):
        for points in doglegs(start, target):
            if path_clear(copper, points, layer):
                add_track(board, points, pad.GetNet(), layer)
                print('tied to via', ref, number, target.x / 1e6, target.y / 1e6)
                return
    grid = range(-SEARCH_STEPS, SEARCH_STEPS + 1)
    spots = sorted(((column, row) for column in grid for row in grid if column or row),
                   key=lambda spot: math.hypot(*spot))
    for column, row in spots:
        position = pcbnew.VECTOR2I(start.x + MM(column * 0.1), start.y + MM(row * 0.1))
        if not via_clear(copper, position):
            continue
        if in_box(position, own_box, MM(VIA_DIAMETER / 2 + 0.1)):  # beside the pad, not in it
            continue
        for points in doglegs(start, position):
            if path_clear(copper, points, layer):
                add_track(board, points, pad.GetNet(), layer)
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(position)
                via.SetWidth(MM(VIA_DIAMETER))
                via.SetDrill(MM(VIA_DRILL))
                via.SetNet(pad.GetNet())
                board.Add(via)
                print('new ground via', ref, number, position.x / 1e6, position.y / 1e6)
                return
    raise RuntimeError(f'no ground connection for {ref} pad {number}')


def add_vias_in_pads(board):
    for ref, number, x, y in VIAS_IN_PADS:
        pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == number)
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        via.SetWidth(MM(VIA_DIAMETER))
        via.SetDrill(MM(VIA_DRILL))
        via.SetNet(pad.GetNet())
        board.Add(via)


def remove_parts(board):
    for ref in REMOVED_PARTS:
        footprint = board.FindFootprintByReference(ref)
        if footprint:
            KEEP.append(footprint)
            board.Remove(footprint)


def add_line(board, template, start, end):
    line = pcbnew.PCB_SHAPE(board)
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    line.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    line.SetLayer(pcbnew.F_SilkS)
    line.SetWidth(template.GetWidth())
    board.Add(line)


def move_section_line(board):
    (x0, y0), (x1, _) = SECTION_LINE
    for drawing in board.GetDrawings():
        if drawing.GetClass() != 'PCB_SHAPE' or drawing.GetLayer() != pcbnew.F_SilkS:
            continue
        start, end = drawing.GetStart(), drawing.GetEnd()
        same = (abs(start.x / 1e6 - x0) < 0.01 and abs(start.y / 1e6 - y0) < 0.01
                and abs(end.x / 1e6 - x1) < 0.01)
        if not same:
            continue
        drawing.SetEnd(pcbnew.VECTOR2I(MM(SECTION_JOG_X), end.y))
        add_line(board, drawing, (SECTION_JOG_X, y0), (SECTION_JOG_X, SECTION_JOG_BOTTOM))
        return
    # already moved on an earlier run


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    remove_parts(board)
    trim_dead_ends(board)
    remove_r68_rail_stub(board)
    if '--ground' in sys.argv:
        move_c132(board)
        add_vias_in_pads(board)
        move_bias_rail(board)
        for ref, number in GROUND_PADS:
            tie_pad_to_ground(board, ref, number)
    move_section_line(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
