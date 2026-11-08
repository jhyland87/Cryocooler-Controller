"""Puts R92 (sine gain trim) and the new R96 (DAC gain trim, RFB to the OPA188 output) on
the R_1206_or_Bourns_3313J land, front side, under U5 and U9. Either part fits: a 1206
resistor on the two end pads, or a 3313J trimmer whose wiper pad is tied to pad 2.

C86 now goes from IOUT1 to the output (AD5453 Figure 44), so the output net takes C86,
U9 pin 1 and R40, and RFB keeps only U6 pin 8 and R96. R40's back-side feed used a via
beside U6 pin 8; it now drops in beside C86 instead. Run `gen_pcb.py link` and
`mask_labels.py` afterwards.

Usage: trim_lands_board.py board.kicad_pcb (edits in place, run it once)
"""
import sys
from pathlib import Path

import pcbnew

LIB = str(Path(__file__).resolve().parents[1] / 'lib' / 'cryocooler.pretty')
FOOTPRINT = 'R_1206_or_Bourns_3313J'
MM = pcbnew.FromMM
KEEP = []  # removed and added items stay referenced, or SWIG frees them under the board

RFB = 'Net-(U6-RFB)'
OUT = 'Net-(C86-Pad2)'
OPA_OUT = 'Net-(C85-Pad2)'
GAIN_TAP = 'Net-(R35-Pad2)'

# (ref, value, origin, pad 1 net, pad 2 net)
PARTS = (
    ('R92', '3.6k', (36.0, 37.6), GAIN_TAP, OPA_OUT),
    ('R96', '0', (55.5, 36.2), RFB, OUT),
)

# (net, ((x, y), (x, y))) segments removed, matched by both ends
RIP_TRACKS = (
    # old R92 pad 2 stub and the U5 output run to its via
    (OPA_OUT, ((34.4, 34.975), (34.975, 34.4))),
    (OPA_OUT, ((34.975, 34.4), (35.0, 34.4))),
    (OPA_OUT, ((35.0, 34.4), (37.0, 32.4))),
    (OPA_OUT, ((37.0, 32.4), (37.0, 32.2))),
    (OPA_OUT, ((37.0, 32.2), (37.05, 32.15))),
    # U6 pin 8 to C86, and the via beside pin 8 that fed R40
    (RFB, ((51.3, 32.45), (51.275, 32.45))),
    (RFB, ((51.65, 32.1), (51.3, 32.45))),
    (RFB, ((52.1, 32.1), (51.65, 32.1))),
    (RFB, ((52.1, 32.08), (52.1, 32.1))),
    (RFB, ((52.7, 31.48), (52.1, 32.08))),
    (RFB, ((51.45, 32.6), (51.3, 32.45))),
    (RFB, ((51.25, 32.4), (51.45, 32.6))),
    (RFB, ((51.25, 32.3), (51.25, 32.4))),
)
RIP_VIAS = ((OPA_OUT, 35.0, 34.4), (RFB, 51.45, 32.6), ('GND', 36.0, 36.0))
# the C86 -> U9 pin 1 run and R40's back-side feed change from RFB to the output net
RENET_BOX = (48.0, 28.0, 54.2, 32.4)

TRACKS = (
    # R92: R35 tap through a via at the old pad 1, U5 output down from its via, clear
    # of U5's mask label
    (GAIN_TAP, pcbnew.F_Cu, 0.2, ((34.4, 33.955), (34.4, 37.0))),
    (OPA_OUT, pcbnew.F_Cu, 0.2, ((37.35, 32.25), (36.9, 32.7), (36.9, 37.0))),
    (OPA_OUT, pcbnew.F_Cu, 0.25, ((36.0, 40.5), (37.35, 40.5), (37.35, 38.2))),
    # R96: RFB down past D16, output under U9's label, wiper tie, R40 feed via beside C86
    (RFB, pcbnew.F_Cu, 0.2, ((51.275, 32.45), (51.275, 32.9), (53.6, 35.225),
                             (53.6, 35.6))),
    (OUT, pcbnew.F_Cu, 0.2, ((54.05, 32.1375), (54.05, 34.9), (56.85, 34.9),
                             (56.85, 35.6))),
    (OUT, pcbnew.F_Cu, 0.25, ((55.5, 39.1), (56.85, 39.1), (56.85, 36.8))),
    (OUT, pcbnew.B_Cu, 0.2, ((51.25, 32.3), (51.8, 31.75), (52.05, 31.75))),
    (OUT, pcbnew.F_Cu, 0.2, ((52.05, 31.75), (52.32, 31.48), (52.7, 31.48))),
)
VIAS = ((GAIN_TAP, 34.4, 33.955), (OUT, 52.05, 31.75))


