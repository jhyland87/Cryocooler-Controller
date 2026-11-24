"""Writes fabrication/pcb-layer-stack.gif: one frame per layer, front to back,
each plotted with the board outline and labelled with the layer name.

    python3 hardware/kicad/tools/layer_stack_gif.py [board.kicad_pcb]

Needs kicad-cli, rsvg-convert (brew install librsvg) and Pillow.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from export_fab import BOARD, fab_dir, run_cli

LAYERS = ['F.Silkscreen', 'F.Paste', 'F.Mask', 'F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu',
          'B.Mask', 'B.Paste', 'B.Silkscreen']
WIDTH = 1600
BACKGROUND = '#10141c'
FRAME_MS = 1500
LABEL_HEIGHT = 70


def frame(board, layer, folder):
    """Plots one layer and returns it as a labelled image."""
    svg = folder / f'{layer}.svg'
    run_cli(['pcb', 'export', 'svg', '--mode-single', '--layers', f'{layer},Edge.Cuts',
             '--exclude-drawing-sheet', '--fit-page-to-board', '--check-zones',
             '-o', str(svg), str(board)])
    plot = folder / f'{layer}.plot.png'
    subprocess.run(['rsvg-convert', '-w', str(WIDTH), '-b', BACKGROUND, '-o', str(plot), str(svg)],
                   check=True)
    image = Image.open(plot).convert('RGB')
    labelled = Image.new('RGB', (image.width, image.height + LABEL_HEIGHT), BACKGROUND)
    labelled.paste(image, (0, LABEL_HEIGHT))
    ImageDraw.Draw(labelled).text((image.width // 2, LABEL_HEIGHT // 2), layer, fill='white',
                                  font=ImageFont.load_default(40), anchor='mm')
    return labelled


def main():
    board = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else BOARD
    output = fab_dir(board) / 'pcb-layer-stack.gif'
    with tempfile.TemporaryDirectory() as scratch:
        frames = [frame(board, layer, Path(scratch)) for layer in LAYERS]
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0,
                   optimize=True)
    print(f'{len(LAYERS)} frames -> {output}')


if __name__ == '__main__':
    main()
