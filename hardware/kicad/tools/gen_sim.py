"""Generates the simulation-only KiCad project for the sine-wave chain
(hardware/kicad/sim/).

The real design (cryocooler.*) is never touched. This project copies the
signal_gen analog chain with the same component values and swaps the parts
that have no SPICE model for sources or stand-ins:
  AD9833 + oscillator -> 60 Hz VSIN
  AD5453              -> behavioural model in sim/models/, code set by CODE
OPA1656 / OPA188 use TI's original models.

Run: python3 hardware/kicad/tools/gen_sim.py
"""

import json

import kicadgen
from kicadgen import Sheet, next_ref
import gen_schematic as real
from gen_schematic import (
    hcap,
    hres,
    net_label,
    pin_cell,
    place_ic,
    rail_symbol,
    vres,
    wire,
)

SIM_DIR = real.ROOT_DIR / 'sim'
PROJECT = 'cryocooler_sim'
ROOT_UUID = '3f6c1b7e-5d0a-4e8b-9a52-7c1d4e2a9b10'
OPAMP_FOOTPRINT = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'

# Sim fields; ${KIPRJMOD} is this sim/ folder.
OPA1656_SIM = {
    'Sim.Device': 'SUBCKT',
    'Sim.Library': '${KIPRJMOD}/models/ti_original/OPA1656.LIB',
    'Sim.Name': 'OPA1656',
    'Sim.Pins': '3=IN+ 2=IN- 8=VCC 4=VEE 1=OUT',
}
OPA188_SIM = {
    'Sim.Device': 'SUBCKT',
    'Sim.Library': '${KIPRJMOD}/models/ti_original/OPAx188.LIB',
    'Sim.Name': 'OPAx188',
    'Sim.Pins': '3=IN+ 2=IN- 7=VCC 4=VEE 6=OUT',
}
AD5453_SIM = {
    'Sim.Device': 'SUBCKT',
    'Sim.Library': '${KIPRJMOD}/models/ad5453_behavioral.lib',
    'Sim.Name': 'AD5453',
    'Sim.Pins': '1=iout 2=gnd 7=vref 8=rfb',
    'Sim.Params': 'code={code}',
}


def vsource(sh, value, column, row, params, sim_type):
    """Stock VSIN/VDC with its Sim fields spelled out; pin 1 (+) is four cells
    above the centre.
    """
    lib_id = (
        'Simulation_SPICE:VSIN'
        if sim_type == 'SIN'
        else 'Simulation_SPICE:VDC'
    )
    props = {
        'Sim.Device': 'V',
        'Sim.Type': sim_type,
        'Sim.Pins': '1=+ 2=-',
        'Sim.Params': params,
    }
    return sh.add(
        lib_id,
        next_ref('V'),
        value,
        column * 1.27,
        row * 1.27,
        auto=False,
        props=props,
    )


def sim_ground(sh, cell):
    """Node-0 ground symbol (KiCad's simulator needs a net named 0)."""
    kicadgen._pwr_counter[0] += 1
    part = sh.add(
        'Simulation_SPICE:0',
        f'#GND{kicadgen._pwr_counter[0]:03d}',
        '0',
        cell[0] * 1.27,
        cell[1] * 1.27,
        auto=False,
        props={'Sim.Device': 'NONE'},
    )
    part.is_power = True
    return part


def sim_drop_ground(sh, cell, length=2):
    wire(sh, cell, (cell[0], cell[1] + length))
    return sim_ground(sh, (cell[0], cell[1] + length))


def rail_source(sh, net, volts, column, row):
    """DC supply rail: the + pin goes to the rail net (or ground for a negative
    rail).
    """
    source = vsource(sh, f'{volts:g}V', column, row, f'dc={abs(volts)}', 'DC')
    top, bottom = pin_cell(source, '1'), pin_cell(source, '2')
    if volts > 0:
        wire(sh, top, (top[0], top[1] - 2))
        rail_symbol(sh, net, (top[0], top[1] - 2))
        sim_drop_ground(sh, bottom)
    else:
        wire(sh, bottom, (bottom[0], bottom[1] + 2))
        rail_symbol(sh, net, (bottom[0], bottom[1] + 2))
        wire(sh, top, (top[0], top[1] - 2))
        sim_ground(sh, (top[0], top[1] - 2))
    return source


