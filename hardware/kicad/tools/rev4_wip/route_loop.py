"""gridroute over a DRC report in net groups, saving the board every few pairs.
Usage: route_loop.py board.kicad_pcb drc.json [PATTERNS ...]   (env as gridroute.py)
Pairs closer than BRIDGE mm (default 2.5) go first: they mend cut tracks. Then each
PATTERNS argument (a comma list of net-name wildcards) in order, shortest pair first,
and a final implicit group takes whatever is left."""
import fnmatch, json, math, os, sys
import pcbnew
import gridroute

path, report_path = sys.argv[1:3]
groups = [arg.split('|') if '|' in arg else arg.split(',') for arg in sys.argv[3:]]
if os.environ.get('ONLY') != '1':
    groups.append(['*'])
bridge = float(os.environ.get('BRIDGE', '2.5'))
board = pcbnew.LoadBoard(path)
entries = json.load(open(report_path))['unconnected_items']
def span(entry):
    a, b = entry['items']
    return math.dist((a['pos']['x'], a['pos']['y']), (b['pos']['x'], b['pos']['y']))
named = [(gridroute.parse_item(board, entry['items'][0])[0], entry) for entry in entries]
named = [(net, entry) for net, entry in named if net not in gridroute.SKIP_NETS]
done = set()
count = 0
failed = []
def run(label, batch):
    global count
    print('group', label, len(batch), flush=True)
    for index, (net, entry) in sorted(batch, key=lambda item: span(item[1][1])):
        done.add(index)
        pair = entry['items']
        result = gridroute.route_pair(board, pair, 6.0)
        if result == 'FAILED':
            result = gridroute.route_pair(board, pair, 40.0)
        if result == 'FAILED':
            failed.append((net, round(span(entry), 1)))
        print(net, round(span(entry), 1), result, flush=True)
        count += 1
        if count % 6 == 0:
            board.Save(path)
run('bridges', [(i, item) for i, item in enumerate(named) if span(item[1]) <= bridge])
for patterns in groups:
    run(' '.join(patterns)[:80], [(i, item) for i, item in enumerate(named)
        if i not in done and any(fnmatch.fnmatchcase(item[0], p) for p in patterns)])
board.Save(path)
print('saved; failed:', failed, flush=True)
