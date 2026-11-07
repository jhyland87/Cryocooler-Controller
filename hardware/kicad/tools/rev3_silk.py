"""Rev 3 silkscreen edits on the routed board: drops texts for parts that left, names the new
isolator on its body, moves the cryocooler label beside J12, and takes the Rails
+-15V box around L2 on the front and clears the box lines that U17's parts, L4, U34 and D17 cross.

Usage: rev3_silk.py board.kicad_pcb (edits in place; run once, before silk_fix.py)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
KEEP = []
STALE_TEXTS = {'ISO7741DW', 'LD1117\nS33TR', 'FAULT'}
MOVED_TEXTS = {'TO CRYO-\nCOOLER': (13.9, 34.6, 90)}
WALL_X = 60.0
WALL_TOP, WALL_BOTTOM = 41.0, 58.0
BOX_X = 56.3
ISOLATOR_WALL_X, ISOLATOR_WALL_NEW_X = 33.0, 32.1  # U17's logic-side parts sit on x 33
ISOLATOR_WALL_TOP, ISOLATOR_WALL_BOTTOM = 13.0, 27.0
SECTION_NAME_RIGHT = 14.4  # the front section name ends left of Q41's pad
SECTION_NAME = 'POWER IN'  # 'POWER & RAILS' is too long to fit past the hole's mask opening
STALE_DOT = (35.46, 22.85)  # pin 1 dot of a rev 2 part, now on C6's pad
# (layer, 'x' or 'y', line position, low, high): gaps where a part sits on a box line
LINE_GAPS = (
    (pcbnew.F_SilkS, 'x', 33.0, 76.9, 84.75),  # L4, C5
    (pcbnew.F_SilkS, 'y', 82.0, 33.0, 33.6),  # L4
    (pcbnew.B_SilkS, 'x', 33.0, 83.9, 85.9),  # U34
    (pcbnew.B_SilkS, 'y', 72.0, 35.7, 41.2),  # D17
)


def add_line(board, start, end, layer=pcbnew.F_SilkS):
    line = pcbnew.PCB_SHAPE(board)
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    line.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    line.SetLayer(layer)
    line.SetWidth(MM(0.15))
    board.Add(line)
    KEEP.append(line)


def reshape_rails_box(board):
    """Cuts the x 60 wall and the y 58 stub out of the L2 span and draws the new corner."""
    for item in list(board.GetDrawings()):
        if item.GetLayer() != pcbnew.F_SilkS or item.GetClass() != 'PCB_SHAPE':
            continue
        start, end = item.GetStart(), item.GetEnd()
        if start.x == end.x == MM(WALL_X):
            low, high = sorted((start.y / 1e6, end.y / 1e6))
            if high <= WALL_TOP or low >= WALL_BOTTOM:
                continue
            KEEP.append(item)
            board.Remove(item)
            if low < WALL_TOP:
                add_line(board, (WALL_X, low), (WALL_X, WALL_TOP))
            if high > WALL_BOTTOM:
                add_line(board, (WALL_X, WALL_BOTTOM), (WALL_X, high))
        elif start.y == end.y == MM(WALL_BOTTOM):
            low, high = sorted((start.x / 1e6, end.x / 1e6))
            if high <= BOX_X or low >= WALL_X:
                continue
            KEEP.append(item)
            board.Remove(item)
            if low < BOX_X:
                add_line(board, (low, WALL_BOTTOM), (BOX_X, WALL_BOTTOM))
            if high > WALL_X:
                add_line(board, (WALL_X, WALL_BOTTOM), (high, WALL_BOTTOM))
    add_line(board, (WALL_X, WALL_TOP), (BOX_X, WALL_TOP))
    add_line(board, (BOX_X, WALL_TOP), (BOX_X, WALL_BOTTOM))


def cut_gap(board, layer, axis, position, low, high):
    """Takes the span low..high out of box lines at x or y = position."""
    for item in list(board.GetDrawings()):
        if item.GetLayer() != layer or item.GetClass() != 'PCB_SHAPE':
            continue
        start, end = item.GetStart(), item.GetEnd()
        if axis == 'x':
            if not start.x == end.x == MM(position):
                continue
            first, second = sorted((start.y / 1e6, end.y / 1e6))
        else:
            if not start.y == end.y == MM(position):
                continue
            first, second = sorted((start.x / 1e6, end.x / 1e6))
        if second <= low or first >= high:
            continue
        KEEP.append(item)
        board.Remove(item)
        for piece_low, piece_high in ((first, low), (high, second)):
            if piece_high - piece_low > 0.01:
                ends = ((position, piece_low), (position, piece_high)) if axis == 'x' else (
                    (piece_low, position), (piece_high, position))
                add_line(board, *ends, layer=layer)


def move_wall_points(board):
    """Walks the x 33 wall around U17's parts."""
    cut_gap(board, pcbnew.F_SilkS, 'x', ISOLATOR_WALL_X, ISOLATOR_WALL_TOP, ISOLATOR_WALL_BOTTOM)
    cut_gap(board, pcbnew.F_SilkS, 'y', ISOLATOR_WALL_TOP, ISOLATOR_WALL_NEW_X, ISOLATOR_WALL_X)
    add_line(board, (ISOLATOR_WALL_NEW_X, ISOLATOR_WALL_TOP),
             (ISOLATOR_WALL_NEW_X, ISOLATOR_WALL_BOTTOM))
    add_line(board, (ISOLATOR_WALL_NEW_X, ISOLATOR_WALL_BOTTOM),
             (ISOLATOR_WALL_X, ISOLATOR_WALL_BOTTOM))


