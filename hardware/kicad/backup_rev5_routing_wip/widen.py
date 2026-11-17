"""Widens thin +12V tracks in place; a segment keeps the new width only if it is in no clearance hit at 0.15 mm."""
import json, os, re, shutil, subprocess
S = os.path.dirname(os.path.abspath(__file__)); P = S + '/pcb'
KPY = '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3'
KC = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
src, out, loose = P + '/rev5_w20', P + '/rev5_w21', P + '/rev5_w21c'
NET = '+12V'

def drc(stem):
    subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all', '--all-track-errors',
                    '--format', 'json', '-o', stem + '.json', stem + '.kicad_pcb'], capture_output=True)
    return json.load(open(stem + '.json'))

def hit_points(d):
    """End points named by any violation that involves a +12V track."""
    pts = set()
    for v in d['violations']:
        for i in v['items']:
            if i['description'].startswith('Track') and '[%s]' % NET in i['description']:
                pts.add((round(i['pos']['x'], 2), round(i['pos']['y'], 2)))
    return pts

for e in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
    shutil.copy(src + e, out + e)
shutil.copy(src + '.kicad_pro', loose + '.kicad_pro')
rules = open(src + '.kicad_dru').read()
open(loose + '.kicad_dru', 'w').write(rules[:rules.index('(rule tight')])
subprocess.run([KPY, S + '/listw.py', out + '.kicad_pcb', NET, '0.2', P + '/thin.json'], capture_output=True)
segs = json.load(open(P + '/thin.json'))
orig = {tuple(s[:5]): s[5] for s in segs}
shutil.copy(out + '.kicad_pcb', loose + '.kicad_pcb')
base = hit_points(drc(loose))
width = dict(orig)
for target in (0.3, 0.25, 0.2):
    trying = {k for k in width if width[k] == orig[k] and orig[k] < target}
    while trying:
        spec = [list(k) + [target if k in trying else width[k]] for k in width]
        json.dump(spec, open(P + '/spec.json', 'w'))
        subprocess.run([KPY, S + '/setw.py', out + '.kicad_pcb', loose + '.kicad_pcb', NET, P + '/spec.json'], capture_output=True)
        pts = hit_points(drc(loose))
        bad = {k for k in trying if (round(k[1], 2), round(k[2], 2)) in pts or (round(k[3], 2), round(k[4], 2)) in pts}
        print(target, 'trying', len(trying), 'bad', len(bad), flush=True)
        if not bad:
            for k in trying:
                width[k] = target
            break
        trying -= bad
json.dump([list(k) + [w] for k, w in width.items()], open(P + '/spec.json', 'w'))
subprocess.run([KPY, S + '/setw.py', out + '.kicad_pcb', out + '.kicad_pcb', NET, P + '/spec.json'], capture_output=True)
d = drc(out)
print('widened', sum(width[k] > orig[k] for k in width), 'of', len(width), '| open', len(d['unconnected_items']),
      'errors', sum(v['severity'] == 'error' for v in d['violations']), flush=True)
print('FINISHED', flush=True)
