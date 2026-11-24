"""Pre-route gate for a placed, unrouted board: decoupling distance, hot-loop
area, courtyard and edge checks, antenna keep-out, test points and edge order.

Needs only footprints, pads, nets, the outline and rule areas; no tracks or
zone fills. Run with KiCad's Python (it imports pcbnew):

    placement_gate.py [--board b.kicad_pcb] [--project p.kicad_pro]
                      [--json out.json] [--update-baseline]

Config (board_checks.json beside the project), all keys optional:

    "placement": {"power_nets": [...], "ground_nets": [...],
                  "edge_parts": [...], "antenna_modules": [...],
                  "topmost_on_edge": [...], "bottommost_on_edge": [...]}
    "hot_loops": {"<name>": ["U5.3", "C40.1", ...]}

A check that cannot run reports an info finding saying so.
"""

import argparse
import math
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import List, Tuple

import pcbnew

from findings import Config, Finding, Report, add_common_arguments

DECAP_WARN_MM = 5.0
DECAP_ERROR_MM = 8.0
DECAP_MISSING_MM = 10.0
LOOP_WARN_MM2 = 25.0
LOOP_ERROR_MM2 = 100.0
EDGE_WARN_MM = 1.0
EDGE_ERROR_MM = 0.5
EDGE_BAND_MM = 5.0
MIN_LOOP_POINTS = 3
GEOMETRY_EPS = 1e-6
DEFAULT_GROUND_NETS = ['GND*']

RULES = {
    'DECAP_DISTANCE': 'power pad to nearest same-net capacitor pad',
    'DECAP_MISSING': 'no capacitor on a power net near an IC power pad',
    'HOT_LOOP_AREA': 'area of the configured switching loops',
    'COURTYARD_OVERLAP': 'courtyards of two parts overlap on one side',
    'EDGE_CLEARANCE': 'courtyard too close to the board outline',
    'OFF_BOARD': 'part position outside the board outline',
    'ANTENNA_KEEPOUT': 'antenna module without keep-out or overhang',
    'TESTPOINT_MISSING': 'IC without a test point on one of its nets',
    'EDGE_ORDER': 'part not first or last along its board edge',
}

Point = Tuple[float, float]
Polygon = List[Point]


@dataclass
class Pad:
    ref: str
    number: str
    net: str
    pin_type: str
    pos: Point


@dataclass
class Part:
    ref: str
    pos: Point
    front: bool
    pads: List[Pad] = field(default_factory=list)
    courtyard: List[Polygon] = field(default_factory=list)


@dataclass
class RuleArea:
    poly: Polygon
    all_copper: bool
    blocks_copper: bool


@dataclass
class Layout:
    parts: List[Part]
    outline: List[Polygon]
    rule_areas: List[RuleArea]


# Geometry (mm, y down)


def polygon_area(points):
    """Absolute shoelace area of a polygon given by its vertices."""
    total = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def point_in_polygon(point, poly):
    """Ray-casting test; points on the boundary may land either way."""
    x, y = point
    inside = False
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) == (y2 > y):
            continue
        if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def segments_cross(p1, p2, q1, q2):
    """True when two segments cross properly (touching ends do not)."""
    d1, d2 = _cross(q1, q2, p1), _cross(q1, q2, p2)
    d3, d4 = _cross(p1, p2, q1), _cross(p1, p2, q2)
    return (
        ((d1 > GEOMETRY_EPS) != (d2 > GEOMETRY_EPS))
        and ((d3 > GEOMETRY_EPS) != (d4 > GEOMETRY_EPS))
        and min(abs(d1), abs(d2), abs(d3), abs(d4)) > GEOMETRY_EPS
    )


def _edges(poly):
    return [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]


def polygons_overlap(a, b):
    """True when two polygons share area (edges cross or one is inside)."""
    for p1, p2 in _edges(a):
        for q1, q2 in _edges(b):
            if segments_cross(p1, p2, q1, q2):
                return True
    return point_in_polygon(a[0], b) or point_in_polygon(b[0], a)


