"""Tiny KiCad 10 schematic writer: parts, wire stubs, labels, power symbols, hierarchical sheets."""
import math
import uuid
from collections import Counter
from pathlib import Path

from sexpr import find_all, pins, resolve, stock_symbol, sval, load_library, dump, parse

PROJECT = 'cryocooler'
VERSION = '20260306'
CUSTOM_LIB_PATH = Path(__file__).resolve().parent.parent / 'lib' / 'cryocooler.kicad_sym'

_ref_counters = Counter()
_pwr_counter = [0]
_custom = {}


_uuid_counter = [0]


def reset_uuids():
    """Restart the deterministic uuid sequence so regenerating gives identical files."""
    _uuid_counter[0] = 0


def new_uuid():
    _uuid_counter[0] += 1
    return stable_uuid(f'item/{_uuid_counter[0]}')


def stable_uuid(name):
    """Name-based uuid so ids do not change between runs."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'cryocooler-schematic/{name}'))


def kicad_format(text):
    """Re-serialize s-expression text the way KiCad writes it: any list with sub-lists is split over lines."""
    def render_node(node, depth):
        if isinstance(node, tuple):
            return '"' + node[1] + '"'
        if isinstance(node, str):
            return node
        if not any(isinstance(child, list) for child in node):
            return '(' + ' '.join(render_node(child, depth) for child in node) + ')'
        head = []
        for child in node:
            if isinstance(child, list):
                break
            head.append(render_node(child, depth))
        out = '(' + ' '.join(head)
        children = node[len(head):]
        if node and node[0] == 'pts':
            # KiCad keeps all points of a pts list on one line
            out += '\n' + '\t' * (depth + 1) + ' '.join(render_node(child, depth + 1) for child in children)
        else:
            for child in children:
                out += '\n' + '\t' * (depth + 1) + render_node(child, depth + 1)
        return out + '\n' + '\t' * depth + ')'
    tree = parse(text)
    if tree and tree[0] == 'kicad_sch':
        tree = sort_schematic_items(tree)
    return render_node(tree, 0) + '\n'


ITEM_ORDER = ['text', 'junction', 'no_connect', 'wire', 'label', 'global_label', 'symbol', 'sheet',
              'sheet_instances', 'embedded_fonts']


def sort_schematic_items(tree):
    """Order schematic items like KiCad: by item type, then by uuid."""
    def uuid_of(item):
        for child in item:
            if isinstance(child, list) and child and child[0] == 'uuid':
                return sval(child[1])
        return ''
    head = [item for item in tree if not (isinstance(item, list) and item and item[0] in ITEM_ORDER)]
    items = [item for item in tree if isinstance(item, list) and item and item[0] in ITEM_ORDER]
    items.sort(key=lambda item: (ITEM_ORDER.index(item[0]), uuid_of(item)))
    return head + items


def q(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"') + '"'


def fmt(value):
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return text if text != '-0' else '0'


def next_ref(prefix):
    _ref_counters[prefix] += 1
    return f'{prefix}{_ref_counters[prefix]}'


def get_symbol(lib_id):
    """Returns the flattened symbol node for 'Lib:Name' (stock lib, or the project 'cryocooler' lib)."""
    lib, name = lib_id.split(':', 1)
    if lib == 'cryocooler':
        if not _custom:
            _custom.update(load_library(CUSTOM_LIB_PATH))
        return resolve(_custom, name)
    return stock_symbol(lib, name)


def symbol_prop(symbol, key):
    for prop in find_all(symbol, 'property'):
        if sval(prop[1]) == key:
            return sval(prop[2])
    return ''


def embed_symbol(lib_id):
    """Returns serialized text of the symbol renamed to lib_id for a sheet's lib_symbols block."""
    symbol = get_symbol(lib_id)
    short = sval(symbol[1])
    node = [symbol[0], ('s', lib_id)] + symbol[2:]
    if not find_all(node, 'embedded_fonts'):
        node.append(['embedded_fonts', 'no'])
    return '\t\t' + dump(node, 2)


