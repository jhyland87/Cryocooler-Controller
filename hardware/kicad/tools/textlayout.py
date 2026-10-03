"""Text placement with a hard no-overlap rule.

After parts are placed and wires/labels routed, every visible text item (reference, value, power-symbol
name, label, note) must not overlap another text item or a symbol body. Fields are placed in the first
position that satisfies the rule; a field is hidden only when no position exists. `check_text` re-verifies.
"""
from kicadgen import get_symbol, symbol_prop
from sexpr import find_all, pins as symbol_pins, sval

CHAR_MM = 1.0      # width per character at 1.27 mm text
LINE_H = 1.6       # height of one text line
LINE_GAP = 0.5     # space between stacked fields (must exceed MARGIN)
MARGIN = 0.3
STEP = 1.27
PIN_TEXT = 1.0     # clearance around a symbol body for pin numbers
GAP = 0.9 + PIN_TEXT + 0.3   # distance from a body to its own fields


def text_width(text, size=1.27):
    return len(str(text)) * CHAR_MM * size / 1.27 + 0.5


def field_box(x, y, width, justify):
    if justify == 'left':
        return (x, y - LINE_H / 2, x + width, y + LINE_H / 2)
    if justify == 'right':
        return (x - width, y - LINE_H / 2, x, y + LINE_H / 2)
    return (x - width / 2, y - LINE_H / 2, x + width / 2, y + LINE_H / 2)


def hits(a, b, margin=MARGIN):
    return not (a[2] + margin <= b[0] or a[0] - margin >= b[2] or a[3] + margin <= b[1] or a[1] - margin >= b[3])


def label_box(kind, net, x, y, angle):
    length = text_width(net) + (2.2 if kind == 'global_label' else 0.3)
    angle = int(angle) % 360
    if angle == 0:
        return (x, y - 1.9, x + length, y + 0.3)
    if angle == 180:
        return (x - length, y - 1.9, x, y + 0.3)
    if angle == 90:
        return (x - 1.5, y - length, x + 1.5, y)
    return (x - 1.5, y, x + 1.5, y + length)


def power_geometry(part):
    """Graphic box and value-text box of an upright power symbol at its pin point."""
    symbol = get_symbol(part.lib_id)
    down = symbol_pins(symbol)[0][4] == 270
    x, y = part.x, part.y
    graphic = (x - 1.5, y, x + 1.5, y + 2.2) if down else (x - 1.5, y - 2.2, x + 1.5, y)
    value_at = None
    for prop in find_all(symbol, 'property'):
        if sval(prop[1]) == 'Value':
            value_at = (float(prop[3][1]), float(prop[3][2]))
    vx = x + (value_at[0] if value_at else 0)
    vy = y - (value_at[1] if value_at else (-3.8 if down else 3.8))
    return graphic, (vx, vy)


