"""Checks how a KiCad schematic is structured, from its .kicad_sch files:
what crosses between sheets and how, label pairs that should be wires, sheet
size, copied sheets and wires that touch a part they don't connect to.

Works on any schematic project in the repo. The project is a .kicad_pro; its
root sheet is the .kicad_sch of the same name, and its settings are in
schematic_checks.json beside it:

    {
      "allowed_globals": ["{SPI}"],    global labels allowed anywhere
      "max_parts_per_sheet": 30,       power symbols and flags not counted
      "long_net_mm": 85,               closer label pairs should be a wire
      "allowed_copies": [["a.kicad_sch", "b.kicad_sch"]],
                                       copied sheets the profile lists as an
                                       exception (user-approved)
      "baseline": "tools/sheet_structure_baseline.json"
    }

Every key is optional (defaults: none allowed, 30, 85, none, no baseline). The
baseline path is relative to the project folder.

Usage (--project defaults to hardware/kicad/cryocooler.kicad_pro):
    T=hardware/kicad/tools
    python3 $T/check_sheet_structure.py --project P.kicad_pro
    python3 $T/check_sheet_structure.py --project P.kicad_pro --update-baseline

A schematic drawn before these rules has a count per check in its baseline. A
count above its baseline fails (exit 1): a change may not add a shortcut. A
count below it passes and asks for --update-baseline, so the baseline only
goes down. A check that is not in the baseline must be 0.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from check_symbols import wires_near_bodies
from sexpr import find_all, parse, sval

DEFAULT_PROJECT = (
    Path(__file__).resolve().parent.parent / 'cryocooler.kicad_pro'
)
CONFIG_NAME = 'schematic_checks.json'
LABEL_KINDS = ('label', 'global_label', 'hierarchical_label')


class Project:
    """A schematic project and its check settings (see the module docstring).
    Every signal that leaves a sheet is a hierarchical label on the sheet and
    a sheet pin on its block in the parent; global labels are only for the
    communication buses in allowed_globals.
    """

    def __init__(self, pro_path):
        self.pro = Path(pro_path).resolve()
        self.dir = self.pro.parent
        self.root = self.pro.with_suffix('.kicad_sch')
        config_file = self.dir / CONFIG_NAME
        config = (
            json.loads(config_file.read_text()) if config_file.exists() else {}
        )
        self.allowed_globals = set(config.get('allowed_globals', []))
        self.max_parts = config.get('max_parts_per_sheet', 30)
        self.long_net_mm = config.get('long_net_mm', 85)
        self.allowed_copies = {
            frozenset(pair) for pair in config.get('allowed_copies', [])
        }
        baseline = config.get('baseline')
        self.baseline = self.dir / baseline if baseline else None

    def checks(self):
        return {
            'global_label': 'global label for a net not in allowed_globals',
            'close_label_pair': 'labels of one net closer than '
            f'{self.long_net_mm} mm (draw a wire)',
            'unmatched_sheet_pin': 'sheet pin without a hierarchical label, '
            'or the other way round',
            'too_many_parts': f'sheet with more than {self.max_parts} parts',
            'copied_sheet': 'two sheet files drawn the same (place one file '
            'twice)',
            'wire_near_body': 'wire, bus or bus entry touching or beside a '
            'part body it does not connect to',
        }


def prop(node, key):
    for item in find_all(node, 'property'):
        if sval(item[1]) == key:
            return sval(item[2])
    return None


def at(node):
    point = find_all(node, 'at')[0]
    return float(point[1]), float(point[2])


def bus_aliases(project):
    settings = json.loads(project.pro.read_text())
    return settings.get('schematic', {}).get('bus_aliases', {})


def bus_members(labels, aliases):
    """Nets carried by the buses labelled on one sheet. A bus label is a group
    in braces, with or without a name before them: an alias ({SPI}) or the
    nets themselves ({IMU_INT1 IMU_INT2}). Their member labels mark bus
    entries, so two of them close together are not a label pair.
    """
    members = set()
    for _kind, name, _point in labels:
        if not name.endswith('}') or '{' not in name:
            continue
        for item in name[name.index('{') + 1 : -1].split():
            members.update(aliases.get(item, [item]))
    return members


def load_sheet(path, root_dir):
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
    # a block names its file relative to the sheet it is drawn on
    folder = path.parent.relative_to(root_dir)
    blocks = [
        (
            (folder / prop(block, 'Sheetfile')).as_posix(),
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


def find_problems(project):
    problems = defaultdict(list)
    aliases = bus_aliases(project)
    root_dir = project.dir
    sheets = {project.root.name: load_sheet(project.root, root_dir)}
    pending = [project.root.name]
    while pending:
        for child, _ in sheets[pending.pop()][2]:
            if child not in sheets:
                sheets[child] = load_sheet(root_dir / child, root_dir)
                pending.append(child)

    for name, (labels, parts, blocks, _) in sheets.items():
        by_net = defaultdict(list)
        members = bus_members(labels, aliases)
        for kind, net, point in labels:
            if kind == 'global_label' and net not in project.allowed_globals:
                problems['global_label'].append(f'{name}: {net}')
            if net not in members:
                by_net[net].append(point)
        for net, points in sorted(by_net.items()):
            for first, second in combinations(points, 2):
                gap = math.dist(first, second)
                if gap < project.long_net_mm:
                    problems['close_label_pair'].append(
                        f'{name}: {net} at {first} and {second} '
                        f'({gap:.0f} mm apart)'
                    )
        if len(parts) > project.max_parts:
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

    for name in sheets:
        for _file, reference, what in wires_near_bodies(root_dir / name):
            problems['wire_near_body'].append(f'{name}: {reference}: {what}')

    # a page that only holds sheet blocks has no circuit to copy
    for (first, a), (second, b) in combinations(sorted(sheets.items()), 2):
        if a[1] and a[3] == b[3]:
            if frozenset((first, second)) in project.allowed_copies:
                continue
            problems['copied_sheet'].append(f'{first} and {second}')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--project', default=DEFAULT_PROJECT)
    parser.add_argument('--update-baseline', action='store_true')
    args = parser.parse_args()
    project = Project(args.project)
    checks = project.checks()
    problems = find_problems(project)
    counts = {check: len(problems[check]) for check in checks}
    if args.update_baseline:
        if project.baseline is None:
            sys.exit(f'no "baseline" in {project.dir / CONFIG_NAME}')
        project.baseline.write_text(json.dumps(counts, indent=2) + '\n')
        print(f'wrote {project.baseline}: {counts}')
        return
    baseline = (
        json.loads(project.baseline.read_text())
        if project.baseline and project.baseline.exists()
        else {}
    )
    print(f'project {project.pro.name}')
    failed = False
    for check, description in checks.items():
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
