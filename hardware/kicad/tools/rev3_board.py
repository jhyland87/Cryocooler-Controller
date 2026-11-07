"""Brings the routed UCS 145-125 board to the rev 3 schematic: removes retired parts, swaps
changed footprints, places new parts, syncs pad nets, renames nets whose copper still
fits, and rips copper on nets that changed. Close the open ends with `gen_pcb.py link`,
`gridroute.py` on the DRC report, then the later rev 3 steps in hardware/HANDOFF_rev3.md.

Parts use the reference numbers from before the rev 3 renumber, so run this before
`renumber_refs.py board`. It was run once on the rev 2 board; the placement tables are
kept as the record of what moved.

Usage: rev3_board.py in.kicad_pcb out.kicad_pcb
"""
import json
import math
import sys
from pathlib import Path

import pcbnew

import pcbnetlist
from spi_expander_board import KEEP, add_part, clear_copper_under, net_of, place

MM = pcbnew.FromMM

# Nets whose copper still fits one new net.
RENAMES = {
    'Net-(J10-Pin_1)': 'RTD_1',
    'Net-(J10-Pin_2)': 'RTD_2',
    'Net-(J10-Pin_3)': 'RTD_3',
    'Net-(J10-Pin_4)': 'RTD_4',
    'ISO_3V3': 'ISO_5V',
    'Net-(D7-K)': 'INA239_ALERT',
    'Net-(U11-~{INT})': 'PWR_INT',
    'MCP4921_CS': 'AD5453_SYNC',
    'Net-(Q1-G)': 'Net-(U11-~{EN})',
}
CLEARANCE = 0.16
PLACEMENT_FILE = Path(__file__).with_name('rev3_placement.json')


def load_placement():
    """Returns ref -> [x, y, rotation, bottom], ripped boxes and removed zones."""
    return json.loads(PLACEMENT_FILE.read_text())


def ends(item):
    if item.Type() == pcbnew.PCB_VIA_T:
        return [item.GetPosition()]
    return [item.GetStart(), item.GetEnd()]


def inside(point, box):
    return box[0] <= point.x / 1e6 <= box[2] and box[1] <= point.y / 1e6 <= box[3]


def drop(board, item):
    KEEP.append(item)
    board.Remove(item)


def remove_retired(board, parts):
    for footprint in list(board.GetFootprints()):
        ref = footprint.GetReference()
        if ref and ref not in parts:
            drop(board, footprint)


def swap_footprints(board, parts, spots):
    """Replaces every part whose footprint changed; keeps its spot unless spots says."""
    swapped = {}
    for footprint in list(board.GetFootprints()):
        ref = footprint.GetReference()
        if not ref or ref not in parts:
            continue
        name = parts[ref]['footprint'].split(':')[-1]
        if str(footprint.GetFPID().GetLibItemName()) == name:
            continue
        spot = spots.get(ref, [
            footprint.GetX() / 1e6, footprint.GetY() / 1e6,
            footprint.GetOrientationDegrees(), footprint.IsFlipped()])
        drop(board, footprint)
        swapped[ref] = add_part(board, ref, parts[ref], spot)
    return swapped


def rip(board, spec):
    """Removes copper: spec is [box, nets]; nets '*' means every net but GND."""
    box, nets = spec
    for item in list(board.GetTracks()):
        name = item.GetNetname()
        wanted = (name not in ('GND', 'ISO_GND')) if nets == '*' else name in nets
        if wanted and any(inside(point, box) for point in ends(item)):
            drop(board, item)


def segment_gap(point, start, end):
    """Distance in nm from a point to a segment."""
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length = delta_x * delta_x + delta_y * delta_y
    ratio = 0 if not length else max(0, min(1, (
        (point[0] - start[0]) * delta_x + (point[1] - start[1]) * delta_y) / length))
    return math.hypot(point[0] - start[0] - ratio * delta_x, point[1] - start[1] - ratio * delta_y)


