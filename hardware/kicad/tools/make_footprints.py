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


def rjsse5380():
    """Amphenol RJSSE-5380 SMT RJ45, 8P8C, shielded, no magnetics (drawing
    P-RJSSE-5380 rev E, component side). Origin midway between the two
    2.69 mm locating holes; +y points out of the jack mouth (board edge).
    Pins centred between the holes at 1.27 pitch (the drawing's 1.63 mm runs
    from the left hole to pin 8's pad edge, not its centre); 0.56 x 2.54 mm
    pads 14.31 mm behind the hole line; shield pads 6.22 x 3.18 mm, 3.00 mm
    behind it, outer edges 1.92 mm outside the holes.
    """
    hole_x = 6.35
    pad_y = -14.31 + 2.54 / 2
    pads = [
        smd_pad(str(number), round((4.5 - number) * 1.27, 3),
                round(pad_y, 3), 0.56, 2.54)
        for number in range(1, 9)
    ]
    shield_y = round(-3.00 - 3.18 / 2, 3)
    shield_x = round(-1.92 + 6.22 / 2 - hole_x, 3)
    pads += [
        smd_pad('SH', shield_x, shield_y, 6.22, 3.18),
        smd_pad('SH', -shield_x, shield_y, 6.22, 3.18),
        npth(-hole_x, 0, 2.69),
        npth(hole_x, 0, 2.69),
    ]
    # body: 16.51 wide, 15.75 deep, front face 4.05 mm in front of the holes;
    # the signal tails reach 14.31 mm back, so the courtyard covers them too
    front, back = 4.05, 4.05 - 15.75
    tails = -14.31
    outline = ''.join(
        line(*points, layer, width)
        for layer, width, grow, rear in (
            ('F.Fab', 0.1, 0.0, back),
            ('F.CrtYd', 0.05, 0.5, tails),
        )
        for points in (
            (-8.255 - grow, rear - grow, 8.255 + grow, rear - grow),
            (8.255 + grow, rear - grow, 8.255 + grow, front + grow),
            (8.255 + grow, front + grow, -8.255 - grow, front + grow),
            (-8.255 - grow, front + grow, -8.255 - grow, rear - grow),
        )
    )
    silk = ''.join(
        line(*points, 'F.SilkS', 0.12)
        for points in (
            (-8.4, -10.0, -8.4, front + 0.15),
            (8.4, -10.0, 8.4, front + 0.15),
        )
    )
    return (
        '(footprint "RJ45_Amphenol_RJSSE-5380_Horizontal"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Amphenol RJSSE-5380 SMT RJ45 8P8C, shielded, no magnetics; '
        'land pattern from drawing P-RJSSE-5380 rev E '
        '(https://www.amphenol-cs.com/modular-jacks-rjsse5380.html)")\n'
        + text('Reference', 'REF**', 0, back - 1.5, 'F.SilkS')
        + text('Value', 'RJSSE-5380', 0, front + 1.5, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + silk
        + ''.join(pads)
        + ')\n'
    )


def box(x1, y1, x2, y2, layer, width):
    """Closed rectangle from corner (x1, y1) to (x2, y2)."""
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    return ''.join(
        line(*corners[index], *corners[(index + 1) % 4], layer, width)
        for index in range(4)
    )


# ─── JST PH compatible 2.0 mm right-angle SMT headers ─────────────────────
# Signal pads 1.0 x 3.5 on 2.0 mm pitch, fitting nails 1.5 x 3.4 with their
# inner edge 1.6 past the outer pin centre, mating face at +y on the nail
# bottoms, pin 1 on the left.
PH_PITCH = 2.0
PH_PAD = (1.0, 3.5)
PH_PAD_Y = -2.85
PH_NAIL = (1.5, 3.4)
PH_BODY_DEPTH = 6.0


def jst_ph_smt(name, pins, nail_top, body_width, description):
    """nail_top: distance from the signal pad tops down to the nail tops."""
    pad_top = PH_PAD_Y - PH_PAD[1] / 2
    first_x = -PH_PITCH * (pins - 1) / 2
    pads = [
        smd_pad(str(pin + 1), round(first_x + pin * PH_PITCH, 3), PH_PAD_Y, *PH_PAD)
        for pin in range(pins)
    ]
    nail_x = round(-first_x + 1.6 + PH_NAIL[0] / 2, 3)
    nail_y = round(pad_top + nail_top + PH_NAIL[1] / 2, 3)
    pads += [smd_pad('MP', side * nail_x, nail_y, *PH_NAIL) for side in (-1, 1)]
    front = round(pad_top + nail_top + PH_NAIL[1], 3)
    back = round(front - PH_BODY_DEPTH, 3)
    half_w = body_width / 2
    court_x = round(max(half_w, nail_x + PH_NAIL[0] / 2) + 0.25, 3)
    court_top = round(pad_top - 0.25, 3)
    court_bottom = round(front + 0.25, 3)
    mark_x = round(first_x - PH_PAD[0] / 2 - 0.4, 3)
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        f'\t(descr "{description}")\n'
        + text('Reference', 'REF**', 0, round(court_top - 0.9, 3), 'F.SilkS')
        + text('Value', name, 0, round(court_bottom + 0.9, 3), 'F.Fab')
        + '\t(attr smd)\n'
        + box(-half_w, back, half_w, front, 'F.Fab', 0.1)
        # pin-1 mark on silk, left of pad 1
        + line(mark_x, PH_PAD_Y - 1.0, mark_x, PH_PAD_Y + 1.0, 'F.SilkS', 0.15)
        + box(-court_x, court_top, court_x, court_bottom, 'F.CrtYd', 0.05)
        + ''.join(pads)
        + ')\n'
    )


def adafruit_1769():
    """Adafruit 1769 (4UCON 17311): nails 5.6 below the pad tops, body 7.9."""
    return jst_ph_smt(
        'Adafruit_1769_JST-PH_1x02_P2.00mm_Horizontal_SMD',
        2,
        5.6,
        7.9,
        'Adafruit 1769 (4UCON 17311) JST PH compatible 2-pin, 2.0 mm pitch, '
        'right angle, SMT, 2 A; land pattern from '
        'https://cdn-shop.adafruit.com/datasheets/17311.pdf',
    )


def adafruit_4392():
    """Adafruit 4392 (Kaweei CW2001-04T-H01-BD-A): nail bottoms 9.2 below the
    pad tops (so tops at 5.8), body B = 12.0 for 4 circuits.
    """
    return jst_ph_smt(
        'Adafruit_4392_JST-PH_1x04_P2.00mm_Horizontal_SMD',
        4,
        9.2 - PH_NAIL[1],
        12.0,
        'Adafruit 4392 (Kaweei CW2001-04T-H01-BD-A) JST PH compatible 4-pin, '
        '2.0 mm pitch, right angle, SMT, 2 A; land pattern from '
        'https://cdn-shop.adafruit.com/product-files/4392/'
        '4392_C13927-001_CW2001-04T-H01-BD-A.PDF',
    )


FOOTPRINTS = {
    'L_Coilcraft_MSD7342': msd7342,
    'RJ45_Amphenol_RJSSE-5380_Horizontal': rjsse5380,
    'Adafruit_1769_JST-PH_1x02_P2.00mm_Horizontal_SMD': adafruit_1769,
    'Adafruit_4392_JST-PH_1x04_P2.00mm_Horizontal_SMD': adafruit_4392,
}


def main():
    for name, build in FOOTPRINTS.items():
        (PRETTY / f'{name}.kicad_mod').write_text(build())
        print(f'wrote {name}')


if __name__ == '__main__':
    main()
