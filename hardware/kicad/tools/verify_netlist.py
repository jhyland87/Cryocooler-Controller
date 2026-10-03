"""Checks an exported netlist: ESP32 GPIO map vs pin_config.h, footprints, dangling nets.

Usage: kicad-cli sch export netlist --format kicadsexpr -o /tmp/x.net cryocooler.kicad_sch
       python3 verify_netlist.py /tmp/x.net
"""
import re
import sys
from pathlib import Path

from sexpr import find_all, parse, sval

EXPECTED = {
    'SDA': 8, 'SCL': 9, 'SPI_SCK': 42, 'SPI_MOSI': 41, 'SPI_MISO': 40, 'AD9833_FSYNC': 7,
    'MCP4921_CS': 5, 'IMU_CS': 1, 'IMU_INT1': 2, 'IMU_INT2': 39, 'ACS_CS': 17, 'ACS_SCK': 11,
    'ACS_MOSI': 12, 'ACS_MISO': 13, 'AMP_REM_EN': 6, 'PWR_KILL': 10, 'LED_FAULT': 14,
    'LED_READY': 15, 'FLOW_TACH': 18, 'FAN_ALERT': 21, 'NTC_ADC': 4, 'STATUS_RGB': 38,
}
PIN_CONFIG = Path(__file__).resolve().parents[3] / 'include' / 'config' / 'pin_config.h'


def load(path):
    root = parse(Path(path).read_text())
    comps = {sval(find_all(c, 'ref')[0][1]): c for c in find_all(find_all(root, 'components')[0], 'comp')}
    nets = {}
    for net in find_all(find_all(root, 'nets')[0], 'net'):
        name = sval(find_all(net, 'name')[0][1])
        nodes = [(sval(find_all(n, 'ref')[0][1]), sval(find_all(n, 'pin')[0][1]),
                  sval(find_all(n, 'pinfunction')[0][1]) if find_all(n, 'pinfunction') else '')
                 for n in find_all(net, 'node')]
        nets[name] = nodes
    return comps, nets


def main(path):
    comps, nets = load(path)
    problems = 0
    esp = next(ref for ref, c in comps.items() if 'ESP32-S3-WROOM-2' in sval(find_all(c, 'value')[0][1]))
    pin_to_net = {}
    net_pins = {}
    for name, nodes in nets.items():
        for ref, pin, function in nodes:
            if ref == esp:
                net_pins[name.split('/')[-1]] = function.rsplit('_', 1)[0]
    for net, gpio in EXPECTED.items():
        want = f'IO{gpio}'
        got = net_pins.get(net)
        status = 'ok' if got == want else 'MISMATCH'
        print(f'{net:14s} GPIO{gpio:<3d} -> module pin {got}  [{status}]')
        problems += status != 'ok'
    # footprints
    missing = [ref for ref, c in comps.items() if not find_all(c, 'footprint') or not sval(find_all(c, 'footprint')[0][1])]
    print('parts without footprint:', missing)
    problems += len(missing)
    single = {n: v for n, v in nets.items() if len(v) < 2 and not n.startswith('unconnected')}
    print('single-node nets:', list(single))
    print('parts:', len(comps), 'nets:', len(nets))
    return problems


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1]) else 0)
