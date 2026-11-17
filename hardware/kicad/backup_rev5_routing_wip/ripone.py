"""Clears other nets' copper round one open connection's ends.
Usage: ripone.py board drc.json out index radius_mm. Prints the stuck net."""
import json, math, os, re, sys
import pcbnew

KEEP = ('GND', 'ISO_GND', '+3V3', '+12V', 'VIN', 'VSW')
board = pcbnew.LoadBoard(sys.argv[1])
entry = json.load(open(sys.argv[2]))['unconnected_items'][int(sys.argv[4])]
radius = pcbnew.FromMM(float(sys.argv[5]))
stuck = re.search(r'\[(.*?)\]', entry['items'][0]['description']).group(1)
spots = [(pcbnew.FromMM(i['pos']['x']), pcbnew.FromMM(i['pos']['y']))
         for i in entry['items'] if i['description'].startswith('Pad')]
if os.environ.get('SPOT'):   # rip round a given point instead of the entry's pads
    spots = [tuple(pcbnew.FromMM(float(v)) for v in os.environ['SPOT'].split(','))]
held, ripped = [], set()
for track in list(board.GetTracks()):
    net = track.GetNetname()
    if net in KEEP or net == stuck or track.IsLocked():
        continue
    points = [track.GetPosition()] if track.Type() == pcbnew.PCB_VIA_T else [track.GetStart(), track.GetEnd()]
    if any(math.hypot(p.x - x, p.y - y) < radius for p in points for x, y in spots):
        held.append(track)
        ripped.add(net)
        board.Remove(track)
board.Save(sys.argv[3])
print(stuck + '|' + ','.join(sorted(ripped)), flush=True)
