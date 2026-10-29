"""Writes footprints that KiCad does not ship into lib/cryocooler.pretty.

Run: python3 hardware/kicad/tools/make_footprints.py
Every dimension comes from the manufacturer drawing named in the footprint's
descr; re-check it there before changing a number.
"""

from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / 'lib' / 'cryocooler.pretty'


def fmt(value):
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def text_prop(name, value, x, y, layer, hide=False):
    hidden = '\n\t\t(hide yes)' if hide else ''
    return (
        f'\t(property "{name}" "{value}"\n\t\t(at {fmt(x)} {fmt(y)} 0)\n'
        f'\t\t(layer "{layer}"){hidden}\n'
        '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
        '\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)'
    )


def line(x1, y1, x2, y2, layer, width):
    return (
        f'\t(fp_line\n\t\t(start {fmt(x1)} {fmt(y1)})\n'
        f'\t\t(end {fmt(x2)} {fmt(y2)})\n'
        f'\t\t(stroke\n\t\t\t(width {fmt(width)})\n\t\t\t(type solid)\n\t\t)\n'
        f'\t\t(layer "{layer}")\n\t)'
    )


def rect(x1, y1, x2, y2, layer, width):
    return [
        line(x1, y1, x2, y1, layer, width),
        line(x2, y1, x2, y2, layer, width),
        line(x2, y2, x1, y2, layer, width),
        line(x1, y2, x1, y1, layer, width),
    ]


def smd_pad(number, x, y, width, height):
    return (
        f'\t(pad "{number}" smd roundrect\n\t\t(at {fmt(x)} {fmt(y)})\n'
        f'\t\t(size {fmt(width)} {fmt(height)})\n'
        '\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n'
        '\t\t(roundrect_rratio 0.1)\n\t)'
    )


def tht_pad(number, x, y, drill, diameter):
    return (
        f'\t(pad "{number}" thru_hole circle\n\t\t(at {fmt(x)} {fmt(y)})\n'
        f'\t\t(size {fmt(diameter)} {fmt(diameter)})\n'
        f'\t\t(drill {fmt(drill)})\n'
        '\t\t(layers "*.Cu" "*.Mask")\n\t)'
    )


def footprint(name, descr, tags, body, attr='smd'):
    # 3D envelope models are attached by pcbmodels.py
    return (
        f'(footprint "{name}"\n\t(version 20260206)\n'
        '\t(generator "cryocooler_gen")\n\t(generator_version "1.0")\n'
        f'\t(layer "F.Cu")\n\t(descr "{descr}")\n\t(tags "{tags}")\n'
        + '\n'.join(body)
        + f'\n\t(attr {attr})\n)\n'
    )


# ─── Molex Micro-Lock Plus 505448-0871 ────────────────────────────────────
# Sales drawing 5054480871_sd.pdf sheet 2 (PCB pattern, component side) and
# sheet 1 table (8 circuits: A 9.6, B 3.75). Mating face is at -y. Odd circuits
# sit on the rear row, even circuits on the row by the mating face; circuit 1
# and 2 are the left-most pads.
MOLEX_PITCH = 1.25
MOLEX_PAD = (0.8, 2.0)
MOLEX_ROW_Y = 3.7          # pad centre to footprint centre (9.4 outer span)
MOLEX_NAIL = (1.0, 4.85)
MOLEX_NAIL_X = 1.875 + 2.2  # end pad centre + 2.2
MOLEX_NAIL_Y = -4.7 + 0.7 + 4.85 / 2  # 0.7 below the front pad edge
MOLEX_BODY = (9.6, 8.95)    # A x body depth (sheet 1 plan view)


