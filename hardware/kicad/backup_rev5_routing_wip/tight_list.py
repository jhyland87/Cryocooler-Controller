"""Lists spots under 0.15 mm on a board with every 0.1 mm rule removed.
Usage: tight_list.py stem out.json"""
import collections, json, os, re, shutil, subprocess, sys
KC = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
stem, out = sys.argv[1], sys.argv[2]
loose = stem + '_loose'
for e in ('.kicad_pcb', '.kicad_pro'):
    shutil.copy(stem + e, loose + e)
rules = open(stem + '.kicad_dru').read()
rules = rules[:rules.index('(rule tight')]
if not os.environ.get('KEEP_VIA'): rules = re.sub(r'\(rule via_in_pad_clearance.*?\n\n', '', rules, flags=re.S)
open(loose + '.kicad_dru', 'w').write(rules)
subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all', '--all-track-errors', '--format', 'json',
                '-o', loose + '.json', loose + '.kicad_pcb'], capture_output=True)
d = json.load(open(loose + '.json'))
spots = []
for v in d['violations']:
    if v['type'] != 'clearance':
        continue
    items = [(i['description'].split()[0], (re.search(r'\[(.*?)\]', i['description']) or [0, '?'])[1],
              i['pos']['x'], i['pos']['y'], i['description']) for i in v['items']]
    actual = float(re.search(r'actual ([\d.]+)', v['description']).group(1))
    spots.append({'actual': actual, 'items': items})
json.dump(spots, open(out, 'w'))
kinds = collections.Counter('+'.join(sorted(i[0] for i in s['items'])) for s in spots)
print(len(spots), 'spots, min', min(s['actual'] for s in spots), dict(kinds))
print('unconnected', len(d['unconnected_items']))
sens = [s for s in spots if any(re.search(r'SET|SPI_|USB|CAN', i[1]) for i in s['items'])]
print('sensitive', len(sens), collections.Counter(i[1] for s in sens for i in s['items']).most_common(12))
print('via nets', collections.Counter(i[1] for s in spots for i in s['items'] if i[0] == 'Via').most_common(15))
