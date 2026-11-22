"""Adds the rev 6.1 headers to the routed rev 6 board: J41 Qwiic / STEMMA QT,
J42 CAN pass-through and JP20 (R516's 0 R link). Only the R516 to CAN_H link and
the GND stitching vias under J42 and JP20 are removed; the rest of the copper stays. Run
`gen_pcb.py link` and DRC.

Usage: rev61_headers_board.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

import pcbmodels
import pcbnetlist
from spi_expander_board import KEEP, add_part, clear_copper_under, net_of

# ref -> (x, y, rotation, bottom side)
NEW_PARTS = {
    'J41': (97.5, 52.0, 90, False),
    'J42': (48.0, 6.5, 270, False),
    'JP20': (59.1, 10.0, 180, False),
}
# new copper drawn by hand (net, layer, points[, width]). JP20: R516 pad 1 to JP20 pad 2,
# and JP20 pad 1 to the CAN_H via that U52 pin 7 already reaches on B.Cu
LINKS = (
    ('Net-(JP20-B)', 'F.Cu', ((57.45, 8.325), (57.45, 9.175), (58.275, 10.0))),
    ('/Display/CAN_H', 'F.Cu', ((59.925, 10.0), (58.725, 8.8), (58.725, 8.208))),
    # J42 pin 1 to R516 pin 2 (CAN_L), on top
    ('/Display/CAN_L', 'F.Cu', ((47.5, 4.5), (56.55, 4.5), (57.45, 5.4))),
    # J42 pin 2 to J15 pin 3 (CAN_H), on top, clear of U52's corner
    ('/Display/CAN_H', 'F.Cu', ((47.5, 6.5), (52.0, 6.5), (52.0, 12.0), (55.0, 15.0), (55.0, 18.5))),
    # J41 (right of J40): SCL over J40's mounting pad into pin 4, SDA under J40
    # and up the right side into pin 3
    ('/AUX Header/AUX13_HDR', 'F.Cu', ((89.0, 50.0), (89.0, 48.7), (89.5, 48.2), (98.325, 48.2),
                                       (98.825, 48.7), (98.825, 50.5))),
    ('/AUX Header/AUX11_HDR', 'F.Cu', ((87.0, 55.0), (87.0, 55.9), (87.3, 56.2), (100.7, 56.2),
                                       (101.0, 55.9), (101.0, 51.8), (100.7, 51.5), (98.825, 51.5))),
    # J41 +3V3: the plane doesn't reach here, so a via to R695's +3V3 pad on B.Cu
    ('+3V3', 'F.Cu', ((98.825, 52.5), (97.55, 52.5), (97.2, 52.15)), 0.3),
    ('+3V3', 'B.Cu', ((97.2, 52.15), (96.2, 51.15), (90.02, 51.15)), 0.3),
)
VIAS = (('+3V3', (97.2, 52.15)),)
# (net, layer, box): tracks (or vias, layer None) with an end in the box are removed
RIP = (
    ('/Display/CAN_H', 'F.Cu', (57.3, 8.0, 58.6, 8.5)),
    ('GND', None, (44.2, 0.26, 52.8, 12.1)),
    ('GND', None, (57.3, 9.4, 57.6, 9.7)),
)

# silk labels in the board's label style (0.8 mm, 0.1 mm stroke), replacing the
# new parts' reference fields: text -> (x, y, angle)
LABELS = {
    'J41 QWIIC': (101.2, 52.0, 90),
    'JP20': (62.25, 10.0, 0),
    'J42 CAN': (48.0, 12.75, 0),
}

# existing board text moved out of J42's way: (text, layer, old x, old y) -> new x, y.
# J15's pin names go below its pins (top edge 0.3 mm under the pads) with the
# connector name beside them; the section title and R515's label move clear of J42.
J15_NAMES_TOP = 21.55
MOVES = {
    ('DISPLAY', 'F.Silkscreen', 44.6, 1.5): (53.0, 1.5),
    ('DISPLAY', 'B.Silkscreen', 44.6, 1.5): (53.0, 1.5),
    ('R515', 'F.Silkscreen', 51.54, 7.64): (54.04, 10.1),
    ('J15 DISPLAY', 'F.Silkscreen', 56.0, 22.2): (66.0, 22.2),
}
J15_NAMES = {'GND': 51.0, '12V': 53.0, 'CANH': 55.0, 'CANL': 57.0, 'BTN': 59.0, 'RST': 61.0}


def ends(item):
    if item.Type() == pcbnew.PCB_VIA_T:
        return [item.GetPosition()]
    return [item.GetStart(), item.GetEnd()]


def inside(point, box):
    return box[0] <= point.x / 1e6 <= box[2] and box[1] <= point.y / 1e6 <= box[3]


def move_texts(board):
    def near(point, x, y):
        return abs(point.x / 1e6 - x) < 0.05 and abs(point.y / 1e6 - y) < 0.05

    moved = set()
    for item in board.GetDrawings():
        if item.Type() != pcbnew.PCB_TEXT_T:
            continue
        text, layer, where = item.GetText(), board.GetLayerName(item.GetLayer()), item.GetPosition()
        for (old_text, old_layer, x, y), (new_x, new_y) in MOVES.items():
            if text == old_text and layer == old_layer and near(where, x, y):
                item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(new_x), pcbnew.FromMM(new_y)))
                moved.add((old_text, old_layer))
        column = J15_NAMES.get(text)
        if column is not None and layer == 'F.Silkscreen' and near(where, column, where.y / 1e6) \
                and 10.0 < where.y / 1e6 < 13.0:
            length = item.GetBoundingBox().GetHeight() / 1e6
            item.SetPosition(pcbnew.VECTOR2I(where.x, pcbnew.FromMM(J15_NAMES_TOP + length / 2)))
            moved.add((text, 'J15'))
    expected = {(t, l) for t, l, _, _ in MOVES} | {(t, 'J15') for t in J15_NAMES}
    assert moved == expected, expected - moved


def main():
    path = sys.argv[1]
    parts, nets = pcbnetlist.load_netlist()
    board = pcbnew.LoadBoard(path)
    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}

    new = [add_part(board, ref, parts[ref], spot) for ref, spot in NEW_PARTS.items()]
    for footprint in new:
        pcbmodels.attach_missing_models(footprint)
    for ref in ('J15', 'J40'):
        board.FindFootprintByReference(ref).SetValue(parts[ref]['value'])
    for footprint in new + [board.FindFootprintByReference('R516')]:
        for pad in footprint.Pads():
            name = pin_net.get((footprint.GetReference(), pad.GetNumber()))
            if name:
                pad.SetNet(net_of(board, name))

    for net, layer, box in RIP:
        for item in list(board.GetTracks()):
            if item.GetNetname() != net or not any(inside(p, box) for p in ends(item)):
                continue
            is_via = item.Type() == pcbnew.PCB_VIA_T
            if is_via != (layer is None) or (layer and board.GetLayerName(item.GetLayer()) != layer):
                continue
            print('removed', net, item.GetClass(), [(p.x / 1e6, p.y / 1e6) for p in ends(item)])
            KEEP.append(item)
            board.Remove(item)

    for net, layer, points, *width in LINKS:
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start[0]), pcbnew.FromMM(start[1])))
            track.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end[0]), pcbnew.FromMM(end[1])))
            track.SetWidth(pcbnew.FromMM(width[0] if width else 0.15))
            track.SetLayer(board.GetLayerID(layer))
            track.SetNet(net_of(board, net))
            board.Add(track)
            KEEP.append(track)

    for net, (x, y) in VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        via.SetWidth(pcbnew.FromMM(0.45))
        via.SetDrill(pcbnew.FromMM(0.2))
        via.SetNet(net_of(board, net))
        board.Add(via)
        KEEP.append(via)

    for footprint in new:
        footprint.Reference().SetVisible(False)
    move_texts(board)
    for text, (x, y, angle) in LABELS.items():
        label = pcbnew.PCB_TEXT(board)
        label.SetText(text)
        label.SetLayer(pcbnew.F_SilkS)
        label.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        label.SetTextAngleDegrees(angle)
        label.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.7), pcbnew.FromMM(0.8)))
        label.SetTextThickness(pcbnew.FromMM(0.1))
        board.Add(label)
        KEEP.append(label)

    cleared = set()
    for footprint in new:
        cleared |= clear_copper_under(board, footprint)
    print('tracks cleared on nets:', sorted(cleared))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
