"""Adds the USB power path to the routed board: U28 / U29 (LM66100 pair), R24,
C49 and TP43 / TP44 on the bottom below U16, and splits +5V so U16, the DDS,
JP3 and the backlight sit on +5V_OR. C65 moves to +5V_OR, so C66 grows to 22 uF.

Leaves the new connections open: run `gen_pcb.py link`, then `gridroute.py` on
the DRC report. The coordinates fit the route committed with this file.

Usage: usb_power_path.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

MM = pcbnew.FromMM
FOOTPRINTS = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
FEED = '+5V_OR'
SELECT = '/Rails 5V 3V3/USB_SEL'
VBUS = 'USB_VBUS'
# ref -> pad -> net, for parts already on the board
MOVED_PADS = {
    'U16': {'3': FEED}, 'C65': {'1': FEED}, 'U3': {'1': FEED, '4': FEED},
    'U4': {'2': FEED}, 'C10': {'1': FEED}, 'C11': {'1': FEED}, 'C3': {'1': FEED},
    'C58': {'1': FEED}, 'R121': {'1': FEED}, 'JP3': {'1': FEED},
}
# (ref, value, source footprint or (library, name), x, y, rotation, pad nets)
NEW_PARTS = (
    ('U28', 'LM66100', ('Package_TO_SOT_SMD', 'SOT-363_SC-70-6'), 27.0, 77.5, 0,
     {'1': '+5V', '2': 'GND', '3': VBUS, '4': 'unconnected-(U28-NC-Pad4)', '5': SELECT, '6': FEED}),
    ('U29', 'LM66100', ('Package_TO_SOT_SMD', 'SOT-363_SC-70-6'), 27.0, 82.0, 0,
     {'1': VBUS, '2': 'GND', '3': SELECT, '4': 'unconnected-(U29-NC-Pad4)', '5': 'GND', '6': FEED}),
    ('R24', '10k', ('Resistor_SMD', 'R_0402_1005Metric'), 30.0, 77.5, 90,
     {'1': SELECT, '2': '+5V'}),
    ('C49', '1uF', ('Capacitor_SMD', 'C_0603_1608Metric'), 30.0, 82.0, 90,
     {'1': VBUS, '2': 'GND'}),
    ('TP43', 'VBUS', 'TP42', 30.5, 85.2, 0, {'1': VBUS}),
    ('TP44', '5V_OR', 'TP42', 27.0, 85.6, 0, {'1': FEED}),
)
# +5V copper that goes: the U15 -> U16 diagonal and stub, and the In2 start of
# the DDS branch
REMOVED = (
    ((25.23, 78.85), (31.07, 73.01)), ((23.52, 78.85), (25.23, 78.85)),
    ((23.0, 79.37), (23.52, 78.85)), ((24.43, 60.87), (31.22, 67.66)),
)
FEED_STUB = (((23.0, 79.37), (23.0, 80.95)), ((24.35, 82.3), (23.0, 80.95)),
             ((24.35, 84.83), (24.35, 82.3)))


def spot(point):
    return (round(point.x / 1e6, 2), round(point.y / 1e6, 2))


def same(item, ends):
    return {spot(item.GetStart()), spot(item.GetEnd())} == set(ends)


def get_net(board, name):
    item = board.FindNet(name)
    if item is None:
        item = pcbnew.NETINFO_ITEM(board, name)
        board.Add(item)
    return item


def set_pad_nets(footprint, nets, board):
    for pad in footprint.Pads():
        wanted = nets.get(pad.GetNumber())
        if wanted:
            pad.SetNet(get_net(board, wanted))


def add_part(source, board):
    """Adds a copy of a board footprint (ref) or a bottom-side library footprint."""
    if isinstance(source, str):
        footprint = pcbnew.Cast_to_FOOTPRINT(board.FindFootprintByReference(source).Duplicate(False))
        board.Add(footprint)
        return footprint
    footprint = pcbnew.FootprintLoad(f'{FOOTPRINTS}/{source[0]}.pretty', source[1])
    board.Add(footprint)
    footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    return footprint


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    feed, five, vbus = get_net(board, FEED), board.FindNet('+5V'), get_net(board, VBUS)

    # rename the VBUS copper to the global net
    old_vbus = board.FindNet('/USB_VBUS')
    for item in board.GetTracks():
        if item.GetNetname() == '/USB_VBUS':
            item.SetNet(vbus)
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetname() == '/USB_VBUS':
                pad.SetNet(vbus)
    assert old_vbus is not None

    removed = 0
    for item in list(board.GetTracks()):
        if item.GetNetname() != '+5V':
            continue
        if item.Type() == pcbnew.PCB_TRACE_T and any(same(item, ends) for ends in REMOVED):
            board.Delete(item)
            removed += 1
    assert removed == len(REMOVED), removed
    for item in board.GetTracks():
        if item.GetNetname() != '+5V':
            continue
        if item.Type() == pcbnew.PCB_TRACE_T:
            start, end = spot(item.GetStart()), spot(item.GetEnd())
            branch = max(start[0], end[0]) < 50 and max(start[1], end[1]) <= 60.9
            if branch or any(same(item, ends) for ends in FEED_STUB):
                item.SetNet(feed)
        else:
            where = spot(item.GetPosition())
            if where[0] < 50 and where[1] <= 60.9:
                item.SetNet(feed)
    for ref, nets in MOVED_PADS.items():
        set_pad_nets(board.FindFootprintByReference(ref), nets, board)

    # +5V drops through to the bottom just north of U16
    stub = pcbnew.PCB_TRACK(board)
    stub.SetStart(pcbnew.VECTOR2I(MM(31.07), MM(73.01)))
    stub.SetEnd(pcbnew.VECTOR2I(MM(29.2), MM(74.88)))
    stub.SetWidth(MM(0.3))
    stub.SetLayer(pcbnew.F_Cu)
    stub.SetNet(five)
    board.Add(stub)
    drop = pcbnew.PCB_VIA(board)
    drop.SetPosition(pcbnew.VECTOR2I(MM(29.2), MM(74.88)))
    drop.SetWidth(MM(0.45))
    drop.SetDrill(MM(0.2))
    drop.SetViaType(pcbnew.VIATYPE_THROUGH)
    drop.SetNet(five)
    board.Add(drop)

    # C66 becomes the second 22 uF buck output cap: 1206, pad 1 stays on the +5V track
    old = board.FindFootprintByReference('C66')
    grounded = old.FindPadByNumber('2').GetNetname()
    board.Delete(old)
    big = add_part(('Capacitor_SMD', 'C_1206_3216Metric'), board)
    big.SetReference('C66')
    big.SetValue('22uF/10V')
    big.SetOrientationDegrees(90)
    big.SetPosition(pcbnew.VECTOR2I(MM(29.575), MM(65.0)))
    set_pad_nets(big, {'1': '+5V', '2': grounded}, board)

    for ref, value, source, x, y, rotation, nets in NEW_PARTS:
        footprint = add_part(source, board)
        footprint.SetReference(ref)
        footprint.SetValue(value)
        footprint.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        footprint.SetOrientationDegrees(rotation)
        set_pad_nets(footprint, nets, board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    for ref in ('C66', 'U28', 'U29', 'R24', 'C49'):
        print(ref, [(pad.GetNumber(), spot(pad.GetPosition()), pad.GetNetname())
                    for pad in board.FindFootprintByReference(ref).Pads()])


if __name__ == '__main__':
    main()
