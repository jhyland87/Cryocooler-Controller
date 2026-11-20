"""Compare connectivity of two exported netlists by part values/pins (ignores
refs and net names). With --strict, compare what the routed board depends on
instead: every reference with its value and footprint, and every net with its
exact name and pins. Every difference is listed. --renamed (with --strict)
accepts a net that kept exactly its pins under another name (a global label
turned into a net label, a sheet moved under a parent): those are counted, and
listed with --list, not reported as differences. The board file must carry the
same new names (rename_board_nets.py).

Usage: python3 compare_netlists.py [--strict [--renamed [--list]]] baseline.net new.net
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


def field(comp, key):
    found = find_all(comp, key)
    return sval(found[0][1]) if found else ''


def board_view(path):
    """What the board is built from: parts by reference, nets by name."""
    comps, nets = load(path)
    parts = {
        ref: {'value': field(c, 'value'), 'footprint': field(c, 'footprint')}
        for ref, c in comps.items()
    }
    pins = {
        name: sorted((ref, pin) for ref, pin, _ in nodes)
        for name, nodes in nets.items()
    }
    return parts, pins


def strict(baseline, new, renamed=False, show=False):
    (base_parts, base_nets), (new_parts, new_nets) = (
        board_view(baseline),
        board_view(new),
    )
    differences = []
    for ref in sorted(base_parts.keys() | new_parts.keys()):
        if ref not in new_parts:
            differences.append(f'part {ref}: missing in new')
            continue
        if ref not in base_parts:
            differences.append(f'part {ref}: extra in new')
            continue
        for key in ('value', 'footprint'):
            old, cur = base_parts[ref][key], new_parts[ref][key]
            if old != cur:
                differences.append(f'part {ref}: {key} {old!r} -> {cur!r}')
    moved = {}
    if renamed:
        new_names = {tuple(pins): name for name, pins in new_nets.items()}
        moved = {
            name: new_names[tuple(pins)]
            for name, pins in base_nets.items()
            if name not in new_nets and new_names.get(tuple(pins), name) not in base_nets
            and tuple(pins) in new_names
        }
        base_nets = {moved.get(n, n): p for n, p in base_nets.items()}
    # a net that kept its pins under another name is reported as a rename
    by_pins = {tuple(pins): name for name, pins in new_nets.items()}
    renamed_to = set()
    for name in sorted(base_nets.keys() | new_nets.keys()):
        old, cur = base_nets.get(name), new_nets.get(name)
        if old == cur:
            continue
        if cur is None:
            other = by_pins.get(tuple(old))
            if other is not None and other not in base_nets:
                differences.append(f'net {name!r}: renamed to {other!r}')
                renamed_to.add(other)
            else:
                differences.append(f'net {name!r}: missing in new')
        elif old is None:
            if name not in renamed_to:
                differences.append(f'net {name!r}: extra in new, pins {cur}')
        else:
            gone = sorted(set(old) - set(cur))
            added = sorted(set(cur) - set(old))
            differences.append(
                f'net {name!r}: pins removed {gone}, pins added {added}'
            )
    print(
        f'strict: {len(base_parts)} parts, {len(base_nets)} nets in baseline; '
        f'{len(new_parts)} parts, {len(new_nets)} nets in new; '
        f'{len(differences)} differences'
        + (f'; {len(moved)} nets renamed with their pins unchanged' if renamed else '')
    )
    if show:
        for old, name in sorted(moved.items()):
            print(f'  renamed {old} -> {name}')
    for difference in differences:
        print(f'  {difference}')
    return 1 if differences else 0


if __name__ == '__main__':
    arguments = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--strict' in sys.argv:
        sys.exit(strict(*arguments, renamed='--renamed' in sys.argv, show='--list' in sys.argv))
    sys.exit(main(*arguments))