def molex_505448_0871():
    name = 'Molex_Micro-Lock_Plus_505448-0871_2x04_P1.25mm_Horizontal'
    columns = 4
    first_x = -MOLEX_PITCH * (columns - 1) / 2
    pads = []
    for column in range(columns):
        x = first_x + column * MOLEX_PITCH
        pads.append(smd_pad(2 * column + 1, x, MOLEX_ROW_Y, *MOLEX_PAD))
        pads.append(smd_pad(2 * column + 2, x, -MOLEX_ROW_Y, *MOLEX_PAD))
    for side in (-1, 1):
        pads.append(
            smd_pad('MP', side * MOLEX_NAIL_X, MOLEX_NAIL_Y, *MOLEX_NAIL)
        )
    half_w = MOLEX_BODY[0] / 2
    half_d = MOLEX_BODY[1] / 2
    court_x = max(half_w, MOLEX_NAIL_X + MOLEX_NAIL[0] / 2) + 0.25
    court_y = MOLEX_ROW_Y + MOLEX_PAD[1] / 2 + 0.25
    body = [
        text_prop('Reference', 'REF**', 0, -court_y - 0.9, 'F.SilkS'),
        text_prop('Value', name, 0, court_y + 0.9, 'F.Fab'),
        text_prop(
            'Datasheet',
            'https://www.molex.com/content/dam/molex/molex-dot-com/products/'
            'automated/en-us/salesdrawingpdf/505/505448/5054480871_sd.pdf',
            0, 0, 'F.Fab', hide=True,
        ),
        text_prop('Description', 'Micro-Lock Plus 1.25 mm dual-row '
                  'right-angle SMT header, 8 circuits', 0, 0, 'F.Fab',
                  hide=True),
    ]
    body += rect(-half_w, -half_d, half_w, half_d, 'F.Fab', 0.1)
    # mating face marker and pin-1 marks (fab + silk, beside circuit 1)
    body.append(line(-half_w, -half_d + 0.6, half_w, -half_d + 0.6, 'F.Fab',
                     0.1))
    pin1_x = first_x - MOLEX_PAD[0] / 2 - 0.35
    pin1_y = MOLEX_ROW_Y + MOLEX_PAD[1] / 2 + 0.45
    body.append(line(pin1_x, pin1_y, pin1_x + 0.9, pin1_y, 'F.SilkS', 0.15))
    body.append(line(pin1_x, pin1_y, pin1_x, pin1_y - 0.9, 'F.SilkS', 0.15))
    body += rect(-court_x, -court_y, court_x, court_y, 'F.CrtYd', 0.05)
    descr = (
        'Molex Micro-Lock Plus 505448-0871, 1.25 mm pitch, 2x4, right angle, '
        'SMT, 1.5 A/contact; land pattern from https://www.molex.com/content/'
        'dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/505/'
        '505448/5054480871_sd.pdf (sheet 2)'
    )
    return name, footprint(
        name, descr, 'connector Molex Micro-Lock Plus 505448', body + pads
    )


# ─── Adafruit 1769 (4UCON 17311), JST PH compatible 2-pin SMT right angle ─
# Drawing https://cdn-shop.adafruit.com/datasheets/17311.pdf: signal pads
# 1.0 x 3.5 on 2.0 mm pitch; fitting nails 1.5 x 3.4, inner edge 1.6 past the
# outer pin centre, top 5.6 below the signal pad tops, bottom at the mating
# face. Body B 7.9 wide, 6.0 deep, 5.5 high, pins 2.6 behind the body. Mating
# face at +y, pin 1 on the left (pin-1 triangle on the plan view).
PH_PITCH = 2.0
PH_PAD = (1.0, 3.5)
PH_PAD_Y = -2.85
PH_NAIL = (1.5, 3.4)
PH_NAIL_TOP = PH_PAD_Y - PH_PAD[1] / 2 + 5.6
PH_BODY = (7.9, 6.0, 5.5)


def adafruit_1769():
    name = 'Adafruit_1769_JST-PH_1x02_P2.00mm_Horizontal_SMD'
    pads = [
        smd_pad(1, -PH_PITCH / 2, PH_PAD_Y, *PH_PAD),
        smd_pad(2, PH_PITCH / 2, PH_PAD_Y, *PH_PAD),
    ]
    nail_x = PH_PITCH / 2 + 1.6 + PH_NAIL[0] / 2
    nail_y = PH_NAIL_TOP + PH_NAIL[1] / 2
    for side in (-1, 1):
        pads.append(smd_pad('MP', side * nail_x, nail_y, *PH_NAIL))
    front = PH_NAIL_TOP + PH_NAIL[1]
    back = front - PH_BODY[1]
    half_w = PH_BODY[0] / 2
    court_x = max(half_w, nail_x + PH_NAIL[0] / 2) + 0.25
    court_top = PH_PAD_Y - PH_PAD[1] / 2 - 0.25
    court_bottom = front + 0.25
    body = [
        text_prop('Reference', 'REF**', 0, court_top - 0.9, 'F.SilkS'),
        text_prop('Value', name, 0, court_bottom + 0.9, 'F.Fab'),
        text_prop('Datasheet', 'https://cdn-shop.adafruit.com/datasheets/17311.pdf',
                  0, 0, 'F.Fab', hide=True),
        text_prop('Description', 'JST PH compatible 2-pin 2.0 mm right-angle '
                  'SMT header (Adafruit 1769)', 0, 0, 'F.Fab', hide=True),
    ]
    body += rect(-half_w, back, half_w, front, 'F.Fab', 0.1)
    # pin-1 mark on silk, left of pad 1
    mark_x = -PH_PITCH / 2 - PH_PAD[0] / 2 - 0.4
    body.append(line(mark_x, PH_PAD_Y - 1.0, mark_x, PH_PAD_Y + 1.0, 'F.SilkS', 0.15))
    body += rect(-court_x, court_top, court_x, court_bottom, 'F.CrtYd', 0.05)
    descr = (
        'Adafruit 1769 (4UCON 17311) JST PH compatible 2-pin, 2.0 mm pitch, '
        'right angle, SMT, 2 A; land pattern from '
        'https://cdn-shop.adafruit.com/datasheets/17311.pdf'
    )
    return name, footprint(name, descr, 'connector JST PH horizontal Adafruit 1769', body + pads)


