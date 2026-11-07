"""Swaps J12 for the TE 643228-1 on the routed board, mating face 3 mm past the left edge.

Its cavities read GND, -, + top to bottom along the wall, so pin 3 (GND) lands above the
two isolated pins. A GND strip now runs up the wall to pin 3, and ISO_GND wraps round its
east end into a lobe around pins 2 and 1. The strip and lobe keep the 1.5 mm barrier on all
layers. J11 moves up and left to clear the ear and U18. Run `mask_labels.py` afterwards.

Usage: j12_643228_board.py board.kicad_pcb (edits in place, run it once)
"""
import sys
from pathlib import Path

import pcbnew

import pcbmodels

LIB = str(Path(__file__).resolve().parents[1] / 'lib' / 'cryocooler.pretty')
FOOTPRINT = 'TE_643228-1_1x03_P6.35mm_Horizontal'
PIN_LINE_X, PIN_1_Y = 12.37, 45.8
J11_SPOT = (8.75, 11.42)
HOLES = ((9.83, 53.165), (9.83, 25.735))
WASHER_RADIUS = 3.5

J11_PLUS = 'Net-(J11-Pin_1)'
J12_PLUS = 'Net-(J12-Pin_1)'
RAW = 'Net-(F1-Pad1)'

# ISO_GND outline, and the path 1.5 mm away from it on the GND side
BARRIER_ISO = ((25.25, 40.5), (16.3, 40.5), (16.3, 42.9), (15.2, 44.0), (15.2, 45.8), (13.2, 47.8),
               (10.37, 47.8), (10.37, 36.6), (15.87, 36.6), (15.87, 29.6), (0.0, 29.6))
BARRIER_GND = ((25.25, 42.0), (17.8, 42.0), (17.8, 43.52), (16.7, 44.62), (16.7, 46.42),
               (13.82, 49.3), (8.87, 49.3), (8.87, 35.1), (14.37, 35.1), (14.37, 31.1),
               (0.0, 31.1))
ISO_OUTLINE = ((0.0, 0.0), (25.25, 0.0), *BARRIER_ISO)
OLD_BAND = (0.0, 40.5, 25.25, 42.0)
# the two old bands only touched at (25.25, 40.5), which let pours within 0.3 mm of ISO_GND
CORNER = ((25.25, 40.5), (26.75, 40.5), (26.75, 42.0), (25.25, 42.0))

