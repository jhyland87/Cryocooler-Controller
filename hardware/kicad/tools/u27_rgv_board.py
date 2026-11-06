"""Moves U27 to the RGV VQFN-16 at the same centre on the back, and joins its ground
pins to the exposed pad. Only back-layer copper is ripped, so J15's front fan-out
stays. Run `gen_pcb.py link`, then `gridroute.py` on the DRC report.

Usage: u27_rgv_board.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

from small_packages_board import swap_parts

MM = pcbnew.FromMM
STUB_WIDTH = 0.2
GROUND_PINS = ('10', '11', '12')  # GND, VBAT, AUX


def finish(board):
    footprint = board.FindFootprintByReference('U27')
    footprint.Value().SetVisible(False)
    exposed = next(p for p in footprint.Pads() if p.GetNumber() == '17').GetPosition()
    for number in GROUND_PINS:
        pad = next(p for p in footprint.Pads() if p.GetNumber() == number)
        start = pad.GetPosition()
        stub = pcbnew.PCB_TRACK(board)
        stub.SetStart(start)
        stub.SetEnd(pcbnew.VECTOR2I(exposed.x, start.y))
        stub.SetWidth(MM(STUB_WIDTH))
        stub.SetLayer(pcbnew.B_Cu)
        stub.SetNet(pad.GetNet())
        board.Add(stub)


def main():
    swap_parts(
        sys.argv[1],
        {'U27': (52.0, 6.5, 0, True)},
        {'U27': (48.5, 3.7, 55.5, 9.3)},
        (('U27', '17'),),
        finish,
        pcbnew.B_Cu,
    )


if __name__ == '__main__':
    main()
