"""Grid A* router for the connections Freerouting left open.

Usage: gridroute.py board.kicad_pcb drc.json [out.kicad_pcb [NET,...]]
Routes each unconnected pair from a kicad-cli DRC report on F.Cu / In2.Cu /
B.Cu (In1 is the GND plane), with 0.45/0.2 through vias, then saves.
Env knobs: FIRST=U20,U21 (pairs on those parts first), FINE=1 (0.1 mm
clearance), IN1=1 / IN1_COST, VIA_COST, HWEIGHT, MAX_EXPAND.
"""
import heapq
import os
import json
import math
import re
import sys

import pcbnew

CELL = 0.05
W_MM, H_MM = 120.0, 100.0
NX, NY = int(W_MM / CELL) + 1, int(H_MM / CELL) + 1
N = NX * NY
FINE = os.environ.get('FINE') == '1'
CLEAR = 0.1 if FINE else 0.15
EDGE = 0.35
VIA_D, VIA_DRILL = 0.45, 0.2
HOLE_GAP = 0.25
VIA_COST = float(os.environ.get('VIA_COST', '30'))
VIA_IN_PAD_COST = 120.0
SOFT_COST = float(os.environ.get('SOFT_COST', '6'))
HWEIGHT = float(os.environ.get('HWEIGHT', '1.0'))
MAX_EXPAND = int(os.environ.get('MAX_EXPAND', '3000000'))
VIA_CLEAR = 0.1  # kicad_dru via_in_pad_clearance: 0.2 mm hole vias
NOTCH = (60.0, 0.0, 80.0, 6.6)
SKIP_NETS = set(os.environ.get('SKIP', 'GND').split(','))  # nets the pours connect
ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
if os.environ.get('IN1') == '1':
    ROUTE_LAYERS.append(pcbnew.In1_Cu)
LAYER_COST = {pcbnew.In1_Cu: float(os.environ.get('IN1_COST', '8'))}
ALL_LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
WIDTHS = {'Power': 0.3, 'Power12V': 0.8, 'Earth': 1.5, 'Usb': 0.2}
SIGNAL_WIDTH = 0.15 if FINE else 0.2


def nm(value):
    return int(round(value * 1e6))


def mm(value):
    return value / 1e6


def cell_of(x, y):
    return int(round(x / CELL)), int(round(y / CELL))


def layer_by_name(board, name):
    return board.GetLayerID(name)


