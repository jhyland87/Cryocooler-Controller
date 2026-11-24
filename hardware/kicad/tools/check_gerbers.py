"""Checks a fab output folder after export: every expected layer is there,
copper and drills lie inside the board outline, the drill files agree with
drill_report.txt, and the JLCPCB zip holds exactly the files in the folder.
Standard library only; the Gerber and Excellon readers handle the subset
KiCad writes, and report anything else as an info finding.

    check_gerbers.py [--fab-dir DIR] [--project path.kicad_pro]
                     [--json out] [--update-baseline]

--fab-dir is the fabrication folder (gerbers/ and the zip inside it). Without
an expected file list the layers are inferred from the Edge.Cuts file name.
"""

import argparse
import math
import re
import sys
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from findings import Config, Finding, Report, add_common_arguments

TOOL = 'check_gerbers.py'
OUTLINE_TOLERANCE_MM = 0.01
DIAMETER_TOLERANCE_MM = 0.001
MM_PER_INCH = 25.4
GERBER_EXTENSIONS = ('.gtl', '.gbl', '.gts', '.gbs', '.gto', '.gbo', '.gm1', '.gtp', '.gbp')
COPPER_EXTENSION = re.compile(r'\.(gtl|gbl|g\d+)$')
EDGE_SUFFIX = '-Edge_Cuts.gm1'
RULES = {
    'GERBER_LAYER_MISSING': 'an expected layer file is missing or empty',
    'GERBER_LAYER_EXTRA': 'a Gerber file the export does not write',
    'GERBER_OUTSIDE_OUTLINE': 'copper outside the Edge.Cuts extents',
    'DRILL_MISMATCH': 'drill files disagree with drill_report.txt',
    'DRILL_OUTSIDE_OUTLINE': 'a drill hit outside the Edge.Cuts extents',
    'ZIP_CONTENTS': 'the zip differs from the Gerber and drill files',
    'GERBER_EMPTY_COPPER': 'a copper layer with no draws or flashes',
}


@dataclass
class Extents:
    """Bounding box of points in mm; empty until a point is added."""

    min_x: float = math.inf
    min_y: float = math.inf
    max_x: float = -math.inf
    max_y: float = -math.inf

    def add(self, x, y):
        self.min_x, self.max_x = min(self.min_x, x), max(self.max_x, x)
        self.min_y, self.max_y = min(self.min_y, y), max(self.max_y, y)

    def empty(self):
        return self.min_x > self.max_x

    def outside(self, outline, tolerance=OUTLINE_TOLERANCE_MM):
        """True when this box leaves the outline box by more than tolerance."""
        return (
            self.min_x < outline.min_x - tolerance
            or self.max_x > outline.max_x + tolerance
            or self.min_y < outline.min_y - tolerance
            or self.max_y > outline.max_y + tolerance
        )

    def text(self):
        return (
            f'x {self.min_x:.3f}..{self.max_x:.3f}, '
            f'y {self.min_y:.3f}..{self.max_y:.3f} mm'
        )


@dataclass
class Parsed:
    """What a reader got from one file. ok is False when it had to stop
    early, leaving notes that say why.
    """

    extents: Extents = field(default_factory=Extents)
    draws: int = 0
    ok: bool = True
    notes: list = field(default_factory=list)
    hits: Counter = field(default_factory=Counter)
    tools: dict = field(default_factory=dict)
    points: list = field(default_factory=list)

    def note(self, text):
        if text not in self.notes:
            self.notes.append(text)

    def abort(self, text):
        """Records why the file cannot be read further."""
        self.ok = False
        self.note(text)


# --- RS-274X reader ---------------------------------------------------------

TOKEN = re.compile(r'%([^%]*)%|([^%*]+)\*', re.DOTALL)
IGNORED_EXTENDED = ('TF', 'TA', 'TD', 'TO', 'AD', 'LP', 'LM', 'LR', 'LS', 'IP')
UNSUPPORTED_EXTENDED = {
    'AM': 'aperture macro (sizes ignored, extents use centre points only)',
    'SR': 'step-and-repeat (only the first tile is counted)',
    'AB': 'aperture block (flash positions of the block are not expanded)',
}
FORMAT = re.compile(r'FSLAX(\d)(\d)Y(\d)(\d)$')


