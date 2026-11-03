"""lt8582_power.py in out — rips the LT8582 stage and draws its power copper by hand."""
import sys
import pcbnew
sys.path.insert(0, 'tools')
import ripup

LOCAL = {'Net-(D5-A)', 'Net-(U20-SWA2)', 'Net-(D6-A)', '/Rails +-15V/VC1', '/Rails +-15V/VC2',
         'Net-(U20-FBX1)', 'Net-(U20-FBX2)', '/Rails +-15V/RT1', '/Rails +-15V/RT2',
         '/Rails +-15V/SS1', '/Rails +-15V/SS2', 'Net-(U20-CLKOUT1)', 'Net-(C63-Pad1)',
         'Net-(C65-Pad1)'}
SHARED = {'+16V5', '-16V5', '+5V_PS15', 'PGP_16V5', 'PGN_16V5', 'GND'}
BOX = (56.5, 23.0, 77.0, 37.0)

nm = lambda v: int(round(v * 1e6))
board = pcbnew.LoadBoard(sys.argv[1])

def inside(item):
    bb = item.GetBoundingBox()
    return (bb.GetLeft() >= nm(BOX[0]) and bb.GetRight() <= nm(BOX[2])
            and bb.GetTop() >= nm(BOX[1]) and bb.GetBottom() <= nm(BOX[3]))

doomed = [t for t in board.GetTracks()
          if t.GetNetname() in LOCAL or (t.GetNetname() in SHARED and inside(t))]
print('ripped', len(doomed))
for item in doomed:
    board.Delete(item)
ripup.prune(board, SHARED)

def track(net, points, width, layer=pcbnew.B_Cu):
    for start, end in zip(points, points[1:]):
        seg = pcbnew.PCB_TRACK(board)
        seg.SetStart(pcbnew.VECTOR2I(nm(start[0]), nm(start[1])))
        seg.SetEnd(pcbnew.VECTOR2I(nm(end[0]), nm(end[1])))
        seg.SetWidth(nm(width))
        seg.SetLayer(layer)
        seg.SetNet(board.FindNet(net))
        seg.SetLocked(True)
        board.Add(seg)

def via(net, x, y):
    hole = pcbnew.PCB_VIA(board)
    hole.SetPosition(pcbnew.VECTOR2I(nm(x), nm(y)))
    hole.SetWidth(nm(0.45))
    hole.SetDrill(nm(0.2))
    hole.SetNet(board.FindNet(net))
    hole.SetLocked(True)
    board.Add(hole)

SW1, SW2, NODE_X = 'Net-(D5-A)', 'Net-(U20-SWA2)', 'Net-(D6-A)'
# boost switch node: C-shaped bus round U20's west end, D5 anode, L2 pad 2 above
track(SW1, [(64.75, 30.5), (63.65, 30.5)], 0.4)
track(SW1, [(64.75, 34.3), (63.65, 34.3)], 0.4)
track(SW1, [(63.65, 30.5), (63.65, 34.3)], 0.8)
track(SW1, [(61.85, 34.12), (63.65, 34.12)], 0.8)
for y in (31.2, 32.0, 32.8, 33.6):
    via(SW1, 63.45, y)
# inverting switch node: bus round the east end, C59 pad 1, L3 pad 3 above
track(SW2, [(70.25, 30.5), (71.25, 30.5)], 0.4)
track(SW2, [(70.25, 34.3), (71.25, 34.3)], 0.4)
track(SW2, [(71.25, 30.5), (71.25, 34.3)], 0.7)
track(SW2, [(71.25, 30.93), (72.7, 30.93)], 0.8)
via(SW2, 71.2, 33.95)
via(SW2, 71.2, 34.75)
# coupled-inductor node X: C59 pad 2 to D6 anode, L3 pad 4 above
track(NODE_X, [(72.7, 33.9), (75.3, 33.9)], 0.8)
via(NODE_X, 72.55, 34.0)
via(NODE_X, 73.15, 34.6)
# boost output: D5 cathode straight up to C58
track('+16V5', [(61.85, 30.6), (61.85, 29.3)], 0.8)
# grounds: U20 exposed pad, pin 19, output caps, D6 cathode
for x in (64.9, 65.9, 67.0, 68.1, 69.2, 70.2):
    for y in (31.9, 32.9):
        via('GND', x, y)
track('GND', [(67.25, 34.3), (67.25, 33.6)], 0.25)
# south pin row: RT1, RT2 and GND drop straight onto R57 / R58; VIN and SS
# leave through vias at their pads (C56 sits on the pin 22 via, C61 / C62 on
# top); CLKOUT1 ties pins 18 and 23 under the resistors
track('/Rails +-15V/RT1', [(66.25, 34.3), (66.25, 35.5), (66.19, 35.9)], 0.15)
track('/Rails +-15V/RT2', [(68.75, 34.3), (68.74, 35.9)], 0.15)
track('GND', [(67.25, 34.3), (67.25, 35.5), (67.21, 35.9)], 0.15)
track('Net-(U20-CLKOUT1)', [(67.75, 34.3), (67.75, 36.5), (65.25, 36.5), (65.25, 34.3)], 0.15)
for net, x in (('+5V_PS15', 65.75), ('/Rails +-15V/SS1', 66.75),
               ('/Rails +-15V/SS2', 68.25), ('+5V_PS15', 69.25)):
    via(net, x, 34.6)
via('GND', 61.3, 25.9)
via('GND', 74.97, 27.9)
via('GND', 75.3, 31.0)
via('GND', 75.3, 32.1)
board.Save(sys.argv[2])
