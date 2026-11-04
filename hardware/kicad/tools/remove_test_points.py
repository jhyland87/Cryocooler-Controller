"""Removes test points from a routed board, with the copper that only served them.
Take them out of the schematic too. Used for the SPI points (TP18-TP28) and SCL (TP31).

Usage: remove_test_points.py board.kicad_pcb TP18 TP19 ... (edits in place, refills zones)
"""
import math
import sys

import pcbnew

from ripup import prune

SLIVER_MM = 0.02  # prune() sees a free end this close to the next track as anchored
ON_LINE_NM = 2000


def distance_to_line(point, track):
    """Distance from a point to a track's centreline, in KiCad units."""
    start, end = track.GetStart(), track.GetEnd()
    delta_x, delta_y = end.x - start.x, end.y - start.y
    length_squared = delta_x ** 2 + delta_y ** 2
    ratio = 0
    if length_squared:
        ratio = max(0, min(1, ((point.x - start.x) * delta_x + (point.y - start.y) * delta_y) / length_squared))
    return math.hypot(point.x - start.x - ratio * delta_x, point.y - start.y - ratio * delta_y)


def net_points(tracks, skip, layer):
    """Track ends on a layer and via centres of a net, without one track's own ends."""
    points = []
    for other in tracks:
        if other.m_Uuid.AsString() == skip.m_Uuid.AsString():
            continue
        if other.GetClass() == 'PCB_VIA':
            points.append(other.GetPosition())
        elif other.GetLayer() == layer:
            points += [other.GetStart(), other.GetEnd()]
    return points


def trim_to_junction(board, pad):
    """Pulls a track end out of the pad, back to the last junction along the track,
    so that prune() does not delete the live part of the track with the stub.
    """
    tracks = [item for item in board.GetTracks() if item.GetNetname() == pad.GetNetname()]
    for track in tracks:
        if track.GetClass() == 'PCB_VIA' or not pad.IsOnLayer(track.GetLayer()):
            continue
        for free, setter in ((track.GetStart(), track.SetStart), (track.GetEnd(), track.SetEnd)):
            if not pad.HitTest(free):
                continue
            junctions = [point for point in net_points(tracks, track, track.GetLayer())
                         if distance_to_line(point, track) < ON_LINE_NM and not pad.HitTest(point)
                         and math.dist((point.x, point.y), (track.GetStart().x, track.GetStart().y)) > ON_LINE_NM
                         and math.dist((point.x, point.y), (track.GetEnd().x, track.GetEnd().y)) > ON_LINE_NM]
            if junctions:
                setter(min(junctions, key=lambda point: math.dist((point.x, point.y), (free.x, free.y))))
            break


def has_free_end(track, tracks):
    """True if nothing meets one of the track's ends on the centreline."""
    others = [item for item in tracks if item.m_Uuid.AsString() != track.m_Uuid.AsString()]

    def met(point):
        for other in others:
            if other.GetClass() == 'PCB_VIA':
                if math.dist((point.x, point.y), (other.GetPosition().x, other.GetPosition().y)) < ON_LINE_NM:
                    return True
            elif other.GetLayer() == track.GetLayer() and distance_to_line(point, other) < ON_LINE_NM:
                return True
        return False

    return not (met(track.GetStart()) and met(track.GetEnd()))


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    nets = set()
    removed = []  # keeps the wrappers alive until the save
    for reference in sys.argv[2:]:
        footprint = board.FindFootprintByReference(reference)
        for pad in footprint.Pads():
            nets.add(pad.GetNetname())
            trim_to_junction(board, pad)
        board.Remove(footprint)
        removed.append(footprint)
    print('removed', len(removed), 'test points on', sorted(nets))
    prune(board, nets)
    tracks = [item for item in board.GetTracks() if item.GetNetname() in nets]
    for track in tracks:
        if (track.Type() == pcbnew.PCB_TRACE_T and track.GetLength() < SLIVER_MM * 1e6
                and has_free_end(track, [item for item in tracks if item.GetNetname() == track.GetNetname()])):
            board.Remove(track)
            removed.append(track)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
