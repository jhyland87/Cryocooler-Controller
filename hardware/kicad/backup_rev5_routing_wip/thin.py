"""thin.py board NET maxwidth: chains of the net's tracks at or under maxwidth, with length and extent."""
import sys, collections, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
ts = [t for t in b.GetTracks() if t.GetNetname() == sys.argv[2] and t.GetClass() != 'PCB_VIA' and mm(t.GetWidth()) <= float(sys.argv[3]) + 1e-6]
vias = [t for t in b.GetTracks() if t.GetNetname() == sys.argv[2] and t.GetClass() == 'PCB_VIA']
parent = list(range(len(ts)))
def find(i):
    while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
    return i
ends = collections.defaultdict(list)
for i, t in enumerate(ts):
    for p in (t.GetStart(), t.GetEnd()):
        ends[(p.x, p.y)].append(i)   # layer ignored: vias join layers at the same point
for g in ends.values():
    for i in g[1:]: parent[find(i)] = find(g[0])
groups = collections.defaultdict(list)
for i, t in enumerate(ts): groups[find(i)].append(t)
for g in sorted(groups.values(), key=lambda g: -sum(t.GetLength() for t in g)):
    xs = [mm(p.x) for t in g for p in (t.GetStart(), t.GetEnd())]; ys = [mm(p.y) for t in g for p in (t.GetStart(), t.GetEnd())]
    nv = sum(1 for v in vias if (v.GetPosition().x, v.GetPosition().y) in {(p.x, p.y) for t in g for p in (t.GetStart(), t.GetEnd())})
    print('%.1f mm, w %s, x %.1f-%.1f y %.1f-%.1f, %d vias, layers %s' % (mm(sum(t.GetLength() for t in g)), sorted({mm(t.GetWidth()) for t in g}), min(xs), max(xs), min(ys), max(ys), nv, sorted({b.GetLayerName(t.GetLayer()) for t in g})))