def point_segment_distance(point, start, end):
    """Distance from a point to a segment."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    t = 0.0
    if length2 > 0:
        t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2
        t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - start[0] - t * dx, point[1] - start[1] - t * dy)


def boundary_distance(a, b):
    """Smallest distance between the boundaries of two polygons; 0 if they
    cross.
    """
    for p1, p2 in _edges(a):
        for q1, q2 in _edges(b):
            if segments_cross(p1, p2, q1, q2):
                return 0.0
    best = math.inf
    for poly, other in ((a, b), (b, a)):
        for vertex in poly:
            for s, e in _edges(other):
                best = min(best, point_segment_distance(vertex, s, e))
    return best


def inside_outline(point, outline):
    """True when the point is inside any outline polygon."""
    return any(point_in_polygon(point, poly) for poly in outline)


# Board loading


def _poly_points(outline):
    return [
        (pcbnew.ToMM(outline.CPoint(i).x), pcbnew.ToMM(outline.CPoint(i).y))
        for i in range(outline.PointCount())
    ]


def _poly_set(poly_set):
    return [
        _poly_points(poly_set.Outline(i))
        for i in range(poly_set.OutlineCount())
    ]


def _load_part(footprint):
    front = footprint.GetLayer() == pcbnew.F_Cu
    ref = footprint.GetReference()
    pos = footprint.GetPosition()
    pads = []
    for pad in footprint.Pads():
        pad_pos = pad.GetPosition()
        pads.append(
            Pad(
                ref,
                pad.GetNumber(),
                pad.GetNetname(),
                str(pad.GetPinType()),
                (pcbnew.ToMM(pad_pos.x), pcbnew.ToMM(pad_pos.y)),
            )
        )
    footprint.BuildCourtyardCaches()
    layer = pcbnew.F_CrtYd if front else pcbnew.B_CrtYd
    return Part(
        ref,
        (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)),
        front,
        pads,
        _poly_set(footprint.GetCourtyard(layer)),
    )


def _load_rule_areas(board):
    copper = list(board.GetEnabledLayers().CuStack())
    areas = []
    for zone in board.Zones():
        if not zone.GetIsRuleArea():
            continue
        all_copper = all(zone.IsOnLayer(layer) for layer in copper)
        blocks = zone.GetDoNotAllowZoneFills() and zone.GetDoNotAllowTracks()
        for poly in _poly_set(zone.Outline()):
            areas.append(RuleArea(poly, all_copper, blocks))
    return areas


def load_layout(path):
    """Read the footprints, outline and rule areas of a board file."""
    board = pcbnew.LoadBoard(str(path))
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    return Layout(
        [_load_part(fp) for fp in board.GetFootprints()],
        _poly_set(outline),
        _load_rule_areas(board),
    )


# Helpers


def _matches(name, patterns):
    return any(fnmatchcase(name, p) for p in patterns)


def _is_ground(net, patterns):
    base = net.rsplit('/', 1)[-1]
    return _matches(net, patterns) or _matches(base, patterns)


def _prefix(ref):
    return ref.rstrip('0123456789')


def _info(rule_id, summary):
    return Finding(rule_id, 'info', 'measured', summary)


def _bounds(outline):
    xs = [x for poly in outline for x, _ in poly]
    ys = [y for poly in outline for _, y in poly]
    return min(xs), min(ys), max(xs), max(ys)


# Checks


def _power_pads(layout, placement):
    """The IC power pads: by pin type, else by the configured nets."""
    ics = [p for p in layout.parts if _prefix(p.ref) == 'U']
    typed = [
        pad
        for part in ics
        for pad in part.pads
        if 'power' in pad.pin_type.lower() and pad.net
    ]
    if typed or any(
        'power' in pad.pin_type.lower()
        for part in layout.parts
        for pad in part.pads
    ):
        return typed, None
    nets = placement.get('power_nets', [])
    note = (
        'board has no pad pin types; using placement.power_nets '
        f'({len(nets)} nets)'
    )
    pads = [
        pad for part in ics for pad in part.pads if pad.net in nets
    ]
    return pads, note


def check_decoupling(layout, config, report):
    """Distance from each IC power pad to the nearest capacitor pad on its
    net (pad centre to pad centre); no capacitor within the limit is
    missing decoupling. Ground nets are skipped.
    """
    placement = config.section('placement', {})
    ground = placement.get('ground_nets', DEFAULT_GROUND_NETS)
    pads, note = _power_pads(layout, placement)
    if note:
        report.add(_info('DECAP_DISTANCE', note))
    cap_pads = [
        pad
        for part in layout.parts
        if _prefix(part.ref) == 'C'
        for pad in part.pads
    ]
    for pad in pads:
        if _is_ground(pad.net, ground):
            continue
        _decap_pad(pad, cap_pads, report)


def _decap_pad(pad, cap_pads, report):
    same = [c for c in cap_pads if c.net == pad.net]
    nearest = min(
        same,
        key=lambda c: math.dist(pad.pos, c.pos),
        default=None,
    )
    where = f'{pad.ref}.{pad.number}'
    if nearest is None or math.dist(pad.pos, nearest.pos) > DECAP_MISSING_MM:
        report.add(
            Finding(
                'DECAP_MISSING',
                'error',
                'measured',
                f'no capacitor on {pad.net} within {DECAP_MISSING_MM:g} mm '
                f'of {where}',
                [pad.ref],
                [pad.net],
                pad.pos,
                'place a decoupling capacitor at the power pin',
            )
        )
        return
    distance = math.dist(pad.pos, nearest.pos)
    severity = (
        'error'
        if distance > DECAP_ERROR_MM
        else 'warning' if distance > DECAP_WARN_MM else None
    )
    if severity is None:
        return
    report.add(
        Finding(
            'DECAP_DISTANCE',
            severity,
            'measured',
            f'{nearest.ref}.{nearest.number} is {distance:.1f} mm from '
            f'{where} (limit {DECAP_WARN_MM:g}/{DECAP_ERROR_MM:g} mm)',
            [pad.ref, nearest.ref],
            [pad.net],
            pad.pos,
            'move the capacitor next to the power pin',
        )
    )


def _loop_points(layout, name, refs, report):
    """Pad centres for a loop's points, or None after reporting why."""
    pads = {(p.ref, pad.number): pad.pos for p in layout.parts for pad in p.pads}
    points = []
    for item in refs:
        ref, _, number = item.rpartition('.')
        if (ref, number) not in pads:
            report.add(
                Finding(
                    'HOT_LOOP_AREA',
                    'error',
                    'measured',
                    f'loop {name}: point {item} is not on the board',
                    [ref],
                )
            )
            return None
        points.append(pads[(ref, number)])
    if len(points) < MIN_LOOP_POINTS:
        report.add(
            Finding(
                'HOT_LOOP_AREA',
                'error',
                'measured',
                f'loop {name} has fewer than {MIN_LOOP_POINTS} points',
            )
        )
        return None
    return points