def unit_pins(symbol, unit):
    """Pins that belong to the given unit (unit 0 shared pins are always included)."""
    result = []
    for sub in find_all(symbol, 'symbol'):
        parts = sval(sub[1]).rsplit('_', 2)
        sub_unit = int(parts[-2])
        if sub_unit not in (0, unit):
            continue
        result.extend(pins(['symbol', sub[1]] + sub[2:]))
    if not find_all(symbol, 'symbol'):
        result = pins(symbol)
    return result


def symbol_extent(symbol, unit, with_pins=True):
    """Bounding box (x0, y0, x1, y1) of a symbol's body graphics and pins in symbol coordinates."""
    xs, ys = [], []

    def add(x, y):
        xs.append(float(x))
        ys.append(float(y))

    for sub in find_all(symbol, 'symbol') or [symbol]:
        if sub is not symbol:
            sub_unit = int(sval(sub[1]).rsplit('_', 2)[-2])
            if sub_unit not in (0, unit):
                continue
        for item in sub:
            if not (isinstance(item, list) and item):
                continue
            kind = item[0]
            if kind == 'rectangle':
                for key in ('start', 'end'):
                    point = find_all(item, key)[0]
                    add(point[1], point[2])
            elif kind == 'polyline':
                for xy in find_all(find_all(item, 'pts')[0], 'xy'):
                    add(xy[1], xy[2])
            elif kind == 'circle':
                center = find_all(item, 'center')[0]
                radius = float(find_all(item, 'radius')[0][1])
                add(float(center[1]) - radius, float(center[2]) - radius)
                add(float(center[1]) + radius, float(center[2]) + radius)
            elif kind == 'arc':
                for key in ('start', 'mid', 'end'):
                    point = find_all(item, key)[0]
                    add(point[1], point[2])
            elif kind == 'pin' and with_pins:
                at = find_all(item, 'at')[0]
                add(at[1], at[2])
    if not xs:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


