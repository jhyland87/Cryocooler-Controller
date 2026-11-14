"""Exports the fabrication files and board renders from a board (the main
cryocooler.kicad_pcb by default) with kicad-cli: Gerbers and drill files
(fabrication/gerbers/ beside the board), the JLCPCB upload zip, and front /
back / angled 3D renders (fabrication/circuit-board-render-*.png). The main
board also gets four edge-on renders and port callouts on front and back.

gen_pcb.py and link_usb_vbus.py run this after they write the board, so the
files never lag the PCB. Run it by hand after any manual board edit:

    python3 hardware/kicad/tools/export_fab.py
    python3 hardware/kicad/tools/export_fab.py hardware/kicad/imu/imu.kicad_pcb

Set SKIP_FAB_EXPORT=1 to skip it (fast iteration on the generators).
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from pcbnetlist import KICAD_CLI, KICAD_DIR

BOARD = KICAD_DIR / 'cryocooler.kicad_pcb'
# Wide enough for the port callouts beside the board (render_callouts.py).
RENDER_SIZE = ('3000', '2100')
ANGLE_RENDER_SIZE = ('2400', '1700')
# Lower lighting keeps the blue solder mask from washing out to purple at this angle.
ANGLE_RENDER_OPTIONS = (
    '--perspective', '--rotate', '-35,-24,2', '--zoom', '0.92', '--pan', '-0.85,0.5,0',
    '--light-camera', '0.2', '--light-top', '0.3', '--light-side', '0.15',
)
# Edge-on views, named for the board edge facing the camera (kicad-cli's 'back'
# and 'front' sides are the top and bottom edges). One zoom keeps the four at
# one scale; the pan centres the parts, which stand taller above the board
# than below it. The border is thin, so re-check after adding a taller part.
EDGE_LONG = ('2400', '520')
EDGE_SHORT = ('1560', '520')
EDGE_VIEW = ('--zoom', '4.3', '--pan', '0,-0.34,0')
RENDERS = (
    ('top', 'circuit-board-render-front.png', RENDER_SIZE, ('--perspective',)),
    ('bottom', 'circuit-board-render-back.png', RENDER_SIZE, ()),
    ('top', 'circuit-board-render-angle.png', ANGLE_RENDER_SIZE, ANGLE_RENDER_OPTIONS),
    ('back', 'circuit-board-render-edge-top.png', EDGE_LONG, EDGE_VIEW),
    ('front', 'circuit-board-render-edge-bottom.png', EDGE_LONG, EDGE_VIEW),
    ('left', 'circuit-board-render-edge-left.png', EDGE_SHORT, EDGE_VIEW),
    ('right', 'circuit-board-render-edge-right.png', EDGE_SHORT, EDGE_VIEW),
)
# The 18 x 18 mm IMU board: flat square views (perspective crops it behind the
# connector) and a steeper angle that shows the board past J1.
SQUARE_RENDER_SIZE = ('2000', '2000')
IMU_RENDERS = (
    ('top', 'circuit-board-render-front.png', SQUARE_RENDER_SIZE, ('--zoom', '0.9')),
    ('bottom', 'circuit-board-render-back.png', SQUARE_RENDER_SIZE, ('--zoom', '0.9')),
    ('top', 'circuit-board-render-angle.png', ANGLE_RENDER_SIZE,
     ('--perspective', '--rotate', '-45,0,-30', '--zoom', '0.8')),
)
RENDERS_BY_BOARD = {'imu': IMU_RENDERS}
# Renders that get port callouts, by board: file name -> copper side shown.
CALLOUT_RENDERS = {
    'cryocooler': {
        'circuit-board-render-front.png': 'F.Cu',
        'circuit-board-render-back.png': 'B.Cu',
    },
}


def run_cli(arguments):
    """Runs kicad-cli, raising with its output if it fails."""
    result = subprocess.run(
        [KICAD_CLI, *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'kicad-cli {" ".join(arguments[:2])} failed:\n{result.stdout}{result.stderr}'
        )


def fab_dir(board):
    """fabrication/ beside the board file."""
    return Path(board).parent / 'fabrication'


def inner_layers(board):
    """Inner copper layer numbers of a board, from its (layers ...) table."""
    text = Path(board).read_text()
    table = text[text.index('\t(layers'):text.index('\t(setup')]
    return sorted(int(n) for n in re.findall(r'"In(\d+)\.Cu"', table))


def gerber_layers(board):
    inner = ''.join(f'In{n}.Cu,' for n in inner_layers(board))
    return f'F.Cu,{inner}B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts'


def zip_files(board):
    """The files JLCPCB wants in the upload, in the order they are zipped."""
    stem = Path(board).stem
    return (
        f'{stem}-F_Cu.gtl',
        *(f'{stem}-In{n}_Cu.g{n}' for n in inner_layers(board)),
        f'{stem}-B_Cu.gbl',
        f'{stem}-F_Mask.gts',
        f'{stem}-B_Mask.gbs',
        f'{stem}-F_Silkscreen.gto',
        f'{stem}-B_Silkscreen.gbo',
        f'{stem}-Edge_Cuts.gm1',
        f'{stem}-PTH.drl',
        f'{stem}-NPTH.drl',
    )


def export_gerbers(board=BOARD):
    """Gerbers (with X2 attributes) and Excellon drill files plus drill maps
    and the drill report.
    """
    gerber_dir = fab_dir(board) / 'gerbers'
    gerber_dir.mkdir(parents=True, exist_ok=True)
    run_cli(
        [
            'pcb', 'export', 'gerbers', '--layers', gerber_layers(board),
            '--subtract-soldermask', '-o', f'{gerber_dir}/', str(board),
        ]
    )
    run_cli(
        [
            'pcb', 'export', 'drill', '--format', 'excellon',
            '--excellon-separate-th', '--excellon-units', 'mm',
            '--excellon-zeros-format', 'decimal', '--drill-origin',
            'absolute', '--generate-map', '--map-format', 'pdf',
            '--generate-report', '--report-path',
            str(gerber_dir / 'drill_report.txt'), '-o', f'{gerber_dir}/',
            str(board),
        ]
    )


def build_zip(board=BOARD):
    """Zips the Gerber and drill files into the JLCPCB upload."""
    gerber_dir = fab_dir(board) / 'gerbers'
    zip_path = fab_dir(board) / f'{Path(board).stem}_jlcpcb.zip'
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in zip_files(board):
            archive.write(gerber_dir / name, name)


def render(board, output, side, size, extra, quality='high', background='opaque'):
    """One kicad-cli 3D render of a board."""
    run_cli(
        [
            'pcb', 'render', '--side', side, '--width', size[0],
            '--height', size[1], '--quality', quality,
            '--background', background, '--use-board-stackup-colors', *extra,
            '-o', str(output), str(board),
        ]
    )


def add_callouts(board):
    """Runs render_callouts.py on a board's renders. It needs Pillow, which
    KiCad's bundled python lacks, so that case uses the python3 on the PATH.
    """
    python = sys.executable
    if importlib.util.find_spec('PIL') is None:
        python = shutil.which('python3')
    script = Path(__file__).with_name('render_callouts.py')
    result = subprocess.run(
        [python, str(script), str(board)], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f'render_callouts.py failed:\n{result.stdout}{result.stderr}')


def render_board(board=BOARD, renders=None):
    """3D renders of the board with its own camera settings from
    RENDERS_BY_BOARD if it has them (top, bottom and angled; the main board
    also gets its four edges and port callouts on the top and bottom views).
    """
    if renders is None:
        renders = RENDERS_BY_BOARD.get(Path(board).stem, RENDERS)
    for side, name, size, extra in renders:
        render(board, fab_dir(board) / name, side, size, extra)
    if Path(board).stem in CALLOUT_RENDERS:
        add_callouts(board)


def export_fabrication(board=BOARD, renders=None):
    """Regenerates the Gerbers, drill files, JLCPCB zip and board renders
    from the current PCB; does nothing if SKIP_FAB_EXPORT is set.

    Returns:
        True if the files were exported, False if skipped.
    """
    if os.environ.get('SKIP_FAB_EXPORT'):
        print('fabrication export skipped (SKIP_FAB_EXPORT)')
        return False
    export_gerbers(board)
    build_zip(board)
    render_board(board, renders)
    print(f'fabrication files and renders written to {fab_dir(board)}')
    return True


if __name__ == '__main__':
    export_fabrication(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BOARD)
    sys.exit(0)
