"""One Freerouting round on a routed board with the rev 3 copper locked, so only
copper added since may be ripped up: fr_trial.py in.kicad_pcb rev3.kicad_pcb out.kicad_pcb
Run with tools/ on PYTHONPATH and FREEROUTING_HIDE=1. Write the output into a scratch
copy of the project, never the repo: saving a board loaded from elsewhere rewrites
the cryocooler.kicad_pro beside it with default settings."""
import sys
from pathlib import Path
import pcbnew
import ucs125_board as ub

in_path, rev3_path, out_path = sys.argv[1:4]
board = pcbnew.LoadBoard(in_path)
old = {item.m_Uuid.AsString() for item in pcbnew.LoadBoard(rev3_path).GetTracks()}

def key(item):
    if item.Type() == pcbnew.PCB_VIA_T:
        return ('via', item.GetPosition().x, item.GetPosition().y)
    a, b = sorted([(item.GetStart().x, item.GetStart().y), (item.GetEnd().x, item.GetEnd().y)])
    return (item.GetLayer(), a, b)

was_locked, kept = set(), 0
for item in board.GetTracks():
    if item.IsLocked():
        was_locked.add(key(item))
    if item.m_Uuid.AsString() in old:
        item.SetLocked(True)
        kept += 1
print('rev 3 items locked:', kept, 'free to move:', len(board.GetTracks()) - kept, flush=True)
work = Path(out_path).with_suffix('.route')
work.mkdir(exist_ok=True)
ub.run_freerouting(board, work, 1)
for item in board.GetTracks():
    item.SetLocked(key(item) in was_locked)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(out_path, board)
print('saved', flush=True)
