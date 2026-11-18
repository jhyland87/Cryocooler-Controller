#!/bin/bash
# usage: drc.sh board.kicad_pcb out.json  -> refills, saves, prints a tally
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$KC pcb drc --format json --severity-error --all-track-errors --refill-zones --save-board -o "$2" "$1" >/dev/null 2>&1
python3 - "$2" <<'PY'
import json, collections, re, sys
d = json.load(open(sys.argv[1]))
u = d.get('unconnected_items', [])
nets = collections.Counter(re.search(r'\[([^\]]+)\]', x['items'][0]['description']).group(1) for x in u)
print('errors', dict(collections.Counter(x['type'] for x in d['violations'])), '| unconnected', len(u), dict(nets.most_common(12)))
PY