class TextLayout:
    def __init__(self, sheet):
        self.sheet = sheet
        self.width, self.height = sheet.PAPER[sheet.paper]
        self.symbols = []        # (part, box) hard obstacles
        self.power_graphics = []
        self.fixed_text = []     # labels and notes
        self.placed = []         # boxes of placed visible text
        self.wires = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])) for a, b in sheet.wires]
        for part in sheet.parts:
            if part.ref.startswith('#'):
                graphic, _ = power_geometry(part) if part.lib_id != 'power:PWR_FLAG' else (self.flag_box(part), None)
                self.power_graphics.append(graphic)
            else:
                x0, y0, x1, y1 = part.bbox()
                # pin numbers sit just outside the body box, so keep fields clear of them too
                self.symbols.append((part, (x0 - PIN_TEXT, y0 - PIN_TEXT, x1 + PIN_TEXT, y1 + PIN_TEXT)))
        for kind, net, (x, y), angle in sheet.labels:
            self.fixed_text.append(label_box(kind, net, x, y, angle))
        for text, x, y, size in sheet.text_items:
            self.fixed_text.append((x, y, x + text_width(text, size) * 1.0, y + size * 1.5))

    @staticmethod
    def flag_box(part):
        return (part.x - 1.5, part.y - 2.2, part.x + 1.5, part.y)

    # ── hard / soft rules ────────────────────────────────────────────────
    def inside_page(self, box):
        title = (self.width - 112, self.height - 36, self.width, self.height)
        return (box[0] >= 6 and box[1] >= 6 and box[2] <= self.width - 6 and box[3] <= self.height - 6
                and not hits(box, title, 0))

    def hard_free(self, box, extra=()):
        if not self.inside_page(box):
            return False
        for _, symbol in self.symbols:
            if hits(box, symbol, 0.2):
                return False
        for graphic in self.power_graphics:
            if hits(box, graphic, 0.1):
                return False
        for other in self.fixed_text:
            if hits(box, other):
                return False
        for other in self.placed:
            if hits(box, other):
                return False
        return not any(hits(box, other) for other in extra)

    def wire_hits(self, box):
        return sum(1 for wire in self.wires if hits(box, wire, 0.15))

    # ── field candidates ─────────────────────────────────────────────────
    def candidates(self, part, widths):
        """Yield (cost, {field: (x, y, justify)}) for blocks of the requested fields, best first."""
        x0, y0, x1, y1 = part.bbox()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        names = list(widths)
        height = LINE_H * len(names) + LINE_GAP * (len(names) - 1)
        block_w = max(widths.values())
        ic = (not part.auto) and len(part.pin_table) > 3
        horizontal = len(part.pin_table) <= 2 and int(part.rot) % 180 == 90
        if ic:
            order = ('above', 'below', 'right', 'left')
        elif horizontal:
            order = ('above', 'below', 'right', 'left')
        else:
            order = ('right', 'left', 'above', 'below')
        for rank, side in enumerate(order):
            for shift_steps in sorted(range(-14, 15), key=abs):
                shift = shift_steps * STEP
                if side in ('right', 'left'):
                    top = cy - height / 2 + shift
                    anchor_x = x1 + GAP if side == 'right' else x0 - GAP
                    justify = 'left' if side == 'right' else 'right'
                else:
                    top = (y0 - GAP - height) if side == 'above' else (y1 + GAP)
                    if ic:
                        anchor_x, justify = x0 + shift, 'left'
                    else:
                        anchor_x, justify = cx + shift, 'center'
                placement = {}
                for index, name in enumerate(names):
                    line_y = top + LINE_H / 2 + index * (LINE_H + LINE_GAP)
                    placement[name] = (anchor_x, line_y, justify)
                yield rank * 4 + abs(shift_steps) * 0.35, placement

    def place_part(self, part):
        fields = {'Reference': text_width(part.ref), 'Value': text_width(part.value)}
        for names in (('Reference', 'Value'), ('Reference',), ('Value',)):
            widths = {name: fields[name] for name in names}
            best = None
            for cost, placement in self.candidates(part, widths):
                boxes = [field_box(x, y, widths[name], justify) for name, (x, y, justify) in placement.items()]
                if not all(self.hard_free(box, boxes[:index]) for index, box in enumerate(boxes)):
                    continue
                total = cost + 3 * sum(self.wire_hits(box) for box in boxes)
                if best is None or total < best[0]:
                    best = (total, placement, boxes)
                if total < 4:
                    break
            if best is not None:
                _, placement, boxes = best
                part.fields = {}
                for name in ('Reference', 'Value'):
                    if name in placement:
                        x, y, justify = placement[name]
                        part.fields[name] = {'x': x, 'y': y, 'justify': justify, 'hide': False}
                    else:
                        part.fields[name] = {'x': part.x, 'y': part.y, 'justify': None, 'hide': True}
                self.placed.extend(boxes)
                return
        part.fields = {name: {'x': part.x, 'y': part.y, 'justify': None, 'hide': True} for name in ('Reference', 'Value')}
        print(f'  [{self.sheet.title}] text hidden for {part.ref} (no free position)')

    def place_power_text(self):
        for part in self.sheet.parts:
            if not part.ref.startswith('#'):
                continue
            part.fields = {'Reference': {'hide': True}, 'Value': {'hide': True}}
            if part.lib_id == 'power:PWR_FLAG' or part.value == 'GND':
                continue
            _, (vx, vy) = power_geometry(part)
            box = field_box(vx, vy, text_width(part.value), 'center')
            if self.hard_free(box):
                part.fields['Value'] = {'x': vx, 'y': vy, 'justify': None, 'hide': False}
                self.placed.append(box)

    def run(self):
        parts = [p for p in self.sheet.parts if not p.ref.startswith('#')]
        parts.sort(key=lambda p: (p.auto, -(p.bbox()[2] - p.bbox()[0]) * (p.bbox()[3] - p.bbox()[1])))
        # power-symbol names are laid out last, so reserve their boxes while placing fields
        for part in parts:
            self.place_part(part)
        self.place_power_text()


def place_text(sheet):
    TextLayout(sheet).run()


def check_text(sheet):
    """Return a list of overlap descriptions for visible text vs text and text vs symbol bodies."""
    layout = TextLayout(sheet)
    items = []   # (description, box)
    for part in sheet.parts:
        fields = getattr(part, 'fields', {})
        for name in ('Reference', 'Value'):
            info = fields.get(name)
            if not info or info.get('hide'):
                continue
            text = part.ref if name == 'Reference' else part.value
            items.append((f'{part.ref}.{name}', field_box(info['x'], info['y'], text_width(text), info['justify'])))
    for kind, net, (x, y), angle in sheet.labels:
        items.append((f'label {net}', label_box(kind, net, x, y, angle)))
    for text, x, y, size in sheet.text_items:
        items.append((f'note "{text[:20]}"', (x, y, x + text_width(text, size), y + size * 1.5)))
    problems = []
    for index, (name, box) in enumerate(items):
        for other_name, other in items[index + 1:]:
            if hits(box, other, 0.05):
                problems.append(f'text {name} overlaps text {other_name}')
        for part, symbol in layout.symbols:
            if name.startswith(part.ref + '.'):
                if hits(box, symbol, 0.05):
                    problems.append(f'text {name} overlaps its own symbol')
                continue
            if name.startswith('label'):
                symbol = part.bbox()
            if hits(box, symbol, 0.05):
                problems.append(f'text {name} overlaps symbol {part.ref}')
        for graphic in layout.power_graphics:
            if hits(box, graphic, 0.0):
                problems.append(f'text {name} overlaps a power symbol')
    return problems
