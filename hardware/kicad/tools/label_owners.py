"""Makes each label read as belonging to its own part: moves a label whose nearest part
is another one to a spot where its own part is clearly nearest. A test point or LED name
with no such spot may take a reference's place, hiding that reference. A reference with no
spot is hidden when it would mislead, and shown again at the end if room opened up.
Also removes the +15V / -15V LED names, because the test point beside each LED prints
the same name. Run after `narrow_silk.py`, then `silk_fix.py`.

Usage: label_owners.py board.kicad_pcb (edits in place)
"""
import math
import sys

import pcbnew

from silk_fix import Box, obstacles

DUPLICATE_NAMES = {'+15V': 'D12', '-15V': 'D13'}  # owner LED of each name to remove
# board text -> the part it names (the instance nearest that part)
NAMED_PARTS = {
    'STATUS': 'D22', '5V': 'D11', 'READY': 'D10', 'FAULT': 'D8', 'COMP RLY': 'D4',
    'POWER': 'D2', '3V3': 'D9', 'SG 3V3': 'JP1', '±15V EN': 'JP2',
    'ISO PS': 'JP3', 'WATER EN': 'JP4', 'HEAD EN': 'JP5',
}
CLEARANCE = 0.2
MAX_OWN_GAP = 1.0
MIN_MARGIN = 0.1  # own part must be at least this much nearer than any other
FAR_OWN_GAP = 2.5  # a further spot is fine when nothing else is near it
FAR_MARGIN = 0.3
MOVE_MARGIN = 0.1  # labels within this of their neighbour read fine as they are
HIDE_MARGIN = 0.3  # a reference this much nearer another part misleads: hide it
REACH = 4.0
STEP = 0.1
KEEP = []
# test point names placed by hand: the only free spot near TP7 fails the box checks
FIXED_NAMES = {'TP7': (33.6, 70.2)}


def gap(first, second):
    """Distance between two boxes (0 when they touch)."""
    delta_x = max(first.left - second.right, second.left - first.right, 0)
    delta_y = max(first.top - second.bottom, second.top - first.bottom, 0)
    return math.hypot(delta_x, delta_y)


def part_box(footprint):
    box = footprint.GetBoundingBox(False)
    return Box(box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6)


def side_parts(board, layer):
    """(reference, box) a reader sees on a silk layer: parts on that side, and the
    through-hole pads of parts on the other side."""
    copper = pcbnew.F_Cu if layer == pcbnew.F_SilkS else pcbnew.B_Cu
    parts = []
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if not reference:
            continue
        if footprint.GetLayer() == copper:
            parts.append((reference, part_box(footprint)))
            continue
        parts += [(reference, Box.of(pad)) for pad in footprint.Pads() if pad.IsOnLayer(copper)]
    return parts


def distances(box, parts, owner):
    """Gap to the owner, and the nearest gap and name among other parts."""
    own = min((gap(box, part) for name, part in parts if name == owner), default=math.inf)
    other, other_name = min(((gap(box, part), name) for name, part in parts if name != owner),
                            default=(math.inf, ''))
    return own, other, other_name


def best_spot(board, text, owner, parts, max_gap=MAX_OWN_GAP, min_margin=MIN_MARGIN, skip_lines=False):
    """Moves the text to the clearest spot beside its owner. Returns True on success."""
    layer = text.GetLayer()
    owner_box = min((part for name, part in parts if name == owner),
                    key=lambda part: (part.right - part.left) * (part.bottom - part.top) * -1)
    near = owner_box.grown(REACH + 3)
    blocked = [box.grown(CLEARANCE) for box in obstacles(board, layer, text, skip_lines)]
    blocked += [part.grown(CLEARANCE) for _, part in parts]
    blocked = [box for box in blocked if box.overlaps(near)]
    nearby = [(name, part) for name, part in parts if part.overlaps(near)]
    start_angle = text.GetTextAngleDegrees()
    best = None
    for angle in (start_angle, 90 if start_angle % 180 == 0 else 0):
        text.SetTextAngleDegrees(angle)
        here = Box.of(text)
        center_x, center_y = (here.left + here.right) / 2, (here.top + here.bottom) / 2
        goal_x, goal_y = (owner_box.left + owner_box.right) / 2, (owner_box.top + owner_box.bottom) / 2
        half_x = (owner_box.right - owner_box.left) / 2 + REACH
        half_y = (owner_box.bottom - owner_box.top) / 2 + REACH
        for x_index in range(int(-half_x / STEP), int(half_x / STEP) + 1):
            for y_index in range(int(-half_y / STEP), int(half_y / STEP) + 1):
                delta_x = goal_x + x_index * STEP - center_x
                delta_y = goal_y + y_index * STEP - center_y
                box = here.shifted(delta_x, delta_y)
                if gap(box, owner_box) > max_gap or any(box.overlaps(other) for other in blocked):
                    continue
                if not inside_board(board, box):
                    continue
                own, other, _ = distances(box, nearby, owner)
                margin = other - own
                if margin < min_margin:
                    continue
                score = (min(margin, 0.5), -own)
                if best is None or score > best[0]:
                    best = (score, angle, delta_x, delta_y)
    if best is None:
        text.SetTextAngleDegrees(start_angle)
        return False
    text.SetTextAngleDegrees(best[1])
    text.Move(pcbnew.VECTOR2I(pcbnew.FromMM(best[2]), pcbnew.FromMM(best[3])))
    return True


