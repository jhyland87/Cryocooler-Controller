"""Generates the simulation-only KiCad project for the sine-wave chain (hardware/kicad/sim/).

The real design (cryocooler.*) is never touched. This project copies the signal_gen analog chain with the
same component values and swaps the parts that have no SPICE model for sources:
  AD9833 + oscillator -> 60 Hz VSIN       MCP4921 + reference -> VDC control voltage
OPA1656 / OPA188 use TI's original models; the AD633 uses the behavioural model in sim/models/.

Run: python3 hardware/kicad/tools/gen_sim.py
"""
import json
from pathlib import Path

import kicadgen
from kicadgen import Sheet, next_ref
import gen_schematic as real
from gen_schematic import (at, drop_ground, hcap, hres, net_label, pin_cell, place_ic, rail_symbol, vres, wire)

SIM_DIR = real.ROOT_DIR / 'sim'
PROJECT = 'cryocooler_sim'
ROOT_UUID = '3f6c1b7e-5d0a-4e8b-9a52-7c1d4e2a9b10'
OPAMP_FOOTPRINT = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'

# Sim fields; ${KIPRJMOD} is this sim/ folder.
OPA1656_SIM = {'Sim.Device': 'SUBCKT', 'Sim.Library': '${KIPRJMOD}/models/ti_original/OPA1656.LIB',
               'Sim.Name': 'OPA1656', 'Sim.Pins': '3=IN+ 2=IN- 8=VCC 4=VEE 1=OUT'}
OPA188_SIM = {'Sim.Device': 'SUBCKT', 'Sim.Library': '${KIPRJMOD}/models/ti_original/OPAx188.LIB',
              'Sim.Name': 'OPAx188', 'Sim.Pins': '3=IN+ 2=IN- 7=VCC 4=VEE 6=OUT'}
AD633_SIM = {'Sim.Device': 'SUBCKT', 'Sim.Library': '${KIPRJMOD}/models/ad633_behavioral.lib',
             'Sim.Name': 'AD633', 'Sim.Pins': '1=y1 2=y2 3=vsn 4=z 5=w 6=vsp 7=x1 8=x2'}


def vsource(sh, value, column, row, params, sim_type):
    """Stock VSIN/VDC with its Sim fields spelled out; pin 1 (+) is four cells above the centre."""
    lib_id = 'Simulation_SPICE:VSIN' if sim_type == 'SIN' else 'Simulation_SPICE:VDC'
    props = {'Sim.Device': 'V', 'Sim.Type': sim_type, 'Sim.Pins': '1=+ 2=-', 'Sim.Params': params}
    return sh.add(lib_id, next_ref('V'), value, column * 1.27, row * 1.27, auto=False, props=props)


def sim_ground(sh, cell):
    """Node-0 ground symbol (KiCad's simulator needs a net named 0)."""
    kicadgen._pwr_counter[0] += 1
    part = sh.add('Simulation_SPICE:0', f'#GND{kicadgen._pwr_counter[0]:03d}', '0', cell[0] * 1.27, cell[1] * 1.27,
                  auto=False, props={'Sim.Device': 'NONE'})
    part.is_power = True
    return part


def sim_drop_ground(sh, cell, length=2):
    wire(sh, cell, (cell[0], cell[1] + length))
    return sim_ground(sh, (cell[0], cell[1] + length))


