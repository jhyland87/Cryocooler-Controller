"""Builds hardware/kicad/lib/cryocooler.kicad_sym: clean on-grid symbols for parts missing from KiCad."""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'lib' / 'cryocooler.kicad_sym'
GRID = 2.54


def f(value):
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def pin_line(side, number, name, ptype, x, y, hide=False):
    angle = {'left': 0, 'right': 180, 'top': 270, 'bottom': 90}[side]
    hidden = ' (hide yes)' if hide else ''
    return (f'\t\t\t(pin {ptype} line (at {f(x)} {f(y)} {angle}) (length {GRID}){hidden}\n'
            f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{number}" (effects (font (size 1.27 1.27))))\n\t\t\t)')


def symbol(name, ref, description, datasheet, footprint, left=(), right=(), top=(), bottom=(),
           keywords=''):
    """Each pin: (number_or_list, name, type). A list of numbers stacks them on one location."""
    def longest(pins):
        return max([len(p[1]) for p in pins] or [0])

    half_width = max(7.62, math.ceil((longest(left) + longest(right)) * 0.75 / 2.54) * 2.54 / 1.0 + 2.54)
    rows = max(len(left), len(right), 1)
    half_height = max(rows * GRID / 2 + GRID, 5.08 if (top or bottom) else 2.54)
    half_height = math.ceil(half_height / GRID) * GRID
    lines = []

    def place(side, pins):
        count = len(pins)
        for index, (numbers, pname, ptype) in enumerate(pins):
            if side in ('left', 'right'):
                y = half_height - GRID * (index + 1) - (half_height - GRID * (rows + 1) / 1.0) / 2
                y = round((half_height - GRID - index * GRID) / 1.27) * 1.27
                x = -(half_width + GRID) if side == 'left' else half_width + GRID
            else:
                x = (index - (count - 1) / 2) * 2 * GRID
                y = half_height + GRID if side == 'top' else -(half_height + GRID)
            numbers = numbers if isinstance(numbers, list) else [numbers]
            for position, number in enumerate(numbers):
                # extra stacked pins are hidden and passive so they don't create implicit power nets
                lines.append(pin_line(side, number, pname, 'passive' if position else ptype, x, y, hide=position > 0))

    place('left', left)
    place('right', right)
    place('top', top)
    place('bottom', bottom)
    props = [('Reference', ref, half_width, half_height + GRID, 'left'),
             ('Value', name, -half_width, half_height + GRID, 'left'),
             ('Footprint', footprint, 0, 0, None), ('Datasheet', datasheet, 0, 0, None),
             ('Description', description, 0, 0, None), ('ki_keywords', keywords, 0, 0, None)]
    out = [f'\t(symbol "{name}"', '\t\t(pin_names (offset 1.016))', '\t\t(exclude_from_sim no)', '\t\t(in_bom yes)',
           '\t\t(on_board yes)', '\t\t(in_pos_files yes)', '\t\t(duplicate_pin_numbers_are_jumpers no)']
    for key, value, x, y, justify in props:
        hide = ' (hide yes)' if key not in ('Reference', 'Value') else ''
        just = f' (justify {justify})' if justify else ''
        out.append(f'\t\t(property "{key}" "{value}" (at {f(x)} {f(y)} 0) (show_name no) (do_not_autoplace no){hide} '
                   f'(effects (font (size 1.27 1.27)){just}))')
    out.append(f'\t\t(symbol "{name}_0_1"')
    out.append(f'\t\t\t(rectangle (start {f(-half_width)} {f(half_height)}) (end {f(half_width)} {f(-half_height)}) '
               f'(stroke (width 0.254) (type default)) (fill (type background)))')
    out.append('\t\t)')
    out.append(f'\t\t(symbol "{name}_1_1"')
    out.extend(lines)
    out.append('\t\t)')
    out.append('\t)')
    return '\n'.join(out)


SYMBOLS = [
    symbol('AD633JRZ-R7', 'U', 'Analog Devices low-cost 4-quadrant analog multiplier, W=(X1-X2)(Y1-Y2)/10V+Z, SOIC-8',
           'https://www.analog.com/media/en/technical-documentation/data-sheets/ad633.pdf',
           'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
           left=[('7', 'X1', 'input'), ('8', 'X2', 'input'), ('1', 'Y1', 'input'), ('2', 'Y2', 'input'),
                 ('4', 'Z', 'input')],
           right=[('5', 'W', 'output')],
           top=[('6', '+VS', 'power_in')], bottom=[('3', '-VS', 'power_in')], keywords='multiplier analog'),
    symbol('ACS37800KMACTR-030B3-SPI', 'U', 'Allegro isolated power monitor IC, +/-30A, SPI, SOIC-16W',
           'https://www.allegromicro.com/-/media/files/datasheets/acs37800-datasheet.pdf',
           'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
           left=[(['1', '2', '3', '4'], 'IP+', 'passive'), (['5', '6', '7', '8'], 'IP-', 'passive'),
                 ('16', 'VINP', 'input'), ('15', 'VINN', 'input')],
           right=[('9', '~{CS}', 'input'), ('10', 'MOSI', 'input'), ('11', 'SCLK', 'input'),
                  ('12', 'MISO', 'output')],
           top=[('13', 'VCC', 'power_in')], bottom=[('14', 'GND', 'power_in')], keywords='current voltage power monitor'),
    symbol('ISO7741DW', 'U', 'TI quad-channel reinforced digital isolator, 3 forward / 1 reverse, SOIC-16W',
           'https://www.ti.com/lit/ds/symlink/iso7741.pdf',
           'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
           left=[('3', 'INA', 'input'), ('4', 'INB', 'input'), ('5', 'INC', 'input'), ('6', 'OUTD', 'output'),
                 ('7', 'EN1', 'input')],
           right=[('14', 'OUTA', 'output'), ('13', 'OUTB', 'output'), ('12', 'OUTC', 'output'),
                  ('11', 'IND', 'input'), ('10', 'EN2', 'input')],
           top=[('1', 'VCC1', 'power_in'), ('16', 'VCC2', 'power_in')],
           bottom=[(['2', '8'], 'GND1', 'power_in'), (['9', '15'], 'GND2', 'power_in')], keywords='isolator'),
    symbol('MIE1W0505BGLVH-3R-Z', 'PS', 'Murata 1W isolated 5V to 5V DC-DC converter, SMD',
           'https://www.murata.com/products/productdata/8807037583390/kdc-mie1w.pdf',
           'cryocooler:CONV_MIE1W0505BGLVH-3R-Z',
           left=[('9_10', 'VIN', 'power_in'), ('8', 'EN', 'input'), (['1', '11_12'], 'GND1', 'power_in')],
           right=[('5_6', 'VOUT', 'power_out'), ('7', 'VSEL', 'passive'), (['2', '3_4'], 'GND2', 'power_in')],
           keywords='dcdc isolated'),
    symbol('ADS122C04IPWR', 'U', 'TI 24-bit, 2-kSPS, 4-channel delta-sigma ADC with I2C, PGA and IDACs, TSSOP-16',
           'https://www.ti.com/lit/ds/symlink/ads122c04.pdf',
           'Package_SO:TSSOP-16_4.4x5mm_P0.65mm',
           left=[('1', 'A0', 'input'), ('2', 'A1', 'input'), ('3', '~{RESET}', 'input'), ('15', 'SDA', 'bidirectional'),
                 ('16', 'SCL', 'input'), ('14', '~{DRDY}', 'output')],
           right=[('6', 'AIN3', 'passive'), ('7', 'AIN2', 'passive'), ('10', 'AIN1', 'passive'),
                  ('11', 'AIN0', 'passive'), ('9', 'REFP', 'input'), ('8', 'REFN', 'input')],
           top=[('12', 'AVDD', 'power_in'), ('13', 'DVDD', 'power_in')],
           bottom=[('5', 'AVSS', 'power_in'), ('4', 'DGND', 'power_in')], keywords='adc rtd'),
    symbol('LTC2954CTS8-2', 'U', 'Pushbutton on/off controller with open-drain EN# output, TSOT-23-8',
           'https://www.analog.com/media/en/technical-documentation/data-sheets/2954fb.pdf',
           'Package_TO_SOT_SMD:TSOT-23-8',
           left=[('1', 'VIN', 'power_in'), ('2', 'PB', 'input'), ('3', 'ONT', 'input')],
           right=[('8', '~{KILL}', 'input'), ('7', 'PDT', 'input'), ('6', '~{EN}', 'open_collector'),
                  ('5', '~{INT}', 'open_collector')],
           bottom=[('4', 'GND', 'power_in')], keywords='power button'),
    symbol('CL25N8-G', 'U', 'Microchip/Supertex CL25 25mA constant-current regulator (two-terminal), SOT-89 (TO-243AA). TO-92 option: CL25N3-G',
           'https://ww1.microchip.com/downloads/en/DeviceDoc/CL25.pdf',
           'Package_TO_SOT_SMD:SOT-89-3',
           left=[('1', 'VA', 'passive')], right=[('2', 'VB', 'passive'), ('3', 'NC', 'no_connect')],
           keywords='led current limiter'),
    symbol('LSM6DSOXTR', 'U', 'ST iNEMO 6-axis IMU, SPI/I2C, LGA-14',
           'https://www.st.com/resource/en/datasheet/lsm6dsox.pdf',
           'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y',
           left=[('12', '~{CS}', 'input'), ('13', 'SPC', 'input'), ('14', 'SDI', 'input'),
                 ('1', 'SDO', 'output'), ('2', 'SDx', 'passive'), ('3', 'SCx', 'passive'),
                 ('10', 'OCS_Aux', 'passive'), ('11', 'SDO_Aux', 'passive')],
           right=[('4', 'INT1', 'output'), ('9', 'INT2', 'output')],
           top=[('8', 'VDD', 'power_in'), ('5', 'VDDIO', 'power_in')],
           bottom=[(['6', '7'], 'GND', 'power_in')], keywords='imu accelerometer'),
]


def main():
    text = ('(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "cryocooler_gen")\n'
            '\t(generator_version "1.0")\n' + '\n'.join(SYMBOLS) + '\n)\n')
    OUT.write_text(text)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
