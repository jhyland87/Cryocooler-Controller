"""
@file gen_oem_schematic.py
@brief Build the OEM controller KiCad project from the figure specs.

Hierarchy: root -> one sheet per patent PDF with schematics -> one page per figure.
Run: python3 -I docs/oem-controller/kicad/tools/gen_oem_schematic.py [spec ...]
(no arguments = every spec in SPECS).
"""

import importlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import os  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import oemsch  # noqa: E402
from oemsch import kicadgen  # noqa: E402

KICAD_DIR = HERE.parent
# OEM_KICAD_OUT redirects all output (scratch builds, parallel checks)
OUT_DIR = Path(os.environ.get('OEM_KICAD_OUT', KICAD_DIR))
oemsch.LIB_PATH = OUT_DIR / 'lib' / f'{oemsch.LIB_NAME}.kicad_sym'
PROJECT = 'oem-controller'
ROOT_UUID = kicadgen.stable_uuid('root')

# (patent sheet title, file stem, [spec module names in page order])
PATENTS = [
    ('US6098409 (= US6256999)', 'US6098409', [
        'fig5a', 'fig5b', 'fig5c', 'fig5d', 'fig5e', 'fig5f', 'fig5g', 'fig5h',
        'fig6a', 'fig6b', 'fig6c',
    ]),
]


def load_specs(only):
    """Load the figure specs (all, or those named in `only`) with project-unique refs."""
    specs = []
    for title, stem, names in PATENTS:
        for name in names:
            if only and name not in only:
                continue
            if not (KICAD_DIR / 'specs' / f'{name}.py').exists():
                print(f'  (skip {name}: no spec yet)')
                continue
            spec = importlib.import_module(f'specs.{name}')
            if getattr(spec, 'REDRAWN', False) and not hasattr(spec, '_all_parts'):
                # tools see every part of the figure; the builder places each on its own sheet
                spec._all_parts = True
                spec.PARTS = list(getattr(spec, 'PAGE_PARTS', [])) + [
                    part for node in spec.CHILDREN for part in node.PARTS]
            specs.append((stem, spec))
    # Refs are made unique among the specs being built (all of them for the real build).
    make_refs_unique([spec for _, spec in specs])
    apply_aliases([spec for _, spec in specs])
    return specs


# Printed name -> name used, for one wire printed differently on different figures.
# Each join is listed on the page it changes and in ../TRANSCRIPTION_NOTES.md.
ALIASES = {
    'COOLER.MON': 'COOLER_MON',      # 5H; 5G prints COOLER_MON (U22 PE5)
    'ERR.WARMERS': 'ERR_WARNERS',    # 5H; 5G prints ERR_WARNERS (U22 PE2)
    'CS_CNTRL': 'CS_CTRL',           # 5A; 5B/5H print CS_CTRL
    'DEMAR_TEMP': 'DEWAR_TEMP',      # 5H; 5A prints DEWAR_TEMP
    'RAM_SHUTO_T-': 'RAW_SHUTO_T-',  # 5E; 5B prints RAW_SHUTO_T-
    # [inference] 5C U33 drives NOT_TOTAL and nothing reads it; 5E/5G read HOT TOTAL /
    # HOT-TOTAL and nothing drives it. Taken as one net.
    'HOT_TOTAL': 'NOT_TOTAL',        # 5E prints "HOT TOTAL"
    'HOT-TOTAL': 'NOT_TOTAL',        # 5G U22 PE4/AN4
}


def apply_aliases(specs):
    """Rename aliased nets in pins and GLOBALS; record the joins on spec._aliases."""
    for spec in specs:
        if hasattr(spec, '_aliases'):
            continue
        used = set()
        for part in spec.PARTS:
            for pin, net in part['pins'].items():
                if ALIASES.get(net, net) != net:
                    used.add(net)
                    part['pins'][pin] = ALIASES[net]
        if hasattr(spec, 'GLOBALS'):
            spec.GLOBALS = [ALIASES.get(net, net) for net in spec.GLOBALS]
        spec._aliases = sorted(used)


def make_refs_unique(specs):
    """
    The patent restarts or reuses designators between figures (e.g. the FIG 6
    daughter board's R1/J1/V1). A ref used on more than one figure gets the
    figure id appended (R16 -> R16_5D) so KiCad does not merge the parts; the
    printed ref is kept in the Printed_Ref field. Runs once per spec module.
    """
    owners = {}
    for spec in specs:
        for part in spec.PARTS:
            owners.setdefault(part['ref'], set()).add(spec.__name__)
    shared = {ref for ref, pages in owners.items() if len(pages) > 1}
    for spec in specs:
        if getattr(spec, '_refs_unique', False):
            continue
        suffix = '_' + spec.__name__.split('.')[-1].replace('fig', '').upper()
        renamed = {}
        for part in spec.PARTS:
            if part['ref'] in shared:
                renamed[part['ref']] = part['ref'] + suffix
                part['printed'] = part['printed'] or part['ref']
                part['ref'] += suffix
        spec._renamed = dict(renamed)
        spec.WIRES = [
            tuple(renamed.get(end.rsplit('.', 1)[0], end.rsplit('.', 1)[0]) + '.' + end.rsplit('.', 1)[1]
                  if index < 2 else end for index, end in enumerate(entry))
            for entry in getattr(spec, 'WIRES', [])
        ]
        spec._refs_unique = True


