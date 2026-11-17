"""Greedy rip-up: one open signal at a time, keep the trial only if the open count falls."""
import json, os, re, shutil, subprocess, sys
S = os.path.dirname(os.path.abspath(__file__))
KPY = '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3'
KC = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
TOOLS = sys.argv[2]
best = sys.argv[1]                      # board stem, e.g. .../rev5_w4
POWER = ('GND', 'ISO_GND', '+3V3')

def drc(stem):
    subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all', '--format', 'json',
                    '-o', stem + '_drc.json', stem + '.kicad_pcb'], capture_output=True)
    d = json.load(open(stem + '_drc.json'))
    errors = sum(1 for v in d['violations'] if v['severity'] == 'error' and v['type'] != 'track_width')
    return len(d['unconnected_items']), errors, d

def net_of(entry):
    return re.search(r'\[(.*?)\]', entry['items'][0]['description']).group(1)

def grid(stem, nets=None, env=None):
    cmd = [KPY, 'gridroute.py', stem + '.kicad_pcb', stem + '_drc.json']
    if nets:
        cmd += [stem + '.kicad_pcb', nets]
    subprocess.run(cmd, cwd=TOOLS, capture_output=True, env={**os.environ, 'SKIP': 'GND,ISO_GND,+3V3', **(env or {})})

count, errors, report = drc(best)
print('start', count, errors, flush=True)
tried = set()
while True:
    todo = [(i, e) for i, e in enumerate(report['unconnected_items'])
            if net_of(e) not in POWER and (net_of(e), e['items'][0]['description']) not in tried]
    if not todo:
        break
    index, entry = todo[0]
    tried.add((net_of(entry), entry['items'][0]['description']))
    for radius in ('1.2', '1.8'):
        trial = best + '_t'
        for ext in ('.kicad_pro', '.kicad_dru'):
            shutil.copy(best + ext, trial + ext)
        net = subprocess.run([KPY, os.path.join(S, 'ripone.py'), best + '.kicad_pcb', best + '_drc.json',
                              trial + '.kicad_pcb', str(index), radius], capture_output=True, text=True).stdout.strip().splitlines()[0]
        net, _, ripped = net.partition('|')
        drc(trial)
        grid(trial, net, {'FINE': '1', 'CLEAR': '0.1', 'WIDTH': '0.15'})
        drc(trial)
        if ripped:
            cond = ' || '.join("A.NetName == '%s'" % n for n in ripped.split(','))
            with open(trial + '.kicad_dru', 'a') as rules:
                rules.write('\n(rule tight_moved_%d_%s\n  (condition "%s")\n  (constraint clearance (min 0.1mm)))\n'
                            % (len(tried), radius.replace('.', '_'), cond))
            grid(trial, ripped, {'FINE': '1', 'CLEAR': '0.1'})
        new_count, new_errors, new_report = drc(trial)
        print(net, radius, new_count, new_errors, 'stuck net still open' if any(net_of(e) == net for e in new_report['unconnected_items']) else 'stuck net closed', flush=True)
        if new_count < count and new_errors <= errors:
            for ext in ('.kicad_pcb', '_drc.json', '.kicad_dru'):
                shutil.copy(trial + ext, best + ext)
            count, errors, report = new_count, new_errors, new_report
            break
print('end', count, errors)