def clear_along(board, net, layer, width, start, end):
    """Rips other nets' copper within clearance of a new track."""
    margin = width / 2 + MM(CLEARANCE)
    steps = max(1, int(math.dist(start, end) / MM(0.05)))
    samples = [(start[0] + (end[0] - start[0]) * step / steps,
                start[1] + (end[1] - start[1]) * step / steps) for step in range(steps + 1)]
    for item in list(board.GetTracks()):
        if item.GetNetname() == net:
            continue
        if item.Type() == pcbnew.PCB_VIA_T:
            where = item.GetPosition()
            reach = margin + item.GetWidth(pcbnew.F_Cu) / 2
            hit = any(math.dist(sample, (where.x, where.y)) < reach for sample in samples)
        else:
            if item.GetLayer() != layer:
                continue
            first, second = item.GetStart(), item.GetEnd()
            reach = margin + item.GetWidth() / 2
            hit = any(segment_gap(sample, (first.x, first.y), (second.x, second.y)) < reach
                      for sample in samples)
        if hit:
            drop(board, item)


def add_copper(board, plan):
    """Draws the hand-placed power copper, clearing whatever crosses it."""
    for net, layer_name, width, points in plan['tracks']:
        layer = board.GetLayerID(layer_name)
        for first, second in zip(points, points[1:]):
            start = (MM(first[0]), MM(first[1]))
            end = (MM(second[0]), MM(second[1]))
            clear_along(board, net, layer, MM(width), start, end)
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(*start))
            track.SetEnd(pcbnew.VECTOR2I(*end))
            track.SetLayer(layer)
            track.SetWidth(MM(width))
            track.SetNet(net_of(board, net))
            board.Add(track)
            KEEP.append(track)
    for net, pos_x, pos_y, diameter, drill in plan['vias']:
        spot = (MM(pos_x), MM(pos_y))
        clear_along(board, net, board.GetLayerID('F.Cu'), MM(diameter), spot, spot)
        clear_along(board, net, board.GetLayerID('In2.Cu'), MM(diameter), spot, spot)
        clear_along(board, net, board.GetLayerID('B.Cu'), MM(diameter), spot, spot)
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(*spot))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetWidth(MM(diameter))
        via.SetDrill(MM(drill))
        via.SetNet(net_of(board, net))
        board.Add(via)
        KEEP.append(via)


def main():
    source, target = sys.argv[1:3]
    parts, nets = pcbnetlist.load_netlist()
    plan = load_placement()
    spots = plan['parts']
    board = pcbnew.LoadBoard(source)
    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}

    remove_retired(board, parts)
    swapped = swap_footprints(board, parts, spots)
    present = {footprint.GetReference() for footprint in board.GetFootprints()}
    for ref in sorted(set(parts) - present):
        add_part(board, ref, parts[ref], spots.get(ref, [125.0, 50.0, 0, False]))
    for ref, spot in spots.items():
        place(board.FindFootprintByReference(ref), *spot)

    for zone in list(board.Zones()):
        name = zone.GetNetname()
        box = plan['removed_plus3v3_box']
        first = zone.Outline().CVertex(0)
        old_tab_pour = name == '+3V3' and zone.GetLayer() == pcbnew.F_Cu and inside(first, box)
        if name in plan['removed_zones'] or old_tab_pour:
            drop(board, zone)

    for item in list(board.GetTracks()):
        name = item.GetNetname()
        name = RENAMES.get(name, name)
        if name not in nets:
            drop(board, item)
        else:
            item.SetNet(net_of(board, name))
    for spec in plan['rips']:
        rip(board, spec)

    no_net = board.FindNet(0)
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if ref not in parts:
            continue
        footprint.SetValue(parts[ref]['value'])
        for pad in footprint.Pads():
            name = pin_net.get((ref, pad.GetNumber()))
            pad.SetNet(net_of(board, name) if name else no_net)

    add_copper(board, plan)
    cut = set()
    for ref in sorted(set(spots) | set(swapped) | (set(parts) - present)):
        cut |= clear_copper_under(board, board.FindFootprintByReference(ref))
    print('cut by moved parts:', sorted(cut))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(target)


if __name__ == '__main__':
    main()
