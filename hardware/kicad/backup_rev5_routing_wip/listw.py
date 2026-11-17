import json, sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
out = [[b.GetLayerName(t.GetLayer()), round(mm(t.GetStart().x), 3), round(mm(t.GetStart().y), 3), round(mm(t.GetEnd().x), 3), round(mm(t.GetEnd().y), 3), mm(t.GetWidth())]
       for t in b.GetTracks() if t.GetNetname() == sys.argv[2] and t.GetClass() != 'PCB_VIA' and not t.IsLocked() and mm(t.GetWidth()) <= float(sys.argv[3]) + 1e-6]
json.dump(out, open(sys.argv[4], 'w'))
