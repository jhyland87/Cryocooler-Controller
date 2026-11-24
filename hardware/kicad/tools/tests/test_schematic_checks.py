"""Unit tests for the wire geometry and label shape checks in textlayout."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import textlayout  # noqa: E402


class FakePart:
    def __init__(self, ref, pins):
        self.ref = ref
        self.pins = pins
        self.pin_table = {number: None for number in pins}

    def pin_point(self, number):
        return self.pins[number]


class FakeSheet:
    filename = 'fake.kicad_sch'

    def __init__(self, wires=(), pins=None, labels=(), junctions=()):
        self.wires = list(wires)
        self.parts = [FakePart('R1', pins or {})]
        self.labels = list(labels)
        self.junctions = list(junctions)

    def routed(self):
        return self.wires, self.junctions


def problems(**kwargs):
    return textlayout.geometry_problems(FakeSheet(**kwargs))


WIRE = ((0.0, 0.0), (10.0, 0.0))


class NearMiss(unittest.TestCase):
    def test_pin_beside_wire_end(self):
        found = problems(wires=[WIRE], pins={'1': (10.03, 0.0)})
        self.assertEqual(len(found), 1)
        self.assertIn('near miss', found[0])

    def test_label_beside_wire_body(self):
        found = problems(
            wires=[WIRE], labels=[('label', 'NET', (5.0, 0.04), 0)]
        )
        self.assertEqual(len(found), 1)
        self.assertIn('near miss', found[0])

    def test_exact_and_far_are_clean(self):
        self.assertEqual(problems(wires=[WIRE], pins={'1': (10.0, 0.0)}), [])
        self.assertEqual(problems(wires=[WIRE], pins={'1': (10.0, 0.5)}), [])


class PinMidWire(unittest.TestCase):
    def test_pin_inside_wire(self):
        found = problems(wires=[WIRE], pins={'1': (5.0, 0.0)})
        self.assertEqual(len(found), 1)
        self.assertIn('middle of a wire', found[0])

    def test_junction_or_wire_end_joins_it(self):
        pins = {'1': (5.0, 0.0)}
        self.assertEqual(
            problems(wires=[WIRE], pins=pins, junctions=[(5.0, 0.0)]), []
        )
        branch = ((5.0, 0.0), (5.0, 5.0))
        self.assertEqual(problems(wires=[WIRE, branch], pins=pins), [])


class WireShape(unittest.TestCase):
    def test_diagonal(self):
        found = problems(wires=[((0.0, 0.0), (5.0, 5.0))])
        self.assertEqual(len(found), 1)
        self.assertIn('diagonal', found[0])

    def test_axis_aligned_is_clean(self):
        self.assertEqual(problems(wires=[WIRE, ((0.0, 0.0), (0.0, 7.0))]), [])

    def test_stub(self):
        found = problems(wires=[((0.0, 0.0), (0.0, 0.635))])
        self.assertEqual(len(found), 1)
        self.assertIn('stub', found[0])

    def test_one_millimetre_is_not_a_stub(self):
        self.assertEqual(problems(wires=[((0.0, 0.0), (1.0, 0.0))]), [])


class LabelShapes(unittest.TestCase):
    def mismatches(self, kinds, is_root=True):
        labels = [(kind, 'IO1_GATE', (i, 0.0), 0) for i, kind in enumerate(kinds)]
        sheet = FakeSheet(labels=labels)
        return textlayout.label_shape_mismatches(sheet, is_root)

    def test_global_and_hierarchical_differ_on_root(self):
        # a net the root drives: its global label differs from a child's
        original = textlayout.label_shape
        textlayout.label_shape = lambda net, is_root, _f: (
            'output' if is_root else 'input'
        )
        try:
            self.assertEqual(
                len(self.mismatches(['global_label', 'hierarchical_label'])), 1
            )
            self.assertEqual(
                self.mismatches(['hierarchical_label', 'hierarchical_label']),
                [],
            )
        finally:
            textlayout.label_shape = original

    def test_local_labels_are_ignored(self):
        self.assertEqual(self.mismatches(['label', 'hierarchical_label']), [])


if __name__ == '__main__':
    unittest.main()
