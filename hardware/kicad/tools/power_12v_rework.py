"""Adds outer-layer copper in parallel with the 0.8 mm In2 12 V runs for a 4 A
total: VIN from F1 to Q1, Q1 to R98, R98 to U15's junction, J5 to J3 to J4, plus
via groups at each layer change. Existing copper stays and shares the current.
Run with the fill and silk steps afterwards.

Usage: power_12v_rework.py board.kicad_pcb (edits in place)
"""
import math
import sys

import pcbnew

import gridroute as route

MM = pcbnew.FromMM
FRONT, BACK = pcbnew.F_Cu, pcbnew.B_Cu
POWER_VIA, POWER_DRILL = 0.7, 0.35
KEEP = []
LOOP_MARGIN = 12.0
RING_STEP_DEG = 45
RING_RADIUS = 1.0
# (net, start, start layers, end, end layers, layers allowed, widths to try)
LEGS = (
    ('VIN', (19.0, 45.05), (FRONT,), (38.35, 67.54), (FRONT, BACK), (FRONT, BACK), (1.2, 1.1)),
    ('+12V', (41.35, 59.54), (BACK,), (38.02, 76.72), (BACK, FRONT), (FRONT, BACK), (1.2, 1.1)),
    ('+12V', (71.04, 86.6), (FRONT, BACK), (83.04, 86.6), (FRONT, BACK), (FRONT,), (1.0, 0.8)),
    ('+12V', (83.04, 86.6), (FRONT, BACK), (94.74, 86.6), (FRONT, BACK), (FRONT,), (1.0, 0.8)),
)
# existing single vias that carry shared current: (net, spot, extra vias wanted)
VIA_GROUPS = (('+12V', (38.02, 76.72), 2), ('+12V', (56.48, 85.52), 2))
# In2 from R98 to the junction would still take about half the current and run
# hot, so it goes; the outer route replaces it. North of this box is R99's sense.
IN2_RIP_NET = '+12V'
IN2_RIP_BOX = (37.4, 60.1, 42.0, 77.3)
# Q1's pin 2 to its tab on F.Cu, then through R98 pad 1 to B.Cu
VSW_STRIP = ((40.0, 65.3), (43.4, 65.3))
VSW_STRIP_WIDTH = 1.4
# either side of the In2 +12V run at x 41.21
VSW_VIAS = ((40.15, 65.46), (42.25, 65.0), (42.25, 65.9))


def add_via(board, net_name, spot):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(MM(spot[0]), MM(spot[1])))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(MM(POWER_VIA))
    via.SetDrill(MM(POWER_DRILL))
    via.SetNet(board.FindNet(net_name))
    board.Add(via)


def add_track(board, net_name, start, end, width, layer):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    track.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    track.SetWidth(MM(width))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    board.Add(track)


def via_spots(run_end, net_code, board, count):
    """Free spots on a ring around run_end, 45 degree multiples only."""
    x, y = run_end
    spots = []
    region = (x - 4, y - 4, x + 4, y + 4)
    for angle in range(0, 360, RING_STEP_DEG):
        spot = (x + RING_RADIUS * math.cos(math.radians(angle)),
                y + RING_RADIUS * math.sin(math.radians(angle)))
        spot = (round(spot[0], 2), round(spot[1], 2))
        grid = route.Grid(board, net_code, 0.8, region)
        cell_x, cell_y = route.cell_of(*spot)
        index = cell_y * route.NX + cell_x
        if grid.via_blocked[index] or grid.blocked[FRONT][index] or grid.blocked[BACK][index]:
            continue
        spots.append(spot)
        if len(spots) == count:
            break
    return spots


def add_group(board, net_name, centre, count):
    """Adds count vias beside centre, each tied to it on both outer layers."""
    code = board.FindNet(net_name).GetNetCode()
    spots = via_spots(centre, code, board, count)
    for spot in spots:
        add_via(board, net_name, spot)
        add_track(board, net_name, centre, spot, 0.8, FRONT)
        add_track(board, net_name, centre, spot, 0.8, BACK)
    print(net_name, 'group at', centre, 'added', spots)
    assert len(spots) == count, (centre, spots)


def route_leg(board, leg):
    net_name, start, start_layers, end, end_layers, layers, widths = leg
    code = board.FindNet(net_name).GetNetCode()
    route.ROUTE_LAYERS = list(layers)
    box = (min(start[0], end[0]) - LOOP_MARGIN, min(start[1], end[1]) - LOOP_MARGIN,
           max(start[0], end[0]) + LOOP_MARGIN, max(start[1], end[1]) + LOOP_MARGIN)
    for width in widths:
        grid = route.Grid(board, code, width, box)
        start_cell, end_cell = route.cell_of(*start), route.cell_of(*end)
        starts = [(layer, start_cell[1] * route.NX + start_cell[0]) for layer in start_layers]
        goals = [(layer, end_cell[1] * route.NX + end_cell[0]) for layer in end_layers]
        for layer, index in starts:
            grid.blocked[layer][index] = 0
        path = route.astar(grid, starts, goals)
        if not path:
            continue
        runs = route.smooth(grid, path)
        route.add_route(board, net_name, runs, start, end, width)
        print(net_name, start, '->', end, 'width', width, 'layer changes', len(runs) - 1)
        return [(index % route.NX * route.CELL, index // route.NX * route.CELL)
                for _, points in runs[:-1] for index in points[-1:]]
    raise RuntimeError(f'no route for {leg}')


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    route.VIA_D, route.VIA_DRILL = POWER_VIA, POWER_DRILL
    route.VIA_COST = 200.0

    for item in list(board.GetTracks()):
        bounds = item.GetBoundingBox()
        if (item.Type() != pcbnew.PCB_VIA_T and item.GetLayer() == pcbnew.In2_Cu
                and item.GetNetname() == IN2_RIP_NET
                and bounds.GetLeft() / 1e6 >= IN2_RIP_BOX[0] and bounds.GetTop() / 1e6 >= IN2_RIP_BOX[1]
                and bounds.GetRight() / 1e6 <= IN2_RIP_BOX[2] and bounds.GetBottom() / 1e6 <= IN2_RIP_BOX[3]):
            print('removed In2', item.GetStart().x / 1e6, item.GetStart().y / 1e6)
            KEEP.append(item)
            board.Remove(item)

    add_track(board, 'VSW', VSW_STRIP[0], VSW_STRIP[1], VSW_STRIP_WIDTH, FRONT)
    for spot in VSW_VIAS:
        add_via(board, 'VSW', spot)

    for leg in LEGS:
        for change in route_leg(board, leg):
            add_group(board, leg[0], change, 2)
    for net_name, spot, count in VIA_GROUPS:
        add_group(board, net_name, spot, count)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
