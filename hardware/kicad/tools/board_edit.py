"""Small hand edits on a routed board, listed in a JSON file: `rip` removes copper of a net
with an end inside a box (optionally on one layer), `track` and `via` add copper.

Usage: board_edit.py board.kicad_pcb edits.json (edits in place)
"""
import json
import sys

import pcbnew

MM = pcbnew.FromMM
KEEP = []


def ends(item):
    if item.Type() == pcbnew.PCB_VIA_T:
        return [item.GetPosition()]
    return [item.GetStart(), item.GetEnd()]


def rip(board, net, box, layer=None):
    count = 0
    for item in list(board.GetTracks()):
        if item.GetNetname() != net:
            continue
        if layer is not None:
            if item.Type() == pcbnew.PCB_VIA_T or item.GetLayerName() != layer:
                continue
        if any(box[0] <= p.x / 1e6 <= box[2] and box[1] <= p.y / 1e6 <= box[3] for p in ends(item)):
            KEEP.append(item)
            board.Remove(item)
            count += 1
    print('ripped', count, net)


def add_track(board, net, layer, width, points):
    for first, second in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(MM(first[0]), MM(first[1])))
        track.SetEnd(pcbnew.VECTOR2I(MM(second[0]), MM(second[1])))
        track.SetLayer(board.GetLayerID(layer))
        track.SetWidth(MM(width))
        track.SetNet(board.FindNet(net))
        board.Add(track)
        KEEP.append(track)


def add_via(board, net, pos_x, pos_y, diameter=0.45, drill=0.2):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(MM(pos_x), MM(pos_y)))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetWidth(MM(diameter))
    via.SetDrill(MM(drill))
    via.SetNet(board.FindNet(net))
    board.Add(via)
    KEEP.append(via)


def main():
    path, edit_path = sys.argv[1:3]
    board = pcbnew.LoadBoard(path)
    for edit in json.load(open(edit_path)):
        kind = edit[0]
        if kind == 'rip':
            rip(board, *edit[1:])
        elif kind == 'track':
            add_track(board, *edit[1:])
        else:
            add_via(board, *edit[1:])
    board.Save(path)


if __name__ == '__main__':
    main()
