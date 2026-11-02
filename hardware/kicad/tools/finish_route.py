"""Removes edge-crowding GND vias, refills, and stitches GND pour islands on
F.Cu and B.Cu with a via each. Usage: finish_route.py in.kicad_pcb out.kicad_pcb"""
import sys

import pcbnew

import fix_route

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


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    print('edge vias removed:', remove_edge_vias(board))
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        print('island vias:', stitch_islands(board, layer))
        filler.Fill(board.Zones())
    board.Save(sys.argv[2])


if __name__ == '__main__':
    main()
