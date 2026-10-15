"""Builds hardware/kicad/lib/cryocooler.kicad_sym: clean on-grid symbols for
parts missing from KiCad.
"""

import math
from pathlib import Path

import sexpr

OUT = Path(__file__).resolve().parent.parent / 'lib' / 'cryocooler.kicad_sym'
GRID = 2.54


def f(value):
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def pin_line(side, number, name, ptype, x, y, hide=False):
    angle = {'left': 0, 'right': 180, 'top': 270, 'bottom': 90}[side]
    hidden = ' (hide yes)' if hide else ''
    return (
        f'\t\t\t(pin {ptype} line (at {f(x)} {f(y)} {angle}) (length '
        f'{GRID}){hidden}\n'
        f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
        f'\t\t\t\t(number "{number}" (effects (font (size 1.27 '
        f'1.27))))\n\t\t\t)'
    )


def symbol(
    name,
    ref,
    description,
    datasheet,
    footprint,
    left=(),
    right=(),
    top=(),
    bottom=(),
    keywords='',
    y_override=None,
    tip_x=None,
    half_height_min=0.0,
):
    """Each pin: (number_or_list, name, type). A list of numbers stacks them on
    one location.

    y_override maps a pin number to its fixed y (mm) on the left/right sides;
    tip_x fixes the side-pin tip x.
    """
    y_override = y_override or {}

    def longest(pins):
        return max([len(p[1]) for p in pins if p] or [0])

    half_width = max(
        7.62,
        math.ceil((longest(left) + longest(right)) * 0.75 / 2.54) * 2.54 / 1.0
        + 2.54,
    )
    edge_width = (max(len(top), len(bottom), 1) - 1) * GRID + GRID
    half_width = max(half_width, math.ceil(edge_width / GRID) * GRID)
    if tip_x is not None:
        half_width = tip_x - GRID
    rows = max(len(left), len(right), 1)
    half_height = max(
        rows * GRID / 2 + GRID, 5.08 if (top or bottom) else 2.54
    )
    if y_override:
        half_height = max(
            half_height, max(abs(v) for v in y_override.values()) + GRID
        )
    half_height = math.ceil(max(half_height, half_height_min) / GRID) * GRID
    lines = []

    def place(side, pins):
        count = len(pins)
        for index, pin in enumerate(pins):
            if pin is None:
                continue
            numbers, pname, ptype = pin
            if side in ('left', 'right'):
                y = (
                    half_height
                    - GRID * (index + 1)
                    - (half_height - GRID * (rows + 1) / 1.0) / 2
                )
                first = numbers[0] if isinstance(numbers, list) else numbers
                y = y_override.get(
                    first,
                    round((half_height - GRID - index * GRID) / 1.27) * 1.27,
                )
                x = (
                    -(half_width + GRID)
                    if side == 'left'
                    else half_width + GRID
                )
            else:
                x = (index - (count - 1) / 2) * 2 * GRID
                y = (
                    half_height + GRID
                    if side == 'top'
                    else -(half_height + GRID)
                )
            numbers = numbers if isinstance(numbers, list) else [numbers]
            for position, number in enumerate(numbers):
                # extra stacked pins are hidden and passive so they don't
                # create implicit power nets
                lines.append(
                    pin_line(
                        side,
                        number,
                        pname,
                        'passive' if position else ptype,
                        x,
                        y,
                        hide=position > 0,
                    )
                )

    place('left', left)
    place('right', right)
    place('top', top)
    place('bottom', bottom)
    props = [
        ('Reference', ref, half_width, half_height + GRID, 'left'),
        ('Value', name, -half_width, half_height + GRID, 'left'),
        ('Footprint', footprint, 0, 0, None),
        ('Datasheet', datasheet, 0, 0, None),
        ('Description', description, 0, 0, None),
        ('ki_keywords', keywords, 0, 0, None),
    ]
    out = [
        f'\t(symbol "{name}"',
        '\t\t(pin_names (offset 1.016))',
        '\t\t(exclude_from_sim no)',
        '\t\t(in_bom yes)',
        '\t\t(on_board yes)',
        '\t\t(in_pos_files yes)',
        '\t\t(duplicate_pin_numbers_are_jumpers no)',
    ]
    for key, value, x, y, justify in props:
        hide = ' (hide yes)' if key not in ('Reference', 'Value') else ''
        just = f' (justify {justify})' if justify else ''
        out.append(
            f'\t\t(property "{key}" "{value}" (at {f(x)} {f(y)} 0) (show_name '
            f'no) (do_not_autoplace no){hide} '
            f'(effects (font (size 1.27 1.27)){just}))'
        )
    out.append(f'\t\t(symbol "{name}_0_1"')
    out.append(
        f'\t\t\t(rectangle (start {f(-half_width)} {f(half_height)}) (end '
        f'{f(half_width)} {f(-half_height)}) '
        f'(stroke (width 0.254) (type default)) (fill (type background)))'
    )
    out.append('\t\t)')
    out.append(f'\t\t(symbol "{name}_1_1"')
    out.extend(lines)
    out.append('\t\t)')
    out.append('\t)')
    return '\n'.join(out)