def build_signal_sim(sh):
    """Hand-laid copy of the signal_gen analog chain with sim sources."""
    sh.handwired = True
    sh.note(
        'SIMULATION ONLY - not part of the build schematic. Mirrors '
        'hardware/kicad/sheets/signal_gen; '
        'regenerate with tools/gen_sim.py.',
        20,
        12,
    )
    sh.note(
        'VSIN stands in for AD9833 + C43 input (0.313 V pk about 0.35 V); the AD5453 is '
        'a behavioural model whose code is the .param below (0..16383).',
        20,
        17,
    )
    sh.note(
        'Probe VREF (AD5453 VREF), OPA_OUT and SIG_SINE (output). Expect '
        'SIG_SINE = -VREF x code / 16384.',
        20,
        22,
    )
    sh.note(
        'R35 + R92 = 47k + 3.6k || 1 nF (gain 16.3, pole ~3 kHz) so full code gives '
        'about 10 Vpp, as on the signal_gen sheet. MMBZ9V1 clamp left out here.',
        20,
        24.5,
    )
    sh.note(
        'Allow ~1 s for the 1 uF / 100 k input coupling to settle; read '
        'peaks after 2 s.',
        20,
        27,
    )
    sh.note('.tran 100u 3 0 100u', 20, 32)
    sh.note('.param code=16383', 20, 36)
    sh.note('.step param code list 0 4096 8192 12288 16383', 20, 40)
    # 60 Hz source in place of oscillator + AD9833, then the same AC coupling
    # as the real sheet
    source = vsource(
        sh, 'AD9833 60Hz', 64, 66, 'dc=0.35 ampl=0.313 f=60 ac=1', 'SIN'
    )
    wire(sh, pin_cell(source, '1'), (74, 62))
    sim_drop_ground(sh, pin_cell(source, '2'))
    hcap(sh, '1uF', 77, 62)
    wire(sh, (80, 62), (92, 62), (92, 58), (104, 58))
    vres(sh, '100k', 86, 62)
    drop_ground_sim(sh, (86, 68))
    # OPA1656 unit A: non-inverting gain of 16.3 (1 + 50.6k/3.3k)
    opa_ref = next_ref('U')
    opa_a = sh.add(
        'Amplifier_Operational:OPA1656ID',
        opa_ref,
        'OPA1656ID',
        110 * 1.27,
        60 * 1.27,
        unit=1,
        auto=False,
        footprint=OPAMP_FOOTPRINT,
        props=OPA1656_SIM,
    )
    wire(sh, pin_cell(opa_a, '2'), (100, 62), (100, 70))
    hres(sh, '47k', 105, 70)
    hres(sh, '3.6k', 111, 70)
    hcap(sh, '1nF', 108, 74)
    wire(sh, (102, 70), (102, 74), (105, 74))
    wire(sh, (114, 70), (114, 74), (111, 74))
    wire(sh, (102, 70), (100, 70))
    vres(sh, '3.3k', 100, 70)
    drop_ground_sim(sh, (100, 76))
    wire(sh, pin_cell(opa_a, '1'), (120, 60), (120, 70), (114, 70))
    wire(sh, (120, 60), (124, 60))
    hres(sh, '220', 127, 60)
    wire(sh, (130, 60), (150, 60), (180, 60))
    net_label(sh, 'VREF', (150, 60), 0)
    # OPA1656 unit C: supply pins
    opa_p = sh.add(
        'Amplifier_Operational:OPA1656ID',
        opa_ref,
        'OPA1656ID',
        260 * 1.27,
        90 * 1.27,
        unit=3,
        auto=False,
        footprint=OPAMP_FOOTPRINT,
        props=OPA1656_SIM,
    )
    top, bottom = pin_cell(opa_p, '8'), pin_cell(opa_p, '4')
    wire(sh, top, (top[0], top[1] - 6))
    rail_symbol(sh, '+15V', (top[0], top[1] - 6))
    wire(
        sh, bottom, (bottom[0], bottom[1] + 4), (bottom[0] + 4, bottom[1] + 4)
    )
    rail_symbol(sh, '-15V', (bottom[0] + 4, bottom[1] + 4))
    # AD5453 behavioural model on the real symbol, then the OPA188 output stage
    mdac = place_ic(
        sh,
        'cryocooler:AD5453WBCPZ',
        'AD5453WBCPZ-RL',
        190,
        64,
        'Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm',
        props=AD5453_SIM,
    )
    drop_ground_sim(sh, pin_cell(mdac, '2'))
    for pin in ('3', '4', '5', '6', '9'):
        sh.nc(mdac, pin)
    opa188 = place_ic(
        sh,
        'Amplifier_Operational:OPA188xxD',
        'OPA188ID',
        226,
        62,
        OPAMP_FOOTPRINT,
        props=OPA188_SIM,
    )
    for pin in ('1', '5', '8'):
        sh.nc(opa188, pin)
    iout, rfb = pin_cell(mdac, '1'), pin_cell(mdac, '8')
    inverting = pin_cell(opa188, '2')
    wire(sh, iout, (206, iout[1]), (206, inverting[1]), inverting)
    sim_drop_ground(sh, pin_cell(opa188, '3'))
    out = pin_cell(opa188, '6')
    wire(sh, rfb, (204, rfb[1]), (204, 84), (out[0] + 4, 84), (out[0] + 4, out[1]))
    wire(sh, out, (out[0] + 4, out[1]), (out[0] + 8, out[1]))
    net_label(sh, 'OPA_OUT', (out[0] + 4, 84), 0)
    hres(sh, '100', out[0] + 11, out[1])
    wire(sh, (out[0] + 14, out[1]), (out[0] + 16, out[1]))
    hcap(sh, '10uF', out[0] + 19, out[1])
    wire(sh, (out[0] + 22, out[1]), (out[0] + 26, out[1]), (out[0] + 32, out[1]))
    net_label(sh, 'SIG_SINE', (out[0] + 32, out[1]), 0)
    vres(sh, '100k', out[0] + 26, out[1])
    drop_ground_sim(sh, (out[0] + 26, out[1] + 6))
    top, bottom = pin_cell(opa188, '7'), pin_cell(opa188, '4')
    wire(sh, top, (top[0], top[1] - 6))
    rail_symbol(sh, '+15V', (top[0], top[1] - 6))
    wire(sh, bottom, (bottom[0], bottom[1] + 4), (bottom[0] + 4, bottom[1] + 4))
    rail_symbol(sh, '-15V', (bottom[0] + 4, bottom[1] + 4))
    # supply rails
    rail_source(sh, '+15V', 15, 30, 100)
    rail_source(sh, '-15V', -15, 50, 100)


