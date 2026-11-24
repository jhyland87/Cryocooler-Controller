"""Shared findings, suppressions and baseline handling for the board and
schematic check scripts.

A check builds a Report of Finding objects. The project's board_checks.json
(beside the .kicad_pro) can suppress findings and name a baseline file. Every
key is optional:

    {
      "suppress": [
        {"rule_id": "DECAP_DISTANCE",
         "refs": ["C12", "C1?"],         glob or list of globs (optional)
         "nets": "+3V3",                 glob or list of globs (optional)
         "at": [46.95, 93.0],            finding within 0.5 mm (optional)
         "reason": "why this is fine"}   required
      ],
      "baseline": "tools/board_checks_baseline.json",
      "net_currents": {},                free-form section for one check
      "hot_loops": {}
    }

The baseline is a JSON file {tool: {rule_id: count}}, path relative to the
project folder, so the check scripts share one file. A count above its baseline fails (exit 1): a change may not add a
finding. A count below it passes and asks for --update-baseline, so the
baseline only goes down. A rule that is not in the baseline must be 0.
Suppressed findings stay in the output, marked, and do not count. Info
findings never count.
"""

import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_PROJECT = (
    Path(__file__).resolve().parent.parent / 'cryocooler.kicad_pro'
)
CONFIG_NAME = 'board_checks.json'
AT_REACH_MM = 0.5
SEVERITIES = ('error', 'warning', 'info')
CONFIDENCES = ('measured', 'heuristic')


@dataclass
class Finding:
    """One problem a check found. severity is error, warning or info;
    confidence is measured (computed from the design) or heuristic (a rule
    of thumb). suppressed holds the reason once the config suppresses the
    finding; a check never sets it.
    """

    rule_id: str
    severity: str
    confidence: str
    summary: str
    refs: List[str] = field(default_factory=list)
    nets: List[str] = field(default_factory=list)
    at: Optional[Tuple[float, float]] = None
    fix: Optional[str] = None
    suppressed: Optional[str] = None

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f'severity {self.severity!r} not in {SEVERITIES}')
        if self.confidence not in CONFIDENCES:
            raise ValueError(
                f'confidence {self.confidence!r} not in {CONFIDENCES}'
            )

    def counts(self):
        """True when this finding counts toward the baseline."""
        return self.suppressed is None and self.severity != 'info'

    def sort_key(self):
        at = self.at if self.at is not None else (0.0, 0.0)
        return (
            self.rule_id,
            sorted(self.refs),
            sorted(self.nets),
            self.at is not None,
            at,
        )

    def to_dict(self):
        """The finding as plain JSON data, lists sorted, position in mm."""
        return {
            'rule_id': self.rule_id,
            'severity': self.severity,
            'confidence': self.confidence,
            'summary': self.summary,
            'refs': sorted(self.refs),
            'nets': sorted(self.nets),
            'at': (
                [round(self.at[0], 3), round(self.at[1], 3)]
                if self.at is not None
                else None
            ),
            'fix': self.fix,
            'suppressed': self.suppressed,
        }


def _globs(value):
    if value is None:
        return None
    return [value] if isinstance(value, str) else list(value)


def _near(at, point):
    return at is not None and math.dist(at, point) <= AT_REACH_MM


def _any_match(names, patterns):
    return any(fnmatchcase(n, p) for n in names for p in patterns)


class Config:
    """The settings from board_checks.json. A missing file gives the
    defaults: no suppressions, no baseline, no check sections.
    """

    def __init__(self, project_dir, data=None):
        self.dir = Path(project_dir)
        data = data or {}
        self.data = data
        self.suppressions = [
            self._parse_suppression(item, index)
            for index, item in enumerate(data.get('suppress', []))
        ]
        baseline = data.get('baseline')
        self.baseline = self.dir / baseline if baseline else None

    @classmethod
    def load(cls, project_dir):
        """Read board_checks.json from the project folder (the one holding
        the .kicad_pro). Exits with a message if a suppression has no
        reason.
        """
        path = Path(project_dir) / CONFIG_NAME
        data = json.loads(path.read_text()) if path.exists() else {}
        return cls(project_dir, data)

    @staticmethod
    def _parse_suppression(item, index):
        rule_id = item.get('rule_id')
        if not rule_id:
            sys.exit(f'{CONFIG_NAME}: suppress[{index}] has no "rule_id"')
        if not str(item.get('reason', '')).strip():
            sys.exit(
                f'{CONFIG_NAME}: suppress[{index}] ({rule_id}) has no '
                '"reason"; every suppression must say why'
            )
        return {
            'rule_id': rule_id,
            'refs': _globs(item.get('refs')),
            'nets': _globs(item.get('nets')),
            'at': item.get('at'),
            'reason': item['reason'],
        }

    def section(self, name, default=None):
        """The free-form settings for one check, or default."""
        return self.data.get(name, default)

    def suppression_for(self, finding):
        """The reason that suppresses this finding, or None. A suppression
        matches when its rule_id is equal and each glob set it gives matches
        at least one of the finding's refs (or nets). An "at" point matches
        a finding located within AT_REACH_MM of it.
        """
        for rule in self.suppressions:
            if rule['rule_id'] != finding.rule_id:
                continue
            if rule['refs'] is not None and not _any_match(
                finding.refs, rule['refs']
            ):
                continue
            if rule['nets'] is not None and not _any_match(
                finding.nets, rule['nets']
            ):
                continue
            if rule['at'] is not None and not _near(finding.at, rule['at']):
                continue
            return rule['reason']
        return None

    def read_baselines(self):
        """Every tool's baseline, {tool: {rule_id: count}}; empty if none is
        set or written.
        """
        if self.baseline is None or not self.baseline.exists():
            return {}
        return json.loads(self.baseline.read_text())

    def read_baseline(self, tool):
        """One tool's {rule_id: count} baseline."""
        return self.read_baselines().get(tool, {})


