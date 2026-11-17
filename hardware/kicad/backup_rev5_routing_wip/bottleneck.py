"""Narrowest track on the widest path from a source part to every pad of a net.
Usage: bottleneck.py board NET SRCREF"""
import sys, heapq, collections, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); net, src = sys.argv[2], sys.argv[3]
BIG = 10 ** 9
items = [t for t in b.GetTracks() if t.GetNetname() == net]
pads = [p for p in b.GetPads() if p.GetNetname() == net]
def on(item, layer):
    return item.IsOnLayer(layer)
def ends(t):
    return [t.GetPosition()] if t.GetClass() == 'PCB_VIA' else [t.GetStart(), t.GetEnd()]
def width(t):
    return BIG if t.GetClass() == 'PCB_VIA' else t.GetWidth()
nodes = items + pads
adj = collections.defaultdict(set)
for i, t in enumerate(items):
    for j, o in enumerate(nodes):
        if i == j: continue
        layers = [l for l in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if on(t, l) and on(o, l)]
        if layers and any(o.HitTest(q, int((t.GetWidth(pcbnew.F_Cu) if t.GetClass() == 'PCB_VIA' else t.GetWidth()) * 0.45)) for q in ends(t)):
            adj[i].add(j); adj[j].add(i)
best = {}
heap = [(-BIG, k) for k, n in enumerate(nodes) if k >= len(items) and n.GetParentFootprint().GetReference() == src]
while heap:
    w, n = heapq.heappop(heap)
    if n in best: continue
    best[n] = -w
    for m in adj[n]:
        if m not in best:
            heapq.heappush(heap, (-min(-w, width(nodes[m]) if m < len(items) else BIG), m))
out = collections.defaultdict(list)
for k in range(len(items), len(nodes)):
    p = nodes[k]
    name = p.GetParentFootprint().GetReference() + '.' + p.GetNumber()
    out['none' if k not in best else 'direct' if best[k] >= BIG else round(pcbnew.ToMM(int(best[k])), 2)].append(name)
for w, names in sorted(out.items(), key=str): print(w, ' '.join(sorted(names)))
