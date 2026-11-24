"""Tests for check_gerbers.py on small hand-made fixtures. Run from
hardware/kicad/tools: python3 -m unittest
"""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_gerbers  # noqa: E402

STEM = 'b'
HEADER = (
    '%TF.GenerationSoftware,KiCad,Pcbnew,10.0*%\n%TF.SameCoordinates,Original*%\n'
    '%FSLAX46Y46*%\nG04 Gerber Fmt 4.6, Leading zero omitted, Abs format (unit mm)*\n'
    '%MOMM*%\n%LPD*%\nG01*\nG04 APERTURE LIST*\n%ADD10C,0.200000*%\n'
    'G04 APERTURE END LIST*\nD10*\n'
)
OUTLINE = (
    'X0Y0D02*\nX50000000Y0D01*\nX50000000Y-30000000D01*\n'
    'X0Y-30000000D01*\nX0Y0D01*\n'
)
INSIDE = 'X10000000Y-10000000D02*\nX20000000Y-10000000D01*\nX30000000Y-20000000D03*\n'
OUTSIDE = 'X10000000Y-10000000D02*\nX60000000Y-10000000D01*\n'
LAYERS = (
    f'{STEM}-F_Cu.gtl', f'{STEM}-B_Cu.gbl', f'{STEM}-F_Mask.gts',
    f'{STEM}-B_Mask.gbs', f'{STEM}-F_Silkscreen.gto',
    f'{STEM}-B_Silkscreen.gbo', f'{STEM}-Edge_Cuts.gm1',
    f'{STEM}-PTH.drl', f'{STEM}-NPTH.drl',
)


def gerber(body):
    return HEADER + body + 'M02*\n'


def excellon(tools, hits):
    defs = ''.join(f'T{n}C{d}\n' for n, d in tools)
    body = ''.join(f'T{n}\n' + ''.join(f'X{x}Y{y}\n' for x, y in pts) for n, pts in hits)
    return f'M48\n; DRILL file\nMETRIC\n{defs}%\nG90\nG05\n{body}M30\n'


REPORT = (
    "Drill file 'b-PTH.drl' contains\n    plated through holes:\n"
    '    Drill T1  0.300 mm  0.0118"  (2 holes)\n'
    "Drill file 'b-NPTH.drl' contains\n    Drill T1  1.000 mm  0.0394\"  (1 hole)\n"
)


class FabTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fab = Path(self.tmp.name)
        self.gdir = self.fab / 'gerbers'
        self.gdir.mkdir()
        for name in LAYERS:
            self.write(name, self.default(name))
        self.write('drill_report.txt', REPORT)
        self.rezip()

    @staticmethod
    def default(name):
        if name.endswith('.gm1'):
            return gerber(OUTLINE)
        if name.endswith('PTH.drl') and 'NPTH' not in name:
            return excellon([(1, '0.300')], [(1, [('10.0', '-10.0'), ('20.0', '-10.0')])])
        if name.endswith('.drl'):
            return excellon([(1, '1.000')], [(1, [('5.0', '-5.0')])])
        return gerber(INSIDE)

    def write(self, name, text):
        (self.gdir / name).write_text(text)

    def rezip(self):
        with zipfile.ZipFile(self.fab / 'b_jlcpcb.zip', 'w') as archive:
            for path in sorted(self.gdir.iterdir()):
                if path.name != 'drill_report.txt':
                    archive.write(path, path.name)

    def rules(self, expected=LAYERS):
        report = check_gerbers.check_fab(self.fab, expected)
        return {(f.rule_id, f.severity) for f in report.findings}


class CleanTests(FabTestCase):
    def test_clean_set_has_no_findings(self):
        self.assertEqual(self.rules(), set())

    def test_inferred_expected_matches(self):
        self.assertEqual(self.rules(expected=None), set())


