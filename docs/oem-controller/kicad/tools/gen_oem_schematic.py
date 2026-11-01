"""
@file gen_oem_schematic.py
@brief Build the OEM controller KiCad project from the figure specs.

Hierarchy: root -> one sheet per patent PDF with schematics -> one page per figure.
Run: python3 -I docs/oem-controller/kicad/tools/gen_oem_schematic.py [spec ...]
(no arguments = every spec in SPECS).
"""

import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import os  # noqa: E402

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
            specs.append((stem, importlib.import_module(f'specs.{name}')))
    # Refs are made unique among the specs being built (all of them for the real build).
    make_refs_unique([spec for _, spec in specs])
    return specs


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
        patent = kicadgen.Sheet(title, f'{stem}.kicad_sch', 'A4')
        patent.uid = kicadgen.stable_uuid('sheet/' + stem)
        patent.path = f'/{ROOT_UUID}/{patent.uid}'
        root.sheet_symbols.append(oemsch.sheet_block(
            '/' + ROOT_UUID, patent, f'sheets/{stem}.kicad_sch', page, 30.48, 60.96 + 20 * p_index, PROJECT))
        project_sheets.append([patent.uid, title])
        page += 1
        patent.note(f'{title}: FIGS. 5A-5H = mother board, FIGS. 6A-6C = daughter board\n'
                    '(US6098409 col. 3). Each child sheet is one figure.', 20, 25, 2)
        children = [(s_stem, spec) for s_stem, spec in specs if s_stem == stem]
        for index, (_, spec) in enumerate(children):
            name = spec.__name__.split('.')[-1]
            child = kicadgen.Sheet(spec.TITLE, f'{stem}_{name}.kicad_sch', getattr(spec, 'PAPER', 'A2'))
            child.uid = kicadgen.stable_uuid(f'sheet/{stem}/{name}')
            child.path = f'{patent.path}/{child.uid}'
            oemsch.build_sheet(child, spec, globals_)
            child.note(f'{spec.TITLE}\nSource: {spec.SOURCE}', 15, 18, 2.5)
            column, row = index % 3, index // 3
            patent.sheet_symbols.append(oemsch.sheet_block(
                patent.path, child, f'{stem}_{name}.kicad_sch', page,
                20 + column * 70, 50 + row * 25, PROJECT))
            project_sheets.append([child.uid, spec.TITLE])
            page += 1
            sheets_out.append(child)
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
