"""Grid A* router for the connections Freerouting left open.

Usage: gridroute.py board.kicad_pcb drc.json [out.kicad_pcb [NET,...]]
Routes each unconnected pair from a kicad-cli DRC report on F.Cu / In2.Cu /
B.Cu (In1 is the GND plane), with 0.45/0.2 through vias, then saves.
LINKS=NET (with `-` for drc.json): joins the separate copper islands of NET (pads, tracks, vias,
pour islands) instead of the DRC list, nearest items first, for a pour the signals have cut up.
NECK=REF.PAD,...: when one of these pads cannot be left at its class width, a 0.2 mm neck of at most 1 mm out of
it, then class width again (off by default; run it last; only for a pad that serves one low-current load, never
on the locked-current nets).
Env knobs: FIRST=U20,U21 (pairs on those parts first), CLEAR=0.15 (clearance, mm), FINE=1 (0.1 mm
clearance), VIA_TRACK_CLEAR=0.15 (new via to tracks and vias, mm; not below the board clearance), IN1=1 / IN1_COST, VIA_COST,
HWEIGHT, MAX_EXPAND.
"""
import heapq
import os
import json
import math
import re
import sys

import pcbnew

CELL = 0.05


def load_argv_board():
    """The board named on the command line; the router needs its outline."""
    path = next((arg for arg in sys.argv[1:] if arg.endswith('.kicad_pcb')), None)
    if path is None:
        sys.exit('gridroute: no .kicad_pcb on the command line')
    return pcbnew.LoadBoard(path)


BOARD = load_argv_board()


def board_size():
    """Right and bottom of the board edge (the outline starts at 0, 0)."""
    box = BOARD.GetBoardEdgesBoundingBox()
    return box.GetRight() / 1e6, box.GetBottom() / 1e6


def top_notch():
    """(x0, y0, x1, y1) of a notch cut into the top edge: the outline corners
    strictly inside the board box in its top half. A far-off box if none."""
    outlines = pcbnew.SHAPE_POLY_SET()
    BOARD.GetBoardPolygonOutlines(outlines, False)
    box = outlines.BBox()
    inner = []
    for index in range(outlines.OutlineCount()):
        line = outlines.Outline(index)
        for point_index in range(line.PointCount()):
            point = line.CPoint(point_index)
            if box.GetLeft() < point.x < box.GetRight() and box.GetTop() < point.y < (box.GetTop() + box.GetBottom()) / 2:
                inner.append((point.x / 1e6, point.y / 1e6))
    if not inner:
        return (-10.0, -10.0, -9.0, -9.0)
    return (min(x for x, _ in inner), 0.0, max(x for x, _ in inner), max(y for _, y in inner))


W_MM, H_MM = board_size()
NX, NY = int(W_MM / CELL) + 1, int(H_MM / CELL) + 1
N = NX * NY
FINE = os.environ.get('FINE') == '1'
CLEAR = float(os.environ.get('CLEAR', 0.1 if FINE else 0.15))
EDGE = 0.35
VIA_D, VIA_DRILL = 0.45, 0.2
HOLE_GAP = 0.25
VIA_COST = float(os.environ.get('VIA_COST', '30'))
VIA_IN_PAD_COST = 120.0
SOFT_COST = float(os.environ.get('SOFT_COST', '6'))
HWEIGHT = float(os.environ.get('HWEIGHT', '1.0'))
MAX_EXPAND = int(os.environ.get('MAX_EXPAND', '3000000'))
VIA_CLEAR = 0.1  # new via to a surface-mount pad (kicad_dru via_in_pad_clearance)
# new via to tracks, vias and through-hole pads: the full board clearance, never VIA_CLEAR
VIA_TRACK_CLEAR = float(os.environ.get('VIA_TRACK_CLEAR', 0.15))
NPTH_CLEAR = 0.25  # kicad_dru jlc_npth_to_copper is 0.2 mm; the grid adds a cell
NOTCH = top_notch()  # antenna notch in the top edge
SKIP_NETS = set(os.environ.get('SKIP', 'GND').split(','))  # nets the pours connect
ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
if os.environ.get('IN1') == '1':
    ROUTE_LAYERS.append(pcbnew.In1_Cu)
