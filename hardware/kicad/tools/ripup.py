"""Rips the named nets' copper inside a box, then prunes dangling stubs.
Usage: ripup.py in.kicad_pcb out.kicad_pcb x0,y0,x1,y1 NET[,NET...]"""
import math
import sys

import pcbnew


def mm(value):
    return value / 1e6


def prune(board, nets):
    """Deletes track ends and vias of nets that no longer touch anything."""
    while True:
        tracks = [t for t in board.GetTracks() if t.GetNetname() in nets]
        pads = [p for p in board.GetPads() if p.GetNetname() in nets]

        def anchored(net, point, layer, self_item):
            for pad in pads:
                if pad.GetNetname() == net and pad.IsOnLayer(layer) and pad.HitTest(point):
                    return True
            for other in tracks:
                if other is self_item or other.GetNetname() != net:
                    continue
                if other.GetClass() == 'PCB_VIA':
                    if math.dist((point.x, point.y), (other.GetPosition().x,
                                                      other.GetPosition().y)) < 1000:
                        return True
                    continue
                if other.GetLayer() != layer:
                    continue
                if other.HitTest(point, 1000):
                    return True
            return False

        dangling = []
        for track in tracks:
            net = track.GetNetname()
            if track.GetClass() == 'PCB_VIA':
                layers = set()
                for other in tracks:
                    if other.GetClass() != 'PCB_VIA' and other.GetNetname() == net and (
                            other.HitTest(track.GetPosition(), 1000)):
                        layers.add(other.GetLayer())
                for pad in pads:
                    if pad.GetNetname() == net and pad.HitTest(track.GetPosition()):
                        layers.add('pad')
                if len(layers) < 2:
                    dangling.append(track)
                continue
            for end in (track.GetStart(), track.GetEnd()):
                if not anchored(net, end, track.GetLayer(), track):
                    dangling.append(track)
                    break
        if not dangling:
            break
        print('pruned', len(dangling))
        for item in dangling:
            board.Delete(item)


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    x0, y0, x1, y1 = (float(v) for v in sys.argv[3].split(','))
    nets = set(sys.argv[4].split(','))

    def inside(point):
        return x0 <= mm(point.x) <= x1 and y0 <= mm(point.y) <= y1

    doomed = [t for t in board.GetTracks() if t.GetNetname() in nets
              and (inside(t.GetStart()) or inside(t.GetEnd()))]
    print('ripped', len(doomed))
    for item in doomed:
        board.Delete(item)

    prune(board, nets)
    board.Save(sys.argv[2])


if __name__ == '__main__':
    main()
