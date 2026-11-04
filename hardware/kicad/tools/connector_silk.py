"""Silk update after `connector_moves.py`: pin labels and connector names follow the
moved headers, and the section lines step around J2, J9 and J4. Run before
`silk_fix.py`.

Usage: connector_silk.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
KEEP = []
F = pcbnew.F_SilkS
B = pcbnew.B_SilkS
# text, layer, x, y of the labels that no longer apply
OLD_TEXT = (
    ('AMP SIGNAL', F, 5.7, 72.6), ('GND', F, 7.9, 70.3), ('+12V', F, 8.1, 49.5), ('GND', F, 8.1, 60.5),
    ('TO CRYOCOOLER', F, 10.0, 27.86), ('SIG', F, 11.2, 70.3), ('GND', F, 12.1, 81.31),
    ('FROM AMP', F, 13.2, 24.42), ('-', F, 13.39, 38.08), ('+', F, 14.14, 32.25), ('GND', F, 14.29, 43.16),
    ('12V IN', F, 15.0, 60.5), ('AMP REM', F, 5.3, 79.41), ('REM', F, 13.1, 78.5), ('+', B, 12.9, 11.7),
    ('-', B, 12.9, 16.78), ('FAN FAULT', F, 96.3, 92.26), ('TACH', F, 101.54, 80.0), ('+12V', F, 101.54, 82.5),
    ('PWM', F, 102.0, 77.5), ('GND', F, 102.0, 88.0), ('PUMP', F, 104.72, 81.25), ('USB', F, 110.22, 8.28),
)
# text, x, y, angle: new top-side labels
NEW_TEXT = (
    ('+', 15.0, 21.0, 0), ('-', 15.0, 26.0, 0), ('FROM AMP', 11.25, 18.6, 0), ('TO\nCRYOCOOLER', 13.15, 29.2, 0),
    ('+', 15.0, 33.5, 0), ('-', 15.0, 38.5, 0), ('GND', 15.4, 43.5, 0),
    ('REM', 9.4, 72.4, 0), ('GND', 9.4, 74.94, 0), ('AMP REM', 9.4, 69.9, 0),
    ('GND', 7.9, 67.0, 0), ('SIG', 11.2, 67.0, 0), ('AMP SIGNAL', 11.0, 59.3, 0),
    ('+12V', 8.1, 80.0, 0), ('GND', 8.1, 91.0, 0), ('12V IN', 17.8, 84.0, 0),
    ('GND', 92.2, 82.0, 90), ('+12V', 94.74, 81.54, 90), ('TACH', 97.28, 81.54, 90), ('PWM', 99.82, 81.54, 90),
    ('PUMP', 95.7, 84.72, 0), ('FAN FAULT', 96.3, 75.6, 0), ('USB', 54.3, 9.3, 0),
)
# text, layer, old x, old y, new x, new y
MOVED_TEXT = (
    ('AMP CONTROL', F, 3.0, 62.5, 3.0, 59.4), ('AMP CONTROL', B, 12.9, 62.5, 12.9, 59.4),
    ('POWER & RAILS', F, 3.0, 85.0, 8.5, 92.7), ('POWER INPUT & RAILS', B, 20.1, 85.0, 20.1, 81.0),
)
USB_DOT = ((111.03, 17.2), (58.3, 8.7))


def same_spot(item, x_mm, y_mm):
    spot = item.GetPosition()
    return abs(spot.x / 1e6 - x_mm) < 0.05 and abs(spot.y / 1e6 - y_mm) < 0.05


def add_line(board, layer, width, start, end):
    line = pcbnew.PCB_SHAPE(board)
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    line.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    line.SetLayer(layer)
    line.SetWidth(width)
    board.Add(line)
    KEEP.append(line)


def update_text(board):
    template = None
    for item in list(board.GetDrawings()):
        if item.GetClass() != 'PCB_TEXT':
            continue
        for text, layer, x_mm, y_mm in OLD_TEXT:
            if item.GetText() == text and item.GetLayer() == layer and same_spot(item, x_mm, y_mm):
                if layer == F:
                    template = item.Duplicate()
                    KEEP.append(template)
                board.Remove(item)
                KEEP.append(item)
                break
        for text, layer, x_mm, y_mm, new_x, new_y in MOVED_TEXT:
            if item.GetText() == text and item.GetLayer() == layer and same_spot(item, x_mm, y_mm):
                item.SetPosition(pcbnew.VECTOR2I(MM(new_x), MM(new_y)))
                break
    for text, x_mm, y_mm, angle in NEW_TEXT:
        label = template.Duplicate()
        label.SetText(text)
        label.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        label.SetTextAngleDegrees(angle)
        board.Add(label)
        KEEP.append(label)


def box_of(item):
    box = item.GetBoundingBox()
    return box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6


# (layer, x, old top, new top): old section line stubs shortened clear of copper
TRIMS = ((F, 13.5, 44.3, 44.8), (B, 13.5, 58.6, 59.4))


def update_lines(board):
    width = MM(0.16)
    for item in list(board.GetDrawings()):
        if item.GetClass() == 'PCB_TEXT' or item.GetLayer() not in (F, B):
            continue
        left, top, right, bottom = box_of(item)
        kind = item.GetShapeStr()
        center = ((left + right) / 2, (top + bottom) / 2)
        if kind == 'Circle' and abs(center[0] - USB_DOT[0][0]) < 0.1 and abs(center[1] - USB_DOT[0][1]) < 0.1:
            item.Move(pcbnew.VECTOR2I(MM(USB_DOT[1][0] - USB_DOT[0][0]), MM(USB_DOT[1][1] - USB_DOT[0][1])))
            continue
        if kind != 'Line':
            continue
        horizontal = bottom - top < 0.2
        vertical = right - left < 0.2
        old_top_line = horizontal and abs(center[1] - 62.5) < 0.1 and right < 22.2
        old_power_line = item.GetLayer() == F and horizontal and abs(center[1] - 85.0) < 0.1 and right < 22.2
        old_water_line = vertical and abs(center[0] - 100.0) < 0.1 and top > 71.8
        for layer, x_mm, old_top, new_top in TRIMS:
            if (item.GetLayer() == layer and vertical and abs(center[0] - x_mm) < 0.1
                    and abs(top - old_top) < 0.15):
                item.SetStart(pcbnew.VECTOR2I(MM(x_mm), MM(new_top)))
                item.SetEnd(pcbnew.VECTOR2I(MM(x_mm), MM(bottom if layer == F else 59.4)))
        if old_top_line or old_power_line or old_water_line:
            width = item.GetWidth()
            board.Remove(item)
            KEEP.append(item)
    for layer in (F, B):
        add_line(board, layer, width, (0.5, 59.4), (22.0, 59.4))
        add_line(board, layer, width, (22.0, 59.4), (22.0, 62.5))
        add_line(board, layer, width, (100.0, 72.0), (102.4, 72.0))
        add_line(board, layer, width, (102.4, 72.0), (102.4, 99.5))
    add_line(board, F, width, (7.6, 78.7), (15.4, 78.7))
    add_line(board, F, width, (15.4, 78.7), (15.4, 85.0))
    add_line(board, F, width, (15.4, 85.0), (22.0, 85.0))


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    update_text(board)
    update_lines(board)
    board.Save(path)


if __name__ == '__main__':
    main()