LAYER_COST = {pcbnew.In1_Cu: float(os.environ.get('IN1_COST', '8'))}
ALL_LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
WIDTHS = {
    'Power': 0.3, 'Power5V': 0.3, 'PowerAnalogPos': 0.3, 'PowerAnalogNeg': 0.3,
    'PowerIso': 0.3,
    'Power12V': 0.8, 'Earth': 1.5, 'Usb': 0.2,
}
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
        via_infl = VIA_TRACK_CLEAR + via_r
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
                # jlc_npth_to_copper: 0.2 mm from an unplated hole, against CLEAR elsewhere
                npth = pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
                extra = 0.15 if inner else NPTH_CLEAR - CLEAR if npth else 0.0
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


VIA_SPACING_CELLS = 9  # a path's own vias stay this many cells (0.45 mm) apart


def via_behind(parent, state):
    """True if the path to `state` changed layer within the last VIA_SPACING_CELLS cells: a second
    via there would put two holes closer than the board allows (the grid only knows existing vias)."""
    for _ in range(VIA_SPACING_CELLS):
        before = parent[state]
        if before is None:
            return False
        if before[0] != state[0]:
            return True
        state = before
    return False


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
        if not grid.via_blocked[index] and not via_behind(parent, state):
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


def class_width(board, net):
    """The net class track width of `net` in mm: the narrowest a route of it may be."""
    settings = board.GetDesignSettings().m_NetSettings
    return mm(settings.GetEffectiveNetClass(net).GetTrackWidth())


def widths_for(board, net):
    """Track widths to try, widest first. The net class width is the floor."""
    # WIDTH forces a width, e.g. for a power net's low-current feedback tap
    if os.environ.get('WIDTH'):
        return [float(os.environ['WIDTH'])]
    netinfo = board.FindNet(net)
    name = netinfo.GetNetClassName() if netinfo else 'Default'
    wanted = next((value for key, value in WIDTHS.items()
                   if key == name or name.endswith(',' + key) or name.startswith(key + ',')), SIGNAL_WIDTH)
    floor = class_width(board, net)
    return sorted({max(wanted, floor), floor}, reverse=True)


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


def pad_cells(board, code, pos, layers, grid):
    """(layer, cell) states on the net's own pad at `pos` that a track of the grid's width fits."""
    cells = []
    point = pcbnew.VECTOR2I(nm(pos[0]), nm(pos[1]))
    for pad in board.GetPads():
        if pad.GetNetCode() != code or not pad.HitTest(point):
            continue
        box = pad.GetBoundingBox()
        for layer in layers:
            if not pad.IsOnLayer(layer):
                continue
            for cy in range(int(mm(box.GetTop()) / CELL), int(mm(box.GetBottom()) / CELL) + 2):
                for cx in range(int(mm(box.GetLeft()) / CELL), int(mm(box.GetRight()) / CELL) + 2):
                    index = cy * NX + cx
                    if (not grid.blocked[layer][index] and pad.HitTest(pcbnew.VECTOR2I(nm(cx * CELL), nm(cy * CELL)))):
                        cells.append((layer, index))
    return cells


NECK = {name for name in os.environ.get('NECK', '').split(',') if name}  # pads (REF.PAD) that may get a neck, last repair step
NECK_WIDTH, NECK_MAX = 0.2, 1.0
NECK_SKIP = {'Net-(F1-Pad1)', 'VIN', 'VSW', 'Net-(J12-Pin_1)', 'Net-(J11-Pin_1)'}  # the locked-current nets


