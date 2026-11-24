"""Tests for placement_gate.py on small boards built here. Run with KiCad's
Python from hardware/kicad/tools:

    $KPY -m unittest tests.test_placement_gate

Each test builds a fixture board in a subprocess (pcbnew allows one board
per process), then runs the gate on it in another and reads its JSON.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
BOARD_W, BOARD_H = 60.0, 40.0


def build_board(spec, out_path):
    """Write a fixture board. Run in its own process (see main below)."""
    import pcbnew

    mm = pcbnew.FromMM
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    w, h = spec.get('size', [BOARD_W, BOARD_H])
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    for i, (x1, y1) in enumerate(corners):
        x2, y2 = corners[(i + 1) % 4]
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        seg.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        board.Add(seg)
    nets = {}
    for part in spec['parts']:
        add_part(board, part, nets)
    for zone in spec.get('keepouts', []):
        add_keepout(board, zone)
    board.Save(str(out_path))


def add_part(board, part, nets):
    import pcbnew

    mm = pcbnew.FromMM
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(part['ref'])
    for number, dx, dy, net, ptype in part.get('pads', []):
        pad = pcbnew.PAD(fp)
        pad.SetNumber(str(number))
        pad.SetSize(pcbnew.VECTOR2I(mm(0.5), mm(0.5)))
        pad.SetPosition(pcbnew.VECTOR2I(mm(dx), mm(dy)))
        pad.SetPinType(ptype)
        if net not in nets:
            nets[net] = pcbnew.NETINFO_ITEM(board, net)
            board.Add(nets[net])
        pad.SetNet(nets[net])
        fp.Add(pad)
    cw, ch = part.get('court', [2.0, 2.0])
    rect = pcbnew.PCB_SHAPE(fp)
    rect.SetShape(pcbnew.SHAPE_T_RECT)
    rect.SetLayer(pcbnew.F_CrtYd)
    rect.SetStart(pcbnew.VECTOR2I(mm(-cw / 2), mm(-ch / 2)))
    rect.SetEnd(pcbnew.VECTOR2I(mm(cw / 2), mm(ch / 2)))
    fp.Add(rect)
    board.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(mm(part['x']), mm(part['y'])))


def add_keepout(board, rect):
    import pcbnew

    mm = pcbnew.FromMM
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetLayerSet(pcbnew.LSET.AllCuMask())
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    x1, y1, x2, y2 = rect
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        outline.Append(mm(x), mm(y))
    board.Add(zone)


def ic(ref, x, y, nets):
    """A 4 mm square IC with one power pad per (net) at the left edge."""
    pads = [
        (i + 1, -1.5, -1.0 + i, net, 'power_in')
        for i, net in enumerate(nets)
    ]
    return {'ref': ref, 'x': x, 'y': y, 'pads': pads, 'court': [4.0, 4.0]}


def cap(ref, x, y, net, ground='GND'):
    pads = [(1, -0.5, 0, net, 'passive'), (2, 0.5, 0, ground, 'passive')]
    return {'ref': ref, 'x': x, 'y': y, 'pads': pads, 'court': [2.0, 1.0]}


def part(ref, x, y, court=(2.0, 2.0), nets=()):
    pads = [(i + 1, 0, 0, n, 'passive') for i, n in enumerate(nets)]
    return {'ref': ref, 'x': x, 'y': y, 'pads': pads, 'court': list(court)}


class GateCase(unittest.TestCase):
    def run_gate(self, parts, config=None, keepouts=(), size=None):
        """Build the fixture, run the gate, return its findings."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        spec = {'parts': parts, 'keepouts': list(keepouts)}
        if size:
            spec['size'] = size
        (root / 'spec.json').write_text(json.dumps(spec))
        (root / 'fixture.kicad_pro').write_text('{}')
        (root / 'board_checks.json').write_text(json.dumps(config or {}))
        subprocess.run(
            [sys.executable, __file__, '--build', str(root / 'spec.json'),
             str(root / 'fixture.kicad_pcb')],
            check=True,
        )
        gate = subprocess.run(
            [sys.executable, str(TOOLS / 'placement_gate.py'),
             '--project', str(root / 'fixture.kicad_pro'),
             '--json', str(root / 'out.json')],
            capture_output=True,
            text=True,
        )
        if not (root / 'out.json').exists():
            self.fail(f'gate wrote no report:\n{gate.stderr}')
        data = json.loads((root / 'out.json').read_text())
        return data['findings']

    def rules(self, findings, rule_id, severity=None):
        return [
            f for f in findings
            if f['rule_id'] == rule_id
            and (severity is None or f['severity'] == severity)
        ]


