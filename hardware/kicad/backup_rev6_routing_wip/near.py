"""Scratch: lists copper within r mm of a point. near.py board x y r"""
import sys, math, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); x, y, r = map(float, sys.argv[2:5])
mm = pcbnew.ToMM
def d(px, py): return math.hypot(mm(px) - x, mm(py) - y)
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition()
        if d(p.x, p.y) < r: print('VIA', t.GetNetname(), round(mm(p.x),2), round(mm(p.y),2), mm(t.GetWidth(pcbnew.F_Cu)), 'locked' if t.IsLocked() else '')
    else:
        s, e = t.GetStart(), t.GetEnd()
        if min(d(s.x, s.y), d(e.x, e.y)) < r:
            print('TRK', t.GetLayerName(), t.GetNetname(), (round(mm(s.x),2), round(mm(s.y),2)), (round(mm(e.x),2), round(mm(e.y),2)), mm(t.GetWidth()))
for p in b.GetPads():
    q = p.GetPosition()
    if d(q.x, q.y) < r: print('PAD', p.GetParentFootprint().GetReference(), p.GetNumber(), p.GetNetname(), round(mm(q.x),2), round(mm(q.y),2), round(mm(p.GetSizeX()),2), round(mm(p.GetSizeY()),2), 'F' if p.IsOnLayer(pcbnew.F_Cu) else '', 'B' if p.IsOnLayer(pcbnew.B_Cu) else '')
