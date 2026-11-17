"""nudge.py in out NET x0,y0,x1,y1 dx dy LAYER: shifts the net's track ends inside the box on one layer."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); net = sys.argv[3]
x0, y0, x1, y1 = (pcbnew.FromMM(float(v)) for v in sys.argv[4].split(','))
d = pcbnew.VECTOR2I(pcbnew.FromMM(float(sys.argv[5])), pcbnew.FromMM(float(sys.argv[6])))
n = 0
for t in b.GetTracks():
    if t.GetNetname() != net or t.GetClass() == 'PCB_VIA' or b.GetLayerName(t.GetLayer()) != sys.argv[7]:
        continue
    for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        p = get()
        if x0 <= p.x <= x1 and y0 <= p.y <= y1:
            put(p + d); n += 1
b.Save(sys.argv[2]); print('moved', n)
