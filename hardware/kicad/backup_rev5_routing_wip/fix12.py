"""Pulls the thin +12V track at the IO4_PULLUP via onto the 0.3 mm +12V track beside it."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
MOVES = {(65.7, 61.25): (65.8, 61.15), (66.65, 61.25): (66.65, 61.15),
         (66.7, 61.2): (66.7, 61.15), (67.1, 61.2): (67.05, 61.15)}
n = 0
for t in b.GetTracks():
    if t.GetNetname() != '+12V' or t.GetClass() == 'PCB_VIA' or t.GetLayer() != pcbnew.F_Cu or pcbnew.ToMM(t.GetWidth()) > 0.16:
        continue
    for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        k = (round(pcbnew.ToMM(get().x), 2), round(pcbnew.ToMM(get().y), 2))
        if k in MOVES:
            put(pcbnew.VECTOR2I(pcbnew.FromMM(MOVES[k][0]), pcbnew.FromMM(MOVES[k][1]))); n += 1
b.Save(sys.argv[2]); print('moved', n)
