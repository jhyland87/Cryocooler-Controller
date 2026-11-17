"""For each open signal connection, how far each end can get before it is boxed in.
Usage: reach.py board.kicad_pcb drc.json"""
import json, sys, collections
sys.argv = [sys.argv[0]] + sys.argv[1:]
import gridroute as g
import pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
SKIP = {'GND', '+3V3', 'ISO_GND', '+12V'}
CAP = 60000
for entry in json.load(open(sys.argv[2]))['unconnected_items']:
    pair = entry['items']
    net, a_pos, a_layers = g.parse_item(board, pair[0])
    if net in SKIP:
        continue
    _, b_pos, b_layers = g.parse_item(board, pair[1])
    code = board.FindNet(net).GetNetCode()
    region = (min(a_pos[0], b_pos[0]) - 8, min(a_pos[1], b_pos[1]) - 8, max(a_pos[0], b_pos[0]) + 8, max(a_pos[1], b_pos[1]) + 8)
    grid = g.Grid(board, code, 0.15, region)
    out = []
    for item, pos, layers in ((pair[0], a_pos, a_layers), (pair[1], b_pos, b_layers)):
        c = g.cell_of(*pos); start = c[1] * g.NX + c[0]
        seen = set((layer, start) for layer in layers); queue = collections.deque(seen); vias = 0
        while queue and len(seen) < CAP:
            layer, index = queue.popleft()
            cx, cy = index % g.NX, index // g.NX
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cy + dy) * g.NX + cx + dx
                if (layer, n) not in seen and not grid.blocked[layer][n]:
                    seen.add((layer, n)); queue.append((layer, n))
            if not grid.via_blocked[index]:
                for other in g.ROUTE_LAYERS:
                    if other != layer and not grid.blocked[other][index] and (other, index) not in seen:
                        vias += 1; seen.add((other, index)); queue.append((other, index))
        area = len(seen) * g.CELL * g.CELL
        out.append(f"{item['description'][:44]:44s} reach {'open' if len(seen) >= CAP else f'{area:6.2f} mm2'} layerchanges {min(vias, 99)}")
    print(net); print('   ' + '\n   '.join(out), flush=True)
