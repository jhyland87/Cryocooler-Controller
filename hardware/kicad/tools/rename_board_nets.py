"""Rename nets on the routed board after a schematic change that only renamed
them (a global label turned into a sheet pin, a sheet moved under a group).

Nets are matched by their pins between the two netlists, so nothing is moved,
rerouted or reconnected: only the names change. Stops if any net's pins differ.

Usage: <KiCad python> rename_board_nets.py baseline.net new.net [board]
Then run `gen_pcb.py link` and DRC with schematic parity.
"""

import sys
from pathlib import Path

import pcbnew

from gen_pcb import save_board
from verify_netlist import load

BOARD = Path(__file__).resolve().parent.parent / 'cryocooler.kicad_pcb'


def pin_groups(path):
    return {
        frozenset((ref, pin) for ref, pin, _ in nodes): name
        for name, nodes in load(path)[1].items()
    }


def main(baseline, new, board_path=BOARD):
    before, after = pin_groups(baseline), pin_groups(new)
    if set(before) != set(after):
        print('the netlists differ in connections, not only in names: nothing renamed')
        return 1
    renames = {
        before[group]: after[group]
        for group in before
        if before[group] != after[group]
    }
    board = pcbnew.LoadBoard(str(board_path))
    # two steps, so a name freed by one rename can be taken by another
    items = {}
    for old in renames:
        item = board.FindNet(old)
        if item is None:
            # a net with no pad on the board (single-pin or unconnected)
            continue
        items[old] = item
        item.SetNetname(f'__renaming__{old}')
    taken = {net.GetNetname() for net in board.GetNetInfo().NetsByName().values()}
    clashes = sorted(renames[old] for old in items if renames[old] in taken)
    if clashes:
        print('names already on the board:', ' '.join(clashes))
        return 1
    for old, item in items.items():
        item.SetNetname(renames[old])
    save_board(board, board_path)
    print(f'nets renamed on the board: {len(items)} of {len(renames)} in the netlist')
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
