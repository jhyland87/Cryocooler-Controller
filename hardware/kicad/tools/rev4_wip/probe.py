"""Flood-fills from a pad on gridroute's grid to see how far a net can get: probe.py board NET x y layer"""
import sys, collections
import pcbnew, gridroute
from gridroute import NX, NY, CELL, cell_of
path, net, x, y, layer = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
board = pcbnew.LoadBoard(path)
code = board.FindNet(net).GetNetCode()
grid = gridroute.Grid(board, code, 0.2, (x - 45, y - 45, x + 45, y + 45))
start_layer = board.GetLayerID(layer)
sc = cell_of(x, y); start = sc[1] * NX + sc[0]
for l in gridroute.ROUTE_LAYERS: pass
grid.blocked[start_layer][start] = 0
seen = {(start_layer, start)}; queue = collections.deque(seen)
reach = collections.defaultdict(lambda: [1e9, -1e9, 1e9, -1e9, 0])
while queue:
    l, i = queue.popleft()
    cx, cy = i % NX, i // NX
    r = reach[l]; r[0] = min(r[0], cx * CELL); r[1] = max(r[1], cx * CELL); r[2] = min(r[2], cy * CELL); r[3] = max(r[3], cy * CELL); r[4] += 1
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = cx + dx, cy + dy
        if 0 <= nx < NX and 0 <= ny < NY:
            j = ny * NX + nx
            if not grid.blocked[l][j] and (l, j) not in seen:
                seen.add((l, j)); queue.append((l, j))
    if not grid.via_blocked[i]:
        for l2 in gridroute.ROUTE_LAYERS:
            if l2 != l and not grid.blocked[l2][i] and (l2, i) not in seen:
                seen.add((l2, i)); queue.append((l2, i))
for l, r in reach.items():
    print(board.GetLayerName(l), 'cells', r[4], 'x', round(r[0], 2), round(r[1], 2), 'y', round(r[2], 2), round(r[3], 2))
