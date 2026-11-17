"""Try every routing order of the ripped signals; keep boards with no open signal."""
import itertools, json, os, shutil, subprocess, sys
S = os.path.dirname(os.path.abspath(__file__)); P = S + '/pcb'; H = P + '/h'
KPY = '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3'
KC = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
T = '/Users/justinhyland/Documents/PlatformIO/Projects/260216-211115-esp32dev/hardware/kicad/tools'
NETS = ['/IO Output Drivers/IO4_DRV', 'IO4_OUT_EN', 'IO1_PULLUP', 'IO1_SENS_EN']
BOX = '57,62,66,72'

def drc(stem):
    subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all', '--format', 'json',
                    '-o', stem + '.json', stem + '.kicad_pcb'], capture_output=True)
    d = json.load(open(stem + '.json'))
    nets = [u['items'][0]['description'].split('[')[1].split(']')[0] for u in d['unconnected_items']]
    errs = sum(1 for v in d['violations'] if v['severity'] == 'error')
    return nets, errs

def route(stem, nets, env):
    subprocess.run([KPY, 'gridroute.py', stem + '.kicad_pcb', stem + '.json', stem + '.kicad_pcb', ','.join(nets)],
                   cwd=T, env={**os.environ, 'SKIP': 'GND', **env}, capture_output=True)

base = H + '/p0'
for e in ('kicad_pro', 'kicad_dru'):
    shutil.copy(P + '/rev5_w13.' + e, base + '.' + e)
subprocess.run([KPY, S + '/ripbox.py', P + '/rev5_w13.kicad_pcb', base + '.kicad_pcb', '+12V:58,66,66,72']
               + [n + ':' + BOX for n in NETS[1:]], capture_output=True)
for k, order in enumerate(itertools.permutations(NETS)):
    stem = H + '/p%d' % (k + 1)
    for e in ('kicad_pcb', 'kicad_pro', 'kicad_dru'):
        shutil.copy(base + '.' + e, stem + '.' + e)
    for _ in range(2):
        for n in order:
            drc(stem); route(stem, [n], {'FINE': '1', 'CLEAR': '0.1'})
    nets, errs = drc(stem)
    sig = [n for n in nets if n not in ('+12V', '+3V3')]
    if not sig:
        for w in ('0.3', '0.2', '0.2'):
            route(stem, ['+12V', '+3V3'], {'FINE': '1', 'CLEAR': '0.15', 'WIDTH': w}); nets, errs = drc(stem)
    print(k + 1, [n[-10:] for n in order], 'open', nets, 'errors', errs, flush=True)
    if not nets and errs <= 52:
        print('DONE', stem, flush=True); break