def from_stock(
    lib,
    stock_name,
    name,
    ref,
    left=(),
    right=(),
    top=(),
    bottom=(),
    keywords='',
    keep_rows=False,
    half_height_min=0.0,
    y_map=None,
):
    """Re-lays-out a stock-library symbol: each side lists pin numbers (a list
    stacks pins on one spot).

    Pin names and electrical types are copied from the stock symbol, so only
    the positions change.
    """
    stock = sexpr.stock_symbol(lib, stock_name)
    info = {
        number: (pin_name, ptype)
        for number, pin_name, _x, _y, _a, _l, ptype in sexpr.pins(stock)
    }

    stock_y = {
        number: y for number, _n, _x, y, _a, _l, _t in sexpr.pins(stock)
    }

    def side(numbers):
        result = []
        for entry in numbers:
            if entry is None:
                result.append(None)
                continue
            first = entry[0] if isinstance(entry, list) else entry
            pin_name, ptype = info[first]
            result.append((entry, pin_name, ptype))
        return result

    props = {
        sexpr.sval(p[1]): sexpr.sval(p[2])
        for p in sexpr.find_all(stock, 'property')
    }
    y_override = dict(y_map) if y_map else None
    tip_x = None
    if keep_rows:
        y_override = {
            pin: stock_y[pin]
            for pin in list(left) + list(right)
            if pin is not None
        }
        tip_x = max(
            abs(info_x)
            for _n, _p, info_x, _y, _a, _l, _t in sexpr.pins(stock)
            if _a in (0.0, 180.0)
        )
    return symbol(
        name,
        ref,
        props.get('Description', ''),
        props.get('Datasheet', ''),
        props.get('Footprint', ''),
        left=side(left),
        right=side(right),
        top=side(top),
        bottom=side(bottom),
        keywords=keywords,
        y_override=y_override,
        tip_x=tip_x,
        half_height_min=half_height_min,
    )