class Grid:
    """Blocked cells for one net: one bytearray per copper layer plus vias."""

    def __init__(self, board, net, width, region, soft_nets=()):
        self.board, self.net, self.width = board, net, width
        self.x0, self.y0, self.x1, self.y1 = region
        self.blocked = {layer: bytearray(N) for layer in ALL_LAYERS}
        self.via_blocked = bytearray(N)
        self.pad_via = bytearray(N)
        # tracks of soft_nets are passable at a cost (rip-up candidates)
        self.soft_nets = set(soft_nets)
        self.soft = {layer: bytearray(N) for layer in ALL_LAYERS} if soft_nets else None
        self.soft_via = bytearray(N) if soft_nets else None
        self.build()

    def cells(self, minx, miny, maxx, maxy):
        cx0 = max(int(math.floor(max(minx, self.x0) / CELL)), 0)
        cy0 = max(int(math.floor(max(miny, self.y0) / CELL)), 0)
        cx1 = min(int(math.ceil(min(maxx, self.x1) / CELL)), NX - 1)
        cy1 = min(int(math.ceil(min(maxy, self.y1) / CELL)), NY - 1)
        return cx0, cy0, cx1, cy1

    def mark_capsule(self, grid, ax, ay, bx, by, radius):
        box = self.cells(min(ax, bx) - radius, min(ay, by) - radius,
                         max(ax, bx) + radius, max(ay, by) + radius)
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        r2 = radius * radius
        for cy in range(box[1], box[3] + 1):
            py = cy * CELL
            row = cy * NX
            for cx in range(box[0], box[2] + 1):
                px = cx * CELL
                if length2 == 0:
                    t = 0.0
                else:
                    t = ((px - ax) * dx + (py - ay) * dy) / length2
                    t = 0.0 if t < 0 else 1.0 if t > 1 else t
                ex, ey = ax + t * dx - px, ay + t * dy - py
                if ex * ex + ey * ey < r2:
                    grid[row + cx] = 1

    def mark_poly(self, grid, item, layer, inflate):
        shape = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(shape, layer, nm(inflate), nm(0.005),
                                     pcbnew.ERROR_OUTSIDE)
        if shape.OutlineCount() == 0:
            return
        bbox = shape.BBox()
        box = self.cells(mm(bbox.GetLeft()), mm(bbox.GetTop()),
                         mm(bbox.GetRight()), mm(bbox.GetBottom()))
        for cy in range(box[1], box[3] + 1):
            row = cy * NX
            for cx in range(box[0], box[2] + 1):
                if not grid[row + cx] and shape.Contains(
                        pcbnew.VECTOR2I(nm(cx * CELL), nm(cy * CELL))):
                    grid[row + cx] = 1

    def targets(self, track):
        """The (per-layer, via) grids a foreign track or via is marked in."""
        if track.GetNetCode() in self.soft_nets:
            return self.soft, self.soft_via
        return self.blocked, self.via_blocked

    def near(self, minx, miny, maxx, maxy, margin):
        return not (maxx + margin < self.x0 or minx - margin > self.x1
                    or maxy + margin < self.y0 or miny - margin > self.y1)

    def build(self):
        board, half = self.board, self.width / 2
        via_r = VIA_D / 2
        track_infl = CLEAR + half
        via_infl = VIA_CLEAR + via_r
        for track in board.GetTracks():
            a, b = track.GetStart(), track.GetEnd()
            ax, ay, bx, by = mm(a.x), mm(a.y), mm(b.x), mm(b.y)
            if not self.near(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), 2):
                continue
            if track.GetClass() == 'PCB_VIA':
                radius = mm(track.GetWidth(pcbnew.F_Cu)) / 2
                drill = mm(track.GetDrillValue()) / 2
                self.mark_capsule(self.via_blocked, ax, ay, ax, ay,
                                  drill + VIA_DRILL / 2 + HOLE_GAP)
                if track.GetNetCode() == self.net:
                    continue
                layers, vias = self.targets(track)
                for layer in ALL_LAYERS:
                    self.mark_capsule(layers[layer], ax, ay, ax, ay, radius + track_infl)
                self.mark_capsule(vias, ax, ay, ax, ay, radius + via_infl)
                continue
            if track.GetNetCode() == self.net:
                continue
            layer = track.GetLayer()
            if layer not in self.blocked:
                continue
            layers, vias = self.targets(track)
            radius = mm(track.GetWidth()) / 2
            if track.GetClass() == 'PCB_ARC':
                self.mark_poly(layers[layer], track, layer, track_infl)
                self.mark_poly(vias, track, layer, via_infl)
                continue
            self.mark_capsule(layers[layer], ax, ay, bx, by, radius + track_infl)
            self.mark_capsule(vias, ax, ay, bx, by, radius + via_infl)
        for pad in board.GetPads():
            bbox = pad.GetBoundingBox()
            if not self.near(mm(bbox.GetLeft()), mm(bbox.GetTop()),
                             mm(bbox.GetRight()), mm(bbox.GetBottom()), 2):
                continue
            own = pad.GetNetCode() == self.net and pad.GetNetCode() > 0
            drill = pad.GetDrillSize()
            if drill.x > 0:
                pos = pad.GetPosition()
                gap = HOLE_GAP + (0.25 if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else 0)
                self.mark_capsule(self.via_blocked, mm(pos.x), mm(pos.y), mm(pos.x), mm(pos.y),
                                  mm(max(drill.x, drill.y)) / 2 + VIA_DRILL / 2 + gap)
            smd = pad.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN)
            for layer in ALL_LAYERS:
                if not pad.IsOnLayer(layer):
                    continue
                if smd and own:
                    # via-in-pad on the net's own pad: allowed, but costly
                    self.mark_poly(self.pad_via, pad, layer, 0.0)
                elif smd:
                    self.mark_poly(self.via_blocked, pad, layer, VIA_CLEAR + via_r)
                if own:
                    continue
                inner = layer in (pcbnew.In1_Cu, pcbnew.In2_Cu) and drill.x > 0
                extra = 0.15 if inner else 0.0
                self.mark_poly(self.blocked[layer], pad, layer, track_infl + extra)
                if not smd:
                    self.mark_poly(self.via_blocked, pad, layer, via_infl + extra)
        for footprint in board.GetFootprints():
            for item in footprint.GraphicalItems():
                layer = item.GetLayer()
                if layer in self.blocked and item.GetClass() != 'PCB_TEXT':
                    self.mark_poly(self.blocked[layer], item, layer, track_infl)
                    self.mark_poly(self.via_blocked, item, layer, via_infl)
        for zone in board.Zones():
            if not zone.GetIsRuleArea():
                continue
            outline = zone.Outline()
            bbox = outline.BBox()
            grow = max(half, VIA_D / 2) + 0.1
            box = self.cells(mm(bbox.GetLeft()) - grow, mm(bbox.GetTop()) - grow,
                             mm(bbox.GetRight()) + grow, mm(bbox.GetBottom()) + grow)
            for cy in range(box[1], box[3] + 1):
                for cx in range(box[0], box[2] + 1):
                    point = pcbnew.VECTOR2I(nm(cx * CELL), nm(cy * CELL))
                    index = cy * NX + cx
                    if zone.GetDoNotAllowVias() and outline.Collide(point, nm(VIA_D / 2 + 0.05)):
                        self.via_blocked[index] = 1
                    if not outline.Collide(point, nm(half + 0.05)):
                        continue
                    if zone.GetDoNotAllowTracks():
                        for layer in ALL_LAYERS:
                            if zone.IsOnLayer(layer):
                                self.blocked[layer][index] = 1
        self.mark_edges()

    def mark_edges(self):
        half = self.width / 2
        for cy in range(NY):
            y = cy * CELL
            for cx in range(NX):
                x = cx * CELL
                outside = (x < EDGE + half or y < EDGE + half or x > W_MM - EDGE - half
                           or y > H_MM - EDGE - half
                           or (NOTCH[0] - EDGE - half < x < NOTCH[2] + EDGE + half
                               and y < NOTCH[3] + EDGE + half)
                           or not (self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1))
                via_out = (x < EDGE + VIA_D / 2 + 0.1 or y < EDGE + VIA_D / 2 + 0.1
                           or x > W_MM - EDGE - VIA_D / 2 - 0.1
                           or y > H_MM - EDGE - VIA_D / 2 - 0.1
                           or (NOTCH[0] - 0.8 < x < NOTCH[2] + 0.8 and y < NOTCH[3] + 0.8))
                index = cy * NX + cx
                if outside:
                    for layer in ALL_LAYERS:
                        self.blocked[layer][index] = 1
                if outside or via_out:
                    self.via_blocked[index] = 1


