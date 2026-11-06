#!/usr/bin/env python3
"""Hand-places the labels around U32, after silk_fix.py has hidden the ones it
could not fit. Usage: cs_decoder_silk.py board.kicad_pcb
"""

import sys

import pcbnew

MM = pcbnew.FromMM
KEEP = []  # SWIG frees removed items when their wrappers die
# Dropped below the labels, with C132 still feeding straight into TP45
TEST_POINT_SPOTS = (('TP45', 90.0, 38.3), ('TP46', 96.0, 38.4))
C132_SPOT = (87.8, 38.3)
FEED_CORNER = (90.0, 37.6)  # where the rail arrives from U32
FEED_WIDTH = 0.3
# (part, Reference or Value, x, y, angle)
LABELS = (
    ('U32', 'Reference', 92.6, 36.7, 0),
    ('C132', 'Reference', 88.9, 36.7, 0),
    ('R182', 'Reference', 97.6, 31.75, 0),
    ('R183', 'Reference', 99.14, 34.4, 90),  # east of its via, inside the section line
    ('R181', 'Reference', 97.6, 36.85, 0),
    ('TP45', 'Value', 92.6, 38.3, 0),
    ('TP46', 'Value', 98.2, 38.4, 0),
)
# back side, clear of the fan-out
BACK_LABELS = (('U27', 56.6, 8.7),)
SECTION_LINE_X = 86.7
SECTION_LINE_BOTTOM = 40.0


def add_feed(board, net, start, end):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetWidth(MM(FEED_WIDTH))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    board.Add(track)


def move_c132(board):
    """Replaces the C132 to TP45 track at its new height."""
    footprint = board.FindFootprintByReference('C132')
    supply = next(p for p in footprint.Pads() if p.GetNumber() == '1')
    corner = pcbnew.VECTOR2I(MM(FEED_CORNER[0]), MM(FEED_CORNER[1]))
    for item in list(board.GetTracks()):
        if item.Type() != pcbnew.PCB_VIA_T and item.GetNetname() == '+3V3' and (
                item.GetEnd().x == corner.x and item.GetEnd().y == corner.y
                and item.GetStart().y == corner.y):
            KEEP.append(item)
            board.Remove(item)
    footprint.SetPosition(pcbnew.VECTOR2I(MM(C132_SPOT[0]), MM(C132_SPOT[1])))
    test_point = board.FindFootprintByReference('TP45').GetPosition()
    add_feed(board, supply.GetNet(), corner, test_point)
    add_feed(board, supply.GetNet(), supply.GetPosition(), test_point)


def place_label(board, template, ref, field, x, y, angle):
    text = getattr(board.FindFootprintByReference(ref), field)()
    text.SetLayer(pcbnew.F_SilkS)
    text.SetVisible(True)
    text.SetTextSize(template.GetTextSize())
    text.SetTextThickness(template.GetTextThickness())
    text.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    text.SetTextAngleDegrees(angle)


def restore_section_line(board):
    """silk_fix.py stops the line short where C132's label used to sit."""
    for drawing in board.GetDrawings():
        if drawing.GetClass() != 'PCB_SHAPE' or drawing.GetLayer() != pcbnew.F_SilkS:
            continue
        start, end = drawing.GetStart(), drawing.GetEnd()
        if start.x == end.x == MM(SECTION_LINE_X):
            drawing.SetEnd(pcbnew.VECTOR2I(end.x, MM(SECTION_LINE_BOTTOM)))
            return


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    for ref, x, y in TEST_POINT_SPOTS:
        board.FindFootprintByReference(ref).SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    # Safe to re-run after silk_fix.py: the feed only moves once
    if board.FindFootprintByReference('C132').GetPosition().y != MM(C132_SPOT[1]):
        move_c132(board)
    template = board.FindFootprintByReference('D10').Reference()
    for ref, field, x, y, angle in LABELS:
        place_label(board, template, ref, field, x, y, angle)
    for ref, x, y in BACK_LABELS:
        back_label = board.FindFootprintByReference(ref).Reference()
        back_label.SetVisible(True)
        back_label.SetLayer(pcbnew.B_SilkS)
        back_label.SetMirrored(True)
        back_label.SetTextAngleDegrees(0)
        back_label.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    restore_section_line(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
