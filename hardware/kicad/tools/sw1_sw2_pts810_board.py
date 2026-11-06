"""Swaps SW1 and SW2 to the C&K PTS810. SW1 moves so DISP_RST (y 10.9) runs between
its pad rows, and TOUCH_CS drops to y 12.35 where SW1's old GND track was. SW2 moves
so its top row sits on ESP_BOOT and clears the via. Run `gen_pcb.py link` afterwards.

Usage: sw1_sw2_pts810_board.py board.kicad_pcb (edits in place)
"""
import sys

import pcbnew

import pcbmodels
from small_packages_board import KEEP, swap_parts

MM = pcbnew.FromMM
TRACK_WIDTH = 0.25
MATCH_TOLERANCE = 0.01
PAD_LEFT, PAD_RIGHT = 64.425, 68.575

# (net, start, end) of F.Cu tracks that served the old pads
OLD_TRACKS = (
    ('ESP_EN', (69.65, 9.1), (63.35, 9.1)),
    ('GND', (69.65, 12.9), (63.35, 12.9)),
    ('GND', (63.35, 12.9), (62.2233, 12.9)),
    ('GND', (62.2233, 14.0737), (62.2233, 12.9)),
    ('GND', (61.7885, 14.5085), (62.2233, 14.0737)),
    ('ESP_BOOT', (63.9134, 16.6), (69.65, 16.6)),
    ('ESP_BOOT', (63.35, 16.6), (63.9134, 16.6)),
    ('GND', (69.65, 20.4), (63.35, 20.4)),
)
# swap_parts has already ripped whichever of these touch the new pads
OLD_TOUCH_CS_TRACKS = (
    ((61.5, 11.85), (63.75, 11.85)),
    ((63.75, 11.85), (63.95, 12.05)),
    ((63.95, 12.05), (70.8, 12.05)),
    ((70.8, 12.05), (70.9, 12.15)),
)
# SW1's bottom row can't reach existing GND past DISP_RST and TOUCH_CS, so it gets a
# via. This spot is 0.25 mm from USB_D- on In2.
SW1_GND_VIA = (69.55, 11.6)
# (net, points of an F.Cu route, width)
NEW_ROUTES = (
    ('ESP_EN', ((PAD_LEFT, 9.35), (PAD_LEFT, 9.1), (PAD_RIGHT, 9.1), (PAD_RIGHT, 9.35))),
    ('ESP_EN', ((PAD_RIGHT, 9.1), (69.65, 9.1))),
    ('GND', ((PAD_LEFT, 11.5), (PAD_RIGHT, 11.5), (69.45, 11.5), SW1_GND_VIA)),
    ('ESP_BOOT', ((PAD_LEFT, 16.6), (PAD_RIGHT, 16.6))),
    # SW2 GND: down from each pad to the existing track at y 20.4
    ('GND', ((PAD_LEFT, 18.75), (PAD_LEFT, 20.4), (PAD_RIGHT, 20.4), (PAD_RIGHT, 18.75))),
    ('GND', ((63.35, 20.4), (PAD_LEFT, 20.4))),
)
TOUCH_CS_WIDTH = 0.2
TOUCH_CS_ROUTE = ((61.5, 11.85), (62.0, 12.35), (70.7, 12.35), (70.9, 12.15))
VIA_DIAMETER = 0.6
VIA_DRILL = 0.3


def same_point(point, target):
    return (abs(point.x / 1e6 - target[0]) < MATCH_TOLERANCE
            and abs(point.y / 1e6 - target[1]) < MATCH_TOLERANCE)


def remove_track(board, net, start, end, required=True):
    for item in board.GetTracks():
        if item.Type() != pcbnew.PCB_TRACE_T or item.GetLayer() != pcbnew.F_Cu:
            continue
        if item.GetNetname() != net:
            continue
        if ((same_point(item.GetStart(), start) and same_point(item.GetEnd(), end))
                or (same_point(item.GetStart(), end) and same_point(item.GetEnd(), start))):
            KEEP.append(item)
            board.Remove(item)
            return
    if required:
        raise ValueError(f'track not found: {net} {start} {end}')


def add_route(board, net, points, width=TRACK_WIDTH):
    net_item = board.FindNet(net)
    for start, end in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        track.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        track.SetWidth(MM(width))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(net_item)
        board.Add(track)


def finish(board):
    for net, start, end in OLD_TRACKS:
        remove_track(board, net, start, end)
    for start, end in OLD_TOUCH_CS_TRACKS:
        remove_track(board, 'TOUCH_CS', start, end, required=False)
    for net, points in NEW_ROUTES:
        add_route(board, net, points)
    add_route(board, 'TOUCH_CS', TOUCH_CS_ROUTE, TOUCH_CS_WIDTH)
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I(MM(SW1_GND_VIA[0]), MM(SW1_GND_VIA[1])))
    via.SetWidth(MM(VIA_DIAMETER))
    via.SetDrill(MM(VIA_DRILL))
    via.SetNet(board.FindNet('GND'))
    board.Add(via)
    for ref in ('SW1', 'SW2'):
        pcbmodels.attach_missing_models(board.FindFootprintByReference(ref))


def main():
    swap_parts(
        sys.argv[1],
        {'SW1': (66.5, 10.425, 0, False), 'SW2': (66.5, 17.675, 0, False)},
        {},
        (),
        finish,
    )


if __name__ == '__main__':
    main()
