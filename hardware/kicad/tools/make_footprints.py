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


def footprint(name, descr, tags, body):
    # 3D envelope models are attached by pcbmodels.py
    return (
        f'(footprint "{name}"\n\t(version 20260206)\n'
        '\t(generator "cryocooler_gen")\n\t(generator_version "1.0")\n'
        f'\t(layer "F.Cu")\n\t(descr "{descr}")\n\t(tags "{tags}")\n'
        + '\n'.join(body)
        + '\n\t(attr smd)\n)\n'
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


FOOTPRINTS = [molex_505448_0871]


def main():
    for build in FOOTPRINTS:
        name, text = build()
        path = OUT_DIR / f'{name}.kicad_mod'
        path.write_text(text)
        print('wrote', path)


if __name__ == '__main__':
    main()
