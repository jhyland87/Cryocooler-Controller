"""Brings the routed UCS 145-125 board to the MCP23S08 schematic: removes the
EMC2303 and bridge parts, swaps U25, L1, L2 and the ground test points, adds the
fan drivers and display buffers, moves J15 left and syncs every pad net to the
netlist. Rips what no longer fits; run `gen_pcb.py link`, then `gridroute.py`.

Usage: spi_expander_board.py board.kicad_pcb (edits in place)
"""
import sys
from pathlib import Path

import pcbnew

import pcbnetlist

MM = pcbnew.FromMM
FOOTPRINT_ROOTS = {
    'cryocooler': str(Path(__file__).resolve().parents[1] / 'lib' / 'cryocooler.pretty'),
}
STOCK = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
# SWIG frees removed items when their wrappers die, so they stay referenced
KEEP = []

# ref -> (x, y, rotation, bottom side)
NEW_PARTS = {
    'Q26': (83.5, 83.8, 0, True),
    'R173': (86.0, 83.8, 90, True),
    'R172': (87.5, 83.8, 90, True),
    'R174': (89.0, 83.8, 90, True),
    'TP31': (100.5, 88.5, 0, True),
    'Q27': (96.0, 82.5, 0, True),
    'R176': (98.5, 82.5, 90, True),
    'R175': (100.0, 82.5, 90, True),
    'R177': (93.1, 81.5, 90, True),
    'U30': (87.5, 28.5, 0, True),
    'U31': (92.5, 28.5, 0, True),
    'R178': (87.5, 31.8, 0, True),
    'R179': (92.5, 31.8, 0, True),
    'C127': (84.6, 28.5, 90, True),
    'C128': (95.4, 28.5, 90, True),
}
# parts that change footprint in place; None keeps the rotation
REPLACED = {
    'U25': (80.0, 78.0, 0, True),
    'L1': (None, None, None, False),
    'L2': (None, None, None, False),
    # ground test points: SMT on the top side, where a probe can reach them
    'TP14': (76.8, 81.5, 0, False),
    'TP15': (45.0, 11.0, 0, False),
    'TP16': (104.2, 85.8, 0, False),
    'TP17': (18.45, 32.6, 90, False),
}
MOVED = {
    'J15': (34.0, 5.0),
    'Q25': (42.7, 11.6),
    'R167': (45.6, 11.2),
}
# all copper of these nets goes: both ends changed
RIP_WHOLE = {
    'LED_READY', 'LED_FAULT', 'DISP_CS', 'DISP_DC', 'DISP_BL_EN',
    '/Display/TOUCH_XP', '/Display/TOUCH_YP', '/Display/TOUCH_XN', '/Display/TOUCH_YN',
    '/Display/DISP_BL_A', '/Display/DISP_BL_K',
    'Net-(J3-Pin_3)', 'Net-(J3-Pin_4)', 'Net-(J4-Pin_3)', 'Net-(J4-Pin_4)',
}
# (x0, y0, x1, y1), nets ripped where a track end lies inside
RIP_BOXES = (
    ((72.0, 72.0, 102.0, 91.0),
     {'SPI_MOSI', 'SPI_SCK', 'SPI_MISO', '+3V3_COOL', '+3V3', 'PGP_15V', 'PGN_15V',
      'PGP_16V5', 'PGN_16V5'}),
    ((24.0, 0.0, 50.0, 13.0), {'SPI_MOSI', 'SPI_SCK', 'DISP_RST', '+3V3'}),
)
PAD_CLEARANCE = 0.15


def load_footprint(lib_id):
    library, name = lib_id.split(':')
    root = FOOTPRINT_ROOTS.get(library, f'{STOCK}/{library}.pretty')
    return pcbnew.FootprintLoad(root, name)


def net_of(board, name):
    item = board.FindNet(name)
    if item is None:
        item = pcbnew.NETINFO_ITEM(board, name)
        board.Add(item)
    return item


def place(footprint, x, y, rotation, bottom):
    if bottom != footprint.IsFlipped():
        footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    footprint.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    footprint.SetOrientationDegrees(rotation)


