"""Moves the fan, pump and flow headers (J3, J4, J5) on the routed board: J3 and
J4 become right-angle 3+1 fan headers if they are not already, J5 the Wurth
61900311021. All three pull in 4.2 mm so their tabs stop at the board edge; the
bottom-side parts behind them and the pin labels move too. Copper in the way is
removed for `gen_pcb.py reroute`, then run `gen_pcb.py link` and `silk_fix.py`.

Usage: fan_headers.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

import pcbmodels

MM = pcbnew.FromMM
LIB = str(pcbmodels.KICAD_DIR / 'lib' / 'cryocooler.pretty')
FAN = 'FanHeader_4P_P2.54mm_Horizontal'
WURTH = 'Wurth_WR-WTB_61900311021_1x03_P2.54mm_Horizontal'
SHIFT = 4.2
HEADERS = {'J3': (FAN, 80.5, 86.6), 'J4': (FAN, 106.6, 85.0), 'J5': (WURTH, 68.5, 86.6)}
# bottom-side parts move onto the old hole line: (dx, dy)
BOTTOM_PARTS = {'C26': (0, SHIFT), 'R18': (0, SHIFT), 'R19': (0, SHIFT), 'R22': (0, SHIFT),
                'R23': (0, SHIFT), 'C27': (SHIFT, 0), 'R20': (SHIFT, 0), 'R21': (SHIFT, 0)}
# (x1, y1, x2, y2, dx, dy) for pin and name labels
LABEL_WINDOWS = ((66, 83, 90, 90, 0, -SHIFT), (103, 75, 110, 87, -SHIFT, 0))
# copper in these areas is ripped up, apart from pour stitching
RIP_WINDOWS = ((64.0, 82.0, 92.0, 94.0), (102.0, 74.0, 116.0, 88.0))
KEEP = []  # SWIG frees removed items when the wrapper dies


def in_window(point, windows):
    x_mm, y_mm = point.x / 1e6, point.y / 1e6
    return any(x1 < x_mm < x2 and y1 < y_mm < y2 for x1, y1, x2, y2 in windows)


def rip(board, windows=RIP_WINDOWS):
    for item in list(board.GetTracks()):
        if item.GetNetname() == 'GND' and item.Type() == pcbnew.PCB_VIA_T:
            continue
        ends = ((item.GetPosition(),) if item.Type() == pcbnew.PCB_VIA_T
                else (item.GetStart(), item.GetEnd()))
        if any(in_window(end, windows) for end in ends):
            board.Remove(item)
            KEEP.append(item)


def place_header(board, reference, name, x_mm, y_mm):
    old = board.FindFootprintByReference(reference)
    nets = {pad.GetNumber(): pad.GetNetname() for pad in old.Pads()}
    new = pcbnew.FootprintLoad(LIB, name)
    new.SetReference(reference)
    new.SetValue(old.GetValue())
    new.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
    board.Add(new)
    new.SetOrientationDegrees(old.GetOrientationDegrees())
    board.Remove(old)
    KEEP.append(old)
    for pad in new.Pads():
        pad.SetNet(board.FindNet(nets[pad.GetNumber()]))
    pcbmodels.attach_missing_models(new)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    rip(board)
    for reference, (name, x_mm, y_mm) in HEADERS.items():
        place_header(board, reference, name, x_mm, y_mm)
    for reference, (dx, dy) in BOTTOM_PARTS.items():
        board.FindFootprintByReference(reference).Move(pcbnew.VECTOR2I(MM(dx), MM(dy)))
    for item in board.GetDrawings():
        if item.GetClass() != 'PCB_TEXT' or item.GetLayer() != pcbnew.F_SilkS:
            continue
        spot = item.GetPosition()
        for x1, y1, x2, y2, dx, dy in LABEL_WINDOWS:
            if x1 < spot.x / 1e6 < x2 and y1 < spot.y / 1e6 < y2:
                item.Move(pcbnew.VECTOR2I(MM(dx), MM(dy)))
                break
    board.Save(path)


if __name__ == '__main__':
    main()
