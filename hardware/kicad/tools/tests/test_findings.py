"""Tests for findings.py. Run from hardware/kicad/tools:
python3 -m unittest
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from findings import Config, Finding, Report  # noqa: E402


def finding(rule='R1', refs=(), nets=(), severity='error', at=None):
    return Finding(rule, severity, 'measured', 'x', list(refs), list(nets), at)


class SuppressionTests(unittest.TestCase):
    def config(self, *rules):
        return Config('.', {'suppress': list(rules)})

    def test_rule_and_ref_glob(self):
        config = self.config(
            {'rule_id': 'R1', 'refs': 'C1?', 'reason': 'ok'}
        )
        self.assertEqual(config.suppression_for(finding(refs=['C12'])), 'ok')
        self.assertIsNone(config.suppression_for(finding(refs=['C2'])))
        self.assertIsNone(config.suppression_for(finding('R2', ['C12'])))

    def test_all_given_sets_must_match(self):
        config = self.config(
            {'rule_id': 'R1', 'refs': ['U*'], 'nets': ['+3V3'], 'reason': 'ok'}
        )
        self.assertIsNotNone(
            config.suppression_for(finding(refs=['U1'], nets=['+3V3', 'GND']))
        )
        self.assertIsNone(config.suppression_for(finding(refs=['U1'])))
        self.assertIsNone(
            config.suppression_for(finding(refs=['C1'], nets=['+3V3']))
        )

    def test_at_matches_nearby_finding_only(self):
        config = self.config({'rule_id': 'R1', 'at': [10, 20], 'reason': 'ok'})
        self.assertIsNotNone(config.suppression_for(finding(at=(10.2, 20.1))))
        self.assertIsNone(config.suppression_for(finding(at=(12, 20))))
        self.assertIsNone(config.suppression_for(finding()))

    def test_rule_only_matches_everything(self):
        config = self.config({'rule_id': 'R1', 'reason': 'ok'})
        self.assertIsNotNone(config.suppression_for(finding()))

    def test_missing_reason_exits(self):
        for rule in ({'rule_id': 'R1'}, {'rule_id': 'R1', 'reason': ' '}):
            with self.assertRaises(SystemExit) as raised:
                self.config(rule)
            self.assertIn('reason', str(raised.exception))

    def test_suppressed_do_not_count(self):
        report = Report('t', 'b')
        report.add(finding(refs=['C1']))
        report.add(finding(refs=['C2']))
        report.add(finding(severity='info'))
        report.apply(self.config({'rule_id': 'R1', 'refs': 'C1', 'reason': 'a'}))
        self.assertEqual(report.counts(), {'R1': 1})
        self.assertEqual(
            report.summary(),
            {'error': 1, 'warning': 0, 'info': 1, 'suppressed': 1},
        )

    def test_load_reads_file_and_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'board_checks.json').write_text(
                json.dumps({'baseline': 'b.json', 'hot_loops': {'a': 1}})
            )
            config = Config.load(tmp)
            self.assertEqual(config.section('hot_loops'), {'a': 1})
            self.assertEqual(config.section('placement', {}), {})
            self.assertEqual(config.baseline, Path(tmp) / 'b.json')
            self.assertEqual(Config.load(tmp + '/missing').suppressions, [])


class JsonTests(unittest.TestCase):
    def test_order_is_stable(self):
        items = [
            finding('B', ['C2']),
            finding('A', ['C9'], at=(2.0, 1.0)),
            finding('A', ['C9'], at=(1.0, 1.0)),
            finding('A', ['C1']),
        ]
        outputs = []
        with tempfile.TemporaryDirectory() as tmp:
            for order in (items, items[::-1]):
                report = Report('tool', 'board')
                for item in order:
                    report.add(item)
                path = Path(tmp, 'r.json')
                report.write_json(path)
                outputs.append(path.read_bytes())
            data = json.loads(outputs[0])
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(
            [(f['rule_id'], f['refs']) for f in data['findings']],
            [('A', ['C1']), ('A', ['C9']), ('A', ['C9']), ('B', ['C2'])],
        )
        self.assertEqual(data['findings'][1]['at'], [1.0, 1.0])
        self.assertEqual(data['tool'], 'tool')

    def test_bad_severity(self):
        with self.assertRaises(ValueError):
            Finding('R', 'fatal', 'measured', 's')


class BaselineTests(unittest.TestCase):
    def run_case(self, count, baseline, update=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'base.json')
            if baseline is not None:
                path.write_text(json.dumps({'t': baseline, 'other': {'X': 1}}))
            config = Config(tmp, {'baseline': 'base.json'})
            report = Report('t', 'b')
            for _ in range(count):
                report.add(finding())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = report.exit_code(config, update)
            written = json.loads(path.read_text()) if path.exists() else None
            return code, out.getvalue(), written

    def test_above_fails(self):
        code, out, _ = self.run_case(3, {'R1': 2})
        self.assertEqual(code, 1)
        self.assertIn('FAIL: above baseline', out)

    def test_equal_passes(self):
        code, out, _ = self.run_case(2, {'R1': 2})
        self.assertEqual(code, 0)
        self.assertIn('R1: 2 (baseline 2) ok', out)

    def test_below_passes_and_asks_update(self):
        code, out, _ = self.run_case(1, {'R1': 2})
        self.assertEqual(code, 0)
        self.assertIn('run --update-baseline', out)

    def test_below_when_rule_gone(self):
        code, out, _ = self.run_case(0, {'R1': 2})
        self.assertEqual(code, 0)
        self.assertIn('R1: 0 (baseline 2) below baseline', out)

    def test_not_in_baseline_must_be_zero(self):
        self.assertEqual(self.run_case(1, {})[0], 1)
        self.assertEqual(self.run_case(1, None)[0], 1)
        self.assertEqual(self.run_case(0, None)[0], 0)

    def test_update_writes_counts(self):
        code, _, written = self.run_case(2, {'R1': 5}, update=True)
        self.assertEqual(code, 0)
        self.assertEqual(written, {'t': {'R1': 2}, 'other': {'X': 1}})

    def test_update_without_baseline_path_exits(self):
        report = Report('t', 'b')
        with self.assertRaises(SystemExit):
            report.exit_code(Config('.', {}), update_baseline=True)


if __name__ == '__main__':
    unittest.main()
