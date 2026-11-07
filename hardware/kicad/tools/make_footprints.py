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


def onsemi_udfn8_517ad():
    """onsemi UDFN8 1.8 x 1.2 mm, 0.4 mm pitch, case 517AD (98AON22154D) soldering
    footprint: 0.25 x 0.45 mm pads (pin 1 is 0.35 mm wide, growing outward), rows
    1.50 mm overall, 1.10 x 0.35 mm ground pad. Pin 1 is bottom left, top view.
    """
    pads = [smd_pad('1', -0.65, 0.525, 0.35, 0.45)]
    pads += [
        smd_pad(number, x, 0.525, 0.25, 0.45)
        for number, x in (('2', -0.2), ('3', 0.2), ('4', 0.6))
    ]
    pads += [
        smd_pad(number, x, -0.525, 0.25, 0.45)
        for number, x in (('5', 0.6), ('6', 0.2), ('7', -0.2), ('8', -0.6))
    ]
    pads.append(smd_pad('9', 0, 0, 1.1, 0.35))
    return footprint(
        'OnSemi_UDFN-8-1EP_517AD',
        'onsemi UDFN8 1.8x1.2 mm 0.4P, case 517AD, with ground pad; land pattern from '
        'https://www.onsemi.com/pdf/datasheet/nuf4001mu-d.pdf',
        (0.9, 0.6),
        pads,
        circle(-1.4, 0.75, 0.12, 'F.SilkS', 0.12, fill=True),
        courtyard=(1.6, 1.1),
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


FOOTPRINTS = {
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
    'AOS_DFN3x3A_8L_EP1': aos_dfn3x3a,
    'OnSemi_UDFN-8-1EP_517AD': onsemi_udfn8_517ad,
    'TI_DFM0020A': ti_dfm0020a,
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
