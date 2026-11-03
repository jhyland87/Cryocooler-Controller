"""Clears the silkscreen overlaps KiCad's DRC finds on a finished board.

Runs `kicad-cli pcb drc`, then for each silk_overlap / silk_over_copper
finding:
- a section line (a straight board drawing) under a text is cut around it;
- a reference designator, an ESP32 pin name that collides with another text
  (test point names win) or a footprint's own marker text is hidden (allowed
  on this crowded board);
- any other text is nudged (up to 4 mm, or 8 mm for a test point name that
  stays nearest its own point; section names only slide along their border)
  to the nearest spot clear of all silk and pads;
- the DROPPED_SECTION_NAMES are removed and their border closed.
Findings it cannot clear are printed. Copper is never touched.

Usage: silk_fix.py board.kicad_pcb (edits in place; runs up to four rounds)
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

import pcbfloorplan

KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
SILK_LAYERS = (pcbnew.F_SilkS, pcbnew.B_SilkS)
# KiCad's silk clearance plus a little margin
CLEARANCE = 0.2
LINE_GAP = 0.3
# items added or removed this run: SWIG frees a wrapper's object when the
# wrapper dies, so they stay referenced until the board is saved
KEEP = []
NUDGE_STEPS = tuple(0.25 * step for step in range(1, 17))  # up to 4 mm
# a test point's name may go further, while it stays nearest its own point
TEST_POINT_STEPS = tuple(0.25 * step for step in range(1, 33))  # up to 8 mm
# section names dropped where their border is too crowded (the outline stays)
DROPPED_SECTION_NAMES = {'MCU & USB', 'INDICATORS'}


class Box:
    """Axis-aligned box in mm."""

    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom

    @classmethod
    def of(cls, item):
        box = item.GetBoundingBox()
        return cls(box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6, box.GetBottom() / 1e6)

    def grown(self, margin):
        return Box(self.left - margin, self.top - margin, self.right + margin, self.bottom + margin)

    def shifted(self, delta_x, delta_y):
        return Box(self.left + delta_x, self.top + delta_y, self.right + delta_x, self.bottom + delta_y)

    def overlaps(self, other):
        return (self.left < other.right and other.left < self.right
                and self.top < other.bottom and other.top < self.bottom)


def drc_findings(path):
    """silk_overlap / silk_over_copper findings as lists of item uuids."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'drc.json'
        subprocess.run(
            [KICAD_CLI, 'pcb', 'drc', '--severity-all', '--format', 'json',
             '-o', str(report), str(path)],
            check=True, capture_output=True,
        )
        data = json.loads(report.read_text())
    return [
        [item['uuid'] for item in violation['items']]
        for violation in data['violations']
        if violation['type'] in ('silk_overlap', 'silk_over_copper')
    ]


def silk_items(board):
    """uuid -> silk item: board drawings and every footprint field / graphic."""
    items = {}
    for drawing in board.GetDrawings():
        if drawing.GetLayer() in SILK_LAYERS:
            items[drawing.m_Uuid.AsString()] = drawing
    for footprint in board.GetFootprints():
        for field in (footprint.Reference(), footprint.Value()):
            items[field.m_Uuid.AsString()] = field
        for graphic in footprint.GraphicalItems():
            if graphic.GetLayer() in SILK_LAYERS:
                items[graphic.m_Uuid.AsString()] = graphic
    return items


def is_section_line(item):
    """A straight silk segment drawn on the board (not part of a footprint)."""
    if item.Type() != pcbnew.PCB_SHAPE_T or item.GetParentFootprint() is not None:
        return False
    if item.GetShape() != pcbnew.SHAPE_T_SEGMENT:
        return False
    start, end = item.GetStart(), item.GetEnd()
    return start.x == end.x or start.y == end.y


def is_text(item):
    return item.Type() in (pcbnew.PCB_TEXT_T, pcbnew.PCB_FIELD_T)


