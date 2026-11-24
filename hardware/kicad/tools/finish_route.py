"""Removes edge-crowding GND vias, refills, and stitches GND pour islands on
F.Cu and B.Cu with a via each. Usage: finish_route.py in.kicad_pcb out.kicad_pcb"""
import argparse
import math
import sys
from pathlib import Path

import pcbnew

import board_checks
import fix_route
import gridroute as gr
from findings import DEFAULT_PROJECT, Config

def mm(value):
    return value / 1e6


def remove_edge_vias(board):
    removed = []
    box = board.GetBoardEdgesBoundingBox()
    right, bottom = mm(box.GetRight()), mm(box.GetBottom())
    for via in [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
        pos = via.GetPosition()
        x, y = mm(pos.x), mm(pos.y)
        radius = mm(via.GetWidth(pcbnew.F_Cu)) / 2
        if min(x, y, right - x, bottom - y) < 0.3 + radius:
            removed.append((round(x, 2), round(y, 2), via.GetNetname()))
            board.Delete(via)
    return removed


def remove_stub_segments(board, shortest=0.01):
    """Deletes segments shorter than `shortest` mm (router snap leftovers)."""
    stubs = [t for t in board.GetTracks()
             if t.Type() == pcbnew.PCB_TRACE_T and mm(t.GetLength()) < shortest]
    for track in stubs:
        board.Delete(track)
    return len(stubs)


def stitch_islands(board, layer, diameter=0.5, drill=0.3):
    added = []
    radius = diameter / 2
    for zone in list(board.Zones()):
        if zone.GetIsRuleArea() or zone.GetNetname() != 'GND' or not zone.IsOnLayer(layer):
            continue
        vias = [t for t in board.GetTracks()
                if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND']
        pads = [p for p in board.GetPads() if p.GetNetname() == 'GND' and p.IsOnLayer(layer)]
        filled = zone.GetFilledPolysList(layer)
        for index in range(filled.OutlineCount()):
            if any(filled.Contains(v.GetPosition(), index) for v in vias):
                continue
            if any(p.GetDrillSize().x > 0 and filled.Contains(p.GetPosition(), index)
                   for p in pads):
                continue
            box = filled.Outline(index).BBox()
            left, top = mm(box.GetLeft()), mm(box.GetTop())
            best = None
            for step_x in range(int((mm(box.GetRight()) - left) / 0.1) + 1):
                for step_y in range(int((mm(box.GetBottom()) - top) / 0.1) + 1):
                    x, y = left + step_x * 0.1, top + step_y * 0.1
                    if not all(filled.Contains(pcbnew.VECTOR2I(pcbnew.FromMM(x + dx),
                                                               pcbnew.FromMM(y + dy)), index)
                               for dx, dy in ((0, 0), (radius, 0), (-radius, 0),
                                              (0, radius), (0, -radius))):
                        continue
                    gap = fix_route.foreign_gap(board, x, y, radius, 'GND')
                    if best is None or gap > best[0]:
                        best = (gap, x, y)
            if best is None or best[0] < 0.2:
                print('no room for an island via near', round(left, 1), round(top, 1))
                continue
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(best[1]), pcbnew.FromMM(best[2])))
            via.SetWidth(pcbnew.FromMM(diameter))
            via.SetDrill(pcbnew.FromMM(drill))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetNet(board.FindNet('GND'))
            board.Add(via)
            added.append((board.GetLayerName(layer), round(best[1], 2), round(best[2], 2)))
    return added


