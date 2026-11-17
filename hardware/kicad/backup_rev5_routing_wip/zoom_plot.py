import json, sys
from PIL import Image, ImageDraw
d = json.load(open(sys.argv[1])); cx, cy, half = map(float, sys.argv[2:5]); out = sys.argv[5]; hl = sys.argv[6] if len(sys.argv) > 6 else ''
W = 900; k = W / (2 * half)
def P(x, y): return ((x - cx + half) * k, (y - cy + half) * k)
im = Image.new('RGB', (W, W), 'white'); dr = ImageDraw.Draw(im, 'RGBA')
col = {'F.Cu': (220, 40, 40, 150), 'B.Cu': (40, 80, 220, 150), 'In2.Cu': (40, 170, 60, 150), 'In1.Cu': (150, 150, 0, 150)}
for l, t, r, b, side, pth, ref, num, net in d['pads']:
    if r < cx - half or l > cx + half or b < cy - half or t > cy + half: continue
    c = (255, 150, 150, 200) if side == 'F' else (150, 170, 255, 200)
    if pth: c = (200, 160, 60, 220)
    dr.rectangle([P(l, t), P(r, b)], fill=c, outline=(0, 0, 0, 255) if net != hl else (255, 0, 255, 255), width=1 if net != hl else 5)
    dr.text(P(l, t), f'{ref}.{num}', fill=(0, 0, 0, 255))
for x1, y1, x2, y2, w, layer, net in d['tracks']:
    if max(x1, x2) < cx - half or min(x1, x2) > cx + half or max(y1, y2) < cy - half or min(y1, y2) > cy + half: continue
    c = col.get(layer, (0, 0, 0, 150))
    if net == hl: c = (255, 0, 255, 255)
    dr.line([P(x1, y1), P(x2, y2)], fill=c, width=max(1, int(w * k)))
for x, y, w, net in d['vias']:
    if abs(x - cx) > half or abs(y - cy) > half: continue
    r = w / 2 * k; px, py = P(x, y)
    dr.ellipse([px - r, py - r, px + r, py + r], fill=(90, 90, 90, 220) if net != hl else (255, 0, 255, 255), outline=(0, 0, 0, 255))
    dr.text((px - r, py - r), net[-6:], fill=(255, 255, 255, 255))
im.save(out)
