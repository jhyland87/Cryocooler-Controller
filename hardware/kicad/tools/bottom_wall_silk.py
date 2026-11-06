"""Silk clean-up after the bottom-wall header moves: removes the old pin-1 dots
of J6, J7 and J13, moves the PANEL / RELAY section divider to run between J7 and
J13, sets their pin labels clear of the C55 body, moves the connector names off
the header plates and redraws the section line above them. Run before `silk_fix.py`.

Usage: bottom_wall_silk.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
OLD_DOTS = ((36.3, 92.15), (46.7, 92.15), (58.5, 92.15))
DIVIDER_X = 38.97
LABELS = {  # x -> y: pin labels above the moved headers
    34.8: 84.0, 37.34: 84.0, 40.6: 84.0, 43.14: 84.0, 60.6: 84.0, 63.14: 84.0,
}
# text -> (x window, new x, new y): names clear of the header plates
NAMES = {'PANEL': ((33.0, 38.0), 33.8, 95.4), 'RELAY': ((40.0, 44.0), 44.7, 94.0),
         'NTC': ((60.5, 63.0), 65.83, 94.0)}
SECTION_LINE_Y = 82.0
KEEP = []


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    width = MM(0.16)
    for item in list(board.GetDrawings()):
        if item.GetLayer() != pcbnew.F_SilkS:
            continue
        box = item.GetBoundingBox()
        left, right, top, bottom = box.GetLeft() / 1e6, box.GetRight() / 1e6, box.GetTop() / 1e6, box.GetBottom() / 1e6
        if item.GetClass() == 'PCB_TEXT':
            spot = item.GetPosition()
            name = NAMES.get(item.GetText())
            if name is not None and spot.y / 1e6 > 90 and name[0][0] < spot.x / 1e6 < name[0][1]:
                item.SetPosition(pcbnew.VECTOR2I(MM(name[1]), MM(name[2])))
                continue
            for x_mm, y_mm in LABELS.items():
                if abs(spot.x / 1e6 - x_mm) < 0.05 and 78 < spot.y / 1e6 < 86:
                    if item.GetText() == '+12V':
                        item.SetText('12V')
                    item.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
            continue
        center = ((left + right) / 2, (top + bottom) / 2)
        if (item.GetShapeStr() == 'Line' and bottom - top < 0.2 and abs(center[1] - SECTION_LINE_Y) < 0.1
                and left > 32.9 and right < 56.1):
            board.Remove(item)
            KEEP.append(item)
            continue
        if item.GetShapeStr() == 'Circle' and any(
                abs(center[0] - x) < 0.1 and abs(center[1] - y) < 0.1 for x, y in OLD_DOTS):
            board.Remove(item)
            KEEP.append(item)
        elif item.GetShapeStr() == 'Line' and 44.1 < left and right < 44.3 and top > 81.5:
            width = item.GetWidth()
            board.Remove(item)
            KEEP.append(item)
    top_line = pcbnew.PCB_SHAPE(board)
    top_line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    top_line.SetStart(pcbnew.VECTOR2I(MM(33.0), MM(SECTION_LINE_Y)))
    top_line.SetEnd(pcbnew.VECTOR2I(MM(56.0), MM(SECTION_LINE_Y)))
    top_line.SetLayer(pcbnew.F_SilkS)
    top_line.SetWidth(width)
    board.Add(top_line)
    KEEP.append(top_line)
    # the bodies leave no room for a line between them, so it stops either side
    for start, end in ((82.0, 88.0), (92.4, 99.5)):
        line = pcbnew.PCB_SHAPE(board)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(pcbnew.VECTOR2I(MM(DIVIDER_X), MM(start)))
        line.SetEnd(pcbnew.VECTOR2I(MM(DIVIDER_X), MM(end)))
        line.SetLayer(pcbnew.F_SilkS)
        line.SetWidth(width)
        board.Add(line)
        KEEP.append(line)
    board.Save(path)


if __name__ == '__main__':
    main()
