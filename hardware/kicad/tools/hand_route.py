"""Hand routes for the connections Freerouting left open on the UCS 145-125
board: U4 pin 5 (DDS clock), U20 pins 2 / 22 (VIN) and 17 (SS2), the LT8582
switch-node pours and exposed-pad GND vias, and the bottom-wall header gaps.

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


def delete_via(board, name, x, y, tolerance=0.02):
    for item in list(board.GetTracks()):
        if item.Type() == pcbnew.PCB_VIA_T and item.GetNetname() == name:
            where = item.GetPosition()
            if abs(where.x / 1e6 - x) < tolerance and abs(where.y / 1e6 - y) < tolerance:
                board.Delete(item)


def zone(board, name, points, layer, clearance=0.2):
    """Solid copper pour of one net over a polygon. Priority 3 beats the
    GND / ISO_GND pours; the filler keeps clearance to everything else, so
    the polygon can be drawn loose."""
    item = pcbnew.ZONE(board)
    item.SetLayer(layer)
    item.SetNet(net(board, name))
    outline = item.Outline()
    outline.NewOutline()
    for x, y in points:
        outline.Append(MM(x), MM(y))
    item.SetAssignedPriority(3)
    item.SetLocalClearance(MM(clearance))
    item.SetMinThickness(MM(0.2))
    item.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    item.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(item)


ROUTES = {
    # U4 pin 5 (DDS clock in) to the U3 oscillator via, on In2 west of the
    # +5V / CAP vias (B.Cu is taken by C3)
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
    # the way; then a via between R92 and C77, In2 between the +5V and
    # NTC_ADC tracks, and up onto the F.Cu VIN track at pin 11
    'u20_vin2': [
        ('delete', 'Net-(D5-A)', [(68.1, 51.25), (67.47, 51.25), (67.47, 50.54), (67.53, 50.49)]),
        ('track', 'Net-(D5-A)', [(68.1, 51.25), (68.1, 50.49)], 0.25, pcbnew.F_Cu),
        ('track', '+5V_PS15', [(68.1, 51.75), (67.2, 51.75), (66.95, 51.62), (66.08, 51.62)], 0.2, pcbnew.F_Cu),
        ('via', '+5V_PS15', 66.08, 51.62),
        ('track', '+5V_PS15', [(66.08, 51.62), (66.08, 55.0), (65.6, 55.48), (65.6, 58.75)], 0.25, pcbnew.In2_Cu),
        ('via', '+5V_PS15', 65.6, 58.75),
    ],
    # U20 pin 17 (SS2) east to a via, then In2 down to C34's via; RT2's
    # jog to R91 is straightened first to make room
    'u20_ss2': [
        ('delete', '/Rails +-15V/RT2', [(73.39, 55.25), (73.06, 55.25), (72.78, 54.97), (72.5, 55.25)]),
        ('track', '/Rails +-15V/RT2', [(72.5, 55.25), (73.39, 55.25)], 0.1874, pcbnew.F_Cu),
        ('track', '/Rails +-15V/SS2', [(71.9, 54.75), (72.8, 54.75), (73.05, 54.5)], 0.2, pcbnew.F_Cu),
        ('via', '/Rails +-15V/SS2', 73.05, 54.5),
        ('track', '/Rails +-15V/SS2', [(73.05, 54.5), (73.45, 54.9), (73.45, 57.0), (72.92, 57.47)], 0.2, pcbnew.In2_Cu),
    ],
    # LT8582 switch nodes as pours instead of 0.25 mm router tracks: SW1
    # (pins 1 / 24, D5 anode, L2 pad 2), SW2 (pins 12 / 13, L3 pad 3 and
    # C76 pad 1 below) and the inverting node X (L3 pad 4, C76 pad 2, D6)
    'sw_nodes': [
        ('zone', 'Net-(D5-A)', [(66.95, 47.5), (69.6, 47.5), (69.6, 45.7), (75.4, 45.7),
                                (75.4, 47.45), (73.2, 49.5), (73.2, 50.2), (72.45, 50.95),
                                (72.45, 51.45), (67.6, 51.45), (66.95, 50.8)], pcbnew.F_Cu),
        ('zone', 'Net-(U20-SWA2)', [(67.6, 56.55), (68.6, 56.55), (68.6, 57.3), (71.45, 57.3),
                                    (71.45, 56.55), (72.45, 56.55), (72.45, 60.75),
                                    (71.1, 60.75), (71.1, 57.9), (67.6, 57.9)], pcbnew.F_Cu),
        ('zone', 'Net-(U20-SWA2)', [(71.0, 56.2), (73.0, 56.2), (73.0, 60.6), (71.0, 60.6)], pcbnew.B_Cu),
        ('zone', 'Net-(D6-A)', [(64.45, 63.1), (64.45, 61.45), (66.6, 59.15), (69.4, 59.15),
                                (69.4, 58.5), (70.65, 58.5), (70.65, 61.6), (66.9, 61.6),
                                (65.6, 63.1)], pcbnew.F_Cu),
        ('zone', 'Net-(D6-A)', [(67.2, 58.6), (69.45, 58.6), (69.45, 60.6), (67.2, 60.6)], pcbnew.B_Cu),
    ],
    # U20 exposed pad: one GND via is not enough heat path (rev 2 had 12);
    # a 3 x 5 grid of capped via-in-pad, clear of the In2 / B.Cu tracks
    'u20_ep_vias': [
        ('via', 'GND', x, y)
        for y in (52.2, 53.1, 54.0, 54.9, 55.8)
        for x in (69.3, 70.0, 70.7)
        if (x, y) != (70.0, 54.0)
    ],
    # after wall_jacks.py: TP36's moved pad back onto Q21's PG_15V pad, the J9 gate
    # stage clear of R38's +12V stub and a leftover drain stub
    'wall_jacks': [
        ('delete', 'Net-(Q5-D)', [(16.938, 67.49), (16.35, 68.15), (16.3, 69.6)]),
        ('track', 'Net-(Q5-D)', [(16.9375, 67.49), (16.2, 68.0), (16.2, 69.5), (16.3, 69.6)], 0.2, pcbnew.B_Cu),
        ('delete', 'Net-(Q21-D)', [(17.637, 78.8), (17.637, 78.697)]),
    ],
    # after usb_power_path.py and gridroute: clears the old +5V leftovers, keeps vias
    # out of the LM66100 pads and takes +5V round U28 on F.Cu, so its GND pad can
    # reach a via under the body. Both GND pads need those vias: the tracks box them in.
    'usb_power_path': [
        ('delete', '+5V', [(31.07, 73.01), (29.2, 74.88)]),
        ('delete_via', '+5V', 29.2, 74.88),
        ('delete', '+5V', [(30.0, 76.99), (28.45, 76.35), (27.25, 76.35), (27.1, 76.45), (27.0, 76.6),
                           (27.0, 77.75), (26.9, 77.9), (26.6, 78.1), (26.16, 78.15)]),
        ('track', '+5V', [(30.05, 75.3), (28.5, 76.8), (26.0, 76.85), (25.85, 78.65)], 0.3, pcbnew.F_Cu),
        ('via', '+5V', 25.85, 78.65),
        ('track', '+5V', [(25.85, 78.65), (26.16, 78.15)], 0.3, pcbnew.B_Cu),
        ('delete', '+5V_OR', [(23.0, 79.37), (23.0, 80.95), (24.35, 82.3)]),
        ('delete', '+5V_OR', [(24.43, 45.18), (24.43, 60.87)]),
        ('delete', '+5V_OR', [(28.3, 79.5), (27.95, 78.35), (27.84, 78.15), (27.3, 78.2),
                              (27.05, 83.9), (27.3, 82.6), (27.84, 82.65)]),
        ('delete_via', '+5V_OR', 27.95, 78.35),
        ('delete_via', '+5V_OR', 27.3, 78.2),
        ('delete_via', '+5V_OR', 27.3, 82.6),
        ('track', '+5V_OR', [(27.84, 78.15), (27.3, 79.0)], 0.3, pcbnew.B_Cu),
        ('via', '+5V_OR', 27.3, 79.0),
        ('track', '+5V_OR', [(27.3, 79.0), (28.3, 79.5)], 0.3, pcbnew.F_Cu),
        ('delete', '+5V_OR', [(24.4, 69.75), (27.3, 78.2)]),
        ('track', '+5V_OR', [(24.4, 69.75), (26.03, 74.5), (26.4, 77.9), (27.3, 79.0)], 0.3, pcbnew.In2_Cu),
        ('track', '+5V_OR', [(28.65, 82.3), (28.8, 82.4)], 0.3, pcbnew.B_Cu),
        ('track', '+5V_OR', [(27.84, 82.65), (28.45, 82.5)], 0.3, pcbnew.B_Cu),
        ('via', '+5V_OR', 28.8, 82.4),
        ('track', '+5V_OR', [(28.8, 82.4), (27.05, 83.9)], 0.3, pcbnew.F_Cu),
        ('via', 'GND', 27.0, 77.5),
        ('track', 'GND', [(26.16, 77.5), (27.0, 77.5)], 0.25, pcbnew.B_Cu),
        ('via', 'GND', 27.0, 82.0),
        ('track', 'GND', [(26.16, 82.0), (27.84, 82.0)], 0.25, pcbnew.B_Cu),
    ],
    # after the bottom-wall headers moved in (fan_headers.py, two_pin_headers.py):
    # NTC_ADC from U1 down In2 to J6, +5V down In2 to R81, a pull-up's +3V3 to JP4 on
    # In2, and a leftover +12V stub cut back
    'bottom_wall_headers': [
        ('track', 'NTC_ADC', [(75.25, 11.3), (74.22, 11.3), (72.38, 13.15), (72.38, 13.3)], 0.25, pcbnew.F_Cu),
        ('via', 'NTC_ADC', 72.38, 13.3),
        ('track', 'NTC_ADC', [(72.38, 13.3), (74.62, 15.54), (74.62, 21.71), (67.39, 28.94), (67.39, 34.89),
                              (65.3, 32.8), (60.75, 37.35), (60.75, 86.55), (60.6, 86.7)], 0.25, pcbnew.In2_Cu),
        ('track', '+5V', [(65.94, 65.72), (65.25, 65.72), (65.25, 86.5), (59.75, 92.0), (54.75, 92.0)],
         0.3, pcbnew.In2_Cu),
        ('via', '+5V', 54.75, 92.0),
        ('track', '+5V', [(54.75, 92.0), (54.85, 91.1)], 0.3, pcbnew.B_Cu),
        ('track', '+3V3', [(86.86, 81.96), (87.1, 82.85)], 0.3, pcbnew.B_Cu),
        ('via', '+3V3', 87.1, 82.85),
        ('track', '+3V3', [(87.1, 82.85), (86.85, 82.7), (84.85, 80.7), (84.85, 75.1), (85.75, 74.2),
                           (86.69, 74.2)], 0.2, pcbnew.In2_Cu),
        ('via', '+3V3', 86.69, 74.2),
        ('delete', '+12V', [(56.13, 89.27), (56.13, 88.5), (54.45, 88.5)]),
        ('track', '+12V', [(54.45, 88.5), (55.08, 88.5)], 0.5408, pcbnew.B_Cu),
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
            elif step[0] == 'delete_via':
                delete_via(board, *step[1:])
            elif step[0] == 'zone':
                zone(board, *step[1:])
            else:
                via(board, *step[1:])
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