NEIGHBOURS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
              (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def astar(grid, starts, goals):
    goal_cells = {index for _, index in goals}
    goal_set = set(goals)
    gx = sum(index % NX for index in goal_cells) / len(goal_cells)
    gy = sum(index // NX for index in goal_cells) / len(goal_cells)

    def heuristic(index):
        dx, dy = abs(index % NX - gx), abs(index // NX - gy)
        return HWEIGHT * (max(dx, dy) + 0.4142 * min(dx, dy))

    best, parent, frontier = {}, {}, []
    for state in starts:
        best[state] = 0.0
        parent[state] = None
        heapq.heappush(frontier, (heuristic(state[1]), 0.0, state))
    expanded = 0
    while frontier:
        _, cost, state = heapq.heappop(frontier)
        if cost > best.get(state, 1e18):
            continue
        if state in goal_set:
            path = []
            while state is not None:
                path.append(state)
                state = parent[state]
            return path[::-1]
        expanded += 1
        if expanded > MAX_EXPAND:
            return None
        layer, index = state
        cx, cy = index % NX, index // NX
        blocked = grid.blocked[layer]
        soft, soft_via = grid.soft, grid.soft_via
        for dx, dy, step in NEIGHBOURS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < NX and 0 <= ny < NY):
                continue
            nindex = ny * NX + nx
            if blocked[nindex] and (layer, nindex) not in goal_set:
                continue
            if dx and dy and (blocked[cy * NX + nx] or blocked[ny * NX + cx]):
                continue
            nstate = (layer, nindex)
            ncost = cost + step * LAYER_COST.get(layer, 1.0)
            if soft is not None and soft[layer][nindex]:
                ncost += SOFT_COST
            if ncost < best.get(nstate, 1e18):
                best[nstate] = ncost
                parent[nstate] = state
                heapq.heappush(frontier, (ncost + heuristic(nindex), ncost, nstate))
        if not grid.via_blocked[index]:
            for other in ROUTE_LAYERS:
                if other == layer or grid.blocked[other][index]:
                    continue
                nstate = (other, index)
                ncost = cost + (VIA_IN_PAD_COST if grid.pad_via[index] else VIA_COST)
                if soft is not None and (soft_via[index] or soft[other][index]):
                    ncost += SOFT_COST * 4
                if ncost < best.get(nstate, 1e18):
                    best[nstate] = ncost
                    parent[nstate] = state
                    heapq.heappush(frontier, (ncost + heuristic(index), ncost, nstate))
    return None


def octilinear(a, b):
    """True if the line between two cells runs at a multiple of 45 degrees."""
    dx, dy = abs(b % NX - a % NX), abs(b // NX - a // NX)
    return dx == 0 or dy == 0 or dx == dy


def clear_line(grid, layer, a, b):
    ax, ay = a % NX, a // NX
    bx, by = b % NX, b // NX
    steps = max(abs(bx - ax), abs(by - ay)) * 2
    blocked = grid.blocked[layer]
    for step in range(steps + 1):
        t = step / steps if steps else 0
        x, y = ax + (bx - ax) * t, ay + (by - ay) * t
        for cx in (math.floor(x), math.ceil(x)):
            for cy in (math.floor(y), math.ceil(y)):
                if blocked[cy * NX + cx]:
                    return False
    return True


def smooth(grid, path):
    """Splits the path into same-layer runs and shortcuts each by line of sight."""
    runs, current = [], [path[0]]
    for state in path[1:]:
        if state[0] != current[-1][0]:
            runs.append(current)
            current = [state]
        else:
            current.append(state)
    runs.append(current)
    result = []
    for run in runs:
        layer = run[0][0]
        points = [run[0][1]]
        i = 0
        while i < len(run) - 1:
            j = len(run) - 1
            while j > i + 1 and not (octilinear(run[i][1], run[j][1])
                                     and clear_line(grid, layer, run[i][1], run[j][1])):
                j -= 1
            points.append(run[j][1])
            i = j
        result.append((layer, points))
    return result


def parse_item(board, item):
    desc = item['description']
    pos = (item['pos']['x'], item['pos']['y'])
    match = re.search(r' on (\S+\.Cu)', desc)
    if desc.startswith('PTH pad'):
        layers = ROUTE_LAYERS
    elif match:
        layers = [layer_by_name(board, match.group(1))]
    else:
        layers = ROUTE_LAYERS
    net = re.search(r'\[(.*?)\]', desc).group(1)
    if board.FindNet(net) is None:  # the report prints {slash} in auto net names as /
        net = net.replace('/', '{slash}')
    return net, pos, [layer for layer in layers if layer in ROUTE_LAYERS]


def width_for(board, net):
    # WIDTH forces a width, e.g. for a power net's low-current feedback tap
    if os.environ.get('WIDTH'):
        return float(os.environ['WIDTH'])
    netinfo = board.FindNet(net)
    name = netinfo.GetNetClassName() if netinfo else 'Default'
    for key, value in WIDTHS.items():
        if key == name or name.endswith(',' + key) or name.startswith(key + ','):
            return value
    return SIGNAL_WIDTH


def add_route(board, net, runs, start_pos, end_pos, width):
    netinfo = board.FindNet(net)
    for number, (layer, points) in enumerate(runs):
        coords = [(index % NX * CELL, index // NX * CELL) for index in points]
        if number == 0:
            coords[0] = start_pos
        if number == len(runs) - 1:
            coords[-1] = end_pos
        for a, b in zip(coords, coords[1:]):
            if math.dist(a, b) < 0.01:
                continue
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(nm(a[0]), nm(a[1])))
            track.SetEnd(pcbnew.VECTOR2I(nm(b[0]), nm(b[1])))
            track.SetWidth(nm(width))
            track.SetLayer(layer)
            track.SetNet(netinfo)
            board.Add(track)
        if number < len(runs) - 1:
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(nm(coords[-1][0]), nm(coords[-1][1])))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetWidth(nm(VIA_D))
            via.SetDrill(nm(VIA_DRILL))
            via.SetNet(netinfo)
            board.Add(via)


def route_pair(board, pair, margin):
    net, start_pos, start_layers = parse_item(board, pair[0])
    _, end_pos, end_layers = parse_item(board, pair[1])
    if net in SKIP_NETS:
        return 'skip'
    code = board.FindNet(net).GetNetCode()
    base = width_for(board, net)
    for width in sorted({base, min(base, SIGNAL_WIDTH), 0.15}, reverse=True):
        region = (min(start_pos[0], end_pos[0]) - margin, min(start_pos[1], end_pos[1]) - margin,
                  max(start_pos[0], end_pos[0]) + margin, max(start_pos[1], end_pos[1]) + margin)
        grid = Grid(board, code, width, region)
        sc, gc = cell_of(*start_pos), cell_of(*end_pos)
        starts = [(layer, sc[1] * NX + sc[0]) for layer in start_layers]
        goals = [(layer, gc[1] * NX + gc[0]) for layer in end_layers]
        for layer, index in starts:
            grid.blocked[layer][index] = 0
        path = astar(grid, starts, goals)
        if path:
            runs = smooth(grid, path)
            add_route(board, net, runs, start_pos, end_pos, width)
            return f'ok w={width} vias={len(runs) - 1}'
    return 'FAILED'


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    report = json.load(open(sys.argv[2]))
    out = sys.argv[3] if len(sys.argv) > 3 else sys.argv[1]
    only = set(sys.argv[4].split(',')) if len(sys.argv) > 4 else None
    first = os.environ.get('FIRST', '').split(',')

    def order(entry):
        a, b = entry['items']
        pinned = any(' of %s ' % ref in item['description'] + ' '
                     for item in (a, b) for ref in first if ref)
        span = math.dist((a['pos']['x'], a['pos']['y']), (b['pos']['x'], b['pos']['y']))
        return (not pinned, span)

    for entry in sorted(report['unconnected_items'], key=order):
        pair = entry['items']
        net = parse_item(board, pair[0])[0]
        if only and net not in only:
            continue
        result = route_pair(board, pair, 6.0)
        if result == 'FAILED':
            result = route_pair(board, pair, 40.0)
        print(net, result, flush=True)
    board.Save(out)


if __name__ == '__main__':
    main()
