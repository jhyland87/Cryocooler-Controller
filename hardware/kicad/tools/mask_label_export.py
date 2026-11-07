"""Exports the board geometry `mask_label_plan.py` needs, because KiCad's Python has no
numpy and the system Python has no pcbnew. Movable labels (references, visible values and
text naming a part) go in `items`. Everything else that stays put goes in the fixed lists.

Usage: mask_label_export.py board.kicad_pcb out.json (KiCad's bundled Python)
"""
import json
import sys

import pcbnew

from label_owners import NAMED_PARTS
from mask_labels import ARROW_GROUP
import silk_fix

ERROR = pcbnew.FromMM(0.005)
MAX_VALUE_DISTANCE = pcbnew.FromMM(3)  # farther text of the same name isn't this test point's
COPPER = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
SILK = {'F': pcbnew.F_SilkS, 'B': pcbnew.B_SilkS}
MASK = {'F': pcbnew.F_Mask, 'B': pcbnew.B_Mask}
FAB = {'F': pcbnew.F_Fab, 'B': pcbnew.B_Fab}
EXTRA_NAMED_PARTS = {'RESET': 'SW1', 'BOOT': 'SW2'}
# text this tool never moves: board ID and names printed on part bodies
FIXED_TEXT = {'POWER & RAILS', 'POWER IN', 'cryocooler', 'ACS37800', 'ISOW7741',
              'TO CRYO-\nCOOLER'}


def to_mm(value):
    return value / 1e6


def add_shape(item, layer, polygons):
    if isinstance(item, pcbnew.PCB_TEXT):
        item.TransformTextToPolySet(polygons, 0, ERROR, pcbnew.ERROR_INSIDE)
    else:
        item.TransformShapeToPolygon(polygons, layer, 0, ERROR, pcbnew.ERROR_INSIDE)


def outlines(polygons):
    """Returns fractured outlines: holes become part of the outline, so they fill correctly."""
    polygons.Simplify()
    polygons.Fracture()
    result = []
    for index in range(polygons.OutlineCount()):
        outline = polygons.Outline(index)
        result.append([(to_mm(outline.CPoint(point).x), to_mm(outline.CPoint(point).y))
                       for point in range(outline.PointCount())])
    return result


def box_of(item):
    bounds = item.GetBoundingBox()
    return [to_mm(bounds.GetLeft()), to_mm(bounds.GetTop()),
            to_mm(bounds.GetRight()), to_mm(bounds.GetBottom())]


def text_record(item, side, kind, **extra):
    return dict(kind=kind, text=item.GetText(), side=side, x=to_mm(item.GetPosition().x),
                y=to_mm(item.GetPosition().y), angle=item.GetTextAngleDegrees(),
                box=box_of(item), visible=item.IsVisible(), **extra)


def fixed_text(item):
    return (silk_fix.is_section_name(item) or item.GetText() in FIXED_TEXT
            or item.GetText().startswith('BETA rev') or silk_fix.is_esp32_name(item))


