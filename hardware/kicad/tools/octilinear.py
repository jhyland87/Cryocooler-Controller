"""Replaces off-angle track segments with 0 / 45 / 90 degree doglegs.

Each segment keeps its two end points and gains one or two corners. A shape is
used only if it clears other nets' copper, keep-outs and small pours. Segments
are split first where a branch or via joins them. A segment no dogleg fits is
rerouted on the grid, on its own layer. Run the DRC afterwards: pad checks use
bounding boxes, so this errs towards leaving a segment alone.

Usage: octilinear.py board.kicad_pcb (edits in place, refills zones)
"""
import collections
import math
import sys

import pcbnew

import gridroute

MM = 1_000_000
CLEARANCE = int(0.16 * MM)
EDGE_CLEARANCE = int(0.31 * MM)
ANGLE_TOLERANCE = 0.1
MIN_CORNER = 5000
BUCKET = 2 * MM
# pours that follow tracks, so a moved track only reshapes them
PLANE_NETS = ('GND', '+3V3', 'ISO_GND')
PASSES = 3


def angle_error(start, end):
    """Degrees between a segment and its nearest multiple of 45."""
    angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 45
    return min(angle, 45 - angle)


def point_segment_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.dist(point, start)
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2
    t = max(0.0, min(1.0, t))
    return math.dist(point, (start[0] + t * dx, start[1] + t * dy))


def segments_cross(a, b, c, d):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def segment_distance(a, b, c, d):
    if segments_cross(a, b, c, d):
        return 0.0
    return min(point_segment_distance(a, c, d), point_segment_distance(b, c, d),
               point_segment_distance(c, a, b), point_segment_distance(d, a, b))


def rect_distance(start, end, rect):
    """Distance from a segment to an axis-aligned (x0, y0, x1, y1) box."""
    x0, y0, x1, y1 = rect
    if x0 <= start[0] <= x1 and y0 <= start[1] <= y1:
        return 0.0
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return min(segment_distance(start, end, corners[i], corners[(i + 1) % 4]) for i in range(4))


