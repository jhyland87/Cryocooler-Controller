"""Brings the routed UCS 145-125 board to the SN74LVC138A chip select decoder:
removes the DISP_CS buffer and the old CS pull-ups, places the decoder and its
parts below U1, syncs pad nets to the netlist, and cuts each CS trace back from
its old GPIO pad so the long run to its device stays. Run `gen_pcb.py link`, then
`gridroute.py` on the DRC report to close the open ends.

Usage: cs_decoder_board.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

import pcbnetlist
from spi_expander_board import KEEP, add_part, clear_copper_under, net_of

MM = pcbnew.FromMM

# ref -> (x, y, rotation, bottom side)
NEW_PARTS = {
    'U32': (92.0, 33.0, 180, False),
    'C42': (87.5, 34.2, 90, False),
    'R28': (97.6, 33.2, 180, False),
    'R29': (97.6, 34.4, 180, False),
    'R27': (97.6, 35.6, 180, False),
    'TP45': (90.0, 37.6, 0, False),
    'TP46': (94.0, 37.6, 0, False),
}
# net -> (x0, y0, x1, y1): copper with any end inside goes
CUT_BOXES = (
    ('MCP4921_CS', (70.6, 10.0, 77.0, 19.0)),
    ('MCP4921_CS', (70.6, 18.0, 71.0, 19.0)),
    ('AD9833_FSYNC', (68.0, 13.0, 77.0, 22.0)),
    ('AD9833_FSYNC', (67.0, 20.5, 68.0, 21.0)),
    ('INA239_CS', (76.95, 25.0, 78.0, 26.5)),
    ('INA239_CS', (22.0, 52.5, 25.0, 53.5)),
    ('EXPANDER_CS', (75.0, 21.0, 77.04, 23.2)),
    ('EXPANDER_CS', (78.35, 76.9, 88.0, 81.5)),
    ('IMU_CS', (92.0, 8.0, 96.0, 20.0)),
    ('ADS1220_CS', (90.5, 12.0, 93.0, 31.0)),
    ('DISP_CS', (83.6, 25.5, 90.0, 28.0)),
    ('TOUCH_CS', (89.7, 23.7, 91.5, 26.0)),
)
# long segment trimmed so it clears a pad that changed net: end -> new x
TRIMS = (
    ('INA239_CS', (76.89, 26.4), 75.0),
)
# removed part pads whose rail stubs go too, as far as the first junction
STUB_BOX = (84.0, 26.0, 90.5, 33.0)
STUB_NETS = {'+3V3', 'GND'}


def ends(item):
    if item.Type() == pcbnew.PCB_VIA_T:
        return [item.GetPosition()]
    return [item.GetStart(), item.GetEnd()]


def inside(point, box):
    return box[0] <= point.x / 1e6 <= box[2] and box[1] <= point.y / 1e6 <= box[3]


def remove(board, item):
    KEEP.append(item)
    board.Remove(item)


def cut_traces(board):
    for net, box in CUT_BOXES:
        for item in list(board.GetTracks()):
            if item.GetNetname() == net and any(inside(p, box) for p in ends(item)):
                remove(board, item)
    for net, old, new_x in TRIMS:
        for item in board.GetTracks():
            if item.GetNetname() != net or item.Type() == pcbnew.PCB_VIA_T:
                continue
            for get, put in ((item.GetStart, item.SetStart), (item.GetEnd, item.SetEnd)):
                point = get()
                if abs(point.x / 1e6 - old[0]) < 0.02 and abs(point.y / 1e6 - old[1]) < 0.02:
                    put(pcbnew.VECTOR2I(MM(new_x), point.y))


def prune_rail_stubs(board):
    """Deletes rail track ends in STUB_BOX that no longer reach a pad or another item."""
    while True:
        removed = False
        tracks = [t for t in board.GetTracks() if t.GetNetname() in STUB_NETS]
        pads = [p for p in board.GetPads() if p.GetNetname() in STUB_NETS]
        for item in tracks:
            if item.Type() == pcbnew.PCB_VIA_T:
                continue
            for point in ends(item):
                if not inside(point, STUB_BOX):
                    continue
                on_pad = any(p.IsOnLayer(item.GetLayer()) and p.HitTest(point) for p in pads)
                joined = any(
                    other is not item and other.GetNetname() == item.GetNetname()
                    and any(abs(q.x - point.x) < 2000 and abs(q.y - point.y) < 2000
                            for q in ends(other))
                    for other in tracks
                )
                if not on_pad and not joined:
                    remove(board, item)
                    removed = True
                    break
            if removed:
                break
        if not removed:
            return


def main():
    path = sys.argv[1]
    parts, nets = pcbnetlist.load_netlist()
    board = pcbnew.LoadBoard(path)
    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}

    for footprint in list(board.GetFootprints()):
        ref = footprint.GetReference()
        if ref and ref not in parts:
            print('removed', ref)
            remove_part = footprint
            KEEP.append(remove_part)
            board.Remove(remove_part)
    new = [add_part(board, ref, parts[ref], spot) for ref, spot in NEW_PARTS.items()]
    missing = set(parts) - {f.GetReference() for f in board.GetFootprints()}
    assert not missing, missing

    no_net = board.FindNet(0)
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            name = pin_net.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(net_of(board, name))
            elif ref == 'U1' and pad.GetNumber() in {'39', '5', '7', '24'}:
                pad.SetNet(no_net)

    for item in list(board.GetTracks()):
        if item.GetNetname() and item.GetNetname() not in nets:
            remove(board, item)
    cut_traces(board)
    prune_rail_stubs(board)

    cleared = set()
    for footprint in new:
        cleared |= clear_copper_under(board, footprint)
    print('tracks cleared on nets:', sorted(cleared))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
