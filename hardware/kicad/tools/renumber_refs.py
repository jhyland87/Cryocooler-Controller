"""Renumbers resistors, capacitors and diodes so parts with the same MPN have consecutive
references, which keeps order customer references short.

  map                      writes ref_map.py from the current schematic
  remap                    renumbers again: rewrites ref_map.py on top of the old map and
                           writes the step from old to new references to ref_map_rev3.py
  board old.net new.net board.kicad_pcb
                           renames footprints and the nets named after them
  text old.net new.net file...
                           renames references and those nets in tools and docs
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

import gen_bom
from sexpr import find_all, parse, sval

MAP_FILE = Path(__file__).parent / 'ref_map.py'
STEP_FILE = Path(__file__).parent / 'ref_map_rev3.py'
HEADER = '''"""Final R, C and D references, keyed by the number gen_schematic.py allocates.
Parts sharing an MPN are consecutive (renumber_refs.py). A part added later isn't
listed, so it keeps its allocated number, which is above all of these.
"""
REF_MAP = {
'''
STEP_HEADER = '''"""R, C and D references before the rev 3 renumber -> after it. Older notes and
commits, and rev3_board.py with rev3_placement.json, use the numbers on the left.
"""
REF_MAP = {
'''
# a reference on its own, not part of a name like AD633JRZ-R7, SMD R24, GD-D2,4 or %C3
REF_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_.%])(?<!JRZ-)(?<!SMD )(?<!GD-)([RCD]\d{1,3})\b(?!\.\d)(?!,\d)')


def build_map(parts):
    groups = defaultdict(lambda: defaultdict(list))
    for ref, value, footprint in parts:
        prefix = re.match(r'[A-Z]+', ref).group()
        if prefix not in ('R', 'C', 'D'):
            continue
        mpn = gen_bom.resolve(gen_bom.bom_value(ref, value, footprint), footprint)[1]
        groups[prefix][mpn].append(ref)
    ref_map = {}
    for prefix, by_mpn in groups.items():
        for refs in by_mpn.values():
            refs.sort(key=gen_bom.sort_key)
        number = 0
        # groups keep the order of their lowest old number, so C1 stays first
        for refs in sorted(by_mpn.values(), key=lambda refs: gen_bom.sort_key(refs[0])):
            for ref in refs:
                number += 1
                ref_map[ref] = f'{prefix}{number}'
    return ref_map


def net_names(path):
    """Maps (ref, pin) to net name for an exported netlist."""
    root = parse(Path(path).read_text())
    names = {}
    for net in find_all(find_all(root, 'nets')[0], 'net'):
        name = sval(find_all(net, 'name')[0][1])
        for node in find_all(net, 'node'):
            pin = (sval(find_all(node, 'ref')[0][1]), sval(find_all(node, 'pin')[0][1]))
            names[pin] = name
    return names


def build_net_map(ref_map, old_path, new_path):
    new_names = net_names(new_path)
    net_map = {}
    for (ref, pin), name in net_names(old_path).items():
        new_name = new_names[(ref_map.get(ref, ref), pin)]
        if new_name != name:
            if net_map.setdefault(name, new_name) != new_name:
                raise ValueError(f'net {name} split into {new_name} and {net_map[name]}')
    return net_map


def rename_board(path, ref_map, net_map):
    text = Path(path).read_text()
    text, count = re.subn(
        r'\(property "Reference" "([RCD]\d+)"',
        lambda match: f'(property "Reference" "{ref_map[match.group(1)]}"',
        text,
    )
    pattern = re.compile('|'.join(re.escape(f'"{name}"') for name in net_map))
    text = pattern.sub(lambda match: f'"{net_map[match.group()[1:-1]]}"', text)
    Path(path).write_text(text)
    print(f'{count} footprints renamed, {len(net_map)} nets renamed')


def rename_text(path, ref_map, net_map):
    text = Path(path).read_text()
    # net names are renamed as whole strings, in one pass so a new name isn't renamed again
    net_pattern = '|'.join(re.escape(name) for name in net_map)
    pieces = re.split(f'({net_pattern})', text)
    for index, piece in enumerate(pieces):
        if index % 2:
            pieces[index] = net_map[piece]
        else:
            pieces[index] = REF_PATTERN.sub(
                lambda match: ref_map.get(match.group(1), match.group(1)), piece)
    Path(path).write_text(''.join(pieces))


def write_map(path, header, ref_map):
    lines = [f"    '{old}': '{new}',\n" for old, new in
             sorted(ref_map.items(), key=lambda item: gen_bom.sort_key(item[0]))]
    path.write_text(header + ''.join(lines) + '}\n')


def remap():
    """Composes a new numbering with the old map, keyed by allocated numbers as before."""
    from ref_map import REF_MAP
    step = build_map(gen_bom.load_netlist())
    allocated = {final: number for number, final in REF_MAP.items()}
    write_map(MAP_FILE, HEADER, {allocated.get(old, old): new for old, new in step.items()})
    write_map(STEP_FILE, STEP_HEADER, step)
    print(len(step), 'references mapped')


def main():
    mode = sys.argv[1]
    if mode == 'remap':
        remap()
        return
    if mode == 'map':
        if MAP_FILE.exists():
            raise SystemExit('ref_map.py exists; it was built from the old numbers')
        ref_map = build_map(gen_bom.load_netlist())
        lines = [f"    '{old}': '{new}',\n" for old, new in
                 sorted(ref_map.items(), key=lambda item: gen_bom.sort_key(item[0]))]
        MAP_FILE.write_text(HEADER + ''.join(lines) + '}\n')
        print(len(ref_map), 'references mapped')
        return
    from ref_map_rev3 import REF_MAP as step
    net_map = build_net_map(step, sys.argv[2], sys.argv[3])
    print('net map:', net_map)
    if mode == 'board':
        rename_board(sys.argv[4], step, net_map)
        return
    for path in sys.argv[4:]:
        rename_text(path, step, net_map)


if __name__ == '__main__':
    main()
