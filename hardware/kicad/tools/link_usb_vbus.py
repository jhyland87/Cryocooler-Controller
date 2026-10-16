"""Post-route fix: joins the two USB-C VBUS pad pairs.

Freerouting links the A9/B4 pair to the rest of USB_VBUS but leaves the
A4/B9 pair isolated. This adds an F.Cu stub, a via pair and a short B.Cu
link, trying a small set of positions until the board is DRC clean.

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
PAD_RIGHT = (98.4, 7.88)  # A4 / B9
# existing F.Cu VBUS segment of the left pair, used as the second joint
SEGMENT_START = (92.646, 9.057)


def mm(value):
    return int(round(value * 1e6))


def build(source, target, right_x, row_y, left_x):
    board = pcbnew.LoadBoard(str(source))
    net = board.FindNet(NET)

    def track(layer, start, end):
        item = pcbnew.PCB_TRACK(board)
        item.SetLayer(layer)
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

    right = (right_x, row_y)
    left = (left_x, SEGMENT_START[1] + (SEGMENT_START[0] - left_x))
    track(pcbnew.F_Cu, PAD_RIGHT, right)
    via(right)
    via(left)
    track(pcbnew.B_Cu, right, left)
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
        for row_y in (11.0, 10.6, 10.2, 9.8, 9.4, 9.0):
            for right_x in (99.4, 99.9, 100.4):
                for left_x in (91.8, 92.2):
                    # the candidate lives next to the project so DRC sees the rules
                    build(source, candidate, right_x, row_y, left_x)
                    shutil.copy(candidate, BOARD)
                    if violations(BOARD) == (0, 0):
                        print('linked USB_VBUS pairs:', right_x, row_y, left_x)
                        export_fab.export_fabrication()
                        return 0
        shutil.copy(source, BOARD)
        print('no clean link found; board left unchanged')
        return 1


if __name__ == '__main__':
    sys.exit(main())
