"""
@file oemsch.py
@brief Spec-driven KiCad writer for the patent schematic transcriptions.

Reuses the project's KiCad writer (hardware/kicad/tools/kicadgen.py) by import
only; nothing there is edited. Project-specific bits (project name, custom
library, uuid namespace) are overridden here.

A figure is described by a spec module (kicad/specs/*.py) as a list of parts
with positions and pin->net maps. Every connected pin gets a short wire stub
ending in a net label, a global label (cross-page signals) or a power symbol,
so the netlist is exact without hand-routing wires.
"""

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KICAD_DIR = HERE.parent
REPO = KICAD_DIR.parents[2]
sys.path.insert(0, str(REPO / 'hardware' / 'kicad' / 'tools'))

import kicadgen  # noqa: E402
from sexpr import load_library, resolve  # noqa: E402

LIB_NAME = 'oem_patent'
LIB_PATH = KICAD_DIR / 'lib' / f'{LIB_NAME}.kicad_sym'
CELL = 1.27

# ─── kicadgen overrides ───
kicadgen.PROJECT = 'oem-controller'
_original_stable_uuid = kicadgen.stable_uuid
_custom_lib = {}


def _stable_uuid(name):
    return _original_stable_uuid('oem-controller/' + name)


def _get_symbol(lib_id):
    lib, name = lib_id.split(':', 1)
    if lib == LIB_NAME:
        if not _custom_lib:
            _custom_lib.update(load_library(sys.modules[__name__].LIB_PATH))
        return resolve(_custom_lib, name)
    return kicadgen.stock_symbol(lib, name)


_original_q = kicadgen.q


def _quote(text):
    # KiCad stores line breaks in strings as \n escapes, not raw newlines
    return _original_q(text).replace('\n', '\\n')


kicadgen.Sheet.PAPER.setdefault('A1', (841, 594))
kicadgen.Sheet.PAPER.setdefault('A0', (1189, 841))
kicadgen.stable_uuid = _stable_uuid
kicadgen.get_symbol = _get_symbol
kicadgen.q = _quote

# ─── Discrete kinds → stock symbols ───
KINDS = {
    'R': ('Device:R_US', 'R'),
    'C': ('Device:C', 'C'),
    'CP': ('Device:C_Polarized', 'C'),
    'D': ('Device:D', 'CR'),
    'DZ': ('Device:D_Zener', 'CR'),
    'LED': ('Device:LED', 'CR'),
    'L': ('Device:L', 'L'),
    'POT': ('Device:R_Potentiometer_US', 'R'),
    'THERM': ('Device:Thermistor', 'RT'),
    'FUSE': ('Device:Fuse', 'F'),
    'NPN': ('Device:Q_NPN', 'Q'),
    'NMOS': ('Device:Q_NMOS', 'Q'),
    'TP': ('Connector:TestPoint', 'TP'),
}

# Net name → stock power symbol. Anything else becomes a label.
POWER = {
    'GND': 'GND', '+5V': '+5V', '+5VA': '+5VA', '+15V': '+15V', '-15V': '-15V',
    '+12V': '+12V', '-12V': '-12V', '-5V': '-5V', '+10V': '+10V', '-10V': '-10V',
    '+28V': '+28V', '+48V': '+48V', 'GNDA': 'GNDA', 'EARTH': 'Earth',
}
NEGATIVE = {'GND', 'GNDA', 'EARTH', '-15V', '-12V', '-5V', '-10V'}


