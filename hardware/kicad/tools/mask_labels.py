"""Turns the board's labels into small solder mask openings over the ground pours, using
the positions in `mask_labels.json`. R, C and D references are 0.5 mm and everything else
is 0.7 mm, because silk can't go under 1.0 mm. The exposed copper forms the letters, so
order ENIG: HASL would blur them. `mask_label_plan.py` chooses the positions: centred on
an edge of the part where possible, 1.0 mm silk (`silk: true`) where mask won't fit, and a
silk arrow as the last resort. Section names, box lines, the board ID and part-body names
are left alone.

Safe to run again; it replaces its own text and arrows. The positions fit the committed
route and silk, and they don't follow a moved part. Run this after `silk_fix.py`, which
could cut the arrows, and re-run DRC after any reroute or refill.

Usage: mask_labels.py board.kicad_pcb (edits in place)
"""
import json
import math
import sys
from pathlib import Path

import pcbnew

LABEL_FILE = Path(__file__).with_name('mask_labels.json')
STROKE = 0.1  # thinner strokes leave a sliver in the 9; "8" keeps 0.115 mm of mask at 0.5 mm
SILK_TEXT_WIDTH = 0.9
SILK_TEXT_HEIGHT = 1.0
SILK_STROKE = 0.15
LEADER_WIDTH = 0.15  # JLCPCB's silk line minimum
ARROW_LENGTH = 0.5
ARROW_WIDTH = 0.4
ARROW_GROUP = 'mask_label_arrows'
MASK_LAYERS = {'F': pcbnew.F_Mask, 'B': pcbnew.B_Mask}
SILK_LAYERS = {'F': pcbnew.F_SilkS, 'B': pcbnew.B_SilkS}


def add_label(board, label):
    """Adds one centred label on the mask layer of its side, mirrored on the back."""
    text = pcbnew.PCB_TEXT(board)
    text.SetText(label['text'])
    if label.get('silk'):
        text.SetLayer(SILK_LAYERS[label['side']])
        text.SetTextSize(pcbnew.VECTOR2I_MM(SILK_TEXT_WIDTH, SILK_TEXT_HEIGHT))
        text.SetTextThickness(pcbnew.FromMM(SILK_STROKE))
    else:
        text.SetLayer(MASK_LAYERS[label['side']])
        text.SetTextSize(pcbnew.VECTOR2I_MM(label['size'], label['size']))
        text.SetTextThickness(pcbnew.FromMM(STROKE))
    text.SetPosition(pcbnew.VECTOR2I_MM(label['x'], label['y']))
    text.SetTextAngleDegrees(label['angle'])
    text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    text.SetMirrored(label['side'] == 'B')
    board.Add(text)
    return text


def add_arrow(board, group, side, points):
    """Draws a silk leader along `points`, with a filled arrowhead at the first point."""
    (tip_x, tip_y), (next_x, next_y) = points[:2]
    length = math.hypot(next_x - tip_x, next_y - tip_y)
    unit_x, unit_y = (next_x - tip_x) / length, (next_y - tip_y) / length
    base_x, base_y = tip_x + unit_x * ARROW_LENGTH, tip_y + unit_y * ARROW_LENGTH
    half = ARROW_WIDTH / 2
    head = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    head.SetPolyPoints([pcbnew.VECTOR2I_MM(*corner) for corner in (
        (tip_x, tip_y),
        (base_x - unit_y * half, base_y + unit_x * half),
        (base_x + unit_y * half, base_y - unit_x * half),
    )])
    head.SetFilled(True)
    head.SetWidth(0)
    shapes = [head]
    for start, end in zip([(base_x, base_y)] + points[1:-1], points[1:]):
        line = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(pcbnew.VECTOR2I_MM(*start))
        line.SetEnd(pcbnew.VECTOR2I_MM(*end))
        line.SetWidth(pcbnew.FromMM(LEADER_WIDTH))
        shapes.append(line)
    for shape in shapes:
        shape.SetLayer(SILK_LAYERS[side])
        board.Add(shape)
        group.AddItem(shape)
    return shapes


def remove_previous(board, removed):
    """Removes mask text and arrows from an earlier run, keeping wrappers in `removed`."""
    for group in [group for group in board.Groups() if group.GetName() == ARROW_GROUP]:
        for item in list(group.GetItems()):
            group.RemoveItem(item)
            board.Remove(item)
            removed.append(item)
        board.Remove(group)
        removed.append(group)
    layers = set(MASK_LAYERS.values())
    for item in [item for item in board.GetDrawings()
                 if isinstance(item, pcbnew.PCB_TEXT) and item.GetLayer() in layers]:
        board.Remove(item)
        removed.append(item)


def hide_silk(board, labels, removed):
    """Hides the silk field, or deletes the board text, that each mask label replaces."""
    by_uuid = {item.m_Uuid.AsString(): item for item in board.GetDrawings()}
    for label in labels:
        if label['kind'] in ('ref', 'value'):
            footprint = board.FindFootprintByReference(label['ref'])
            field = footprint.Reference() if label['kind'] == 'ref' else footprint.Value()
            field.SetVisible(False)
        elif label.get('uuid') in by_uuid:
            item = by_uuid[label['uuid']]
            board.Remove(item)
            removed.append(item)


def main():
    path = sys.argv[1]
    labels = json.loads(LABEL_FILE.read_text())
    board = pcbnew.LoadBoard(path)
    # SWIG frees removed or added items when their wrappers die: keep them until the save
    kept = []
    remove_previous(board, kept)
    hide_silk(board, labels, kept)
    group = pcbnew.PCB_GROUP(board)
    group.SetName(ARROW_GROUP)
    board.Add(group)
    kept.append(group)
    for label in labels:
        text = add_label(board, label)
        kept.append(text)
        if label.get('silk'):
            group.AddItem(text)  # lets the next run find and replace it
        if label.get('arrow'):
            kept.extend(add_arrow(board, group, label['side'], label['arrow']))
    board.Save(path)
    arrows = sum(1 for label in labels if label.get('arrow'))
    print(f'mask labels: {len(labels)}, {arrows} with arrows')


if __name__ == '__main__':
    main()