def check_hot_loops(layout, config, report):
    """Area of the polygon through each configured loop's pad centres."""
    loops = config.section('hot_loops', {})
    if not loops:
        report.add(
            _info('HOT_LOOP_AREA', 'no hot_loops configured; area not checked')
        )
        return
    for name, refs in loops.items():
        points = _loop_points(layout, name, refs, report)
        if points is None:
            continue
        area = polygon_area(points)
        severity = (
            'error'
            if area > LOOP_ERROR_MM2
            else 'warning' if area >= LOOP_WARN_MM2 else None
        )
        if severity is None:
            continue
        report.add(
            Finding(
                'HOT_LOOP_AREA',
                severity,
                'measured',
                f'loop {name} encloses {area:.1f} mm2 '
                f'(limit {LOOP_WARN_MM2:g}/{LOOP_ERROR_MM2:g} mm2)',
                sorted({r.rpartition('.')[0] for r in refs}),
                [],
                points[0],
                'tighten the loop: move the parts together',
            )
        )


def check_courtyard_overlap(layout, report):
    """Courtyards of two parts on the same side that overlap."""
    parts = [p for p in layout.parts if p.courtyard]
    missing = sorted(p.ref for p in layout.parts if not p.courtyard)
    if missing:
        report.add(
            Finding(
                'COURTYARD_OVERLAP',
                'info',
                'measured',
                f'{len(missing)} parts have no courtyard and were not '
                'checked',
                missing,
            )
        )
    for i, first in enumerate(parts):
        for second in parts[i + 1 :]:
            if first.front != second.front:
                continue
            if any(
                polygons_overlap(a, b)
                for a in first.courtyard
                for b in second.courtyard
            ):
                report.add(
                    Finding(
                        'COURTYARD_OVERLAP',
                        'error',
                        'measured',
                        f'courtyards of {first.ref} and {second.ref} overlap',
                        [first.ref, second.ref],
                        [],
                        first.pos,
                        'move one part',
                    )
                )