class Obstacles:
    """Copper of every net, bucketed by location, per layer."""

    def __init__(self, board):
        self.segments = collections.defaultdict(set)
        self.boxes = collections.defaultdict(list)
        self.items = {}
        self.next_id = 0
        for track in board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                continue
            self.add_segment(track.GetNetCode(), track.GetLayer(), xy(track.GetStart()),
                             xy(track.GetEnd()), track.GetWidth(), track)
        self.vias = []
        for track in board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                self.vias.append((track.GetNetCode(), xy(track.GetPosition()),
                                  track.GetWidth(pcbnew.F_Cu)))
        self.pads = []
        for pad in board.GetPads():
            box = pad.GetBoundingBox()
            self.pads.append((pad.GetNetCode(), pad,
                              (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())))

    def cells(self, start, end, margin):
        x0, x1 = sorted((start[0], end[0]))
        y0, y1 = sorted((start[1], end[1]))
        for cx in range((x0 - margin) // BUCKET, (x1 + margin) // BUCKET + 1):
            for cy in range((y0 - margin) // BUCKET, (y1 + margin) // BUCKET + 1):
                yield cx, cy

    def add_segment(self, net, layer, start, end, width, track):
        item_id = self.next_id
        self.next_id += 1
        self.items[item_id] = (net, layer, start, end, width, track)
        for cell in self.cells(start, end, width):
            self.segments[(layer, cell)].add(item_id)
        return item_id

    def remove_track(self, track):
        for item_id, item in list(self.items.items()):
            if item[5] is track:
                for cell in self.cells(item[2], item[3], item[4]):
                    self.segments[(item[1], cell)].discard(item_id)
                del self.items[item_id]

    def near(self, layer, start, end, margin):
        seen = set()
        for cell in self.cells(start, end, margin):
            for item_id in self.segments.get((layer, cell), ()):
                if item_id not in seen:
                    seen.add(item_id)
                    yield self.items[item_id]


def xy(point):
    return (point.x, point.y)


class Rules:
    def __init__(self, board):
        self.board = board
        self.obstacles = Obstacles(board)
        box = board.GetBoardEdgesBoundingBox()
        self.edge = (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())
        self.zones = []
        for zone in board.Zones():
            if zone.GetIsRuleArea():
                if zone.GetDoNotAllowTracks():
                    self.zones.append((None, zone))
            elif zone.GetNetname() not in PLANE_NETS:
                self.zones.append((zone.GetNetCode(), zone))

    def has_branch(self, net, layer, start, end, width):
        """True if something of the same net joins the segment away from its ends."""
        reach = width // 2 + 2000

        def interior(point):
            return (math.dist(point, start) > reach and math.dist(point, end) > reach
                    and point_segment_distance(point, start, end) < reach)

        for item in self.obstacles.near(layer, start, end, reach):
            if item[0] == net and (interior(item[2]) or interior(item[3])):
                return True
        for via_net, where, _ in self.obstacles.vias:
            if via_net == net and interior(where):
                return True
        for pad_net, pad, rect in self.obstacles.pads:
            if pad_net != net or not pad.IsOnLayer(layer):
                continue
            if rect_distance(start, end, rect) > width // 2:
                continue
            at_end = (rect[0] <= start[0] <= rect[2] and rect[1] <= start[1] <= rect[3]) or (
                rect[0] <= end[0] <= rect[2] and rect[1] <= end[1] <= rect[3])
            if not at_end:
                return True
        return False

    def clear(self, net, layer, start, end, width):
        half = width // 2
        x0, y0, x1, y1 = self.edge
        margin = half + EDGE_CLEARANCE
        for point in (start, end):
            if not (x0 + margin <= point[0] <= x1 - margin
                    and y0 + margin <= point[1] <= y1 - margin):
                return False
        reach = half + CLEARANCE
        for other in self.obstacles.near(layer, start, end, reach + 1000000):
            if other[0] != net and segment_distance(start, end, other[2], other[3]) < (
                    reach + other[4] // 2):
                return False
        for via_net, where, diameter in self.obstacles.vias:
            if via_net != net and point_segment_distance(where, start, end) < (
                    reach + diameter // 2):
                return False
        for pad_net, pad, rect in self.obstacles.pads:
            if pad_net == net or not (pad.IsOnLayer(layer) or pad.GetDrillSizeX()):
                continue
            if rect_distance(start, end, rect) < reach:
                return False
        steps = max(1, int(math.dist(start, end) / (0.2 * MM)))
        for zone_net, zone in self.zones:
            if zone_net == net or not zone.IsOnLayer(layer):
                continue
            for step in range(steps + 1):
                where = pcbnew.VECTOR2I(start[0] + (end[0] - start[0]) * step // steps,
                                        start[1] + (end[1] - start[1]) * step // steps)
                if zone.Outline().Collide(where, reach):
                    return False
        return True


def shapes(start, end):
    """Candidate corner lists from start to end, one corner shapes first."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    diagonal = min(abs(dx), abs(dy))
    step = (sx * diagonal, sy * diagonal)
    straight = (dx - step[0], dy - step[1])
    half_straight = (straight[0] // 2, straight[1] // 2)
    half_diagonal = (step[0] // 2, step[1] // 2)
    yield [(start[0] + step[0], start[1] + step[1])]
    yield [(start[0] + straight[0], start[1] + straight[1])]
    first = (start[0] + half_straight[0], start[1] + half_straight[1])
    yield [first, (first[0] + step[0], first[1] + step[1])]
    first = (start[0] + half_diagonal[0], start[1] + half_diagonal[1])
    yield [first, (first[0] + straight[0], first[1] + straight[1])]


def straighten(board, rules, track):
    """Replaces one track with a dogleg. Returns 'done', 'branch' or 'blocked'."""
    net, layer, width = track.GetNetCode(), track.GetLayer(), track.GetWidth()
    start, end = xy(track.GetStart()), xy(track.GetEnd())
    if rules.has_branch(net, layer, start, end, width):
        return 'branch'
    if min(abs(end[0] - start[0]), abs(end[1] - start[1])) < MIN_CORNER:
        return 'tiny'
    obstacles = rules.obstacles
    for corners in shapes(start, end):
        points = [start, *corners, end]
        legs = [(a, b) for a, b in zip(points, points[1:]) if a != b]
        if not all(rules.clear(net, layer, a, b, width) for a, b in legs):
            continue
        obstacles.remove_track(track)
        for a, b in legs:
            leg = pcbnew.PCB_TRACK(board)
            leg.SetStart(pcbnew.VECTOR2I(*a))
            leg.SetEnd(pcbnew.VECTOR2I(*b))
            leg.SetWidth(width)
            leg.SetLayer(layer)
            leg.SetNetCode(net)
            board.Add(leg)
            obstacles.add_segment(net, layer, a, b, width, leg)
        return 'done'
    return 'blocked'


def split_at_branches(board):
    """Splits off-angle segments at the same-net track ends and vias on their length."""
    by_net = collections.defaultdict(list)
    tracks = [track for track in board.GetTracks()]
    for track in tracks:
        if track.Type() == pcbnew.PCB_VIA_T:
            by_net[track.GetNetCode()].append((xy(track.GetPosition()), None))
        else:
            by_net[track.GetNetCode()].append((xy(track.GetStart()), track.GetLayer()))
            by_net[track.GetNetCode()].append((xy(track.GetEnd()), track.GetLayer()))
    removed = []
    for track in tracks:
        if track.Type() == pcbnew.PCB_VIA_T:
            continue
        start, end = xy(track.GetStart()), xy(track.GetEnd())
        if start == end or angle_error(start, end) <= ANGLE_TOLERANCE:
            continue
        reach = track.GetWidth() // 2 + 2000
        joints = {point for point, layer in by_net[track.GetNetCode()]
                  if layer in (None, track.GetLayer())
                  and math.dist(point, start) > reach and math.dist(point, end) > reach
                  and point_segment_distance(point, start, end) < reach}
        if not joints:
            continue
        ordered = sorted(joints, key=lambda point: math.dist(point, start))
        points = [start, *ordered, end]
        for first, second in zip(points, points[1:]):
            add_leg(board, track, first, second)
        removed.append(track)
        board.Remove(track)
    return removed


def add_leg(board, like, start, end):
    leg = pcbnew.PCB_TRACK(board)
    leg.SetStart(pcbnew.VECTOR2I(*start))
    leg.SetEnd(pcbnew.VECTOR2I(*end))
    leg.SetWidth(like.GetWidth())
    leg.SetLayer(like.GetLayer())
    leg.SetNetCode(like.GetNetCode())
    board.Add(leg)
    return leg


def reroute_blocked(board, removed):
    """Reroutes remaining off-angle segments on the grid, same layer, no new vias."""
    counts = collections.Counter()
    for track in list(board.GetTracks()):
        if track.Type() == pcbnew.PCB_VIA_T or 'Usb' in track.GetNetClassName():
            continue
        start, end = xy(track.GetStart()), xy(track.GetEnd())
        if start == end or angle_error(start, end) <= ANGLE_TOLERANCE:
            continue
        if math.dist(start, end) < 0.3 * MM:
            counts['short'] += 1
            continue
        margin = 2.0
        region = (min(start[0], end[0]) / MM - margin, min(start[1], end[1]) / MM - margin,
                  max(start[0], end[0]) / MM + margin, max(start[1], end[1]) / MM + margin)
        layer = track.GetLayer()
        grid = gridroute.Grid(board, track.GetNetCode(), track.GetWidth() / MM, region)
        first = gridroute.cell_of(start[0] / MM, start[1] / MM)
        last = gridroute.cell_of(end[0] / MM, end[1] / MM)
        from_cell = first[1] * gridroute.NX + first[0]
        to_cell = last[1] * gridroute.NX + last[0]
        grid.blocked[layer][from_cell] = 0
        grid.via_blocked = bytearray(b'\x01') * gridroute.N
        path = gridroute.astar(grid, [(layer, from_cell)], [(layer, to_cell)])
        if not path:
            counts['no path'] += 1
            continue
        corners = gridroute.smooth(grid, path)[0][1]
        points = [(index % gridroute.NX * int(gridroute.CELL * MM),
                   index // gridroute.NX * int(gridroute.CELL * MM)) for index in corners]
        points[0], points[-1] = start, end
        for one, two in zip(points, points[1:]):
            if one != two:
                add_leg(board, track, one, two)
        removed.append(track)
        board.Remove(track)
        counts['rerouted'] += 1
    print('reroute:', dict(counts), flush=True)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    removed = split_at_branches(board)
    rules = Rules(board)
    for number in range(PASSES):
        counts = collections.Counter()
        for track in list(board.GetTracks()):
            if track.Type() == pcbnew.PCB_VIA_T:
                continue
            start, end = xy(track.GetStart()), xy(track.GetEnd())
            if start == end or angle_error(start, end) <= ANGLE_TOLERANCE:
                continue
            result = straighten(board, rules, track)
            counts[result] += 1
            if result == 'done':
                removed.append(track)
                board.Remove(track)
        print(f'pass {number + 1}:', dict(counts), flush=True)
        if not counts['done']:
            break
    reroute_blocked(board, removed)
    rules = Rules(board)
    for track in list(board.GetTracks()):
        if track.Type() == pcbnew.PCB_VIA_T:
            continue
        start, end = xy(track.GetStart()), xy(track.GetEnd())
        if start != end and angle_error(start, end) > ANGLE_TOLERANCE and straighten(
                board, rules, track) == 'done':
            removed.append(track)
            board.Remove(track)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