def global_nets(specs):
    """Nets used on more than one page become global labels."""
    pages = {}
    for _, spec in specs:
        for part in spec.PARTS:
            for net in part['pins'].values():
                pages.setdefault(net, set()).add(spec.__name__)
    declared = set()
    for _, spec in specs:
        declared |= set(getattr(spec, 'GLOBALS', ()))
    return {net for net, used in pages.items() if len(used) > 1} | declared


def build_redrawn(figure, spec, stem, name, globals_, page, project_sheets, sheets_out):
    """
    Draw a redrawn figure: one sheet per child, and the figure page with their blocks.
    Returns the next free page number.
    """
    block_ends = {}
    for node in spec.CHILDREN:
        sheet = kicadgen.Sheet(node.TITLE, f'{stem}_{name}_{node.NAME}.kicad_sch', node.PAPER)
        sheet.uid = kicadgen.stable_uuid(f'sheet/{stem}/{name}/{node.NAME}')
        sheet.path = f'{figure.path}/{sheet.uid}'
        oemsch.build_node(sheet, node, spec, globals_, page_name=f'{spec.__name__}/{node.NAME}')
        sheet.note(f'{spec.TITLE}\n{node.TITLE}\nSource: {spec.SOURCE}', 15, 18, 2.5)
        col, row = node.AT
        text, ends = oemsch.sheet_block_pins(figure.path, sheet, sheet.filename, page,
                                             col * oemsch.CELL, row * oemsch.CELL, PROJECT, node,
                                             sheet_name=node.SHORT)
        figure.sheet_symbols.append(text)
        for net, end in ends.items():
            block_ends[f'{node.NAME}:{net}'] = end
            figure.wires.append((sheet_pin_point(end), end[0]))
        project_sheets.append([sheet.uid, node.TITLE])
        page += 1
        sheets_out.append(sheet)
    page_node = SimpleNamespace(PARTS=[], PAGE_PARTS=list(getattr(spec, 'PAGE_PARTS', [])),
                                WIRES=list(getattr(spec, 'PAGE_WIRES', [])), PORTS=spec.PORTS,
                                NOTES=getattr(spec, 'NOTES', []),
                                LONG_NETS=set(getattr(spec, 'PAGE_LONG_NETS', ())),
                                NAMES=dict(getattr(spec, 'PAGE_NAMES', {})),
                                TAPS=list(getattr(spec, 'PAGE_TAPS', [])))
    oemsch.build_node(figure, page_node, spec, globals_, block_ends=block_ends)
    used = {net for sheet in sheets_out + [figure] if sheet.filename.startswith(f'{stem}_{name}')
            for _, net, _, _ in sheet.labels}
    unused = set(spec.NET_DESCRIPTIONS) - used
    assert not unused, f'{spec.__name__}: NET_DESCRIPTIONS for labels that are gone: {sorted(unused)}'
    return page


def sheet_pin_point(end):
    """The pin point on the block edge for a stub end 2 cells out."""
    (x, y), (dx, dy) = end
    return (x - dx * 2 * oemsch.CELL, y - dy * 2 * oemsch.CELL)


def redrawn_only(specs):
    """Nets used on more than one figure, all of them redrawn: joined by sheet pins."""
    pages, redrawn = {}, set()
    for _, spec in specs:
        if getattr(spec, 'REDRAWN', False):
            redrawn.add(spec.__name__)
        for part in spec.PARTS:
            for net in part['pins'].values():
                pages.setdefault(net, set()).add(spec.__name__)
    return {net for net, used in pages.items() if len(used) > 1 and used <= redrawn}


def bridge_to_globals(patent, ends, globals_, joined):
    """
    Until every figure is redrawn, the other figures still reach these nets through
    global labels; a global label on each of a redrawn figure's sheet pins joins them.
    A net whose figures are all redrawn is collected in `joined` for join_figures().
    """
    for net, ((x, y), (dx, dy)) in ends.items():
        assert net in globals_, f'figure port {net} is not used on any other figure'
        patent.wires.append((sheet_pin_point(((x, y), (dx, dy))), (x, y)))
        if net in joined:
            joined[net].append(((x, y), (dx, dy)))
            continue
        patent.labels.append(('global_label', net, (x, y), 0 if dx > 0 else 180))


def join_figures(patent, joined):
    """
    Join redrawn figures' sheet pins on the patent sheet: two facing pins on one row by
    a wire, otherwise a net label on each pin.
    """
    for net, ends in joined.items():
        if not ends:
            continue  # not a figure port (a power net)
        assert len(ends) > 1, f'{net}: only one redrawn figure has a sheet pin for it'
        (a, da), (b, db) = sorted(ends)[0], sorted(ends)[-1]
        if len(ends) == 2 and abs(a[1] - b[1]) < 1e-6 and da == (1, 0) and db == (-1, 0):
            patent.wires.append((a, b))
            continue
        for (x, y), (dx, _) in ends:
            patent.labels.append(('label', net, (x, y), 0 if dx > 0 else 180))


