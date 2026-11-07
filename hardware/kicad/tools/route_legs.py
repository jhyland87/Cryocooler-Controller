"""Routes one long net leg by leg through way-point vias with gridroute's A*, for a connection
too long for one search. Way points are free spots where a via can sit; everything runs in one
process because KiCad gives an unconnected via the pour's net when a board is reloaded.

Usage: route_legs.py board.kicad_pcb NET x,y x,y ... (first and last are existing copper)
"""
import sys

import pcbnew

import gridroute


def add_via(board, net, point):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(gridroute.nm(point[0]), gridroute.nm(point[1])))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(gridroute.nm(gridroute.VIA_D))
    via.SetDrill(gridroute.nm(gridroute.VIA_DRILL))
    via.SetNet(board.FindNet(net))
    board.Add(via)


def main():
    path, net = sys.argv[1:3]
    points = [tuple(float(value) for value in text.split(',')) for text in sys.argv[3:]]
    board = pcbnew.LoadBoard(path)
    for point in points[1:-1]:
        add_via(board, net, point)
    for first, second in zip(points, points[1:]):
        pair = [
            {'description': f'Via [{net}]', 'pos': {'x': first[0], 'y': first[1]}},
            {'description': f'Via [{net}]', 'pos': {'x': second[0], 'y': second[1]}},
        ]
        print(first, second, gridroute.route_pair(board, pair, 6.0), flush=True)
    board.Save(path)


if __name__ == '__main__':
    main()
