"""Re-routes, at 0.15 mm, the track near each via/SPI/SET spot that sits under 0.15 mm.
Keeps a trial only if the board stays connected and clean and the spot count falls."""
import json, os, re, shutil, subprocess
S = os.path.dirname(os.path.abspath(__file__)); P = S + '/pcb'
KPY = '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3'
KC = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
T = '/Users/justinhyland/Documents/PlatformIO/Projects/260216-211115-esp32dev/hardware/kicad/tools'
EXTS = ('.kicad_pcb', '.kicad_pro', '.kicad_dru')
best, trial, loose = P + '/rev5_w19', P + '/rev5_w19t', P + '/rev5_w19c'
SENSITIVE = re.compile(r'SET|SPI_|REFP')

def copy(a, b):
    for e in EXTS:
        shutil.copy(a + e, b + e)

def drc(stem):
    subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all', '--all-track-errors', '--format', 'json',
                    '-o', stem + '.json', stem + '.kicad_pcb'], capture_output=True)
    d = json.load(open(stem + '.json'))
    return len(d['unconnected_items']), sum(v['severity'] == 'error' for v in d['violations']), d

def spots(stem):
    """(all, target) spots under 0.15 mm with the tight rules removed."""
    for e in EXTS[:2]:
        shutil.copy(stem + e, loose + e)
    rules = open(stem + '.kicad_dru').read()
    open(loose + '.kicad_dru', 'w').write(rules[:rules.index('(rule tight')])
    found = []
    for v in drc(loose)[2]['violations']:
        if v['type'] != 'clearance':
            continue
        items = [(i['description'].split()[0], (re.search(r'\[(.*?)\]', i['description']) or [0, '?'])[1],
                  i['pos']['x'], i['pos']['y']) for i in v['items']]
        found.append(items)
    target = [s for s in found if any(i[0] == 'Via' or SENSITIVE.search(i[1]) for i in s)]
    return found, target

def clusters(target):
    """{(net to rip, 3 mm cell): box} from the track items of each spot."""
    out = {}
    for s in target:
        xs, ys = [i[2] for i in s], [i[3] for i in s]
        for kind, net, _, _ in s:
            if kind != 'Track' or net in ('GND', '+3V3', '+12V'):
                continue
            key = (net, round(xs[0] / 3), round(ys[0] / 3))
            b = out.setdefault(key, [min(xs), min(ys), max(xs), max(ys)])
            b[:] = [min(b[0], *xs), min(b[1], *ys), max(b[2], *xs), max(b[3], *ys)]
    return out

def attempt(net, box):
    copy(best, trial)
    subprocess.run([KPY, S + '/ripbox.py', trial + '.kicad_pcb', trial + '.kicad_pcb',
                    '%s:%.2f,%.2f,%.2f,%.2f' % (net, *box)], capture_output=True)
    for _ in range(2):
        drc(trial)
        subprocess.run([KPY, 'gridroute.py', trial + '.kicad_pcb', trial + '.json', trial + '.kicad_pcb', net], cwd=T,
                       capture_output=True, env={**os.environ, 'SKIP': 'GND', 'FINE': '1', 'CLEAR': '0.15'})
    for _ in range(3):
        drc(trial)
        subprocess.run([KPY, 'prune_flagged.py', trial + '.kicad_pcb', trial + '.json'], cwd=T, capture_output=True)
    return drc(trial)[:2]

if not os.path.exists(best + '.kicad_pcb'):
    copy(P + '/rev5_w18', best)
found, target = spots(best)
print('start', len(found), 'spots,', len(target), 'via/SPI/SET', flush=True)
tried = {('Net-(U22-SET)', 26, 17), ('Net-(U14-AIN0/REFP1)', 5, 10), ('Net-(U14-AIN0/REFP1)', 7, 13), ('SPI_MOSI', 6, 14)}
while True:
    todo = [(k, b) for k, b in clusters(target).items() if k not in tried]
    if not todo:
        break
    key, b = todo[0]
    tried.add(key)
    for margin in (1.0, 2.5, 200):   # local, wider, whole net
        box = (b[0] - margin, b[1] - margin, b[2] + margin, b[3] + margin)
        opened, errors = attempt(key[0], box)
        if opened or errors:
            print(key, margin, 'no (%d open, %d errors)' % (opened, errors), flush=True)
            continue
        f2, t2 = spots(trial)
        if len(t2) < len(target) and len(f2) <= len(found):
            copy(trial, best)
            found, target = f2, t2
            print(key, margin, 'kept ->', len(found), len(target), flush=True)
            break
        print(key, margin, 'no gain (%d, %d)' % (len(f2), len(t2)), flush=True)
print('end', len(found), 'spots,', len(target), 'via/SPI/SET', flush=True)
print('FINISHED', flush=True)
