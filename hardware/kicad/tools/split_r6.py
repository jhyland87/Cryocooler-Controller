"""Splits the sine gain feedback into R6 (47k) + R170 (2.4k) on the routed board:
output -> R170 -> R6 -> inverting input, with C121 still across both.

The coordinates fit the route committed with this file. Run `gen_pcb.py link`
and `silk_fix.py` afterwards (no room for either reference, so it hides both).

Usage: split_r6.py board.kicad_pcb (edits in place, refills zones)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
OUTPUT = 'Net-(C121-Pad2)'
MIDDLE = 'Net-(R170-Pad1)'
FOOTPRINT_LIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Resistor_SMD.pretty'
# output copper that met R6 pad 2 and R8 pad 1 there
OLD_OUTPUT_POINTS = ((35.355, 33.475), (34.776, 32.896), (35.355, 34.485), (35.845, 34.975))


def near(point, spots, tolerance=0.02):
    return any(abs(point.x / 1e6 - x) < tolerance and abs(point.y / 1e6 - y) < tolerance
               for x, y in spots)


def add_track(board, net, points):
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        segment = pcbnew.PCB_TRACK(board)
        segment.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1)))
        segment.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
        segment.SetWidth(MM(0.25))
        segment.SetLayer(pcbnew.B_Cu)
        segment.SetNet(net)
        board.Add(segment)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    removed = [item for item in board.GetTracks()
               if item.Type() == pcbnew.PCB_TRACE_T and item.GetNetname() == OUTPUT
               and item.GetLayer() == pcbnew.B_Cu
               and near(item.GetStart(), OLD_OUTPUT_POINTS) and near(item.GetEnd(), OLD_OUTPUT_POINTS)]
    assert len(removed) == 4, len(removed)
    for item in removed:
        board.Remove(item)

    middle = pcbnew.NETINFO_ITEM(board, MIDDLE)
    board.Add(middle)
    output = board.FindNet(OUTPUT)

    r6 = board.FindFootprintByReference('R6')
    r6.SetValue('47k')
    pads = {pad.GetNumber(): pad for pad in r6.Pads()}
    pads['2'].SetNet(middle)

    r170 = pcbnew.FootprintLoad(FOOTPRINT_LIB, 'R_0402_1005Metric')
    r170.SetReference('R170')
    r170.SetValue('2.4k')
    r170.SetPosition(pcbnew.VECTOR2I(MM(34.4), MM(34.465)))
    board.Add(r170)
    r170.Flip(r170.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    r170.SetOrientationDegrees(270)
    r170.Reference().SetTextSize(r6.Reference().GetTextSize())
    r170.Reference().SetTextThickness(r6.Reference().GetTextThickness())
    r170.Value().SetVisible(False)
    for pad in r170.Pads():
        pad.SetNet(middle if pad.GetNumber() == '1' else output)
        print('R170 pad', pad.GetNumber(), pad.GetPosition().x / 1e6, pad.GetPosition().y / 1e6)
    top = {pad.GetNumber(): pad.GetPosition().y for pad in r170.Pads()}
    assert top['1'] < top['2'], 'pad 1 must face R6'

    add_track(board, middle, [(34.4, 33.955), (34.875, 33.955), (35.355, 33.475)])
    add_track(board, output, [(34.4, 34.975), (35.845, 34.975)])
    add_track(board, output, [(34.4, 34.975), (33.75, 34.975), (33.75, 32.915), (34.272, 32.393)])

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
