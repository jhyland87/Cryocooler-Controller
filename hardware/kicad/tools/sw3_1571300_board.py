"""Moves SW3 (power button) to the right edge as a TE 1571300-2 right-angle switch.

The front face sits on the edge at x 120, so the actuator sticks 2.7 mm out of the board.
The old TL6800AF lands go; the PB track that ran between its two pad-1 lands stays, so
J7 and U11 keep their connection. PB runs on In2 from J7 pin 1 to a via beside pad 1
(the corridor `gridroute.py` found clear of the mask labels, straightened). Pad 2
gets a GND via. Run `gen_pcb.py link` and `mask_labels.py` afterwards.

Usage: sw3_1571300_board.py board.kicad_pcb (edits in place, run it once)
"""
import sys
from pathlib import Path

import pcbnew

import pcbmodels

LIB = str(Path(__file__).resolve().parents[1] / 'lib' / 'cryocooler.pretty')
FOOTPRINT = 'SW_TE_1571300-2'
ORIGIN = (117.25, 80.0)  # body centre; rotation 90 points the actuator at +x
MM = pcbnew.FromMM
KEEP = []  # removed and added items stay referenced, or SWIG frees them under the board

# old pad-2 GND run on F.Cu (some segments are doubled), and the stitching vias under the
# new body
RIP_TRACKS = (
    ('GND', ((22.671, 96.848), (22.671, 97.647))),
    ('GND', ((22.671, 97.647), (22.723, 97.7))),
    ('GND', ((23.85, 97.7), (22.723, 97.7))),
    ('GND', ((30.15, 97.7), (23.85, 97.7))),
)
RIP_VIAS = (('GND', 116.0, 76.0), ('GND', 116.0, 80.0), ('GND', 116.0, 84.0))
PB = 'Net-(J7-Pin_1)'
TRACKS = (
    ('GND', pcbnew.F_Cu, 0.3, ((115.0, 78.0), (113.3, 78.0))),
    (PB, pcbnew.In2_Cu, 0.2, ((34.8, 86.7), (35.4, 87.3), (36.1, 87.3), (36.8, 88.0),
                              (39.15, 88.0), (39.7, 88.55), (45.9, 88.55), (48.6, 91.25),
                              (53.25, 91.25), (54.45, 92.45), (74.75, 92.45), (75.75, 91.45),
                              (81.95, 91.45), (83.7, 89.7), (89.65, 89.7), (90.75, 88.6),
                              (100.4, 88.6), (107.0, 82.0), (114.95, 82.0))),
    (PB, pcbnew.F_Cu, 0.2, ((114.95, 82.0), (116.75, 82.0))),
)
VIAS = (('GND', 113.3, 78.0, 0.6, 0.3), (PB, 114.95, 82.0, 0.45, 0.2))


def point(item_point):
    return round(item_point.x / 1e6, 3), round(item_point.y / 1e6, 3)


def rip(board):
    """Removes every listed segment and via (duplicates included); fails if one is missing."""
    wanted = {(name, frozenset(ends)) for name, ends in RIP_TRACKS}
    found = set()
    for item in list(board.GetTracks()):
        if item.Type() == pcbnew.PCB_VIA_T:
            key = (item.GetNetname(), *point(item.GetPosition()))
            if key not in RIP_VIAS:
                continue
        else:
            key = (item.GetNetname(), frozenset((point(item.GetStart()), point(item.GetEnd()))))
            if item.GetLayer() != pcbnew.F_Cu or key not in wanted:
                continue
        found.add(key)
        KEEP.append(item)
        board.Remove(item)
    missing = (wanted | set(RIP_VIAS)) - found
    if missing:
        raise SystemExit(f'not found: {missing}')


def swap_sw3(board):
    old = board.FindFootprintByReference('SW3')
    nets = {pad.GetNumber(): pad.GetNetname() for pad in old.Pads()}
    new = pcbnew.FootprintLoad(LIB, FOOTPRINT)
    new.SetReference('SW3')
    new.SetValue(old.GetValue())
    new.SetPath(old.GetPath())
    new.SetSheetname(old.GetSheetname())
    new.SetSheetfile(old.GetSheetfile())
    new.SetFPIDAsString(f'cryocooler:{FOOTPRINT}')
    board.Add(new)
    new.SetPosition(pcbnew.VECTOR2I(MM(ORIGIN[0]), MM(ORIGIN[1])))
    new.SetOrientationDegrees(90.0)
    new.Reference().SetVisible(False)
    new.Value().SetVisible(False)
    for pad in new.Pads():
        if pad.GetNumber():
            pad.SetNet(board.FindNet(nets[pad.GetNumber()]))
    pcbmodels.attach_missing_models(new)
    KEEP.extend((old, new))
    board.Remove(old)
    for pad in new.Pads():
        print('pad', pad.GetNumber() or '-', point(pad.GetPosition()), pad.GetNetname())


def add_copper(board):
    for name, layer, width, points in TRACKS:
        for first, second in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(MM(first[0]), MM(first[1])))
            track.SetEnd(pcbnew.VECTOR2I(MM(second[0]), MM(second[1])))
            track.SetLayer(layer)
            track.SetWidth(MM(width))
            track.SetNet(board.FindNet(name))
            board.Add(track)
            KEEP.append(track)
    for name, x_mm, y_mm, diameter, drill in VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetWidth(MM(diameter))
        via.SetDrill(MM(drill))
        via.SetNet(board.FindNet(name))
        board.Add(via)
        KEEP.append(via)


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    rip(board)
    swap_sw3(board)
    add_copper(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
