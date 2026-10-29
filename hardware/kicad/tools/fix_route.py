"""Post-route clean-up for the board `gen_pcb.py route` writes.

Run with KiCad's bundled python after `gen_pcb.py route` and before
`link_usb_vbus.py`:
    .../Python.framework/Versions/Current/bin/python3 tools/fix_route.py [board]

Fixes the leftovers of Freerouting and the stitching / escape-via passes:
  * GND vias that short or crowd a track of another net (inner layers
    included) are removed, and co-located duplicates are collapsed;
  * GND vias inside a no-via keep-out (board or footprint rule area) or on a
    pad of another net (either side) are removed;
  * pour fragments left without a via get one at their roomiest point (or a
    short track from a stranded ground pad to a new via), and signal vias
    that touch copper on one layer only are removed;
  * pads whose thermal relief leads into an isolated pour island get their
    pour connection switched off (DRC "starved thermal").
"""

import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

KICAD_DIR = Path(__file__).resolve().parent.parent
KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
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


def relocate_pad_via(board, via, position, radius, clearance=0.25):
    """Moves a via inside a large pad of its own net to the point of the pad
    with the most room to foreign copper; False if no spot has `clearance`.
    """
    net = via.GetNetname()
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            box = pad.GetBoundingBox()
            width, height = mm(box.GetWidth()), mm(box.GetHeight())
            if pad.GetNetname() != net or min(width, height) < 1.5:
                continue
            left, top = mm(box.GetLeft()), mm(box.GetTop())
            right, bottom = mm(box.GetRight()), mm(box.GetBottom())
            if not (left <= position[0] <= right and top <= position[1] <= bottom):
                continue
            best = None
            margin = radius + 0.15
            x = left + margin
            while x <= right - margin:
                y = top + margin
                while y <= bottom - margin:
                    gap = foreign_gap(board, x, y, radius, net)
                    if best is None or gap > best[0]:
                        best = (gap, x, y)
                    y += 0.25
                x += 0.25
            if best and best[0] >= clearance:
                via.SetPosition(
                    pcbnew.VECTOR2I(pcbnew.FromMM(best[1]), pcbnew.FromMM(best[2]))
                )
                return True
    return False


