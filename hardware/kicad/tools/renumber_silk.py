"""Moves the three silk references the new reference numbers pushed onto a part's
outline. Run after renumber_refs.py board.

Usage: renumber_silk.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
# reference: (x, y) of its silk text
REFERENCE_SPOTS = {
    'R45': (38.415, 31.725),
    'R44': (32.87, 82.0),
    'C41': (96.86, 28.5),
}


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    for ref, (pos_x, pos_y) in REFERENCE_SPOTS.items():
        board.FindFootprintByReference(ref).Reference().SetPosition(
            pcbnew.VECTOR2I(MM(pos_x), MM(pos_y)))
    board.Save(sys.argv[1])


if __name__ == '__main__':
    main()
