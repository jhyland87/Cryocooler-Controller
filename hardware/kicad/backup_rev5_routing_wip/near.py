"""near.py board NET REF radius: pads of REF and the net's tracks/vias within radius of them."""
import sys, math, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); net, ref, rad = sys.argv[2], sys.argv[3], float(sys.argv[4])
mm = pcbnew.ToMM
fp = b.FindFootprintByReference(ref)
c = fp.GetPosition(); print(ref, 'at', mm(c.x), mm(c.y), 'back' if fp.IsFlipped() else 'front')
for p in fp.Pads():
    s = p.GetSize(pcbnew.F_Cu) if hasattr(p, 'GetSize') else None
    print(' pad', p.GetNumber(), p.GetNetname(), round(mm(p.GetPosition().x), 2), round(mm(p.GetPosition().y), 2), mm(s.x), mm(s.y))
for t in b.GetTracks():
    if t.GetNetname() != net: continue
    a, e = t.GetStart(), t.GetEnd()
    if min(math.hypot(mm(q.x - c.x), mm(q.y - c.y)) for q in (a, e)) > rad: continue
    if t.GetClass() == 'PCB_VIA': print(' via', round(mm(a.x), 2), round(mm(a.y), 2), mm(t.GetWidth(pcbnew.F_Cu)))
    else: print(' trk', b.GetLayerName(t.GetLayer()), round(mm(a.x), 2), round(mm(a.y), 2), '->', round(mm(e.x), 2), round(mm(e.y), 2), 'w', mm(t.GetWidth()), 'L' if t.IsLocked() else '')
