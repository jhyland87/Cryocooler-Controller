"""setw.py in out NET spec.json: sets track widths; spec = [[layer, x0, y0, x1, y1, width_mm], ...]"""
import json, sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
spec = {tuple(s[:5]): s[5] for s in json.load(open(sys.argv[4]))}
for t in b.GetTracks():
    if t.GetNetname() != sys.argv[3] or t.GetClass() == 'PCB_VIA':
        continue
    k = (b.GetLayerName(t.GetLayer()), round(mm(t.GetStart().x), 3), round(mm(t.GetStart().y), 3), round(mm(t.GetEnd().x), 3), round(mm(t.GetEnd().y), 3))
    if k in spec:
        t.SetWidth(pcbnew.FromMM(spec[k]))
b.Save(sys.argv[2])