def rail_source(sh, net, volts, column, row):
    """DC supply rail: the + pin goes to the rail net (or ground for a negative rail)."""
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
    """Hand-laid copy of the signal_gen analog chain with simulation sources."""
    sh.handwired = True
    sh.note('SIMULATION ONLY - not part of the build schematic. Mirrors hardware/kicad/sheets/signal_gen; '
            'regenerate with tools/gen_sim.py.', 20, 12)
    sh.note('VSIN stands in for AD9833 + C10 input (0.3 V pk about 0.35 V); VDC "DAC_OUT" stands in for MCP4921 '
            '(0..2.5 V, x4 = 0..10 V control).', 20, 17)
    sh.note('Probe SINE_X (AD633 X1), CTL (AD633 Y1) and SIG_SINE (output). Expect SIG_SINE = SINE_X x CTL / 10.',
            20, 22)
    sh.note('TRIAL: R8 = 51k (gain 16.45) so CTL = 10 V gives ~5 V pk (10 Vpp, 3.5 Vrms). Real signal_gen still has 33k.',
            20, 24.5)
    sh.note('Allow ~1 s for the 1 uF / 100 k input coupling to settle; read peaks after 2 s.', 20, 27)
    sh.note('.tran 100u 3 0 100u', 20, 32)
    sh.note('.param vdac=2.5', 20, 36)
    sh.note('.step param vdac list 0 0.625 1.25 1.875 2.5', 20, 40)
    sh.note('DAC_OUT = {vdac}: edit .param (single run) or the .step list (sweep); keep vdac <= 2.5 V.', 20, 44)
    # 60 Hz source in place of oscillator + AD9833, then the same AC coupling as the real sheet
    source = vsource(sh, 'AD9833 60Hz', 64, 66, 'dc=0.35 ampl=0.3 f=60 ac=1', 'SIN')
    wire(sh, pin_cell(source, '1'), (74, 62))
    sim_drop_ground(sh, pin_cell(source, '2'))
    hcap(sh, '1uF', 77, 62)
    wire(sh, (80, 62), (92, 62), (92, 58), (104, 58))
    vres(sh, '100k', 86, 62)
    drop_ground_sim(sh, (86, 68))
    # OPA1656 unit A: non-inverting gain of 11
    opa_ref = next_ref('U')
    opa_a = sh.add('Amplifier_Operational:OPA1656ID', opa_ref, 'OPA1656ID', 110 * 1.27, 60 * 1.27, unit=1,
                   auto=False, footprint=OPAMP_FOOTPRINT, props=OPA1656_SIM)
    wire(sh, pin_cell(opa_a, '2'), (100, 62), (100, 70))
    hres(sh, '51k', 110, 70)
    wire(sh, (107, 70), (100, 70))
    vres(sh, '3.3k', 100, 70)
    drop_ground_sim(sh, (100, 76))
    wire(sh, pin_cell(opa_a, '1'), (120, 60), (120, 70), (113, 70))
    wire(sh, (120, 60), (124, 60))
    hres(sh, '100', 127, 60)
    wire(sh, (130, 60), (192, 60))
    net_label(sh, 'SINE_X', (150, 60), 0)
    # OPA1656 unit C: supply pins
    opa_p = sh.add('Amplifier_Operational:OPA1656ID', opa_ref, 'OPA1656ID', 260 * 1.27, 90 * 1.27, unit=3,
                   auto=False, footprint=OPAMP_FOOTPRINT, props=OPA1656_SIM)
    top, bottom = pin_cell(opa_p, '8'), pin_cell(opa_p, '4')
    wire(sh, top, (top[0], top[1] - 6))
    rail_symbol(sh, '+15V', (top[0], top[1] - 6))
    wire(sh, bottom, (bottom[0], bottom[1] + 4), (bottom[0] + 4, bottom[1] + 4))
    rail_symbol(sh, '-15V', (bottom[0] + 4, bottom[1] + 4))
    # AD633 behavioural multiplier on the real symbol
    mult = place_ic(sh, 'cryocooler:AD633JRZ-R7', 'AD633JRZ-R7', 200, 66, 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
                    props=AD633_SIM)
    wire(sh, pin_cell(mult, '8'), (188, 62), (188, 68))
    wire(sh, pin_cell(mult, '2'), (188, 66))
    wire(sh, pin_cell(mult, '4'), (188, 68))
    drop_ground_sim(sh, (188, 68))
    plus = pin_cell(mult, '6')
    wire(sh, plus, (plus[0], 48))
    rail_symbol(sh, '+15V', (plus[0], 48))
    minus = pin_cell(mult, '3')
    wire(sh, minus, (minus[0], 80), (minus[0] + 4, 80))
    rail_symbol(sh, '-15V', (minus[0] + 4, 80))
    wire(sh, pin_cell(mult, '5'), (214, 60))
    hres(sh, '100', 217, 60)
    wire(sh, (220, 60), (224, 60))
    hcap(sh, '10uF', 227, 60)
    wire(sh, (230, 60), (240, 60))
    net_label(sh, 'SIG_SINE', (240, 60), 0)
    vres(sh, '100k', 234, 60)
    drop_ground_sim(sh, (234, 66))
    # control voltage: DC source in place of MCP4921 + reference, then the real OPA188 gain-of-4 stage
    opa188 = place_ic(sh, 'Amplifier_Operational:OPA188xxD', 'OPA188ID', 130, 110, OPAMP_FOOTPRINT, props=OPA188_SIM)
    dac = vsource(sh, 'DAC_OUT', 100, 112, 'dc={vdac}', 'DC')
    dac_top = pin_cell(dac, '1')
    wire(sh, dac_top, (110, dac_top[1]), (110, 108), pin_cell(opa188, '3'))
    sim_drop_ground(sh, pin_cell(dac, '2'))
    for pin in ('1', '5', '8'):
        sh.nc(opa188, pin)
    wire(sh, pin_cell(opa188, '2'), (120, 112), (120, 132))
    wire(sh, pin_cell(opa188, '6'), (146, 110), (146, 132), (133, 132))
    hres(sh, '30k', 130, 132)
    wire(sh, (127, 132), (120, 132))
    vres(sh, '10k', 120, 132)
    drop_ground_sim(sh, (120, 138))
    top, bottom = pin_cell(opa188, '7'), pin_cell(opa188, '4')
    wire(sh, top, (top[0], 98))
    rail_symbol(sh, '+15V', (top[0], 98))
    wire(sh, bottom, (bottom[0], 120), (bottom[0] + 4, 120))
    rail_symbol(sh, '-15V', (bottom[0] + 4, 120))
    wire(sh, (146, 110), (170, 110), (170, 64), pin_cell(mult, '1'))
    net_label(sh, 'CTL', (170, 90), 90)
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
    # KiCad rewrites these when the project is saved; only create them the first time.
    library_table = SIM_DIR / 'sym-lib-table'
    if not library_table.exists():
        library_table.write_text(
            '(sym_lib_table\n  (version 7)\n  (lib (name "cryocooler")(type "KiCad")'
            '(uri "${KIPRJMOD}/../lib/cryocooler.kicad_sym")(options "")(descr "Parts missing from stock KiCad"))\n)\n')
    project_file = SIM_DIR / f'{PROJECT}.kicad_pro'
    if not project_file.exists():
        project = {'meta': {'filename': f'{PROJECT}.kicad_pro', 'version': 3}, 'sheets': [[ROOT_UUID, 'Root']],
                   'schematic': {'drawing': {}}}
        project_file.write_text(json.dumps(project, indent=2) + '\n')
    print('wrote', SIM_DIR / f'{PROJECT}.kicad_sch')


if __name__ == '__main__':
    main()
