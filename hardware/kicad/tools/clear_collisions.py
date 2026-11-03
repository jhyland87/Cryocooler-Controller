"""clear_collisions.py in out REF,REF — deletes other-net copper that collides with the
re-placed stage's pads or its locked power copper, then prunes."""
import sys
import pcbnew
sys.path.insert(0, 'tools')
import ripup
STAGE = sys.argv[3].split(',')
board = pcbnew.LoadBoard(sys.argv[1])
nm = lambda v: int(round(v * 1e6))
obstacles = []
for ref in STAGE:
    for pad in board.FindFootprintByReference(ref).Pads():
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if pad.IsOnLayer(layer):
                obstacles.append((pad.GetNetname(), layer, pad))
for item in board.GetTracks():
    if item.IsLocked():
        for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            if item.IsOnLayer(layer):
                obstacles.append((item.GetNetname(), layer, item))
doomed, nets = [], set()
for item in board.GetTracks():
    if item.IsLocked():
        continue
    for net, layer, other in obstacles:
        if net == item.GetNetname() or not item.IsOnLayer(layer):
            continue
        mine = pcbnew.SHAPE_POLY_SET()
        item.TransformShapeToPolygon(mine, layer, nm(0.16), nm(0.005), pcbnew.ERROR_OUTSIDE)
        theirs = pcbnew.SHAPE_POLY_SET()
        other.TransformShapeToPolygon(theirs, layer, 0, nm(0.005), pcbnew.ERROR_OUTSIDE)
        mine.BooleanIntersection(theirs)
        if mine.OutlineCount():
            doomed.append(item)
            nets.add(item.GetNetname())
            break
print('cleared', len(doomed), sorted(nets))
for item in doomed:
    board.Delete(item)
ripup.prune(board, nets)
board.Save(sys.argv[2])