def point(item_point):
    return round(item_point.x / 1e6, 4), round(item_point.y / 1e6, 4)


def net(board, name):
    found = board.FindNet(name)
    if found is None:
        found = pcbnew.NETINFO_ITEM(board, name)
        board.Add(found)
        KEEP.append(found)
    return found


def rip(board):
    """Removes every listed segment and via (duplicates included); fails if one is missing."""
    wanted = {(name, frozenset(ends)) for name, ends in RIP_TRACKS}
    found = set()
    for item in list(board.GetTracks()):
        if item.Type() == pcbnew.PCB_VIA_T:
            key = (item.GetNetname(), *point(item.GetPosition()))
            if key not in RIP_VIAS:
                continue
        else:
            key = (item.GetNetname(), frozenset((point(item.GetStart()), point(item.GetEnd()))))
            if key not in wanted:
                continue
        found.add(key)
        KEEP.append(item)
        board.Remove(item)
    missing = (wanted | set(RIP_VIAS)) - found
    if missing:
        raise SystemExit(f'not found: {missing}')


def renet(board):
    left, top, right, bottom = RENET_BOX
    output = net(board, OUT)
    for item in board.GetTracks():
        if item.GetNetname() != RFB:
            continue
        ends = [item.GetPosition()] if item.Type() == pcbnew.PCB_VIA_T else [
            item.GetStart(), item.GetEnd()]
        if all(left <= x_mm <= right and top <= y_mm <= bottom
               for x_mm, y_mm in map(point, ends)) and point(ends[0]) != (51.275, 32.45):
            item.SetNet(output)
    for ref, number in (('U9', '1'), ('C86', '2'), ('R40', '1')):
        board.FindFootprintByReference(ref).FindPadByNumber(number).SetNet(output)


def place(board, ref, value, origin, first_net, second_net):
    old = board.FindFootprintByReference(ref)
    footprint = pcbnew.FootprintLoad(LIB, FOOTPRINT)
    footprint.SetReference(ref)
    footprint.SetValue(value)
    footprint.SetPosition(pcbnew.VECTOR2I(MM(origin[0]), MM(origin[1])))
    if old is not None:
        footprint.Reference().SetVisible(old.Reference().IsVisible())
        KEEP.append(old)
        board.Remove(old)
    else:
        footprint.Reference().SetVisible(False)
    board.Add(footprint)
    KEEP.append(footprint)
    for pad in footprint.Pads():
        pad.SetNet(net(board, first_net if pad.GetNumber() == '1' else second_net))


def add_copper(board):
    for name, layer, width, points in TRACKS:
        for first, second in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(MM(first[0]), MM(first[1])))
            track.SetEnd(pcbnew.VECTOR2I(MM(second[0]), MM(second[1])))
            track.SetLayer(layer)
            track.SetWidth(MM(width))
            track.SetNet(net(board, name))
            board.Add(track)
            KEEP.append(track)
    for name, x_mm, y_mm in VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetWidth(MM(0.45))
        via.SetDrill(MM(0.2))
        via.SetNet(net(board, name))
        board.Add(via)
        KEEP.append(via)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    rip(board)
    renet(board)
    for part in PARTS:
        place(board, *part)
    add_copper(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    print('placed', ', '.join(part[0] for part in PARTS))


if __name__ == '__main__':
    main()
