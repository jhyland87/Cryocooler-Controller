"""Tests for board_checks.py and finish_route.py --stitch. Run with KiCad's
bundled Python from hardware/kicad/tools:
  $KPY -m unittest tests.test_board_checks

pcbnew handles one board per process, so each fixture is built, and each tool
run, in its own subprocess. This file is also the fixture builder:
  $KPY tests/test_board_checks.py --build KIND DIR
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))

WIDTH, HEIGHT = 40.0, 30.0


def add_net(board, name):
    import pcbnew

    net = pcbnew.NETINFO_ITEM(board, name, board.GetNetCount())
    board.Add(net)
    return net


def vec(x, y):
    import pcbnew

    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def add_track(board, net, layer, start, end, width=0.25, locked=False):
    import pcbnew

    track = pcbnew.PCB_TRACK(board)
    track.SetStart(vec(*start))
    track.SetEnd(vec(*end))
    track.SetWidth(pcbnew.FromMM(width))
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetLocked(locked)
    board.Add(track)


def add_via(board, net, x, y, drill=0.3, diameter=0.6):
    import pcbnew

    via = pcbnew.PCB_VIA(board)
    via.SetPosition(vec(x, y))
    via.SetWidth(pcbnew.FromMM(diameter))
    via.SetDrill(pcbnew.FromMM(drill))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetNet(net)
    board.Add(via)


def add_zone(board, layer, box, net=None, keepout=False):
    import pcbnew

    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    if keepout:
        zone.SetIsRuleArea(True)
        zone.SetDoNotAllowZoneFills(True)
    else:
        zone.SetNet(net)
    outline = zone.Outline()
    outline.NewOutline()
    x0, y0, x1, y1 = box
    for corner in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        outline.Append(pcbnew.FromMM(corner[0]), pcbnew.FromMM(corner[1]))
    board.Add(zone)


def add_outline(board):
    import pcbnew

    corners = [(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT), (0, 0)]
    for a, b in zip(corners, corners[1:]):
        line = pcbnew.PCB_SHAPE(board)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetLayer(pcbnew.Edge_Cuts)
        line.SetStart(vec(*a))
        line.SetEnd(vec(*b))
        board.Add(line)


def add_pad(footprint, number, net, x, y, w, h):
    import pcbnew

    pad = pcbnew.PAD(footprint)
    pad.SetNumber(number)
    pad.SetShape(pcbnew.PAD_SHAPE_RECT)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    pad.SetLayerSet(pad.SMDMask())
    pad.SetSize(vec(w, h))
    pad.SetPosition(vec(x, y))
    if net is not None:
        pad.SetNet(net)
    footprint.Add(pad)


def add_footprint(board, ref, x, y):
    import pcbnew

    footprint = pcbnew.FOOTPRINT(board)
    footprint.SetReference(ref)
    footprint.SetPosition(vec(x, y))
    board.Add(footprint)
    return footprint


def add_text(board, text, x, y, layer):
    import pcbnew

    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetPosition(vec(x, y))
    item.SetLayer(layer)
    item.SetTextSize(vec(1.0, 1.0))
    board.Add(item)


def base_board():
    import pcbnew

    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(4)
    add_outline(board)
    gnd = add_net(board, 'GND')
    add_zone(board, pcbnew.In1_Cu, (1, 1, WIDTH - 1, HEIGHT - 1), gnd)
    return board, gnd


def build_return(board, gap, net='SIG'):
    """A track over a slot `gap` mm wide in In1 (None: no slot)."""
    import pcbnew

    sig = add_net(board, net)
    if gap:
        add_zone(board, pcbnew.In1_Cu, (19, 0, 19 + gap, HEIGHT), keepout=True)
    add_track(board, sig, pcbnew.F_Cu, (5, 15), (35, 15))


def build_via(board, gnd, layer, ground_at, net='SIG'):
    """A signal via between F.Cu and `layer`, with a ground via `ground_at` mm
    away (None: only a distant one).
    """
    import pcbnew

    sig = add_net(board, net)
    add_track(board, sig, pcbnew.F_Cu, (5, 15), (15, 15))
    add_via(board, sig, 15, 15)
    add_track(board, sig, layer, (15, 15), (25, 15))
    far = (35, 25) if ground_at is None else (15, 15 + ground_at)
    add_via(board, gnd, *far)


def build_current(board, width):
    import pcbnew

    pwr = add_net(board, 'PWR')
    add_track(board, pwr, pcbnew.F_Cu, (5, 15), (35, 15), width)


def build_return_via(board, own):
    import pcbnew

    sig = add_net(board, 'SIG')
    other = add_net(board, 'OTHER')
    add_zone(board, pcbnew.In1_Cu, (18.2, 0, 19.8, HEIGHT), keepout=True)
    next(iter(board.Zones())).SetLocalClearance(pcbnew.FromMM(0.3))
    add_track(board, sig, pcbnew.F_Cu, (5, 15), (35, 15))
    # Beside the track, not on it: a via on a track of another net is a short.
    add_via(board, sig if own else other, 19, 15.45)


def build_locked(board, vias, stub):
    import pcbnew

    pwr = add_net(board, 'PWR')
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        add_track(board, pwr, layer, (5, 15), (35, 15), 2.0, locked=True)
    for index in range(vias):
        add_via(board, pwr, 10 + 2 * index, 15)
    if stub:
        add_track(board, pwr, pcbnew.F_Cu, (20, 15), (20, 25), stub)


def build_pad(board, gnd, vias):
    footprint = add_footprint(board, 'U1', 20, 15)
    add_pad(footprint, '1', gnd, 20, 15, 3, 3)
    for number in range(2, 10):
        add_pad(footprint, str(number), None, 14 + number, 20, 0.3, 0.8)
    for index in range(vias):
        add_via(board, gnd, 19 + (index % 3), 14 + index // 3)
    # A second ground pad joined only through the plane.
    add_pad(add_footprint(board, 'J2', 35, 25), '1', gnd, 35, 25, 1, 1)
    add_via(board, gnd, 35, 25)


def build_open(board, joined):
    import pcbnew

    sig = add_net(board, 'SIG')
    footprint = add_footprint(board, 'J1', 20, 5)
    add_pad(footprint, '1', sig, 5, 5, 1, 1)
    add_pad(footprint, '2', sig, 35, 5, 1, 1)
    end = (35, 5) if joined else (15, 5)
    add_track(board, sig, pcbnew.F_Cu, (5, 5), end)


def build_mask(board, overlap):
    import pcbnew

    add_text(board, 'AAAA', 10, 10, pcbnew.F_Mask)
    add_text(board, 'BBBB', 11 if overlap else 20, 10, pcbnew.F_Mask)


def build(kind, folder):
    """Write board.kicad_pcb, proj.kicad_pro and board_checks.json for one
    fixture kind into folder.
    """
    import pcbnew

    board, gnd = base_board()
    config = {
        'net_currents': {'PWR': 5},
        'fast_signals': {'classes': ['SPI'], 'nets': ['SIG']},
        'ground_via': {'reach_mm': 3},
        'return_path': {'min_gap_mm': 3},
    }
    if kind.startswith('return_') and kind.endswith('_via'):
        config['return_path'] = {'min_gap_mm': 0.25}
    back, in2 = pcbnew.B_Cu, pcbnew.In2_Cu
    builders = {
        'return_gap': lambda: build_return(board, 6),
        'return_gap_2': lambda: build_return(board, 2),
        'return_gap_5': lambda: build_return(board, 5),
        'return_gap_slow': lambda: build_return(board, 5, 'SLOW'),
        'return_solid': lambda: build_return(board, None),
        'via_bad': lambda: build_via(board, gnd, back, None),
        'via_ok': lambda: build_via(board, gnd, back, 0.8),
        'via_f_in2': lambda: build_via(board, gnd, in2, None),
        'via_2_5': lambda: build_via(board, gnd, back, 2.5),
        'via_3_5': lambda: build_via(board, gnd, back, 3.5),
        'via_slow': lambda: build_via(board, gnd, back, None, 'SLOW'),
        'current_bad': lambda: build_current(board, 0.2),
        'current_ok': lambda: build_current(board, 4.0),
        'return_own_via': lambda: build_return_via(board, True),
        'return_other_via': lambda: build_return_via(board, False),
        'locked_pair': lambda: build_locked(board, 4, None),
        'locked_one_via': lambda: build_locked(board, 1, None),
        'locked_thin_stub': lambda: build_locked(board, 4, 0.05),
        'locked_stub': lambda: build_locked(board, 4, 0.3),
        'pad_bad': lambda: build_pad(board, gnd, 1),
        'pad_ok': lambda: build_pad(board, gnd, 9),
        'open': lambda: build_open(board, False),
        'closed': lambda: build_open(board, True),
        'mask_bad': lambda: build_mask(board, True),
        'mask_ok': lambda: build_mask(board, False),
    }
    builders[kind]()
    folder = Path(folder)
    board.Save(str(folder / 'board.kicad_pcb'))
    (folder / 'proj.kicad_pro').write_text('{}')
    (folder / 'board_checks.json').write_text(json.dumps(config))


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def python(self, *args):
        return subprocess.run(
            [sys.executable, *map(str, args)],
            capture_output=True, text=True, cwd=TOOLS,
            env=dict(os.environ, PYTHONHASHSEED='0'),
        )

    def make(self, kind):
        result = self.python(HERE / 'test_board_checks.py', '--build', kind, self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)

    def findings(self, kind):
        """Build the fixture, run board_checks on it, return the findings."""
        self.make(kind)
        out = self.dir / 'out.json'
        result = self.python(
            TOOLS / 'board_checks.py', '--board', self.dir / 'board.kicad_pcb',
            '--project', self.dir / 'proj.kicad_pro', '--json', out,
        )
        self.assertTrue(out.exists(), result.stdout + result.stderr)
        return json.loads(out.read_text())['findings']

    def rules(self, kind, severity=None):
        return [
            f['rule_id'] for f in self.findings(kind)
            if severity is None or f['severity'] == severity
        ]


class ReturnPathTests(FixtureTest):
    def test_gap_flagged(self):
        found = [f for f in self.findings('return_gap')
                 if f['rule_id'] == 'RETURN_PATH_GAP']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['nets'], ['SIG'])
        self.assertGreater(found[0]['at'][0], 18)
        self.assertLess(found[0]['at'][0], 26)

    def test_short_gap_passes(self):
        self.assertNotIn('RETURN_PATH_GAP', self.rules('return_gap_2'))

    def test_long_gap_fails(self):
        self.assertIn('RETURN_PATH_GAP', self.rules('return_gap_5', 'warning'))

    def test_long_gap_on_slow_net_is_ignored(self):
        self.assertNotIn('RETURN_PATH_GAP', self.rules('return_gap_slow'))

    def test_solid_plane_clean(self):
        self.assertNotIn('RETURN_PATH_GAP', self.rules('return_solid'))

    def test_own_via_antipad_is_not_a_gap(self):
        self.assertNotIn('RETURN_PATH_GAP', self.rules('return_own_via'))

    def test_other_net_via_is_still_a_gap(self):
        self.assertIn('RETURN_PATH_GAP', self.rules('return_other_via'))


class ViaTests(FixtureTest):
    def test_missing_ground_via(self):
        self.assertIn('VIA_NO_GROUND_VIA', self.rules('via_bad', 'warning'))

    def test_ground_via_present(self):
        self.assertNotIn('VIA_NO_GROUND_VIA', self.rules('via_ok', 'warning'))

    def test_f_in2_change_is_exempt(self):
        self.assertNotIn('VIA_NO_GROUND_VIA', self.rules('via_f_in2', 'warning'))

    def test_ground_via_inside_reach_passes(self):
        self.assertNotIn('VIA_NO_GROUND_VIA', self.rules('via_2_5', 'warning'))

    def test_ground_via_outside_reach_fails(self):
        self.assertIn('VIA_NO_GROUND_VIA', self.rules('via_3_5', 'warning'))

    def test_slow_net_is_ignored(self):
        self.assertNotIn('VIA_NO_GROUND_VIA', self.rules('via_slow', 'warning'))


class CurrentTests(FixtureTest):
    def test_narrow_track_errors(self):
        self.assertIn('TRACE_CURRENT', self.rules('current_bad', 'error'))

    def test_wide_track_passes(self):
        self.assertNotIn('TRACE_CURRENT', self.rules('current_ok', 'error'))
        self.assertNotIn('TRACE_CURRENT', self.rules('current_ok', 'warning'))

    def current(self, kind):
        return [f for f in self.findings(kind)
                if f['rule_id'] == 'TRACE_CURRENT' and f['severity'] != 'info']

    def test_locked_layers_add_through_vias(self):
        self.assertEqual(self.current('locked_pair'), [])

    def test_locked_layers_limited_by_vias(self):
        found = self.current('locked_one_via')
        self.assertEqual([f['severity'] for f in found], ['error'])
        self.assertEqual(found[0]['nets'], ['PWR'])
        self.assertIn('assumed 1 A per via', found[0]['summary'])

    def test_unlocked_stub_needs_only_class_width(self):
        self.assertEqual(self.current('locked_stub'), [])

    def test_unlocked_track_below_class_width_flagged(self):
        found = self.current('locked_thin_stub')
        self.assertEqual([f['severity'] for f in found], ['warning'])
        self.assertIn('net class minimum width', found[0]['summary'])

    def test_not_configured_is_info(self):
        self.make('current_ok')
        (self.dir / 'board_checks.json').write_text('{}')
        out = self.dir / 'out.json'
        self.python(
            TOOLS / 'board_checks.py', '--board', self.dir / 'board.kicad_pcb',
            '--project', self.dir / 'proj.kicad_pro', '--json', out,
        )
        found = json.loads(out.read_text())['findings']
        notes = [f for f in found if f['rule_id'] == 'TRACE_CURRENT']
        self.assertEqual([f['severity'] for f in notes], ['info'])


class ThermalPadTests(FixtureTest):
    def test_one_via_flagged(self):
        self.assertIn('THERMAL_PAD_VIAS', self.rules('pad_bad'))

    def test_nine_vias_pass(self):
        self.assertNotIn('THERMAL_PAD_VIAS', self.rules('pad_ok'))


class NetOpenTests(FixtureTest):
    def test_gap_is_open(self):
        found = [f for f in self.findings('open') if f['rule_id'] == 'NET_OPEN']
        self.assertEqual(len(found), 1)
        self.assertIn('J1.1', found[0]['summary'])
        self.assertIn('J1.2', found[0]['summary'])

    def test_joined_net_is_closed(self):
        self.assertNotIn('NET_OPEN', self.rules('closed'))


class MaskTextTests(FixtureTest):
    def test_overlap_errors(self):
        self.assertIn('MASK_TEXT_OVERLAP', self.rules('mask_bad', 'error'))

    def test_apart_is_clean(self):
        self.assertNotIn('MASK_TEXT_OVERLAP', self.rules('mask_ok'))


class StitchTests(FixtureTest):
    def stitch_findings(self, extra):
        out = self.dir / 'stitched.kicad_pcb'
        result = self.python(
            TOOLS / 'finish_route.py', self.dir / 'board.kicad_pcb', out,
            '--project', self.dir / 'proj.kicad_pro', *extra,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = self.dir / 'after.json'
        self.python(
            TOOLS / 'board_checks.py', '--board', out, '--no-refill',
            '--project', self.dir / 'proj.kicad_pro', '--json', report,
        )
        return result.stdout, json.loads(report.read_text())['findings']

    def test_stitch_adds_the_missing_via(self):
        self.make('via_bad')
        stdout, found = self.stitch_findings(['--stitch'])
        self.assertIn('stitch vias: 1 added, 0 skipped', stdout)
        self.assertNotIn(
            'VIA_NO_GROUND_VIA',
            [f['rule_id'] for f in found if f['severity'] == 'warning'],
        )

    def test_no_flag_adds_nothing(self):
        self.make('via_bad')
        stdout, found = self.stitch_findings([])
        self.assertNotIn('stitch vias', stdout)
        self.assertIn('VIA_NO_GROUND_VIA', [f['rule_id'] for f in found])


class StackupTests(unittest.TestCase):
    def test_parse_and_thickness(self):
        from board_checks import Stackup, parse_stackup

        text = (
            '(kicad_pcb (setup (stackup\n'
            '(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))\n'
            '(layer "F.Cu" (type "copper") (thickness 0.035))\n'
            '(layer "dielectric 1" (type "prepreg") (thickness 0.2))\n'
            '(layer "In1.Cu" (type "copper") (thickness 0.0175))\n'
            ')))'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'b.kicad_pcb'
            path.write_text(text)
            stackup = Stackup(parse_stackup(path))
        self.assertAlmostEqual(stackup.dielectric_mm('F.Cu', 'In1.Cu'), 0.2)
        self.assertAlmostEqual(stackup.copper_mm('In1.Cu'), 0.0175)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--build':
        build(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