# (net, layer, width, points)
RIP_TRACKS = (
    ('ISO_GND', ((8.6, 26.0), (7.0, 26.0))),
    ('ISO_GND', ((7.0, 26.0), (7.0, 38.5))),
    ('ISO_GND', ((7.0, 38.5), (8.6, 38.5))),
    (J11_PLUS, ((10.7, 20.1), (10.7, 21.0))),
    (J11_PLUS, ((10.7, 20.1), (10.7, 11.5))),
    (J12_PLUS, ((13.0, 30.6), (13.0, 17.2))),
    (J12_PLUS, ((13.0, 33.5), (13.0, 30.6))),
    (RAW, ((9.5, 78.0), (9.5, 52.0))),
    (RAW, ((9.5, 52.0), (11.5, 50.0))),
    (RAW, ((11.5, 50.0), (11.5, 49.95))),
    (RAW, ((11.5, 49.95), (19.0, 49.95))),
)
RIP_VIAS = (
    *[(J12_PLUS, x_mm, y_mm) for x_mm in (12.2, 13.0, 13.8) for y_mm in (29.6, 30.6)],
    *[('ISO_GND', x_mm, y_mm) for x_mm, y_mm in (
        (8.0, 12.0), (8.0, 16.0), (8.0, 24.0), (16.0, 28.0), (6.8, 30.0), (6.8, 32.0), (6.8, 34.0),
        (6.8, 36.0), (16.0, 32.0), (16.0, 36.0))],
    *[('GND', x_mm, y_mm) for x_mm, y_mm in (
        (16.0, 44.0), (16.0, 48.0), (12.0, 48.0), (12.0, 52.0), (8.0, 52.0), (12.0, 56.0))],
)
TRACKS = (
    # + from pin 1, north past pins 2 and 3 to the via group beside U18; 1.6 mm past the tab
    (J12_PLUS, pcbnew.B_Cu, 2.0, ((12.37, 45.35), (15.15, 42.57), (15.15, 38.83), (16.7, 37.28))),
    (J12_PLUS, pcbnew.B_Cu, 1.6, ((16.7, 37.28), (16.7, 29.2), (14.9, 27.4))),
    (J12_PLUS, pcbnew.B_Cu, 2.0, ((14.9, 27.4), (14.9, 21.1), (13.0, 19.2), (13.0, 17.2))),
    # - from pin 2 to J11 pin 2, the same way; 1.2 mm past the tab, with the pours in parallel
    ('ISO_GND', pcbnew.F_Cu, 2.0, ((12.37, 39.45), (15.13, 39.45), (16.5, 38.08))),
    ('ISO_GND', pcbnew.F_Cu, 1.2, ((16.5, 38.08), (16.5, 29.3), (15.2, 28.0))),
    ('ISO_GND', pcbnew.F_Cu, 2.0, ((15.2, 28.0), (13.2, 26.0), (13.2, 23.2), (10.7, 20.7),
                                   (10.7, 16.9))),
    # raw 12 V, round the lower hole
    (RAW, pcbnew.F_Cu, 2.0, ((9.5, 78.0), (9.5, 59.0), (13.2, 55.3), (13.2, 52.2), (15.0, 50.4),
                             (19.0, 50.4))),
)
VIAS = (
    ('ISO_GND', 8.0, 21.0), ('ISO_GND', 5.0, 26.0), ('ISO_GND', 11.2, 42.2),
    ('GND', 4.0, 32.0), ('GND', 4.0, 38.0),
)

# silk: (layer, x0, y0, x1, y1) removed, then lines added
SILK_REMOVE = (
    (pcbnew.F_SilkS, 0.5, 47.8, 13.5, 47.8),
    (pcbnew.F_SilkS, 13.5, 44.8, 13.5, 47.8),
    (pcbnew.F_SilkS, 13.5, 42.0, 22.0, 42.0),
    (pcbnew.B_SilkS, 0.5, 47.8, 13.5, 47.8),
    (pcbnew.B_SilkS, 13.5, 42.0, 13.5, 47.8),
    (pcbnew.B_SilkS, 13.5, 47.8, 13.5, 51.25),
    (pcbnew.B_SilkS, 13.5, 53.55, 13.5, 56.33),
    (pcbnew.B_SilkS, 13.5, 42.0, 22.0, 42.0),
)
SILK_ADD = (
    (pcbnew.F_SilkS, 16.1, 42.0, 22.0, 42.0),
    (pcbnew.F_SilkS, 16.1, 42.0, 16.1, 52.1),
    (pcbnew.F_SilkS, 16.1, 52.1, 14.6, 53.6),
    (pcbnew.F_SilkS, 14.6, 53.6, 14.6, 58.7),
    (pcbnew.B_SilkS, 14.6, 42.0, 22.0, 42.0),
    (pcbnew.B_SilkS, 14.6, 42.0, 14.6, 51.25),
    (pcbnew.B_SilkS, 14.6, 53.55, 14.6, 56.33),
)
# (old text, old x, old y) -> (new text, new x, new y)
TEXT_MOVES = {
    ('FROM AMP', 9.0, 16.35): ('FROM\nAMP', 3.2, 22.9),
    ('TO CRYO-\nCOOLER', 18.65, 38.35): ('TO CRYO-\nCOOLER', 20.7, 38.2),
    ('AMP SIGNAL', 9.0, 57.3): ('AMP\nSIGNAL', 3.2, 56.5),
    ('-', 15.0, 26.0): ('-', 10.4, 14.75),
    ('+', 15.0, 33.5): ('+', 15.4, 45.8),
}
KEEP = []


def point(x_mm, y_mm):
    return pcbnew.VECTOR2I_MM(x_mm, y_mm)


def near(first, second, margin=0.02):
    return abs(first - second) <= margin


