"""Compare connectivity of two exported netlists by part values/pins (ignores
refs and net names). With --names, also require every net to keep its name and
its exact pins, which is what the routed board's schematic parity needs.

Usage: python3 compare_netlists.py [--names] baseline.net new.net
"""

import collections
import sys

from sexpr import find_all, sval
from verify_netlist import load


def signatures(path):
    comps, nets = load(path)
    values = {
        ref: sval(find_all(c, 'value')[0][1]) for ref, c in comps.items()
    }
    # two-pin parts without polarity can be drawn either way round, so their
    # pin numbers are ignored
    symmetric = {
        ref
        for ref, c in comps.items()
        if sval(find_all(find_all(c, 'libsource')[0], 'part')[0][1])
        in ('R_US', 'R_Small_US', 'C', 'C_Small', 'L', 'Fuse')
    }
    result = collections.Counter()
    for nodes in nets.values():
        group = tuple(
            sorted(
                (values[r], '*' if r in symmetric else pin)
                for r, pin, _ in nodes
            )
        )
        if len(group) > 1:
            result[group] += 1
    return result


def main(baseline, new):
    base, cur = signatures(baseline), signatures(new)
    only_base = base - cur
    only_new = cur - base
    print('nets:', sum(base.values()), sum(cur.values()))
    for label, items in (
        ('missing in new', only_base),
        ('extra in new', only_new),
    ):
        for group in list(items)[:12]:
            print(
                f'  {label}:',
                list(group)[:10],
                '...' if len(group) > 10 else '',
            )
    return 0 if not only_base and not only_new else 1


def renamed(baseline, new):
    """Prints nets whose name or pins differ; returns how many."""
    base, cur = (
        {
            name: sorted((ref, pin) for ref, pin, _ in nodes)
            for name, nodes in load(path)[1].items()
        }
        for path in (baseline, new)
    )
    changed = sorted(n for n in base.keys() | cur.keys() if base.get(n) != cur.get(n))
    print(f'net names: {len(changed)} of {len(base)} nets renamed or changed')
    for name in changed[:20]:
        where = 'both' if name in base and name in cur else (
            'baseline only' if name in base else 'new only'
        )
        print(f'  {name} ({where})')
    return len(changed)


if __name__ == '__main__':
    arguments = [a for a in sys.argv[1:] if a != '--names']
    status = main(*arguments)
    if '--names' in sys.argv and renamed(*arguments):
        status = 1
    sys.exit(status)