class DecapTests(GateCase):
    def test_far_cap_is_error(self):
        parts = [ic('U1', 30, 20, ['+3V3']), cap('C1', 20.5, 20, '+3V3')]
        # pad at (28.5, 19); cap pad 1 at (20, 20): 8.6 mm
        found = self.rules(self.run_gate(parts), 'DECAP_DISTANCE', 'error')
        self.assertEqual(len(found), 1)

    def test_between_five_and_eight_is_warning(self):
        parts = [ic('U1', 30, 20, ['+3V3']), cap('C1', 23.5, 19.5, '+3V3')]
        found = self.rules(self.run_gate(parts), 'DECAP_DISTANCE')
        self.assertEqual([f['severity'] for f in found], ['warning'])

    def test_near_cap_is_clean(self):
        parts = [ic('U1', 30, 20, ['+3V3']), cap('C1', 27.5, 20, '+3V3')]
        findings = self.run_gate(parts)
        self.assertEqual(self.rules(findings, 'DECAP_DISTANCE'), [])
        self.assertEqual(self.rules(findings, 'DECAP_MISSING'), [])

    def test_missing_cap(self):
        parts = [ic('U1', 30, 20, ['+3V3']), cap('C1', 5, 5, '+3V3')]
        found = self.rules(self.run_gate(parts), 'DECAP_MISSING', 'error')
        self.assertEqual(len(found), 1)

    def test_ground_pad_is_skipped(self):
        parts = [ic('U1', 30, 20, ['GND'])]
        self.assertEqual(
            self.rules(self.run_gate(parts), 'DECAP_MISSING'), []
        )

    def test_no_pin_types_uses_config_nets(self):
        u1 = ic('U1', 30, 20, ['+3V3'])
        u1['pads'] = [(n, x, y, net, '') for n, x, y, net, _ in u1['pads']]
        c1 = cap('C1', 5, 5, '+3V3')
        findings = self.run_gate(
            [u1, c1], {'placement': {'power_nets': ['+3V3']}}
        )
        self.assertTrue(
            [f for f in findings if f['severity'] == 'info'
             and 'pin types' in f['summary']]
        )
        self.assertEqual(len(self.rules(findings, 'DECAP_MISSING')), 1)


class HotLoopTests(GateCase):
    def loop_parts(self, side):
        return [
            part('U5', 10, 10, nets=['A']),
            part('C40', 10 + side, 10, nets=['A']),
            part('L3', 10 + side, 10 + side, nets=['A']),
        ]

    def config(self):
        return {'hot_loops': {'buck': ['U5.1', 'C40.1', 'L3.1']}}

    def test_large_loop_is_flagged(self):
        # right triangle with legs 8 mm: 32 mm2 -> warning
        found = self.rules(
            self.run_gate(self.loop_parts(8), self.config()), 'HOT_LOOP_AREA'
        )
        self.assertEqual([f['severity'] for f in found], ['warning'])

    def test_huge_loop_is_error(self):
        found = self.rules(
            self.run_gate(self.loop_parts(16), self.config()), 'HOT_LOOP_AREA'
        )
        self.assertEqual([f['severity'] for f in found], ['error'])

    def test_small_loop_is_clean(self):
        found = self.rules(
            self.run_gate(self.loop_parts(4), self.config()), 'HOT_LOOP_AREA'
        )
        self.assertEqual(found, [])

    def test_not_configured_says_so(self):
        found = self.rules(self.run_gate(self.loop_parts(4)), 'HOT_LOOP_AREA')
        self.assertEqual([f['severity'] for f in found], ['info'])


class CourtyardTests(GateCase):
    def test_overlap_is_error(self):
        parts = [part('R1', 20, 20), part('R2', 21, 20)]
        found = self.rules(self.run_gate(parts), 'COURTYARD_OVERLAP', 'error')
        self.assertEqual(len(found), 1)

    def test_apart_is_clean(self):
        parts = [part('R1', 20, 20), part('R2', 24, 20)]
        found = self.rules(self.run_gate(parts), 'COURTYARD_OVERLAP', 'error')
        self.assertEqual(found, [])

    def test_touching_is_clean(self):
        parts = [part('R1', 20, 20), part('R2', 22, 20)]
        found = self.rules(self.run_gate(parts), 'COURTYARD_OVERLAP', 'error')
        self.assertEqual(found, [])


