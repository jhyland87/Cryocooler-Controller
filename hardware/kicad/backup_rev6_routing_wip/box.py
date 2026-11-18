"""Scratch: copper touching a box, one line per item. box.py board x0 y0 x1 y1"""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); x0, y0, x1, y1 = map(float, sys.argv[2:6]); mm = pcbnew.ToMM
def inside(x, y): return x0 <= x <= x1 and y0 <= y <= y1
def seg_hits(ax, ay, bx, by):
    for i in range(41):
        t = i / 40
        if inside(ax + (bx - ax) * t, ay + (by - ay) * t): return True
    return False
rows = []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition()
        if inside(mm(p.x), mm(p.y)): rows.append(('VIA', '', t.GetNetname(), f'{mm(p.x):.2f},{mm(p.y):.2f}', mm(t.GetWidth(pcbnew.F_Cu))))
    else:
        s, e = t.GetStart(), t.GetEnd()
        if seg_hits(mm(s.x), mm(s.y), mm(e.x), mm(e.y)):
            rows.append(('TRK', t.GetLayerName(), t.GetNetname(), f'{mm(s.x):.2f},{mm(s.y):.2f} -> {mm(e.x):.2f},{mm(e.y):.2f}', mm(t.GetWidth())))
for p in b.GetPads():
    box = p.GetBoundingBox()
    if mm(box.GetRight()) >= x0 and mm(box.GetLeft()) <= x1 and mm(box.GetBottom()) >= y0 and mm(box.GetTop()) <= y1:
        lay = ('F' if p.IsOnLayer(pcbnew.F_Cu) else '') + ('B' if p.IsOnLayer(pcbnew.B_Cu) else '')
        rows.append(('PAD', lay, p.GetNetname(), f'{p.GetParentFootprint().GetReference()}.{p.GetNumber()} box {mm(box.GetLeft()):.2f},{mm(box.GetTop()):.2f} {mm(box.GetRight()):.2f},{mm(box.GetBottom()):.2f}', ''))
for r in sorted(rows, key=lambda r: (r[1], r[0])): print(*r)