def is_reference(item):
    return item.Type() == pcbnew.PCB_FIELD_T and item.IsReference()


# section names printed on the section border lines
SECTION_NAMES = {
    text
    for module in pcbfloorplan.MODULE_REGIONS
    for text in pcbfloorplan.label_texts(module)
}


def is_section_name(item):
    return item.Type() == pcbnew.PCB_TEXT_T and item.GetText() in SECTION_NAMES


# ESP32 pin names printed around U1 (gen_pcb.add_esp32_pin_names)
ESP32_NAME = re.compile(r'^(IO\d+|EN|TXD0|RXD0|USB_D[+-])$')


def is_esp32_name(item):
    return item.Type() == pcbnew.PCB_TEXT_T and ESP32_NAME.match(item.GetText()) is not None


def is_footprint_text(item):
    """A plain text inside a footprint (not its reference / value field)."""
    return item.Type() == pcbnew.PCB_TEXT_T and item.GetParentFootprint() is not None


def cut_line(board, line, box, removed):
    """Splits a horizontal / vertical line around a box."""
    start, end = line.GetStart(), line.GetEnd()
    x1, y1, x2, y2 = start.x / 1e6, start.y / 1e6, end.x / 1e6, end.y / 1e6
    if y1 == y2:
        low, high = sorted((x1, x2))
        pieces = [((low, y1), (box.left, y1)), ((box.right, y1), (high, y1))]
        pieces = [p for p in pieces if p[1][0] - p[0][0] > 0.2]
    else:
        low, high = sorted((y1, y2))
        pieces = [((x1, low), (x1, box.top)), ((x1, box.bottom), (x1, high))]
        pieces = [p for p in pieces if p[1][1] - p[0][1] > 0.2]
    for (start_x, start_y), (end_x, end_y) in pieces:
        piece = line.Duplicate()
        piece.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start_x), pcbnew.FromMM(start_y)))
        piece.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end_x), pcbnew.FromMM(end_y)))
        board.Add(piece)
        KEEP.append(piece)
    board.Remove(line)
    removed.append(line)
    KEEP.append(line)


def obstacles(board, layer, skip, skip_lines=False):
    """Boxes another silk item on `layer` must clear: silk items (without
    the section lines when `skip_lines`) and the pads on that side.
    """
    copper = pcbnew.F_Cu if layer == pcbnew.F_SilkS else pcbnew.B_Cu
    boxes = []
    for uuid, item in silk_items(board).items():
        # SWIG hands out a new wrapper per lookup: compare by uuid
        if uuid == skip.m_Uuid.AsString() or item.GetLayer() != layer:
            continue
        if is_text(item) and not item.IsVisible():
            continue
        if skip_lines and is_section_line(item):
            continue
        boxes.append(Box.of(item))
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.IsOnLayer(copper):
                boxes.append(Box.of(pad))
    return boxes


