"""Traces cooler_source.webp into artwork/cooler_trace.png (and, with potrace,
cooler_trace.geojson, which gen_pcb.py puts on the back silkscreen).

The two white stickers are masked out and the silhouette outline is added so
the barrel edge behind them stays. The committed trace was made with this
logic (a re-run may differ by a couple of pixels; keep LOGO_SOURCE_SIZE in
gen_pcb.py equal to the bitmap size you vectorize). Usage (needs Pillow, numpy and potrace):

    python3 artwork/trace_cooler.py            # threshold 9
    potrace -b geojson --turdsize 12 --alphamax 1.0 --opttolerance 0.6 \
        -o artwork/cooler_trace.geojson artwork/cooler_trace.bmp
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 9.0
# sticker corners in source pixels
STICKERS = [
    [(790, 500), (905, 418), (1112, 622), (995, 722)],
    [(950, 366), (1040, 312), (1268, 506), (1166, 594)],
]
AXIS_DEGREES = -33.4  # rotate so the cooler axis is horizontal


def main():
    source = Image.open(HERE / 'cooler_source.webp').convert('RGB')
    width, height = source.size
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for corners in STICKERS:
        draw.polygon(corners, fill=255)
    mask = mask.filter(ImageFilter.MaxFilter(15))
    gray = np.asarray(source.convert('L'), dtype=float)
    blurred = np.asarray(
        Image.fromarray(gray.astype('uint8')).filter(
            ImageFilter.GaussianBlur(1.6)
        ),
        dtype=float,
    )
    grad_x = np.zeros_like(blurred)
    grad_y = np.zeros_like(blurred)
    grad_x[:, 1:-1] = blurred[:, 2:] - blurred[:, :-2]
    grad_y[1:-1, :] = blurred[2:, :] - blurred[:-2, :]
    edges = (np.hypot(grad_x, grad_y) > THRESHOLD).astype('uint8') * 255
    edges[np.asarray(mask) > 0] = 0
    # silhouette outline from the filled object
    filled = Image.fromarray(((gray < 246) * 255).astype('uint8'))
    ImageDraw.floodfill(filled, (2, 2), 128)
    obj = Image.fromarray(((np.asarray(filled) != 128) * 255).astype('uint8'))
    rim = np.asarray(obj.filter(ImageFilter.MaxFilter(5)), dtype=int) - np.asarray(
        obj.filter(ImageFilter.MinFilter(5)), dtype=int
    )
    edges = np.maximum(edges, (rim > 0).astype('uint8') * 255)
    lines = Image.fromarray(edges).rotate(
        AXIS_DEGREES, expand=True, fillcolor=0, resample=Image.BICUBIC
    )
    lines = lines.crop(lines.getbbox()).filter(ImageFilter.MaxFilter(3))
    lines = lines.point(lambda value: 255 if value > 60 else 0)
    result = Image.eval(lines, lambda value: 255 - value)
    result.save(HERE / 'cooler_trace.png')
    result.convert('1').save(HERE / 'cooler_trace.bmp')
    print('trace size', result.size)


if __name__ == '__main__':
    main()
