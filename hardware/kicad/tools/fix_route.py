"""Post-route clean-up for the board `gen_pcb.py route` writes.

Run with KiCad's bundled python after `gen_pcb.py route` and before
`link_usb_vbus.py`:
    .../Python.framework/Versions/Current/bin/python3 tools/fix_route.py [board]

Fixes the leftovers Freerouting 2.5.0 produced on the LT3097 revision:
  * GND vias that short or crowd a track of another net (inner layers
    included) are removed, and co-located duplicates are collapsed;
  * pour fragments left without a via get one at their roomiest point, and
    signal vias that touch copper on one layer only are removed;
  * the R53 pad 2 to J12 current-path link is closed with a short F.Cu track;
  * the Q2 gate track is pulled 0.25 mm away from Q4 pad 2.
The track edits match one routing result (coordinates below), so they only
apply when the expected segments are found; a re-route needs them re-checked.
"""

import math
import sys
from pathlib import Path

import pcbnew

KICAD_DIR = Path(__file__).resolve().parent.parent
GROUND_NETS = {'GND', 'ISO_GND'}
# removed items stay referenced: freeing them while the board is in use
# corrupts the other pcbnew objects
REMOVED = []
# clearance a via keeps from a foreign-net track (via_in_pad_clearance rule)
VIA_TRACK_CLEARANCE = 0.1


def mm(value):
    return value / 1e6


def segment_distance(point, start, end):
    """Distance from a point to a segment, all (x, y) in mm."""
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length_squared = delta_x * delta_x + delta_y * delta_y
    fraction = (
        0.0
        if length_squared == 0
        else max(
            0.0,
            min(
                1.0,
                ((point[0] - start[0]) * delta_x + (point[1] - start[1]) * delta_y)
                / length_squared,
            ),
        )
    )
    return math.hypot(
        point[0] - (start[0] + fraction * delta_x),
        point[1] - (start[1] + fraction * delta_y),
    )


def remove_crowding_vias(board):
    """Removes GND vias within clearance of a foreign-net track on any layer,
    and duplicate vias at one position. Returns the removed vias' positions.
    """
    removed = []
    tracks = [
        item
        for item in board.GetTracks()
        if item.Type() == pcbnew.PCB_TRACE_T
    ]
    vias = [
        item
        for item in board.GetTracks()
        if item.Type() == pcbnew.PCB_VIA_T
    ]
    seen = set()
    for via in vias:
        position = (mm(via.GetPosition().x), mm(via.GetPosition().y))
        key = (round(position[0], 3), round(position[1], 3), via.GetNetname())
        if key in seen:
            board.Remove(via)
            REMOVED.append(via)
            removed.append(position)
            continue
        seen.add(key)
        if via.GetNetname() not in GROUND_NETS:
            continue
        radius = mm(via.GetWidth()) / 2
        for track in tracks:
            if track.GetNetname() == via.GetNetname():
                continue
            start = (mm(track.GetStart().x), mm(track.GetStart().y))
            end = (mm(track.GetEnd().x), mm(track.GetEnd().y))
            limit = radius + mm(track.GetWidth()) / 2 + VIA_TRACK_CLEARANCE
            if segment_distance(position, start, end) < limit:
                board.Remove(via)
                REMOVED.append(via)
                removed.append(position)
                break
    return removed


def find_track(board, net, start, end, tolerance=0.01):
    """Finds a track of a net between two points (either direction)."""
    for item in board.GetTracks():
        if item.Type() != pcbnew.PCB_TRACE_T or item.GetNetname() != net:
            continue
        ends = (
            (mm(item.GetStart().x), mm(item.GetStart().y)),
            (mm(item.GetEnd().x), mm(item.GetEnd().y)),
        )
        for first, second in (ends, ends[::-1]):
            if math.dist(first, start) < tolerance and math.dist(
                second, end
            ) < tolerance:
                return item
    return None


def add_track(board, net_name, points, width, layer=pcbnew.F_Cu):
    net = board.FindNet(net_name)
    for start, end in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start[0]), pcbnew.FromMM(start[1])))
        track.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end[0]), pcbnew.FromMM(end[1])))
        track.SetWidth(pcbnew.FromMM(width))
        track.SetLayer(layer)
        track.SetNet(net)
        board.Add(track)


def close_current_path_link(board):
    """R53 pad 2 up to the locked 2 mm J12 -> ACS37800 path."""
    pad = next(
        pad
        for footprint in board.GetFootprints()
        if footprint.GetReference() == 'R53'
        for pad in footprint.Pads()
        if pad.GetNumber() == '2'
    )
    x, y = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
    # the 2 mm path runs along y = 55.0 from J12 to x = 21.35
    add_track(board, pad.GetNetname(), [(x, y), (x, 55.0)], 0.25)


def move_q2_gate_track(board):
    """Q2 gate stub: replace the 0.15 mm squeeze past Q4 pad 2 by a 0.25 mm
    run 0.35 mm further from the pad.
    """
    net = 'Net-(Q2-G)'
    vertical = find_track(board, net, (34.6787, 90.9941), (34.6787, 90.5448))
    horizontal = find_track(board, net, (34.6787, 90.5448), (35.2138, 90.5448))
    diagonal = find_track(board, net, (35.2138, 90.5448), (35.4647, 90.2939))
    if not (vertical and horizontal and diagonal):
        return False
    board.Remove(horizontal)
    board.Remove(diagonal)
    REMOVED.extend([horizontal, diagonal])
    vertical.SetEnd(
        pcbnew.VECTOR2I(pcbnew.FromMM(34.6787), pcbnew.FromMM(90.2939))
    )
    add_track(board, net, [(34.6787, 90.2939), (35.4647, 90.2939)], 0.25)
    return True


