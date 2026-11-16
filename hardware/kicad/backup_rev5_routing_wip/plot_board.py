import json, sys, importlib.util
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, sys.argv[4])
parts = json.load(open(sys.argv[1])); meta = json.load(open(sys.argv[2]))
SC = 14; W, H = 120, 100; M = 30
SECTIONS = {
 'POWER INPUT': [(0,0,22.3,22.4),(22.3,14.5,54,34),(19,22.4,44,47.5),(108,78,120,93)], 'WATER COOLING & RELAY': [(22.3,0,54,14.5)],
 'MCU & USB': [(54,0,92,34),(92,0,100,22)], 'EXPANSION': [(100,0,120,18),(90,22,104,42)],
 'AMP CONTROL': [(100,18,120,39.5)], 'PRECISION PORTS': [(100,39.5,120,65)], 'AMBIENT': [(108,65,120,78)],
 'CRYO SENSORS': [(0,22.4,19,47.5)], 'AMP CURRENT (ISOLATED)': [(0,47.5,44,86.7)],
 'LOGIC RAILS': [(44,34,58,57)], 'RAILS +-15V': [(58,34,82,57)], 'SIGNAL GENERATOR': [(82,34,92,57),(92,37,100,57)],
 'DISPLAY': [(0,86.7,44,100)], 'UNIVERSAL I/O': [(44,57,100,72)], 'I/O CHANNELS 1-4 (pairs)': [(44,70,102,100)],
}
import colorsys
sheets = sorted({m['sheet'] for m in meta.values()})
col = {s: tuple(int(c*255) for c in colorsys.hsv_to_rgb(i/len(sheets), 0.45, 0.95)) for i, s in enumerate(sheets)}
font = ImageFont.load_default()
for side in ('top', 'bottom'):
    im = Image.new('RGB', (W*SC+2*M, H*SC+2*M), 'white'); d = ImageDraw.Draw(im)
    def P(x, y):
        if side == 'bottom': x = W - x   # seen from the back
        return (M + x*SC, M + y*SC)
    def R(b, **k):
        a, c = P(b[0], b[1]), P(b[2], b[3])
        d.rectangle([min(a[0],c[0]), min(a[1],c[1]), max(a[0],c[0]), max(a[1],c[1])], **k)
    R((0,0,W,H), outline='black', width=3)
    R((74.5,0,93.5,6), fill=(200,200,200))
    for name, rects in SECTIONS.items():
        for r in rects: R(r, outline=(150,150,150), width=1)
        r = rects[0]; a = P(r[0] if side=='top' else r[2], r[1]); d.text((a[0]+4, a[1]+3), name, fill=(110,110,110), font=font)
    for hx, hy in ((4.2,4.2),(115.8,4.2),(4.2,95.8),(115.8,95.8)):
        c = P(hx, hy); d.ellipse([c[0]-3*SC, c[1]-3*SC, c[0]+3*SC, c[1]+3*SC], outline='black')
    for p in parts:
        if p['side'] != side: continue
        m = meta.get(p['ref'])
        R(p['box'], fill=col[m['sheet']] if m else (220,220,220), outline=(60,60,60))
        b = p['box']
        if (b[2]-b[0]) * (b[3]-b[1]) > 9:
            a = P((b[0]+b[2])/2, (b[1]+b[3])/2); d.text((a[0]-3*len(p['ref']), a[1]-5), p['ref'], fill='black', font=font)
    d.text((M, 6), f'Rev 5 placement, simplified I/O, {side} side' + (' (seen from the back)' if side=='bottom' else ''), fill='black', font=font)
    im.save(f'{sys.argv[3]}_{side}.png')