def isolated_ground_pads(board):
    """GND SMD pads sitting in a pour fragment with no via or plated hole."""
    vias = [t for t in board.GetTracks()
            if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND']
    found = []
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetNetname() != 'GND':
            continue
        layer = zone.GetLayer()
        filled = zone.GetFilledPolysList(layer)
        pads = [p for p in board.GetPads() if p.GetNetname() == 'GND' and p.IsOnLayer(layer)]
        tracks = [t for t in board.GetTracks()
                  if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == 'GND'
                  and t.GetLayer() == layer]
        for index in range(filled.OutlineCount()):
            if any(filled.Contains(v.GetPosition(), index) for v in vias):
                continue
            if any(p.GetDrillSize().x > 0 and filled.Contains(p.GetPosition(), index)
                   for p in pads):
                continue
            if any(filled.Contains(t.GetStart(), index) or filled.Contains(t.GetEnd(), index)
                   for t in tracks):
                continue
            found += [(p, layer) for p in pads
                      if p.GetDrillSize().x == 0 and filled.Contains(p.GetPosition(), index)]
    return found


def dogbone_to_plane(board, pad, layer, width=0.25):
    """Short track from the pad to the nearest legal via spot, plus the via."""
    centre = pad.GetPosition()
    x, y = mm(centre.x), mm(centre.y)
    grid = gr.Grid(board, pad.GetNetCode(), width, (x - 4, y - 4, x + 4, y + 4))
    cx, cy = gr.cell_of(x, y)
    start = cy * gr.NX + cx
    blocked = grid.blocked[layer]
    parent = {start: None}
    queue = [start]
    for index in queue:
        if not grid.via_blocked[index] and not grid.pad_via[index]:
            path = []
            while index is not None:
                path.append(index)
                index = parent[index]
            points = [(i % gr.NX * gr.CELL, i // gr.NX * gr.CELL) for i in reversed(path)]
            points[0] = (x, y)
            gr.add_route(board, 'GND', [(layer, [gr.cell_of(*p)[1] * gr.NX + gr.cell_of(*p)[0]
                                                  for p in points]), (pcbnew.In1_Cu, [path[0]])],
                         (x, y), points[-1], width)
            return points[-1]
        ix, iy = index % gr.NX, index // gr.NX
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (iy + dy) * gr.NX + ix + dx
            if nxt not in parent and not blocked[nxt]:
                parent[nxt] = index
                queue.append(nxt)
    return None


def lands_on_ground_fill(board, ctx, x, y, radius):
    """True if a via of this radius at (x, y) sits wholly on filled ground
    zone copper on some layer.
    """
    spots = [(0, 0), (radius, 0), (-radius, 0), (0, radius), (0, -radius)]
    for zone in board.Zones():
        if zone.GetIsRuleArea() or not ctx.is_ground(zone.GetNetname()):
            continue
        for layer in zone.GetLayerSet().Seq():
            filled = zone.GetFilledPolysList(layer)
            if all(filled.Contains(board_checks.point(x + dx, y + dy))
                   for dx, dy in spots):
                return zone.GetNetname()
    return None


HOLE_GAP = 0.2  # board setting: smallest gap between two drilled holes, mm


class Holes:
    """Drilled holes (vias and pads) in 1 mm buckets, to keep a new via's hole off the rest."""

    def __init__(self, board):
        self.buckets = {}
        for item in board.GetTracks():
            if item.Type() == pcbnew.PCB_VIA_T:
                self.add(mm(item.GetPosition().x), mm(item.GetPosition().y), mm(item.GetDrillValue()) / 2)
        for pad in board.GetPads():
            if pad.GetDrillSize().x > 0:
                self.add(mm(pad.GetPosition().x), mm(pad.GetPosition().y), mm(max(pad.GetDrillSize().x, pad.GetDrillSize().y)) / 2)

    def add(self, x, y, radius):
        self.buckets.setdefault((int(x), int(y)), []).append((x, y, radius))

    def clear(self, x, y, radius):
        return not any(math.dist((x, y), (hx, hy)) < radius + hr + HOLE_GAP
                       for i in range(int(x) - 1, int(x) + 2) for j in range(int(y) - 1, int(y) + 2)
                       for hx, hy, hr in self.buckets.get((i, j), ()))


def stitch_spot(board, ctx, via, reach, radius, clearance, holes=None, drill=0.3):
    """Nearest (x, y, ground net) within reach of the via where a ground via
    clears other copper by `clearance` and lands on ground fill, or None.
    A spot whose hole would sit closer than HOLE_GAP to another hole is skipped.
    """
    cx, cy = board_checks.xy(via.GetPosition())
    steps = int(reach / 0.1)
    spots = sorted(
        (math.hypot(i, j), i, j)
        for i in range(-steps, steps + 1)
        for j in range(-steps, steps + 1)
        if math.hypot(i, j) * 0.1 <= reach
    )
    for _, i, j in spots:
        x, y = cx + i * 0.1, cy + j * 0.1
        if holes is not None and not holes.clear(x, y, drill / 2):
            continue
        if fix_route.foreign_gap(board, x, y, radius, 'GND') < clearance:
            continue
        net = lands_on_ground_fill(board, ctx, x, y, radius)
        if net:
            return x, y, net
    return None


def far_signal_vias(board, ctx, reach, nets=None):
    """[(via, search limit)] for unlocked signal vias (optionally only of `nets`) with no ground via
    or plated ground hole within `reach` mm; the limit is just under the distance to the nearest one."""
    vias = [v for v in board.GetTracks() if board_checks.is_via(v)]
    ground = [board_checks.xy(v.GetPosition()) for v in vias if ctx.is_ground(v.GetNetname())]
    ground += [board_checks.xy(p.GetPosition()) for p in board.GetPads()
               if p.HasHole() and ctx.is_ground(p.GetNetname())]
    found = []
    for via in vias:
        net = via.GetNetname()
        if not net or via.IsLocked() or ctx.is_plane(net) or (nets and net not in nets):
            continue
        near = min((math.dist(board_checks.xy(via.GetPosition()), g) for g in ground), default=1e9)
        if near > reach:
            found.append((via, near - 0.1))
    return found


def stitch_signal_vias(board, ctx, diameter=0.5, drill=0.3, reach=None, nets=None):
    """Adds a ground via near each signal via that has none within reach.
    Returns (added, skipped) counts. By default `reach` is the check's own, and the
    via goes within it. With `reach` (mm), every unlocked signal via (of `nets`, if given)
    farther than that from a ground via gets one at the nearest legal spot closer than
    its current nearest ground.
    """
    # the net classes' clearance (0.15 mm), not the board minimum (0.1 mm): a via at the minimum
    # fails DRC against tracks
    settings = board.GetDesignSettings()
    clearance = mm(max(settings.m_MinClearance, settings.m_NetSettings.GetDefaultNetclass().GetClearance()))
    added = skipped = 0
    holes = Holes(board)
    if reach is None:
        failing = board_checks.vias_without_ground_via(ctx)
    else:
        failing = far_signal_vias(board, ctx, reach, nets)
    for via, limit in failing:
        spot = stitch_spot(board, ctx, via, limit, diameter / 2, clearance, holes, drill)
        if spot is None:
            skipped += 1
            continue
        new = pcbnew.PCB_VIA(board)
        new.SetPosition(board_checks.point(spot[0], spot[1]))
        new.SetWidth(pcbnew.FromMM(diameter))
        new.SetDrill(pcbnew.FromMM(drill))
        new.SetViaType(pcbnew.VIATYPE_THROUGH)
        new.SetNet(board.FindNet(spot[2]))
        board.Add(new)
        holes.add(spot[0], spot[1], drill / 2)
        added += 1
    return added, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('output')
    parser.add_argument('--stitch', action='store_true',
                        help='add ground vias beside signal vias lacking one')
    parser.add_argument('--reach', type=float,
                        help='with --stitch: stitch every signal via farther than MM from a ground via')
    parser.add_argument('--nets', help='with --reach: only these nets, comma separated')
    parser.add_argument('--project', default=DEFAULT_PROJECT)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(args.input)
    print('edge vias removed:', remove_edge_vias(board))
    print('stub segments removed:', remove_stub_segments(board))
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        print('island vias:', stitch_islands(board, layer))
        filler.Fill(board.Zones())
    for pad, layer in isolated_ground_pads(board):
        name = pad.GetParentFootprint().GetReference() + '.' + pad.GetNumber()
        print('dog-bone for', name, dogbone_to_plane(board, pad, layer))
    if args.stitch:
        ctx = board_checks.Context(
            board, Config.load(Path(args.project).parent), args.input)
        added, skipped = stitch_signal_vias(
            board, ctx, reach=args.reach, nets=set(args.nets.split(',')) if args.nets else None)
        print(f'stitch vias: {added} added, {skipped} skipped')
    filler.Fill(board.Zones())
    board.Save(args.output)


if __name__ == '__main__':
    main()
