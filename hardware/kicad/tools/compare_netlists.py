"""Compare connectivity of two exported netlists by part values/pins (ignores refs and net names).

Usage: python3 compare_netlists.py baseline.net new.net
"""
import collections
import sys

from sexpr import find_all, sval
from verify_netlist import load


def signatures(path):
    comps, nets = load(path)
    values = {ref: sval(find_all(c, 'value')[0][1]) for ref, c in comps.items()}
    # two-pin parts without polarity can be drawn either way round, so their pin numbers are ignored
    symmetric = {ref for ref, c in comps.items()
                 if sval(find_all(find_all(c, 'libsource')[0], 'part')[0][1]) in ('R_US', 'C', 'L', 'Fuse')}
    result = collections.Counter()
    for nodes in nets.values():
        group = tuple(sorted((values[r], '*' if r in symmetric else pin) for r, pin, _ in nodes))
        if len(group) > 1:
            result[group] += 1
    return result


def main(baseline, new):
    base, cur = signatures(baseline), signatures(new)
    only_base = base - cur
    only_new = cur - base
    print('nets:', sum(base.values()), sum(cur.values()))
    for label, items in (('missing in new', only_base), ('extra in new', only_new)):
        for group in list(items)[:12]:
            print(f'  {label}:', list(group)[:10], '...' if len(group) > 10 else '')
    return 0 if not only_base and not only_new else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