def remove_crowding_vias(board):
    """Moves (inside a large pad) or removes GND vias within clearance of a
    foreign-net track on any layer, and collapses duplicate vias at one
    position. Returns the positions of the vias it changed.
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
                if relocate_pad_via(board, via, position, radius):
                    removed.append(position)
                    break
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


def remove_blocked_ground_vias(board):
    """Removes GND vias inside a no-via rule area (the board's or a
    footprint's) or overlapping a pad of another net on either side.
    Returns their positions.
    """
    areas = [zone for zone in board.Zones() if zone.GetIsRuleArea()]
    for footprint in board.GetFootprints():
        areas += [zone for zone in footprint.Zones() if zone.GetIsRuleArea()]
    areas = [zone for zone in areas if zone.GetDoNotAllowVias()]
    pads = [pad for footprint in board.GetFootprints() for pad in footprint.Pads()]
    removed = []
    for via in [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
        if via.GetNetname() not in GROUND_NETS:
            continue
        position = via.GetPosition()
        reach = via.GetWidth() // 2
        blocked = any(zone.Outline().Collide(position, reach) for zone in areas)
        if not blocked:
            for pad in pads:
                if pad.GetNetname() == via.GetNetname():
                    continue
                box = pad.GetBoundingBox()
                box.Inflate(reach)
                if box.Contains(position) and pad.HitTest(position, reach):
                    blocked = True
                    break
        if blocked:
            board.Remove(via)
            REMOVED.append(via)
            removed.append((round(mm(position.x), 2), round(mm(position.y), 2)))
    return removed


def foreign_gap(board, x, y, radius, net, layer=None):
    """Smallest gap in mm between a via of the given radius at (x, y) and
    copper of any other net (tracks on every layer, vias, pads); with
    `layer`, only copper on that layer (for a track there).
    """
    gap = 1e9
    for item in board.GetTracks():
        if item.GetNetname() == net:
            continue
        if layer is not None and not item.IsOnLayer(layer):
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
            if layer is not None and not pad.IsOnLayer(layer):
                continue
            box = pad.GetBoundingBox()
            delta_x = max(mm(box.GetLeft()) - x, x - mm(box.GetRight()), 0.0)
            delta_y = max(mm(box.GetTop()) - y, y - mm(box.GetBottom()), 0.0)
            gap = min(gap, math.hypot(delta_x, delta_y) - radius)
    return gap


def reconnect_ground_islands(board, diameter=0.5, drill=0.3, margin=0.2):
    """Gives each outer-layer ground pour fragment that has no via (after the
    removals above) one via at its roomiest point, clear of foreign copper.
    """
    added = []
    radius = diameter / 2
    for zone in list(board.Zones()):
        if (
            zone.GetIsRuleArea()
            or zone.GetNetname() not in GROUND_NETS
            or zone.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu)
        ):
            continue
        net = zone.GetNetname()
        vias = [
            item
            for item in board.GetTracks()
            if item.Type() == pcbnew.PCB_VIA_T and item.GetNetname() == net
        ]
        filled = zone.GetFilledPolysList(zone.GetLayer())
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


def link_stranded_ground_pads(board, diameter=0.45, drill=0.2, width=0.25):
    """For each outer-layer ground pour fragment still without a via, joins
    one of its ground pads by a short track on that layer to a new via within 2 mm, at the
    first spot where both clear other nets (0.15 mm). Returns the vias.
    """
    added = []
    radius = diameter / 2
    for zone in list(board.Zones()):
        if zone.GetIsRuleArea() or zone.GetNetname() not in GROUND_NETS:
            continue
        if zone.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
            continue
        net = zone.GetNetname()
        vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == net]
        filled = zone.GetFilledPolysList(zone.GetLayer())
        for index in range(filled.OutlineCount()):
            if any(filled.Contains(via.GetPosition(), index) for via in vias):
                continue
            pads = [
                pad
                for footprint in board.GetFootprints()
                for pad in footprint.Pads()
                if pad.GetNetname() == net
                and pad.IsOnLayer(zone.GetLayer())
                and filled.Contains(pad.GetPosition(), index)
            ]
            spot = None
            for pad in pads:
                pad_x, pad_y = mm(pad.GetPosition().x), mm(pad.GetPosition().y)
                candidates = sorted(
                    (
                        (pad_x + 0.1 * step_x, pad_y + 0.1 * step_y)
                        for step_x in range(-20, 21)
                        for step_y in range(-20, 21)
                    ),
                    key=lambda point: math.dist(point, (pad_x, pad_y)),
                )
                for via_x, via_y in candidates:
                    if foreign_gap(board, via_x, via_y, radius, net) < 0.15:
                        continue
                    length = math.dist((pad_x, pad_y), (via_x, via_y))
                    steps = max(1, int(length / 0.1))
                    points = [
                        (
                            pad_x + (via_x - pad_x) * step / steps,
                            pad_y + (via_y - pad_y) * step / steps,
                        )
                        for step in range(steps + 1)
                    ]
                    # the part of the track on the pad adds no copper
                    points = [
                        point
                        for point in points
                        if not pad.HitTest(
                            pcbnew.VECTOR2I(pcbnew.FromMM(point[0]), pcbnew.FromMM(point[1]))
                        )
                    ]
                    if all(
                        foreign_gap(board, *point, width / 2, net, zone.GetLayer()) >= 0.15
                        for point in points
                    ):
                        spot = (pad, via_x, via_y, pad_x, pad_y)
                        break
                if spot:
                    break
            if spot is None:
                print('no spot to link a stranded ground pad near', [p.GetParentFootprint().GetReference() for p in pads])
                continue
            pad, via_x, via_y, pad_x, pad_y = spot
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(via_x), pcbnew.FromMM(via_y)))
            via.SetWidth(pcbnew.FromMM(diameter))
            via.SetDrill(pcbnew.FromMM(drill))
            via.SetNet(pad.GetNet())
            board.Add(via)
            if math.dist((pad_x, pad_y), (via_x, via_y)) > 1e-6:
                add_track(board, net, [(pad_x, pad_y), (via_x, via_y)], width, zone.GetLayer())
            vias.append(via)
            added.append((pad.GetParentFootprint().GetReference(), pad.GetNumber(), round(via_x, 2), round(via_y, 2)))
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
        # a track counts if it reaches the via pad, not only its centre
        reach = mm(via.GetWidth()) / 2
        for item in board.GetTracks():
            if item.Type() != pcbnew.PCB_TRACE_T or item.GetNetname() != via.GetNetname():
                continue
            start = (mm(item.GetStart().x), mm(item.GetStart().y))
            end = (mm(item.GetEnd().x), mm(item.GetEnd().y))
            if segment_distance(position, start, end) < reach + mm(item.GetWidth()) / 2:
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


def drc_violations(path, kind):
    """Error-level DRC violations of one type for the board file."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'drc.json'
        subprocess.run(
            [
                KICAD_CLI, 'pcb', 'drc', '--format', 'json',
                '--severity-error', '--output', str(report), str(path),
            ],
            check=False,
            capture_output=True,
        )
        data = json.loads(report.read_text())
    return [v for v in data.get('violations', []) if v.get('type') == kind]


def nudge_crowded_tracks(board, path, margin=0.005):
    """Moves a track segment that DRC finds too close to a track of another
    net (usually one Freerouting squeezed and gen_pcb then widened) away by
    the shortfall, dragging the ends of the same-net segments it joins.
    Returns the nets nudged.
    """
    tracks = {
        item.m_Uuid.AsString(): item
        for item in board.GetTracks()
        if item.Type() == pcbnew.PCB_TRACE_T
    }
    nudged = []
    moved = set()
    for violation in drc_violations(path, 'clearance'):
        found = [tracks.get(item.get('uuid')) for item in violation.get('items', [])]
        if len(found) != 2 or None in found:
            continue
        match = re.search(r'clearance ([\d.]+) mm; actual ([\d.]+) mm', violation['description'])
        if not match:
            continue
        shortfall = float(match.group(1)) - float(match.group(2)) + margin
        mover, other = sorted(found, key=lambda t: t.GetWidth())
        if mover.m_Uuid.AsString() in moved:
            continue  # DRC lists a crowded pair once per segment end
        moved.add(mover.m_Uuid.AsString())
        start = (mm(mover.GetStart().x), mm(mover.GetStart().y))
        end = (mm(mover.GetEnd().x), mm(mover.GetEnd().y))
        middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        other_start = (mm(other.GetStart().x), mm(other.GetStart().y))
        other_end = (mm(other.GetEnd().x), mm(other.GetEnd().y))
        # the point of the other segment nearest the mover's middle
        delta = (other_end[0] - other_start[0], other_end[1] - other_start[1])
        length_sq = delta[0] ** 2 + delta[1] ** 2 or 1e-12
        ratio = max(0.0, min(1.0, (
            (middle[0] - other_start[0]) * delta[0] + (middle[1] - other_start[1]) * delta[1]
        ) / length_sq))
        nearest = (other_start[0] + ratio * delta[0], other_start[1] + ratio * delta[1])
        away = (middle[0] - nearest[0], middle[1] - nearest[1])
        norm = math.hypot(*away) or 1.0
        shift = (away[0] / norm * shortfall, away[1] / norm * shortfall)
        for old in (start, end):
            new = pcbnew.VECTOR2I(pcbnew.FromMM(old[0] + shift[0]), pcbnew.FromMM(old[1] + shift[1]))
            for track in tracks.values():
                if track.GetNetname() != mover.GetNetname() or track.GetLayer() != mover.GetLayer():
                    continue
                if math.dist(old, (mm(track.GetStart().x), mm(track.GetStart().y))) < 1e-3:
                    track.SetStart(new)
                if math.dist(old, (mm(track.GetEnd().x), mm(track.GetEnd().y))) < 1e-3:
                    track.SetEnd(new)
        nudged.append(mover.GetNetname())
    return nudged


def starved_thermal_pads(path):
    """(reference, pad number) of every pad DRC reports with a starved thermal
    relief (spokes into an isolated pour island).
    """
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'drc.json'
        subprocess.run(
            [
                KICAD_CLI, 'pcb', 'drc', '--format', 'json',
                '--severity-error', '--output', str(report), str(path),
            ],
            check=False,
            capture_output=True,
        )
        data = json.loads(report.read_text())
    pads = []
    for violation in data.get('violations', []):
        if violation.get('type') != 'starved_thermal':
            continue
        for item in violation.get('items', []):
            match = re.search(r'pad (\S+) \[.*\] of (\S+)', item.get('description', ''))
            if match:
                pads.append((match.group(2), match.group(1)))
    return pads


def disconnect_starved_pads(board, pads):
    """Turns the pour connection off for pads whose only spokes lead into an
    isolated island (they are wired by tracks).
    """
    done = []
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if (footprint.GetReference(), pad.GetNumber()) in pads:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
                done.append((footprint.GetReference(), pad.GetNumber()))
    return done


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else KICAD_DIR / 'cryocooler.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    print('vias removed:', remove_crowding_vias(board))
    print('blocked GND vias removed:', remove_blocked_ground_vias(board))
    print('dangling vias removed:', remove_dangling_vias(board))
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print('island vias added:', reconnect_ground_islands(board))
    filler.Fill(board.Zones())
    # the fine-pitch via size (cryocooler.kicad_dru) for the tight fragments
    print('small island vias added:', reconnect_ground_islands(board, 0.45, 0.2, 0.1))
    filler.Fill(board.Zones())
    print('stranded ground pads linked:', link_stranded_ground_pads(board))
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(path), board)
    nudged = nudge_crowded_tracks(board, path)
    if nudged:
        print('tracks nudged clear:', nudged)
        filler.Fill(board.Zones())
        pcbnew.SaveBoard(str(path), board)
    starved = starved_thermal_pads(path)
    if starved:
        print('pour connection off for:', disconnect_starved_pads(board, starved))
        filler.Fill(board.Zones())
        pcbnew.SaveBoard(str(path), board)


if __name__ == '__main__':
    main()
