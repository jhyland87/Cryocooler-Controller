"""Exports the fabrication files and board renders from cryocooler.kicad_pcb
with kicad-cli: Gerbers and drill files (fabrication/gerbers/), the JLCPCB
upload zip, and front / back 3D renders (fabrication/circuit-board-render-*.png).

gen_pcb.py and link_usb_vbus.py run this after they write the board, so the
files never lag the PCB. Run it by hand after any manual board edit:

    python3 hardware/kicad/tools/export_fab.py

Set SKIP_FAB_EXPORT=1 to skip it (fast iteration on the generators).
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

from pcbnetlist import KICAD_CLI, KICAD_DIR

BOARD = KICAD_DIR / 'cryocooler.kicad_pcb'
FAB_DIR = KICAD_DIR / 'fabrication'
GERBER_DIR = FAB_DIR / 'gerbers'
ZIP_PATH = FAB_DIR / 'cryocooler_jlcpcb.zip'
GERBER_LAYERS = (
    'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts'
)
# the files JLCPCB wants in the upload, in the order they are zipped
ZIP_FILES = (
    'cryocooler-F_Cu.gtl',
    'cryocooler-In1_Cu.g1',
    'cryocooler-In2_Cu.g2',
    'cryocooler-B_Cu.gbl',
    'cryocooler-F_Mask.gts',
    'cryocooler-B_Mask.gbs',
    'cryocooler-F_Silkscreen.gto',
    'cryocooler-B_Silkscreen.gbo',
    'cryocooler-Edge_Cuts.gm1',
    'cryocooler-PTH.drl',
    'cryocooler-NPTH.drl',
)
RENDERS = (
    ('top', 'circuit-board-render-front.png', ('--perspective',)),
    ('bottom', 'circuit-board-render-back.png', ()),
)
RENDER_SIZE = ('2400', '2100')


def run_cli(arguments):
    """Runs kicad-cli, raising with its output if it fails."""
    result = subprocess.run(
        [KICAD_CLI, *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'kicad-cli {" ".join(arguments[:2])} failed:\n{result.stdout}{result.stderr}'
        )


def export_gerbers():
    """Gerbers (with X2 attributes) and Excellon drill files plus drill maps
    and the drill report.
    """
    GERBER_DIR.mkdir(parents=True, exist_ok=True)
    run_cli(
        [
            'pcb', 'export', 'gerbers', '--layers', GERBER_LAYERS,
            '--subtract-soldermask', '-o', f'{GERBER_DIR}/', str(BOARD),
        ]
    )
    run_cli(
        [
            'pcb', 'export', 'drill', '--format', 'excellon',
            '--excellon-separate-th', '--excellon-units', 'mm',
            '--excellon-zeros-format', 'decimal', '--drill-origin',
            'absolute', '--generate-map', '--map-format', 'pdf',
            '--generate-report', '--report-path',
            str(GERBER_DIR / 'drill_report.txt'), '-o', f'{GERBER_DIR}/',
            str(BOARD),
        ]
    )


def build_zip():
    """Zips the Gerber and drill files into the JLCPCB upload."""
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ZIP_FILES:
            archive.write(GERBER_DIR / name, name)


def render_board():
    """3D renders of the top (perspective) and bottom of the board."""
    for side, name, extra in RENDERS:
        run_cli(
            [
                'pcb', 'render', '--side', side, '--width', RENDER_SIZE[0],
                '--height', RENDER_SIZE[1], '--quality', 'high',
                '--background', 'opaque', *extra,
                '-o', str(FAB_DIR / name), str(BOARD),
            ]
        )


def export_fabrication():
    """Regenerates the Gerbers, drill files, JLCPCB zip and board renders
    from the current PCB; does nothing if SKIP_FAB_EXPORT is set.

    Returns:
        True if the files were exported, False if skipped.
    """
    if os.environ.get('SKIP_FAB_EXPORT'):
        print('fabrication export skipped (SKIP_FAB_EXPORT)')
        return False
    export_gerbers()
    build_zip()
    render_board()
    print(f'fabrication files and renders written to {FAB_DIR}')
    return True


if __name__ == '__main__':
    export_fabrication()
    sys.exit(0)