def foreign_gap(board, x, y, radius, net):
    """Smallest gap in mm between a via of the given radius at (x, y) and
    copper of any other net (tracks on every layer, vias, pads).
    """
    gap = 1e9
    for item in board.GetTracks():
        if item.GetNetname() == net:
            continue
        if item.Type() == pcbnew.PCB_VIA_T:
            centre = (mm(item.GetPosition().x), mm(item.GetPosition().y))
            reach = mm(item.GetWidth()) / 2
            gap = min(gap, math.dist((x, y), centre) - reach - radius)
            continue
        start = (mm(item.GetStart().x), mm(item.GetStart().y))
        end = (mm(item.GetEnd().x), mm(item.GetEnd().y))
        gap = min(
            gap,
            segment_distance((x, y), start, end)
            - mm(item.GetWidth()) / 2
            - radius,
        )
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetname() == net:
                continue
            box = pad.GetBoundingBox()
            delta_x = max(mm(box.GetLeft()) - x, x - mm(box.GetRight()), 0.0)
            delta_y = max(mm(box.GetTop()) - y, y - mm(box.GetBottom()), 0.0)
            gap = min(gap, math.hypot(delta_x, delta_y) - radius)
    return gap


def reconnect_ground_islands(board, diameter=0.5, drill=0.3, margin=0.2):
    """Gives each F.Cu ground pour fragment that has no via (after the removals
    above) one via at its roomiest point, clear of foreign copper.
    """
    added = []
    radius = diameter / 2
    for zone in list(board.Zones()):
        if (
            zone.GetIsRuleArea()
            or zone.GetNetname() not in GROUND_NETS
            or zone.GetLayer() != pcbnew.F_Cu
        ):
            continue
        net = zone.GetNetname()
        vias = [
            item
            for item in board.GetTracks()
            if item.Type() == pcbnew.PCB_VIA_T and item.GetNetname() == net
        ]
        filled = zone.GetFilledPolysList(pcbnew.F_Cu)
        for index in range(filled.OutlineCount()):
            if any(filled.Contains(via.GetPosition(), index) for via in vias):
                continue
            box = filled.Outline(index).BBox()
            left, right = mm(box.GetLeft()), mm(box.GetRight())
            top, bottom = mm(box.GetTop()), mm(box.GetBottom())
            best = None
            steps_x = int((right - left) / 0.1) + 1
            steps_y = int((bottom - top) / 0.1) + 1
            for step_x in range(steps_x):
                for step_y in range(steps_y):
                    x, y = left + step_x * 0.1, top + step_y * 0.1
                    point = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
                    if not filled.Contains(point, index):
                        continue
                    # keep the via's copper inside the fragment
                    if not all(
                        filled.Contains(
                            pcbnew.VECTOR2I(
                                pcbnew.FromMM(x + dx), pcbnew.FromMM(y + dy)
                            ),
                            index,
                        )
                        for dx, dy in (
                            (radius, 0), (-radius, 0), (0, radius), (0, -radius)
                        )
                    ):
                        continue
                    gap = foreign_gap(board, x, y, radius, net)
                    if best is None or gap > best[0]:
                        best = (gap, x, y)
            if best is None or best[0] < margin:
                print('no room for an island via in', left, top, right, bottom)
                continue
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(
                pcbnew.VECTOR2I(pcbnew.FromMM(best[1]), pcbnew.FromMM(best[2]))
            )
            via.SetWidth(pcbnew.FromMM(diameter))
            via.SetDrill(pcbnew.FromMM(drill))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetNet(board.FindNet(net))
            board.Add(via)
            added.append((round(best[1], 3), round(best[2], 3), round(best[0], 2)))
    return added


def remove_dangling_vias(board):
    """Removes signal vias that touch copper on only one layer."""
    layers = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
    removed = []
    for via in [
        item for item in board.GetTracks() if item.Type() == pcbnew.PCB_VIA_T
    ]:
        if via.GetNetname() in GROUND_NETS:
            continue
        centre = via.GetPosition()
        position = (mm(centre.x), mm(centre.y))
        touched = set()
        for item in board.GetTracks():
            if item.Type() != pcbnew.PCB_TRACE_T or item.GetNetname() != via.GetNetname():
                continue
            for end in (item.GetStart(), item.GetEnd()):
                if math.dist(position, (mm(end.x), mm(end.y))) < 0.01:
                    touched.add(item.GetLayer())
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                if pad.GetNetname() == via.GetNetname() and pad.HitTest(centre):
                    touched.update(layer for layer in layers if pad.IsOnLayer(layer))
        if len(touched) < 2:
            board.Remove(via)
            REMOVED.append(via)
            removed.append(position)
    return removed


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else KICAD_DIR / 'cryocooler.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    print('vias removed:', remove_crowding_vias(board))
    close_current_path_link(board)
    print('J12 / R53 link added')
    print('Q2 gate track moved:', move_q2_gate_track(board))
    print('dangling vias removed:', remove_dangling_vias(board))
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print('island vias added:', reconnect_ground_islands(board))
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(path), board)


if __name__ == '__main__':
    main()