def render(sheet):
    text = sheet.render(ROOT_UUID)
    return text.replace('(company "Cryocooler Controller")',
                        '(company "OEM controller - patent transcription")')


def main():
    only = set(sys.argv[1:])
    kicadgen.reset_uuids()
    specs = load_specs(only)
    oemsch.write_library([spec for _, spec in specs])
    globals_ = global_nets(specs)

    root = kicadgen.Sheet('OEM controller (patent schematics)', f'{PROJECT}.kicad_sch', 'A4')
    root.uid = ROOT_UUID
    root.path = '/' + ROOT_UUID
    root.note('Transcribed from the STI patents. One sheet per patent PDF that contains\n'
              'electrical schematics; one page per figure. See ../TRANSCRIPTION_NOTES.md.',
              20, 30, 2)
    sheets_out, project_sheets = [], [[ROOT_UUID, 'Root']]
    page = 2
    for p_index, (title, stem, names) in enumerate(PATENTS):
        patent = kicadgen.Sheet(title, f'{stem}.kicad_sch', 'A3')
        patent.uid = kicadgen.stable_uuid('sheet/' + stem)
        patent.path = f'/{ROOT_UUID}/{patent.uid}'
        root.sheet_symbols.append(oemsch.sheet_block(
            '/' + ROOT_UUID, patent, f'sheets/{stem}.kicad_sch', page, 30.48, 60.96 + 20 * p_index, PROJECT))
        project_sheets.append([patent.uid, title])
        page += 1
        patent.note(f'{title}: FIGS. 5A-5H = mother board, FIGS. 6A-6C = daughter board\n'
                    '(US6098409 col. 3). Each child sheet is one figure.', 20, 25, 2)
        children = [(s_stem, spec) for s_stem, spec in specs if s_stem == stem]
        column_y = [40 * 1.27] * 3  # next free y in each column of blocks
        pin_joins = {net: [] for net in redrawn_only(specs)}
        for index, (_, spec) in enumerate(children):
            name = spec.__name__.split('.')[-1]
            child = kicadgen.Sheet(spec.TITLE, f'{stem}_{name}.kicad_sch', getattr(spec, 'PAPER', 'A2'))
            child.uid = kicadgen.stable_uuid(f'sheet/{stem}/{name}')
            child.path = f'{patent.path}/{child.uid}'
            joined = ''.join(f'\nNet joined across figures: printed "{net}" = {ALIASES[net]}'
                             for net in spec._aliases)
            child.note(f'{spec.TITLE}\nSource: {spec.SOURCE}{joined}', 15, 18, 2.5)
            column = index % 3
            redrawn = getattr(spec, 'REDRAWN', False)
            figure = SimpleNamespace(PORTS=spec.PORTS, WIDTH=60.96) if redrawn else None
            height = oemsch.block_geometry(figure)[1] if redrawn else 10.16
            # blocks stack down each column by their height, on the 1.27 mm grid
            x, y = 20 * 1.27 + column * 103 * 1.27, column_y[column]
            column_y[column] = y + 1.27 * math.ceil((height + 20.32) / 1.27)
            project_sheets.append([child.uid, spec.TITLE])
            figure_page = page
            page += 1
            sheets_out.append(child)
            if not redrawn:
                oemsch.build_sheet(child, spec, globals_)
                patent.sheet_symbols.append(oemsch.sheet_block(
                    patent.path, child, f'{stem}_{name}.kicad_sch', figure_page, x, y, PROJECT))
                continue
            page = build_redrawn(child, spec, stem, name, globals_, page, project_sheets, sheets_out)
            text, ends = oemsch.sheet_block_pins(patent.path, child, f'{stem}_{name}.kicad_sch',
                                                 figure_page, x, y, PROJECT, figure)
            patent.sheet_symbols.append(text)
            bridge_to_globals(patent, ends, globals_, pin_joins)
        join_figures(patent, pin_joins)
        sheets_out.append(patent)

    (OUT_DIR / 'sheets').mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f'{PROJECT}.kicad_sch').write_text(render(root))
    for sheet in sheets_out:
        (OUT_DIR / 'sheets' / sheet.filename).write_text(render(sheet))
    (OUT_DIR / f'{PROJECT}.kicad_pro').write_text(json.dumps(
        {'meta': {'filename': f'{PROJECT}.kicad_pro', 'version': 3}, 'sheets': project_sheets},
        indent=2) + '\n')
    (OUT_DIR / 'sym-lib-table').write_text(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "oem_patent")(type "KiCad")'
        '(uri "${KIPRJMOD}/lib/oem_patent.kicad_sym")(options "")(descr "Patent transcription symbols"))\n)\n')
    print(f'wrote {len(sheets_out) + 1} sheets, {len(globals_)} global nets')


if __name__ == '__main__':
    main()