def add_part(board, ref, part, spot):
    footprint = load_footprint(part['footprint'])
    board.Add(footprint)
    footprint.SetReference(ref)
    footprint.SetValue(part['value'])
    place(footprint, *spot)
    return footprint


def replace_part(board, ref, part, spot):
    old = board.FindFootprintByReference(ref)
    x, y, rotation, bottom = spot
    x = old.GetX() / 1e6 if x is None else x
    y = old.GetY() / 1e6 if y is None else y
    rotation = old.GetOrientationDegrees() if rotation is None else rotation
    KEEP.append(old)
    board.Remove(old)
    return add_part(board, ref, part, (x, y, rotation, bottom))


def clear_copper_under(board, footprint):
    """Rips other nets' tracks and vias that touch this footprint's pads (by each
    pad's bounding box, inflated by the clearance and the item's half width).
    """
    cleared = set()
    for pad in footprint.Pads():
        box = pad.GetBoundingBox()
        left, right = box.GetLeft(), box.GetRight()
        top, bottom = box.GetTop(), box.GetBottom()

        def touches(x, y, half_width):
            margin = half_width + MM(PAD_CLEARANCE)
            return (left - margin <= x <= right + margin
                    and top - margin <= y <= bottom + margin)

        for item in list(board.GetTracks()):
            if item.GetNetCode() == pad.GetNetCode():
                continue
            if item.Type() == pcbnew.PCB_VIA_T:
                where = item.GetPosition()
                hits = touches(where.x, where.y, item.GetWidth(pcbnew.F_Cu) // 2)
            else:
                start, end = item.GetStart(), item.GetEnd()
                steps = max(1, int(item.GetLength() / MM(0.05)))
                hits = pad.IsOnLayer(item.GetLayer()) and any(
                    touches(start.x + (end.x - start.x) * step // steps,
                            start.y + (end.y - start.y) * step // steps,
                            item.GetWidth() // 2)
                    for step in range(steps + 1)
                )
            if hits:
                cleared.add(item.GetNetname())
                KEEP.append(item)
                board.Remove(item)
    return cleared


def main():
    path = sys.argv[1]
    parts, nets = pcbnetlist.load_netlist()
    board = pcbnew.LoadBoard(path)
    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}

    # parts no longer in the schematic
    for footprint in list(board.GetFootprints()):
        ref = footprint.GetReference()
        if ref and ref not in parts:
            KEEP.append(footprint)
            board.Remove(footprint)

    changed = []
    for ref, spot in REPLACED.items():
        changed.append(replace_part(board, ref, parts[ref], spot))
    for ref, spot in NEW_PARTS.items():
        changed.append(add_part(board, ref, parts[ref], spot))
    for ref, (x, y) in MOVED.items():
        footprint = board.FindFootprintByReference(ref)
        footprint.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        changed.append(footprint)
    missing = set(parts) - {f.GetReference() for f in board.GetFootprints()}
    assert not missing, missing

    # pad nets from the netlist
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            name = pin_net.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(net_of(board, name))
        if ref in parts:
            footprint.SetValue(parts[ref]['value'])

    # copper of nets that left the schematic, and nets rerouted end to end
    doomed = set(RIP_WHOLE)
    for item in board.GetTracks():
        if item.GetNetname() and item.GetNetname() not in nets:
            doomed.add(item.GetNetname())
    print('whole nets ripped:', sorted(doomed))
    for item in list(board.GetTracks()):
        if item.GetNetname() in doomed:
            KEEP.append(item)
            board.Remove(item)

    def end_inside(item, box):
        x0, y0, x1, y1 = box
        points = [item.GetPosition()] if item.Type() == pcbnew.PCB_VIA_T else [
            item.GetStart(), item.GetEnd()]
        return any(x0 <= p.x / 1e6 <= x1 and y0 <= p.y / 1e6 <= y1 for p in points)

    for box, box_nets in RIP_BOXES:
        for item in list(board.GetTracks()):
            if item.GetNetname() in box_nets and end_inside(item, box):
                KEEP.append(item)
                board.Remove(item)

    cleared = set()
    for footprint in changed:
        cleared |= clear_copper_under(board, footprint)
    print('tracks cleared on nets:', sorted(cleared))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