def nudge(board, text):
    """Moves a text to the nearest clear spot (a section name only slides
    along its border; other texts may also turn 90 degrees). Returns True on
    success.
    """
    outline = board.GetBoardEdgesBoundingBox()
    inner = Box(outline.GetLeft() / 1e6 + 0.5, outline.GetTop() / 1e6 + 0.5,
                outline.GetRight() / 1e6 - 0.5, outline.GetBottom() / 1e6 - 0.5)
    section = is_section_name(text)
    blocked = [
        box.grown(CLEARANCE)
        for box in obstacles(board, text.GetLayer(), text, skip_lines=section)
    ]
    angles = (0,) if section else (0, 90)
    owner = text.GetParentFootprint()
    test_point = (owner is not None and owner.GetReference().startswith('TP')
                  and text.Type() == pcbnew.PCB_FIELD_T and not text.IsReference())
    steps = TEST_POINT_STEPS if test_point else NUDGE_STEPS
    start_angle = text.GetTextAngleDegrees()
    for angle in angles:
        # turn between reading across and reading up, never upside down
        text.SetTextAngleDegrees(start_angle if angle == 0 else (90 if start_angle % 180 == 0 else 0))
        here = Box.of(text)
        for step in steps:
            directions = ((-step, 0), (step, 0)) if section else (
                (0, -step), (0, step), (-step, 0), (step, 0),
                (-step, -step), (step, -step), (-step, step), (step, step))
            if test_point:
                # every grid spot at this distance, not just the eight rays
                count = int(round(step / 0.25))
                directions = [
                    (0.25 * ix, 0.25 * iy)
                    for ix in range(-count, count + 1)
                    for iy in range(-count, count + 1)
                    if max(abs(ix), abs(iy)) == count
                ]
            for delta_x, delta_y in directions:
                moved = here.shifted(delta_x, delta_y)
                if not (inner.left <= moved.left and moved.right <= inner.right
                        and inner.top <= moved.top and moved.bottom <= inner.bottom):
                    continue
                if any(moved.overlaps(box) for box in blocked):
                    continue
                if test_point and not nearest_own(board, owner, moved):
                    continue
                old_box = Box.of(text)
                text.Move(pcbnew.VECTOR2I(pcbnew.FromMM(delta_x), pcbnew.FromMM(delta_y)))
                if section:
                    redraw_border(board, text, old_box)
                return True
    text.SetTextAngleDegrees(start_angle)
    return False


def nearest_own(board, owner, box):
    """True if a name box is nearer its own test point than any other."""
    center_x = (box.left + box.right) / 2
    center_y = (box.top + box.bottom) / 2

    def distance(footprint):
        position = footprint.GetPosition()
        return (position.x / 1e6 - center_x) ** 2 + (position.y / 1e6 - center_y) ** 2

    own = distance(owner)
    return all(
        distance(other) > own
        for other in board.GetFootprints()
        if other.GetReference().startswith('TP') and other.GetReference() != owner.GetReference()
    )


def drop_section_names(board):
    """Deletes the DROPPED_SECTION_NAMES texts and closes their border gaps.
    Returns the removed items (kept referenced until the board is saved).
    """
    removed = []
    for text in list(board.GetDrawings()):
        if not (is_section_name(text) and text.GetText() in DROPPED_SECTION_NAMES):
            continue
        box = Box.of(text)
        board.Remove(text)
        removed.append(text)
        KEEP.append(text)
        close_gap(board, text.GetLayer(), box)
    return removed


def close_gap(board, layer, box):
    """Joins the two border lines that end either side of a removed name."""
    line_y = (box.top + box.bottom) / 2
    lines = [
        drawing for drawing in board.GetDrawings()
        if drawing.GetLayer() == layer and is_section_line(drawing)
        and drawing.GetStart().y == drawing.GetEnd().y
        and abs(drawing.GetStart().y / 1e6 - line_y) < 0.05
    ]
    left_ends = [max(d.GetStart().x, d.GetEnd().x) / 1e6 for d in lines
                 if max(d.GetStart().x, d.GetEnd().x) / 1e6 <= box.left + 0.01]
    right_ends = [min(d.GetStart().x, d.GetEnd().x) / 1e6 for d in lines
                  if min(d.GetStart().x, d.GetEnd().x) / 1e6 >= box.right - 0.01]
    if not left_ends or not right_ends:
        return
    piece = lines[0].Duplicate()
    piece.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(max(left_ends)), lines[0].GetStart().y))
    piece.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(min(right_ends)), lines[0].GetStart().y))
    board.Add(piece)
    KEEP.append(piece)