def park_section_name(board):
    """Shortens the front 'POWER & RAILS' and slides it along its line to end left of Q41."""
    for item in board.GetDrawings():
        if item.GetClass() == 'PCB_TEXT' and item.GetText() == 'POWER & RAILS' and (
                item.GetLayer() == pcbnew.F_SilkS):
            item.SetText(SECTION_NAME)
            box = item.GetBoundingBox()
            shift = MM(SECTION_NAME_RIGHT) - box.GetRight()
            item.SetPosition(pcbnew.VECTOR2I(item.GetPosition().x + shift, item.GetPosition().y))
            print(SECTION_NAME, 'spans', (box.GetLeft() + shift) / 1e6, SECTION_NAME_RIGHT)


def remove_stale_dot(board):
    """Removes the silk dot left behind where a rev 2 part used to sit."""
    for item in list(board.GetDrawings()):
        if item.GetClass() == 'PCB_SHAPE' and item.GetLayer() == pcbnew.F_SilkS and (
                item.GetShape() == pcbnew.SHAPE_T_CIRCLE):
            center = item.GetCenter()
            if abs(center.x - MM(STALE_DOT[0])) < MM(0.05) and (
                    abs(center.y - MM(STALE_DOT[1])) < MM(0.05)):
                KEEP.append(item)
                board.Remove(item)


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    template = None
    for item in list(board.GetDrawings()):
        if item.GetClass() != 'PCB_TEXT' or item.GetLayer() != pcbnew.F_SilkS:
            continue
        text = item.GetText()
        if text == 'ACS37800':
            template = item
        if text in STALE_TEXTS:
            KEEP.append(item)
            board.Remove(item)
        elif text in MOVED_TEXTS:
            pos_x, pos_y, angle = MOVED_TEXTS[text]
            item.SetPosition(pcbnew.VECTOR2I(MM(pos_x), MM(pos_y)))
            item.SetTextAngleDegrees(angle)
    name = pcbnew.PCB_TEXT(template)
    name.SetText('ISOW7741')
    name.SetPosition(pcbnew.VECTOR2I(MM(26.0), MM(26.4)))
    name.SetTextAngleDegrees(90)
    board.Add(name)
    KEEP.append(name)
    reshape_rails_box(board)
    move_wall_points(board)
    for layer, axis, position, low, high in LINE_GAPS:
        cut_gap(board, layer, axis, position, low, high)
    park_section_name(board)
    remove_stale_dot(board)
    board.Save(sys.argv[1])


if __name__ == '__main__':
    main()
