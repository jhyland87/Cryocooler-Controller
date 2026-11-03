"""Removes edge-crowding GND vias, refills, and stitches GND pour islands on
F.Cu and B.Cu with a via each. Usage: finish_route.py in.kicad_pcb out.kicad_pcb"""
import sys

import pcbnew

import fix_route
import gridroute as gr

def mm(value):
    return value / 1e6


def remove_edge_vias(board):
    removed = []
    for via in [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
        pos = via.GetPosition()
        x, y = mm(pos.x), mm(pos.y)
        radius = mm(via.GetWidth(pcbnew.F_Cu)) / 2
        if min(x, y, 100 - x, 62 - y) < 0.3 + radius:
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


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
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
    filler.Fill(board.Zones())
    board.Save(sys.argv[2])


if __name__ == '__main__':
    main()
