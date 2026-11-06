"""Moves U32 to the RGY VQFN-16 at the same centre and rotation, and joins its
ground pins to the exposed pad. Run `gen_pcb.py link`, then `gridroute.py` on the
DRC report to close the open ends.

Usage: u32_rgy_board.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

from small_packages_board import swap_parts

MM = pcbnew.FromMM
KEEP = []  # SWIG frees removed items when their wrappers die
PART_NAME = '138'  # the exposed pad leaves no room for it
STUB_WIDTH = 0.2
# pad number, end of the stub inside the exposed pad (mm)
GROUND_STUBS = (('5', 92.9, 32.75), ('8', 92.75, 31.9))


def finish(board):
    for drawing in list(board.GetDrawings()):
        if drawing.GetClass() == 'PCB_TEXT' and drawing.GetText() == PART_NAME:
            KEEP.append(drawing)
            board.Remove(drawing)
    footprint = board.FindFootprintByReference('U32')
    footprint.Value().SetVisible(False)
    for number, x, y in GROUND_STUBS:
        pad = next(p for p in footprint.Pads() if p.GetNumber() == number)
        stub = pcbnew.PCB_TRACK(board)
        stub.SetStart(pad.GetPosition())
        stub.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
        stub.SetWidth(MM(STUB_WIDTH))
        stub.SetLayer(pcbnew.F_Cu)
        stub.SetNet(pad.GetNet())
        board.Add(stub)


def main():
    swap_parts(
        sys.argv[1],
        {'U32': (92.0, 33.0, 180, False)},
        {'U32': (88.0, 29.5, 96.0, 36.5)},
        (('U32', '17'),),
        finish,
    )


if __name__ == '__main__':
    main()