def rip_copper(board):
    tracks = list(RIP_TRACKS)
    vias = list(RIP_VIAS)
    for item in list(board.GetTracks()):
        name = item.GetNetname()
        spot_list = None
        if item.Type() == pcbnew.PCB_VIA_T:
            spot = pcbnew.ToMM(item.GetPosition().x), pcbnew.ToMM(item.GetPosition().y)
            match = next((via for via in vias if via[0] == name and near(via[1], spot[0])
                          and near(via[2], spot[1])), None)
            if match is None:
                continue
            vias.remove(match)
        else:
            ends = {(round(pcbnew.ToMM(end.x), 2), round(pcbnew.ToMM(end.y), 2))
                    for end in (item.GetStart(), item.GetEnd())}
            match = next((track for track in tracks if track[0] == name
                          and {tuple(end) for end in track[1]} == ends), None)
            if match is None:
                continue
            tracks.remove(match)
        KEEP.append(item)
        board.Remove(item)
    if tracks or vias:
        raise RuntimeError(f'copper not found: {tracks} {vias}')


def add_copper(board):
    for name, layer, width, points in TRACKS:
        net = board.FindNet(name)
        for first, second in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(point(*first))
            track.SetEnd(point(*second))
            track.SetWidth(pcbnew.FromMM(width))
            track.SetLayer(layer)
            track.SetNet(net)
            board.Add(track)
            KEEP.append(track)
    for name, x_mm, y_mm in VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(x_mm, y_mm))
        via.SetWidth(pcbnew.FromMM(0.6))
        via.SetDrill(pcbnew.FromMM(0.3))
        via.SetNet(board.FindNet(name))
        board.Add(via)
        KEEP.append(via)


def swap_j12(board):
    old = board.FindFootprintByReference('J12')
    nets = {pad.GetNumber(): pad.GetNetname() for pad in old.Pads()}
    new = pcbnew.FootprintLoad(LIB, FOOTPRINT)
    new.SetReference('J12')
    new.SetValue(old.GetValue())
    new.SetPath(old.GetPath())
    new.SetSheetname(old.GetSheetname())
    new.SetSheetfile(old.GetSheetfile())
    new.SetFPIDAsString(f'cryocooler:{FOOTPRINT}')
    board.Add(new)
    new.SetPosition(point(PIN_LINE_X, PIN_1_Y))
    new.SetOrientationDegrees(90.0)
    new.Reference().SetVisible(False)
    new.Value().SetVisible(False)
    new.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText(
        old.GetField(pcbnew.FIELD_T_DESCRIPTION).GetText())
    new.GetField(pcbnew.FIELD_T_DATASHEET).SetText(
        'https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv'
        '&DocNm=643228&DocType=Customer+Drawing&DocLang=English')
    product = pcbnew.PCB_FIELD(new, pcbnew.FIELD_T_USER, 'Product')
    product.SetText(
        'https://www.digikey.com/en/products/detail/te-connectivity-amp-connectors/643228-1/297685')
    product.SetVisible(False)
    product.SetLayer(pcbnew.F_Fab)
    new.Add(product)
    KEEP.append(product)
    for pad in new.Pads():
        if pad.GetNumber():
            pad.SetNet(board.FindNet(nets[pad.GetNumber()]))
    pcbmodels.attach_missing_models(new)
    KEEP.append(old)
    board.Remove(old)
    KEEP.append(new)


