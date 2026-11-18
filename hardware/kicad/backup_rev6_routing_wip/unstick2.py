"""Scratch: clears every net's unlocked copper round one point (KEEP nets stay), routes the stuck net first,
then everything else, re-ties the planes, and keeps the result only if the open count falls with no errors.
Usage: unstick2.py stem tools_dir NET x,y radius"""
import json, math, os, re, shutil, subprocess, sys
KPY = '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3'
KC = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
stem, tools, stuck, spot, radius = sys.argv[1:6]
KEEP = set(os.environ.get('KEEP', 'ISO_GND,VIN,VSW,+12V').split(','))
ENV = {**os.environ, 'FINE': '1', 'CLEAR': '0.15', 'VIA_TRACK_CLEAR': '0.15'}

def drc(s):
    subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-error', '--all-track-errors',
                    '--format', 'json', '-o', s + '_drc.json', s + '.kicad_pcb'], capture_output=True)
    d = json.load(open(s + '_drc.json'))
    return len(d['unconnected_items']), len(d['violations']), d

def grid(s, nets=None, skip='GND'):
    cmd = [KPY, 'gridroute.py', s + '.kicad_pcb', s + '_drc.json']
    if nets:
        cmd += [s + '.kicad_pcb', nets]
    subprocess.run(cmd, cwd=tools, capture_output=True, env={**ENV, 'SKIP': skip})

RIP = r'''
import sys, math, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); x, y = (pcbnew.FromMM(float(v)) for v in sys.argv[3].split(',')); r = pcbnew.FromMM(float(sys.argv[4]))
keep = set(sys.argv[5].split(',')); held = []
for t in list(b.GetTracks()):
    if t.GetNetname() in keep or t.IsLocked(): continue
    pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    if any(math.hypot(p.x - x, p.y - y) < r for p in pts):
        held.append(t); b.Remove(t)
b.Save(sys.argv[2]); print(len(held))
'''
count, errors, _ = drc(stem)
trial = stem + '_t'
for ext in ('.kicad_pro', '.kicad_dru'):
    shutil.copy(stem + ext, trial + ext)
out = subprocess.run([KPY, '-c', RIP, stem + '.kicad_pcb', trial + '.kicad_pcb', spot, radius, ','.join(KEEP)],
                     capture_output=True, text=True).stdout.strip().splitlines()[-1]
drc(trial); grid(trial, stuck)
for _ in range(2):
    drc(trial); grid(trial)
    drc(trial); subprocess.run([KPY, 'plane_ties.py', trial + '.kicad_pcb', trial + '_drc.json', 'GND,+3V3'], cwd=tools, capture_output=True)
new_count, new_errors, report = drc(trial)
nets = sorted({re.search(r'\[(.*?)\]', e['items'][0]['description']).group(1) for e in report['unconnected_items']})
print(f'{stuck} r={radius}: {count}/{errors} -> {new_count}/{new_errors} open nets {nets}', flush=True)
if new_count < count and new_errors <= errors:
    for ext in ('.kicad_pcb', '_drc.json'):
        shutil.copy(trial + ext, stem + ext)
    print('kept')
