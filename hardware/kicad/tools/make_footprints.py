"""Writes the vendor footprints that the stock KiCad libraries lack into
lib/cryocooler.pretty. Every dimension comes from the maker's drawing named in
the footprint's description.

Usage: python3 tools/make_footprints.py
"""

from pathlib import Path

PRETTY = Path(__file__).resolve().parents[1] / 'lib' / 'cryocooler.pretty'


def text(kind, value, x, y, layer, hide=False):
    hidden = '\n\t\t(hide yes)' if hide else ''
    return f'''\t(property "{kind}" "{value}"
\t\t(at {x} {y} 0)
\t\t(layer "{layer}"){hidden}
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
'''


def line(x1, y1, x2, y2, layer, width):
    return f'''\t(fp_line
\t\t(start {x1} {y1})
\t\t(end {x2} {y2})
\t\t(stroke
\t\t\t(width {width})
\t\t\t(type solid)
\t\t)
\t\t(layer "{layer}")
\t)
'''


def rect(half_x, half_y, layer, width):
    """Closed rectangle centred on the origin, drawn as four lines."""
    corners = [
        (-half_x, -half_y),
        (half_x, -half_y),
        (half_x, half_y),
        (-half_x, half_y),
    ]
    return ''.join(
        line(*corners[index], *corners[(index + 1) % 4], layer, width)
        for index in range(4)
    )


def circle(x, y, radius, layer, width, fill=False):
    return f'''\t(fp_circle
\t\t(center {x} {y})
\t\t(end {x + radius} {y})
\t\t(stroke
\t\t\t(width {width})
\t\t\t(type solid)
\t\t)
\t\t(fill {'yes' if fill else 'no'})
\t\t(layer "{layer}")
\t)
'''


def smd_pad(number, x, y, width, height):
    return f'''\t(pad "{number}" smd rect
\t\t(at {x} {y})
\t\t(size {width} {height})
\t\t(layers "F.Cu" "F.Paste" "F.Mask")
\t)
'''


def npth(x, y, drill):
    return f'''\t(pad "" np_thru_hole circle
\t\t(at {x} {y})
\t\t(size {drill} {drill})
\t\t(drill {drill})
\t\t(layers "*.Cu" "*.Mask")
\t)
'''


def footprint(name, description, body, pads, extra=''):
    """body = (half_x, half_y) of the part outline."""
    half_x, half_y = body
    courtyard = (round(half_x + 0.5, 2), round(half_y + 0.5, 2))
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        f'\t(descr "{description}")\n'
        + text('Reference', 'REF**', 0, -half_y - 1.2, 'F.SilkS')
        + text('Value', name, 0, half_y + 1.2, 'F.Fab')
        + '\t(attr smd)\n'
        + rect(half_x, half_y, 'F.Fab', 0.1)
        + rect(half_x + 0.3, half_y + 0.3, 'F.SilkS', 0.12)
        + rect(*courtyard, 'F.CrtYd', 0.05)
        + extra
        + ''.join(pads)
        + ')\n'
    )


def msd7342():
    """Coilcraft MSD7342 coupled inductor, 7.5 x 7.5 mm. Land pattern
    (Document 621-1): 1.10 x 2.1 mm pads, 2.8 mm across a row, 3.3 mm
    between rows; top row 2 / 1, bottom row 3 / 4 (top view, dot = pin 1).
    Windings: 1 (dot) - 3 and 2 (dot) - 4.
    """
    pad_x, pad_y = 0.85, 2.7
    pads = [
        smd_pad('2', -pad_x, -pad_y, 1.1, 2.1),
        smd_pad('1', pad_x, -pad_y, 1.1, 2.1),
        smd_pad('3', -pad_x, pad_y, 1.1, 2.1),
        smd_pad('4', pad_x, pad_y, 1.1, 2.1),
    ]
    return footprint(
        'L_Coilcraft_MSD7342',
        'Coilcraft MSD7342 1:1 coupled inductor, 7.5 x 7.5 x 4.6 mm; land '
        'pattern from https://www.coilcraft.com/getmedia/msd7342.pdf '
        '(Document 621-1)',
        (3.75, 3.75),
        pads,
        circle(2.6, -2.6, 0.25, 'F.SilkS', 0.12, fill=True),
    )


FOOTPRINTS = {
    'L_Coilcraft_MSD7342': msd7342,
}


def main():
    for name, build in FOOTPRINTS.items():
        (PRETTY / f'{name}.kicad_mod').write_text(build())
        print(f'wrote {name}')


if __name__ == '__main__':
    main()