def nearest_value_owner(board, label, text_item, copper):
    """Returns the closest test point on this side whose hidden value field reads `label`."""
    position = text_item.GetPosition()
    matches = [footprint for footprint in board.GetFootprints()
               if footprint.GetReference().startswith('TP') and footprint.GetLayer() == copper
               and footprint.GetValue() == label and not footprint.Value().IsVisible()
               and (footprint.GetPosition() - position).EuclideanNorm() < MAX_VALUE_DISTANCE]
    if not matches:
        return None
    closest = min(matches, key=lambda footprint: (footprint.GetPosition() - position).EuclideanNorm())
    return closest.GetReference()


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    named = dict(NAMED_PARTS, **EXTRA_NAMED_PARTS)
    arrow_items = set()
    for group in board.Groups():
        if group.GetName() == ARROW_GROUP:
            arrow_items = {item.m_Uuid.AsString() for item in group.GetItems()}
    references = {footprint.GetReference() for footprint in board.GetFootprints()}
    result = {'items': [], 'bodies': {'F': {}, 'B': {}}, 'parts': {'F': {}, 'B': {}}, 'vias': []}
    for key in ('pour', 'silk', 'mask', 'pads', 'body', 'no_mask'):
        result[key] = {}
    for side in COPPER:
        pour, silk, mask, pads, bodies, no_mask = (pcbnew.SHAPE_POLY_SET() for _ in range(6))
        for zone in board.Zones():
            copper = COPPER[side]
            if (zone.GetNetname() in ('GND', 'ISO_GND') and zone.IsOnLayer(copper)
                    and zone.HasFilledPolysForLayer(copper)):
                pour.BooleanAdd(zone.GetFilledPolysList(copper))
        for drawing in board.GetDrawings():
            if drawing.m_Uuid.AsString() in arrow_items:
                continue
            is_text = isinstance(drawing, pcbnew.PCB_TEXT)
            if drawing.GetLayer() == SILK[side]:
                if is_text and not fixed_text(drawing):
                    owner = named.get(drawing.GetText())
                    result['items'].append(text_record(drawing, side, 'board', uuid=drawing.m_Uuid.AsString(), ref=owner))
                else:
                    add_shape(drawing, SILK[side], silk)
            elif drawing.GetLayer() == MASK[side]:
                if is_text:
                    label = drawing.GetText()
                    # a mask label of a reference is the field's own label, already an item
                    # unless it's a test point, whose hidden field isn't exported
                    if label in references:
                        if label.startswith('TP'):
                            result['items'].append(text_record(drawing, side, 'ref', ref=label, on_mask=True))
                        continue
                    owner = nearest_value_owner(board, label, drawing, COPPER[side])
                    if owner:
                        result['items'].append(text_record(drawing, side, 'value', ref=owner, on_mask=True))
                    else:
                        result['items'].append(text_record(drawing, side, 'board', uuid=drawing.m_Uuid.AsString(), ref=named.get(label), on_mask=True))
                else:
                    add_shape(drawing, MASK[side], no_mask)
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                if pad.IsOnLayer(COPPER[side]):
                    pad.TransformShapeToPolygon(pads, COPPER[side], 0, ERROR, pcbnew.ERROR_INSIDE)
            for graphic in footprint.GraphicalItems():
                if isinstance(graphic, pcbnew.PCB_TEXT):
                    continue
                if graphic.GetLayer() == SILK[side]:
                    add_shape(graphic, SILK[side], silk)
                elif graphic.GetLayer() == FAB[side]:
                    add_shape(graphic, FAB[side], bodies)
            if (footprint.GetLayer() == COPPER[side]):
                parts = [box_of(pad) for pad in footprint.Pads()]
                parts += [box_of(graphic) for graphic in footprint.GraphicalItems()
                          if graphic.GetLayer() == FAB[side] and not isinstance(graphic, pcbnew.PCB_TEXT)]
                reference = footprint.GetReference()
                if parts:
                    result['bodies'][side][reference] = [min(box[0] for box in parts), min(box[1] for box in parts),
                                                         max(box[2] for box in parts), max(box[3] for box in parts)]
                    result['parts'][side][reference] = footprint.GetOrientationDegrees()
                field = footprint.Reference()
                if reference and reference != 'U1' and (field.IsVisible() or not reference.startswith('TP')):
                    result['items'].append(text_record(field, side, 'ref', ref=reference))
                value = footprint.Value()
                if value.IsVisible() and value.GetLayer() in (SILK[side], MASK[side]):
                    result['items'].append(text_record(value, side, 'value', ref=reference))
        result['pour'][side], result['silk'][side] = outlines(pour), outlines(silk)
        result['mask'][side], result['pads'][side] = outlines(mask), outlines(pads)
        result['body'][side], result['no_mask'][side] = outlines(bodies), outlines(no_mask)
    result['vias'] = [[to_mm(track.GetPosition().x), to_mm(track.GetPosition().y), to_mm(track.GetWidth(pcbnew.F_Cu)),
                       track.GetNetname() in ('GND', 'ISO_GND')]
                      for track in board.GetTracks() if isinstance(track, pcbnew.PCB_VIA)]
    edges = board.GetBoardEdgesBoundingBox()
    result['edge'] = [to_mm(edges.GetLeft()), to_mm(edges.GetTop()), to_mm(edges.GetRight()), to_mm(edges.GetBottom())]
    with open(sys.argv[2], 'w') as out:
        json.dump(result, out)
    print('items', len(result['items']))


if __name__ == '__main__':
    main()