def _edge_distance(part, outline):
    return min(
        boundary_distance(poly, edge)
        for poly in part.courtyard
        for edge in outline
    )


def check_board_edge(layout, config, report):
    """Part positions inside the outline and courtyards clear of it.
    Footprints with no reference (mounting holes) are not parts.
    """
    skip = config.section('placement', {}).get('edge_parts', [])
    if not layout.outline:
        report.add(
            _info('OFF_BOARD', 'no board outline found; edge checks skipped')
        )
        return
    for part in layout.parts:
        if not inside_outline(part.pos, layout.outline):
            report.add(
                Finding(
                    'OFF_BOARD',
                    'error',
                    'measured',
                    f'{part.ref} is outside the board outline',
                    [part.ref],
                    [],
                    part.pos,
                    'move the part onto the board',
                )
            )
            continue
        if not part.ref or not part.courtyard or _matches(part.ref, skip):
            continue
        _edge_clearance(part, layout.outline, report)


def _edge_clearance(part, outline, report):
    distance = _edge_distance(part, outline)
    if distance >= EDGE_WARN_MM:
        return
    severity = 'error' if distance < EDGE_ERROR_MM else 'warning'
    report.add(
        Finding(
            'EDGE_CLEARANCE',
            severity,
            'measured',
            f'{part.ref} courtyard is {distance:.2f} mm from the outline '
            f'(limit {EDGE_WARN_MM:g}/{EDGE_ERROR_MM:g} mm)',
            [part.ref],
            [],
            part.pos,
            'move the part inward or list it in placement.edge_parts',
        )
    )


def _antenna_ok(part, layout):
    """Keep-out rule area over the module, or courtyard past the outline."""
    for area in layout.rule_areas:
        if not (area.all_copper and area.blocks_copper):
            continue
        if any(polygons_overlap(area.poly, c) for c in part.courtyard):
            return True
    return any(
        not inside_outline(vertex, layout.outline)
        for poly in part.courtyard
        for vertex in poly
    )


def check_antenna(layout, config, report):
    """Each antenna module needs an all-copper keep-out over it or must
    overhang the board edge (heuristic).
    """
    refs = config.section('placement', {}).get('antenna_modules', [])
    if not refs:
        report.add(
            _info(
                'ANTENNA_KEEPOUT',
                'no placement.antenna_modules configured; not checked',
            )
        )
        return
    by_ref = {p.ref: p for p in layout.parts}
    for ref in refs:
        part = by_ref.get(ref)
        if part is None or not part.courtyard:
            report.add(
                Finding(
                    'ANTENNA_KEEPOUT',
                    'error',
                    'heuristic',
                    f'{ref} not on the board or has no courtyard',
                    [ref],
                )
            )
        elif not _antenna_ok(part, layout):
            report.add(
                Finding(
                    'ANTENNA_KEEPOUT',
                    'error',
                    'heuristic',
                    f'{ref} has no all-layer keep-out and does not overhang '
                    'the edge',
                    [ref],
                    [],
                    part.pos,
                    'add a keep-out or cut-out under the antenna',
                )
            )


