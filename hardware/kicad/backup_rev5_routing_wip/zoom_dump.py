import json, sys, pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
out = {'tracks': [], 'vias': [], 'pads': []}
for t in board.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition(); out['vias'].append([p.x/1e6, p.y/1e6, t.GetWidth(pcbnew.F_Cu)/1e6, t.GetNetname()])
    else:
        a, b = t.GetStart(), t.GetEnd()
        out['tracks'].append([a.x/1e6, a.y/1e6, b.x/1e6, b.y/1e6, t.GetWidth()/1e6, board.GetLayerName(t.GetLayer()), t.GetNetname()])
for f in board.GetFootprints():
    for p in f.Pads():
        b = p.GetBoundingBox()
        out['pads'].append([b.GetLeft()/1e6, b.GetTop()/1e6, b.GetRight()/1e6, b.GetBottom()/1e6, 'B' if f.IsFlipped() else 'F', p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH, f.GetReference(), p.GetNumber(), p.GetNetname()])
json.dump(out, open(sys.argv[2], 'w'))
