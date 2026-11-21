"""Active-low nets and how they are drawn.

The generators and the firmware name these nets in plain ASCII (`ADS1220_CS`,
`IO_EXP_INT_N`). The schematic draws them with an overbar and no `_N`
(`~{ADS1220_CS}`, `~{IO_EXP_INT}`). `drawn()` makes the drawn name when a label or
sheet pin is written; `source()` maps a netlist name back so the checks keep
using the ASCII names.
"""

import re

ACTIVE_LOW = (
    # chip selects
    'AD9833_FSYNC', 'AD5453_SYNC', 'INA239_CS', 'EXPANDER_CS', 'ACS_CS',
    'ADS1220_CS', 'IMU_CS', 'AMBIENT_CS', 'IO_ADC_CS', 'IO_DAC_CS', 'IO_EXP_CS',
    'RS485_CS', 'EXP_CS_A', 'EXP_CS_B', 'EXP_CSA', 'EXP_CSB', 'CS_EN_N',
    # interrupts, alerts and fault flags
    'AMBIENT_INT', 'AMBIENT_CT', 'INA239_ALERT', 'PWR_INT', 'RS485_IRQ_N',
    'IO_EXP_INT_N', 'EXP_INT_N', 'IO_ADC_DRDY_N', 'PREC_EXC_FLT_N',
    'IO_OUT_FLT_A_N', 'PG_15V_N',
    *(f'IO{n}_SENS_FLT_N' for n in range(1, 5)),
    # buttons, resets, enables and control
    'PWR_BTN', 'DISP_PWR_BTN', 'PWR_KILL', 'DISP_RESET', 'ESP_BOOT',
    'RS485_RTS_N', *(f'IO{n}_BUF_OE_N' for n in range(1, 5)),
)

# `_N` names that are the negative side of a pair, not active-low
NEGATIVE_INPUTS = re.compile(r'PREC_[AB]_N(_PIN)?')

# Nets on a barred pin that are high when on, or where the pin's other job leads
HIGH_TRUE = re.compile(
    r'ESP_EN|IO\d_(SENS_EN|DIRECT)|PREC_EXC_EN|SPI_MISO'
    r'|GND|\+\w+|Net-\(.*\)|unconnected-.*'
)

_DRAWN = {name: '~{' + name.removesuffix('_N') + '}' for name in ACTIVE_LOW}
_SOURCE = {drawn_name: name for name, drawn_name in _DRAWN.items()}


def drawn(net):
    """The name a label or sheet pin shows for a generator net name."""
    return _DRAWN.get(net, net)


def source(net):
    """The generator name for a netlist name, keeping any sheet path."""
    path, _, short = net.rpartition('/')
    return (path + '/' if path else '') + _SOURCE.get(short, short)


def problems(nets):
    """Unbarred active-low nets in a netlist ({name: [(ref, pin, function)]}):
    a `_N` name, or a plain name on a barred pin.
    """
    found = []
    for name, nodes in nets.items():
        short = name.rpartition('/')[2]
        if short.startswith('~{'):
            continue
        if short.endswith('_N') and not NEGATIVE_INPUTS.fullmatch(short):
            found.append(f'{name}: _N suffix, draw it as ~{{...}}')
            continue
        barred = [f'{ref}.{fn}' for ref, _, fn in nodes if fn.startswith('~{')]
        if barred and not HIGH_TRUE.fullmatch(short):
            found.append(f'{name}: on barred pin {", ".join(barred)}')
    return found
