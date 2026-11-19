"""Block diagrams for the root and group sheets: sheet boxes with pins, placed
from a table, and a grid router that wires the pins net by net.

Everything is in schematic grid cells (1.27 mm). Wires run on every second
cell, so parallel wires sit 2.54 mm apart.
"""

import heapq
import re

STEP = 2
BEND_COST = 3
CROSS_COST = 6
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Router:
    """Routes nets one at a time on the wire grid.

    Wires of different nets may cross at right angles in the middle of both,
    which KiCad does not connect. They never share a segment, and never touch
    at a bend, an end or a junction.
    """

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.blocked = set()
        self.nodes = {}  # node -> {net: 'h' | 'v' | 'x'}
        self.edges = {}  # frozenset of two nodes -> net
        self.escapes = {}  # net -> escape nodes of its terminals

    def block(self, x0, y0, x1, y1):
        """Keeps wires out of a rectangle (edges included)."""
        for x in range(x0 - x0 % STEP, x1 + 1, STEP):
            for y in range(y0 - y0 % STEP, y1 + 1, STEP):
                self.blocked.add((x, y))

    def terminal(self, net, node, out):
        """Reserves a pin and the first step away from it, so a wire routed
        earlier can cross that step but not close the pin in.
        """
        escape = (node[0] + out[0] * STEP, node[1] + out[1] * STEP)
        self.blocked.add(node)
        self.blocked.discard(escape)
        self.nodes.setdefault(node, {})[net] = 'x'
        self.nodes.setdefault(escape, {})[net] = 'h' if out[0] else 'v'
        self.edges[frozenset((node, escape))] = net
        self.escapes.setdefault(net, set()).add(escape)

    def others(self, node, net):
        return [kind for name, kind in self.nodes.get(node, {}).items() if name != net]

    def search(self, net, starts, pin_goals, tree_goals):
        """A* from any of the start ends to an open end of the net, or onto
        its routed line.
        """
        goals = list(pin_goals) + list(tree_goals)
        origin = {node for node, _ in starts}

        def remaining(node):
            return min(
                abs(node[0] - x) + abs(node[1] - y) for x, y in goals
            ) // STEP

        queue = [(remaining(node), 0, node, out, None) for node, out in starts]
        heapq.heapify(queue)
        best = {}
        came = {}
        while queue:
            _, cost, node, heading, parent = heapq.heappop(queue)
            state = (node, heading)
            if state in came:
                continue
            came[state] = parent
            if node not in origin and (node in pin_goals or node in tree_goals):
                path = [node]
                while parent is not None:
                    path.append(parent[0])
                    parent = came[parent]
                return path[::-1]
            crossing = bool(self.others(node, net))
            for step in DIRECTIONS:
                if step == (-heading[0], -heading[1]):
                    continue
                if (node in origin or crossing) and step != heading:
                    continue
                target = (node[0] + step[0] * STEP, node[1] + step[1] * STEP)
                if not (0 < target[0] < self.width and 0 < target[1] < self.height):
                    continue
                if self.edges.get(frozenset((node, target)), net) != net:
                    continue
                across = 'v' if step[0] else 'h'
                foreign = self.others(target, net)
                if target in origin:
                    continue
                if target in pin_goals:
                    if step != pin_goals[target]:
                        continue
                elif target in tree_goals:
                    # join the net's own line as a T, square on
                    if foreign or tree_goals[target] != across:
                        continue
                elif target in self.blocked:
                    continue
                elif any(kind != across for kind in foreign):
                    continue
                elif net in self.nodes.get(target, {}) and (
                    target not in self.escapes[net]
                ):
                    continue
                price = cost + 1 + CROSS_COST * len(foreign)
                if step != heading:
                    price += BEND_COST
                key = (target, step)
                if price < best.get(key, 1e9):
                    best[key] = price
                    heapq.heappush(
                        queue,
                        (price + remaining(target), price, target, step, state),
                    )
        return None

    def commit(self, net, path):
        for index, node in enumerate(path):
            kind = 'x'
            if 0 < index < len(path) - 1:
                before, after = path[index - 1], path[index + 1]
                if before[0] == after[0]:
                    kind = 'v'
                elif before[1] == after[1]:
                    kind = 'h'
            self.nodes.setdefault(node, {})[net] = kind
        for first, second in zip(path, path[1:]):
            self.edges[frozenset((first, second))] = net

    def route(self, net, terminals):
        """Joins a net's terminals. Each terminal is a list of alternative
        ends, (node, outward step) each, of which one or more get used (a bus
        tap column can be entered at the top and left at the bottom). Returns
        the polylines as corner cells, and the points where a line ends in a T
        on an earlier one.
        """
        lines, joins = [], []
        tree = {}
        open_ends = {node: (-out[0], -out[1]) for node, out in terminals[0]}
        for ends in terminals[1:]:
            path = self.search(net, ends, open_ends, tree)
            if path is None:
                raise RuntimeError(f'block diagram: no route for {net} from {ends[0][0]}')
            self.commit(net, path)
            if path[-1] in open_ends:
                del open_ends[path[-1]]
            else:
                joins.append(path[-1])
            for node, out in ends:
                if node != path[0]:
                    open_ends[node] = (-out[0], -out[1])
            for position, kind in self.nodes.items():
                if kind.get(net) in ('h', 'v') and position not in self.escapes[net]:
                    tree[position] = kind[net]
            lines.append(corners(path))
        return lines, joins