class Report:
    """The findings of one check run. tool names the script and board the
    board or project file. rules optionally maps a rule_id to a description
    for the verdict lines.
    """

    def __init__(self, tool, board, rules=None):
        self.tool = tool
        self.board = board
        self.rules = rules or {}
        self.findings: List[Finding] = []

    def add(self, finding):
        self.findings.append(finding)

    def apply(self, config):
        """Mark the findings the config suppresses."""
        for finding in self.findings:
            finding.suppressed = config.suppression_for(finding)

    def counts(self):
        """{rule_id: count} of unsuppressed error and warning findings."""
        return dict(Counter(f.rule_id for f in self.findings if f.counts()))

    def summary(self):
        live = [f for f in self.findings if f.suppressed is None]
        result = {s: sum(f.severity == s for f in live) for s in SEVERITIES}
        result['suppressed'] = len(self.findings) - len(live)
        return result

    def _sorted(self):
        return sorted(self.findings, key=Finding.sort_key)

    def write_json(self, path):
        """Write the report as JSON, ordered so equal runs give equal
        files.
        """
        data = {
            'tool': self.tool,
            'board': self.board,
            'summary': self.summary(),
            'findings': [f.to_dict() for f in self._sorted()],
        }
        Path(path).write_text(
            json.dumps(data, indent=2, sort_keys=True) + '\n'
        )

    def print_text(self):
        """Print one line per finding grouped by rule, suppressed ones last
        with their reason.
        """
        print(f'{self.tool}: {self.board}')
        ordered = sorted(
            self._sorted(), key=lambda f: f.suppressed is not None
        )
        for finding in ordered:
            where = ' '.join(sorted(finding.refs) + sorted(finding.nets))
            position = (
                f' at ({finding.at[0]:.2f}, {finding.at[1]:.2f})'
                if finding.at is not None
                else ''
            )
            line = (
                f'  [{finding.rule_id}] {finding.severity}/'
                f'{finding.confidence}: {finding.summary}'
            )
            if where:
                line += f' ({where})'
            line += position
            if finding.fix:
                line += f' - fix: {finding.fix}'
            if finding.suppressed is not None:
                line += f' - SUPPRESSED: {finding.suppressed}'
            print(line)

    def exit_code(self, config, update_baseline=False):
        """Compare the counts with the baseline and print a verdict per
        rule. Returns 1 if any rule is above its baseline, else 0. With
        update_baseline, writes the counts as this tool's baseline, leaving
        the other tools' entries alone, and returns 0.
        """
        counts = self.counts()
        if update_baseline:
            if config.baseline is None:
                sys.exit(f'no "baseline" in {config.dir / CONFIG_NAME}')
            baselines = config.read_baselines()
            baselines[self.tool] = counts
            config.baseline.write_text(
                json.dumps(baselines, indent=2, sort_keys=True) + '\n'
            )
            print(f'wrote {config.baseline}: {self.tool} {counts}')
            return 0
        baseline = config.read_baseline(self.tool)
        failed = False
        for rule_id in sorted(set(counts) | set(baseline) | set(self.rules)):
            count = counts.get(rule_id, 0)
            limit = baseline.get(rule_id, 0)
            verdict = 'ok'
            if count > limit:
                verdict = 'FAIL: above baseline'
                failed = True
            elif count < limit:
                verdict = 'below baseline: run --update-baseline'
            line = f'{rule_id}: {count} (baseline {limit}) {verdict}'
            if rule_id in self.rules:
                line += f' - {self.rules[rule_id]}'
            print(line)
        return 1 if failed else 0


def add_common_arguments(parser):
    """Add --project (the .kicad_pro), --json (report path) and
    --update-baseline to an argparse parser.
    """
    parser.add_argument(
        '--project',
        default=DEFAULT_PROJECT,
        help='path to the .kicad_pro (default: the cryocooler project)',
    )
    parser.add_argument('--json', help='write the report to this JSON file')
    parser.add_argument(
        '--update-baseline',
        action='store_true',
        help='write the current counts as the baseline',
    )