SYMBOLS = [
    symbol(
        'AD633JRZ-R7',
        'U',
        'Analog Devices low-cost 4-quadrant analog multiplier, '
        'W=(X1-X2)(Y1-Y2)/10V+Z, SOIC-8',
        'https://www.analog.com/media/en/'
        'technical-documentation/data-sheets/ad633.pdf',
        'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
        left=[
            ('7', 'X1', 'input'),
            ('1', 'Y1', 'input'),
            ('8', 'X2', 'input'),
            ('2', 'Y2', 'input'),
            ('4', 'Z', 'input'),
        ],
        right=[('5', 'W', 'output')],
        top=[('6', '+VS', 'power_in')],
        bottom=[('3', '-VS', 'power_in')],
        keywords='multiplier analog',
    ),
    symbol(
        'ACS37800KMACTR-030B3-SPI',
        'U',
        'Allegro isolated power monitor IC, +/-30A, SPI, SOIC-16W',
        'https://www.allegromicro.com/-/media/files/datasheets/'
        'acs37800-datasheet.pdf',
        'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
        left=[
            ('15', 'VINN', 'input'),
            ('16', 'VINP', 'input'),
            (['5', '6', '7', '8'], 'IP-', 'passive'),
            (['1', '2', '3', '4'], 'IP+', 'passive'),
        ],
        right=[
            ('12', 'MISO', 'output'),
            ('11', 'SCLK', 'input'),
            ('10', 'MOSI', 'input'),
            ('9', '~{CS}', 'input'),
        ],
        top=[('13', 'VCC', 'power_in')],
        bottom=[('14', 'GND', 'power_in')],
        keywords='current voltage power monitor',
    ),
    symbol(
        'ISO7741DW',
        'U',
        'TI quad-channel reinforced digital isolator, 3 forward / 1 reverse, '
        'SOIC-16W',
        'https://www.ti.com/lit/ds/symlink/iso7741.pdf',
        'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
        left=[
            ('7', 'EN1', 'input'),
            ('3', 'INA', 'input'),
            ('4', 'INB', 'input'),
            ('5', 'INC', 'input'),
            ('6', 'OUTD', 'output'),
        ],
        right=[
            ('10', 'EN2', 'input'),
            ('14', 'OUTA', 'output'),
            ('13', 'OUTB', 'output'),
            ('12', 'OUTC', 'output'),
            ('11', 'IND', 'input'),
        ],
        top=[('1', 'VCC1', 'power_in'), ('16', 'VCC2', 'power_in')],
        bottom=[
            (['2', '8'], 'GND1', 'power_in'),
            (['9', '15'], 'GND2', 'power_in'),
        ],
        keywords='isolator',
    ),
    symbol(
        'MIE1W0505BGLVH-3R-Z',
        'PS',
        'Murata 1W isolated 5V to 5V DC-DC converter, SMD',
        'https://www.murata.com/products/productdata/'
        '8807037583390/kdc-mie1w.pdf',
        'cryocooler:CONV_MIE1W0505BGLVH-3R-Z',
        left=[('9_10', 'VIN', 'power_in'), ('8', 'EN', 'input')],
        right=[('5_6', 'VOUT', 'power_out'), ('7', 'VSEL', 'passive')],
        bottom=[
            (['1', '11_12'], 'GND1', 'power_in'),
            (['2', '3_4'], 'GND2', 'power_in'),
        ],
        keywords='dcdc isolated',
    ),
    symbol(
        'ADS122C04IPWR',
        'U',
        'TI 24-bit, 2-kSPS, 4-channel delta-sigma ADC with I2C, PGA and '
        'IDACs, TSSOP-16',
        'https://www.ti.com/lit/ds/symlink/ads122c04.pdf',
        'Package_SO:TSSOP-16_4.4x5mm_P0.65mm',
        left=[
            ('1', 'A0', 'input'),
            ('2', 'A1', 'input'),
            ('3', '~{RESET}', 'input'),
            ('15', 'SDA', 'bidirectional'),
            ('16', 'SCL', 'input'),
            ('14', '~{DRDY}', 'output'),
        ],
        right=[
            ('6', 'AIN3', 'passive'),
            ('7', 'AIN2', 'passive'),
            ('10', 'AIN1', 'passive'),
            ('11', 'AIN0', 'passive'),
            ('9', 'REFP', 'input'),
        ],
        top=[('12', 'AVDD', 'power_in'), ('13', 'DVDD', 'power_in')],
        bottom=[
            ('8', 'REFN', 'input'),
            ('5', 'AVSS', 'power_in'),
            ('4', 'DGND', 'power_in'),
        ],
        keywords='adc rtd',
    ),
    symbol(
        'LTC2954CTS8-2',
        'U',
        'Pushbutton on/off controller with open-drain EN# output, TSOT-23-8',
        'https://www.analog.com/media/en/'
        'technical-documentation/data-sheets/2954fb.pdf',
        'Package_TO_SOT_SMD:TSOT-23-8',
        left=[('2', 'PB', 'input'), ('3', 'ONT', 'input')],
        top=[('1', 'VIN', 'power_in')],
        right=[
            ('8', '~{KILL}', 'input'),
            ('7', 'PDT', 'input'),
            ('6', '~{EN}', 'open_collector'),
            ('5', '~{INT}', 'open_collector'),
        ],
        bottom=[('4', 'GND', 'power_in')],
        keywords='power button',
    ),
    symbol(
        'CL25N8-G',
        'U',
        'Microchip/Supertex CL25 25mA constant-current regulator '
        '(two-terminal), SOT-89 (TO-243AA). TO-92 option: CL25N3-G',
        'https://ww1.microchip.com/downloads/en/DeviceDoc/CL25.pdf',
        'Package_TO_SOT_SMD:SOT-89-3',
        left=[('1', 'VA', 'passive')],
        right=[('2', 'VB', 'passive'), ('3', 'NC', 'no_connect')],
        keywords='led current limiter',
    ),
    symbol(
        'LSM6DSOXTR',
        'U',
        'ST iNEMO 6-axis IMU, SPI/I2C, LGA-14',
        'https://www.st.com/resource/en/datasheet/lsm6dsox.pdf',
        'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y',
        left=[
            ('12', '~{CS}', 'input'),
            ('13', 'SPC', 'input'),
            ('14', 'SDI', 'input'),
            ('1', 'SDO', 'output'),
            ('10', 'OCS_Aux', 'passive'),
            ('11', 'SDO_Aux', 'passive'),
        ],
        right=[('4', 'INT1', 'output'), ('9', 'INT2', 'output')],
        top=[('8', 'VDD', 'power_in'), ('5', 'VDDIO', 'power_in')],
        bottom=[
            ('2', 'SDx', 'passive'),
            ('3', 'SCx', 'passive'),
            (['6', '7'], 'GND', 'power_in'),
        ],
        keywords='imu accelerometer',
        half_height_min=15.24,
    ),
    from_stock(
        'Sensor_Energy',
        'INA237',
        'INA237',
        'U',
        left=['8', '10', '9'],
        right=['4', '5', '3'],
        top=['6'],
        bottom=['2', '7', '1'],
        keywords='power monitor',
        keep_rows=True,
        half_height_min=15.24,
    ),
    from_stock(
        'Regulator_Linear',
        'ADP7182AUJZ',
        'ADP7182AUJZ',
        'U',
        left=['2', '3'],
        right=['5', '4'],
        bottom=['1'],
        keywords='negative ldo',
    ),
    from_stock(
        'Regulator_Switching',
        'ADP5071AREZ',
        'ADP5071AREZ',
        'U',
        left=['8', '9', '17', '19', '18', '16', '12', '11', '10', '5'],
        right=['3', '2', '7', '14', '13', '20'],
        bottom=['4', '6', '1', '15', '21'],
        keywords='dual output regulator',
        keep_rows=True,
        half_height_min=26,
    ),
    from_stock(
        'Analog_DAC',
        'MCP4921',
        'MCP4921',
        'U',
        left=['2', '3', '4'],
        right=['8'],
        top=['1', '6'],
        bottom=['5', '7'],
        keywords='dac',
        keep_rows=True,
    ),
    from_stock(
        '74xGxx',
        '74AHCT1G125',
        '74AHCT1G125',
        'U',
        left=['2'],
        right=['4'],
        top=['5'],
        bottom=['1', '3'],
        keywords='buffer level shifter',
    ),
    from_stock(
        'Power_Protection',
        'USBLC6-2SC6',
        'USBLC6-2SC6',
        'U',
        left=['4', '6'],
        right=['3', '1'],
        top=['5'],
        bottom=['2'],
        keywords='esd usb',
        half_height_min=7.62,
        y_map={'4': 2.54, '3': 2.54, '6': 0.0, '1': 0.0},
    ),
    from_stock(
        'Oscillator',
        'SG-8002CA',
        'SG-8002CA',
        'U',
        right=['3'],
        top=['1', '4'],
        bottom=['2'],
        keywords='oscillator',
    ),
]


def main():
    text = (
        '(kicad_symbol_lib\n\t(version 20251024)\n\t(generator '
        '"cryocooler_gen")\n'
        '\t(generator_version "1.0")\n' + '\n'.join(SYMBOLS) + '\n)\n'
    )
    OUT.write_text(text)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