class EdgeTests(GateCase):
    def test_near_edge_is_warning(self):
        parts = [part('R1', 1.5, 20)]  # courtyard edge 0.5 mm from outline
        found = self.rules(self.run_gate(parts), 'EDGE_CLEARANCE')
        self.assertEqual([f['severity'] for f in found], ['warning'])

    def test_very_near_edge_is_error(self):
        parts = [part('R1', 1.2, 20)]
        found = self.rules(self.run_gate(parts), 'EDGE_CLEARANCE')
        self.assertEqual([f['severity'] for f in found], ['error'])

    def test_edge_parts_are_skipped(self):
        parts = [part('J1', 1.2, 20)]
        found = self.run_gate(parts, {'placement': {'edge_parts': ['J*']}})
        self.assertEqual(self.rules(found, 'EDGE_CLEARANCE'), [])

    def test_inside_is_clean(self):
        found = self.run_gate([part('R1', 30, 20)])
        self.assertEqual(self.rules(found, 'EDGE_CLEARANCE'), [])
        self.assertEqual(self.rules(found, 'OFF_BOARD'), [])

    def test_off_board(self):
        found = self.run_gate([part('R1', 70, 20)])
        self.assertEqual(len(self.rules(found, 'OFF_BOARD', 'error')), 1)


class AntennaTests(GateCase):
    CONFIG = {'placement': {'antenna_modules': ['U1']}}

    def module(self, x):
        return part('U1', x, 20, court=(10.0, 10.0))

    def test_without_keepout_is_error(self):
        found = self.run_gate([self.module(30)], self.CONFIG)
        self.assertEqual(len(self.rules(found, 'ANTENNA_KEEPOUT', 'error')), 1)

    def test_with_keepout_is_clean(self):
        found = self.run_gate(
            [self.module(30)], self.CONFIG, keepouts=[(24, 14, 36, 26)]
        )
        self.assertEqual(self.rules(found, 'ANTENNA_KEEPOUT'), [])

    def test_overhang_is_clean(self):
        found = self.run_gate([self.module(2)], self.CONFIG)
        self.assertEqual(self.rules(found, 'ANTENNA_KEEPOUT'), [])

    def test_not_configured_says_so(self):
        found = self.rules(self.run_gate([self.module(30)]), 'ANTENNA_KEEPOUT')
        self.assertEqual([f['severity'] for f in found], ['info'])


class TestpointTests(GateCase):
    def test_ic_without_testpoint_warns(self):
        parts = [ic('U1', 30, 20, ['+3V3']), part('TP1', 10, 10, nets=['X'])]
        found = self.rules(self.run_gate(parts), 'TESTPOINT_MISSING')
        self.assertEqual([f['severity'] for f in found], ['warning'])

    def test_ic_with_testpoint_is_clean(self):
        parts = [ic('U1', 30, 20, ['+3V3']), part('TP1', 10, 10, nets=['+3V3'])]
        found = self.rules(self.run_gate(parts), 'TESTPOINT_MISSING')
        self.assertEqual(found, [])


class EdgeOrderTests(GateCase):
    CONFIG = {'placement': {'topmost_on_edge': ['SW1']}}

    def test_part_above_it_is_error(self):
        parts = [part('SW1', 2, 20), part('J9', 2, 10)]
        found = self.rules(
            self.run_gate(parts, self.CONFIG), 'EDGE_ORDER', 'error'
        )
        self.assertEqual(len(found), 1)
        self.assertIn('J9', found[0]['refs'])

    def test_topmost_is_clean(self):
        parts = [part('SW1', 2, 10), part('J9', 2, 20)]
        found = self.run_gate(parts, self.CONFIG)
        self.assertEqual(self.rules(found, 'EDGE_ORDER'), [])

    def test_far_part_does_not_count(self):
        parts = [part('SW1', 2, 20), part('J9', 30, 10)]
        found = self.run_gate(parts, self.CONFIG)
        self.assertEqual(self.rules(found, 'EDGE_ORDER'), [])

    def test_bottommost_violation_on_right_edge(self):
        parts = [part('J3', 58, 20), part('J4', 58, 30)]
        config = {'placement': {'bottommost_on_edge': ['J3']}}
        found = self.rules(self.run_gate(parts, config), 'EDGE_ORDER', 'error')
        self.assertEqual(len(found), 1)

    def test_on_bottom_edge_fails_topmost(self):
        parts = [part('SW1', 30, 38)]
        found = self.rules(
            self.run_gate(parts, self.CONFIG), 'EDGE_ORDER', 'error'
        )
        self.assertEqual(len(found), 1)

    def test_missing_ref_is_error(self):
        found = self.rules(
            self.run_gate([part('R1', 30, 20)], self.CONFIG),
            'EDGE_ORDER', 'error',
        )
        self.assertEqual(len(found), 1)

    def test_not_configured_says_so(self):
        found = self.rules(self.run_gate([part('R1', 30, 20)]), 'EDGE_ORDER')
        self.assertEqual([f['severity'] for f in found], ['info'])


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--build':
        build_board(json.loads(Path(sys.argv[2]).read_text()), sys.argv[3])
    else:
        unittest.main()
