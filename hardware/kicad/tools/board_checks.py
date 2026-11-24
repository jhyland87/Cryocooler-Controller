"""Electrical and physical checks on a routed KiCad board.

Loads the board, refills the zones in memory (the file is never saved), then
runs six checks and prints the findings:

  RETURN_PATH_GAP / REFERENCE_CHANGE  fast-net tracks over a 3 mm or longer gap
                                      in their plane (a via's own antipad is
                                      not a gap); reference-plane changes
  VIA_NO_GROUND_VIA                   fast-net vias that change layer to or from
                                      B.Cu with no ground via or pad within 3 mm
  TRACE_CURRENT                       locked current copper against its current,
                                      other tracks against their class width
  THERMAL_PAD_VIAS                    exposed pads with too few vias
  NET_OPEN                            nets split into several copper islands
  MASK_TEXT_OVERLAP                   overlapping text on a solder mask layer

Settings come from board_checks.json beside the .kicad_pro (see findings.py):
  "ground_nets", "power_nets"          net names or globs
  "net_currents": {"<net glob>": A}    amps each net must carry
  "fast_signals": {"classes": [...], "nets": [...]}  nets the return-path and
                                       ground-via checks apply to
  "ground_via": {"reach_mm": 3}, "return_path": {"min_gap_mm": 3}
  "board": {"reference_layers": {"F.Cu": "In1.Cu", ...}, "temp_rise_c": 10}

Trace capacity uses IPC-2221 section 6.2, I = k * dT**0.44 * A**0.725 with A in
mil^2 and k = 0.048 (outer) or 0.024 (inner). It is conservative against
IPC-2152, which credits the board's heat spreading.

Run with KiCad's bundled Python (it has pcbnew):
  board_checks.py [--board b.kicad_pcb] [--project p.kicad_pro] [--json out]
                  [--update-baseline] [--no-refill]
"""

import argparse
import math
import re
import sys
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path

import pcbnew

from findings import Config, Finding, Report, add_common_arguments

SAMPLE_STEP_MM = 0.25
MIN_GAP_MM = 3.0
REFERENCE_REACH_MM = 0.5
MIN_VIA_REACH_MM = 1.0
GROUND_VIA_REACH_MM = 3.0
VIA_REACH_FACTOR = 2.0
DEFAULT_TEMP_RISE_C = 10.0
DEFAULT_COPPER_UM = 35.0
IPC_K_OUTER = 0.048
IPC_K_INNER = 0.024
CURRENT_MARGIN = 1.25
VIA_AMPS = 1.0  # assumed per 0.7/0.35 mm via (see rev7_current.py)
ANTIPAD_TOLERANCE_MM = 0.05
PAD_MIN_AREA_MM2 = 4.0
PAD_EXPOSED_RATIO = 2.0
PAD_REF_DRILL_MM = 0.3
PAD_SMALL_MM2 = 10.0
PAD_MEDIUM_MM2 = 25.0
PAD_VIAS_SMALL = 5.0
PAD_VIAS_MEDIUM = 9.0
PAD_VIAS_PER_MM2 = 0.5
GROUND_HINTS = ('GND', 'VSS')

RULES = {
    'RETURN_PATH_GAP': 'signal track lacks plane copper within reach',
    'REFERENCE_CHANGE': 'net changes reference plane net',
    'VIA_NO_GROUND_VIA': 'signal via without a nearby ground via',
    'TRACE_CURRENT': 'track too narrow for its current',
    'THERMAL_PAD_VIAS': 'exposed pad with too few thermal vias',
    'NET_OPEN': 'net in more than one copper island',
    'MASK_TEXT_OVERLAP': 'overlapping text on a mask layer',
}


def mm(value):
    return pcbnew.ToMM(value)