def drop_ground_sim(sh, cell, length=2):
    return sim_drop_ground(sh, cell, length)


def main():
    kicadgen.reset_uuids()
    kicadgen.PROJECT = PROJECT
    root = Sheet('Signal Chain Simulation', f'{PROJECT}.kicad_sch', 'A3')
    root.uid = ROOT_UUID
    root.path = '/' + ROOT_UUID
    build_signal_sim(root)
    root.finalize()
    SIM_DIR.mkdir(exist_ok=True)
    (SIM_DIR / f'{PROJECT}.kicad_sch').write_text(root.render(ROOT_UUID))
    # KiCad rewrites these when the project is saved; only create them the
    # first time.
    library_table = SIM_DIR / 'sym-lib-table'
    if not library_table.exists():
        library_table.write_text(
            '(sym_lib_table\n  (version 7)\n  (lib (name "cryocooler")(type '
            '"KiCad")'
            '(uri "${KIPRJMOD}/../lib/cryocooler.kicad_sym")(options '
            '"")(descr "Parts missing from stock KiCad"))\n)\n'
        )
    project_file = SIM_DIR / f'{PROJECT}.kicad_pro'
    if not project_file.exists():
        project = {
            'meta': {'filename': f'{PROJECT}.kicad_pro', 'version': 3},
            'sheets': [[ROOT_UUID, 'Root']],
            'schematic': {'drawing': {}},
        }
        project_file.write_text(json.dumps(project, indent=2) + '\n')
    print('wrote', SIM_DIR / f'{PROJECT}.kicad_sch')


if __name__ == '__main__':
    main()