def route_between(board, net, code, start_pos, start_layers, end_pos, end_layers, margin, widths):
    """A* between two points, widest width first; a result text, or None if no width worked."""
    for width in widths:
        region = (min(start_pos[0], end_pos[0]) - margin, min(start_pos[1], end_pos[1]) - margin,
                  max(start_pos[0], end_pos[0]) + margin, max(start_pos[1], end_pos[1]) + margin)
        grid = Grid(board, code, width, region)
        sc, gc = cell_of(*start_pos), cell_of(*end_pos)
        starts = [(layer, sc[1] * NX + sc[0]) for layer in start_layers]
        goals = [(layer, gc[1] * NX + gc[0]) for layer in end_layers]
        # a wide track must fit at its pads; only the narrowest width may force it
        if width > widths[-1] and not all(any(not grid.blocked[layer][index] for layer, index in group)
                                          for group in (starts, goals)):
            continue
        # a track may also begin or end anywhere on its pad where it clears the neighbours
        # (a pad's centre can be too close to a neighbour for the track's width)
        centres = (set(starts), set(goals))
        starts = starts + [cell for cell in pad_cells(board, code, start_pos, start_layers, grid) if cell not in starts]
        goals = goals + [cell for cell in pad_cells(board, code, end_pos, end_layers, grid) if cell not in goals]
        for layer, index in centres[0]:
            grid.blocked[layer][index] = 0
        path = astar(grid, starts, goals)
        if path:
            runs = smooth(grid, path)
            first, last = path[0], path[-1]
            if first not in centres[0]:
                start_pos = (first[1] % NX * CELL, first[1] // NX * CELL)
            if last not in centres[1]:
                end_pos = (last[1] % NX * CELL, last[1] // NX * CELL)
            add_route(board, net, runs, start_pos, end_pos, width)
            return f'ok w={width} vias={len(runs) - 1}'
    return None


def free_region(grid, layer, index, limit=4000):
    """True if the cell is part of a free area of at least `limit` cells on its layer."""
    seen, queue = {index}, [index]
    for current in queue:
        x, y = current % NX, current // NX
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (y + dy) * NX + x + dx
            if 0 <= nxt < N and not grid.blocked[layer][nxt] and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
                if len(seen) >= limit:
                    return True
    return False


def neck_out(board, net, code, pos, layers, class_width, margin=4.0):
    """Finds a NECK_WIDTH track from the pad at `pos` to the nearest cell (within NECK_MAX mm) where a
    track of the class width fits in open copper; returns (cell position, layer, length, pad name, a function
    that draws the neck) or None."""
    region = (pos[0] - margin, pos[1] - margin, pos[0] + margin, pos[1] + margin)
    narrow, wide = Grid(board, code, NECK_WIDTH, region), Grid(board, code, class_width, region)
    for layer in layers:
        starts = [cell for cell in pad_cells(board, code, pos, [layer], narrow)]
        if not starts:
            continue
        best, parent, frontier = {cell: 0.0 for cell in starts}, {cell: None for cell in starts}, [(0.0, cell) for cell in starts]
        while frontier:
            dist, cell = heapq.heappop(frontier)
            if dist > best.get(cell, 1e9):
                continue
            index = cell[1]
            if cell not in starts and not wide.blocked[layer][index] and free_region(wide, layer, index):
                path = []
                while cell is not None:
                    path.append(cell)
                    cell = parent[cell]
                path.reverse()
                runs = smooth(narrow, path)
                begin, end = (path[0][1] % NX * CELL, path[0][1] // NX * CELL), (path[-1][1] % NX * CELL, path[-1][1] // NX * CELL)
                name = pad_name(board, code, pos)
                return end, layer, dist, name, lambda: add_route(board, net, runs, begin, end, NECK_WIDTH)
            x, y = index % NX, index // NX
            for dx, dy, step in NEIGHBOURS:
                nxt = (y + dy) * NX + x + dx
                if 0 <= nxt < N and not narrow.blocked[layer][nxt] and dist + step * CELL <= NECK_MAX:
                    state = (layer, nxt)
                    if dist + step * CELL < best.get(state, 1e9):
                        best[state] = dist + step * CELL
                        parent[state] = cell
                        heapq.heappush(frontier, (best[state], state))
    return None


def pad_name(board, code, pos):
    """REF.PAD of the net's pad at `pos`, or '?'."""
    point = pcbnew.VECTOR2I(nm(pos[0]), nm(pos[1]))
    return next((f'{p.GetParentFootprint().GetReference()}.{p.GetNumber()}' for p in board.GetPads()
                 if p.GetNetCode() == code and p.HitTest(point)), '?')


def route_pair(board, pair, margin):
    net, start_pos, start_layers = parse_item(board, pair[0])
    _, end_pos, end_layers = parse_item(board, pair[1])
    if net in SKIP_NETS:
        return 'skip'
    code = board.FindNet(net).GetNetCode()
    widths = widths_for(board, net)
    result = route_between(board, net, code, start_pos, start_layers, end_pos, end_layers, margin, widths)
    if result:
        return result
    if not NECK or net in NECK_SKIP or widths[-1] <= NECK_WIDTH:
        return 'FAILED'
    for ends in ((start_pos, start_layers, end_pos, end_layers), (end_pos, end_layers, start_pos, start_layers)):
        if pad_name(board, code, ends[0]) not in NECK:
            continue
        found = neck_out(board, net, code, ends[0], ends[1], widths[-1])
        if found is None:
            continue
        cell, layer, length, name, draw = found
        result = route_between(board, net, code, cell, [layer], ends[2], ends[3], margin, widths)
        if result:
            draw()
            print(f'neck {net} pad {name}: {NECK_WIDTH:g} mm wide, {length:.2f} mm long')
            return result + ' (neck)'
    return 'FAILED'


def fragment_links(board, net):
    """DRC-style unconnected pairs joining each smaller copper cluster of `net` (pads, tracks,
    vias and filled pour islands, joined by overlap) to the largest one at their nearest
    via or pad."""
    code = board.FindNet(net).GetNetCode()
    nodes = []
    for track in board.GetTracks():
        if track.GetNetCode() == code:
            nodes.append(('via' if track.GetClass() == 'PCB_VIA' else 'trk', track, track.GetPosition()))
    for pad in board.GetPads():
        if pad.GetNetCode() == code:
            nodes.append(('pad', pad, pad.GetPosition()))
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetNetCode() != code:
            continue
        for layer in zone.GetLayerSet().Seq():
            filled = zone.GetFilledPolysList(layer)
            nodes += [('isl', (filled, index, layer), None) for index in range(filled.OutlineCount())]
    parent = list(range(len(nodes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(i, j):
        parent[find(i)] = find(j)

    kinds = {kind: [i for i, node in enumerate(nodes) if node[0] == kind] for kind in ('via', 'trk', 'pad', 'isl')}
    accuracy = nm(0.001)
    for i in kinds['trk']:
        track = nodes[i][1]
        for j in kinds['trk']:
            other = nodes[j][1]
            if j > i and other.GetLayer() == track.GetLayer() and (
                    track.HitTest(other.GetStart(), accuracy) or track.HitTest(other.GetEnd(), accuracy)
                    or other.HitTest(track.GetStart(), accuracy) or other.HitTest(track.GetEnd(), accuracy)):
                join(i, j)
        for j in kinds['via']:
            if track.HitTest(nodes[j][2], accuracy):
                join(i, j)
        for j in kinds['pad']:
            pad = nodes[j][1]
            if pad.IsOnLayer(track.GetLayer()) and (pad.HitTest(track.GetStart()) or pad.HitTest(track.GetEnd())
                                                    or track.HitTest(pad.GetPosition(), accuracy)):
                join(i, j)
    for j in kinds['via']:
        via = nodes[j][1]
        for k in kinds['pad']:
            if nodes[k][1].HitTest(nodes[j][2]):
                join(j, k)
        for k in kinds['via']:
            other = nodes[k][1]
            if k > j and math.dist((nodes[j][2].x, nodes[j][2].y), (nodes[k][2].x, nodes[k][2].y)) < (
                    via.GetWidth(pcbnew.F_Cu) + other.GetWidth(pcbnew.F_Cu)) / 2:
                join(j, k)
    for k in kinds['isl']:
        filled, index, layer = nodes[k][1]
        for j in kinds['via']:
            if filled.Contains(nodes[j][2], index):
                join(k, j)
        for j in kinds['pad']:
            if nodes[j][1].IsOnLayer(layer) and filled.Contains(nodes[j][2], index):
                join(k, j)
        for j in kinds['trk']:
            track = nodes[j][1]
            if track.GetLayer() == layer and (filled.Contains(track.GetStart(), index) or filled.Contains(track.GetEnd(), index)):
                join(k, j)
    clusters = {}
    for i in range(len(nodes)):
        clusters.setdefault(find(i), []).append(i)
    clusters = sorted((c for c in clusters.values() if any(nodes[i][0] != 'isl' for i in c)), key=len, reverse=True)

    def anchors(cluster):
        return [nodes[i] for i in cluster if nodes[i][0] in ('via', 'pad')]

    def item(node):
        kind, obj, pos = node
        if kind == 'via':
            text = f'Via [{net}] on F.Cu - B.Cu'
        elif obj.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            text = f'PTH pad {obj.GetNumber()} [{net}] of {obj.GetParentFootprint().GetReference()}'
        else:
            text = (f'Pad {obj.GetNumber()} [{net}] of {obj.GetParentFootprint().GetReference()} on '
                    f'{"B" if obj.GetParentFootprint().IsFlipped() else "F"}.Cu')
        return {'description': text, 'pos': {'x': mm(pos.x), 'y': mm(pos.y)}}

    pairs = []
    for cluster in clusters[1:]:
        small = anchors(cluster)
        if small:
            a, b = min(((x, y) for x in small for y in anchors(clusters[0])),
                       key=lambda pair: math.dist((pair[0][2].x, pair[0][2].y), (pair[1][2].x, pair[1][2].y)))
            pairs.append({'items': [item(a), item(b)]})
    return pairs


def main():
    board = BOARD
    links = os.environ.get('LINKS')
    report = {'unconnected_items': fragment_links(board, links)} if links else json.load(open(sys.argv[2]))
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
