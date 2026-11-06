"""Brings the routed board to the smaller analog packages: U5 OPA1655 and U9 OPA188
in SOT-23-5, U7 MCP4921 in DFN-8 (MC). Swaps the footprints in place, moves copper
to the renamed nets, rips the parts' own nets inside each box and trims dead ends.
Run `gen_pcb.py link`, then `gridroute.py` on the DRC report to close the open ends.

Usage: small_packages_board.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

import pcbnetlist
from spi_expander_board import KEEP, clear_copper_under, net_of, replace_part

MM = pcbnew.FromMM

# ref -> (x, y, rotation, bottom side)
SWAPPED = {
    'U5': (38.0, 31.0, 90, False),
    'U7': (55.0, 19.5, 90, False),
    'U9': (55.0, 31.0, 90, False),
}
# (x0, y0, x1, y1), nets ripped where a track end lies inside. Long trunks end at
# the box edge, so the router reconnects them.
RIP_BOXES = {
    'U5': (35.5, 27.6, 41.0, 35.0),
    'U7': (52.5, 16.5, 57.5, 22.5),
    'U9': (52.8, 28.0, 57.5, 34.0),
}
# DS22248 3.8: the exposed pad and VSS share a potential. The via is filled and
# capped, like the other fine-pitch ground pads (fabrication/README.md).
EP_VIA = ('U7', '9')
VIA_DIAMETER, VIA_DRILL = 0.45, 0.2
JOIN_TOLERANCE = 2000  # nm


def ends(item):
    if item.Type() == pcbnew.PCB_VIA_T:
        return [item.GetPosition()]
    return [item.GetStart(), item.GetEnd()]


def inside(point, box):
    return box[0] <= point.x / 1e6 <= box[2] and box[1] <= point.y / 1e6 <= box[3]


def remove(board, item):
    KEEP.append(item)
    board.Remove(item)


def net_map(board, pin_net):
    """Old net -> new net, read from the pads of the parts that stay."""
    names = {}
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if ref in SWAPPED:
            continue
        for pad in footprint.Pads():
            new = pin_net.get((ref, pad.GetNumber()))
            if new and pad.GetNetname():
                names[pad.GetNetname()] = new
    return names


def trim_dead_ends(board, nets, box):
    """Deletes track ends in the box that reach neither a pad nor other copper."""
    while True:
        removed = False
        tracks = [t for t in board.GetTracks() if t.GetNetname() in nets]
        pads = [p for p in board.GetPads() if p.GetNetname() in nets]
        for item in tracks:
            for point in ends(item):
                if not inside(point, box):
                    continue
                on_pad = any(
                    p.HitTest(point)
                    and (item.Type() == pcbnew.PCB_VIA_T or p.IsOnLayer(item.GetLayer()))
                    for p in pads
                )
                joined = any(
                    other is not item
                    and other.GetNetname() == item.GetNetname()
                    and any(
                        abs(q.x - point.x) < JOIN_TOLERANCE
                        and abs(q.y - point.y) < JOIN_TOLERANCE
                        for q in ends(other)
                    )
                    for other in tracks
                )
                if not on_pad and not joined:
                    remove(board, item)
                    removed = True
                    break
            if removed:
                break
        if not removed:
            return


def main():
    path = sys.argv[1]
    parts, nets = pcbnetlist.load_netlist()
    board = pcbnew.LoadBoard(path)
    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}
    renames = net_map(board, pin_net)

    ripped = {}
    for ref in SWAPPED:
        old = board.FindFootprintByReference(ref)
        ripped[ref] = {
            renames.get(pad.GetNetname(), pad.GetNetname())
            for pad in old.Pads()
            if pad.GetNetname() and not pad.GetNetname().startswith('unconnected')
        }
    swapped = {ref: replace_part(board, ref, parts[ref], spot) for ref, spot in SWAPPED.items()}

    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            name = pin_net.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(net_of(board, name))

    for item in list(board.GetTracks()):
        name = item.GetNetname()
        if not name or name in nets:
            continue
        if name in renames:
            item.SetNet(net_of(board, renames[name]))
        else:
            remove(board, item)

    for ref, box in RIP_BOXES.items():
        keep_nets = ripped[ref] & set(nets)
        for item in list(board.GetTracks()):
            if item.GetNetname() in keep_nets and any(inside(p, box) for p in ends(item)):
                remove(board, item)
        trim_dead_ends(board, keep_nets, box)
    for footprint in swapped.values():
        print('other-net copper cleared:', clear_copper_under(board, footprint))

    ref, number = EP_VIA
    pad = next(p for p in swapped[ref].Pads() if p.GetNumber() == number)
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pad.GetPosition())
    via.SetWidth(MM(VIA_DIAMETER))
    via.SetDrill(MM(VIA_DRILL))
    via.SetNet(pad.GetNet())
    board.Add(via)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
