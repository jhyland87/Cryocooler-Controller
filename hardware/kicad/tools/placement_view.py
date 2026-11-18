"""Draws a placed board as two SVGs (front, back seen through the board) with the
section floorplan. Usage (KiCad's python, from hardware/kicad/tools):
    placement_view.py board.kicad_pcb out_prefix
"""
import sys

import pcbnew

sys.path.insert(0, '.')
import rev6_board as rev6  # noqa: E402
import rev5_board as rev5  # noqa: E402
import ucs125_board as base  # noqa: E402

SCALE = 8.0
PAD = 14.0
COLOURS = ['#dbeafe', '#fde68a', '#d1fae5', '#fce7f3', '#e0e7ff', '#fee2e2', '#ccfbf1', '#fef3c7',
           '#ede9fe', '#dcfce7', '#ffe4e6', '#e0f2fe', '#f5f5f4', '#fae8ff', '#ecfccb', '#ffedd5']


def mm(value):
    return pcbnew.ToMM(value)


def box_of(footprint):
    flipped = footprint.IsFlipped()
    yard = footprint.GetCourtyard(pcbnew.B_CrtYd if flipped else pcbnew.F_CrtYd)
    box = yard.BBox() if yard.OutlineCount() else footprint.GetBoundingBox(False, False)
    return mm(box.GetLeft()), mm(box.GetTop()), mm(box.GetRight()), mm(box.GetBottom())


def draw(board, side, path):
    width, height = base.WIDTH, base.HEIGHT
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{(width + 2 * PAD) * SCALE:.0f}" '
           f'height="{(height + 2 * PAD) * SCALE:.0f}" viewBox="{-PAD} {-PAD} {width + 2 * PAD} {height + 2 * PAD}" '
           'font-family="Helvetica, Arial, sans-serif">',
           f'<rect x="{-PAD}" y="{-PAD}" width="{width + 2 * PAD}" height="{height + 2 * PAD}" fill="white"/>']
    notch = base.NOTCH
    points = [(0, 0), (notch.min_x, 0), (notch.min_x, notch.max_y), (notch.max_x, notch.max_y),
              (notch.max_x, 0), (width, 0), (width, height), (0, height)]
    out.append('<polygon points="' + ' '.join(f'{x},{y}' for x, y in points)
               + '" fill="#f8fafc" stroke="black" stroke-width="0.4"/>')
    sections = dict(rev5.PRINTED_SECTIONS)
    for index, (name, rects) in enumerate(sections.items()):
        for rect in rects:
            out.append(f'<rect x="{rect.min_x}" y="{rect.min_y}" width="{rect.max_x - rect.min_x}" '
                       f'height="{rect.max_y - rect.min_y}" fill="{COLOURS[index % len(COLOURS)]}" '
                       'fill-opacity="0.75" stroke="#64748b" stroke-width="0.15" stroke-dasharray="1 0.6"/>')
    for rect in base.ISO_RECTS:
        out.append(f'<rect x="{rect.min_x}" y="{rect.min_y}" width="{rect.max_x - rect.min_x}" '
                   f'height="{rect.max_y - rect.min_y}" fill="none" stroke="#dc2626" stroke-width="0.4"/>')
    for keepout in base.ANTENNA_KEEPOUTS:
        out.append(f'<rect x="{keepout.min_x}" y="{keepout.min_y}" width="{keepout.max_x - keepout.min_x}" '
                   f'height="{keepout.max_y - keepout.min_y}" fill="#e5e7eb" stroke="#9ca3af" stroke-width="0.15"/>')
    for hole_x, hole_y in base.HOLES:
        out.append(f'<circle cx="{hole_x}" cy="{hole_y}" r="1.6" fill="white" stroke="black" stroke-width="0.3"/>')
    labels = []
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if not ref or footprint.IsFlipped() != (side == 'back'):
            continue
        left, top, right, bottom = box_of(footprint)
        if ref.startswith(('J', 'SW')):
            fill, stroke = '#2563eb', '#1e3a8a'
        elif ref.startswith('U'):
            fill, stroke = '#f59e0b', '#92400e'
        elif ref.startswith(('L', 'F', 'Q', 'D')):
            fill, stroke = '#10b981', '#065f46'
        elif ref.startswith('TP'):
            fill, stroke = '#a3a3a3', '#525252'
        else:
            fill, stroke = '#94a3b8', '#475569'
        out.append(f'<rect x="{left:.2f}" y="{top:.2f}" width="{right - left:.2f}" height="{bottom - top:.2f}" '
                   f'fill="{fill}" fill-opacity="0.8" stroke="{stroke}" stroke-width="0.1"/>')
        if ref.startswith(('J', 'SW', 'U')) and not ref.startswith('JP'):
            name = base.LABEL_FUNCTIONS.get(ref)
            text = f'{ref} {name}' if name else ref
            size = 1.5 if ref.startswith(('J', 'SW')) else 1.1
            labels.append(((left + right) / 2, (top + bottom) / 2, text, size, right - left, bottom - top))
    for x, y, text, size, wide, tall in labels:
        turn = f' transform="rotate(-90 {x:.2f} {y:.2f})"' if tall > wide * 1.3 else ''
        out.append(f'<text x="{x:.2f}" y="{y + size * 0.35:.2f}" font-size="{size}" text-anchor="middle" '
                   f'font-weight="bold" fill="black" stroke="white" stroke-width="0.25" paint-order="stroke"{turn}>{text}</text>')
    for index, (name, rects) in enumerate(sections.items()):
        rect = rects[0]
        out.append(f'<text x="{rect.min_x + 0.6}" y="{rect.max_y - 0.8}" font-size="1.5" fill="#334155" '
                   f'stroke="white" stroke-width="0.2" paint-order="stroke">{name.replace("&", "&amp;")}</text>')
    title = f'Rev 6 trial placement, {side} ({width:g} x {height:g} mm)' + (
        ', seen through the board' if side == 'back' else '')
    out.append(f'<text x="0" y="-8" font-size="3">{title}</text>')
    for edge, x, y in (('free edge (glue domes), antenna notch', width / 2, -3), ('long wall (housing)', width / 2, height + 5)):
        out.append(f'<text x="{x}" y="{y}" font-size="2.4" text-anchor="middle" fill="#475569">{edge}</text>')
    out.append(f'<text x="-4" y="{height / 2}" font-size="2.4" text-anchor="middle" fill="#475569" '
               f'transform="rotate(-90 -4 {height / 2})">side wall</text>')
    out.append(f'<text x="{width + 5}" y="{height / 2}" font-size="2.4" text-anchor="middle" fill="#475569" '
               f'transform="rotate(90 {width + 5} {height / 2})">side wall</text>')
    out.append('</svg>')
    with open(path, 'w') as handle:
        handle.write('\n'.join(out))


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    for side in ('front', 'back'):
        draw(board, side, f'{sys.argv[2]}_{side}.svg')


if __name__ == '__main__':
    main()
