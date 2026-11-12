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


def footprint(name, description, body, pads, extra='', courtyard=None):
    """body = (half_x, half_y) of the part outline; courtyard defaults to the
    outline plus 0.5 mm, so pass it when pads reach past that.
    """
    half_x, half_y = body
    courtyard = courtyard or (round(half_x + 0.5, 2), round(half_y + 0.5, 2))
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


def srp6050ca():
    """Bourns SRP6050CA, 6.6 x 6.4 x 4.8 mm. Recommended layout (datasheet p.1):
    5.6 mm pad width, 5.6 mm overall, 2.5 mm gap, so 1.55 mm pads. Turned 90
    degrees from the drawing so the terminals sit on the x axis.
    """
    pads = [smd_pad('1', -2.025, 0, 1.55, 5.6), smd_pad('2', 2.025, 0, 1.55, 5.6)]
    return footprint(
        'L_Bourns_SRP6050CA',
        'Bourns SRP6050CA shielded power inductor, 6.6 x 6.4 x 4.8 mm; land pattern '
        'from https://www.bourns.com/docs/product-datasheets/srp6050ca.pdf',
        (3.2, 3.3),
        pads,
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


MICRO_LOCK_NAME = 'Molex_Micro-Lock_Plus_505448-0891_2x04_P1.25mm_Horizontal'


def molex_505448_0891():
    """Molex Micro-Lock Plus 505448-0891: 1.25 mm, 2x4, right angle, SMT, positive
    lock (drawing 5054480003-SD rev C1, recommended layout, component side).
    Origin at the pad pattern centre; +y points out of the mating face.
    Pads 0.8 x 2.0, rows 7.4 apart: odd pins on the back row, even pins on the
    mating-side row, pin 1 on the right seen from above (mating face down).
    Nails 1.0 x 4.85, 8.15 apart, 0.7 in from the mating-side pad edge.
    Body 9.6 wide, 8.43 deep from a face 0.25 past the even pads; tails reach
    0.42 further back; 8.95 high.
    """
    pads = []
    for column in range(4):
        x = round(1.875 - column * 1.25, 3)
        pads.append(smd_pad(str(2 * column + 1), x, -3.7, 0.8, 2.0))
        pads.append(smd_pad(str(2 * column + 2), x, 3.7, 0.8, 2.0))
    pads += [smd_pad('MP', side * 4.075, 1.575, 1.0, 4.85) for side in (-1, 1)]
    face, back = 4.95, round(4.95 - 8.43, 3)
    return (
        f'(footprint "{MICRO_LOCK_NAME}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Molex Micro-Lock Plus 505448-0891, 1.25 mm pitch, dual row 2x4, '
        'right angle, SMT, positive lock; land pattern from drawing 5054480003-SD '
        '(https://www.molex.com/en-us/products/part-detail/5054480891)")\n'
        + text('Reference', 'REF**', 0, -5.9, 'F.SilkS')
        + text('Value', '505448-0891', 0, 6.1, 'F.Fab')
        + '\t(attr smd)\n'
        + box(-4.8, back, 4.8, face, 'F.Fab', 0.1)
        + line(4.92, -3.3, 4.92, face - 0.4, 'F.SilkS', 0.12)
        + line(-4.92, -3.3, -4.92, face - 0.4, 'F.SilkS', 0.12)
        # pin-1 dot behind the back row, beside pad 1
        + circle(2.75, -4.45, 0.15, 'F.SilkS', 0.1, fill=True)
        + box(-5.05, -4.95, 5.05, face + 0.25, 'F.CrtYd', 0.05)
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


def fan_header_4p():
    """Right-angle 4-pin (3+1) PC fan header, 2.54 mm pitch, through hole. No
    maker drawing exists: dimensions come from fan_header_90deg.step (GrabCAD),
    so check them against the real part. Origin on pin 1; +y points out of the
    mating side. Pins 1-3 share the key tab, pin 4 (PWM) is the separate one.
    """
    pads = [
        f'''\t(pad "{number}" thru_hole {'roundrect' if number == 1 else 'oval'}
\t\t(at {round((number - 1) * 2.54, 2)} 0)
\t\t(size 1.8 1.8)
\t\t(drill 1.1)
\t\t(layers "*.Cu" "*.Mask")
{'''\t\t(roundrect_rratio 0.25)
''' if number == 1 else ''}\t)
'''
        for number in range(1, 5)
    ]
    body_left, body_right = -1.594, 9.214
    body_back, body_front = 1.804, 7.092
    tab_end = 13.346
    outline = (
        box(body_left, body_back, body_right, body_front, 'F.Fab', 0.1)
        + box(-0.02, body_front, 7.6, tab_end, 'F.Fab', 0.1)
        + box(body_left - 0.12, body_back - 0.12, body_right + 0.12,
              body_front + 0.12, 'F.SilkS', 0.12)
        + box(body_left - 0.25, -1.4, body_right + 0.25, tab_end + 0.25,
              'F.CrtYd', 0.05)
        # pin 1 mark, behind the tail
        + line(-1.3, -1.25, -0.7, -1.25, 'F.SilkS', 0.12)
    )
    return (
        '(footprint "FanHeader_4P_P2.54mm_Horizontal"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Right-angle 3+1 pin PC fan header, 2.54 mm pitch (MODDIY '
        'FC-3+1P-MA); dimensions from a CAD model, no maker drawing")\n'
        + text('Reference', 'REF**', 3.81, -2.4, 'F.SilkS')
        + text('Value', 'FanHeader_4P', 3.81, 4.4, 'F.Fab')
        + '\t(attr through_hole)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def wurth_61900311021():
    """Wurth WR-WTB 61900311021, 3-pin right-angle locking header (datasheet
    rev 002.000). Origin on pin 1; +y points out of the mating side. 1.0 mm
    holes at 2.54 mm; 7.62 wide, 3.3 deep, 5.8 high; plate ends 11.5 mm in
    front of the body back. The drawing gives no tail-to-body distance: 1.69 mm
    is scaled from it and agrees with the 12.47 mm tail-to-tip figure.
    """
    pads = [
        f'''\t(pad "{number}" thru_hole {'roundrect' if number == 1 else 'oval'}
\t\t(at {round((number - 1) * 2.54, 2)} 0)
\t\t(size 1.7 1.7)
\t\t(drill 1.0)
\t\t(layers "*.Cu" "*.Mask")
{'''\t\t(roundrect_rratio 0.25)
''' if number == 1 else ''}\t)
'''
        for number in range(1, 4)
    ]
    body_left, body_right = -1.27, 6.35
    body_back, body_front = 1.69, 4.99
    plate_end = 13.19
    outline = (
        box(body_left, body_back, body_right, body_front, 'F.Fab', 0.1)
        + box(-0.3, body_front, 5.38, plate_end, 'F.Fab', 0.1)
        + box(body_left - 0.12, body_back - 0.12, body_right + 0.12,
              body_front + 0.12, 'F.SilkS', 0.12)
        + box(body_left - 0.25, -1.3, body_right + 0.25, plate_end + 0.25,
              'F.CrtYd', 0.05)
        + line(-1.2, -1.2, -0.6, -1.2, 'F.SilkS', 0.12)
    )
    return (
        '(footprint "Wurth_WR-WTB_61900311021_1x03_P2.54mm_Horizontal"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Wurth WR-WTB 61900311021 right-angle locking header, 3 pins, '
        '2.54 mm (datasheet rev 002.000)")\n'
        + text('Reference', 'REF**', 2.54, -2.3, 'F.SilkS')
        + text('Value', '61900311021', 2.54, 3.3, 'F.Fab')
        + '\t(attr through_hole)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def sullins_swr25x_s02_rb():
    """Sullins SWR25X-NRTC-S02-RB-BA, 2-pin right-angle wafer (Type 1). Origin
    on pin 1; +y points out of the mating side. Catalog p.136-137: 1.00 mm holes
    at 2.54 mm; 5.12 wide (B), 3.2 deep, 5.8 high; tail 1.9 behind the body;
    plate ends 11.4 in front of the body back. The drawing shows 6-20 positions,
    so the plate width here is an estimate.
    """
    pads = [
        f'''\t(pad "{number}" thru_hole {'roundrect' if number == 1 else 'oval'}
\t\t(at {round((number - 1) * 2.54, 2)} 0)
\t\t(size 1.7 1.7)
\t\t(drill 1.0)
\t\t(layers "*.Cu" "*.Mask")
{'''\t\t(roundrect_rratio 0.25)
''' if number == 1 else ''}\t)
'''
        for number in range(1, 3)
    ]
    body_left, body_right = -1.29, 3.83
    body_back, body_front = 1.9, 5.1
    plate_end = 13.3
    outline = (
        box(body_left, body_back, body_right, body_front, 'F.Fab', 0.1)
        + box(-0.3, body_front, 2.84, plate_end, 'F.Fab', 0.1)
        + box(body_left - 0.12, body_back - 0.12, body_right + 0.12,
              body_front + 0.12, 'F.SilkS', 0.12)
        + box(body_left - 0.25, -1.3, body_right + 0.25, plate_end + 0.25,
              'F.CrtYd', 0.05)
        + line(-1.2, -1.2, -0.6, -1.2, 'F.SilkS', 0.12)
    )
    return (
        '(footprint "Sullins_SWR25X-NRTC-S02-RB-BA_1x02_P2.54mm_Horizontal"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Sullins SWR25X-NRTC-S02-RB-BA right-angle wafer, 2 pins, 2.54 mm '
        '(catalog p.136-137)")\n'
        + text('Reference', 'REF**', 1.27, -2.3, 'F.SilkS')
        + text('Value', 'SWR25X-S02', 1.27, 3.5, 'F.Fab')
        + '\t(attr through_hole)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def tensility_54_00164():
    """Tensility 54-00164, 5.5 x 2.1 mm right-angle SMT DC jack (drawing rev A,
    07/03/2019). Origin at the mouth on the jack axis; +y points out of the
    mouth. Pads 2 x 2 at 13 across; pegs 1.6 and 1.8. Pads: 1 = A (centre pin,
    both pads), 2 = B (sleeve contact), 3 = C (normally closed switch).
    """
    pads = [smd_pad(number, x_mm, y_mm, 2, 2) for number, x_mm, y_mm in (
        (1, -5.5, -5.0), (1, -5.5, -11.2), (2, 5.5, -5.0), (3, 5.5, -11.2))]
    pads += [npth(0, -5.0, 1.6), npth(0, -9.5, 1.8)]
    outline = (
        box(-4.5, -14.7, 4.5, 0, 'F.Fab', 0.1)
        + line(-3.9, -0.5, -3.9, -3.7, 'F.SilkS', 0.12)
        + line(3.9, -0.5, 3.9, -3.7, 'F.SilkS', 0.12)
        + line(-3.9, -6.3, -3.9, -9.9, 'F.SilkS', 0.12)
        + line(3.9, -6.3, 3.9, -9.9, 'F.SilkS', 0.12)
        + line(-3.9, -14.8, 3.9, -14.8, 'F.SilkS', 0.12)
        + box(-6.75, -15.0, 6.75, 0.25, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "Tensility_54-00164_5.5x2.1mm_Horizontal_SMD"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Tensility 54-00164 DC jack 5.5 x 2.1 mm, right angle, SMT '
        '(drawing rev A)")\n'
        + text('Reference', 'REF**', 0, -16.2, 'F.SilkS')
        + text('Value', '54-00164', 0, -7.0, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def same_sky_mj_3523():
    """Same Sky MJ-3523-SMT-TR, 3.5 mm mono right-angle SMT jack (datasheet rev
    1.06). Origin at the nose tip on the jack axis; +y points out of the nose.
    Nose 2.5, body 14.5, pads as the recommended layout. Pads: 1 = sleeve,
    2 = tip, 10 = tip switch.
    """
    shoulder = -2.5
    pads = [
        smd_pad(1, 3.7, round(shoulder - 2.4, 2), 2.8, 2.2),
        smd_pad(2, 3.7, round(shoulder - 11.8, 2), 2.8, 2.8),
        smd_pad(10, -0.75, round(shoulder - 14.5 - 1.3, 2), 2.8, 2.6),
        npth(0, shoulder - 3.5, 1.7),
        npth(0, shoulder - 10.5, 1.7),
    ]
    # stepped to follow the pads, so parts can sit beside the rear pad
    corners = ((-3.25, 0.25), (3.25, 0.25), (3.25, -3.55), (5.35, -3.55), (5.35, -16.0),
               (3.25, -16.0), (3.25, -17.25), (0.9, -17.25), (0.9, -19.85), (-2.4, -19.85),
               (-2.4, -17.25), (-3.25, -17.25), (-3.25, 0.25))
    courtyard = ''.join(line(*start, *end, 'F.CrtYd', 0.05)
                        for start, end in zip(corners, corners[1:]))
    outline = (
        box(-3.0, -17.0, 3.0, shoulder, 'F.Fab', 0.1)
        + box(-2.5, shoulder, 2.5, 0, 'F.Fab', 0.1)
        + line(-3.1, -16.8, -3.1, -13.2, 'F.SilkS', 0.12)
        + line(-3.1, shoulder, -2.6, shoulder, 'F.SilkS', 0.12)
        + line(-2.6, shoulder, -2.6, -0.5, 'F.SilkS', 0.12)
        + line(2.6, shoulder, 2.6, -0.5, 'F.SilkS', 0.12)
        + line(2.6, shoulder, 3.1, shoulder, 'F.SilkS', 0.12)
        + line(3.1, -6.3, 3.1, -12.6, 'F.SilkS', 0.12)
        + courtyard
    )
    return (
        '(footprint "SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Same Sky MJ-3523-SMT-TR 3.5 mm mono jack, right angle, SMT '
        '(datasheet rev 1.06)")\n'
        + text('Reference', 'REF**', -4.5, -9.0, 'F.SilkS')
        + text('Value', 'MJ-3523', 0, -9.0, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def polygon(points, layer, width):
    """Closed outline through the given (x, y) points."""
    return ''.join(
        line(*points[index], *points[(index + 1) % len(points)], layer, width)
        for index in range(len(points))
    )


def te_2305908(positions):
    """TE 2305908-x right-angle SMT terminal block header, 5.00 mm pitch (customer
    drawing C-2305908 rev A1). Origin on pin 1's pad; +y points out of the mating
    side. Pads 2.00 x 5.50 with their inner edge 9.0 behind the body front; body
    9.8 deep, 8.9 high; L2 = 5(n-1) + 7.0 wide, 3.5 from its edge to pin 1; tails
    end 4.2 behind the body. Solder pads only: no locating pegs.
    """
    name = f'TE_2305908-{positions}_1x{positions:02d}_P5.00mm_Horizontal_SMD'
    span = 5.0 * (positions - 1)
    left, right = -3.5, span + 3.5
    body_back, body_front = 1.95, 11.75
    silk_back = round(body_back + 1.0, 2)  # clear of the pads
    pads = [smd_pad(number + 1, round(number * 5.0, 2), 0, 2.0, 5.5)
            for number in range(positions)]
    silk = ''.join(
        line(round(number * 5.0 + 1.3, 2), silk_back,
             round((number + 1) * 5.0 - 1.3, 2), silk_back, 'F.SilkS', 0.12)
        for number in range(positions - 1)
    )
    outline = (
        box(left, body_back, right, body_front, 'F.Fab', 0.1)
        + silk
        + line(left, silk_back, -1.3, silk_back, 'F.SilkS', 0.12)
        + line(span + 1.3, silk_back, right, silk_back, 'F.SilkS', 0.12)
        + line(left, silk_back, left, body_front, 'F.SilkS', 0.12)
        + line(right, silk_back, right, body_front, 'F.SilkS', 0.12)
        + polygon(((left - 0.25, 1.7), (-1.25, 1.7), (-1.25, -3.0), (span + 1.25, -3.0),
                   (span + 1.25, 1.7), (right + 0.25, 1.7), (right + 0.25, body_front + 0.25),
                   (left - 0.25, body_front + 0.25)), 'F.CrtYd', 0.05)
        + circle(-1.9, -2.4, 0.2, 'F.SilkS', 0.12, fill=True)
    )
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        f'\t(descr "TE Connectivity 2305908-{positions} right-angle SMT terminal block '
        'header, 5.00 mm (drawing C-2305908 rev A1)")\n'
        + text('Reference', 'REF**', span / 2, -4.0, 'F.SilkS')
        + text('Value', f'2305908-{positions}', span / 2, 7.0, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def te_643228_1():
    """TE 643228-1 right-angle through-hole Universal MATE-N-LOK socket header, 3
    position, 6.35 mm pitch (customer drawing C-643228 rev D3). Origin on pin 1; -y
    points out of the mating face, as in the drawing's plan view, so seen from the
    front with the tails down the cavities read 3, 2, 1 left to right. Mating face
    15.37 ahead of the pins (12.83 to the Ø3.81 holes + 2.54); ears 37.97 wide, 1.90
    behind the pins; wings 25.4 wide, 6.60 deep, carried above the board.
    Silk stops short of the face, because the part is meant to overhang the edge.
    """
    name = 'TE_643228-1_1x03_P6.35mm_Horizontal'
    centre = 6.35
    face, wing_back, ear_front, body_back, ear_back = -15.37, -8.77, -6.1, -0.64, 1.9
    silk_front = -11.8
    drill = 1.52
    pads = [
        f'''\t(pad "{number}" thru_hole {'roundrect' if number == 1 else 'circle'}
\t\t(at {round((number - 1) * centre, 2)} 0)
\t\t(size 3 3)
\t\t(drill {drill})
\t\t(layers "*.Cu" "*.Mask")
{'''\t\t(roundrect_rratio 0.25)
''' if number == 1 else ''}\t)
'''
        for number in range(1, 4)
    ]
    holes = npth(-7.365, -2.54, 3.81) + npth(20.065, -2.54, 3.81)

    def side(sign):
        """Fab and silk outline of one side of the part, from the centre line."""
        point = lambda offset, y_pos: (round(centre + sign * offset, 3), y_pos)
        fab = [point(10.16, face), point(12.7, face), point(12.7, wing_back),
               point(10.16, wing_back), point(10.16, ear_front), point(18.985, ear_front),
               point(18.985, ear_back), point(9.14, ear_back), point(9.14, body_back)]
        silk = [point(12.7, silk_front), *fab[2:8]]
        return (
            ''.join(line(*start, *end, 'F.Fab', 0.1) for start, end in zip(fab, fab[1:]))
            + ''.join(line(*start, *end, 'F.SilkS', 0.12) for start, end in zip(silk, silk[1:]))
        )

    courtyard = []
    for sign, order in ((-1, 1), (1, -1)):
        half = [(12.95, -15.62), (12.95, -8.52), (10.41, -8.52), (10.41, -6.35),
                (19.235, -6.35), (19.235, 2.05)]
        courtyard += [(round(centre + sign * offset, 3), y_pos)
                      for offset, y_pos in half[::order]]
    outline = (
        side(-1)
        + side(1)
        + line(-3.81, face, 16.51, face, 'F.Fab', 0.1)
        + line(-2.79, body_back, 15.49, body_back, 'F.Fab', 0.1)
        + polygon(courtyard, 'F.CrtYd', 0.05)
        + circle(-1.7, 1.6, 0.2, 'F.SilkS', 0.12, fill=True)
    )
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "TE Connectivity 643228-1 right-angle through-hole Universal MATE-N-LOK '
        'socket header, 3 position, 6.35 mm (drawing C-643228 rev D3)")\n'
        + text('Reference', 'REF**', centre, -4.0, 'F.SilkS')
        + text('Value', '643228-1', centre, -10.0, 'F.Fab')
        + '\t(attr through_hole)\n'
        + outline
        + ''.join(pads)
        + holes
        + ')\n'
    )


def te_2305908_2():
    return te_2305908(2)


def te_2305908_3():
    return te_2305908(3)


def panasonic_evq_p2f():
    """Panasonic EVQP2 with ground terminal, 4.7 x 3.5 mm (datasheet sw_lt_eng_4735s p.4,
    land pattern for reference): 1.0 x 1.45 mm pads, 2.7 mm across a row with a 0.7 mm gap,
    6.6 mm overall with a 3.7 mm gap between rows. Contacts 1-3 and 2-4 are common, so the
    left column is pin 1 and the right column pin 2. GND land 0.65 x 1.4 mm, 1.7 to 2.35 mm
    left of centre. It is numbered 2, so it only suits parts with pin 2 on GND.
    """
    pad_x, pad_y = 0.85, 2.575
    pads = [
        smd_pad('1', -pad_x, -pad_y, 1.0, 1.45),
        smd_pad('2', pad_x, -pad_y, 1.0, 1.45),
        smd_pad('1', -pad_x, pad_y, 1.0, 1.45),
        smd_pad('2', pad_x, pad_y, 1.0, 1.45),
        smd_pad('2', -2.025, 0, 0.65, 1.4),
    ]
    outline = (
        box(-1.75, -2.35, 1.75, 2.35, 'F.Fab', 0.1)
        + line(1.85, -2.45, 1.85, 2.45, 'F.SilkS', 0.12)
        + line(-1.85, -2.45, -1.85, -0.9, 'F.SilkS', 0.12)
        + line(-1.85, 0.9, -1.85, 2.45, 'F.SilkS', 0.12)
        + box(-2.6, -3.55, 2.6, 3.55, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "SW_Panasonic_EVQ-P2F"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Panasonic EVQP2 tactile switch with ground terminal, 4.7 x 3.5 mm; land '
        'pattern from datasheet sw_lt_eng_4735s p.4")\n'
        '\t(tags "Switch Tactile")\n'
        + text('Reference', 'REF**', 0, -4.2, 'F.SilkS')
        + text('Value', 'EVQ-P2F02K', 0, 4.2, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def panasonic_evp_aa():
    """Panasonic EVPAA without ground terminal, 3.5 x 2.9 mm, J-bent leads (catalog
    ANCTB18E 201612, No. 1, PWB land pattern for reference): 1.15 x 0.4 mm pads,
    4.5 mm overall with a 2.2 mm gap, rows 2.5 mm overall. Contacts 1-1' (top row)
    and 2-2' (bottom row) are common, so each row is one pin.
    """
    pad_x, pad_y = 1.675, 1.05
    pads = [
        smd_pad('1', -pad_x, -pad_y, 1.15, 0.4),
        smd_pad('1', pad_x, -pad_y, 1.15, 0.4),
        smd_pad('2', -pad_x, pad_y, 1.15, 0.4),
        smd_pad('2', pad_x, pad_y, 1.15, 0.4),
    ]
    outline = (
        box(-1.75, -1.45, 1.75, 1.45, 'F.Fab', 0.1)
        + circle(0, 0, 0.9, 'F.Fab', 0.1)
        + line(-0.95, -1.55, 0.95, -1.55, 'F.SilkS', 0.12)
        + line(-0.95, 1.55, 0.95, 1.55, 'F.SilkS', 0.12)
        + box(-2.5, -1.75, 2.5, 1.75, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "SW_Panasonic_EVP-AA"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Panasonic EVPAA tactile switch, 3.5 x 2.9 mm, J-bent leads, no ground '
        'terminal; land pattern from catalog ANCTB18E")\n'
        '\t(tags "Switch Tactile")\n'
        + text('Reference', 'REF**', 0, -2.4, 'F.SilkS')
        + text('Value', 'EVP-AA802Q', 0, 2.4, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def custom_pad(number, x, y, points, layers='"F.Cu" "F.Paste" "F.Mask"'):
    """SMD pad of any polygon shape; points are relative to (x, y), and the
    0.1 mm anchor square must sit inside the polygon.
    """
    pts = ' '.join(f'(xy {round(px, 4)} {round(py, 4)})' for px, py in points)
    return f"""\t(pad "{number}" smd custom
\t\t(at {x} {y})
\t\t(size 0.1 0.1)
\t\t(layers {layers})
\t\t(options
\t\t\t(clearance outline)
\t\t\t(anchor rect)
\t\t)
\t\t(primitives
\t\t\t(gr_poly
\t\t\t\t(pts {pts})
\t\t\t\t(width 0)
\t\t\t\t(fill yes)
\t\t\t)
\t\t)
\t)
"""


def nexperia_sot1226_3():
    """Nexperia X2SON5 (SOT1226-3), 0.8 x 0.8 x 0.32 mm (package information,
    27 August 2020, reflow footprint sot1226-3_fr): 0.32 x 0.26 mm corner lands at
    (+/-0.32, +/-0.25) and a 0.28 mm square GND land turned 45 degrees in the
    centre. The corner lands' inner corners are cut on a 45 degree line 0.16 mm
    from the GND land. Top view as datasheet Fig. 5: 1 top left, 2 bottom left,
    4 bottom right, 5 top right, 3 centre; the terminals (and lands) run out
    past the left and right body edges. sot1226-3_fr is drawn turned 90 degrees
    from Fig. 5, so its lands are transposed here.

    The GND land can't be escaped at 0.15 mm clearance with a 0.45 mm via, so a
    0.15 mm copper bridge (a second pad 3, copper only) joins it to pad 1, which
    is n.c. inside the part and tied to GND in the schematic.
    """
    half_diagonal = round(0.28 / 2 ** 0.5, 4)
    chamfer = round(half_diagonal + 0.16 * 2 ** 0.5, 4)  # |x| + |y| of the cut
    pads = []
    for number, sign_x, sign_y in (('1', -1, -1), ('5', 1, -1), ('2', -1, 1), ('4', 1, 1)):
        corner = [  # (|x|, |y|) of the land outline
            (chamfer - 0.12, 0.12),
            (0.48, 0.12),
            (0.48, 0.38),
            (0.16, 0.38),
            (0.16, chamfer - 0.16),
        ]
        pads.append(custom_pad(
            number, sign_x * 0.32, sign_y * 0.25,
            [(sign_x * px - sign_x * 0.32, sign_y * py - sign_y * 0.25) for px, py in corner],
        ))
    pads.append(custom_pad(
        '3', 0, 0,
        [(0, -half_diagonal), (half_diagonal, 0), (0, half_diagonal), (-half_diagonal, 0)],
    ))
    # bridge from the GND land to pad 1, 0.15 mm wide, copper only
    end_x, end_y = -0.32, -0.25
    length = (end_x ** 2 + end_y ** 2) ** 0.5
    normal_x, normal_y = -end_y / length * 0.075, end_x / length * 0.075
    mid_x, mid_y = end_x / 2, end_y / 2
    stripe = [
        (normal_x, normal_y), (end_x + normal_x, end_y + normal_y),
        (end_x - normal_x, end_y - normal_y), (-normal_x, -normal_y),
    ]
    pads.append(custom_pad(
        '3', mid_x, mid_y, [(px - mid_x, py - mid_y) for px, py in stripe], '"F.Cu"',
    ))
    outline = (
        box(-0.4, -0.4, 0.4, 0.4, 'F.Fab', 0.05)
        + line(-0.62, -0.2, -0.62, 0.45, 'F.SilkS', 0.08)
        + line(0.62, -0.45, 0.62, 0.45, 'F.SilkS', 0.08)
        + circle(-0.6, -0.55, 0.07, 'F.SilkS', 0.05, fill=True)
        + box(-0.75, -0.7, 0.75, 0.6, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "Nexperia_X2SON-5_SOT1226-3_0.8x0.8mm_P0.5mm"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Nexperia X2SON5 SOT1226-3 0.8 x 0.8 mm, 0.5 mm pitch; land pattern from '
        'https://assets.nexperia.com/documents/package-information/SOT1226-3.pdf, with a '
        'copper bridge from the GND land (3) to pad 1")\n'
        '\t(tags "X2SON5 SOT1226")\n'
        + text('Reference', 'REF**', 0, -1.2, 'F.SilkS')
        + text('Value', '74LV1T34GX', 0, 1.2, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def nexperia_sot886():
    """Nexperia XSON6 (SOT886), 1.0 x 1.45 x 0.5 mm, 0.5 mm pitch (SOT886 package
    information, 1 June 2022, reflow footprint sot886_fr): 0.40 x 0.30 mm lands on
    0.60 mm column pitch. Top view: pins 1-3 down the left column, 4-6 up the right (6 beside 1). KiCad's
    1 x 1.45 mm USON-6 STEP has the same body and pin 1 corner.
    """
    pads = []
    for index in range(3):
        row = round(-0.5 + index * 0.5, 2)
        pads.append(smd_pad(str(index + 1), -0.3, row, 0.4, 0.3))
        pads.append(smd_pad(str(6 - index), 0.3, row, 0.4, 0.3))
    outline = (
        box(-0.5, -0.725, 0.5, 0.725, 'F.Fab', 0.05)
        + line(-0.25, -0.9, 0.6, -0.9, 'F.SilkS', 0.08)
        + line(-0.6, 0.9, 0.6, 0.9, 'F.SilkS', 0.08)
        + circle(-0.7, -0.8, 0.07, 'F.SilkS', 0.05, fill=True)
        + box(-0.85, -1.0, 0.75, 1.0, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "Nexperia_XSON-6_SOT886_1.0x1.45mm_P0.5mm"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Nexperia XSON6 SOT886 1.0 x 1.45 mm, 0.5 mm pitch; land pattern from '
        'https://assets.nexperia.com/documents/package-information/SOT886.pdf")\n'
        '\t(tags "XSON6 SOT886")\n'
        + text('Reference', 'REF**', 0, -1.5, 'F.SilkS')
        + text('Value', '74AHCT1G125GM', 0, 1.5, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + '''\t(model "${KICAD10_3DMODEL_DIR}/Package_SON.3dshapes/USON-6_1x1.45mm_P0.5mm.step"
\t\t(offset
\t\t\t(xyz 0 0 0)
\t\t)
\t\t(scale
\t\t\t(xyz 1 1 1)
\t\t)
\t\t(rotate
\t\t\t(xyz 0 0 0)
\t\t)
\t)
'''
        + ')\n'
    )


def littelfuse_dfn5():
    """Littelfuse SP3422 DFN-5, 1.0 x 0.6 mm (SP3422 rev GD, recommended soldering
    pad layout; same as Littelfuse's DFN_04UTG_LTF): 0.34 x 0.175 mm pads, 0.35 mm
    pitch, rows 0.515 mm apart. Pins 1-3 top to bottom on the left (2 = GND), 5 and 4
    on the right, offset half a pitch. Pin 1 dot on the silk.
    """
    pads = [
        smd_pad('1', -0.2575, -0.35, 0.34, 0.175),
        smd_pad('2', -0.2575, 0, 0.34, 0.175),
        smd_pad('3', -0.2575, 0.35, 0.34, 0.175),
        smd_pad('4', 0.2575, 0.175, 0.34, 0.175),
        smd_pad('5', 0.2575, -0.175, 0.34, 0.175),
    ]
    outline = (
        box(-0.3, -0.5, 0.3, 0.5, 'F.Fab', 0.05)
        + line(-0.15, -0.65, 0.5, -0.65, 'F.SilkS', 0.08)
        + line(-0.5, 0.65, 0.5, 0.65, 'F.SilkS', 0.08)
        + circle(-0.6, -0.6, 0.07, 'F.SilkS', 0.05, fill=True)
        + box(-0.75, -0.75, 0.65, 0.75, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "Littelfuse_DFN-5_1.0x0.6mm_P0.35mm"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Littelfuse DFN-5 1.0 x 0.6 mm, 0.35 mm pitch (SP3422-04UTG); land pattern from '
        'https://www.littelfuse.com/assetdocs/littelfuse-tvs-diode-array-sp3422-datasheet")\n'
        '\t(tags "ESD TVS DFN")\n'
        + text('Reference', 'REF**', 0, -1.2, 'F.SilkS')
        + text('Value', 'SP3422-04UTG', 0, 1.2, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def ti_dsg0008a():
    """TI DSG0008A WSON-8, 2 x 2 x 0.8 mm, 0.5 mm pitch (OPA2991 datasheet, DSG
    land pattern example): 0.5 x 0.25 mm pads on 1.9 mm row centres and a
    0.9 x 1.6 mm thermal pad (9, to V- on the OPA2991). Pins 1-4 down the left,
    5-8 up the right. KiCad's stock DSG0008A footprint has 0.6 mm pads.
    """
    pads = []
    for index in range(4):
        row = round(-0.75 + index * 0.5, 2)
        pads.append(smd_pad(str(index + 1), -0.95, row, 0.5, 0.25))
        pads.append(smd_pad(str(8 - index), 0.95, row, 0.5, 0.25))
    pads.append(smd_pad('9', 0, 0, 0.9, 1.6))
    outline = (
        box(-1.0, -1.0, 1.0, 1.0, 'F.Fab', 0.05)
        + line(-0.6, -1.15, 1.0, -1.15, 'F.SilkS', 0.08)
        + line(-1.0, 1.15, 1.0, 1.15, 'F.SilkS', 0.08)
        + circle(-1.15, -1.15, 0.07, 'F.SilkS', 0.05, fill=True)
        + box(-1.45, -1.3, 1.45, 1.3, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "TI_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "TI DSG0008A WSON-8 2 x 2 mm, 0.5 mm pitch, 0.9 x 1.6 mm thermal pad; land pattern from '
        'https://www.ti.com/lit/ds/symlink/opa2991.pdf")\n'
        '\t(tags "WSON DSG opamp")\n'
        + text('Reference', 'REF**', 0, -1.7, 'F.SilkS')
        + text('Value', 'OPA2991IDSGR', 0, 1.7, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + '''\t(model "${KICAD10_3DMODEL_DIR}/Package_SON.3dshapes/WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm.step"
\t\t(offset
\t\t\t(xyz 0 0 0)
\t\t)
\t\t(scale
\t\t\t(xyz 1 1 1)
\t\t)
\t\t(rotate
\t\t\t(xyz 0 0 0)
\t\t)
\t)
'''
        + ')\n'
    )


def mcc_dfn1510_6():
    """MCC DFN1510-6, 1.5 x 1.0 x 0.55 mm, 0.5 mm pitch (SRL05P7 rev 3-5,
    suggested solder pad layout): 0.20 x 0.35 mm pads, rows 0.65 mm apart.
    Top view as the datasheet: 1-3 left to right along the bottom, 4-6 right to
    left along the top (pin 1 bottom left). Pin 1 dot on the silk.
    """
    pads = []
    for number, x, y in (
        ('1', -0.5, 0.325), ('2', 0, 0.325), ('3', 0.5, 0.325),
        ('4', 0.5, -0.325), ('5', 0, -0.325), ('6', -0.5, -0.325),
    ):
        pads.append(smd_pad(number, x, y, 0.2, 0.35))
    outline = (
        box(-0.75, -0.5, 0.75, 0.5, 'F.Fab', 0.05)
        + line(-0.95, -0.25, -0.95, 0.25, 'F.SilkS', 0.08)
        + line(0.95, -0.25, 0.95, 0.25, 'F.SilkS', 0.08)
        + circle(-0.95, 0.6, 0.07, 'F.SilkS', 0.05, fill=True)
        + box(-1.1, -0.75, 1.0, 0.75, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "MCC_DFN1510-6_1.5x1.0mm_P0.5mm"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "MCC DFN1510-6 1.5 x 1.0 mm, 0.5 mm pitch (SRL05P7-TP); land pattern from '
        'https://www.mccsemi.com/pdf/Products/SRL05P7(DFN1510-6).pdf")\n'
        '\t(tags "ESD TVS USB DFN")\n'
        + text('Reference', 'REF**', 0, -1.2, 'F.SilkS')
        + text('Value', 'SRL05P7', 0, 1.2, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def kingbright_apgb0607():
    """Kingbright APGB0607 bi-colour LED, 0.65 x 0.65 x 0.25 mm (APGB0607G22R23C
    rev V.3A, recommended soldering pattern): four 0.25 x 0.25 mm pads with 0.15 mm
    gaps. Top view: 1 green anode top left, 2 green cathode bottom left, 3 red
    cathode bottom right, 4 red anode top right. Pin 1 dot on the silk.
    """
    offset = 0.2
    pads = [
        smd_pad('1', -offset, -offset, 0.25, 0.25),
        smd_pad('2', -offset, offset, 0.25, 0.25),
        smd_pad('3', offset, offset, 0.25, 0.25),
        smd_pad('4', offset, -offset, 0.25, 0.25),
    ]
    outline = (
        box(-0.325, -0.325, 0.325, 0.325, 'F.Fab', 0.05)
        + circle(-0.56, -0.56, 0.07, 'F.SilkS', 0.05, fill=True)
        + box(-0.7, -0.7, 0.6, 0.6, 'F.CrtYd', 0.05)
    )
    return (
        '(footprint "LED_Kingbright_APGB0607"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Kingbright APGB0607 green/red bi-colour LED, 0.65 x 0.65 mm, 4 pads; '
        'land pattern from https://www.kingbrightusa.com/images/catalog/SPEC/APGB0607G22R23C.pdf")\n'
        '\t(tags "LED bicolor")\n'
        + text('Reference', 'REF**', 0, -1.1, 'F.SilkS')
        + text('Value', 'APGB0607G22R23C', 0, 1.1, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def phoenix_mc05_2_smd():
    """Phoenix MC 0,5/ 2-G-2,54 SMD R24 (1821698), drawing 00783144 rev 02. Origin
    on pin 1's pad; +y points out of the mating side. Pads 1.2 x 2.06 at 2.54, their
    outer edge 7.38 behind the mating face; peg holes 1.2, 2.54 outside the end pins
    and 4.24 behind the mating face; body 9.66 wide (3.56 to pin 1), 7.1 deep, 4.85
    high; end flanges stop 3.1 short of the face, the centre starts 1.52 from pin 1.
    """
    face = 6.35  # 7.38 - 2.06 / 2
    back = round(face - 7.1, 2)
    hole_y = round(face - 4.24, 2)
    left, right = -3.56, 6.10
    flange_end = round(face - 3.1, 2)
    pads = [smd_pad(1, 0, 0, 1.2, 2.06), smd_pad(2, 2.54, 0, 1.2, 2.06),
            npth(-2.54, hole_y, 1.2), npth(5.08, hole_y, 1.2)]
    outline = (
        line(left, back, right, back, 'F.Fab', 0.1)
        + line(right, back, right, flange_end, 'F.Fab', 0.1)
        + line(right, flange_end, 4.06, flange_end, 'F.Fab', 0.1)
        + line(4.06, flange_end, 4.06, face, 'F.Fab', 0.1)
        + line(4.06, face, -1.52, face, 'F.Fab', 0.1)
        + line(-1.52, face, -1.52, flange_end, 'F.Fab', 0.1)
        + line(-1.52, flange_end, left, flange_end, 'F.Fab', 0.1)
        + line(left, flange_end, left, back, 'F.Fab', 0.1)
        + line(left - 0.12, -0.8, left - 0.12, flange_end + 0.12, 'F.SilkS', 0.12)
        + line(right + 0.12, -0.8, right + 0.12, flange_end + 0.12, 'F.SilkS', 0.12)
        + box(left - 0.25, -1.3, right + 0.25, face + 0.25, 'F.CrtYd', 0.05)
        + circle(-1.1, -0.9, 0.2, 'F.SilkS', 0.12, fill=True)
    )
    return (
        '(footprint "PhoenixContact_MC_0,5_2-G-2,54_SMD_1x02_P2.54mm_Horizontal"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "Phoenix Contact 1821698 MC 0,5/ 2-G-2,54 SMD R24, right angle, '
        '2.54 mm (drawing 00783144 rev 02)")\n'
        + text('Reference', 'REF**', 1.27, -2.4, 'F.SilkS')
        + text('Value', '1821698', 1.27, 3.0, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def srp4020ta():
    """Bourns SRP4020TA, 4.45 x 4.06 x 1.8 mm. Recommended layout (datasheet p.1):
    5.2 mm overall, 2.2 mm gap, 2.4 mm tall, so 1.5 mm wide pads. The outline is
    drawn slightly wide so the silkscreen clears the pads.
    """
    pads = [smd_pad('1', -1.85, 0, 1.5, 2.4), smd_pad('2', 1.85, 0, 1.5, 2.4)]
    return footprint(
        'L_Bourns_SRP4020TA',
        'Bourns SRP4020TA shielded power inductor, 4.45 x 4.06 x 1.8 mm; land pattern '
        'from https://www.bourns.com/docs/product-datasheets/srp4020ta.pdf',
        (2.4, 2.03),
        pads,
        courtyard=(2.85, 2.53),
    )


def aos_dfn3x3a():
    """AOS DFN3x3A_8L_EP1_P (PO-00047 ver I) recommended land pattern. Bottom row
    1-4 left to right (S, S, S, G), 0.35 x 0.5 mm at 0.65 mm pitch, centres 1.40 mm
    below the tab line. Drain pad: 2.45 mm wide, ending 0.63 mm below the tab line,
    four 0.4 mm fingers on top (pins 5-8 right to left), 0.38 mm tabs on each side.
    """
    row_x = (-0.975, -0.325, 0.325, 0.975)
    pads = [
        smd_pad(str(index + 1), x, 1.4, 0.35, 0.5)
        for index, x in enumerate(row_x)
    ]
    pads += [
        smd_pad(str(8 - index), x, -1.475, 0.4, 0.35)
        for index, x in enumerate(row_x)
    ]
    pads.append(smd_pad('5', 0, -0.36, 2.45, 1.98))  # merged drain pad
    pads.append(smd_pad('5', 0, 0, 3.21, 0.43))  # side tabs
    return footprint(
        'AOS_DFN3x3A_8L_EP1',
        'AOS DFN 3x3 EP (AONR21307, drawn for AONR21305C) with 8 leads; land pattern from AOS drawing '
        'PO-00047 ver I, DFN3x3A_8L_EP1_P. Pins 5-8 and the drain pad are one net',
        (1.5, 1.5),
        pads,
        circle(-1.95, 1.4, 0.12, 'F.SilkS', 0.12, fill=True),
        courtyard=(2.1, 2.0),
    )


def onsemi_dfn12_506ad():
    """onsemi DFN12 3.0 x 1.35 mm, 0.5 mm pitch, case 506AD (NUF6401/D rev 5)
    soldering footprint: 0.479 x 0.265 mm pads, 0.199 mm from a 2.352 x 0.351 mm
    ground pad. Top view: pins 1-6 left to right on the bottom row, 7-12 right to
    left on the top row (12 above 1).
    """
    row = round(0.351 / 2 + 0.199 + 0.479 / 2, 4)
    pads = []
    for index in range(6):
        x = round(-1.25 + index * 0.5, 2)
        pads.append(smd_pad(str(index + 1), x, row, 0.265, 0.479))
        pads.append(smd_pad(str(12 - index), x, -row, 0.265, 0.479))
    pads.append(smd_pad('13', 0, 0, 2.352, 0.351))
    return footprint(
        'OnSemi_DFN-12-1EP_506AD',
        'onsemi DFN12 3.0x1.35 mm 0.5P, case 506AD, with ground pad; land pattern from '
        'https://www.onsemi.com/pdf/datasheet/nuf6401-d.pdf',
        (1.5, 0.675),
        pads,
        circle(-2.0, 0.9, 0.12, 'F.SilkS', 0.12, fill=True),
        courtyard=(2.2, 1.2),
    )


def ti_dfm0020a():
    """TI DFM0020A SOIC-20W land pattern for 8.1 mm clearance/creepage (ISOW774x
    SLLSFK1C): 20 x 1.65 x 0.6 mm pads, 1.27 mm pitch, 9.75 mm between pad centres.
    Stock SOIC-20W land patterns leave less clearance than this. The silkscreen
    outline is drawn narrower than the 7.5 mm body to clear the pads.
    """
    pads = []
    for index in range(10):
        row = round(-5.715 + index * 1.27, 3)
        pads.append(smd_pad(str(index + 1), -4.875, row, 1.65, 0.6))
        pads.append(smd_pad(str(20 - index), 4.875, row, 1.65, 0.6))
    return footprint(
        'TI_DFM0020A',
        'TI DFM0020A SOIC-20W, 7.5 x 12.8 mm body; 8.1 mm clearance land pattern from '
        'https://www.ti.com/lit/ds/symlink/isow7741.pdf',
        (3.6, 6.4),
        pads,
        circle(-4.875, -6.5, 0.15, 'F.SilkS', 0.12, fill=True),
        courtyard=(5.95, 6.9),
    )


def r_1206_or_bourns_3313j():
    """A 1206 resistor or a Bourns 3313J trimmer used as a rheostat. The trimmer's end
    pads (1 left, 3 right, J leads up) double as the 1206 lands, so pad 2 is pin 3 and
    the wiper pad below; route a track between them. Land pattern from the 3313J
    drawing (pads 1.1 x 1.6 at +/-1.15, wiper 1.6 x 1.6, rows 2.9 apart), with the end
    pads 0.4 mm longer outward and 0.15 mm taller for the 1206 toe. The wiper has no
    paste, so the assembled 1206 leaves it bare. Clockwise raises the resistance.
    """
    pads = [
        smd_pad('1', -1.35, 0, 1.5, 1.75),
        smd_pad('2', 1.35, 0, 1.5, 1.75),
        '''\t(pad "2" smd rect
\t\t(at 0 2.9)
\t\t(size 1.6 1.6)
\t\t(layers "F.Cu" "F.Mask")
\t)
''',
    ]
    silk = (
        line(-2.36, -1.135, 2.36, -1.135, 'F.SilkS', 0.12)
        + line(2.36, -1.135, 2.36, 3.96, 'F.SilkS', 0.12)
        + line(2.36, 3.96, -2.36, 3.96, 'F.SilkS', 0.12)
        + line(-2.36, 3.96, -2.36, -1.135, 'F.SilkS', 0.12)
    )
    # 1206 body, and the trimmer body (3.2 x 3.5, centred between the pad rows)
    fab = rect(1.6, 0.8, 'F.Fab', 0.1) + ''.join(
        line(*start, *end, 'F.Fab', 0.1)
        for start, end in (
            ((-1.6, -0.3), (1.6, -0.3)),
            ((1.6, -0.3), (1.6, 3.2)),
            ((1.6, 3.2), (-1.6, 3.2)),
            ((-1.6, 3.2), (-1.6, -0.3)),
        )
    )
    courtyard = ''.join(
        line(*start, *end, 'F.CrtYd', 0.05)
        for start, end in (
            ((-2.5, -1.3), (2.5, -1.3)),
            ((2.5, -1.3), (2.5, 4.1)),
            ((2.5, 4.1), (-2.5, 4.1)),
            ((-2.5, 4.1), (-2.5, -1.3)),
        )
    )
    name = 'R_1206_or_Bourns_3313J'
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "1206 resistor, or Bourns 3313J-1 3 mm trimmer as a rheostat (wiper tied '
        'to pin 3); land pattern from https://www.bourns.com/docs/Product-Datasheets/3313.pdf")\n'
        + text('Reference', 'REF**', 0, -2.3, 'F.SilkS')
        + text('Value', name, 0, 5.2, 'F.Fab')
        + '\t(attr smd)\n'
        + fab
        + silk
        + courtyard
        + ''.join(pads)
        + '''\t(model "${KICAD10_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_1206_3216Metric.step"
\t\t(offset
\t\t\t(xyz 0 0 0)
\t\t)
\t\t(scale
\t\t\t(xyz 1 1 1)
\t\t)
\t\t(rotate
\t\t\t(xyz 0 0 0)
\t\t)
\t)
'''
        + ')\n'
    )


def te_1571300_2():
    """TE 1571300-2 right-angle SMT tact switch (customer drawing C-1571300). Origin at the
    body centre, +y towards the actuator: body 8.1 x 5.5, actuator 3.3 wide and 2.7 past the
    front face. Contacts 1.5 x 3.5 at x +/-2.0, y -0.5; bracket lands 1.65 wide at x +/-4.775
    (rear 1.8 long at y -2.85, front 2.0 long at y 1.05), unnumbered; Ø0.85 locating pegs at
    x +/-4.4, y -1.25. Silk runs along the rear only, so the front can sit at the board edge.
    """
    name = 'SW_TE_1571300-2'
    pads = [
        smd_pad('1', -2.0, -0.5, 1.5, 3.5),
        smd_pad('2', 2.0, -0.5, 1.5, 3.5),
        *[smd_pad('', sign * 4.775, -2.85, 1.65, 1.8) for sign in (-1, 1)],
        *[smd_pad('', sign * 4.775, 1.05, 1.65, 2.0) for sign in (-1, 1)],
        npth(-4.4, -1.25, 0.85),
        npth(4.4, -1.25, 0.85),
    ]
    outline = (
        rect(4.05, 2.75, 'F.Fab', 0.1)
        + line(-1.65, 2.75, -1.65, 5.45, 'F.Fab', 0.1)
        + line(-1.65, 5.45, 1.65, 5.45, 'F.Fab', 0.1)
        + line(1.65, 5.45, 1.65, 2.75, 'F.Fab', 0.1)
        + line(-3.7, -3.05, 3.7, -3.05, 'F.SilkS', 0.12)
        + circle(-2.0, -3.55, 0.15, 'F.SilkS', 0.12, fill=True)
        + polygon([(-5.85, -4.0), (5.85, -4.0), (5.85, 5.7), (-5.85, 5.7)], 'F.CrtYd', 0.05)
    )
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "TE Connectivity 1571300-2 right-angle SMT tact switch, SPST-NO '
        '(drawing C-1571300)")\n'
        + text('Reference', 'REF**', 0, -5.0, 'F.SilkS')
        + text('Value', '1571300-2', 0, 0.5, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def xkb_x2510wrs(pins):
    """XKB X2510WRS-0N-9TSN right-angle SMT wafer, 2.54 mm (drawing X-X2510WRS-02-9TSN
    rev A0, which covers 2, 4 and 5 poles). Origin on pin 1's pad; +y points out of the
    mating side. Signal pads 1.2 x 4.0; hold-down pads 1.1 x 3.4, 1.73 outside the end
    pins and ending 6.0 from the signal pads' rear edge. Body (N + 1) x 2.54 wide and
    4.35 deep; tails 2.25 behind it, pins and friction wall 7.0 ahead (13.6 overall).
    The tail tips sit about 0.44 inside the pads' rear edge (scaled, not dimensioned).
    """
    name = f'XKB_X2510WRS-{pins:02d}-9TSN_1x{pins:02d}_P2.54mm_Horizontal'
    span = round((pins - 1) * 2.54, 2)
    body_back, body_front, tip = 0.69, 5.04, 12.04
    left, right = -2.54, round(span + 2.54, 2)
    pads = [smd_pad(str(index + 1), round(index * 2.54, 2), 0, 1.2, 4.0)
            for index in range(pins)]
    pads += [smd_pad('', -1.73, 2.3, 1.1, 3.4),
             smd_pad('', round(span + 1.73, 2), 2.3, 1.1, 3.4)]
    outline = (
        box(left, body_back, right, body_front, 'F.Fab', 0.1)
        + box(-0.6, body_front, round(span + 0.6, 2), tip, 'F.Fab', 0.1)
        + line(left - 0.12, body_back, left - 0.12, body_front, 'F.SilkS', 0.12)
        + line(right + 0.12, body_back, right + 0.12, body_front, 'F.SilkS', 0.12)
        + circle(-1.2, -1.4, 0.2, 'F.SilkS', 0.12, fill=True)
        + box(left - 0.25, -2.15, right + 0.25, tip + 0.25, 'F.CrtYd', 0.05)
    )
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        f'\t(descr "XKB X2510WRS-{pins:02d}-9TSN right-angle SMT wafer, {pins} pins, '
        '2.54 mm, mates with X2510H housings (drawing X-X2510WRS-02-9TSN rev A0)")\n'
        + text('Reference', 'REF**', round(span / 2, 2), -3.2, 'F.SilkS')
        + text('Value', f'X2510WRS-{pins:02d}', round(span / 2, 2), 2.9, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


def xkb_x2510wrs_02():
    return xkb_x2510wrs(2)


def xkb_x2510wrs_04():
    return xkb_x2510wrs(4)


def plated_slot(number, x, y, size, drill):
    """Plated oval through-hole pad; size and drill are (x, y) pairs."""
    return f'''\t(pad "{number}" thru_hole oval
\t\t(at {x} {y})
\t\t(size {size[0]} {size[1]})
\t\t(drill oval {drill[0]} {drill[1]})
\t\t(layers "*.Cu" "*.Mask")
\t)
'''


def gct_usb4205():
    """GCT USB4205-GF-A, 16-pin USB-C 2.0 flag-type receptacle standing on its side
    (drawing USB4205 rev A2, 06/05/25). Origin at the centre of the pad field; +y points
    out of the mouth. Two columns of eight pads, 1.05 long with outer edges 2.80 apart,
    B12..B1 on -x and A1..A12 on +x from the back: rows at 2.6 / 1.8 (0.45 wide) and
    1.05 / 0.35 (0.35 wide). Shell stakes: 0.60 x 1.20 plated slots at x +/-2.03, 6.10
    apart; Ø0.80 pegs on the axis, 7.15 apart. Body 3.71 x 14.0, 12.5 high; GCT draws the
    board edge 2.70 past the front slots (y 5.58), which leaves the mouth 4.3 past it.
    """
    name = 'USB_C_Receptacle_GCT_USB4205-GF-A_16P_Flag'
    rows = ((2.6, 0.45, ('12', '1')), (1.8, 0.45, ('9', '4')),
            (1.05, 0.35, ('8', '5')), (0.35, 0.35, ('7', '6')))
    pads = []
    for offset, width, (back_b, back_a) in rows:
        front_b, front_a = str(13 - int(back_b)), str(13 - int(back_a))
        pads += [
            smd_pad(f'B{back_b}', -0.875, -offset, 1.05, width),
            smd_pad(f'A{back_a}', 0.875, -offset, 1.05, width),
            smd_pad(f'B{front_b}', -0.875, offset, 1.05, width),
            smd_pad(f'A{front_a}', 0.875, offset, 1.05, width),
        ]
    pads += [plated_slot('SH', sign * 2.03, y, (0.9, 1.5), (0.6, 1.2))
             for sign in (-1, 1) for y in (-3.22, 2.88)]
    pads += [npth(0, -3.57, 0.8), npth(0, 3.58, 0.8)]
    back, mouth = -4.12, 9.88
    outline = (
        box(-1.855, back, 1.855, mouth, 'F.Fab', 0.1)
        + line(-1.2, back - 0.25, 1.2, back - 0.25, 'F.SilkS', 0.12)
        + circle(2.0, -4.4, 0.15, 'F.SilkS', 0.12, fill=True)
        + box(-2.6, back - 0.4, 2.6, mouth + 0.25, 'F.CrtYd', 0.05)
    )
    return (
        f'(footprint "{name}"\n'
        '\t(version 20260206)\n'
        '\t(generator "make_footprints")\n'
        '\t(layer "F.Cu")\n'
        '\t(descr "GCT USB4205-GF-A USB-C 2.0 receptacle, 16 pin, flag type, top mount '
        '(https://gct.co/files/drawings/usb4205.pdf rev A2)")\n'
        + text('Reference', 'REF**', 0, -5.6, 'F.SilkS')
        + text('Value', 'USB4205-GF-A', 0, 6.5, 'F.Fab')
        + '\t(attr smd)\n'
        + outline
        + ''.join(pads)
        + ')\n'
    )


FOOTPRINTS = {
    'XKB_X2510WRS-02-9TSN_1x02_P2.54mm_Horizontal': xkb_x2510wrs_02,
    'XKB_X2510WRS-04-9TSN_1x04_P2.54mm_Horizontal': xkb_x2510wrs_04,
    'USB_C_Receptacle_GCT_USB4205-GF-A_16P_Flag': gct_usb4205,
    'SW_TE_1571300-2': te_1571300_2,
    'R_1206_or_Bourns_3313J': r_1206_or_bourns_3313j,
    'TE_2305908-2_1x02_P5.00mm_Horizontal_SMD': te_2305908_2,
    'TE_2305908-3_1x03_P5.00mm_Horizontal_SMD': te_2305908_3,
    'TE_643228-1_1x03_P6.35mm_Horizontal': te_643228_1,
    'PhoenixContact_MC_0,5_2-G-2,54_SMD_1x02_P2.54mm_Horizontal': phoenix_mc05_2_smd,
    'Tensility_54-00164_5.5x2.1mm_Horizontal_SMD': tensility_54_00164,
    'SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD': same_sky_mj_3523,
    'Sullins_SWR25X-NRTC-S02-RB-BA_1x02_P2.54mm_Horizontal': sullins_swr25x_s02_rb,
    'FanHeader_4P_P2.54mm_Horizontal': fan_header_4p,
    'Wurth_WR-WTB_61900311021_1x03_P2.54mm_Horizontal': wurth_61900311021,
    'L_Coilcraft_MSD7342': msd7342,
    'L_Bourns_SRP6050CA': srp6050ca,
    'L_Bourns_SRP4020TA': srp4020ta,
    'SW_Panasonic_EVQ-P2F': panasonic_evq_p2f,
    'SW_Panasonic_EVP-AA': panasonic_evp_aa,
    'LED_Kingbright_APGB0607': kingbright_apgb0607,
    'AOS_DFN3x3A_8L_EP1': aos_dfn3x3a,
    'OnSemi_DFN-12-1EP_506AD': onsemi_dfn12_506ad,
    'Littelfuse_DFN-5_1.0x0.6mm_P0.35mm': littelfuse_dfn5,
    'MCC_DFN1510-6_1.5x1.0mm_P0.5mm': mcc_dfn1510_6,
    'TI_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm': ti_dsg0008a,
    'Nexperia_XSON-6_SOT886_1.0x1.45mm_P0.5mm': nexperia_sot886,
    'Nexperia_X2SON-5_SOT1226-3_0.8x0.8mm_P0.5mm': nexperia_sot1226_3,
    'TI_DFM0020A': ti_dfm0020a,
    'RJ45_Amphenol_RJSSE-5380_Horizontal': rjsse5380,
    MICRO_LOCK_NAME: molex_505448_0891,
    'Adafruit_1769_JST-PH_1x02_P2.00mm_Horizontal_SMD': adafruit_1769,
    'Adafruit_4392_JST-PH_1x04_P2.00mm_Horizontal_SMD': adafruit_4392,
}


def main():
    for name, build in FOOTPRINTS.items():
        (PRETTY / f'{name}.kicad_mod').write_text(build())
        print(f'wrote {name}')


if __name__ == '__main__':
    main()
