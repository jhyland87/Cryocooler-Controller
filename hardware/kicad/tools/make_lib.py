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
    extra_pins=None,
):
    """Re-lays-out a stock-library symbol: each side lists pin numbers (a list
    stacks pins on one spot).

    Pin names and electrical types are copied from the stock symbol, so only
    the positions change. extra_pins = {number: (name, type)} adds pins the stock
    symbol lacks, such as an exposed pad.
    """
    stock = sexpr.stock_symbol(lib, stock_name)
    info = {
        number: (pin_name, ptype)
        for number, pin_name, _x, _y, _a, _l, ptype in sexpr.pins(stock)
    }
    info.update(extra_pins or {})

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


def stock_copy(lib, stock_name, name, props, extra_pins=()):
    """A stock symbol under a new name with the same pins and drawing, new
    property values, and extra pins: (copy_of, number, name, x, y, angle), each
    copied from an existing pin's style.
    """
    import copy

    node = copy.deepcopy(sexpr.stock_symbol(lib, stock_name))
    node[1] = ('s', name)
    for child in node[2:]:
        if not (isinstance(child, list) and child):
            continue
        if child[0] == 'property' and sexpr.sval(child[1]) in props:
            child[2] = ('s', props[sexpr.sval(child[1])])
        if child[0] == 'symbol':
            child[1] = ('s', sexpr.sval(child[1]).replace(stock_name, name, 1))
    units = [child for child in node if isinstance(child, list) and child and child[0] == 'symbol']
    for source, number, pin_name, x, y, angle in extra_pins:
        for unit in units:
            for pin in sexpr.find_all(unit, 'pin'):
                if sexpr.sval(sexpr.find_all(pin, 'number')[0][1]) != source:
                    continue
                added = copy.deepcopy(pin)
                sexpr.find_all(added, 'at')[0][1:4] = [str(x), str(y), str(angle)]
                sexpr.find_all(added, 'number')[0][1] = ('s', number)
                sexpr.find_all(added, 'name')[0][1] = ('s', pin_name)
                unit.append(added)
    return sexpr.dump(node, 1)


