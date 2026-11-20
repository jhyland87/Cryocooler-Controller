"""Checks how the generated schematic is structured, from the .kicad_sch
files: what crosses between sheets and how, label pairs that should be wires,
sheet size and copied sheets.

Usage (from hardware/kicad/):
    python3 tools/check_sheet_structure.py                    # check
    python3 tools/check_sheet_structure.py --update-baseline  # after a fix

The schematic was drawn with global labels before these rules existed, so
each check has a count in tools/sheet_structure_baseline.json. A count above
its baseline fails (exit 1): a change may not add a shortcut. A count below
it passes and asks for --update-baseline, so the baseline only goes down. A
check that is not in the baseline must be 0.
"""

import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from layout import LONG_NET_MM
from sexpr import find_all, parse, sval

ROOT_DIR = Path(__file__).resolve().parent.parent
ROOT_FILE = ROOT_DIR / 'cryocooler.kicad_sch'
BASELINE_FILE = Path(__file__).resolve().parent / (
    'sheet_structure_baseline.json'
)

# Global labels allowed anywhere. Every other signal that leaves a sheet is a
# hierarchical label on the sheet and a sheet pin on its block in the parent.
# Shared buses are drawn as a KiCad bus ending in one global label; their
# member nets carry local labels.
ALLOWED_GLOBALS = {'{SPI}', '{I2C}'}
# A sheet holds one function. Past this many parts (power symbols and flags
# not counted) it is split.
MAX_PARTS_PER_SHEET = 30
LABEL_KINDS = ('label', 'global_label', 'hierarchical_label')
CHECKS = {
    'global_label': 'global label for a net not in ALLOWED_GLOBALS',
    'close_label_pair': f'labels of one net closer than {LONG_NET_MM} mm '
    '(draw a wire)',
    'unmatched_sheet_pin': 'sheet pin without a hierarchical label, or the '
    'other way round',
    'too_many_parts': f'sheet with more than {MAX_PARTS_PER_SHEET} parts',
    'copied_sheet': 'two sheet files drawn the same (place one file twice)',
}


def prop(node, key):
    for item in find_all(node, 'property'):
        if sval(item[1]) == key:
            return sval(item[2])
    return None


def at(node):
    point = find_all(node, 'at')[0]
    return float(point[1]), float(point[2])


def bus_members():
    project = json.loads((ROOT_DIR / 'cryocooler.kicad_pro').read_text())
    aliases = project.get('schematic', {}).get('bus_aliases', {})
    return {net for members in aliases.values() for net in members}


def load_sheet(path):
    tree = parse(path.read_text())
    labels = [
        (kind, sval(item[1]), at(item))
        for kind in LABEL_KINDS
        for item in find_all(tree, kind)
    ]
    parts = [
        item
        for item in find_all(tree, 'symbol')
        if not sval(find_all(item, 'lib_id')[0][1]).startswith('power:')
    ]
    blocks = [
        (
            prop(block, 'Sheetfile'),
            {sval(pin[1]) for pin in find_all(block, 'pin')},
        )
        for block in find_all(tree, 'sheet')
    ]
    wires = sorted(
        tuple(
            (float(xy[1]), float(xy[2]))
            for xy in find_all(find_all(wire, 'pts')[0], 'xy')
        )
        for wire in find_all(tree, 'wire')
    )
    # what the page looks like, ignoring references, values and net names
    # (a copied channel often differs only in "IO1" vs "IO2"): two sheets with
    # the same drawing are one circuit that should be placed twice
    drawing = (
        tuple(wires),
        tuple(
            sorted((sval(find_all(p, 'lib_id')[0][1]), at(p)) for p in parts)
        ),
        tuple(sorted((kind, point) for kind, _, point in labels)),
    )
    return labels, parts, blocks, drawing


def find_problems():
    problems = defaultdict(list)
    members = bus_members()
    sheets = {'cryocooler.kicad_sch': load_sheet(ROOT_FILE)}
    pending = [ROOT_FILE.name]
    while pending:
        for child, _ in sheets[pending.pop()][2]:
            if child not in sheets:
                sheets[child] = load_sheet(ROOT_DIR / child)
                pending.append(child)

    for name, (labels, parts, blocks, _) in sheets.items():
        by_net = defaultdict(list)
        for kind, net, point in labels:
            if kind == 'global_label' and net not in ALLOWED_GLOBALS:
                problems['global_label'].append(f'{name}: {net}')
            if net not in members:
                by_net[net].append(point)
        for net, points in sorted(by_net.items()):
            for first, second in combinations(points, 2):
                gap = math.dist(first, second)
                if gap < LONG_NET_MM:
                    problems['close_label_pair'].append(
                        f'{name}: {net} at {first} and {second} '
                        f'({gap:.0f} mm apart)'
                    )
        if len(parts) > MAX_PARTS_PER_SHEET:
            problems['too_many_parts'].append(f'{name}: {len(parts)} parts')
        for child, pins in blocks:
            hier = {
                net
                for kind, net, _ in sheets[child][0]
                if kind == 'hierarchical_label'
            }
            for net in sorted(pins - hier):
                problems['unmatched_sheet_pin'].append(
                    f'{name}: block {child} has pin {net}, the sheet has no '
                    'hierarchical label for it'
                )
            for net in sorted(hier - pins):
                problems['unmatched_sheet_pin'].append(
                    f'{child}: hierarchical label {net} has no pin on its '
                    f'block in {name}'
                )

    for (first, a), (second, b) in combinations(sorted(sheets.items()), 2):
        if a[3] == b[3]:
            problems['copied_sheet'].append(f'{first} and {second}')
    return problems


def main():
    problems = find_problems()
    counts = {check: len(problems[check]) for check in CHECKS}
    if '--update-baseline' in sys.argv:
        BASELINE_FILE.write_text(json.dumps(counts, indent=2) + '\n')
        print(f'wrote {BASELINE_FILE.name}: {counts}')
        return
    baseline = (
        json.loads(BASELINE_FILE.read_text()) if BASELINE_FILE.exists() else {}
    )
    failed = False
    for check, description in CHECKS.items():
        limit = baseline.get(check, 0)
        count = counts[check]
        for problem in problems[check]:
            print(f'  [{check}] {problem}')
        verdict = 'ok'
        if count > limit:
            verdict = 'FAIL: above baseline'
            failed = True
        elif count < limit:
            verdict = 'below baseline: run --update-baseline'
        print(f'{check}: {count} (baseline {limit}) {verdict} - {description}')
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
