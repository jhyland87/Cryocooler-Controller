"""Point the board's footprints at their symbols after parts changed sheets (a
sheet moved under a parent, a group split off onto a sheet of its own): each
footprint takes the symbol path and sheet name the new netlist gives its
reference. Text only: the script proves it by blanking every path and sheet
name in the old and the new text and comparing. Safe to run twice.

Usage: python3 relink_board_sheets.py new.net
Then run DRC with schematic parity.
"""

import re
import sys
from pathlib import Path

from sexpr import find_all, sval
from verify_netlist import load

BOARD = Path(__file__).resolve().parent.parent / 'cryocooler.kicad_pcb'
LINK = re.compile(r'\((path|sheetname) "[^"]*"\)')


def symbol_links(netlist):
    """reference -> (symbol path, sheet name) from a netlist export."""
    links = {}
    for ref, comp in load(netlist)[0].items():
        sheet = find_all(comp, 'sheetpath')[0]
        names = sval(find_all(sheet, 'names')[0][1])
        stamps = sval(find_all(sheet, 'tstamps')[0][1])
        symbol = sval([node for node in comp[1:] if node[0] == 'tstamps'][0][1])
        links[ref] = (stamps.rstrip('/') + '/' + symbol, names)
    return links


def main(netlist):
    links = symbol_links(netlist)
    before = BOARD.read_text()
    chunks = before.split('\n\t(footprint ')
    moved = 0
    for index, chunk in enumerate(chunks[1:], 1):
        found = re.search(r'\(property "Reference" "([^"]+)"', chunk)
        if not found or found.group(1) not in links:
            continue
        path, names = links[found.group(1)]
        new = re.sub(r'\(path "[^"]*"\)', f'(path "{path}")', chunk, count=1)
        new = re.sub(r'\(sheetname "[^"]*"\)', f'(sheetname "{names}")', new, count=1)
        moved += new != chunk
        chunks[index] = new
    text = '\n\t(footprint '.join(chunks)
    if LINK.sub(r'(\1)', text) != LINK.sub(r'(\1)', before):
        print('more than paths and sheet names would change; nothing written')
        return 1
    BOARD.write_text(text)
    print(f'footprints relinked to their sheets: {moved}')
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
