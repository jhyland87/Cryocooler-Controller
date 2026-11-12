"""Dumps silk texts, silk graphics, mask texts and pads of one side in a window: silk_dump.py board out.json F|B x0 y0 x1 y1"""
import sys, json, pcbnew
b=pcbnew.LoadBoard(sys.argv[1]); side=sys.argv[3]; x0,y0,x1,y1=map(float,sys.argv[4:8])
silk=pcbnew.F_SilkS if side=='F' else pcbnew.B_SilkS; mask=pcbnew.F_Mask if side=='F' else pcbnew.B_Mask; cu=pcbnew.F_Cu if side=='F' else pcbnew.B_Cu
def box(bb): return [bb.GetLeft()/1e6,bb.GetTop()/1e6,bb.GetRight()/1e6,bb.GetBottom()/1e6]
def hit(r): return not (r[2]<x0 or r[0]>x1 or r[3]<y0 or r[1]>y1)
out={'win':[x0,y0,x1,y1],'texts':[],'lines':[],'pads':[],'side':side}
def add_text(t, kind):
    if not t.IsVisible(): return
    r=box(t.GetBoundingBox())
    if t.GetLayer() in (silk,mask) and hit(r): out['texts'].append([r, t.GetText(), kind+('M' if t.GetLayer()==mask else '')])
for d in b.GetDrawings():
    if d.Type()==pcbnew.PCB_TEXT_T: add_text(d,'T')
    elif d.GetLayer()==silk and hasattr(d,'GetStart'):
        r=box(d.GetBoundingBox())
        if hit(r): out['lines'].append([d.GetStart().x/1e6,d.GetStart().y/1e6,d.GetEnd().x/1e6,d.GetEnd().y/1e6,'board'])
for fp in b.GetFootprints():
    for f in fp.GetFields(): add_text(f,'F')
    for g in fp.GraphicalItems():
        if g.Type()==pcbnew.PCB_TEXT_T: add_text(g,'G')
        elif g.GetLayer()==silk and hasattr(g,'GetStart'):
            r=box(g.GetBoundingBox())
            if hit(r): out['lines'].append([g.GetStart().x/1e6,g.GetStart().y/1e6,g.GetEnd().x/1e6,g.GetEnd().y/1e6,fp.GetReference()])
    for p in fp.Pads():
        if p.IsOnLayer(cu):
            r=box(p.GetBoundingBox())
            if hit(r): out['pads'].append([r, fp.GetReference()+'.'+p.GetNumber()])
json.dump(out,open(sys.argv[2],'w'))
