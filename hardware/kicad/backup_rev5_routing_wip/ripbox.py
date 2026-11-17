"""ripbox.py in out NET:x0,y0,x1,y1 ... : remove a net's unlocked tracks/vias inside a box."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); M = pcbnew.ToMM; gone = []
for spec in sys.argv[3:]:
    net, box = spec.rsplit(':', 1); x0, y0, x1, y1 = map(float, box.split(','))
    for t in list(b.GetTracks()):
        if t.GetNetname() != net or t.IsLocked(): continue
        pts = [t.GetStart(), t.GetEnd()]
        if any(x0 <= M(p.x) <= x1 and y0 <= M(p.y) <= y1 for p in pts):
            b.Remove(t); gone.append(t)
    print(net, len(gone))
b.Save(sys.argv[2])