def redraw_border(board, label, old_box):
    """Redraws the horizontal border a section name moved along: the old
    gap is closed and a new one opened under the name.
    """
    layer = label.GetLayer()
    line_y = (old_box.top + old_box.bottom) / 2
    lines = [
        drawing for drawing in board.GetDrawings()
        if drawing.GetLayer() == layer and is_section_line(drawing)
        and drawing.GetStart().y == drawing.GetEnd().y
        and abs(drawing.GetStart().y / 1e6 - line_y) < 0.05
    ]
    # the stretch to close: the old gap between the lines that end at it
    left_ends = [max(d.GetStart().x, d.GetEnd().x) / 1e6 for d in lines
                 if max(d.GetStart().x, d.GetEnd().x) / 1e6 <= old_box.left + 0.01]
    right_ends = [min(d.GetStart().x, d.GetEnd().x) / 1e6 for d in lines
                  if min(d.GetStart().x, d.GetEnd().x) / 1e6 >= old_box.right - 0.01]
    if not left_ends or not right_ends:
        return
    template = lines[0]
    gap_left, gap_right = max(left_ends), min(right_ends)
    new_box = Box.of(label).grown(LINE_GAP)
    for start_x, end_x in ((gap_left, new_box.left), (new_box.right, gap_right)):
        if end_x - start_x <= 0.2:
            continue
        piece = template.Duplicate()
        piece.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start_x), template.GetStart().y))
        piece.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end_x), template.GetStart().y))
        board.Add(piece)
        KEEP.append(piece)


def fix_once(path):
    """One DRC + fix round; returns (fixes made, texts hidden or deleted,
    texts nudged, findings left).
    """
    findings = drc_findings(path)
    board = pcbnew.LoadBoard(str(path))
    # removed items stay referenced until the save: freeing them while the
    # board is open corrupts it
    dropped = drop_section_names(board)
    removed, nudged, left = [], [], []
    hidden = [f'section {item.GetText()}' for item in dropped]
    items = silk_items(board)
    done = set()
    for uuids in findings:
        found = [items.get(uuid) for uuid in uuids]
        found = [item for item in found if item is not None]
        # one fix per item per round: the next DRC round sees the result
        touched = {item.m_Uuid.AsString() for item in found}
        if touched & done:
            continue
        done |= touched
        lines = [item for item in found if is_section_line(item)]
        texts = [item for item in found if is_text(item)]
        if lines and texts:
            cut_line(board, lines[0], Box.of(texts[0]).grown(LINE_GAP), removed)
            continue
        references = [item for item in found if is_reference(item) and item.IsVisible()]
        if references:
            references[0].SetVisible(False)
            hidden.append(references[0].GetText())
            continue
        # a test point's name outranks an ESP32 pin name; a footprint's own
        # marker text is dropped
        droppable = [
            item for item in texts
            if item.IsVisible() and (is_footprint_text(item) or (
                is_esp32_name(item) and len(texts) > 1))
        ]
        if droppable:
            # board and footprint texts cannot be hidden: delete them
            dropped = droppable[0]
            owner = dropped.GetParentFootprint()
            (owner if owner is not None else board).Remove(dropped)
            removed.append(dropped)
            hidden.append(dropped.GetText())
            continue
        movable = [item for item in texts if item.IsVisible()]
        moved = next((item for item in movable if nudge(board, item)), None)
        if moved is not None:
            nudged.append(moved.GetText())
            continue
        left.append(' / '.join(
            item.GetText() if is_text(item) else item.GetClass() for item in found
        ))
    board.Save(str(path))
    del dropped  # KEEP and removed hold the rest
    return len(removed) + len(hidden) + len(nudged), hidden, nudged, left


def main():
    path = Path(sys.argv[1])
    if len(sys.argv) > 2:  # one round in its own process (pcbnew loads a board once)
        fixed, hidden, nudged, left = fix_once(path)
        print(f'fixed {fixed}; hidden or deleted {hidden}; nudged {nudged}')
        print('left (not fixable here):', left)
        sys.exit(3 if fixed else 0)
    for _ in range(4):
        round_run = subprocess.run([sys.executable, __file__, str(path), 'once'])
        if round_run.returncode != 3:
            break


if __name__ == '__main__':
    main()
