"""Scratch: removes the unlocked track (or edge-violating via) of each clearance error in a DRC report."""
import json, sys, pcbnew
path, report = sys.argv[1:3]
flag = set()
for v in json.load(open(report))['violations']:
    if v['type'] == 'clearance':
        tracks = [i for i in v['items'] if i['description'].startswith('Track')]
        flag.update(i['uuid'] for i in (tracks[:1] if len(tracks) == 2 else tracks))
    elif v['type'] == 'copper_edge_clearance':
        flag.update(i['uuid'] for i in v['items'] if i['description'].startswith(('Via', 'Track')))
b = pcbnew.LoadBoard(path); keep = []; n = 0
for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in flag and not t.IsLocked():
        keep.append(t); b.Remove(t); n += 1
b.Save(path); print('ripped', n, 'of', len(flag))
