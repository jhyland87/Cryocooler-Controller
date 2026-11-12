"""Rip-up routing for walled-in pairs, then re-routes what it displaced.
Usage: soft8.py board.kicad_pcb drc.json 'NET|NET...'  (run from tools/, env as gridroute.py)"""
import json, math, os, sys
os.environ.setdefault('SOFT_COST', '30')
import pcbnew
import gridroute as gr
import softroute
import ripup

softroute.SOFT_CLASSES = {'Default', 'Control'}
MARGIN = float(os.environ.get('SOFT_MARGIN', '12'))

def soft_path(board, pair, codes):
    net, start_pos, start_layers = gr.parse_item(board, pair[0])
    _, end_pos, end_layers = gr.parse_item(board, pair[1])
    region = (min(start_pos[0], end_pos[0]) - MARGIN, min(start_pos[1], end_pos[1]) - MARGIN,
              max(start_pos[0], end_pos[0]) + MARGIN, max(start_pos[1], end_pos[1]) + MARGIN)
    grid = gr.Grid(board, board.FindNet(net).GetNetCode(), softroute.PATH_WIDTH, region, codes)
    sc, gc = gr.cell_of(*start_pos), gr.cell_of(*end_pos)
    starts = [(layer, sc[1] * gr.NX + sc[0]) for layer in start_layers]
    goals = [(layer, gc[1] * gr.NX + gc[0]) for layer in end_layers]
    for layer, index in starts:
        grid.blocked[layer][index] = 0
    return gr.astar(grid, starts, goals)

path, report_path = sys.argv[1:3]
wanted = set(sys.argv[3].split('|'))
board = pcbnew.LoadBoard(path)
report = json.load(open(report_path))
displaced = set()
for entry in report['unconnected_items']:
    pair = entry['items']
    net = gr.parse_item(board, pair[0])[0]
    if net not in wanted:
        continue
    result = gr.route_pair(board, pair, 8.0)
    if result != 'FAILED':
        print(net, 'plain', result, flush=True)
        continue
    codes = softroute.soft_codes(board, wanted | softroute.KEEP)
    found = soft_path(board, pair, codes)
    if not found:
        print(net, 'no soft path', flush=True)
        continue
    hits = softroute.conflicts(board, found, codes)
    nets = {track.GetNetname() for track in hits}
    print(net, 'rips', len(hits), 'pieces of', sorted(nets), flush=True)
    for track in hits:
        board.Delete(track)
    ripup.prune(board, nets)
    displaced |= nets
    print(net, gr.route_pair(board, pair, 40.0), flush=True)
board.Save(path)
print('displaced:', '|'.join(sorted(displaced)), flush=True)