def corners(path):
    """Drops the points in the middle of a straight run."""
    kept = [path[0]]
    for before, node, after in zip(path, path[1:], path[2:]):
        if (before[0] == node[0]) != (node[0] == after[0]):
            kept.append(node)
    kept.append(path[-1])
    return kept


def box_height(left, right):
    return max(8, 2 * max(left, right) + 2)


def arrange(boxes, fixed, nets, width):
    """Chooses a side and a row for every sheet pin.

    boxes: name -> (column, row, box width). fixed: net -> [(cell, outward
    step)] for terminals that are not sheet pins. nets: net -> box names.
    Returns name -> (height, [(net, cell, 'left' | 'right')]).
    A pin faces the rest of its net, and pins on one side are ordered by where
    their wires go, which keeps crossings down.
    """
    place = {}  # (box, net) -> cell
    for name, (column, row, box_width) in boxes.items():
        for net, names in nets.items():
            if name in names:
                place[(name, net)] = (column + box_width // 2, row + 4)
    result = {}
    for _ in range(3):
        for name, (column, row, box_width) in boxes.items():
            centre = column + box_width / 2
            sides = {'left': [], 'right': []}
            for net, names in nets.items():
                if name not in names:
                    continue
                # other sheets' pins decide; the sheet's own terminals only
                # when no other box carries the net
                ends = [place[(other, net)] for other in names if other != name]
                own = [cell for cell, _ in fixed.get(net, [])]
                if not ends or (net.startswith('{') and own):
                    # a bus pin faces the edge the bus comes in from
                    ends = own
                mean_x = sum(x for x, _ in ends) / len(ends)
                mean_y = sum(y for _, y in ends) / len(ends)
                sides['left' if mean_x < centre else 'right'].append((mean_y, net))
            height = box_height(len(sides['left']), len(sides['right']))
            pins = []
            for side, entries in sides.items():
                x = column if side == 'left' else column + box_width
                for index, (_, net) in enumerate(sorted(entries)):
                    cell = (x, row + 2 + 2 * index)
                    place[(name, net)] = cell
                    pins.append((net, cell, side))
            result[name] = (height, pins)
    return result


def natural(text):
    """Sort key that puts IO2 before IO10."""
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', text)]


def one_side(boxes, nets, width):
    """Pins for a diagram whose boxes tap a bus: every pin of a box on the
    side that faces the middle of the sheet, in name order, with bus pins
    (names in braces) last after a gap. Same result shape as arrange().
    """
    result = {}
    for name, (column, row, box_width) in boxes.items():
        side = 'right' if column + box_width / 2 < width / 2 else 'left'
        x = column + box_width if side == 'right' else column
        own = sorted((net for net, names in nets.items() if name in names), key=natural)
        signals = [net for net in own if not net.startswith('{')]
        buses = [net for net in own if net.startswith('{')]
        pins = [(net, (x, row + 2 + 2 * index), side) for index, net in enumerate(signals)]
        top = row + 2 + 2 * len(signals) + (2 if signals else 0)
        pins += [(net, (x, top + 2 * index), side) for index, net in enumerate(buses)]
        height = max(8, pins[-1][1][1] - row + 2) if pins else 8
        result[name] = (height, pins)
    return result


def tap_column(ends, step):
    """Bus tap column for wire ends that share a column: each end gets a
    45-degree entry down onto a vertical bus two cells away (step +1 to the
    right, -1 to the left). Returns the entries as (x, y, dx, dy), the bus
    as two cells, and its top and bottom as router ends.
    """
    column = ends[0][0] + 2 * step
    rows = sorted(row for _, row in ends)
    entries = [(x, y, 2 * step, 2) for x, y in ends]
    top, bottom = (column, rows[0]), (column, rows[-1] + 2)
    return entries, (top, bottom), [(top, (0, -1)), (bottom, (0, 1))]


def preview(path, width, height, boxes, pins, lines, buses, blocked, scale=5):
    """Draws a block diagram to a PNG for checking a layout without KiCad.
    boxes: name -> (column, row, width, height).
    """
    from PIL import Image, ImageDraw

    image = Image.new('RGB', (width * scale, height * scale), 'white')
    draw = ImageDraw.Draw(image)
    for x, y in blocked:
        draw.point((x * scale, y * scale), fill=(215, 215, 215))
    for name, (column, row, box_width, box_height) in boxes.items():
        draw.rectangle(
            (column * scale, row * scale, (column + box_width) * scale,
             (row + box_height) * scale),
            outline=(150, 0, 0),
        )
        draw.text((column * scale, (row - 2) * scale - 4), name, fill=(0, 100, 100))
        for net, (x, y), side in pins[name][1]:
            offset = 3 if side == 'left' else -6 * len(net) - 3
            draw.text((x * scale + offset, y * scale - 5), net, fill=(0, 0, 0))
    for line in lines:
        draw.line([(x * scale, y * scale) for x, y in line], fill=(0, 140, 0), width=1)
    for line in buses:
        draw.line([(x * scale, y * scale) for x, y in line], fill=(0, 0, 200), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
