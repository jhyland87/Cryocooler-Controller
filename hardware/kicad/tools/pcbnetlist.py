"""Netlist -> footprint/net tables for the PCB generator (pure Python, no pcbnet dependency).

Run with any python3; `gen_pcb.py` needs KiCad's bundled python for `pcbnew`.
"""
import subprocess
import tempfile
from pathlib import Path

from sexpr import find_all, parse, sval

KICAD_DIR = Path(__file__).resolve().parents[1]
KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'


def export_netlist(out_path):
    """Exports the root schematic netlist (kicadsexpr) to out_path."""
    subprocess.run([KICAD_CLI, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o',
                    str(out_path), str(KICAD_DIR / 'cryocooler.kicad_sch')], check=True,
                   capture_output=True)


def load_netlist():
    """Returns (parts, nets): parts[ref] = dict(value, footprint, sheet); nets[name] = [(ref, pin)]."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'n.net'
        export_netlist(path)
        root = parse(path.read_text())
    parts = {}
    for comp in find_all(find_all(root, 'components')[0], 'comp'):
        ref = sval(find_all(comp, 'ref')[0][1])
        sheet = ''
        for prop in find_all(comp, 'property'):
            if sval(find_all(prop, 'name')[0][1]) == 'Sheetname':
                sheet = sval(find_all(prop, 'value')[0][1])
        parts[ref] = {'value': sval(find_all(comp, 'value')[0][1]),
                      'footprint': sval(find_all(comp, 'footprint')[0][1]), 'sheet': sheet}
    nets = {}
    for net in find_all(find_all(root, 'nets')[0], 'net'):
        name = sval(find_all(net, 'name')[0][1])
        nets[name] = [(sval(find_all(n, 'ref')[0][1]), sval(find_all(n, 'pin')[0][1]))
                      for n in find_all(net, 'node')]
    return parts, nets