def check_testpoints(layout, config, report):
    """Each IC shares a non-ground net with at least one test point."""
    ground = config.section('placement', {}).get(
        'ground_nets', DEFAULT_GROUND_NETS
    )
    tp_nets = {
        pad.net
        for part in layout.parts
        if _prefix(part.ref) == 'TP'
        for pad in part.pads
    }
    for part in layout.parts:
        if _prefix(part.ref) != 'U':
            continue
        nets = {p.net for p in part.pads if p.net and not _is_ground(p.net, ground)}
        if nets & tp_nets:
            continue
        report.add(
            Finding(
                'TESTPOINT_MISSING',
                'warning',
                'heuristic',
                f'{part.ref} has no test point on any of its nets',
                [part.ref],
                [],
                part.pos,
                'add a test point on a supply or key signal',
            )
        )


def _nearest_edge(pos, bounds):
    left, top, right, bottom = bounds
    distances = {
        'left': pos[0] - left,
        'right': right - pos[0],
        'top': pos[1] - top,
        'bottom': bottom - pos[1],
    }
    edge = min(distances, key=distances.get)
    return edge, distances[edge], distances


def check_edge_order(layout, config, report):
    """Parts that must be first (topmost) or last (bottommost) along the
    left or right edge, as seen from the front; on the top or bottom edge
    the answer is fixed by the edge.
    """
    placement = config.section('placement', {})
    wanted = [(r, True) for r in placement.get('topmost_on_edge', [])] + [
        (r, False) for r in placement.get('bottommost_on_edge', [])
    ]
    if not wanted:
        report.add(
            _info('EDGE_ORDER', 'no edge-order parts configured; not checked')
        )
        return
    if not layout.outline:
        report.add(_info('EDGE_ORDER', 'no board outline found; not checked'))
        return
    bounds = _bounds(layout.outline)
    by_ref = {p.ref: p for p in layout.parts}
    for ref, topmost in wanted:
        part = by_ref.get(ref)
        if part is None:
            report.add(
                Finding(
                    'EDGE_ORDER',
                    'error',
                    'measured',
                    f'{ref} is not on the board',
                    [ref],
                )
            )
            continue
        _edge_order(part, topmost, layout, bounds, report)


def _edge_order(part, topmost, layout, bounds, report):
    edge, _, distances = _nearest_edge(part.pos, bounds)
    word = 'topmost' if topmost else 'bottommost'
    if edge in ('top', 'bottom'):
        if (edge == 'top') != topmost:
            report.add(
                Finding(
                    'EDGE_ORDER',
                    'error',
                    'measured',
                    f'{part.ref} must be {word} but sits on the {edge} edge',
                    [part.ref],
                    [],
                    part.pos,
                )
            )
        return
    sign = 1 if topmost else -1
    beaten = sorted(
        other.ref
        for other in layout.parts
        if other.ref
        and other.ref != part.ref
        and _nearest_edge(other.pos, bounds)[2][edge] < EDGE_BAND_MM
        and sign * (other.pos[1] - part.pos[1]) < 0
    )
    if not beaten:
        return
    side = 'above' if topmost else 'below'
    report.add(
        Finding(
            'EDGE_ORDER',
            'error',
            'measured',
            f'{part.ref} is not {word} on the {edge} edge; {side} it: '
            + ', '.join(beaten),
            [part.ref] + beaten,
            [],
            part.pos,
            f'move {part.ref} toward the {"top" if topmost else "bottom"}',
        )
    )


def run_checks(layout, config, report):
    """Run every check and add its findings to the report."""
    check_decoupling(layout, config, report)
    check_hot_loops(layout, config, report)
    check_courtyard_overlap(layout, report)
    check_board_edge(layout, config, report)
    check_antenna(layout, config, report)
    check_testpoints(layout, config, report)
    check_edge_order(layout, config, report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    add_common_arguments(parser)
    parser.add_argument('--board', help='the .kicad_pcb to check')
    args = parser.parse_args(argv)
    project = Path(args.project)
    board = Path(args.board) if args.board else project.with_suffix('.kicad_pcb')
    if not board.exists():
        sys.exit(f'board not found: {board}')
    config = Config.load(project.parent)
    report = Report('placement_gate', str(board), RULES)
    run_checks(load_layout(board), config, report)
    report.apply(config)
    report.print_text()
    if args.json:
        report.write_json(args.json)
    return report.exit_code(config, args.update_baseline)


if __name__ == '__main__':
    sys.exit(main())
