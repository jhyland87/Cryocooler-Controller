"""Removes dangling tracks and vias until none is left.
prune_all.py board [x0,y0,x1,y1 ...]   with boxes, only items wholly inside one go"""
import sys, pcbnew
path = sys.argv[1]
boxes = [tuple(float(v) for v in arg.split(',')) for arg in sys.argv[2:]]
board = pcbnew.LoadBoard(path); keep = []; total = 0
def inside(item):
    if not boxes:
        return True
    points = [item.GetPosition()] if item.Type() == pcbnew.PCB_VIA_T else [item.GetStart(), item.GetEnd()]
    return any(all(x0 <= p.x / 1e6 <= x1 and y0 <= p.y / 1e6 <= y1 for p in points) for x0, y0, x1, y1 in boxes)
for round_number in range(300):
    board.BuildConnectivity(); conn = board.GetConnectivity()
    gone = [item for item in board.GetTracks() if inside(item) and conn.TestTrackEndpointDangling(item, True)]
    if not gone: break
    for item in gone: keep.append(item); board.Remove(item)
    total += len(gone)
print('rounds', round_number, 'removed', total)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(path)
