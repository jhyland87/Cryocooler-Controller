"""Narrows all silk text to SILK_TEXT_WIDTH (height stays at JLCPCB's 1.0 mm minimum),
then shows each hidden reference designator that now fits beside its part. Test points
keep their net names instead. Run after `hand_route.py`, then `silk_fix.py`.

Usage: narrow_silk.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

from silk_fix import Box, SILK_LAYERS, is_text, obstacles, silk_items

SILK_TEXT_WIDTH = 0.9  # below this, letter gaps drop well under JLCPCB's 0.15 mm
CLEARANCE = 0.2
MAX_GAP_TO_PART = 0.5  # a label further from its part could be read as another part's
STEP = 0.25
SKIP = ('TP', 'U1')


def part_box(footprint):
    box = footprint.GetBoundingBox(False)
    return Box(box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6)


def narrow_all(board):
    """Sets the width of every silk text, keeping its height."""
    count = 0
    for item in silk_items(board).values():
        if is_text(item) and item.GetLayer() in SILK_LAYERS:
            item.SetTextWidth(pcbnew.FromMM(SILK_TEXT_WIDTH))
            count += 1
    return count


def gap_between(first, second):
    return max(first.left - second.right, second.left - first.right,
               first.top - second.bottom, second.top - first.bottom, 0)


def spots(owner):
    """Text centre offsets around a part, nearest the part's centre first."""
    half_x = (owner.right - owner.left) / 2 + 3.0
    half_y = (owner.bottom - owner.top) / 2 + 3.0
    center = ((owner.left + owner.right) / 2, (owner.top + owner.bottom) / 2)
    grid = [(center[0] + STEP * ix, center[1] + STEP * iy)
            for ix in range(int(-half_x / STEP), int(half_x / STEP) + 1)
            for iy in range(int(-half_y / STEP), int(half_y / STEP) + 1)]
    return sorted(grid, key=lambda spot: (spot[0] - center[0]) ** 2 + (spot[1] - center[1]) ** 2)


def show_reference(board, footprint, outline):
    """Places a hidden reference at the nearest clear spot beside its part."""
    text = footprint.Reference()
    layer = text.GetLayer()
    owner = part_box(footprint)
    copper = pcbnew.F_Cu if layer == pcbnew.F_SilkS else pcbnew.B_Cu
    bodies = [part_box(other) for other in board.GetFootprints()
              if other.GetReference() and other.GetReference() != footprint.GetReference()
              and other.GetLayer() == copper]
    blocked = [box.grown(CLEARANCE) for box in obstacles(board, layer, text) + bodies + [owner]]
    start_angle = text.GetTextAngleDegrees()
    for angle in (start_angle, 90 if start_angle % 180 == 0 else 0):
        text.SetTextAngleDegrees(angle)
        for x_mm, y_mm in spots(owner):
            text.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
            box = Box.of(text)
            if (box.left < outline.left or box.right > outline.right
                    or box.top < outline.top or box.bottom > outline.bottom):
                continue
            if gap_between(box, owner) > MAX_GAP_TO_PART or any(box.overlaps(other) for other in blocked):
                continue
            text.SetVisible(True)
            return True
    return False


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    print('texts narrowed:', narrow_all(board))
    edges = board.GetBoardEdgesBoundingBox()
    outline = Box(edges.GetLeft() / 1e6 + 0.5, edges.GetTop() / 1e6 + 0.5,
                  edges.GetRight() / 1e6 - 0.5, edges.GetBottom() / 1e6 - 0.5)
    shown, left = [], []
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if not reference or reference.startswith(SKIP) or footprint.Reference().IsVisible():
            continue
        saved = (footprint.Reference().GetPosition(), footprint.Reference().GetTextAngleDegrees())
        if show_reference(board, footprint, outline):
            shown.append(reference)
        else:
            footprint.Reference().SetPosition(saved[0])
            footprint.Reference().SetTextAngleDegrees(saved[1])
            left.append(reference)
    print('references shown again:', sorted(shown))
    print('still hidden:', sorted(left))
    board.Save(path)


if __name__ == '__main__':
    main()