def set_outline(zone, points):
    outline = zone.Outline()
    outline.RemoveAllContours()
    outline.NewOutline()
    for x_mm, y_mm in points:
        outline.Append(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def reshape_zones(board):
    changed = 0
    for zone in board.Zones():
        if not zone.GetIsRuleArea() and zone.GetNetname() == 'ISO_GND':
            set_outline(zone, ISO_OUTLINE)
            changed += 1
            continue
        box = zone.GetBoundingBox()
        spans = (pcbnew.ToMM(box.GetLeft()), pcbnew.ToMM(box.GetTop()),
                 pcbnew.ToMM(box.GetRight()), pcbnew.ToMM(box.GetBottom()))
        if zone.GetIsRuleArea() and all(near(*pair, 0.1) for pair in zip(spans, OLD_BAND)):
            set_outline(zone, (*BARRIER_ISO, *reversed(BARRIER_GND)))
            changed += 1
    if changed != 5:
        raise RuntimeError(f'expected 4 ISO zones and 1 band, changed {changed}')


def add_corner_keepout(board):
    """Pours only: +3V3 and +5V_OR tracks pass through this corner."""
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    layers = pcbnew.LSET()
    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        layers.AddLayer(layer)
    zone.SetLayerSet(layers)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowTracks(False)
    zone.SetDoNotAllowVias(False)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    polygon = pcbnew.SHAPE_POLY_SET()
    polygon.NewOutline()
    for x_mm, y_mm in CORNER:
        polygon.Append(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))
    zone.SetOutline(polygon)
    board.Add(zone)
    KEEP.extend((zone, polygon))


def add_washer_keepouts(board):
    """B.Cu circles under the ear screws, so a metal washer can't touch a pour or a track."""
    for x_mm, y_mm in HOLES:
        zone = pcbnew.ZONE(board)
        zone.SetIsRuleArea(True)
        layers = pcbnew.LSET()
        layers.AddLayer(pcbnew.B_Cu)
        zone.SetLayerSet(layers)
        zone.SetDoNotAllowZoneFills(True)
        zone.SetDoNotAllowTracks(True)
        zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowPads(False)
        zone.SetDoNotAllowFootprints(False)
        polygon = pcbnew.SHAPE_POLY_SET()
        polygon.NewOutline()
        for step in range(24):
            angle = pcbnew.EDA_ANGLE(step * 15.0, pcbnew.DEGREES_T)
            polygon.Append(pcbnew.FromMM(x_mm + WASHER_RADIUS * angle.Cos()),
                           pcbnew.FromMM(y_mm + WASHER_RADIUS * angle.Sin()))
        zone.SetOutline(polygon)
        board.Add(zone)
        KEEP.extend((zone, polygon))


def edit_silk(board):
    remove = list(SILK_REMOVE)
    for item in list(board.GetDrawings()):
        if item.GetClass() != 'PCB_SHAPE':
            continue
        ends = (pcbnew.ToMM(item.GetStart().x), pcbnew.ToMM(item.GetStart().y),
                pcbnew.ToMM(item.GetEnd().x), pcbnew.ToMM(item.GetEnd().y))
        match = next((line for line in remove if line[0] == item.GetLayer()
                      and all(near(*pair) for pair in zip(line[1:], ends))), None)
        if match is None:
            continue
        remove.remove(match)
        KEEP.append(item)
        board.Remove(item)
    if remove:
        raise RuntimeError(f'silk not found: {remove}')
    for layer, x0, y0, x1, y1 in SILK_ADD:
        line = pcbnew.PCB_SHAPE(board)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(point(x0, y0))
        line.SetEnd(point(x1, y1))
        line.SetLayer(layer)
        line.SetWidth(pcbnew.FromMM(0.15))
        board.Add(line)
        KEEP.append(line)
    pending = dict(TEXT_MOVES)
    for item in board.GetDrawings():
        if item.GetClass() != 'PCB_TEXT' or item.GetLayer() != pcbnew.F_SilkS:
            continue
        spot = pcbnew.ToMM(item.GetPosition().x), pcbnew.ToMM(item.GetPosition().y)
        key = next((old for old in pending if old[0] == item.GetText()
                    and near(old[1], spot[0], 0.05) and near(old[2], spot[1], 0.05)), None)
        if key is None:
            continue
        text, x_mm, y_mm = pending.pop(key)
        item.SetText(text)
        item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        item.SetPosition(point(x_mm, y_mm))
    if pending:
        raise RuntimeError(f'text not found: {list(pending)}')


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    rip_copper(board)
    swap_j12(board)
    board.FindFootprintByReference('J11').SetPosition(point(*J11_SPOT))
    add_copper(board)
    reshape_zones(board)
    add_corner_keepout(board)
    add_washer_keepouts(board)
    edit_silk(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    print('saved', path)


if __name__ == '__main__':
    main()
