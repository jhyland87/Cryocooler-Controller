"""Routes connections that are walled in by rip-up: finds the cheapest path
treating other signal tracks as passable at a cost, deletes only the track
pieces that path crosses, routes the connection, and leaves the displaced
nets open for gridroute.py.

Usage: [KEEP='NET|NET'] softroute.py in.kicad_pcb drc.json out.kicad_pcb 'NET[|NET...]'
(net names can hold commas and spaces, so the list is '|'-separated).
"""
import json
import math
import sys

import pcbnew

import os

os.environ.setdefault('SOFT_COST', '30')
import gridroute as gr  # noqa: E402  (reads SOFT_COST at import)
import ripup  # noqa: E402

# never ripped: switch nodes, a compensation node and the rail PG flags
PROTECTED = {'GND', 'ISO_GND', 'Net-(U20-SWA2)', 'Net-(D5-A)', 'Net-(D6-A)',
             'Net-(C77-Pad1)', 'PGP_15V', 'PGN_15V', 'PGN_16V5'}
# SPI, Analog and Control are schematic colour classes with Default's rules
SOFT_CLASSES = {'Default', 'SPI', 'Analog', 'Control'}
# extra nets to leave alone this run ('|'-separated)
KEEP = set(filter(None, os.environ.get('KEEP', '').split('|')))
PATH_WIDTH = 0.2


def soft_codes(board, keep):
    codes = set()
    for name, net in board.GetNetsByName().items():
        name = str(name)
        if not name or name in PROTECTED or name in keep or 'SW' in name:
            continue
        if net.GetNetClassName() in SOFT_CLASSES:
            codes.add(net.GetNetCode())
    return codes


def soft_path(board, pair, codes):
    """Cheapest path for the pair with soft nets passable; list of states."""
    net, start_pos, start_layers = gr.parse_item(board, pair[0])
    _, end_pos, end_layers = gr.parse_item(board, pair[1])
    grid = gr.Grid(board, board.FindNet(net).GetNetCode(), PATH_WIDTH,
                   (-1, -1, gr.W_MM + 1, gr.H_MM + 1), codes)
    gr.apply_iso(grid, gr.in_iso(start_pos) and gr.in_iso(end_pos))
    sc, gc = gr.cell_of(*start_pos), gr.cell_of(*end_pos)
    starts = [(layer, sc[1] * gr.NX + sc[0]) for layer in start_layers]
    goals = [(layer, gc[1] * gr.NX + gc[0]) for layer in end_layers]
    for layer, index in starts:
        grid.blocked[layer][index] = 0
    return gr.astar(grid, starts, goals)


def conflicts(board, path, codes):
    """Soft-net tracks and vias within clearance of the path."""
    cells = {}
    via_cells = set()
    for (layer, index), (next_layer, next_index) in zip(path, path[1:] + path[-1:]):
        point = (index % gr.NX * gr.CELL, index // gr.NX * gr.CELL)
        cells.setdefault(layer, []).append(point)
        if next_layer != layer:
            via_cells.add(point)
    hits = []
    for track in board.GetTracks():
        if track.GetNetCode() not in codes:
            continue
        a, b = track.GetStart(), track.GetEnd()
        ax, ay, bx, by = gr.mm(a.x), gr.mm(a.y), gr.mm(b.x), gr.mm(b.y)
        if track.GetClass() == 'PCB_VIA':
            reach = gr.mm(track.GetWidth(pcbnew.F_Cu)) / 2 + gr.CLEAR + PATH_WIDTH / 2 + 0.05
            points = [p for layer_points in cells.values() for p in layer_points]
        else:
            reach = gr.mm(track.GetWidth()) / 2 + gr.CLEAR + PATH_WIDTH / 2 + 0.05
            points = cells.get(track.GetLayer(), [])
            # a path via touches every layer
            points = points + list(via_cells)
            reach_via = gr.mm(track.GetWidth()) / 2 + gr.VIA_CLEAR + gr.VIA_D / 2 + 0.05
        lo_x, hi_x = min(ax, bx) - 1, max(ax, bx) + 1
        lo_y, hi_y = min(ay, by) - 1, max(ay, by) + 1
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        for px, py in points:
            if not (lo_x <= px <= hi_x and lo_y <= py <= hi_y):
                continue
            t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy)
                                                        / length2))
            gap = math.hypot(ax + t * dx - px, ay + t * dy - py)
            limit = reach
            if track.GetClass() != 'PCB_VIA' and (px, py) in via_cells:
                limit = max(reach, reach_via)
            if gap < limit:
                hits.append(track)
                break
    return hits


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    report = json.load(open(sys.argv[2]))
    wanted = set(sys.argv[4].split('|'))
    displaced = set()
    for entry in report['unconnected_items']:
        pair = entry['items']
        net = gr.parse_item(board, pair[0])[0]
        if net not in wanted:
            continue
        codes = soft_codes(board, wanted | KEEP)
        path = soft_path(board, pair, codes)
        if not path:
            print(net, 'no soft path')
            continue
        hits = conflicts(board, path, codes)
        nets = {track.GetNetname() for track in hits}
        print(net, 'rips', len(hits), 'pieces of', sorted(nets), flush=True)
        for track in hits:
            board.Delete(track)
        ripup.prune(board, nets)
        displaced |= nets
        print(net, gr.route_pair(board, pair, 40.0), flush=True)
    print('displaced:', ','.join(sorted(displaced)))
    board.Save(sys.argv[3])


if __name__ == '__main__':
    main()
