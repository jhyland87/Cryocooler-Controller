"""Pre-order audit fixes on the routed UCS 145-125 board: a short wide U15 switch
node, thermal copper on the U16 tab, the USB_VBUS bleed resistor and the second
rail capacitors. Coordinates fit the route committed with this file; run
`gen_pcb.py link`, `silk_fix.py` and DRC afterwards.

Usage: audit_fixes_board.py board.kicad_pcb (edits in place, refills zones)
"""
import math
import sys

import pcbnew

import hand_route
import pcbnetlist
import spi_expander_board

F = pcbnew.F_Cu
B = pcbnew.B_Cu
IN2 = pcbnew.In2_Cu
SWITCH_NODE = 'Net-(U15-SW)'
TAB_VIAS = tuple((x, y) for x in (32.4, 33.2) for y in (79.0, 80.0, 81.0))
# ref -> (x, y, bottom side, point pin 1 must face)
NEW_PARTS = {
    'C129': (84.0, 66.5, False, (82.5, 66.5)),
    'C130': (83.5, 44.5, True, (83.5, 46.0)),
    'C131': (85.0, 49.5, True, (83.5, 49.5)),
    'R180': (31.4, 82.0, True, (31.4, 82.5)),
}


def place_new_part(board, ref, part, spot):
    """Adds a part, turned so pin 1 lands nearest the wanted point."""
    x, y, bottom, target = spot
    footprint = spi_expander_board.add_part(board, ref, part, (x, y, 0, bottom))
    for rotation in (0, 90, 180, 270):
        footprint.SetOrientationDegrees(rotation)
        pad = next(pad for pad in footprint.Pads() if pad.GetNumber() == '1')
        if math.hypot(pad.GetX() / 1e6 - target[0], pad.GetY() / 1e6 - target[1]) < 0.3:
            return footprint
    raise ValueError(f'{ref}: no rotation puts pin 1 at {target}')


def reroute_switch_node(board):
    """U15 SW to L1 pad 1: 0.4 mm on F.Cu, then 1 mm on In2 (between the BST via
    and +5V_OR) to two vias in the L1 pad. The via west of L1 stays: it feeds C39
    on the back.
    """
    for item in list(board.GetTracks()):
        if item.Type() != pcbnew.PCB_TRACE_T or item.GetNetname() != SWITCH_NODE:
            continue
        near_u15 = item.GetLayer() == F and item.GetEnd().y / 1e6 > 70
        if item.GetLayer() == IN2 or near_u15:
            board.Delete(item)
    hand_route.track(board, SWITCH_NODE,
                     [(28.64, 72.5), (29.0, 72.5), (29.3, 72.8), (29.75, 72.8)], 0.4, F)
    hand_route.track(board, SWITCH_NODE, [(29.75, 72.87), (29.2, 72.87)], 0.5, IN2)
    hand_route.track(board, SWITCH_NODE, [(29.2, 72.87), (25.03, 68.7)], 1.0, IN2)
    hand_route.track(board, SWITCH_NODE, [(25.03, 68.7), (25.8, 68.7)], 0.6, IN2)
    hand_route.via(board, SWITCH_NODE, 25.03, 68.7, 0.6, 0.3)
    hand_route.via(board, SWITCH_NODE, 25.8, 68.7, 0.6, 0.3)


def add_tab_copper(board):
    """Pour east of the U16 tab, stitched into the In2 +3V3 pour."""
    hand_route.zone(board, '+3V3',
                    [(29.7, 78.0), (33.8, 78.0), (33.8, 83.5), (31.4, 83.5), (29.7, 82.0)], F)
    for x, y in TAB_VIAS:
        hand_route.via(board, '+3V3', x, y, 0.6, 0.3)


def connect_new_parts(board):
    # +15 V second output cap: off the C67 track, under the F.Cu signals on In2
    hand_route.track(board, '+15V', [(80.9, 61.38), (80.9, 62.0)], 0.3, F)
    hand_route.via(board, '+15V', 80.9, 62.0, 0.6, 0.3)
    hand_route.track(board, '+15V', [(80.9, 62.0), (80.9, 65.15), (81.6, 65.85)], 0.3, IN2)
    hand_route.via(board, '+15V', 81.6, 65.85, 0.6, 0.3)
    hand_route.track(board, '+15V', [(81.6, 65.85), (82.25, 66.5), (82.52, 66.5)], 0.3, F)
    # -15 V: via between the C69 pads, through the back cap's pad
    hand_route.via(board, '-15V', 83.5, 46.0, 0.6, 0.3)
    hand_route.track(board, '-15V', [(83.5, 46.0), (83.5, 47.2)], 0.3, F)
    # -16V5: via through both capacitor pads
    hand_route.via(board, '-16V5', 83.53, 49.7, 0.6, 0.3)
    # USB_VBUS bleed joins the C126 / TP43 track
    hand_route.track(board, 'USB_VBUS', [(31.4, 82.51), (30.63, 83.28), (30.5, 83.28)], 0.3, B)


def main():
    path = sys.argv[1]
    parts, nets = pcbnetlist.load_netlist()
    board = pcbnew.LoadBoard(path)
    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}

    for ref, spot in NEW_PARTS.items():
        place_new_part(board, ref, parts[ref], spot)
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            name = pin_net.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(spi_expander_board.net_of(board, name))
        if ref in parts:
            footprint.SetValue(parts[ref]['value'])

    reroute_switch_node(board)
    add_tab_copper(board)
    connect_new_parts(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
