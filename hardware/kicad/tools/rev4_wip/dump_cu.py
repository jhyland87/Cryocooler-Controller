"""Dumps pads, tracks, vias, courtyards of a board window to JSON: dump_cu.py board out.json x0 y0 x1 y1"""
import sys, json, pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); x0,y0,x1,y1=map(float,sys.argv[3:7])
def inside(x,y,m=3): return x0-m<=x<=x1+m and y0-m<=y<=y1+m
out={'tracks':[], 'vias':[], 'pads':[], 'parts':[], 'win':[x0,y0,x1,y1]}
for t in b.GetTracks():
    if t.Type()==pcbnew.PCB_VIA_T:
        p=t.GetPosition()
        if inside(p.x/1e6,p.y/1e6): out['vias'].append([p.x/1e6,p.y/1e6,t.GetWidth(pcbnew.F_Cu)/1e6,t.GetNetname()])
        continue
    s,e=t.GetStart(),t.GetEnd()
    if inside(s.x/1e6,s.y/1e6) or inside(e.x/1e6,e.y/1e6):
        out['tracks'].append([s.x/1e6,s.y/1e6,e.x/1e6,e.y/1e6,t.GetWidth()/1e6,b.GetLayerName(t.GetLayer()),t.GetNetname()])
for fp in b.GetFootprints():
    bb=fp.GetBoundingBox(False)
    if not (bb.GetRight()/1e6<x0 or bb.GetLeft()/1e6>x1 or bb.GetBottom()/1e6<y0 or bb.GetTop()/1e6>y1):
        out['parts'].append([fp.GetReference(), 'B' if fp.IsFlipped() else 'F', fp.GetPosition().x/1e6, fp.GetPosition().y/1e6])
        for p in fp.Pads():
            r=p.GetBoundingBox()
            layer='T' if p.GetDrillSize().x>0 else ('B' if p.IsOnLayer(pcbnew.B_Cu) else 'F')
            out['pads'].append([r.GetLeft()/1e6,r.GetTop()/1e6,r.GetRight()/1e6,r.GetBottom()/1e6,layer,p.GetNetname(),fp.GetReference()+'.'+p.GetNumber()])
json.dump(out,open(sys.argv[2],'w'))
