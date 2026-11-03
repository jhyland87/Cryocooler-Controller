"""Hand routes for the connections Freerouting left open on the UCS 145-125
board: U4 pin 5 (DDS clock), U20 pins 2 / 22 (VIN) and 17 (SS2).

The coordinates fit the route committed with this file; a new autoroute
leaves different copper, so check them (DRC) before reusing them. Run after
`gen_pcb.py route`, then `silk_fix.py`.

Usage: hand_route.py board.kicad_pcb [route name ...] (edits in place,
refills zones; all routes when none is named)
"""
import sys

import pcbnew

MM = pcbnew.FromMM


def net(board, name):
    item = board.FindNet(name)
    if item is None:
        raise KeyError(name)
    return item


def track(board, name, points, width, layer):
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        seg = pcbnew.PCB_TRACK(board)
        seg.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1)))
        seg.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
        seg.SetWidth(MM(width))
        seg.SetLayer(layer)
        seg.SetNet(net(board, name))
        board.Add(seg)


def delete(board, name, points, tolerance=0.02):
    """Removes the segments of a net whose ends both lie on the given points."""
    def near(point):
        return any(abs(point.x / 1e6 - x) < tolerance and abs(point.y / 1e6 - y) < tolerance
                   for x, y in points)
    for item in list(board.GetTracks()):
        if (item.Type() == pcbnew.PCB_TRACE_T and item.GetNetname() == name
                and near(item.GetStart()) and near(item.GetEnd())):
            board.Delete(item)


def via(board, name, x, y, diameter=0.45, drill=0.2):
    item = pcbnew.PCB_VIA(board)
    item.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    item.SetWidth(MM(diameter))
    item.SetDrill(MM(drill))
    item.SetViaType(pcbnew.VIATYPE_THROUGH)
    item.SetNet(net(board, name))
    board.Add(item)


ROUTES = {
    # U4 pin 5 (DDS clock in) to the U3 oscillator via, on In2 west of the
    # +5V / CAP vias (B.Cu is taken by C15)
    'u4': [
        ('track', 'Net-(U3-OUT)', [(44.4, 19.5), (43.65, 19.5), (43.45, 19.7), (43.45, 20.1)], 0.2, pcbnew.F_Cu),
        ('via', 'Net-(U3-OUT)', 43.45, 20.1),
        ('track', 'Net-(U3-OUT)', [(43.45, 20.1), (41.3, 20.1), (41.3, 17.0), (41.93, 16.4)], 0.2, pcbnew.In2_Cu),
    ],
    # U20 pin 22 (VIN) down to the +5V_PS15 In2 track beside it
    'u20_vin': [
        ('track', '+5V_PS15', [(71.9, 52.25), (72.6, 52.25)], 0.2, pcbnew.F_Cu),
        ('via', '+5V_PS15', 72.6, 52.25),
    ],
    # U20 pin 2 (VIN): pin 1's switch-node stub goes straight north to free
    # the way; then a via between R59 and C63, In2 between the +5V and
    # NTC_ADC tracks, and up onto the F.Cu VIN track at pin 11
    'u20_vin2': [
        ('delete', 'Net-(D5-A)', [(68.1, 51.25), (67.47, 51.25), (67.47, 50.54), (67.53, 50.49)]),
        ('track', 'Net-(D5-A)', [(68.1, 51.25), (68.1, 50.49)], 0.25, pcbnew.F_Cu),
        ('track', '+5V_PS15', [(68.1, 51.75), (67.2, 51.75), (66.95, 51.62), (66.08, 51.62)], 0.2, pcbnew.F_Cu),
        ('via', '+5V_PS15', 66.08, 51.62),
        ('track', '+5V_PS15', [(66.08, 51.62), (66.08, 55.0), (65.6, 55.48), (65.6, 58.75)], 0.25, pcbnew.In2_Cu),
        ('via', '+5V_PS15', 65.6, 58.75),
    ],
    # U20 pin 17 (SS2) east to a via, then In2 down to C62's via; RT2's
    # jog to R58 is straightened first to make room
    'u20_ss2': [
        ('delete', '/Rails +-15V/RT2', [(73.39, 55.25), (73.06, 55.25), (72.78, 54.97), (72.5, 55.25)]),
        ('track', '/Rails +-15V/RT2', [(72.5, 55.25), (73.39, 55.25)], 0.1874, pcbnew.F_Cu),
        ('track', '/Rails +-15V/SS2', [(71.9, 54.75), (72.8, 54.75), (73.05, 54.5)], 0.2, pcbnew.F_Cu),
        ('via', '/Rails +-15V/SS2', 73.05, 54.5),
        ('track', '/Rails +-15V/SS2', [(73.05, 54.5), (73.45, 54.9), (73.45, 57.0), (72.92, 57.47)], 0.2, pcbnew.In2_Cu),
    ],
}


def main():
    path = sys.argv[1]
    board = pcbnew.LoadBoard(path)
    for name in sys.argv[2:] or ROUTES:
        for step in ROUTES[name]:
            if step[0] == 'track':
                track(board, *step[1:])
            elif step[0] == 'delete':
                delete(board, *step[1:])
            else:
                via(board, *step[1:])
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
