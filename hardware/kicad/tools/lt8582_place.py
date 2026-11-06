"""lt8582_place.py in out — re-places the LT8582 power stage (positions, angles)."""
import sys
import pcbnew

PLACE = {
    'U20': (67.5, 32.4, 270),
    'D5': (61.85, 32.6, 270),
    'L2': (60.98, 32.6, 0),
    'C69': (61.9, 27.35, 90, 'bottom'),
    'C76': (72.7, 32.4, 270),
    'D6': (75.3, 32.4, 270),
    'L3': (72.0, 31.9, 0),
    'C70': (73.5, 27.4, 0, 'bottom'),
    'C52': (66.1, 30.0, 90),
    'C51': (65.6, 33.6, 90),
    'C78': (64.45, 28.0, 90),
    'R92': (65.55, 28.0, 90),
    'R88': (66.65, 28.0, 90),
    'R89': (67.75, 28.0, 90),
    'R93': (68.85, 28.0, 90),
    'C79': (69.95, 28.0, 90),
    'C77': (65.55, 25.7, 90),
    'C80': (68.85, 25.7, 90),
    'R90': (66.7, 35.9, 0),
    'R91': (69.25, 35.9, 0),
    'C33': (67.15, 34.9, 270, 'top'),
    'C34': (66.0, 36.4, 180, 'top'),
}

board = pcbnew.LoadBoard(sys.argv[1])
for ref, (x, y, angle, *side) in PLACE.items():
    fp = board.FindFootprintByReference(ref)
    if side and (side[0] == 'bottom') != fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetPosition(pcbnew.VECTOR2I(int(x * 1e6), int(y * 1e6)))
    fp.SetOrientationDegrees(angle)
board.Save(sys.argv[2])
mm = lambda v: round(v / 1e6, 2)
for ref in PLACE:
    fp = board.FindFootprintByReference(ref)
    print(ref, [(p.GetNumber(), p.GetNetname().replace('/Rails +-15V/', '')[:12], mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in fp.Pads() if p.GetNumber()][:4])
# courtyard overlaps among all same-side footprints near the stage
fps = [f for f in board.GetFootprints()]
for ref in PLACE:
    fp = board.FindFootprintByReference(ref)
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    mine = fp.GetCourtyard(layer)
    for other in fps:
        if other.GetReference() == ref or other.IsFlipped() != fp.IsFlipped():
            continue
        if mine.Collide(other.GetCourtyard(layer)):
            print('OVERLAP', ref, other.GetReference())
