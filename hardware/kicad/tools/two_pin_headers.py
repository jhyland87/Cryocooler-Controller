"""Replaces the 2-pin headers J6 (NTC), J7 (panel) and J13 (relay out) with
right-angle Sullins wafers on the routed board, on the bottom-wall hole line, and
moves their labels. J7 and J13 shift west to clear D4 and Q7. Copper in the way
is removed for `gen_pcb.py reroute`; then run `gen_pcb.py link` and `silk_fix.py`.

Usage: two_pin_headers.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

from fan_headers import KEEP, MM, place_header, rip

NAME = 'Sullins_SWR25X-NRTC-S02-RB-BA_1x02_P2.54mm_Horizontal'
HEADERS = {'J7': (34.8, 86.7), 'J13': (40.6, 86.7), 'J6': (60.6, 86.7)}
RIP_WINDOWS = ((33.0, 83.0, 45.5, 99.5), (44.0, 90.0, 55.0, 99.5), (56.5, 83.0, 66.0, 99.5))
# (text, old x, old y) -> (new x, new y)
LABELS = {
    ('PANEL', 33.8, 94.9): (36.07, 93.4),
    ('BTN', 37.8, 88.36): (34.8, 83.3),
    ('GND', 39.8, 88.36): (37.34, 83.3),
    ('+12V', 48.2, 87.91): (40.6, 83.3),
    ('GND', 50.2, 88.36): (43.14, 83.3),
    ('RELAY', 45.7, 82.0): (41.87, 93.4),
    ('NTC', 60.0, 88.36): (60.6, 83.3),
    ('GND', 62.0, 88.36): (63.14, 83.3),
    ('NTC', 61.0, 84.8): (61.87, 93.4),
}


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    rip(board, RIP_WINDOWS)
    for reference, (x_mm, y_mm) in HEADERS.items():
        place_header(board, reference, NAME, x_mm, y_mm)
    moved = 0
    for item in board.GetDrawings():
        if item.GetClass() != 'PCB_TEXT' or item.GetLayer() != pcbnew.F_SilkS:
            continue
        spot = item.GetPosition()
        for (text, old_x, old_y), (new_x, new_y) in LABELS.items():
            if (item.GetText() == text and abs(spot.x / 1e6 - old_x) < 0.05
                    and abs(spot.y / 1e6 - old_y) < 0.05):
                item.SetPosition(pcbnew.VECTOR2I(MM(new_x), MM(new_y)))
                moved += 1
                break
    assert moved == len(LABELS), moved
    board.Save(path)


if __name__ == '__main__':
    main()