SYMBOLS = [
    symbol(
        'MJ-3523-SMT-TR',
        'J',
        'Same Sky 3.5 mm mono jack with tip switch, right angle, SMT',
        'https://www.sameskydevices.com/product/resource/mj-3523-smt.pdf',
        'cryocooler:SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD',
        left=[
            ('2', 'TIP', 'passive'),
            ('1', 'SLEEVE', 'passive'),
            ('10', 'SWITCH', 'passive'),
        ],
        keywords='audio jack 3.5mm',
    ),
    symbol(
        'INA239AIDGSR',
        'U',
        'TI 85 V, 16-bit SPI power monitor with 5 uV offset, VSSOP-10',
        'https://www.ti.com/lit/ds/symlink/ina239.pdf',
        'Package_SO:TSSOP-10_3x3mm_P0.5mm',
        left=[
            ('8', 'VBUS', 'input'),
            ('9', 'IN-', 'input'),
            ('10', 'IN+', 'input'),
        ],
        right=[
            ('1', '~{CS}', 'input'),
            ('5', 'SCLK', 'input'),
            ('2', 'SDI', 'input'),
            ('4', 'SDO', 'tri_state'),
            ('3', '~{ALERT}', 'open_collector'),
        ],
        top=[('6', 'VS', 'power_in')],
        bottom=[('7', 'GND', 'power_in')],
        keywords='power monitor spi',
    ),
    symbol(
        'LT3097ADJC',
        'U',
        'Analog Devices dual 500 mA positive/negative ultra-low noise LDO '
        'with power good, 22-lead DFN. Pads 23 (GND) and 24 (INN) are the '
        'exposed pads',
        'https://www.analog.com/media/en/technical-documentation/'
        'data-sheets/lt3097.pdf',
        'cryocooler:DFN-22-2EP_6x3mm_P0.5mm_LT3097',
        left=[
            (['1', '2'], 'INP', 'power_in'),
            ('3', 'ENP/UVP', 'input'),
            (['6', '7', '24'], 'INN', 'power_in'),
            ('8', 'ENN/UVN', 'input'),
        ],
        right=[
            (['21', '22'], 'OUTP', 'power_out'),
            ('20', 'OUTSP', 'input'),
            ('17', 'PGFBP', 'input'),
            ('4', 'PGP', 'open_collector'),
            ('18', 'SETP', 'passive'),
            (['15', '16'], 'OUTN', 'power_out'),
            ('14', 'OUTSN', 'input'),
            ('10', 'PGFBN', 'input'),
            ('9', 'PGN', 'open_collector'),
            ('12', 'SETN', 'passive'),
        ],
        bottom=[
            ('5', 'ILIMP', 'passive'),
            (['13', '19', '23'], 'GND', 'power_in'),
            ('11', 'ILIMN', 'passive'),
        ],
        keywords='dual ldo low noise power good',
        # pin rows in mm above the symbol centre: the positive group sits on
        # top, the negative group below, each with room for its feedback parts
        y_override={
            '1': 30.48,
            '3': 27.94,
            '6': -12.7,
            '8': -15.24,
            '21': 30.48,
            '20': 27.94,
            '17': 22.86,
            '4': 17.78,
            '18': 7.62,
            '15': -12.7,
            '14': -15.24,
            '10': -20.32,
            '9': -25.4,
            '12': -35.56,
        },
    ),
    symbol(
        '74AHCT1G125GM',
        'U',
        'Nexperia single 3-state buffer, TTL inputs (VIH 2.0 V at 4.5-5.5 V), VCC 4.5-5.5 V, '
        '+/-8 mA, XSON6 SOT886 1.0 x 1.45 mm. Pin 5 is not connected',
        'https://assets.nexperia.com/documents/data-sheet/74AHC_AHCT1G125.pdf',
        'cryocooler:Nexperia_XSON-6_SOT886_1.0x1.45mm_P0.5mm',
        left=[('2', 'A', 'input')],
        right=[('4', 'Y', 'tri_state'), ('5', 'NC', 'no_connect')],
        top=[('6', 'VCC', 'power_in')],
        bottom=[('1', '~{OE}', 'input'), ('3', 'GND', 'power_in')],
        keywords='buffer level shifter',
    ),
    symbol(
        '74LV1T34GX',
        'U',
        'Nexperia single-supply translating buffer: VIH 1.37 V at VCC 3.0-3.3 V, so 1.8 V '
        'logic in, VCC-level out; inputs 5 V tolerant. X2SON5 SOT1226-3 0.8 x 0.8 mm. '
        'Pin 1 is n.c.; tied to GND to escape the centre GND land',
        'https://assets.nexperia.com/documents/data-sheet/74LV1T34.pdf',
        'cryocooler:Nexperia_X2SON-5_SOT1226-3_0.8x0.8mm_P0.5mm',
        left=[('2', 'A', 'input')],
        right=[('4', 'Y', 'output')],
        top=[('5', 'VCC', 'power_in')],
        bottom=[('1', 'NC', 'passive'), ('3', 'GND', 'power_in')],
        keywords='buffer level shifter translator',
    ),
    symbol(
        'SN74LVC138A',
        'U',
        'TI 3-line to 8-line decoder, 1.65-3.6 V, inputs tolerate 5.5 V, '
        'active-low outputs, VQFN-16 (RGY)',
        'https://www.ti.com/lit/ds/symlink/sn74lvc138a.pdf',
        'Package_DFN_QFN:Texas_RGY_R-PVQFN-N16_EP2.05x2.55mm',
        left=[
            ('6', 'G1', 'input'),
            ('1', 'A', 'input'),
            ('2', 'B', 'input'),
            ('3', 'C', 'input'),
            ('4', '~{G2A}', 'input'),
            ('5', '~{G2B}', 'input'),
        ],
        right=[
            ('15', '~{Y0}', 'output'),
            ('14', '~{Y1}', 'output'),
            ('13', '~{Y2}', 'output'),
            ('12', '~{Y3}', 'output'),
            ('11', '~{Y4}', 'output'),
            ('10', '~{Y5}', 'output'),
            ('9', '~{Y6}', 'output'),
            ('7', '~{Y7}', 'output'),
        ],
        top=[('16', 'VCC', 'power_in')],
        bottom=[('8', 'GND', 'power_in'), ('17', 'EP', 'passive')],
        keywords='decoder demultiplexer chip select',
    ),
    symbol(
        'TSC2046EIRGVT',
        'U',
        'TI 4-wire resistive touch-screen controller, 12-bit SPI ADC, DOUT '
        'high-Z with CS high, VQFN-16 (RGV)',
        'https://www.ti.com/lit/ds/symlink/tsc2046e.pdf',
        'Package_DFN_QFN:Texas_RGV0016A_VQFN-16-1EP_4x4mm_P0.65mm_EP2.1x2.1mm',
        left=[
            ('6', 'X+', 'passive'),
            ('7', 'Y+', 'passive'),
            ('8', 'X-', 'passive'),
            ('9', 'Y-', 'passive'),
        ],
        right=[
            ('4', 'DCLK', 'input'),
            ('3', '~{CS}', 'input'),
            ('2', 'DIN', 'input'),
            ('16', 'DOUT', 'tri_state'),
            ('1', 'BUSY', 'tri_state'),
            ('15', '~{PENIRQ}', 'output'),
        ],
        top=[
            ('5', '+VCC', 'power_in'),
            ('14', 'IOVDD', 'power_in'),
            ('13', 'VREF', 'passive'),
        ],
        bottom=[
            ('10', 'GND', 'power_in'),
            ('11', 'VBAT', 'input'),
            ('12', 'AUX', 'input'),
            ('17', 'EP', 'passive'),
        ],
        keywords='touch screen controller resistive spi',
    ),
    symbol(
        'MCP23S08',
        'U',
        'Microchip 8-bit I/O expander, SPI (modes 0,0 and 1,1), 10 MHz at '
        '2.7-5.5 V, QFN-20 4 x 4 mm with exposed pad',
        'https://ww1.microchip.com/downloads/en/DeviceDoc/MCP23008-MCP23S08-Data-Sheet-20001919F.pdf',
        'Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.7x2.7mm',
        left=[
            ('5', '~{CS}', 'input'),
            ('19', 'SCK', 'input'),
            ('20', 'SI', 'input'),
            ('4', '~{RESET}', 'input'),
            ('3', 'A0', 'input'),
            ('2', 'A1', 'input'),
        ],
        right=[
            ('1', 'SO', 'tri_state'),
            ('9', 'GP0', 'bidirectional'),
            ('10', 'GP1', 'bidirectional'),
            ('11', 'GP2', 'bidirectional'),
            ('12', 'GP3', 'bidirectional'),
            ('13', 'GP4', 'bidirectional'),
            ('14', 'GP5', 'bidirectional'),
            ('15', 'GP6', 'bidirectional'),
            ('16', 'GP7', 'bidirectional'),
            ('7', 'INT', 'output'),
        ],
        top=[('18', 'VDD', 'power_in')],
        bottom=[('17', 'VSS', 'power_in'), ('21', 'EP', 'passive')],
        keywords='spi gpio expander',
    ),
    # SRL05P7 (MCC DFN1510-6): same pin functions as the USBLC6-2SC6, with
    # 1-6 and 3-4 joined inside, so it reuses the stock symbol
    from_stock(
        'Power_Protection',
        'USBLC6-2SC6',
        'SRL05P7',
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
        'Connector',
        '8P8C_Shielded',
        '8P8C_Shielded_Rails_At_Ends',
        'J',
        right=['4', '8', '7', '6', '5', '3', '1', '2'],
        bottom=['SH'],
        keywords='rj45 8p8c',
    ),
    # J14 Molex Micro-Lock Plus 2x4: pins in the RJ45 symbol's order, so the
    # IMU sheet keeps its layout
    from_stock(
        'Connector_Generic',
        'Conn_02x04_Odd_Even',
        'Conn_02x04_Rails_At_Ends',
        'J',
        right=['4', '8', '7', '6', '5', '3', '1', '2'],
        keywords='connector 2x04 micro-lock',
    ),
    symbol(
        'ACS37800KMACTR-015B5-SPI',
        'U',
        'Allegro isolated power monitor IC, +/-15 A, 5 V supply, SPI, SOIC-16W',
        'https://www.allegromicro.com/-/media/files/datasheets/'
        'acs37800-datasheet.pdf',
        'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
        left=[
            ('16', 'VINP', 'input'),
            ('15', 'VINN', 'input'),
            None,  # room for VINN's ground symbol
            (['5', '6', '7', '8'], 'IP-', 'passive'),
            (['1', '2', '3', '4'], 'IP+', 'passive'),
        ],
        right=[
            ('10', 'MOSI', 'input'),
            ('11', 'SCLK', 'input'),
            ('9', '~{CS}', 'input'),
            ('12', 'MISO', 'output'),
        ],
        top=[('13', 'VCC', 'power_in')],
        bottom=[('14', 'GND', 'power_in')],
        keywords='current voltage power monitor',
    ),
    symbol(
        'ISOW7741DFMR',
        'U',
        'TI quad digital isolator with integrated DC-DC, 3 forward / 1 reverse, '
        '5 kVrms reinforced, SOIC-20W (DFM, 8.1 mm clearance)',
        'https://www.ti.com/lit/ds/symlink/isow7741.pdf',
        'cryocooler:TI_DFM0020A',
        left=[
            ('8', 'EN/FLT', 'input'),
            ('7', 'EN_IO1', 'input'),
            ('2', 'INA', 'input'),
            ('3', 'INB', 'input'),
            ('4', 'INC', 'input'),
            ('5', 'OUTD', 'output'),
        ],
        right=[
            ('14', 'EN_IO2', 'input'),
            ('13', 'VSEL', 'input'),
            ('19', 'OUTA', 'output'),
            ('18', 'OUTB', 'output'),
            ('17', 'OUTC', 'output'),
            ('16', 'IND', 'input'),
        ],
        top=[
            ('1', 'VIO', 'power_in'),
            ('9', 'VDD', 'power_in'),
            ('12', 'VISOOUT', 'power_out'),
            ('20', 'VISOIN', 'power_in'),
        ],
        bottom=[
            ('6', 'GNDIO', 'power_in'),
            ('10', 'GND1', 'power_in'),
            ('15', 'GISOIN', 'power_in'),
            ('11', 'GND2', 'power_in'),
        ],
        tip_x=20.32,
        keywords='isolator dcdc spi',
    ),
    symbol(
        'ADS1220IRVAR',
        'U',
        'TI 24-bit, 2-kSPS, 4-channel delta-sigma ADC with SPI, PGA and '
        'IDACs, VQFN-16 (RVA). Thermal pad to AVSS',
        'https://www.ti.com/lit/ds/symlink/ads1220.pdf',
        'Package_DFN_QFN:Texas_RVA_VQFN-16-1EP_3.5x3.5mm_P0.5mm_EP2.14x2.14mm',
        left=[
            ('16', '~{CS}', 'input'),
            ('15', 'SCLK', 'input'),
            ('14', 'DIN', 'input'),
            ('13', 'DOUT/~{DRDY}', 'tri_state'),
            ('12', '~{DRDY}', 'output'),
        ],
        right=[
            ('4', 'AIN3/REFN1', 'passive'),
            ('5', 'AIN2', 'passive'),
            ('8', 'AIN1', 'passive'),
            ('9', 'AIN0/REFP1', 'passive'),
            ('7', 'REFP0', 'input'),
        ],
        top=[('10', 'AVDD', 'power_in'), ('11', 'DVDD', 'power_in')],
        bottom=[
            ('6', 'REFN0', 'input'),
            ('3', 'AVSS', 'power_in'),
            ('2', 'DGND', 'power_in'),
            ('1', 'CLK', 'input'),
            ('17', 'EP', 'passive'),
        ],
        keywords='adc rtd spi',
    ),
    symbol(
        'LTC2954CDDB-2',
        'U',
        'Pushbutton on/off controller with open-drain EN# output, 3 x 2 mm DFN-8 '
        '(DDB). Exposed pad 9 may float or go to GND',
        'https://www.analog.com/media/en/'
        'technical-documentation/data-sheets/2954fb.pdf',
        'Package_DFN_QFN:DFN-8-1EP_2x3mm_P0.5mm_EP0.61x2.2mm',
        left=[('3', 'PB', 'input'), ('2', 'ONT', 'input')],
        top=[('4', 'VIN', 'power_in')],
        right=[
            ('5', '~{KILL}', 'input'),
            ('6', 'PDT', 'input'),
            ('7', '~{EN}', 'open_collector'),
            ('8', '~{INT}', 'open_collector'),
        ],
        bottom=[('1', 'GND', 'power_in'), ('9', 'EP', 'passive')],
        keywords='power button',
    ),
    symbol(
        'AONR21307',
        'Q',
        'AOS P-channel MOSFET, -30 V, 11 mOhm at -10 V, 3 x 3 mm DFN',
        'https://www.aosmd.com/res/datasheets/AONR21307.pdf',
        'cryocooler:AOS_DFN3x3A_8L_EP1',
        left=[('4', 'G', 'input')],
        right=[
            (['1', '2', '3'], 'S', 'passive'),
            (['5', '6', '7', '8'], 'D', 'passive'),
        ],
        keywords='pmos power switch',
    ),
    symbol(
        'MMBZ9V1ALT1G',
        'D',
        'onsemi dual common-anode 9.1 V Zener, SOT-23. Pins 1 and 2 with pin 3 '
        'open form a bidirectional clamp',
        'https://www.onsemi.com/download/data-sheet/pdf/mmbz5v6alt1-d.pdf',
        'Package_TO_SOT_SMD:SOT-23',
        left=[('1', 'K1', 'passive')],
        right=[('2', 'K2', 'passive')],
        bottom=[('3', 'A', 'passive')],
        keywords='zener clamp bidirectional',
        tip_x=10.16,
    ),
    symbol(
        'ADP5071ACPZ',
        'U',
        'Analog Devices dual boost + inverting DC/DC, 2 A / 1 A switches, 4 x 4 mm '
        'LFCSP-20. Exposed pad 21 to AGND',
        'https://www.analog.com/media/en/technical-documentation/'
        'data-sheets/ADP5071.pdf',
        'Package_CSP:LFCSP-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm',
        left=[
            ('6', 'COMP1', 'passive'),
            ('7', 'EN1', 'input'),
            ('15', 'PVIN1', 'power_in'),
            ('17', 'PVIN2', 'power_in'),
            ('16', 'PVINSYS', 'power_in'),
            ('14', 'VREG', 'power_out'),
            ('10', 'COMP2', 'passive'),
            ('9', 'EN2', 'input'),
            ('8', 'SS', 'passive'),
            ('3', 'SEQ', 'input'),
            ('2', 'SYNC', 'input'),
            ('4', 'SLEW', 'input'),
        ],
        right=[
            ('1', 'INBK', 'passive'),
            ('20', 'SW1', 'passive'),
            ('5', 'FB1', 'input'),
            ('12', 'VREF', 'power_out'),
            ('11', 'FB2', 'input'),
            ('18', 'SW2', 'passive'),
        ],
        bottom=[
            ('13', 'AGND', 'power_in'),
            ('21', 'EP', 'passive'),
            ('19', 'PGND', 'power_in'),
        ],
        keywords='boost inverting dual switching regulator',
        # SEQ sits above SYNC and SLEW, so their ground wires never pass its tip
        y_override={
            '6': 20.32,
            '7': 17.78,
            '15': 12.7,
            '17': 10.16,
            '16': 7.62,
            '14': 5.08,
            '10': 0,
            '9': -2.54,
            '8': -7.62,
            '3': -10.16,
            '2': -12.7,
            '4': -15.24,
            '1': 15.24,
            '20': 12.7,
            '5': 10.16,
            '12': -5.08,
            '11': -7.62,
            '18': -10.16,
        },
        tip_x=15.24,
    ),
    symbol(
        'TPS62822DLCR',
        'U',
        'TI 2 A synchronous buck, 2.4-5.5 V in, 2.2 MHz, adjustable, VSON-HR-8 '
        '1.5 x 2 mm',
        'https://www.ti.com/lit/ds/symlink/tps62822.pdf',
        'Package_SON:Texas_VSON-HR-8_1.5x2mm_P0.5mm',
        left=[('7', 'VIN', 'power_in'), ('1', 'EN', 'input')],
        right=[
            ('6', 'SW', 'power_out'),
            ('2', 'FB', 'input'),
            ('8', 'PG', 'open_collector'),
            ('4', 'NC', 'no_connect'),
        ],
        bottom=[('3', 'AGND', 'power_in'), ('5', 'PGND', 'power_in')],
        keywords='buck regulator',
        tip_x=10.16,
    ),
    symbol(
        'TPS2116DRLR',
        'U',
        'TI 2-channel power mux, 1.6-5.5 V, 2.5 A, automatic priority or manual, '
        'SOT-583-8',
        'https://www.ti.com/lit/ds/symlink/tps2116.pdf',
        'Package_TO_SOT_SMD:SOT-583-8',
        left=[
            ('3', 'VIN1', 'power_in'),
            ('5', 'MODE', 'input'),
            ('4', 'PR1', 'input'),
            ('6', 'VIN2', 'power_in'),
        ],
        right=[(['2', '7'], 'VOUT', 'power_out'), ('8', 'ST', 'open_collector')],
        bottom=[('1', 'GND', 'power_in')],
        keywords='power mux priority',
    ),
    symbol(
        'AD5453WBCPZ',
        'U',
        'Analog Devices 14-bit current-output multiplying DAC, SPI, 3 x 3 mm '
        'LFCSP-8 (CP-8-3). VREF and RFB limited to +/-12 V',
        'https://www.analog.com/media/en/technical-documentation/'
        'data-sheets/AD5450_5451_5452_5453.pdf',
        'Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm',
        left=[
            ('7', 'VREF', 'input'),
            ('5', '~{SYNC}', 'input'),
            ('3', 'SCLK', 'input'),
            ('4', 'SDIN', 'input'),
        ],
        right=[('1', 'IOUT1', 'output'), ('8', 'RFB', 'passive')],
        top=[('6', 'VDD', 'power_in')],
        bottom=[('2', 'GND', 'power_in'), ('9', 'EP', 'passive')],
        keywords='mdac dac multiplying',
    ),
    symbol(
        'TPD4E05U06DQAR',
        'U',
        'TI 4-channel 5.5 V ESD clamp, 0.5 pF, USON-10 2.5 x 1 mm. Each I/O clamps '
        'to GND',
        'https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf',
        'Package_SON:USON-10_2.5x1.0mm_P0.5mm',
        left=[
            ('1', 'IO1', 'passive'),
            ('2', 'IO2', 'passive'),
            ('4', 'IO3', 'passive'),
            ('5', 'IO4', 'passive'),
        ],
        right=[
            ('10', 'NC', 'no_connect'),
            ('9', 'NC', 'no_connect'),
            ('7', 'NC', 'no_connect'),
            ('6', 'NC', 'no_connect'),
        ],
        bottom=[(['3', '8'], 'GND', 'passive')],
        keywords='esd tvs',
        tip_x=10.16,
    ),
    symbol(
        'SP3422-04UTG',
        'U',
        'Littelfuse 4-channel 5 V ESD clamp, 0.2 pF, +22/-10 kV IEC contact, 1 uA max '
        'leakage at 5 V, DFN-5 1.0 x 0.6 mm. Each I/O clamps to GND',
        'https://www.littelfuse.com/assetdocs/littelfuse-tvs-diode-array-sp3422-datasheet'
        '?assetguid=21918f04-36bb-469b-8a84-152f9e3b0285',
        'cryocooler:Littelfuse_DFN-5_1.0x0.6mm_P0.35mm',
        left=[
            ('1', 'IO1', 'passive'),
            ('3', 'IO2', 'passive'),
            ('4', 'IO3', 'passive'),
            ('5', 'IO4', 'passive'),
        ],
        bottom=[('2', 'GND', 'passive')],
        keywords='esd tvs',
        tip_x=10.16,
    ),
    symbol(
        'NUF6401MNT1G',
        'U',
        'onsemi 6-channel C-R-C EMI filter with ESD clamps: 100 ohm, 17 pF each side, '
        '5 V, +/-15 kV IEC contact, DFN12 3.0 x 1.35 mm. Channels 1-12, 2-11, 3-10, '
        '4-9, 5-8, 6-7',
        'https://www.onsemi.com/pdf/datasheet/nuf6401-d.pdf',
        'cryocooler:OnSemi_DFN-12-1EP_506AD',
        left=[(str(pin), f'CH{pin}', 'passive') for pin in range(1, 7)],
        right=[(str(13 - pin), f'CH{pin}', 'passive') for pin in range(1, 7)],
        bottom=[('13', 'GND', 'passive')],
        keywords='emi filter esd tvs',
        tip_x=10.16,
        half_height_min=7.62,
    ),
    # IMU board (imu/): pin numbers and functions from DS12814 Table 1
    symbol(
        'LSM6DSOXTR',
        'U',
        'ST iNEMO 6-axis IMU (3D accelerometer + 3D gyroscope), SPI/I2C/I3C, '
        'VDD 1.71-3.6 V, VDDIO 1.62-3.6 V, LGA-14L 2.5 x 3.0 x 0.83 mm',
        'https://www.st.com/resource/en/datasheet/lsm6dsox.pdf',
        'Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y',
        left=[
            ('12', '~{CS}', 'input'),
            ('13', 'SPC', 'input'),
            ('14', 'SDI', 'input'),
            ('1', 'SDO', 'tri_state'),
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
        keywords='imu accelerometer gyroscope',
        half_height_min=15.24,
    ),
    symbol(
        'APGB0607G22R23C',
        'D',
        'Kingbright green/red bi-colour LED, independent dies, 0.65 x 0.65 x 0.25 mm. '
        'Green VF 2.85 V typ / 3.3 V max, red 1.95 V / 2.3 V max at 5 mA; 10 mA max, VR 5 V',
        'https://www.kingbrightusa.com/images/catalog/SPEC/APGB0607G22R23C.pdf',
        'cryocooler:LED_Kingbright_APGB0607',
        left=[('1', 'GA', 'passive'), ('4', 'RA', 'passive')],
        right=[('2', 'GK', 'passive'), ('3', 'RK', 'passive')],
        keywords='led bicolor red green',
        tip_x=7.62,
    ),
    # OPA2991 in DSG: the TLV9062xDSG pinout (A 1-3, B 5-7, V- 4, V+ 8, pad 9)
    stock_copy(
        'Amplifier_Operational',
        'TLV9062xDSG',
        'OPA2991IDSG',
        {
            'Value': 'OPA2991IDSGR',
            'Footprint': 'cryocooler:TI_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm',
            'Datasheet': 'https://www.ti.com/lit/ds/symlink/opa2991.pdf',
            'Description': 'TI dual 40 V rail-to-rail input/output op amp, 4.5 MHz, 10 pA bias, '
            'WSON-8 2 x 2 mm, thermal pad to V-',
        },
    ),
    stock_copy(
        'Interface',
        'AD9833xRM',
        'AD9837BCPZ',
        {
            'Value': 'AD9837BCPZ',
            'Footprint': 'Package_CSP:LFCSP-WD-10-1EP_3x3mm_P0.5mm_EP1.64x2.38mm',
            'Datasheet': 'https://www.analog.com/media/en/technical-documentation/data-sheets/AD9837.pdf',
            'Description': 'Analog Devices programmable waveform generator, 28-bit, 16 MHz MCLK (B grade), '
            '2.3-5.5 V, AD9833 register set and pin numbers, LFCSP-WD-10 3 x 3 mm with exposed pad to ground',
        },
        extra_pins=[('9', '11', 'EP', 0, -12.7, 90)],
    ),
    symbol(
        'TPD1E05U06DPYR',
        'U',
        'TI 1-channel 5.5 V ESD clamp, 0.42 pF, DPY 0.6 x 1 mm',
        'https://www.ti.com/lit/ds/symlink/tpd1e05u06.pdf',
        'Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm',
        left=[('1', 'IO', 'passive')],
        bottom=[('2', 'GND', 'passive')],
        keywords='esd tvs',
        tip_x=7.62,
    ),
    from_stock(
        'Oscillator',
        'ECS-2520MV-xxx-xx',
        'ECS-2520MV',
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
