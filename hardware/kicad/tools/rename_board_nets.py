"""Rename nets in the routed board after the schematic renamed them without
changing a pin (a global label became a net label, a sheet moved under a
parent). Names only: every `(net "NAME")` of a renamed net is rewritten and
nothing else, which the script proves by undoing the names in memory and
comparing with the file it read.

Usage: python3 rename_board_nets.py baseline.net new.net
baseline.net is the netlist the board was routed from (rev6-schematic).
Then run DRC with schematic parity.
"""

import sys
from pathlib import Path

from compare_netlists import board_view

BOARD = Path(__file__).resolve().parent.parent / 'cryocooler.kicad_pcb'


def main(baseline, new):
    (_, base_nets), (_, new_nets) = board_view(baseline), board_view(new)
    new_names = {tuple(pins): name for name, pins in new_nets.items()}
    renames = {
        name: new_names[tuple(pins)]
        for name, pins in base_nets.items()
        if name not in new_nets and tuple(pins) in new_names
    }
    before = BOARD.read_text()
    # the board may hold an in-between name from an earlier run: find each
    # net under the name it has now
    current = {}
    for old, name in renames.items():
        held = [n for n in {old, '/' + old, name} if f'(net "{n}")' in before]
        if len(held) != 1:
            print(f'{old}: found on the board as {held}; nothing written')
            return 1
        current[held[0]] = name
    text, done = before, {}
    for held, name in current.items():
        if held == name:
            continue
        tag = f'(net "{held}")'
        if text.count(f'"{held}"') != text.count(tag) or f'"{name}"' in text:
            print(f'{held}: named outside a net entry, or {name} is taken; nothing written')
            return 1
        done[held] = (name, text.count(tag))
        text = text.replace(tag, f'(net "{name}")')
    undone = text
    for held, (name, _) in done.items():
        undone = undone.replace(f'(net "{name}")', f'(net "{held}")')
    if undone != before:
        print('undoing the names does not give the board back; nothing written')
        return 1
    BOARD.write_text(text)
    print(f'{len(done)} nets renamed on the board '
          f'({sum(count for _, count in done.values())} entries)')
    for held, (name, _) in sorted(done.items()):
        print(f'  {held} -> {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