class FaultTests(FabTestCase):
    def test_missing_layer(self):
        (self.gdir / f'{STEM}-B_Cu.gbl').unlink()
        self.assertIn(('GERBER_LAYER_MISSING', 'error'), self.rules())

    def test_empty_file_counts_as_missing(self):
        self.write(f'{STEM}-B_Mask.gbs', '')
        self.assertIn(('GERBER_LAYER_MISSING', 'error'), self.rules())

    def test_extra_layer(self):
        self.write(f'{STEM}-F_Paste.gtp', gerber(INSIDE))
        self.assertIn(('GERBER_LAYER_EXTRA', 'warning'), self.rules())

    def test_copper_outside_outline(self):
        self.write(f'{STEM}-F_Cu.gtl', gerber(OUTSIDE))
        self.rezip()
        self.assertIn(('GERBER_OUTSIDE_OUTLINE', 'error'), self.rules())

    def test_silk_outside_outline_is_info(self):
        self.write(f'{STEM}-F_Silkscreen.gto', gerber(OUTSIDE))
        self.rezip()
        self.assertEqual(self.rules(), {('GERBER_OUTSIDE_OUTLINE', 'info')})

    def test_drill_count_mismatch(self):
        self.write('drill_report.txt', REPORT.replace('(2 holes)', '(3 holes)'))
        self.assertIn(('DRILL_MISMATCH', 'error'), self.rules())

    def test_drill_outside_outline(self):
        self.write(f'{STEM}-NPTH.drl', excellon([(1, '1.000')], [(1, [('99.0', '-5.0')])]))
        self.rezip()
        self.assertIn(('DRILL_OUTSIDE_OUTLINE', 'error'), self.rules())

    def test_stale_file_in_zip(self):
        with zipfile.ZipFile(self.fab / 'b_jlcpcb.zip', 'a') as archive:
            archive.writestr(f'{STEM}-F_Paste.gtp', 'old')
        self.assertIn(('ZIP_CONTENTS', 'error'), self.rules())

    def test_changed_file_vs_zip(self):
        self.write(f'{STEM}-F_Cu.gtl', gerber(INSIDE + INSIDE))
        self.assertIn(('ZIP_CONTENTS', 'error'), self.rules())

    def test_empty_copper(self):
        self.write(f'{STEM}-B_Cu.gbl', gerber(''))
        self.rezip()
        self.assertIn(('GERBER_EMPTY_COPPER', 'warning'), self.rules())


class SkipAndParserTests(FabTestCase):
    def test_no_drill_report_is_info(self):
        (self.gdir / 'drill_report.txt').unlink()
        self.assertEqual(self.rules(), {('DRILL_MISMATCH', 'info')})

    def test_aperture_macro_is_info(self):
        self.write(f'{STEM}-F_Mask.gts', gerber('%AMX*1,1,1,0,0*%\n' + INSIDE))
        self.rezip()
        self.assertEqual(self.rules(), {('GERBER_UNSUPPORTED', 'info')})

    def test_unsupported_format_is_info_not_pass(self):
        text = gerber(INSIDE).replace('%FSLAX46Y46*%', '%FSTAX46Y46*%')
        self.write(f'{STEM}-F_Cu.gtl', text)
        self.rezip()
        self.assertEqual(self.rules(), {('GERBER_UNSUPPORTED', 'info')})

    def test_arc_extents(self):
        text = gerber('G75*\nX0Y0D02*\nG02*\nX20000000Y0I10000000J0D01*\n')
        parsed = check_gerbers.parse_gerber(text)
        self.assertAlmostEqual(parsed.extents.max_y, 10.0, places=6)
        self.assertAlmostEqual(parsed.extents.min_y, 0.0, places=6)

    def test_inch_gerber(self):
        text = gerber('').replace('%MOMM*%', '%MOIN*%') + ''
        text = text.replace('M02*', 'X1000000Y0D03*\nM02*')
        parsed = check_gerbers.parse_gerber(text)
        self.assertAlmostEqual(parsed.extents.max_x, 25.4)


if __name__ == '__main__':
    unittest.main()