# ─── TE T4145035041-001, M12 A-coded 4-pin female, right angle, shielded ──
# Customer drawing T41450350X1001 rev B (recommended PCB layout, component
# side; PCB 1.6 mm): contacts 1-4 on Ø1.30 holes at 45° on a Ø5.00 circle
# about the datum; Ø2.35 legs at X ±7.50 on the datum row, Ø2.80 legs and
# the Ø1.30 shield hole 4.00 towards the panel. The panel's inner face is
# 9.0 in front of the datum row (side view: 4.0 legs to contacts, 9.0 panel
# to contacts); body 19.5 wide, rear 11.9 behind the panel face, axis 8.5
# above the board, 16.0 high. Panel 2.0-3.0 thick, Ø12.20 cutout. +y is the
# panel side.
M12_CONTACT_DRILL = 1.30
M12_CONTACT_PAD = 2.0
M12_CIRCLE = 5.0
M12_LEG_X = 7.5
M12_FRONT_ROW = 4.0
M12_PANEL_Y = 9.0
M12_REAR_Y = M12_PANEL_Y - 11.9
M12_WIDTH = 19.5


def te_t4145035041():
    name = 'TE_T4145035041-001_M12_A-Code_4P_Female_Horizontal'
    offset = M12_CIRCLE / 2 / 2 ** 0.5
    pads = [
        tht_pad(1, -offset, -offset, M12_CONTACT_DRILL, M12_CONTACT_PAD),
        tht_pad(2, offset, -offset, M12_CONTACT_DRILL, M12_CONTACT_PAD),
        tht_pad(3, offset, offset, M12_CONTACT_DRILL, M12_CONTACT_PAD),
        tht_pad(4, -offset, offset, M12_CONTACT_DRILL, M12_CONTACT_PAD),
        # shield pin and the four shell legs: the symbol's SH pin (to GND)
        tht_pad('SH', 0, M12_FRONT_ROW, M12_CONTACT_DRILL, M12_CONTACT_PAD),
    ]
    for side in (-1, 1):
        pads.append(tht_pad('SH', side * M12_LEG_X, 0, 2.35, 3.0))
        pads.append(tht_pad('SH', side * M12_LEG_X, M12_FRONT_ROW, 2.80, 3.5))
    half_w = M12_WIDTH / 2
    court_x = half_w + 0.25
    body = [
        text_prop('Reference', 'REF**', 0, M12_REAR_Y - 1.2, 'F.SilkS'),
        text_prop('Value', name, 0, M12_PANEL_Y + 1.2, 'F.Fab'),
        text_prop('Datasheet', 'https://www.te.com/commerce/DocumentDelivery/DDEController'
                  '?Action=srchrtrv&DocNm=T41450350X1001&DocType=Customer%20Drawing'
                  '&DocLang=English&DocFormat=pdf&PartCntxt=T4145035041-001',
                  0, 0, 'F.Fab', hide=True),
        text_prop('Description', 'M12 A-coded 4-pin female receptacle, right angle, '
                  'shielded, panel and PCB mount (TE T4145035041-001)', 0, 0, 'F.Fab',
                  hide=True),
    ]
    body += rect(-half_w, M12_REAR_Y, half_w, M12_PANEL_Y, 'F.Fab', 0.1)
    # panel face line, and a pin-1 mark on silk beside contact 1
    body.append(line(-half_w, M12_PANEL_Y - 0.2, half_w, M12_PANEL_Y - 0.2, 'F.Fab', 0.1))
    body.append(line(-offset - 1.6, -offset - 1.2, -offset - 1.6, -offset + 0.2, 'F.SilkS', 0.15))
    body += rect(-court_x, M12_REAR_Y - 0.25, court_x, M12_PANEL_Y, 'F.CrtYd', 0.05)
    descr = (
        'TE Connectivity T4145035041-001, M12 A-coded 4-pin female, right angle, '
        'shielded, 4 A, 250 V, IP67, panel 2.0-3.0 mm; layout from TE customer '
        'drawing T41450350X1001 rev B'
    )
    return name, footprint(name, descr, 'connector M12 circular TE A-code', body + pads,
                           attr='through_hole')


FOOTPRINTS = [molex_505448_0871, adafruit_1769, te_t4145035041]


def main():
    for build in FOOTPRINTS:
        name, text = build()
        path = OUT_DIR / f'{name}.kicad_mod'
        path.write_text(text)
        print('wrote', path)


if __name__ == '__main__':
    main()
