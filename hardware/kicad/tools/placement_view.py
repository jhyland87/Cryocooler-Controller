"""Draws a placed board as two SVGs (front, back seen through the board) with the
section floorplan. Usage (KiCad's python, from hardware/kicad/tools):
    placement_view.py board.kicad_pcb out_prefix [board_module]
board_module is the board script that holds the floorplan (default rev7_board). A module
that sets PLACEMENT_VIEW_BY_SHEET = True has no sections: its parts are coloured by schematic
sheet instead and no boxes are drawn.
"""
import importlib
import sys

import pcbnew

sys.path.insert(0, '.')
import rev5_board as rev5  # noqa: E402
import ucs125_board as base  # noqa: E402

SCALE = 8.0
PAD = 14.0
COLOURS = ['#dbeafe', '#fde68a', '#d1fae5', '#fce7f3', '#e0e7ff', '#fee2e2', '#ccfbf1', '#fef3c7',
           '#ede9fe', '#dcfce7', '#ffe4e6', '#e0f2fe', '#f5f5f4', '#fae8ff', '#ecfccb', '#ffedd5']


BOARD_MODULE = importlib.import_module(sys.argv[3] if len(sys.argv) > 3 else 'rev7_board')
BY_SHEET = getattr(BOARD_MODULE, 'PLACEMENT_VIEW_BY_SHEET', False)
SHEET_COLOURS = ['#60a5fa', '#f59e0b', '#34d399', '#f472b6', '#a78bfa', '#f87171', '#2dd4bf', '#fbbf24',
                 '#818cf8', '#4ade80', '#fb7185', '#38bdf8', '#a3a3a3', '#e879f9', '#a3e635', '#fb923c']


def mm(value):
    return pcbnew.ToMM(value)


def box_of(footprint):
    flipped = footprint.IsFlipped()
    yard = footprint.GetCourtyard(pcbnew.B_CrtYd if flipped else pcbnew.F_CrtYd)
    box = yard.BBox() if yard.OutlineCount() else footprint.GetBoundingBox(False, False)
    return mm(box.GetLeft()), mm(box.GetTop()), mm(box.GetRight()), mm(box.GetBottom())


def draw(board, side, path):
    width, height = base.WIDTH, base.HEIGHT
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{(width + 2 * PAD + (30 if BY_SHEET else 0)) * SCALE:.0f}" '
           f'height="{(height + 2 * PAD) * SCALE:.0f}" viewBox="{-PAD} {-PAD} {width + 2 * PAD + (30 if BY_SHEET else 0)} {height + 2 * PAD}" '
           'font-family="Helvetica, Arial, sans-serif">',
           f'<rect x="{-PAD}" y="{-PAD}" width="{width + 2 * PAD + (30 if BY_SHEET else 0)}" height="{height + 2 * PAD}" fill="white"/>']
    notch = base.NOTCH
    points = [(0, 0), (notch.min_x, 0), (notch.min_x, notch.max_y), (notch.max_x, notch.max_y),
              (notch.max_x, 0), (width, 0), (width, height), (0, height)]
    out.append('<polygon points="' + ' '.join(f'{x},{y}' for x, y in points)
               + '" fill="#f8fafc" stroke="black" stroke-width="0.4"/>')
    sections = {} if BY_SHEET else dict(rev5.PRINTED_SECTIONS)
    sheet_of = {ref: part['sheet'] for ref, part in rev5.load_netlist()[0].items()} if BY_SHEET else {}
    sheets = sorted(set(sheet_of.values()))
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
        if BY_SHEET and ref in sheet_of:
            fill, stroke = SHEET_COLOURS[sheets.index(sheet_of[ref]) % len(SHEET_COLOURS)], '#1f2937'
        elif ref.startswith(('J', 'SW')):
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
    for index, name in enumerate(sheets):
        out.append(f'<rect x="{width + 3}" y="{index * 3.2}" width="2.4" height="2.4" '
                   f'fill="{SHEET_COLOURS[index % len(SHEET_COLOURS)]}" stroke="#1f2937" stroke-width="0.1"/>')
        out.append(f'<text x="{width + 6.2}" y="{index * 3.2 + 1.9}" font-size="1.8">{name.replace("&", "&amp;")}</text>')
    title = f'Placement, {side} ({width:g} x {height:g} mm)' + (
        ', seen through the board' if side == 'back' else '')
    out.append(f'<text x="0" y="-8" font-size="3">{title}</text>')
    out.append('</svg>')
    with open(path, 'w') as handle:
        handle.write('\n'.join(out))


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    for side in ('front', 'back'):
        draw(board, side, f'{sys.argv[2]}_{side}.svg')


if __name__ == '__main__':
    main()