def point(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def xy(vector):
    return (mm(vector.x), mm(vector.y))


def matches(name, patterns):
    return any(fnmatchcase(name, p) for p in patterns)


def is_trace(item):
    return item.Type() in (pcbnew.PCB_TRACE_T, pcbnew.PCB_ARC_T)


def is_via(item):
    return item.Type() == pcbnew.PCB_VIA_T


def parse_stackup(path):
    """Read the (stackup ...) block of a .kicad_pcb as an ordered list of
    ('copper', layer name, mm) and ('dielectric', None, mm) entries. pcbnew's
    Python API does not expose the stackup. Returns None if there is none.
    """
    text = Path(path).read_text()
    start = text.find('(stackup')
    if start < 0:
        return None
    depth, end = 0, start
    for index in range(start, len(text)):
        depth += {'(': 1, ')': -1}.get(text[index], 0)
        if depth == 0:
            end = index
            break
    block = text[start:end]
    entries = []
    parts = re.split(r'\(layer\s+"', block)[1:]
    for part in parts:
        name = part.split('"', 1)[0]
        kind = re.search(r'\(type\s+"([^"]*)"', part)
        thick = re.search(r'\(thickness\s+([0-9.]+)', part)
        if not kind or not thick:
            continue
        kind = kind.group(1).lower()
        if kind == 'copper':
            entries.append(('copper', name, float(thick.group(1))))
        elif not any(w in kind for w in ('silk', 'paste', 'mask')):
            entries.append(('dielectric', None, float(thick.group(1))))
    return entries or None


class Stackup:
    """Copper and dielectric thicknesses from the board's stackup."""

    def __init__(self, entries):
        self.entries = entries

    def copper_mm(self, layer):
        """Copper thickness of a layer by name, or None."""
        for kind, name, thick in self.entries:
            if kind == 'copper' and name == layer:
                return thick
        return None

    def dielectric_mm(self, layer_a, layer_b):
        """Total dielectric thickness between two copper layers, or None."""
        names = [n for k, n, _ in self.entries if k == 'copper']
        if layer_a not in names or layer_b not in names:
            return None
        inside, total = False, 0.0
        for kind, name, thick in self.entries:
            if kind == 'copper' and name in (layer_a, layer_b):
                if inside:
                    return total
                inside = True
            elif kind == 'dielectric' and inside:
                total += thick
        return None


class Context:
    """The board plus the settings and derived sets the checks share."""

    def __init__(self, board, config, board_path):
        self.board = board
        self.config = config
        entries = parse_stackup(board_path)
        self.stackup = Stackup(entries) if entries else None
        self.zone_nets = {
            z.GetNetname()
            for z in board.Zones()
            if not z.GetIsRuleArea() and z.GetNetname()
        }
        self.ground_patterns = list(config.section('ground_nets', []))
        self.power_patterns = list(config.section('power_nets', []))
        settings = config.section('board', {})
        self.reference_layers = self._reference_layers(settings)
        self.temp_rise = float(settings.get('temp_rise_c', DEFAULT_TEMP_RISE_C))

    def _reference_layers(self, settings):
        inner = [
            self.board.GetLayerName(layer_id)
            for layer_id in self.board.GetEnabledLayers().Seq()
            if pcbnew.IsCopperLayer(layer_id)
            and layer_id not in (pcbnew.F_Cu, pcbnew.B_Cu)
        ]
        pairs = {}
        if inner:
            pairs = {'F.Cu': inner[0], 'B.Cu': inner[-1]}
        pairs.update(settings.get('reference_layers', {}))
        return pairs

    def is_ground(self, net):
        if matches(net, self.ground_patterns):
            return True
        return net in self.zone_nets and any(
            h in net.upper() for h in GROUND_HINTS
        )

    def is_plane(self, net):
        """True for a net that owns a zone or is configured as power or
        ground.
        """
        return (
            net in self.zone_nets
            or self.is_ground(net)
            or matches(net, self.power_patterns)
        )

    def layer_id(self, name):
        return self.board.GetLayerID(name)


def signal_traces(ctx, outer_only=False):
    outer = (pcbnew.F_Cu, pcbnew.B_Cu)
    for item in ctx.board.GetTracks():
        if not is_trace(item) or not item.GetNetname():
            continue
        if ctx.is_plane(item.GetNetname()):
            continue
        if outer_only and item.GetLayer() not in outer:
            continue
        yield item


def sample_points(start, end):
    length = math.dist(start, end)
    count = max(1, math.ceil(length / SAMPLE_STEP_MM))
    return [
        (
            start[0] + (end[0] - start[0]) * i / count,
            start[1] + (end[1] - start[1]) * i / count,
        )
        for i in range(count + 1)
    ]


def plane_polys(ctx, layer_name):
    """[(net, filled polygons)] of the filled zones on a layer."""
    layer = ctx.layer_id(layer_name)
    return [
        (z.GetNetname(), z.GetFilledPolysList(layer))
        for z in ctx.board.Zones()
        if not z.GetIsRuleArea() and z.IsOnLayer(layer)
    ]


def reference_net_at(polys, pos):
    """Net of the plane copper within reach of pos, or None."""
    reach = pcbnew.FromMM(REFERENCE_REACH_MM)
    vec = point(*pos)
    for net, poly in polys:
        if poly.Collide(vec, reach):
            return net
    return None


def gap_runs(flags, points):
    """[(length mm, midpoint)] of each run of uncovered samples."""
    runs, run = [], []
    for covered, pos in zip(flags + [True], points + [None]):
        if covered:
            if run:
                runs.append((len(run) * SAMPLE_STEP_MM, run[len(run) // 2]))
            run = []
        else:
            run.append(pos)
    return runs


def segment_coverage(polys, track):
    points = sample_points(xy(track.GetStart()), xy(track.GetEnd()))
    nets = [reference_net_at(polys, p) for p in points]
    return points, nets


def antipads(ctx, ref):
    """{net: [(x, y, radius mm)]}: each through via's hole in the reference
    layer's copper, the via radius plus the zone clearance.
    """
    layer = ctx.layer_id(ref)
    zones = [
        z for z in ctx.board.Zones()
        if not z.GetIsRuleArea() and z.IsOnLayer(layer)
    ]
    clearance = max((mm(z.GetLocalClearance()) for z in zones), default=0.0)
    found = {}
    for via in ctx.board.GetTracks():
        if not is_via(via) or not via.IsOnLayer(layer):
            continue
        radius = mm(via.GetWidth(pcbnew.F_Cu)) / 2
        pos = xy(via.GetPosition())
        found.setdefault(via.GetNetname(), []).append(
            (*pos, radius + clearance + ANTIPAD_TOLERANCE_MM)
        )
    return found


def in_antipad(holes, pos):
    return any(math.dist(pos, h[:2]) <= h[2] for h in holes)


def check_return_path(ctx, report):
    """Fast-net runs on outer-layer tracks, sampled every SAMPLE_STEP_MM, with
    no plane copper of the reference layer within 0.5 mm for min_gap_mm or
    more. A sample inside the antipad of a via of the net itself is covered.
    REFERENCE_CHANGE covers every signal net.
    """
    min_gap = float(
        ctx.config.section('return_path', {}).get('min_gap_mm', MIN_GAP_MM)
    )
    polys = {}
    holes = {}
    refs = {}
    gaps = {}
    for track in signal_traces(ctx, outer_only=True):
        layer = ctx.board.GetLayerName(track.GetLayer())
        ref = ctx.reference_layers.get(layer)
        if ref is None:
            report.add(
                Finding(
                    'RETURN_PATH_GAP', 'info', 'measured',
                    f'no reference layer for {layer}; its tracks were not '
                    'checked',
                )
            )
            ctx.reference_layers[layer] = False
            continue
        if ref is False:
            continue
        if ref not in polys:
            polys[ref] = plane_polys(ctx, ref)
            holes[ref] = antipads(ctx, ref)
        net = track.GetNetname()
        points, nets = segment_coverage(polys[ref], track)
        used = Counter(n for n in nets if n)
        if used:
            refs.setdefault(net, set()).add(used.most_common(1)[0][0])
        if not is_fast_net(ctx, net):
            continue
        own = holes[ref].get(net, [])
        covered = [
            n is not None or in_antipad(own, p) for n, p in zip(nets, points)
        ]
        for length, where in gap_runs(covered, points):
            if length >= min_gap:
                gaps.setdefault(net, []).append((length, where, layer, ref))
    for net, used in sorted(refs.items()):
        if len(used) > 1:
            report.add(
                Finding(
                    'REFERENCE_CHANGE', 'info', 'measured',
                    'reference plane changes between runs: '
                    + ', '.join(sorted(used)),
                    nets=[net],
                )
            )
    for net, found in sorted(gaps.items()):
        for length, where, layer, ref in found:
            report.add(
                Finding(
                    'RETURN_PATH_GAP', 'warning', 'measured',
                    f'{length:.1f} mm of {layer} track has no plane copper '
                    f'within {REFERENCE_REACH_MM} mm on {ref}',
                    nets=[net], at=where,
                    fix='route the net over unbroken plane or fill the gap',
                )
            )


def via_layers(ctx, via):
    """Outer layers where the via's net has a track ending at the via."""
    pos, radius = xy(via.GetPosition()), mm(via.GetWidth(pcbnew.F_Cu)) / 2
    layers = set()
    for track in ctx.board.GetTracks():
        if not is_trace(track) or track.GetNetname() != via.GetNetname():
            continue
        ends = (xy(track.GetStart()), xy(track.GetEnd()))
        if any(math.dist(pos, e) <= radius for e in ends):
            layers.add(ctx.board.GetLayerName(track.GetLayer()))
    return layers & {'F.Cu', 'B.Cu'} or {'F.Cu'}


def via_reach_mm(ctx, via):
    """Distance a ground via may be from a signal via: twice the dielectric
    height to the reference plane, at least MIN_VIA_REACH_MM.
    """
    if ctx.stackup is None:
        return MIN_VIA_REACH_MM
    heights = [
        ctx.stackup.dielectric_mm(layer, ctx.reference_layers.get(layer))
        for layer in via_layers(ctx, via)
    ]
    heights = [h for h in heights if h]
    return max(VIA_REACH_FACTOR * max(heights, default=0), MIN_VIA_REACH_MM)


def vias_without_ground_via(ctx):
    """[(via, reach in mm)] for signal vias with no ground-net via within
    twice the dielectric height. finish_route.py --stitch uses this (a
    tighter rule than the check's).
    """
    vias = [v for v in ctx.board.GetTracks() if is_via(v)]
    ground = [
        xy(v.GetPosition()) for v in vias if ctx.is_ground(v.GetNetname())
    ]
    failing = []
    for via in vias:
        net = via.GetNetname()
        if not net or ctx.is_plane(net):
            continue
        reach = via_reach_mm(ctx, via)
        pos = xy(via.GetPosition())
        if not any(math.dist(pos, g) <= reach for g in ground):
            failing.append((via, reach))
    return failing


def copper_order(ctx):
    """Copper layer names from F.Cu to B.Cu."""
    ids = [
        i for i in ctx.board.GetEnabledLayers().Seq() if pcbnew.IsCopperLayer(i)
    ]
    ids.sort(key=lambda i: (i != pcbnew.F_Cu, i == pcbnew.B_Cu, i))
    return [ctx.board.GetLayerName(i) for i in ids]


def via_net_layers(ctx, via):
    """Copper layers where the via's net has a track ending at the via, or an
    SMD pad over it.
    """
    net = via.GetNetname()
    pos, radius = xy(via.GetPosition()), mm(via.GetWidth(pcbnew.F_Cu)) / 2
    layers = set()
    for track in ctx.board.GetTracks():
        if not is_trace(track) or track.GetNetname() != net:
            continue
        ends = (xy(track.GetStart()), xy(track.GetEnd()))
        if any(math.dist(pos, e) <= radius for e in ends):
            layers.add(ctx.board.GetLayerName(track.GetLayer()))
    for pad in ctx.board.GetPads():
        if pad.GetNetname() != net or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        if pad.HitTest(point(*pos)):
            layers.update(
                ctx.board.GetLayerName(i) for i in pad.GetLayerSet().Seq()
                if pcbnew.IsCopperLayer(i)
            )
    return layers


def ground_plane_layers(ctx, pos, radius):
    """Copper layer names whose ground zone covers pos; reach spans the via's
    own antipad (radius plus zone clearance) and REFERENCE_REACH_MM.
    """
    vec = point(*pos)
    found = set()
    for zone in ctx.board.Zones():
        if zone.GetIsRuleArea() or not ctx.is_ground(zone.GetNetname()):
            continue
        reach = pcbnew.FromMM(
            radius + mm(zone.GetLocalClearance()) + REFERENCE_REACH_MM
        )
        for name in copper_order(ctx):
            layer = ctx.layer_id(name)
            if zone.IsOnLayer(layer) and zone.GetFilledPolysList(layer).Collide(vec, reach):
                found.add(name)
    return found


def keeps_reference(ctx, via, layers):
    """True if every layer is directly beside one solid ground plane at the
    via, so the return current stays on that plane.
    """
    order = copper_order(ctx)
    pos, radius = xy(via.GetPosition()), mm(via.GetWidth(pcbnew.F_Cu)) / 2
    for plane in ground_plane_layers(ctx, pos, radius):
        at = order.index(plane)
        if layers <= set(order[max(at - 1, 0):at + 2]) - {plane}:
            return True
    return False


def is_fast_net(ctx, net):
    """True if the net is in a fast class or named in "fast_signals"."""
    fast = ctx.config.section('fast_signals', {})
    if matches(net, fast.get('nets', [])):
        return True
    classes = (
        ctx.board.GetDesignSettings().m_NetSettings
        .GetEffectiveNetClass(net).GetName().split(',')
    )
    return any(c in fast.get('classes', []) for c in classes)


def vias_missing_ground(ctx):
    """([(via, reach mm)], exempt) for fast-net vias that change layer to or
    from B.Cu (or between layers without a shared ground plane) and have no
    ground via or ground through-hole pad within reach. exempt counts the
    other signal vias by reason: 'same_plane', 'no_change', 'slow'.
    """
    reach = float(
        ctx.config.section('ground_via', {}).get('reach_mm', GROUND_VIA_REACH_MM)
    )
    vias = [v for v in ctx.board.GetTracks() if is_via(v)]
    ground = [xy(v.GetPosition()) for v in vias if ctx.is_ground(v.GetNetname())]
    ground += [
        xy(p.GetPosition()) for p in ctx.board.GetPads()
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and ctx.is_ground(p.GetNetname())
    ]
    failing, exempt = [], Counter()
    for via in vias:
        net = via.GetNetname()
        if not net or ctx.is_plane(net):
            continue
        layers = via_net_layers(ctx, via)
        if len(layers) < 2:
            exempt['no_change'] += 1
        elif keeps_reference(ctx, via, layers):
            exempt['same_plane'] += 1
        elif not is_fast_net(ctx, net):
            exempt['slow'] += 1
        elif not any(math.dist(xy(via.GetPosition()), g) <= reach for g in ground):
            failing.append((via, reach))
    return failing, exempt


def check_via_ground(ctx, report):
    """Fast-net vias that change layer without a shared ground plane (any
    change to or from B.Cu) and have no ground via within reach.
    """
    failing, _ = vias_missing_ground(ctx)
    for via, reach in failing:
        report.add(
            Finding(
                'VIA_NO_GROUND_VIA', 'warning', 'measured',
                f'no ground via within {reach:.1f} mm of this fast-net via',
                nets=[via.GetNetname()], at=xy(via.GetPosition()),
                fix='add a ground via beside it (finish_route.py --stitch)',
            )
        )


def copper_um(ctx, layer_name):
    if ctx.stackup is not None:
        thick = ctx.stackup.copper_mm(layer_name)
        if thick:
            return thick * 1000.0, True
    return DEFAULT_COPPER_UM, False


def ipc2221_amps(width_mm, thick_um, rise_c, outer):
    """Current in A a track of this size carries at the given rise."""
    area_mil2 = (width_mm / 0.0254) * (thick_um / 25.4)
    k = IPC_K_OUTER if outer else IPC_K_INNER
    return k * rise_c**0.44 * area_mil2**0.725


def net_traces(ctx, net):
    return [
        t for t in ctx.board.GetTracks()
        if is_trace(t) and t.GetNetname() == net
    ]


def point_segment_mm(pos, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if not length2:
        return math.dist(pos, start)
    t = ((pos[0] - start[0]) * dx + (pos[1] - start[1]) * dy) / length2
    t = max(0.0, min(1.0, t))
    return math.dist(pos, (start[0] + t * dx, start[1] + t * dy))


def crosses(a0, a1, b0, b1):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return (
        side(a0, a1, b0) * side(a0, a1, b1) < 0
        and side(b0, b1, a0) * side(b0, b1, a1) < 0
    )


def track_ends(track):
    return xy(track.GetStart()), xy(track.GetEnd())


def tracks_overlap(a, b):
    """True if two tracks overlap in plan."""
    (a0, a1), (b0, b1) = track_ends(a), track_ends(b)
    if crosses(a0, a1, b0, b1):
        return True
    gap = min(
        point_segment_mm(a0, b0, b1), point_segment_mm(a1, b0, b1),
        point_segment_mm(b0, a0, a1), point_segment_mm(b1, a0, a1),
    )
    return gap < (mm(a.GetWidth()) + mm(b.GetWidth())) / 2


def via_joins(via, track):
    start, end = track_ends(track)
    return point_segment_mm(xy(via.GetPosition()), start, end) <= (
        mm(track.GetWidth()) / 2
    )


def track_capacity(ctx, track):
    """(capacity in A, copper um, from stackup) of one track on its own."""
    layer = ctx.board.GetLayerName(track.GetLayer())
    outer = track.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)
    thick, from_stackup = copper_um(ctx, layer)
    amps = ipc2221_amps(mm(track.GetWidth()), thick, ctx.temp_rise, outer)
    return amps, thick, from_stackup


def paired_capacity(ctx, track, locked, vias):
    """Capacity of a locked track plus the locked tracks of the net on other
    layers that overlap it, the extra limited by the joining vias.
    """
    own = track_capacity(ctx, track)
    partners = [
        t for t in locked
        if t.GetLayer() != track.GetLayer() and tracks_overlap(track, t)
    ]
    joined = {
        id(v) for v in vias
        if via_joins(v, track) and any(via_joins(v, t) for t in partners)
    }
    other = sum(track_capacity(ctx, t)[0] for t in partners)
    amps = own[0] + min(other, VIA_AMPS * len(joined))
    return amps, own[1], own[2], len(partners), len(joined)


def check_trace_current(ctx, report):
    """Locked tracks of each net with a configured current carry the full
    current (layers joined by vias add); its other tracks only need their
    net class width. A net with no locked copper is tested by its narrowest
    track. Zone copper on the net is noted, not credited.
    """
    currents = ctx.config.section('net_currents', {})
    if not currents:
        report.add(
            Finding(
                'TRACE_CURRENT', 'info', 'measured',
                'did not run: no "net_currents" in board_checks.json',
            )
        )
        return
    nets = sorted({t.GetNetname() for t in ctx.board.GetTracks()})
    used_default = False
    for net in nets:
        pattern = next((p for p in currents if fnmatchcase(net, p)), None)
        if pattern is None:
            continue
        tracks = net_traces(ctx, net)
        if not tracks:
            continue
        need = float(currents[pattern])
        locked = [t for t in tracks if t.IsLocked()]
        if not locked:
            narrow = min(tracks, key=lambda t: t.GetWidth())
            used_default |= report_current(ctx, report, net, narrow, need)
            continue
        vias = [
            v for v in ctx.board.GetTracks()
            if is_via(v) and v.GetNetname() == net
        ]
        weakest = min(
            locked, key=lambda t: paired_capacity(ctx, t, locked, vias)[0]
        )
        used_default |= report_current(
            ctx, report, net, weakest, need,
            pair=paired_capacity(ctx, weakest, locked, vias),
        )
        used_default |= report_class_width(
            ctx, report, net, [t for t in tracks if not t.IsLocked()]
        )
    if used_default:
        report.add(
            Finding(
                'TRACE_CURRENT', 'info', 'measured',
                f'no copper thickness in the stackup; used '
                f'{DEFAULT_COPPER_UM:g} um',
            )
        )


def has_zone(ctx, net):
    return any(
        z.GetNetname() == net and not z.GetIsRuleArea()
        for z in ctx.board.Zones()
    )


def report_current(ctx, report, net, track, need, pair=None):
    """Add a finding if the track (with the parallel layer and vias in
    pair, from paired_capacity) is too narrow; True if the copper thickness
    was the default.
    """
    layer = ctx.board.GetLayerName(track.GetLayer())
    width = mm(track.GetWidth())
    if pair is None:
        capacity, thick, from_stackup = track_capacity(ctx, track)
        what = f'narrowest track {width:.3f} mm on {layer}'
        note = ''
    else:
        capacity, thick, from_stackup, parallel, via_count = pair
        what = f'locked track {width:.3f} mm on {layer}'
        if parallel:
            what += (
                f' with {parallel} parallel track(s) joined by '
                f'{via_count} via(s)'
            )
        note = f'; assumed {VIA_AMPS:g} A per via'
    if capacity >= need * CURRENT_MARGIN:
        return not from_stackup
    if has_zone(ctx, net):
        note += '; zone copper on the net is not credited'
    report.add(
        Finding(
            'TRACE_CURRENT',
            'error' if capacity < need else 'warning',
            'measured',
            f'{what} carries {capacity:.2f} A at {ctx.temp_rise:g} C rise '
            f'(IPC-2221, {thick:g} um copper); needs {need:g} A{note}',
            nets=[net], at=xy(track.GetCenter()),
            fix='widen the track or add parallel copper',
        )
    )
    return not from_stackup


def report_class_width(ctx, report, net, tracks):
    """Add a finding for the narrowest track below its net class width;
    True if the copper thickness was the default.
    """
    if not tracks:
        return False
    floor = mm(
        ctx.board.GetDesignSettings().m_NetSettings
        .GetEffectiveNetClass(net).GetTrackWidth()
    )
    track = min(tracks, key=lambda t: t.GetWidth())
    width = mm(track.GetWidth())
    capacity, thick, from_stackup = track_capacity(ctx, track)
    if width >= floor - 1e-6:
        return not from_stackup
    layer = ctx.board.GetLayerName(track.GetLayer())
    report.add(
        Finding(
            'TRACE_CURRENT', 'warning', 'measured',
            f'unlocked track {width:.3f} mm on {layer} carries '
            f'{capacity:.2f} A at {ctx.temp_rise:g} C rise (IPC-2221, '
            f'{thick:g} um copper); below the net class minimum width '
            f'{floor:g} mm',
            nets=[net], at=xy(track.GetCenter()),
            fix='widen the track to the net class width',
        )
    )
    return not from_stackup


def pad_area(pad):
    size = pad.GetSize()
    area = mm(size.x) * mm(size.y)
    if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
        return area * math.pi / 4
    return area


def exposed_pads(ctx):
    """Ground or power SMD pads over PAD_MIN_AREA_MM2 that are the largest
    pad of their footprint and at least PAD_EXPOSED_RATIO times its mean.
    """
    for footprint in ctx.board.GetFootprints():
        pads = list(footprint.Pads())
        if len(pads) < 2:
            continue
        areas = [pad_area(p) for p in pads]
        mean = sum(areas) / len(areas)
        pad = pads[areas.index(max(areas))]
        area = max(areas)
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        net = pad.GetNetname()
        if not net or not ctx.is_plane(net):
            continue
        if area > PAD_MIN_AREA_MM2 and area >= PAD_EXPOSED_RATIO * mean:
            yield footprint, pad, area


def required_vias(area):
    if area < PAD_SMALL_MM2:
        return PAD_VIAS_SMALL
    if area <= PAD_MEDIUM_MM2:
        return PAD_VIAS_MEDIUM
    return PAD_VIAS_PER_MM2 * area


def check_thermal_pads(ctx, report):
    """Exposed pads whose vias, weighted by drill area against a 0.3 mm
    drill, fall short of the count for the pad's size.
    """
    vias = [v for v in ctx.board.GetTracks() if is_via(v)]
    for footprint, pad, area in exposed_pads(ctx):
        inside = [v for v in vias if pad.HitTest(v.GetPosition())]
        have = sum(
            (mm(v.GetDrillValue()) / PAD_REF_DRILL_MM) ** 2 for v in inside
        )
        need = required_vias(area)
        if have >= need:
            continue
        ref = footprint.GetReference()
        report.add(
            Finding(
                'THERMAL_PAD_VIAS', 'warning', 'heuristic',
                f'pad {pad.GetNumber()} ({area:.1f} mm2) has {have:.1f} '
                f'effective vias ({len(inside)} placed), wants {need:g}',
                refs=[ref], nets=[pad.GetNetname()],
                at=xy(pad.GetPosition()),
                fix='add vias in the pad',
            )
        )


def pad_name(pad):
    return f'{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}'


def pad_islands(ctx, pads):
    """Group pads of one net by the copper they are connected to, using
    pcbnew's connectivity (tracks, vias and filled zones).
    """
    connectivity = ctx.board.GetConnectivity()
    parent = {id(p): id(p) for p in pads}
    by_id = {id(p): p for p in pads}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    keys = {p.m_Uuid.AsString(): id(p) for p in pads}
    for pad in pads:
        for other in connectivity.GetConnectedItems(pad):
            if other.Type() != pcbnew.PCB_PAD_T:
                continue
            key = keys.get(other.m_Uuid.AsString())
            if key is not None:
                parent[find(key)] = find(id(pad))
    groups = {}
    for key in parent:
        groups.setdefault(find(key), []).append(by_id[key])
    return list(groups.values())


def check_net_open(ctx, report):
    """Nets whose pads are not all joined through copper. Uses pcbnew's
    connectivity (GetConnectedItems) after the zone refill.
    """
    ctx.board.BuildConnectivity()
    by_net = {}
    for pad in ctx.board.GetPads():
        if pad.GetNetname():
            by_net.setdefault(pad.GetNetname(), []).append(pad)
    for net, pads in sorted(by_net.items()):
        if len(pads) < 2:
            continue
        islands = pad_islands(ctx, pads)
        if len(islands) < 2:
            continue
        names = ' | '.join(
            ' '.join(sorted(pad_name(p) for p in isl)) for isl in islands
        )
        report.add(
            Finding(
                'NET_OPEN', 'error', 'measured',
                f'{len(islands)} copper islands: {names}',
                nets=[net], at=xy(islands[-1][0].GetPosition()),
                fix='connect the islands',
            )
        )


def mask_texts(board, layer):
    """Visible text items (board text, footprint fields and text) on a layer
    as (label, bounding box).
    """
    items = [d for d in board.Drawings() if d.Type() == pcbnew.PCB_TEXT_T]
    for footprint in board.GetFootprints():
        items += list(footprint.GetFields())
        items += [
            g for g in footprint.GraphicalItems()
            if g.Type() == pcbnew.PCB_TEXT_T
        ]
    return [
        (i.GetText(), i.GetBoundingBox())
        for i in items
        if i.GetLayer() == layer and i.IsVisible() and i.GetText()
    ]


def check_mask_text(ctx, report):
    """Text on F.Mask or B.Mask whose bounding boxes overlap another's; KiCad
    DRC does not check mask against mask.
    """
    for layer, name in ((pcbnew.F_Mask, 'F.Mask'), (pcbnew.B_Mask, 'B.Mask')):
        texts = mask_texts(ctx.board, layer)
        for i, (label_a, box_a) in enumerate(texts):
            for label_b, box_b in texts[i + 1:]:
                if not box_a.Intersects(box_b):
                    continue
                report.add(
                    Finding(
                        'MASK_TEXT_OVERLAP', 'error', 'measured',
                        f'{name} text "{label_a}" overlaps "{label_b}"',
                        at=xy(box_a.Centre()),
                        fix='move one of the labels',
                    )
                )


CHECKS = (
    check_return_path,
    check_via_ground,
    check_trace_current,
    check_thermal_pads,
    check_net_open,
    check_mask_text,
)


def refill(board, report, enabled):
    """Refill all zones in memory so the checks see current fills."""
    if not enabled:
        report.add(
            Finding(
                'RETURN_PATH_GAP', 'info', 'measured',
                'zones not refilled (--no-refill); the stored fills were used',
            )
        )
        return
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f'refilled {len(board.Zones())} zones in memory (board not saved)')


def run_checks(board, config, board_path, report, do_refill=True):
    """Refill and run every check, adding findings to the report."""
    refill(board, report, do_refill)
    ctx = Context(board, config, board_path)
    for check in CHECKS:
        check(ctx, report)
    return ctx


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    add_common_arguments(parser)
    parser.add_argument('--board', help='the .kicad_pcb (default: the project)')
    parser.add_argument(
        '--no-refill', action='store_true', help='use the stored zone fills'
    )
    args = parser.parse_args(argv)
    project = Path(args.project)
    board_path = Path(args.board) if args.board else project.with_suffix(
        '.kicad_pcb'
    )
    config = Config.load(project.parent)
    board = pcbnew.LoadBoard(str(board_path))
    report = Report('board_checks', str(board_path), RULES)
    run_checks(board, config, board_path, report, not args.no_refill)
    report.apply(config)
    report.print_text()
    if args.json:
        report.write_json(args.json)
    return report.exit_code(config, args.update_baseline)


if __name__ == '__main__':
    sys.exit(main())
