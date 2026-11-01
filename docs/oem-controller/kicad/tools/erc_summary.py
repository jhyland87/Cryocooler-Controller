"""Summarise a kicad-cli ERC json report: counts per type and per sheet, details of real errors."""
import collections
import json
import sys

# Expected for a label-stub transcription: a net used by one pin only on a page,
# and power pins with no driver (no PWR_FLAGs on transcribed pages).
EXPECTED = {'label_dangling', 'power_pin_not_driven', 'pin_not_driven', 'global_label_dangling',
            'isolated_pin_label', 'lib_symbol_issues', 'lib_symbol_mismatch', 'footprint_link_issues'}

report = json.load(open(sys.argv[1]))
counts = collections.Counter()
for sheet in report['sheets']:
    for violation in sheet['violations']:
        counts[violation['type']] += 1
        if violation['type'] not in EXPECTED:
            items = '; '.join(item['description'] for item in violation['items'])
            print(f"  {sheet['path']}: {violation['type']}: {items}")
print('ERC counts:', dict(counts))