class GerberState:
    """Modal state of the Gerber reader."""

    def __init__(self, parsed):
        self.parsed = parsed
        self.scale = None
        self.unit = None
        self.x = self.y = 0.0
        self.mode = 1
        self.multi_quadrant = False

    def number(self, digits):
        return int(digits) / self.scale

    def point(self, coords):
        """The new (x, y) after applying a word's coordinates."""
        x = self.number(coords['X']) * self.unit if 'X' in coords else self.x
        y = self.number(coords['Y']) * self.unit if 'Y' in coords else self.y
        return x, y


def extended_command(state, body):
    """Handles one %...% block. Returns False to stop the file."""
    parsed = state.parsed
    for word in (w for w in body.split('*') if w):
        code = word[:2]
        if code == 'FS':
            match = FORMAT.match(word)
            if not match or match.group(1) != match.group(3):
                parsed.abort(f'unsupported coordinate format {word!r}')
                return False
            state.scale = 10 ** int(match.group(2))
        elif code == 'MO':
            state.unit = MM_PER_INCH if word.startswith('MOIN') else 1.0
        elif code in UNSUPPORTED_EXTENDED:
            parsed.note(UNSUPPORTED_EXTENDED[code])
        elif code not in IGNORED_EXTENDED:
            parsed.note(f'unknown extended command {code}')
    return True


def arc_extents(extents, start, end, offset, ccw):
    """Adds the bounding box of an arc (multi-quadrant, centre = start +
    offset) to extents.
    """
    (x0, y0), (x1, y1) = start, end
    cx, cy = x0 + offset[0], y0 + offset[1]
    radius = math.hypot(*offset)
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    full = 2 * math.pi
    sweep = (a1 - a0) % full if ccw else (a0 - a1) % full
    if math.hypot(x1 - x0, y1 - y0) < 1e-9:
        sweep = full
    extents.add(x0, y0)
    extents.add(x1, y1)
    for quarter in range(4):
        angle = quarter * math.pi / 2
        reach = (angle - a0) % full if ccw else (a0 - angle) % full
        if reach <= sweep:
            extents.add(cx + radius * math.cos(angle), cy + radius * math.sin(angle))


def draw(state, coords, d_code):
    """Handles a D01/D02/D03 operation."""
    parsed = state.parsed
    start = (state.x, state.y)
    end = state.point(coords)
    if d_code == 1:
        parsed.draws += 1
        if state.mode == 1:
            parsed.extents.add(*start)
            parsed.extents.add(*end)
        elif state.multi_quadrant and 'I' in coords:
            offset = (
                state.number(coords['I']) * state.unit,
                state.number(coords.get('J', '0')) * state.unit,
            )
            arc_extents(parsed.extents, start, end, offset, state.mode == 3)
        else:
            parsed.note('arc without G75 multi-quadrant mode (endpoints only)')
            parsed.extents.add(*start)
            parsed.extents.add(*end)
    elif d_code == 3:
        parsed.draws += 1
        parsed.extents.add(*end)
    state.x, state.y = end


def gerber_word(state, word):
    """Handles one data word. Returns False to stop the file."""
    parsed = state.parsed
    if word.startswith('G04'):
        return True
    if word == 'M02':
        return False
    for code in re.findall(r'G(\d+)', word):
        code = int(code)
        if code in (1, 2, 3):
            state.mode = code
        elif code == 74:
            state.multi_quadrant = False
        elif code == 75:
            state.multi_quadrant = True
        elif code == 91:
            parsed.abort('incremental coordinates (G91) are not supported')
            return False
        elif code not in (36, 37, 54, 55, 90):
            parsed.note(f'unsupported G{code:02d}')
    d_match = re.search(r'D(\d+)$', word)
    if not d_match or int(d_match.group(1)) >= 10:
        return True
    if state.scale is None or state.unit is None:
        parsed.abort('coordinates before the format and unit commands')
        return False
    coords = dict(re.findall(r'([XYIJ])([+-]?\d+)', word))
    draw(state, coords, int(d_match.group(1)))
    return True


