"""Count wire crossings on schematic sheets: a horizontal and a vertical wire
segment that pass through each other away from their ends. Buses are not
counted. One line per sheet that has any, then a total.

Usage: python3 count_crossings.py [sheet.kicad_sch ...]   (default: every sheet)
"""

import re
import sys
from pathlib import Path

KICAD_DIR = Path(__file__).resolve().parent.parent
WIRE = re.compile(
    r'\(wire\s*\(pts\s*\(xy ([\d.]+) ([\d.]+)\)\s*\(xy ([\d.]+) ([\d.]+)\)'
)


def crossings(path):
    wires = [tuple(float(v) for v in found) for found in WIRE.findall(path.read_text())]
    flat = [(min(a, c), max(a, c), b) for a, b, c, d in wires if abs(b - d) < 1e-6]
    upright = [(a, min(b, d), max(b, d)) for a, b, c, d in wires if abs(a - c) < 1e-6]
    return [
        (x, y)
        for x0, x1, y in flat
        for x, y0, y1 in upright
        if x0 + 0.01 < x < x1 - 0.01 and y0 + 0.01 < y < y1 - 0.01
    ]


def main(paths):
    sheets = [Path(p) for p in paths] or [
        KICAD_DIR / 'cryocooler.kicad_sch', *sorted((KICAD_DIR / 'sheets').glob('*.kicad_sch'))
    ]
    total = 0
    for sheet in sheets:
        found = crossings(sheet)
        total += len(found)
        if found:
            print(f'{sheet.name}: {len(found)} at ' + ', '.join(f'({x}, {y})' for x, y in found))
    print(f'wire crossings: {total}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
