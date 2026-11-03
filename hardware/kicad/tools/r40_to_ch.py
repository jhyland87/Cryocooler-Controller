"""r40_to_ch.py in out — moves R40 (ADS1220 CS pull-up) from +3V3 to +3V3_CH."""
import sys
import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
pad = [p for p in board.FindFootprintByReference('R40').Pads() if p.GetNumber() == '1'][0]
assert pad.GetNetname() == '+3V3', pad.GetNetname()
spot = pad.GetPosition()
stubs = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == '+3V3'
         and t.GetLayer() == pcbnew.B_Cu and spot in (t.GetStart(), t.GetEnd())]
print('stubs', len(stubs))
for track in stubs:
    board.Delete(track)
pad.SetNet(board.FindNet('+3V3_CH'))
board.Save(sys.argv[2])
