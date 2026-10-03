"""Auto-placement of passives next to the pins they connect to, plus orthogonal wire routing.

Power nets get a stub + power symbol at every pin; other nets are drawn as real wires between
their pins (A* on the 1.27 mm grid) and fall back to net labels when a route is too long or blocked.
"""
import heapq
import math

import kicadgen
from kicadgen import GLOBAL_NETS, POWER_SYMBOLS, get_symbol
from sexpr import pins as symbol_pins

CELL = 1.27
STUB_CELLS = 2
LONG_NET_MM = 85
# screen-space step for an outward angle given in math convention (y up)
STEP = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}


def to_cell(value):
    return int(round(value / CELL))


def to_mm(cell):
    return round(cell * CELL, 4)


def on_grid(value):
    return abs(value / CELL - round(value / CELL)) < 0.02


def expand(box, cells):
    margin = cells * CELL
    return (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)


def overlaps(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def pin_zone(part, number, x=None, y=None, rot=None):
    """Box covering a power pin's stub and symbol (so other parts keep clear of it)."""
    px, py = part.pin_point(number, x, y, rot)
    angle = part.pin_out_angle(number, rot)
    dx, dy = STEP[int(angle) % 360]
    end = (px + dx * STUB_CELLS * CELL, py + dy * STUB_CELLS * CELL)
    return [expand((min(px, end[0]), min(py, end[1]), max(px, end[0]), max(py, end[1])), 1.0),
            (end[0] - 2.5 * CELL, end[1] - 5 * CELL, end[0] + 2.5 * CELL, end[1] + 5 * CELL)]


class Layout:
    def __init__(self, sheet):
        self.sheet = sheet
        self.width, self.height = sheet.PAPER[sheet.paper]
        self.nets = {}
        self.glob = {}
        self.power_pins = set()
        for part, number, net, is_global in sheet.conns:
            self.nets.setdefault(net, []).append((part, number))
            if is_global or net in GLOBAL_NETS:
                self.glob[net] = True
            if net in POWER_SYMBOLS:
                self.power_pins.add((id(part), number))
        self.placed = set()
        self.keepouts = {}
        self.pin_zones = []
        self.net_by_pin = {(id(part), number): net for part, number, net, _ in sheet.conns}

    # ── placement ────────────────────────────────────────────────────────
    def keepout(self, part, x=None, y=None, rot=None):
        body = expand(part.bbox(x, y, rot), 1.5 if part.auto else 0.5)
        boxes = [body]
        if part.auto and not part.ref.startswith('#'):
            # reference/value text sits to the right of the part origin
            px = part.x if x is None else x
            py = part.y if y is None else y
            width = 1.1 * max(len(part.ref), len(str(part.value))) + 2
            use_rot = part.rot if rot is None else rot
            if len(part.pin_table) <= 2 and int(use_rot) % 180 == 90:
                boxes.append((px - width / 2 - 1, py - 6.5, px + width / 2 + 1, py + 6.5))
            else:
                boxes.append((px + 1.5, py - 4.2, px + 2.54 + width, py + 4.2))
        for number in part.pin_table:
            if (id(part), number) in self.power_pins:
                boxes.extend(pin_zone(part, number, x, y, rot))
            elif not part.auto and self.net_by_pin.get((id(part), number)) in self.glob:
                boxes.append(self.label_zone(part, number, x, y, rot))
        return boxes

    def corridor_zones(self, part):
        """Exit corridors (stub + 5 cells) in front of a fixed part's local-net signal pins."""
        zones = []
        for number in part.pin_table:
            net = self.net_by_pin.get((id(part), number))
            if net is None or net in POWER_SYMBOLS or net in self.glob:
                continue
            px, py = part.pin_point(number)
            dx, dy = STEP[int(part.pin_out_angle(number)) % 360]
            far = (px + dx * 7 * CELL, py + dy * 7 * CELL)
            box = expand((min(px, far[0]), min(py, far[1]), max(px, far[0]), max(py, far[1])), 0.9)
            zones.append((box, id(part), number))
        return zones

    def label_zone(self, part, number, x=None, y=None, rot=None):
        """Box covering a fixed pin's stub and the global-label text beyond it."""
        px, py = part.pin_point(number, x, y, rot)
        angle = part.pin_out_angle(number, rot)
        dx, dy = STEP[int(angle) % 360]
        net = self.net_by_pin[(id(part), number)]
        length = 2 * CELL + 1.15 * len(net) + 3
        far = (px + dx * length, py + dy * length)
        return expand((min(px, far[0]), min(py, far[1]), max(px, far[0]), max(py, far[1])), 0.8)

    def free(self, boxes, ignore=None, anchor_pin=None):
        title = (self.width - 112, self.height - 36, self.width, self.height)
        for box in boxes:
            if box[0] < 8 or box[1] < 22 or box[2] > self.width - 8 or box[3] > self.height - 8:
                return False
            if overlaps(box, title):
                return False
            for other, other_boxes in self.keepouts.items():
                if other is ignore:
                    continue
                if any(overlaps(box, ob) for ob in other_boxes):
                    return False
            for zone, part_id, number in self.pin_zones:
                if anchor_pin == (part_id, number):
                    continue
                if overlaps(box, zone):
                    return False
        return True

    def connected_nets(self, part):
        result = []
        for net, members in self.nets.items():
            for member, number in members:
                if member is part:
                    result.append((net, number))
        return result

    def placed_pins(self, net, fixed_only=False):
        out = []
        for member, number in self.nets[net]:
            if id(member) in self.placed and (not fixed_only or not member.auto):
                out.append((member, number))
        return out

    def place_auto(self):
        sheet = self.sheet
        for part in sheet.parts:
            if not part.auto:
                self.placed.add(id(part))
                self.keepouts[id(part)] = self.keepout(part)
                self.pin_zones.extend(self.corridor_zones(part))
        remaining = [part for part in sheet.parts if part.auto]
        scratch_x, scratch_y = 20, 40
        while remaining:
            def strength(part):
                if part.near is not None:
                    return 50 if id(part.near[0]) in self.placed else -1
                score = 0
                for net, number in self.connected_nets(part):
                    if net in POWER_SYMBOLS:
                        score += 0.2 if self.placed_pins(net, True) else 0
                    elif self.placed_pins(net):
                        score += 1
                return score
            part = max(remaining, key=strength)
            remaining.remove(part)
            if not self.place_one(part):
                x, y = self.scratch_spot(part, scratch_x, scratch_y)
                part.x, part.y = sheet.snap(x), sheet.snap(y)
                print(f'  [{sheet.title}] {part.ref} placed in scratch area (no anchor)')
            self.placed.add(id(part))
            self.keepouts[id(part)] = self.keepout(part)

    def scratch_spot(self, part, x0, y0):
        for gy in range(int(y0), int(self.height - 40), 8):
            for gx in range(int(x0), int(self.width - 40), 8):
                boxes = self.keepout(part, gx, gy, part.rot)
                if self.free(boxes):
                    return gx, gy
        return x0, y0

    def place_one(self, part):
        sheet = self.sheet
        hint = (part.x, part.y)
        nets = self.connected_nets(part)
        anchors = []
        if part.near is not None and id(part.near[0]) in self.placed:
            near_part, near_pin = part.near
            near_net = self.net_by_pin.get((id(near_part), near_pin))
            for net, number in nets:
                if net == near_net:
                    anchors = [(net, number, near_part, near_pin)]
                    break
        for net, number in nets:
            if anchors or net in POWER_SYMBOLS:
                continue
            for member, member_pin in self.placed_pins(net):
                anchors.append((net, number, member, member_pin))
        if not anchors:
            candidates = []
            for net, number in nets:
                for member, member_pin in self.placed_pins(net, fixed_only=True):
                    px, py = member.pin_point(member_pin)
                    candidates.append((abs(px - hint[0]) + abs(py - hint[1]), net, number, member, member_pin))
            candidates.sort(key=lambda item: item[0])
            anchors = [(n, num, m, mp) for _, n, num, m, mp in candidates[:8]]
        best = self.search(part, anchors, hint)
        if best is None and part.near is not None:
            inferred = []
            for net, number in nets:
                if net in POWER_SYMBOLS:
                    continue
                for member, member_pin in self.placed_pins(net):
                    inferred.append((net, number, member, member_pin))
            best = self.search(part, inferred, hint)
        if best is None:
            return False
        _, part.x, part.y, part.rot = best
        return True

    def search(self, part, anchors, hint):
        sheet = self.sheet
        best = None
        for net, number, member, member_pin in anchors:
            anchor = member.pin_point(member_pin)
            angle = int(member.pin_out_angle(member_pin)) % 360
            dx, dy = STEP[angle]
            px, py = -dy, dx
            for rot in (0, 90, 180, 270):
                facing = int(part.pin_out_angle(number, rot)) % 360
                penalty = 0 if (facing == (angle + 180) % 360 or len(part.pin_table) > 2) else 8
                if not self.symbols_ok(part, rot, number):
                    continue
                offset = part.pin_point(number, 0, 0, rot)
                for k in (5, 6, 8, 10, 13, 16, 20, 26, 34, 44):
                    for lateral in (0, 3, -3, 6, -6, 9, -9, 13, -13, 18, -18):
                        target = (anchor[0] + dx * k * CELL + px * lateral * CELL,
                                  anchor[1] + dy * k * CELL + py * lateral * CELL)
                        x = sheet.snap(target[0] - offset[0])
                        y = sheet.snap(target[1] - offset[1])
                        boxes = self.keepout(part, x, y, rot)
                        if not self.free(boxes, anchor_pin=(id(member), member_pin)):
                            continue
                        cost = self.cost(part, x, y, rot, hint) + k * 0.5 + abs(lateral) * 0.3 + penalty
                        if best is None or cost < best[0]:
                            best = (cost, x, y, rot)
                if best is not None:
                    break
        return best

    def symbols_ok(self, part, rot, anchor_pin):
        """Grounds hang down and supplies point up, so reject poses that would aim a symbol into the part."""
        for net, number in self.connected_nets(part):
            if net not in POWER_SYMBOLS or number == anchor_pin:
                continue
            angle = int(part.pin_out_angle(number, rot)) % 360
            down = symbol_pins(get_symbol(f'power:{POWER_SYMBOLS[net]}'))[0][4] == 270
            if (down and angle == 90) or (not down and angle == 270):
                return False
        return True

    def cost(self, part, x, y, rot, hint):
        total = 0.0
        has_signal = False
        for net, number in self.connected_nets(part):
            px, py = part.pin_point(number, x, y, rot)
            if net in POWER_SYMBOLS:
                continue
            others = self.placed_pins(net)
            if not others:
                continue
            has_signal = True
            total += min(abs(px - m.pin_point(mp)[0]) + abs(py - m.pin_point(mp)[1]) for m, mp in others)
        if not has_signal:
            total += (abs(x - hint[0]) + abs(y - hint[1])) * 0.2
        return total

    # ── routing ──────────────────────────────────────────────────────────
    def route(self):
        sheet = self.sheet
        self.blocked = set()
        self.owner = {}
        self.edges = {}
        import textlayout
        self.tl = textlayout
        self.part_boxes = [p.bbox() for p in sheet.parts if not p.ref.startswith('#')]
        self.power_boxes = []
        self.label_boxes = []
        self.note_boxes = [(x, y, x + textlayout.text_width(t, size), y + size * 1.5)
                           for t, x, y, size in sheet.text_items]
        # wires must end at every pin / power-symbol point rather than run through it
        self.nodes = {(to_cell(p.pin_point(n)[0]), to_cell(p.pin_point(n)[1]))
                      for p in sheet.parts for n in p.pin_table}
        for part in sheet.parts:
            x0, y0, x1, y1 = part.bbox()
            for cx in range(to_cell(x0) - 1, to_cell(x1) + 2):
                for cy in range(to_cell(y0) - 1, to_cell(y1) + 2):
                    self.blocked.add((cx, cy))
        # power stubs and symbols first so signal wires route around them
        seen_power = set()
        self.power_trees = {}
        self.power_tags = []
        attached = []
        for part, number, net, is_global in list(sheet.conns):
            if net not in POWER_SYMBOLS:
                continue
            anchor = part.near
            if (part.auto and anchor and not anchor[0].auto
                    and self.net_by_pin.get((id(anchor[0]), anchor[1])) == net):
                attached.append((part, number, net))
                continue
            self.power_stub(part, number, net, seen_power)
        for part, number, net in attached:
            self.attach_power(part, number, net, seen_power)
        for tag in self.power_tags:
            self.flush_edges(tag)
        for net, members in self.nets.items():
            if net in POWER_SYMBOLS:
                continue
            for part, number in members:
                if not (on_grid(part.pin_point(number)[0]) and on_grid(part.pin_point(number)[1])):
                    continue
                cells, angle = self.stub_cells(part, number)
                dx, dy = STEP[angle]
                corridor = list(cells)
                for i in range(1, 5):
                    corridor.append((cells[-1][0] + dx * i, cells[-1][1] + dy * i))
                for index, cell in enumerate(corridor):
                    if index > 2 and (cell in self.blocked or cell in self.owner):
                        break
                    self.owner.setdefault(cell, net)
        signal = [(net, members) for net, members in self.nets.items() if net not in POWER_SYMBOLS]
        signal.sort(key=lambda item: self.span(item[1]))
        for net, members in signal:
            self.route_net(net, members)
        for part, number in sheet.ncs:
            sheet.no_connects.append(part.pin_point(number))

    def span(self, members):
        points = [m.pin_point(n) for m, n in members]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    def stub_cells(self, part, number):
        px, py = part.pin_point(number)
        angle = int(part.pin_out_angle(number)) % 360
        dx, dy = STEP[angle]
        base = (to_cell(px), to_cell(py))
        return [(base[0] + dx * i, base[1] + dy * i) for i in range(STUB_CELLS + 1)], angle

    def add_edges(self, net, cells):
        store = self.edges.setdefault(net, set())
        for first, second in zip(cells, cells[1:]):
            store.add(frozenset((first, second)))
        for cell in cells:
            self.owner[cell] = net

    def power_stub(self, part, number, net, seen):
        px, py = part.pin_point(number)
        key = (round(px, 2), round(py, 2), net)
        if key in seen:
            return
        seen.add(key)
        cells, angle = self.stub_cells(part, number)
        tag = f'power:{key}'
        self.add_edges(tag, cells)
        self.power_trees[key] = (tag, cells)
        self.power_tags.append(tag)
        end = cells[-1]
        down = symbol_pins(get_symbol(f'power:{POWER_SYMBOLS[net]}'))[0][4] == 270
        self.owner[(end[0], end[1] + (1 if down else -1))] = tag + ':symbol'
        symbol_name = POWER_SYMBOLS[net]
        lib_id = f'power:{symbol_name}'
        kicadgen._pwr_counter[0] += 1
        ref = f'#PWR{kicadgen._pwr_counter[0]:03d}'
        self.nodes.add(end)
        power = self.sheet.add(lib_id, ref, net, to_mm(end[0]), to_mm(end[1]), rot=0)
        graphic_x, graphic_y = to_mm(end[0]), to_mm(end[1])
        self.power_boxes.append((graphic_x - 1.5, graphic_y, graphic_x + 1.5, graphic_y + 2.2) if down
                                else (graphic_x - 1.5, graphic_y - 2.2, graphic_x + 1.5, graphic_y))
        power.is_power = True

    def attach_power(self, part, number, net, seen):
        """Wire a decoupling cap/pull-up straight into the power stub of the IC pin it serves."""
        near_part, near_pin = part.near
        px, py = near_part.pin_point(near_pin)
        entry = self.power_trees.get((round(px, 2), round(py, 2), net))
        if entry is not None:
            tag, cells = entry
            stub, _ = self.stub_cells(part, number)
            if all(self.owner.get(c) in (None, tag) for c in stub):
                path = self.astar(stub[-1], set(cells), tag)
                if path is not None and len(path) <= 25:
                    self.add_edges(tag, stub)
                    self.add_edges(tag, path)
                    return
        self.power_stub(part, number, net, seen)

    def passable(self, cell, net):
        owner = self.owner.get(cell)
        if owner == net:
            return True
        return owner is None and cell not in self.blocked

    def route_net(self, net, members):
        sheet = self.sheet
        unique = []
        seen_points = set()
        for part, number in members:
            point = part.pin_point(number)
            key = (round(point[0], 2), round(point[1], 2))
            if key not in seen_points:
                seen_points.add(key)
                unique.append((part, number))
        is_global = self.glob.get(net, False)
        if len(unique) == 1:
            for part, number in unique:
                self.label_pin(part, number, net, is_global)
            return
        routable = [(p, n) for p, n in unique if on_grid(p.pin_point(n)[0]) and on_grid(p.pin_point(n)[1])]
        for part, number in unique:
            if (part, number) not in routable:
                self.label_pin(part, number, net, is_global)
        if len(routable) < 2:
            for part, number in routable:
                self.label_pin(part, number, net, is_global)
            return
        pending = list(routable)
        clusters = []
        while pending:
            seed = pending.pop(0)
            cells, angle = self.stub_cells(*seed)
            if any(self.owner.get(c) not in (None, net) for c in cells):
                clusters.append(([seed], seed))
                self.label_pin(seed[0], seed[1], net, is_global, 'seed blocked')
                continue
            self.add_edges(net, cells)
            tree = set(cells)
            members = [seed]
            progress = True
            while progress and pending:
                progress = False
                ordered = sorted(pending, key=lambda pn: self.tree_distance(pn, tree))
                for pn in ordered:
                    if self.tree_distance(pn, tree) * CELL > LONG_NET_MM:
                        break
                    stub, _ = self.stub_cells(*pn)
                    if any(self.owner.get(c) not in (None, net) for c in stub):
                        continue
                    path = self.astar(stub[-1], tree, net)
                    if path is None or len(path) > 1.5 * self.tree_distance(pn, tree) + 8:
                        continue
                    self.add_edges(net, stub)
                    self.add_edges(net, path)
                    tree.update(stub)
                    tree.update(path)
                    members.append(pn)
                    pending.remove(pn)
                    progress = True
                    break
            clusters.append((members, seed))
        # pins that could not join a cluster stay as single-pin clusters with a label
        multi = len(clusters) > 1
        for members, seed in clusters:
            if len(members) == 1 and multi:
                self.label_pin(seed[0], seed[1], net, is_global)
            elif is_global or multi:
                site = self.best_label_pin(members, net)
                self.global_label(site[0], site[1], net, local=not is_global)
        self.flush_edges(net)

    def best_label_pin(self, members, net):
        """Pick the cluster pin whose label text has the most room (fixed parts preferred)."""
        best = None
        for index, (part, number) in enumerate(members):
            cells, angle = self.stub_cells(part, number)
            fit = self.label_fit(cells[-1], angle, net, net, 'label')
            if fit is None:
                continue
            score = fit['length'] * 2 + (0 if not part.auto else 3) + index * 0.01
            if best is None or score < best[0]:
                best = (score, part, number)
        if best is None:
            return members[0]
        return (best[1], best[2])

    def tree_distance(self, pin, tree):
        part, number = pin
        px, py = part.pin_point(number)
        cell = (to_cell(px), to_cell(py))
        return min(abs(cell[0] - c[0]) + abs(cell[1] - c[1]) for c in tree)

    def label_text_cells(self, end, angle, net):
        length = 1.05 * len(net) + 3.5
        count = int(math.ceil(length / CELL))
        dx, dy = STEP[int(angle) % 360]
        return [(end[0] + dx * i, end[1] + dy * i) for i in range(1, count + 1)]

    def label_box_free(self, kind, net, site, angle):
        box = self.tl.label_box(kind, net, to_mm(site[0]), to_mm(site[1]), angle)
        if not (6 <= box[0] and 6 <= box[1] and box[2] <= self.width - 6 and box[3] <= self.height - 6):
            return False
        title = (self.width - 112, self.height - 36, self.width, self.height)
        if self.tl.hits(box, title, 0):
            return False
        for other in self.part_boxes:
            if self.tl.hits(box, other, 0.3):
                return False
        for other in self.power_boxes + self.label_boxes + self.note_boxes:
            if self.tl.hits(box, other, 0.2):
                return False
        return True

    def label_fit(self, stub_end, angle, net, tag, kind='label'):
        """Shortest wire path (straight, optionally bent 90 degrees) ending in a free label spot, or None."""
        base = int(angle) % 360
        candidates = []
        for extra in (0, 2, 4, 6, 9, 12, 16):
            candidates.append((extra, None, 0))
            for turn in (90, 270):
                for length in (2, 4, 6, 9, 12, 16, 20):
                    candidates.append((extra + length + 1, turn, length) if False else (extra + length + 1, turn, (extra, length)))
        candidates.sort(key=lambda item: item[0])
        for cost, turn, detail in candidates:
            if turn is None:
                extra, length, label_angle = cost, 0, base
            else:
                extra, length = detail
                label_angle = (base + turn) % 360
            dx, dy = STEP[base]
            path = [(stub_end[0] + dx * i, stub_end[1] + dy * i) for i in range(1, extra + 1)]
            corner = path[-1] if path else stub_end
            if turn is not None:
                tx, ty = STEP[label_angle]
                path += [(corner[0] + tx * i, corner[1] + ty * i) for i in range(1, length + 1)]
            site = path[-1] if path else stub_end
            text = self.label_text_cells(site, label_angle, net)
            if (all(self.passable(c, tag) or self.passable(c, net) or self.margin_cell(c, tag, net) for c in path)
                    and self.label_box_free(kind, net, site, label_angle)):
                return {'path': path, 'site': site, 'angle': label_angle, 'length': len(path)}
        return self.label_search(stub_end, net, tag, kind)

    def margin_cell(self, cell, tag, net):
        """True for an unowned cell that is only inside a part's keep-out margin, not its body or a pin."""
        if cell in self.nodes or self.owner.get(cell) not in (None, tag, net):
            return False
        x, y = to_mm(cell[0]), to_mm(cell[1])
        return not any(b[0] - 0.4 <= x <= b[2] + 0.4 and b[1] - 0.4 <= y <= b[3] + 0.4
                       for b in self.part_boxes)

    def label_search(self, stub_end, net, tag, kind):
        """Breadth-first escape from a boxed-in stub to the nearest free label spot, or None."""
        seen = {stub_end: None}
        queue = [stub_end]
        for cell in queue:
            depth = 0
            walk = cell
            while seen[walk] is not None:
                walk = seen[walk]
                depth += 1
            if depth > 60:
                continue
            if depth > 0:
                for label_angle in (0, 180, 90, 270):
                    if self.label_box_free(kind, net, cell, label_angle):
                        path = []
                        walk = cell
                        while walk != stub_end:
                            path.append(walk)
                            walk = seen[walk]
                        path.reverse()
                        return {'path': path, 'site': cell, 'angle': label_angle, 'length': len(path)}
            for dx, dy in STEP.values():
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt in seen or not (self.passable(nxt, tag) or self.passable(nxt, net)
                                       or self.margin_cell(nxt, tag, net)):
                    continue
                seen[nxt] = cell
                queue.append(nxt)
        return None

    def place_label(self, net, kind, stub, angle, tag):
        """Place a label at the end of a (possibly bent) stub whose text area is free."""
        end = stub[-1]
        fit = self.label_fit(end, angle, net, tag, kind)
        if fit is None:
            print(f'  [{self.sheet.title}] label {net}: no free position')
            fit = {'path': [], 'site': end, 'angle': int(angle) % 360}
        site, label_angle = fit['site'], fit['angle']
        if fit['path']:
            self.add_edges(tag, [end] + fit['path'])
        for cell in self.label_text_cells(site, label_angle, net):
            self.owner.setdefault(cell, tag)
        self.label_boxes.append(self.tl.label_box(kind, net, to_mm(site[0]), to_mm(site[1]), label_angle))
        self.sheet.labels.append((kind, net, (to_mm(site[0]), to_mm(site[1])), label_angle))
        return site

    def label_pin(self, part, number, net, is_global, reason=''):
        """Net-label fallback: a short stub plus a label with a reserved text area."""
        cells, angle = self.stub_cells(part, number)
        tag = f'label:{net}:{id(part)}:{number}'
        if any(self.owner.get(c) not in (None, net) for c in cells[1:]):
            cells = cells[:1]
        else:
            for cell in cells:
                self.owner.setdefault(cell, tag)
        if reason:
            print(f'  [{self.sheet.title}] label fallback {net} at {part.ref}.{number}: {reason}')
        self.add_edges(tag, cells)
        self.place_label(net, 'global_label' if is_global else 'label', cells, angle, tag)
        self.flush_edges(tag)

    def global_label(self, part, number, net, local=False):
        cells, angle = self.stub_cells(part, number)
        tag = net
        kind = 'label' if local else 'global_label'
        self.place_label(net, kind, cells, angle, tag)

    def astar(self, start, goals, net):
        xs = [g[0] for g in goals]
        ys = [g[1] for g in goals]
        box = (min(xs), min(ys), max(xs), max(ys))
        max_x = int(self.width / CELL) - 6
        max_y = int(self.height / CELL) - 6

        def heuristic(cell):
            dx = max(box[0] - cell[0], 0, cell[0] - box[2])
            dy = max(box[1] - cell[1], 0, cell[1] - box[3])
            return dx + dy

        queue = [(heuristic(start), 0, start, None)]
        best = {(start, None): 0}
        parent = {}
        while queue:
            _, cost, cell, heading = heapq.heappop(queue)
            if cell in goals and cell != start:
                path = [cell]
                state = (cell, heading)
                while state in parent:
                    state = parent[state]
                    path.append(state[0])
                return path[::-1]
            if cost > best.get((cell, heading), 1e9) or cost > 700:
                continue
            for direction in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cell[0] + direction[0], cell[1] + direction[1])
                if not (6 <= nxt[0] <= max_x and 6 <= nxt[1] <= max_y):
                    continue
                if not self.passable(nxt, net):
                    continue
                step = 1 + (3 if heading is not None and direction != heading else 0)
                new_cost = cost + step
                state = (nxt, direction)
                if new_cost < best.get(state, 1e9):
                    best[state] = new_cost
                    parent[state] = (cell, heading)
                    heapq.heappush(queue, (new_cost + heuristic(nxt), new_cost, nxt, direction))
        return None

    def flush_edges(self, net):
        edges = self.edges.get(net, set())
        degree = {}
        for edge in edges:
            for cell in edge:
                degree[cell] = degree.get(cell, 0) + 1
        for cell, count in degree.items():
            if count >= 3:
                self.sheet.junctions.append((to_mm(cell[0]), to_mm(cell[1])))
        horizontal = {}
        vertical = {}
        for edge in edges:
            first, second = sorted(edge)
            if first[1] == second[1]:
                horizontal.setdefault(first[1], []).append(first[0])
            else:
                vertical.setdefault(first[0], []).append(first[1])
        for row, starts in horizontal.items():
            for run in runs(sorted(starts), lambda cell, row=row: (cell, row) in self.nodes):
                self.sheet.wires.append(((to_mm(run[0]), to_mm(row)), (to_mm(run[1] + 1), to_mm(row))))
        for column, starts in vertical.items():
            for run in runs(sorted(starts), lambda cell, column=column: (column, cell) in self.nodes):
                self.sheet.wires.append(((to_mm(column), to_mm(run[0])), (to_mm(column), to_mm(run[1] + 1))))
        self.edges[net] = set()


def runs(values, is_break=lambda cell: False):
    """Merge consecutive integer starts into (first, last) runs, splitting at break cells."""
    result = []
    for value in values:
        if result and value == result[-1][1] + 1 and not is_break(value):
            result[-1][1] = value
        else:
            result.append([value, value])
    return [tuple(item) for item in result]


def finalize(sheet):
    if sheet.handwired:
        sheet.no_connects.extend(part.pin_point(number) for part, number in sheet.ncs)
    else:
        layout = Layout(sheet)
        layout.place_auto()
        layout.route()
    import textlayout
    textlayout.place_text(sheet)
