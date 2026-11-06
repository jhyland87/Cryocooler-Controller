"""Swaps SW3 to the E-Switch TL6800AF260QJ in place. The new pads cover the old pad
centres, so the existing tracks still land on them.

Usage: sw3_tl6800_board.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

import pcbmodels
from small_packages_board import swap_parts

MM = pcbnew.FromMM


def finish(board):
    footprint = board.FindFootprintByReference('SW3')
    pcbmodels.attach_missing_models(footprint)
    # clear of C68's vertical reference, in the narrow silk text the board uses
    reference = footprint.Reference()
    reference.SetPosition(pcbnew.VECTOR2I(MM(24.4), MM(91.7)))
    reference.SetTextSize(pcbnew.VECTOR2I(MM(0.9), MM(1.0)))
    # J7's POWER label, moved off the wider pad and into the gap in the wall line
    for drawing in board.GetDrawings():
        if drawing.GetClass() != 'PCB_TEXT' or drawing.GetText() != 'POWER':
            continue
        if drawing.GetPosition().x == MM(31.9) and drawing.GetLayer() == pcbnew.F_SilkS:
            drawing.SetPosition(pcbnew.VECTOR2I(MM(32.45), MM(94.85)))


def main():
    swap_parts(sys.argv[1], {'SW3': (27.0, 95.8, 0, False)}, {}, (), finish)


if __name__ == '__main__':
    main()
