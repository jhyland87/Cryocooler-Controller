"""Moves C39, U27's 100 nF, from the far side of J15's fan-out to just below U27.
Run `gen_pcb.py link`, then `gridroute.py` on the DRC report to reconnect it.

Usage: c122_move.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
SPOT = (52.7, 11.6)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    capacitor = board.FindFootprintByReference('C39')
    capacitor.SetPosition(pcbnew.VECTOR2I(MM(SPOT[0]), MM(SPOT[1])))
    capacitor.SetOrientationDegrees(0)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
