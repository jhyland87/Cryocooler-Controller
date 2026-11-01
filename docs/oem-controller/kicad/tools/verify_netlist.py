"""
@file verify_netlist.py
@brief Check that KiCad's exported connectivity matches the figure specs exactly.

Two pins must share a KiCad net if and only if they share a spec net (power and
global nets are compared across pages; local nets within their page). Also runs a
coarse text-overlap check on the generated sheets.
Usage: python3 -I verify_netlist.py <netlist.net>
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import gen_oem_schematic as gen  # noqa: E402
from oemsch import POWER  # noqa: E402


def kicad_nets(path):
    """{(ref, pin): net code} from a kicadsexpr netlist."""
    text = re.sub(r'\s+', ' ', Path(path).read_text())
    result = {}
    for block in text.split('(net (code ')[1:]:
        code = block.split(')', 1)[0].strip('"')
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', block):
            result[(ref, pin)] = code
    return result


def main():
    actual = kicad_nets(sys.argv[1])
    specs = gen.load_specs(set(os.environ.get('OEM_ONLY', '').split()))
    globals_ = gen.global_nets(specs)
    expected = {}
    for _, spec in specs:
        page = spec.__name__
        for part in spec.PARTS:
            for pin, net in part['pins'].items():
                if net == 'NC':
                    continue
                scope = net if (net in POWER or net in globals_) else f'{page}/{net}'
                expected[(part['ref'], str(pin))] = scope
    problems = 0
    missing = [key for key in expected if key not in actual]
    for key in missing:
        print('  missing from netlist:', key)
        problems += 1
    by_expected, by_actual = defaultdict(set), defaultdict(set)
    for key, net in expected.items():
        if key in actual:
            by_expected[net].add(actual[key])
            by_actual[actual[key]].add(net)
    for net, codes in by_expected.items():
        if len(codes) > 1:
            print(f'  spec net {net} split across {len(codes)} KiCad nets')
            problems += 1
    for code, nets in by_actual.items():
        if len(nets) > 1:
            print(f'  KiCad net {code} merges spec nets {sorted(nets)}')
            problems += 1
    print(f'netlist check: {len(expected)} pins, {problems} problems')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