def P(ref, value, kind, at, rot=0, mirror=False, pins=None, printed=None,
      probable=None, datasheet=None, note=None, pinmap=None):
    """
    Describe one part.

    @param ref       Unique reference used in KiCad (suffix duplicates, e.g. R229B).
    @param value     Value/part number exactly as printed ('?' if illegible).
    @param kind      Key of KINDS, 'OPAMP', 'CONN', or a custom SYMBOLS name.
    @param at        (column, row) grid cells (1 cell = 1.27 mm) of the symbol origin.
    @param rot       Rotation in degrees (0/90/180/270).
    @param pins      {pin number: net}; use 'NC' for a drawn no-connect.
    @param printed   Reference as printed when it differs from `ref`.
    @param probable  Probable real part (identification guess; never replaces value).
    @param pinmap    OPAMP only: {'+','-','out','v+','v-'} -> printed pin numbers.
    @returns dict consumed by build_sheet().
    """
    return dict(ref=ref, value=value, kind=kind, at=at, rot=rot, mirror=mirror,
                pins=pins or {}, printed=printed, probable=probable,
                datasheet=datasheet, note=note, pinmap=pinmap)


# ─── Custom symbol library ───

def _pin(number, name, x, y, angle, length=2.54):
    return (f'\t\t\t(pin passive line (at {x:g} {y:g} {angle}) (length {length:g})\n'
            f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{number}" (effects (font (size 1.27 1.27))))\n\t\t\t)\n')


def _symbol(name, ref_prefix, graphics, pin_text, hide_names=False, value=None):
    names = '(pin_names (offset 1.016) (hide yes))' if hide_names else '(pin_names (offset 1.016))'
    return (f'\t(symbol "{name}"\n\t\t{names}\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
            f'\t\t(on_board yes)\n\t\t(in_pos_files yes)\n\t\t(duplicate_pin_numbers_are_jumpers no)\n'
            f'\t\t(property "Reference" "{ref_prefix}" (at 0 1.27 0) (show_name no) (do_not_autoplace no) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(property "Value" "{value or name}" (at 0 -1.27 0) (show_name no) (do_not_autoplace no) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(property "Footprint" "" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(property "Datasheet" "" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(property "Description" "Patent transcription symbol (pins as printed)" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(symbol "{name}_0_1"\n{graphics}\t\t)\n'
            f'\t\t(symbol "{name}_1_1"\n{pin_text}\t\t)\n'
            f'\t\t(embedded_fonts no)\n\t)\n')


def box_symbol(name, spec):
    """Rectangle IC. spec: left/right/top/bottom lists of (number, name) or None gaps."""
    left, right = spec.get('left', []), spec.get('right', [])
    top, bottom = spec.get('top', []), spec.get('bottom', [])
    rows = max(len(left), len(right), 1)
    half_h = 2.54 * math.ceil((rows + 1) / 2)
    longest = max([len(p[1]) for p in left + right if p] + [1])
    across = max(len(top), len(bottom))
    width = max(10.16, 2.54 * math.ceil((2 * longest * 0.9 + 5) / 2.54), 2.54 * (across + 1))
    width = 2.54 * math.ceil(width / 2.54 / 2) * 2
    half_w = width / 2
    graphics = (f'\t\t\t(rectangle (start {-half_w:g} {half_h:g}) (end {half_w:g} {-half_h:g}) '
                '(stroke (width 0.254) (type default)) (fill (type background)))\n')
    text = ''
    for index, entry in enumerate(left):
        if entry:
            text += _pin(entry[0], entry[1], -half_w - 2.54, half_h - 2.54 * (index + 1), 0)
    for index, entry in enumerate(right):
        if entry:
            text += _pin(entry[0], entry[1], half_w + 2.54, half_h - 2.54 * (index + 1), 180)
    for side, y, angle in ((top, half_h + 2.54, 270), (bottom, -half_h - 2.54, 90)):
        start = -2.54 * (len(side) - 1) / 2
        for index, entry in enumerate(side):
            if entry:
                text += _pin(entry[0], entry[1], round((start + 2.54 * index) / 1.27) * 1.27, y, angle)
    return _symbol(name, spec.get('prefix', 'U'), graphics, text)


def opamp_symbol(name, pinmap):
    """Triangle op-amp/comparator; pinmap {'+','-','out','v+','v-'} -> numbers."""
    graphics = ('\t\t\t(polyline (pts (xy -5.08 5.08) (xy 5.08 0) (xy -5.08 -5.08) (xy -5.08 5.08)) '
                '(stroke (width 0.254) (type default)) (fill (type background)))\n')
    text = ''
    if '-' in pinmap:
        text += _pin(pinmap['-'], '-', -7.62, 2.54, 0)
    if '+' in pinmap:
        text += _pin(pinmap['+'], '+', -7.62, -2.54, 0)
    if 'out' in pinmap:
        text += _pin(pinmap['out'], '~', 7.62, 0, 180)
    if 'v+' in pinmap:
        text += _pin(pinmap['v+'], 'V+', -2.54, 6.35, 270)
    if 'v-' in pinmap:
        text += _pin(pinmap['v-'], 'V-', -2.54, -6.35, 90)
    return _symbol(name, 'U', graphics, text)


def conn_symbol(count):
    """Single-row connector, pin 1 at top, pins on the left."""
    spec = {'left': [(str(n), str(n)) for n in range(1, count + 1)], 'prefix': 'J'}
    return box_symbol(f'CONN_{count}', spec)


def opamp_name(pinmap):
    order = ('-', '+', 'out', 'v+', 'v-')
    return 'OPAMP_' + '_'.join(pinmap.get(key, 'x') for key in order)


def write_library(specs):
    """Collect every custom symbol the specs need and write the .kicad_sym."""
    symbols = {}
    for spec in specs:
        for name, body in getattr(spec, 'SYMBOLS', {}).items():
            text = box_symbol(name, body)
            assert symbols.get(name, text) == text, f'symbol {name} defined twice differently'
            symbols[name] = text
        for part in spec.PARTS:
            if part['kind'] == 'OPAMP':
                name = opamp_name(part['pinmap'])
                symbols[name] = opamp_symbol(name, part['pinmap'])
            elif part['kind'].startswith('CONN'):
                count = int(part['kind'].split('_')[1])
                symbols[f'CONN_{count}'] = conn_symbol(count)
    lib_path = sys.modules[__name__].LIB_PATH
    lib_path.parent.mkdir(parents=True, exist_ok=True)
    lib_path.write_text('(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "oem_patent_gen")\n'
                        '\t(generator_version "1.0")\n' + ''.join(symbols[k] for k in sorted(symbols))
                        + ')\n')
    _custom_lib.clear()


# ─── Sheet building ───

def lib_id_for(part):
    kind = part['kind']
    if kind in KINDS:
        return KINDS[kind][0]
    if kind == 'OPAMP':
        return f'{LIB_NAME}:{opamp_name(part["pinmap"])}'
    return f'{LIB_NAME}:{kind}'


def _direction(angle):
    """Unit step (dx, dy) in sheet coords (y down) for a math-convention angle."""
    radians = math.radians(angle)
    return round(math.cos(radians)), -round(math.sin(radians))


def _wired_groups(spec, placed_by_ref):
    """
    Resolve spec.WIRES ('REF.PIN', 'REF.PIN'[, 'hv'|'vh']) into pin groups.

    Returns ({(ref, pin): group id}, [(a, b, order)]) and checks that both ends of
    every wire sit on the same net.
    """
    parent = {}

    def find(key):
        while parent.setdefault(key, key) != key:
            key = parent[key]
        return key

    wires = []
    for entry in getattr(spec, 'WIRES', []):
        a, b = (tuple(end.rsplit('.', 1)) for end in entry[:2])
        order = entry[2] if len(entry) > 2 else 'hv'
        net_a = placed_by_ref[a[0]][1]['pins'][a[1]]
        net_b = placed_by_ref[b[0]][1]['pins'][b[1]]
        assert net_a == net_b, f'{spec.__name__}: wire {entry} joins {net_a} and {net_b}'
        parent[find(a)] = find(b)
        wires.append((a, b, order))
    return {key: find(key) for key in parent}, wires


def _net_only_in_group(net, group, stub_end, groups):
    """True when every pin of `net` on this page is in the wired group (no label needed)."""
    return all(groups.get(key) == group for key, (_, _, other) in stub_end.items() if other == net)


def build_sheet(sheet, spec, globals_):
    """Place the spec's parts on `sheet` and attach stubs, wires, labels and power symbols."""
    sheet.handwired = True
    placed_by_ref = {}
    stub_end = {}
    for part in spec.PARTS:
        col, row = part['at']
        placed = sheet.add(lib_id_for(part), part['ref'], part['value'], col * CELL, row * CELL,
                           rot=part['rot'], mirror=part['mirror'], auto=False)
        props = {}
        if part['printed'] and part['printed'] != part['ref']:
            props['Printed_Ref'] = part['printed']
        if part['probable']:
            props['Probable_Part'] = part['probable']
        if part['note']:
            props['Note'] = part['note']
        placed.props = props
        if part['datasheet']:
            placed.props['Datasheet'] = part['datasheet']
        part['pins'] = {str(k): v for k, v in part['pins'].items()}
        assert part['ref'] not in placed_by_ref, f'{spec.__name__}: duplicate ref {part["ref"]}'
        placed_by_ref[part['ref']] = (placed, part)
        for number, net in part['pins'].items():
            assert number in placed.pin_table, f'{spec.__name__}: {part["ref"]} has no pin {number}'
            x, y = placed.pin_point(number)
            if net == 'NC':
                sheet.no_connects.append((x, y))
                continue
            dx, dy = _direction(placed.pin_out_angle(number))
            end = (x + dx * 2 * CELL, y + dy * 2 * CELL)
            sheet.wires.append(((x, y), end))
            stub_end[(part['ref'], number)] = (end, (dx, dy), net)

    groups, wires = _wired_groups(spec, placed_by_ref)
    for a, b, order in wires:
        (ax, ay), (bx, by) = stub_end[a][0], stub_end[b][0]
        corner = (bx, ay) if order == 'hv' else (ax, by)
        for start, stop in (((ax, ay), corner), (corner, (bx, by))):
            if start != stop:
                sheet.wires.append((start, stop))

    # Every pin gets a label/power symbol unless it is wired to a pin that already has one.
    labelled_groups = set()
    for key, (end, (dx, dy), net) in stub_end.items():
        group = groups.get(key)
        if group is not None:
            if group in labelled_groups:
                continue
            labelled_groups.add(group)
        if net in POWER:
            kicadgen._pwr_counter[0] += 1
            symbol = sheet.add(f'power:{POWER[net]}', f'#PWR{kicadgen._pwr_counter[0]:03d}', net,
                               end[0], end[1], auto=False)
            symbol.is_power = True
            continue
        if group is not None and _net_only_in_group(net, group, stub_end, groups) and net not in globals_:
            continue
        angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
        kind = 'global_label' if net in globals_ else 'label'
        sheet.labels.append((kind, net, end, angle))
    for text, col, row in getattr(spec, 'NOTES', []):
        sheet.note(text, col * CELL, row * CELL, 1.5)


def sheet_block(parent_path_uuid, child, file_ref, page, x, y, project):
    """Hierarchical sheet symbol text for a parent sheet."""
    width, height = 60.96, 10.16
    return (
        f'\t(sheet (at {x:g} {y:g}) (size {width:g} {height:g}) (exclude_from_sim no) '
        f'(in_bom yes) (on_board yes) (dnp no) (fields_autoplaced yes) '
        f'(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0)) (uuid "{child.uid}")\n'
        f'\t\t(property "Sheetname" "{child.title}" (at {x:g} {y - 0.7:g} 0) (show_name no) '
        f'(do_not_autoplace no) (effects (font (size 1.27 1.27)) (justify left bottom)))\n'
        f'\t\t(property "Sheetfile" "{file_ref}" (at {x:g} {y + height + 0.6:g} 0) (show_name no) '
        f'(do_not_autoplace no) (effects (font (size 1.27 1.27)) (justify left top)))\n'
        f'\t\t(instances (project "{project}" (path "{parent_path_uuid}" (page "{page}"))))\n\t)'
    )