def parse_gerber(text):
    """Reads an RS-274X file into a Parsed (extents of the centre points of
    draws and flashes in mm, and the draw count).
    """
    parsed = Parsed()
    state = GerberState(parsed)
    for extended, data in TOKEN.findall(text):
        word = ''.join(data.split())
        keep_going = (
            extended_command(state, extended) if extended
            else gerber_word(state, word) if word
            else True
        )
        if not keep_going:
            break
    return parsed


# --- Excellon reader --------------------------------------------------------

TOOL_DEFINITION = re.compile(r'T(\d+)C([\d.]+)')
HIT = re.compile(r'X([+-]?[\d.]+)Y([+-]?[\d.]+)(?:G85X([+-]?[\d.]+)Y([+-]?[\d.]+))?$')


def parse_excellon(text):
    """Reads a decimal-coordinate Excellon file into a Parsed: tools
    {number: diameter mm}, hits per tool and every hit point in mm.
    """
    parsed = Parsed()
    unit = 1.0
    tool = None
    in_header = True
    for line in (raw.strip() for raw in text.splitlines()):
        if not line or line.startswith(';'):
            continue
        if in_header:
            if line.startswith('INCH'):
                unit = MM_PER_INCH
            elif line in ('%', 'M95'):
                in_header = False
            elif match := TOOL_DEFINITION.match(line):
                parsed.tools[int(match.group(1))] = float(match.group(2)) * unit
            continue
        if line == 'M30':
            break
        if re.fullmatch(r'T\d+', line):
            tool = int(line[1:])
        elif match := HIT.match(line):
            if not excellon_hit(parsed, tool, match, unit):
                break
        elif not re.fullmatch(r'G\d+|M\d+|FMAT,\d', line):
            parsed.note(f'unsupported Excellon line {line!r} (routed slots?)')
    return parsed


def excellon_hit(parsed, tool, match, unit):
    """Counts one drill hit or slot. Returns False when the file cannot be
    read (integer coordinates).
    """
    values = [g for g in match.groups() if g is not None]
    if any('.' not in v for v in values):
        parsed.abort('Excellon coordinates without a decimal point')
        return False
    parsed.hits[tool] += 1
    for x, y in zip(values[0::2], values[1::2]):
        point = (float(x) * unit, float(y) * unit)
        parsed.points.append(point)
        parsed.extents.add(*point)
    return True


# --- Drill report -----------------------------------------------------------

REPORT_FILE = re.compile(r"Drill file '([^']+\.drl)'")
REPORT_TOOL = re.compile(r'T(\d+)\s+([\d.]+)\s*mm.*?\((\d+)\s+holes?\)')


def parse_drill_report(text):
    """{drill file name: Counter of (diameter mm to 3 places, holes)}."""
    sections = {}
    current = None
    for line in text.splitlines():
        if match := REPORT_FILE.search(line):
            current = sections.setdefault(Path(match.group(1)).name, Counter())
        elif current is not None and (match := REPORT_TOOL.search(line)):
            current[(round(float(match.group(2)), 3), int(match.group(3)))] += 1
    return sections


# --- Checks -----------------------------------------------------------------


def add(report, rule, severity, summary, at=None, fix=None, refs=()):
    report.add(Finding(rule, severity, 'measured', summary, list(refs), [], at, fix))


def skip(report, rule, why):
    add(report, rule, 'info', f'check skipped: {why}')


def is_gerber(path):
    return path.suffix in GERBER_EXTENSIONS or bool(COPPER_EXTENSION.search(path.name))


def is_drill(path):
    return path.suffix == '.drl'


