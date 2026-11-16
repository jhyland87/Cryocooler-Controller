"""Clears other nets' copper round each stuck pad so the stuck net can be routed
first. Usage: unstick.py board.kicad_pcb drc.json out.kicad_pcb [window_mm]
Prints the stuck nets, comma separated."""
import json, math, re, sys
import pcbnew

KEEP_NETS = ('GND', 'ISO_GND', '+3V3', '+12V', 'VIN', 'VSW', 'Net-(F1-Pad1)', 'Net-(J11-Pin_1)', 'Net-(J12-Pin_1)')
board = pcbnew.LoadBoard(sys.argv[1])
window = pcbnew.FromMM(float(sys.argv[4]) if len(sys.argv) > 4 else 2.5)
report = json.load(open(sys.argv[2]))
stuck, spots = set(), []
for entry in report['unconnected_items']:
    net = re.search(r'\[(.*?)\]', entry['items'][0]['description']).group(1)
    if net in KEEP_NETS:
        continue
    stuck.add(net)
    for item in entry['items']:
        if item['description'].startswith('Pad'):
            spots.append((pcbnew.FromMM(item['pos']['x']), pcbnew.FromMM(item['pos']['y'])))
held, removed = [], 0
for track in list(board.GetTracks()):
    net = track.GetNetname()
    if net in KEEP_NETS or net in stuck or track.IsLocked():
        continue
    points = [track.GetPosition()] if track.Type() == pcbnew.PCB_VIA_T else [track.GetStart(), track.GetEnd()]
    if any(math.hypot(p.x - x, p.y - y) < window for p in points for x, y in spots):
        held.append(track)
        board.Remove(track)
        removed += 1
board.Save(sys.argv[3])
print('removed', removed, file=sys.stderr)
print(','.join(sorted(stuck)))