class Part:
    """A placed symbol; exposes pin connection points in sheet coordinates."""

    def __init__(self, sheet, lib_id, ref, value, x, y, rot=0, mirror=False, unit=1,
                 footprint=None, props=None, auto=False, near=None):
        self.sheet = sheet
        self.lib_id = lib_id
        self.ref = ref
        self.value = value
        self.x = x
        self.y = y
        self.rot = rot
        self.mirror = mirror
        self.unit = unit
        self.footprint = footprint
        self.props = props or {}
        self.auto = auto
        self.near = near
        self.uid = new_uuid()
        symbol = get_symbol(lib_id)
        self.extent = symbol_extent(symbol, unit)
        self.body_extent = symbol_extent(symbol, unit, with_pins=False)
        self.pin_table = {}
        for number, name, px, py, angle, length, ptype in unit_pins(symbol, unit):
            self.pin_table.setdefault(number, []).append((name, px, py, angle))

    def _to_sheet(self, px, py, x=None, y=None, rot=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        rot = self.rot if rot is None else rot
        if self.mirror:
            px = -px
        for _ in range(int(rot // 90) % 4):
            px, py = -py, px
        return (x + px, y - py)

    def pin_point(self, number, x=None, y=None, rot=None):
        name, px, py, angle = self.pin_table[number][0]
        return self._to_sheet(px, py, x, y, rot)

    def pin_out_angle(self, number, rot=None):
        """Direction (degrees, math convention, y up) a wire stub should leave the pin."""
        rot = self.rot if rot is None else rot
        name, px, py, angle = self.pin_table[number][0]
        out = (angle + 180) % 360
        if self.mirror:
            out = (180 - out) % 360
        return (out + rot) % 360

    def pin_name(self, number):
        return self.pin_table[number][0][0]

    def bbox(self, x=None, y=None, rot=None):
        """Body bounding box in sheet coordinates (x0, y0, x1, y1)."""
        x0, y0, x1, y1 = self.extent
        corners = [self._to_sheet(px, py, x, y, rot) for px in (x0, x1) for py in (y0, y1)]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return (min(xs), min(ys), max(xs), max(ys))


# Global-label direction seen from the ESP32 (root) sheet: 'out' = root drives the net, 'in' = root reads it.
LABEL_DIRECTION = {
    'SPI_MOSI': 'out', 'SPI_SCK': 'out', 'IMU_CS': 'out', 'MCP4921_CS': 'out', 'AD9833_FSYNC': 'out',
    'AMP_REM_EN': 'out', 'PWR_KILL': 'out', 'ACS_SCK': 'out', 'ACS_MOSI': 'out', 'ACS_CS': 'out',
    'LED_FAULT': 'out', 'LED_READY': 'out', 'STATUS_RGB': 'out',
    'SPI_MISO': 'in', 'ACS_MISO': 'in', 'IMU_INT1': 'in', 'IMU_INT2': 'in', 'FLOW_TACH': 'in',
    'FAN_ALERT': 'in', 'PWR_INT': 'in', 'NTC_ADC': 'in',
}


def label_shape(net, is_root, filename):
    """KiCad global-label shape for a net on a given sheet (bidirectional when the direction is not fixed)."""
    if net == 'SIG_SINE':
        return {'signal_gen.kicad_sch': 'output', 'amp_control.kicad_sch': 'input'}.get(filename, 'bidirectional')
    direction = LABEL_DIRECTION.get(net)
    if direction is None:
        return 'bidirectional'
    drives = (direction == 'out') == is_root
    return 'output' if drives else 'input'


def merge_overlapping_wires(wires):
    """Union collinear wires that share more than a point, so no wire ends in the middle of another."""
    horizontal, vertical, merged = {}, {}, []
    for (x1, y1), (x2, y2) in wires:
        if abs(y1 - y2) < 1e-6:
            horizontal.setdefault(round(y1, 4), []).append(sorted((x1, x2)))
        elif abs(x1 - x2) < 1e-6:
            vertical.setdefault(round(x1, 4), []).append(sorted((y1, y2)))
        else:
            merged.append(((x1, y1), (x2, y2)))
    for fixed, spans in horizontal.items():
        for start, end in union_spans(spans):
            merged.append(((start, fixed), (end, fixed)))
    for fixed, spans in vertical.items():
        for start, end in union_spans(spans):
            merged.append(((fixed, start), (fixed, end)))
    return merged


def t_junctions(wires):
    """Points where a wire end lands in the interior of another wire."""
    found = []
    for index, (start, end) in enumerate(wires):
        for point in (start, end):
            for other_index, ((x1, y1), (x2, y2)) in enumerate(wires):
                if other_index == index:
                    continue
                horizontal = abs(y1 - y2) < 1e-6 and abs(point[1] - y1) < 1e-6
                vertical = abs(x1 - x2) < 1e-6 and abs(point[0] - x1) < 1e-6
                low, high = (min(x1, x2), max(x1, x2)) if horizontal else (min(y1, y2), max(y1, y2))
                value = point[0] if horizontal else point[1]
                if (horizontal or vertical) and low + 1e-6 < value < high - 1e-6:
                    found.append(point)
    return found


def split_wires_at(wires, points):
    """Split axis-aligned wires wherever one of the points lies strictly inside them."""
    result = []
    for (x1, y1), (x2, y2) in wires:
        horizontal = abs(y1 - y2) < 1e-6
        vertical = abs(x1 - x2) < 1e-6
        cuts = []
        for px, py in points:
            if horizontal and abs(py - y1) < 1e-6 and min(x1, x2) + 1e-6 < px < max(x1, x2) - 1e-6:
                cuts.append(px)
            if vertical and abs(px - x1) < 1e-6 and min(y1, y2) + 1e-6 < py < max(y1, y2) - 1e-6:
                cuts.append(py)
        if not cuts:
            result.append(((x1, y1), (x2, y2)))
            continue
        ends = sorted({round(v, 4) for v in cuts + ([x1, x2] if horizontal else [y1, y2])})
        for first, second in zip(ends, ends[1:]):
            if horizontal:
                result.append(((first, y1), (second, y1)))
            else:
                result.append(((x1, first), (x1, second)))
    return result


def connection_counts(wires, pins):
    """Number of wire ends and pins meeting at each point (a wire passing straight through counts as two)."""
    counts = {}
    for start, end in wires:
        for point in (start, end):
            key = (round(point[0], 2), round(point[1], 2))
            counts[key] = counts.get(key, 0) + 1
    for point in pins:
        key = (round(point[0], 2), round(point[1], 2))
        counts[key] = counts.get(key, 0) + 1
    return counts


def distinct_pins(parts):
    """Pin points of all parts; stacked pins of one part count once."""
    return list({(id(p), round(p.pin_point(n)[0], 2), round(p.pin_point(n)[1], 2)): p.pin_point(n)
                 for p in parts if not p.ref.startswith('#') for n in p.pin_table}.values())


def point_inside_wire(point, wire):
    """True when the point lies strictly inside an axis-aligned wire."""
    (x1, y1), (x2, y2) = wire
    if abs(y1 - y2) < 1e-6 and abs(point[1] - y1) < 1e-6:
        return min(x1, x2) + 1e-6 < point[0] < max(x1, x2) - 1e-6
    if abs(x1 - x2) < 1e-6 and abs(point[0] - x1) < 1e-6:
        return min(y1, y2) + 1e-6 < point[1] < max(y1, y2) - 1e-6
    return False


def merge_touching_wires(wires, keep):
    """Join collinear wires that only touch end to end when nothing else connects at the joint."""
    keep_points = {(round(x, 2), round(y, 2)) for x, y in keep}
    ends = {}
    for start, end in wires:
        for point in (start, end):
            key = (round(point[0], 2), round(point[1], 2))
            ends[key] = ends.get(key, 0) + 1
    result = list(wires)
    changed = True
    while changed:
        changed = False
        for index, ((x1, y1), (x2, y2)) in enumerate(result):
            for other_index in range(index + 1, len(result)):
                (u1, v1), (u2, v2) = result[other_index]
                for joint_a, far_a, joint_b, far_b in (((x2, y2), (x1, y1), (u1, v1), (u2, v2)),
                                                       ((x1, y1), (x2, y2), (u1, v1), (u2, v2)),
                                                       ((x2, y2), (x1, y1), (u2, v2), (u1, v1)),
                                                       ((x1, y1), (x2, y2), (u2, v2), (u1, v1))):
                    key = (round(joint_a[0], 2), round(joint_a[1], 2))
                    if key != (round(joint_b[0], 2), round(joint_b[1], 2)):
                        continue
                    collinear = (abs(far_a[0] - joint_a[0]) < 1e-6 and abs(far_b[0] - joint_a[0]) < 1e-6) or \
                                (abs(far_a[1] - joint_a[1]) < 1e-6 and abs(far_b[1] - joint_a[1]) < 1e-6)
                    opposite = (far_a[0] - joint_a[0]) * (far_b[0] - joint_a[0]) <= 0 and \
                               (far_a[1] - joint_a[1]) * (far_b[1] - joint_a[1]) <= 0
                    crossed = any(point_inside_wire(joint_a, wire) for wire in result)
                    if collinear and opposite and key not in keep_points and ends.get(key, 0) == 2 and not crossed:
                        result[index] = (far_a, far_b)
                        del result[other_index]
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    return result


def meeting_points(wires, pins):
    """Points that need a junction dot: wire ends plus real part pins (not power symbols) totalling three."""
    counts = {}
    for start, end in wires:
        for point in (start, end):
            key = (round(point[0], 2), round(point[1], 2))
            counts[key] = counts.get(key, 0) + 1
    for point in pins:
        key = (round(point[0], 2), round(point[1], 2))
        counts[key] = counts.get(key, 0) + 1
    return [point for point, count in counts.items() if count >= 3]


def union_spans(spans):
    result = []
    for start, end in sorted(spans):
        if result and start < result[-1][1] - 1e-6:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


class Sheet:
    PAPER = {'A4': (297, 210), 'A3': (420, 297), 'A2': (594, 420)}

    def __init__(self, title, filename, paper='A3'):
        self.title = title
        self.filename = filename
        self.paper = paper
        self.uid = new_uuid()
        self.parts = []
        self.wires = []
        self.labels = []
        self.no_connects = []
        self.junctions = []
        self.text_items = []
        self.sheet_symbols = []
        self.used_libs = []
        self.conns = []
        self.ncs = []
        self.path = ''
        self.finalized = False
        self.handwired = False
        self.screen_uid = new_uuid()   # a sheet file's own uuid differs from its sheet block's uuid

    @staticmethod
    def snap(value):
        return round(value / 1.27) * 1.27

    # ── placement ────────────────────────────────────────────────────────
    def add(self, lib_id, ref, value, x, y, **kwargs):
        if kwargs.get('auto') is None:
            kwargs['auto'] = lib_id in AUTO_LIBS or lib_id.startswith('Device:D')
        part = Part(self, lib_id, ref, value, self.snap(x), self.snap(y), **kwargs)
        self.parts.append(part)
        if lib_id not in self.used_libs:
            self.used_libs.append(lib_id)
        return part

    def connect(self, part, number, net, glob=False):
        """Record a pin->net connection; wires/labels/power symbols are generated at finalize."""
        self.conns.append((part, number, net, glob))

    def nc(self, part, number):
        self.ncs.append((part, number))

    def flag(self, net, near=None):
        """PWR_FLAG on a net (auto-placed next to the net's pins)."""
        _pwr_counter[0] += 1
        part = self.add('power:PWR_FLAG', f'#FLG{_pwr_counter[0]:03d}', 'PWR_FLAG', 0, 0, auto=True, near=near)
        self.connect(part, '1', net)
        return part

    def note(self, text, x, y, size=1.8):
        self.text_items.append((text, x, y, size))

    def finalize(self):
        if self.finalized:
            return
        self.finalized = True
        import layout
        layout.finalize(self)

    # ── serialization ────────────────────────────────────────────────────
    def _effects(self, size=1.27, justify=None):
        out = f'(effects (font (size {size} {size}))'
        if justify and justify != 'center':
            out += f' (justify {justify})'
        return out + ')'

    def _property(self, key, value, x, y, rot=0, hide=False, justify=None):
        # format 20260306 keeps (hide yes) directly in the property, not inside (effects)
        hidden = ' (hide yes)' if hide else ''
        return (f'\t\t(property {q(key)} {q(value)} (at {fmt(x)} {fmt(y)} {rot}){hidden} '
                f'(show_name no) (do_not_autoplace no) '
                f'{self._effects(justify=justify)})')

    def render_part(self, part, root_uuid):
        symbol = get_symbol(part.lib_id)
        # KiCad stores a 180-degree rotation plus mirror-y as no rotation plus mirror-x
        flipped = part.mirror and int(part.rot) % 360 == 180
        lines = ['\t(symbol', f'\t\t(lib_id {q(part.lib_id)})',
                 f'\t\t(at {fmt(part.x)} {fmt(part.y)} {0 if flipped else part.rot})']
        if flipped:
            lines.append('\t\t(mirror x)')
        elif part.mirror:
            lines.append('\t\t(mirror y)')
        lines += [f'\t\t(unit {part.unit})', '\t\t(body_style 1)', '\t\t(exclude_from_sim no)',
                  '\t\t(in_bom yes)' if not getattr(part, 'is_power', False) and not part.ref.startswith('#') else '\t\t(in_bom no)',
                  '\t\t(on_board yes)' if not part.ref.startswith('#') else '\t\t(on_board no)',
                  '\t\t(in_pos_files yes)', '\t\t(dnp no)', f'\t\t(uuid {q(part.uid)})']
        is_power = part.ref.startswith('#')
        # field angles are relative to the symbol, so cancel its rotation to keep text horizontal
        angle = 0 if int(part.rot) % 180 == 0 else (-int(part.rot)) % 360
        fields = getattr(part, 'fields', None) or {
            'Reference': {'x': part.x + 2.54, 'y': part.y - 2.54, 'justify': 'left', 'hide': is_power},
            'Value': {'x': part.x + 2.54, 'y': part.y + 2.54, 'justify': 'left', 'hide': False}}
        for name, text in (('Reference', part.ref), ('Value', part.value)):
            info = fields[name]
            justify = info.get('justify')
            if (int(part.rot) % 360 == 180) != bool(part.mirror):
                # KiCad mirrors a field's horizontal justification with the symbol
                justify = {'left': 'right', 'right': 'left'}.get(justify, justify)
            lines.append(self._property(name, text, info.get('x', part.x), info.get('y', part.y), angle,
                                        hide=info['hide'], justify=justify))
        footprint = part.footprint if part.footprint is not None else symbol_prop(symbol, 'Footprint')
        lines.append(self._property('Footprint', footprint, part.x, part.y, 0, hide=True))
        lines.append(self._property('Datasheet', part.props.get('Datasheet', symbol_prop(symbol, 'Datasheet')), part.x, part.y, 0, hide=True))
        description = part.props.get('Description', symbol_prop(symbol, 'Description'))
        lines.append(self._property('Description', description, part.x, part.y, 0, hide=True))
        for key, value in part.props.items():
            if key in ('Datasheet', 'Description'):
                continue
            lines.append(self._property(key, value, part.x, part.y, 0, hide=True))
        # KiCad lists every pin of the symbol on each unit of a multi-unit part
        all_numbers = list(dict.fromkeys(pin[0] for pin in pins(symbol)))
        for number in all_numbers or part.pin_table:
            lines.append(f'\t\t(pin {q(number)} (uuid {q(new_uuid())}))')
        lines.append(f'\t\t(instances (project {q(PROJECT)} (path {q(self.path)} (reference {q(part.ref)}) (unit {part.unit}))))')
        lines.append('\t)')
        return '\n'.join(lines)

    def four_way_junctions(self):
        """Points where four or more connections meet; call after finalize()."""
        wires = merge_overlapping_wires(self.wires)
        # stacked pins of one part (e.g. several GND pins at one point) look like a single connection
        pins = list({(id(p), round(p.pin_point(n)[0], 2), round(p.pin_point(n)[1], 2)): p.pin_point(n)
                     for p in self.parts for n in p.pin_table}.values())
        if self.handwired:
            nodes = pins + [(p.x, p.y) for p in self.parts if p.ref.startswith('#')]
            wires = split_wires_at(wires, nodes)
        counts = connection_counts(wires, pins)
        return [(x / 1.27, y / 1.27, c) for (x, y), c in counts.items() if c >= 4]

    def render(self, root_uuid):
        self.finalize()
        self.wires = merge_overlapping_wires(self.wires)
        if self.handwired:
            # a pin or symbol in the middle of a wire is not connected in KiCad, so split wires there
            nodes = [p.pin_point(n) for p in self.parts for n in p.pin_table]
            nodes += [(p.x, p.y) for p in self.parts if p.ref.startswith('#')]
            self.wires = split_wires_at(self.wires, nodes)
            keep = list(nodes) + [(x, y) for _, _, (x, y), _ in self.labels]
            self.wires = merge_touching_wires(self.wires, keep)
        known = {(round(x, 3), round(y, 3)) for x, y in self.junctions}
        if self.handwired:
            self.junctions.extend(meeting_points(self.wires, distinct_pins(self.parts)))
        for point in t_junctions(self.wires):
            if (round(point[0], 3), round(point[1], 3)) not in known:
                self.junctions.append(point)
        out = ['(kicad_sch', f'\t(version {VERSION})', '\t(generator "eeschema")', '\t(generator_version "10.0")',
               f'\t(uuid {q(self.uid if self.path == "/" + root_uuid else self.screen_uid)})', f'\t(paper {q(self.paper)})',
               f'\t(title_block (title {q(self.title)}) (rev "A") (company "Cryocooler Controller"))',
               '\t(lib_symbols']
        for lib_id in sorted(self.used_libs):
            out.append(embed_symbol(lib_id))
        out.append('\t)')
        for (x1, y1), (x2, y2) in self.wires:
            out.append(f'\t(wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})) '
                       f'(stroke (width 0) (type default)) (uuid {q(new_uuid())}))')
        self.junctions = list({(round(x, 3), round(y, 3)): (x, y) for x, y in self.junctions}.values())
        for (x, y) in self.junctions:
            out.append(f'\t(junction (at {fmt(x)} {fmt(y)}) (diameter 0) (color 0 0 0 0) (uuid {q(new_uuid())}))')
        for (x, y) in self.no_connects:
            out.append(f'\t(no_connect (at {fmt(x)} {fmt(y)}) (uuid {q(new_uuid())}))')
        for kind, net, (x, y), angle in self.labels:
            rotation = int(angle) % 360
            justify = 'right' if rotation in (180, 270) else 'left'
            if kind == 'label':
                out.append(f'\t(label {q(net)} (at {fmt(x)} {fmt(y)} {rotation}) '
                           f'(effects (font (size 1.27 1.27)) (justify {justify} bottom)) (uuid {q(new_uuid())}))')
            else:
                out.append(f'\t(global_label {q(net)} (shape {label_shape(net, self.path == '/' + root_uuid, self.filename)}) (at {fmt(x)} {fmt(y)} {rotation}) '
                           f'(fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify {justify})) '
                           f'(uuid {q(new_uuid())}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
                           f'(at {fmt(x)} {fmt(y)} 0) (hide yes) (show_name no) (do_not_autoplace no) '
                           f'(effects (font (size 1.27 1.27)) (justify {justify}))))')
        for text, x, y, size in self.text_items:
            out.append(f'\t(text {q(text)} (exclude_from_sim no) (at {fmt(x)} {fmt(y)} 0) '
                       f'(effects (font (size {size} {size})) (justify left top)) (uuid {q(new_uuid())}))')
        for part in self.parts:
            out.append(self.render_part(part, root_uuid))
        for item in self.sheet_symbols:
            out.append(item)
        if self.path == '/' + root_uuid:
            out.append('\t(sheet_instances (path "/" (page "1")))')
        if self.path == '/' + root_uuid:
            out.append('\t(embedded_fonts no)')
        out.append(')')
        return kicad_format('\n'.join(out) + '\n')


# ── nets ─────────────────────────────────────────────────────────────────
# discrete parts the layout engine places next to the pins they connect to
AUTO_LIBS = {
    'Device:R_US', 'Device:C', 'Device:C_Polarized', 'Device:L', 'Device:LED', 'Device:LED_Dual_Bidirectional',
    'Device:Fuse', 'Switch:SW_Push', 'Reference_Voltage:LM4040DBZ-5', 'Reference_Voltage:LM4040DBZ-2.5',
    'Transistor_FET:BSS138', 'Transistor_FET:BSS84', 'power:PWR_FLAG',
}

POWER_SYMBOLS = {
    'GND': 'GND', '+3V3': '+3V3', '+5V': '+5V', '+12V': '+12V', '+15V': '+15V', '-15V': '-15V',
    'VIN': '+12V', 'VSW': '+12V', '+16V5': '+15V', '-16V5': '-15V',
    'ISO_GND': 'GNDREF', 'ISO_5V': '+5VA', 'ISO_3V3': '+3.3VA',
}

GLOBAL_NETS = {
    'SDA', 'SCL', 'SPI_SCK', 'SPI_MOSI', 'SPI_MISO', 'AD9833_FSYNC', 'MCP4921_CS', 'IMU_CS',
    'IMU_INT1', 'IMU_INT2', 'ACS_SCK', 'ACS_MOSI', 'ACS_MISO', 'ACS_CS', 'AMP_REM_EN', 'PWR_KILL',
    'LED_FAULT', 'LED_READY', 'FLOW_TACH', 'FAN_ALERT', 'NTC_ADC', 'STATUS_RGB', 'PWR_INT',
    'SIG_SINE', 'AMP_REM',
}
