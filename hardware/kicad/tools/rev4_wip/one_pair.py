"""Routes one connection by hand-given ends: one_pair.py board NET x0 y0 layer0 x1 y1 layer1 [margin]"""
import sys, time
import pcbnew, gridroute
path, net = sys.argv[1:3]
x0, y0, l0, x1, y1, l1 = float(sys.argv[3]), float(sys.argv[4]), sys.argv[5], float(sys.argv[6]), float(sys.argv[7]), sys.argv[8]
margin = float(sys.argv[9]) if len(sys.argv) > 9 else 8.0
board = pcbnew.LoadBoard(path)
def item(x, y, layer): return {'description': f'Track [{net}] on {layer}', 'pos': {'x': x, 'y': y}}
start = time.time()
result = gridroute.route_pair(board, [item(x0, y0, l0), item(x1, y1, l1)], margin)
print(net, result, round(time.time() - start), 's', flush=True)
if result != 'FAILED':
    board.Save(path)
