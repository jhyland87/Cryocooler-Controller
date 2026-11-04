"""Replaces J2 (12 V in) and J9 (amplifier signal) with SMT right-angle jacks on
the routed board: Tensility 54-00164 and Same Sky MJ-3523-SMT-TR, mouths at the
left board edge. Q5, Q6, TP36 and TP38 move to clear J9. Copper in the way is
removed and the jack power, ground and signal copper is drawn; the rest is left
for `gridroute.py` (Freerouting closes none of it). Then run `gen_pcb.py link` and
`finish`, `hand_route.py wall_jacks` and `silk_fix.py`.

Usage: wall_jacks.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

import pcbmodels
import ripup
from fan_headers import KEEP, LIB, MM

OLD_RAW_NET = 'Net-(J2-Pin_1)'
RAW_NET = 'Net-(F1-Pad1)'
SWITCH_NET = 'unconnected-(J9-SWITCH-Pad10)'
# reference -> (footprint, x, y, pad number -> net)
JACKS = {
    'J2': ('Tensility_54-00164_5.5x2.1mm_Horizontal_SMD', 0.0, 55.0,
           {'1': RAW_NET, '2': 'GND', '3': 'GND'}),
    'J9': ('SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD', 0.0, 66.3,
           {'1': 'GND', '2': 'SIG_SINE', '10': SWITCH_NET}),
}
MOVES = {'Q5': (20.0, 69.9), 'Q6': (16.0, 73.4), 'TP36': (15.06, 76.3), 'TP38': (20.85, 65.0)}
# nets of the moved parts and jacks: ripped inside the window
WINDOW = (0.0, 47.5, 22.5, 75.5)
RIP_NETS = {RAW_NET, OLD_RAW_NET, 'SIG_SINE', '+12V', 'Net-(Q5-D)', 'Net-(Q5-G)', 'Net-(Q21-D)',
            '/Amp Control/AMP_REM'}
OLD_TEXT = (('SIG', 12.095, 66.3), ('GND', 12.095, 70.11), ('12V IN', 17.2, 61.62),
            ('GND', 13.8, 57.48), ('+12V', 14.25, 52.4))
# text, x, y: labels on the bare board beside the pads
NEW_TEXT = (('+12V', 8.1, 49.5), ('GND', 8.1, 60.5), ('12V IN', 15.0, 60.5),
            ('GND', 7.9, 70.3), ('SIG', 11.2, 70.3), ('AMP SIGNAL', 5.7, 72.6))
# (net, points, width); F.Cu
TRACKS = (
    (RAW_NET, ((5.0, 49.5), (11.2, 49.5), (19.0, 49.955)), 2.0),
    ('GND', ((5.0, 60.5), (11.2, 60.5)), 2.0),
    ('GND', ((8.0, 60.5), (8.0, 58.0)), 1.0),
    ('SIG_SINE', ((25.59, 59.55), (21.6, 63.54), (20.85, 65.0), (20.85, 67.4), (18.0, 67.4),
                  (15.2, 70.0)), 0.25),
)
GROUND_VIAS = ((6.8, 58.9), (8.0, 58.9), (9.2, 58.9), (8.0, 57.8), (3.0, 72.0))
CLEARANCE = 0.25


def net_of(board, name):
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        KEEP.append(net)
    return net


def near_box(point, box, margin):
    """True when a point (mm) lies within margin of a (x1, y1, x2, y2) box."""
    return (box[0] - margin < point[0] < box[2] + margin
            and box[1] - margin < point[1] < box[3] + margin)


def hits(item, boxes):
    """True when a track or via comes within clearance of a keep-out box."""
    if item.Type() == pcbnew.PCB_VIA_T:
        spot = item.GetPosition()
        return any(near_box((spot.x / 1e6, spot.y / 1e6), box, item.GetWidth() / 2e6 + CLEARANCE)
                   for box, _ in boxes)
    start, end = item.GetStart(), item.GetEnd()
    steps = max(2, int(item.GetLength() / 5e4))
    for step in range(steps + 1):
        x_mm = (start.x + (end.x - start.x) * step / steps) / 1e6
        y_mm = (start.y + (end.y - start.y) * step / steps) / 1e6
        for box, all_layers in boxes:
            if (all_layers or item.GetLayer() == pcbnew.F_Cu) and near_box(
                    (x_mm, y_mm), box, item.GetWidth() / 2e6 + CLEARANCE):
                return True
    return False


def place_jacks(board):
    for pad in board.GetPads():
        if pad.GetNetname() == OLD_RAW_NET:
            pad.SetNet(net_of(board, RAW_NET))
    for reference, (name, x_mm, y_mm, nets) in JACKS.items():
        old = board.FindFootprintByReference(reference)
        new = pcbnew.FootprintLoad(LIB, name)
        new.SetReference(reference)
        new.SetValue(old.GetValue())
        new.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        board.Add(new)
        new.SetOrientationDegrees(old.GetOrientationDegrees())
        board.Remove(old)
        KEEP.append(old)
        for pad in new.Pads():
            if pad.GetNumber():
                pad.SetNet(net_of(board, nets[pad.GetNumber()]))
        pcbmodels.attach_missing_models(new)
    for reference, (x_mm, y_mm) in MOVES.items():
        board.FindFootprintByReference(reference).SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))


def keep_out_boxes(board):
    """Box and all-layers flag for each new jack / moved part pad and hole."""
    boxes = []
    for reference in (*JACKS, *MOVES):
        for pad in board.FindFootprintByReference(reference).Pads():
            box = pad.GetBoundingBox()
            boxes.append(((box.GetLeft() / 1e6, box.GetTop() / 1e6, box.GetRight() / 1e6,
                           box.GetBottom() / 1e6), pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH))
    return boxes


def rip(board):
    boxes = keep_out_boxes(board)
    touched = set()
    for item in list(board.GetTracks()):
        ends = ((item.GetPosition(),) if item.Type() == pcbnew.PCB_VIA_T
                else (item.GetStart(), item.GetEnd()))
        in_window = item.GetNetname() in RIP_NETS and any(
            near_box((end.x / 1e6, end.y / 1e6), WINDOW, 0) for end in ends)
        if in_window or hits(item, boxes):
            touched.add(item.GetNetname())
            board.Remove(item)
            KEEP.append(item)
    print('ripped nets:', sorted(touched))
    return touched - {'GND'}  # pour stubs would all look dangling


def draw_copper(board):
    for name, points, width in TRACKS:
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1)))
            track.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
            track.SetWidth(MM(width))
            track.SetLayer(pcbnew.F_Cu)
            track.SetNet(net_of(board, name))
            board.Add(track)
    for x_mm, y_mm in GROUND_VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        via.SetWidth(MM(0.6))
        via.SetDrill(MM(0.3))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetNet(net_of(board, 'GND'))
        board.Add(via)


def update_silk(board):
    template = None
    for item in list(board.GetDrawings()):
        if item.GetClass() == 'PCB_TEXT':
            spot = item.GetPosition()
            for text, x_mm, y_mm in OLD_TEXT:
                if (item.GetText() == text and abs(spot.x / 1e6 - x_mm) < 0.05
                        and abs(spot.y / 1e6 - y_mm) < 0.05):
                    if item.GetLayer() == pcbnew.F_SilkS:
                        template = item
                    board.Remove(item)
                    KEEP.append(item)
            continue
        # J2's body now crosses the section line beside the old terminal
        box = item.GetBoundingBox()
        if (item.GetLayer() == pcbnew.F_SilkS and box.GetWidth() < MM(0.2)
                and 13.4 < box.GetLeft() / 1e6 < 13.6 and box.GetTop() / 1e6 > 47.6):
            board.Remove(item)
            KEEP.append(item)
    for text, x_mm, y_mm in NEW_TEXT:
        label = template.Duplicate()
        label.SetText(text)
        label.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))
        label.SetTextAngleDegrees(0)
        board.Add(label)
    # text carried along by the moved parts, set clear of J9's rear pad and each other
    for reference, get_field, x_mm, y_mm in (
            ('TP38', 'Value', 20.1, 63.4), ('Q5', 'Reference', 20.9, 67.4), ('Q6', 'Reference', 19.2, 74.6),
            ('J2', 'Reference', 2.6, 49.5), ('J9', 'Reference', 2.2, 70.3)):
        footprint = board.FindFootprintByReference(reference)
        field = footprint.Value() if get_field == 'Value' else footprint.Reference()
        field.SetPosition(pcbnew.VECTOR2I(MM(x_mm), MM(y_mm)))


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    place_jacks(board)
    touched = rip(board)
    draw_copper(board)
    ripup.prune(board, touched)
    update_silk(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