def place_over_references(board, text, owner, parts):
    """best_spot that ignores reference designators, then hides the ones in the way.
    Returns the hidden references, or None when there is still no spot."""
    layer = text.GetLayer()
    references = [footprint.Reference() for footprint in board.GetFootprints()
                  if footprint.GetReference() and not footprint.GetReference().startswith('TP')
                  and footprint.Reference().IsVisible() and footprint.Reference().GetLayer() == layer]
    for reference in references:
        reference.SetVisible(False)
    placed = best_spot(board, text, owner, parts)
    hidden = []
    final = Box.of(text).grown(CLEARANCE) if placed else None
    for reference in references:
        if placed and Box.of(reference).overlaps(final):
            hidden.append(reference.GetText())
        else:
            reference.SetVisible(True)
    return hidden if placed else None


def inside_board(board, box):
    edges = board.GetBoardEdgesBoundingBox()
    return (edges.GetLeft() / 1e6 + 0.5 <= box.left and box.right <= edges.GetRight() / 1e6 - 0.5
            and edges.GetTop() / 1e6 + 0.5 <= box.top and box.bottom <= edges.GetBottom() / 1e6 - 0.5)


def named_text(board, name, owner):
    """The board text with this name nearest the owner part."""
    footprint = board.FindFootprintByReference(owner)
    texts = [item for item in board.GetDrawings()
             if item.GetClass() == 'PCB_TEXT' and item.GetText() == name
             and item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)
             and (item.GetLayer() == pcbnew.F_SilkS) == (footprint.GetLayer() == pcbnew.F_Cu)]
    position = footprint.GetPosition()
    return min(texts, key=lambda item: math.dist((item.GetPosition().x, item.GetPosition().y),
                                                 (position.x, position.y)), default=None)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    for name, owner in DUPLICATE_NAMES.items():
        text = named_text(board, name, owner)
        if text is not None:
            board.Remove(text)
        KEEP.append(text)
    labels = []  # (text, owner, may hide)
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if not reference:
            continue
        test_point = reference.startswith('TP')
        text = footprint.Value() if test_point else footprint.Reference()
        if text.IsVisible() and text.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            labels.append((text, reference, not test_point))
    for name, owner in NAMED_PARTS.items():
        text = named_text(board, name, owner)
        if text is not None:
            labels.append((text, owner, False))

    moved, hidden, stuck = [], [], []
    parts_by_layer = {layer: side_parts(board, layer) for layer in (pcbnew.F_SilkS, pcbnew.B_SilkS)}

    def badness(label):
        own, other, _ = distances(Box.of(label[0]), parts_by_layer[label[0].GetLayer()], label[1])
        return own - other

    for label in sorted(labels, key=badness, reverse=True):
        text, owner, may_hide = label
        parts = parts_by_layer[text.GetLayer()]
        own, other, other_name = distances(Box.of(text), parts, owner)
        if own - other < MOVE_MARGIN and own <= MAX_OWN_GAP:
            continue
        name = text.GetShownText(False) if text.GetClass() != 'PCB_TEXT' else text.GetText()
        if (best_spot(board, text, owner, parts)
                or best_spot(board, text, owner, parts, FAR_OWN_GAP, FAR_MARGIN)):
            moved.append(owner if name == owner else f'{name} ({owner})')
        elif may_hide and own - other >= HIDE_MARGIN:
            text.SetVisible(False)
            hidden.append(owner)
        else:
            stuck.append(f'{name} ({owner}): own {own:.2f}, {other_name} {other:.2f}')
    # names first took the room they needed; a reference may fit in what is left
    for label in labels:
        text, owner, may_hide = label
        if may_hide or owner in hidden:
            continue
        parts = parts_by_layer[text.GetLayer()]
        own, other, _ = distances(Box.of(text), parts, owner)
        if own - other < HIDE_MARGIN and own <= MAX_OWN_GAP:
            continue
        name = text.GetText() if text.GetClass() == 'PCB_TEXT' else text.GetShownText(False)
        displaced = place_over_references(board, text, owner, parts)
        if displaced is not None:
            moved.append(f'{name} ({owner})')
            hidden += displaced
            stuck = [entry for entry in stuck if not entry.startswith(f'{name} ({owner})')]
    # last resort for a name still far from its part: cross a section line (silk_fix cuts it)
    for text, owner, may_hide in labels:
        if may_hide or owner in hidden:
            continue
        parts = parts_by_layer[text.GetLayer()]
        own, other, _ = distances(Box.of(text), parts, owner)
        name = text.GetText() if text.GetClass() == 'PCB_TEXT' else text.GetShownText(False)
        if own > MAX_OWN_GAP and own > other and best_spot(board, text, owner, parts, skip_lines=True):
            moved.append(f'{name} ({owner})')
            stuck = [entry for entry in stuck if not entry.startswith(f'{name} ({owner})')]
    for reference, (x_mm, y_mm) in FIXED_NAMES.items():
        board.FindFootprintByReference(reference).Value().SetPosition(
            pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if reference in hidden:
            parts = parts_by_layer[footprint.Reference().GetLayer()]
            if best_spot(board, footprint.Reference(), reference, parts, FAR_OWN_GAP, FAR_MARGIN):
                footprint.Reference().SetVisible(True)
                hidden.remove(reference)
    print('moved', len(moved), sorted(moved))
    print('hidden', len(hidden), sorted(hidden))
    print('left in place', len(stuck), stuck)
    board.Save(path)


if __name__ == '__main__':
    main()
