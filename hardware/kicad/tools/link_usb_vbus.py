"""Post-route fix: joins the two USB-C VBUS pad pairs.

Freerouting links one USB-C VBUS pad pair to the rest of USB_VBUS but leaves
the other pair isolated. This adds a via and a short B.Cu link between the two
pairs, trying a small set of positions until the board is DRC clean.

Run with KiCad's bundled python after `gen_pcb.py route` (edits the board in
place):  python3 tools/link_usb_vbus.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import export_fab
import pcbnew

KICAD_DIR = Path(__file__).resolve().parents[1]
BOARD = KICAD_DIR / 'cryocooler.kicad_pcb'
KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
NET = '/USB_VBUS'
# the right pair (A4 / B9) is at this x; the left pair (A9 / B4) runs along F.Cu
# on a horizontal segment that crosses x = LEFT_X
RIGHT_X = 98.4
LEFT_X_RANGE = (90.6, 91.4)


def mm(value):
    return int(round(value * 1e6))


def left_run_y(board):
    """y of the left pair's horizontal F.Cu run (the segment spanning LEFT_X_RANGE)."""
    for item in board.GetTracks():
        if item.GetClass() != 'PCB_TRACK' or item.GetNetname() != NET:
            continue
        start, end = item.GetStart(), item.GetEnd()
        if start.y != end.y:
            continue
        low, high = sorted((start.x, end.x))
        if low <= mm(LEFT_X_RANGE[0]) and high >= mm(LEFT_X_RANGE[1]):
            return start.y / 1e6
    raise RuntimeError('left VBUS run not found')


def build(source, target, left_x, row_y):
    board = pcbnew.LoadBoard(str(source))
    net = board.FindNet(NET)
    run_y = left_run_y(board)

    def track(points):
        for start, end in zip(points, points[1:]):
            item = pcbnew.PCB_TRACK(board)
            item.SetLayer(pcbnew.B_Cu)
            item.SetWidth(mm(0.3))
            item.SetStart(pcbnew.VECTOR2I(mm(start[0]), mm(start[1])))
            item.SetEnd(pcbnew.VECTOR2I(mm(end[0]), mm(end[1])))
            item.SetNet(net)
            board.Add(item)

    def via(point):
        item = pcbnew.PCB_VIA(board)
        item.SetPosition(pcbnew.VECTOR2I(mm(point[0]), mm(point[1])))
        item.SetWidth(mm(0.6))
        item.SetDrill(mm(0.3))
        item.SetViaType(pcbnew.VIATYPE_THROUGH)
        item.SetNet(net)
        board.Add(item)

    # via on the left pair's F.Cu run, B.Cu link above the D- via to a via at
    # the right pair's pads
    left = (left_x, run_y)
    right = (RIGHT_X, row_y)
    via(left)
    via(right)
    track([left, (93.0, run_y), (93.5, row_y), right])
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(target), board)


def violations(path):
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'drc.json'
        subprocess.run(
            [
                KICAD_CLI, 'pcb', 'drc', '--severity-all', '--format', 'json',
                '-o', str(report), str(path),
            ],
            capture_output=True,
            check=False,
        )
        data = json.loads(report.read_text())
    errors = [v for v in data['violations'] if v['severity'] == 'error']
    return len(errors), len(data['unconnected_items'])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / 'routed.kicad_pcb'
        candidate = Path(tmp) / 'candidate.kicad_pcb'
        shutil.copy(BOARD, source)
        for row_y in (8.3, 8.2):
            for left_x in (91.0, 90.6):
                # the candidate lives next to the project so DRC sees the rules
                build(source, candidate, left_x, row_y)
                shutil.copy(candidate, BOARD)
                if violations(BOARD) == (0, 0):
                    print('linked USB_VBUS pairs:', left_x, row_y)
                    export_fab.export_fabrication()
                    return 0
        shutil.copy(source, BOARD)
        print('no clean link found; board left unchanged')
        return 1


if __name__ == '__main__':
    sys.exit(main())
