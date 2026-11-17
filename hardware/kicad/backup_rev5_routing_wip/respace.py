"""Re-route each 0.1 mm-rule net at 0.15 mm clearance; keep it only if the board stays clean."""
import json, os, re, shutil, subprocess, sys
S = os.path.dirname(os.path.abspath(__file__)); P = S + '/pcb'
KPY = '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3'
KC = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
T = '/Users/justinhyland/Documents/PlatformIO/Projects/260216-211115-esp32dev/hardware/kicad/tools'
best, trial, loose = P + '/rev5_w18', P + '/rev5_w18t', P + '/rev5_w18c'

def drc(stem, save=True):
    cmd = [KC, 'pcb', 'drc', '--severity-all', '--format', 'json', '-o', stem + '.json']
    subprocess.run(cmd + (['--refill-zones', '--save-board'] if save else []) + [stem + '.kicad_pcb'], capture_output=True)
    d = json.load(open(stem + '.json'))
    return len(d['unconnected_items']), sum(v['severity'] == 'error' for v in d['violations']), d

def tight_by_net(stem):
    """Clearance hits per net when the 0.1 mm rules are taken away (KiCad stops at 499)."""
    for e in ('.kicad_pcb', '.kicad_pro'):
        shutil.copy(stem + e, loose + e)
    rules = open(stem + '.kicad_dru').read()
    open(loose + '.kicad_dru', 'w').write(rules[:rules.index('(rule tight')])
    d = drc(loose, save=False)[2]
    hits = {}
    for v in d['violations']:
        if v['type'] == 'clearance':
            for i in v['items']:
                m = re.search(r'\[(.*?)\]', i['description'])
                if m: hits[m.group(1)] = hits.get(m.group(1), 0) + 1
    return sum(v['type'] == 'clearance' for v in d['violations']), hits

if not os.path.exists(best + '.kicad_pcb'):
    for e in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
        shutil.copy(P + '/rev5_w17' + e, best + e)
done = set(open(P + '/respace_done.txt').read().split('\n')) if os.path.exists(P + '/respace_done.txt') else set()
total, hits = tight_by_net(best)
print('start tight spots', total, flush=True)
skip = ('GND', '+3V3', '+12V', 'ISO_GND')
for net in sorted((n for n in hits if n not in skip and n not in done), key=lambda n: -hits[n]):
    for e in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
        shutil.copy(best + e, trial + e)
    subprocess.run([KPY, S + '/ripbox.py', trial + '.kicad_pcb', trial + '.kicad_pcb', net + ':0,0,200,200'], capture_output=True)
    for _ in range(2):
        drc(trial)
        subprocess.run([KPY, 'gridroute.py', trial + '.kicad_pcb', trial + '.json', trial + '.kicad_pcb', net], cwd=T,
                       capture_output=True, env={**os.environ, 'SKIP': 'GND', 'FINE': '1', 'CLEAR': '0.15'})
    opened, errors, _ = drc(trial)
    kept = opened == 0 and errors == 0
    if kept:
        for e in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
            shutil.copy(trial + e, best + e)
    open(P + '/respace_done.txt', 'a').write(net + '\n')
    print(net, hits[net], 'kept' if kept else 'no (%d open, %d errors)' % (opened, errors), flush=True)
print('end tight spots', tight_by_net(best)[0], flush=True)
print('FINISHED', flush=True)