def infer_expected(gerber_dir):
    """The layer file names implied by the Edge.Cuts file's stem, or None."""
    edges = sorted(gerber_dir.glob(f'*{EDGE_SUFFIX}'))
    if not edges:
        return None
    stem = edges[0].name[: -len(EDGE_SUFFIX)]
    inner = sorted(
        p.name for p in gerber_dir.glob(f'{stem}-In*_Cu.g*') if COPPER_EXTENSION.search(p.name)
    )
    return (
        f'{stem}-F_Cu.gtl', *inner, f'{stem}-B_Cu.gbl',
        f'{stem}-F_Mask.gts', f'{stem}-B_Mask.gbs',
        f'{stem}-F_Silkscreen.gto', f'{stem}-B_Silkscreen.gbo',
        f'{stem}-Edge_Cuts.gm1', f'{stem}-PTH.drl', f'{stem}-NPTH.drl',
    )


def check_layers(report, gerber_dir, expected):
    """Expected files exist and are non-empty; no other Gerber files."""
    for name in expected:
        path = gerber_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            add(report, 'GERBER_LAYER_MISSING', 'error', f'{name} is missing or empty',
                fix='re-run export_fab.py', refs=[name])
    present = [p for p in sorted(gerber_dir.iterdir()) if is_gerber(p) or is_drill(p)]
    for path in present:
        if path.name not in expected:
            add(report, 'GERBER_LAYER_EXTRA', 'warning',
                f'{path.name} is not a file the export writes', refs=[path.name])


def read_parsed(report, gerber_dir, name, parser):
    """Parses one file, adding its parser notes as info findings. None if
    the file is absent or the parser stopped early.
    """
    path = gerber_dir / name
    if not path.is_file():
        return None
    parsed = parser(path.read_text(errors='replace'))
    for note in parsed.notes:
        add(report, 'GERBER_UNSUPPORTED', 'info', f'{name}: {note}', refs=[name])
    return parsed if parsed.ok else None


def check_gerber_extents(report, gerber_dir, expected):
    """Copper extents inside the outline (error); other layers info only;
    copper layers with no draws warn. Returns the outline extents or None.
    """
    edge = next((n for n in expected if n.endswith(EDGE_SUFFIX)), None)
    outline = read_parsed(report, gerber_dir, edge, parse_gerber) if edge else None
    if outline is None or outline.extents.empty():
        skip(report, 'GERBER_OUTSIDE_OUTLINE', 'no readable Edge.Cuts outline')
        outline = None
    for name in expected:
        if not is_gerber(Path(name)) or name == edge:
            continue
        parsed = read_parsed(report, gerber_dir, name, parse_gerber)
        if parsed is None:
            continue
        copper = bool(COPPER_EXTENSION.search(name))
        if copper and parsed.draws == 0:
            add(report, 'GERBER_EMPTY_COPPER', 'warning',
                f'{name} has no draws or flashes', refs=[name])
            continue
        if outline is None or not parsed.extents.outside(outline.extents):
            continue
        add(report, 'GERBER_OUTSIDE_OUTLINE', 'error' if copper else 'info',
            f'{name} extends outside the outline: {parsed.extents.text()} '
            f'vs outline {outline.extents.text()}', refs=[name])
    return outline.extents if outline else None


def tool_summary(parsed):
    """Counter of (diameter mm to 3 places, hits) for a parsed drill file."""
    return Counter(
        (round(diameter, 3), parsed.hits[number])
        for number, diameter in parsed.tools.items()
        if parsed.hits[number]
    )


