import sys, json
import pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
out = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if not ref: continue
    bottom = fp.IsFlipped()
    box = fp.GetCourtyard(pcbnew.B_CrtYd if bottom else pcbnew.F_CrtYd).BBox()
    if box.GetWidth() == 0: box = fp.GetBoundingBox(False)
    pos = fp.GetPosition()
    out.append(dict(ref=ref, side='bottom' if bottom else 'top', x=pos.x/1e6, y=pos.y/1e6, rot=fp.GetOrientationDegrees(),
        box=[box.GetLeft()/1e6, box.GetTop()/1e6, box.GetRight()/1e6, box.GetBottom()/1e6]))
json.dump(out, open(sys.argv[2], 'w'))
print(len(out))
