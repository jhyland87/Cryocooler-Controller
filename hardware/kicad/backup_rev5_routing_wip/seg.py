import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
x0, y0, x1, y1 = map(float, sys.argv[2].split(','))
for t in b.GetTracks():
    a, e = t.GetStart(), t.GetEnd()
    if any(x0 <= mm(p.x) <= x1 and y0 <= mm(p.y) <= y1 for p in (a, e)):
        print(t.GetClass()[4:], t.GetNetname(), b.GetLayerName(t.GetLayer()), round(mm(a.x),2), round(mm(a.y),2), round(mm(e.x),2), round(mm(e.y),2), mm(t.GetWidth(pcbnew.F_Cu)) if t.GetClass()=='PCB_VIA' else mm(t.GetWidth()))
for p in b.GetPads():
    q = p.GetPosition()
    if x0 <= mm(q.x) <= x1 and y0 <= mm(q.y) <= y1:
        print('PAD', p.GetParentFootprint().GetReference(), p.GetNumber(), p.GetNetname(), round(mm(q.x),2), round(mm(q.y),2), mm(p.GetSize(pcbnew.F_Cu).x), mm(p.GetSize(pcbnew.F_Cu).y), 'B' if p.IsOnLayer(pcbnew.B_Cu) else 'F')