def check_drills(report, gerber_dir, expected, outline):
    """Drill hits inside the outline and tools matching drill_report.txt."""
    report_path = gerber_dir / 'drill_report.txt'
    sections = parse_drill_report(report_path.read_text()) if report_path.is_file() else {}
    if not report_path.is_file():
        skip(report, 'DRILL_MISMATCH', 'no drill_report.txt')
    elif not sections:
        skip(report, 'DRILL_MISMATCH', 'drill_report.txt has no recognised drill sections')
    for name in (n for n in expected if is_drill(Path(n))):
        parsed = read_parsed(report, gerber_dir, name, parse_excellon)
        if parsed is None:
            continue
        if sections and tool_summary(parsed) != sections.get(name, Counter()):
            add(report, 'DRILL_MISMATCH', 'error',
                f'{name}: file has {sorted(tool_summary(parsed).items())} (diameter, hits), '
                f'report has {sorted(sections.get(name, Counter()).items())}', refs=[name])
        if outline is None:
            skip(report, 'DRILL_OUTSIDE_OUTLINE', 'no outline extents')
            continue
        outside = [p for p in parsed.points if hit_outside(p, outline)]
        if outside:
            add(report, 'DRILL_OUTSIDE_OUTLINE', 'error',
                f'{name}: {len(outside)} hit(s) outside the outline', at=outside[0], refs=[name])


def hit_outside(point, outline):
    probe = Extents()
    probe.add(*point)
    return probe.outside(outline)


def check_zip(report, gerber_dir, zip_path):
    """The zip holds exactly the Gerber and drill files, byte for byte."""
    if not zip_path.is_file():
        add(report, 'ZIP_CONTENTS', 'error', f'{zip_path.name} is missing',
            fix='re-run export_fab.py')
        return
    folder = {p.name: p for p in gerber_dir.iterdir() if is_gerber(p) or is_drill(p)}
    with zipfile.ZipFile(zip_path) as archive:
        members = {info.filename: info for info in archive.infolist()}
    for name in sorted(set(members) | set(folder)):
        if name not in folder:
            problem = 'is in the zip but not in the folder (stale)'
        elif name not in members:
            problem = 'is in the folder but not in the zip'
        elif not same_bytes(folder[name], members[name]):
            problem = 'differs between the zip and the folder'
        else:
            continue
        add(report, 'ZIP_CONTENTS', 'error', f'{name} {problem}', refs=[name])


def same_bytes(path, info):
    data = path.read_bytes()
    return len(data) == info.file_size and zlib.crc32(data) == info.CRC


def check_fab(fab_dir, expected=None, zip_name=None):
    """Runs every check on a fabrication folder. expected is the layer file
    names the export writes (None infers them from the Edge.Cuts name);
    zip_name defaults to the single *.zip beside gerbers/.
    """
    fab_dir = Path(fab_dir)
    gerber_dir = fab_dir / 'gerbers'
    report = Report(TOOL, str(fab_dir), RULES)
    if not gerber_dir.is_dir():
        add(report, 'GERBER_LAYER_MISSING', 'error', f'{gerber_dir} does not exist')
        return report
    expected = tuple(expected) if expected else infer_expected(gerber_dir)
    if expected is None:
        add(report, 'GERBER_LAYER_MISSING', 'error', f'no *{EDGE_SUFFIX} in {gerber_dir}')
        return report
    check_layers(report, gerber_dir, expected)
    outline = check_gerber_extents(report, gerber_dir, expected)
    check_drills(report, gerber_dir, expected, outline)
    zips = [fab_dir / zip_name] if zip_name else sorted(fab_dir.glob('*.zip'))
    if len(zips) == 1:
        check_zip(report, gerber_dir, zips[0])
    else:
        add(report, 'ZIP_CONTENTS', 'error', f'expected one zip in {fab_dir}, found {len(zips)}')
    return report


def run(fab_dir, project, expected=None, zip_name=None, json_path=None,
        update_baseline=False):
    """Checks, prints the report and the baseline verdicts; returns the
    exit code.
    """
    report = check_fab(fab_dir, expected, zip_name)
    config = Config.load(Path(project).parent)
    report.apply(config)
    report.print_text()
    if json_path:
        report.write_json(json_path)
    return report.exit_code(config, update_baseline)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    add_common_arguments(parser)
    parser.add_argument('--fab-dir', help='fabrication folder (default: beside the project)')
    args = parser.parse_args()
    project = Path(args.project)
    fab_dir = Path(args.fab_dir) if args.fab_dir else project.parent / 'fabrication'
    sys.exit(run(fab_dir, project, json_path=args.json, update_baseline=args.update_baseline))


if __name__ == '__main__':
    main()
