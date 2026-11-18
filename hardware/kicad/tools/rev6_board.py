"""Places rev 6 in the Phoenix UCS 237-195 housing (PCB drawing 2203457: 212 x 170 mm
at most). The board runs the full 212 mm along one long wall and is cut back in
depth, so the two corners on that wall use the housing's own mounts and the free
edge sits on glue domes.

Rev 6 against rev 5: every wall connector is on the front, the display, RS-485,
SPI expansion and AUX ports are top-entry JST PH headers inside the board, and the
ESP32 antenna is on the free edge. The connector wall is the bottom edge of the
board file, as the housing hangs. The modes and the placer are rev5_board.py's.

Usage (KiCad's python): as rev5_board.py, e.g.
    rev6_board.py place in.kicad_pcb out.kicad_pcb
    rev6_board.py rules      (net class widths and vias in cryocooler.kicad_pro)
"""
import json
import sys
from pathlib import Path

import pcbnew

import rev5_board as rev5
import ucs125_board as base
from pcbplace import Rect

# ─── outline ───
base.WIDTH, base.HEIGHT = 212.0, 84.0
WIDTH, HEIGHT = base.WIDTH, base.HEIGHT
# bottom pair: housing corner mounts (203.6 mm apart); top pair: glue domes
base.HOLES = [(4.2, 4.2), (WIDTH - 4.2, 4.2), (4.2, HEIGHT - 4.2), (WIDTH - 4.2, HEIGHT - 4.2)]
# antenna over a notch in the free (top) edge
base.U1_SPOT = (106.0, 12.75)
base.NOTCH = Rect(96.5, 0.0, 115.5, 6.0)
base.ANTENNA_KEEPOUTS = [Rect(82.0, 0.0, 96.5, 6.75), Rect(115.5, 0.0, 130.0, 6.75)]
base.ANCHORS = {'U1': (*base.U1_SPOT, 0, 'top')}

# Wall connectors, all on the front: (ref, edge, side, start along the edge, overhang).
# Bottom (long wall): flow, fan and pump below the +12V end of the shunt, NTC, relay,
# the two cryocooler sensor cables, USB, I/O 1-4, the two pressure ports.
# Left, top to bottom: cryocooler output (its ground pin at the top, away from the
# isolated pins), amplifier input, 12 V in at the corner beside the fan header.
# Right, top to bottom: power button, amplifier REM and signal, the two precision
# ports. The top edge is free.
IO_START = 110.0
IO_PITCH = 13.3
base.EDGE_PLAN = [
    ('J12', 'left', 'top', 7.6, 3.29),
    ('J11', 'left', 'top', 46.4, 3.29),
    ('J2', 'left', 'top', 65.5, 0.3),
    ('J5', 'bottom', 'top', 22.2, 0.08),
    ('J3', 'bottom', 'top', 35.8, 0.24),
    ('J4', 'bottom', 'top', 49.1, 0.24),
    ('J6', 'bottom', 'top', 62.4, 0.3),
    ('J13', 'bottom', 'top', 70.7, 0.3),
    ('J10', 'bottom', 'top', 79.0, -0.3),
    ('J14', 'bottom', 'top', 92.0, 0.05),
    ('J1', 'bottom', 'top', 103.0, 0.55),
    *[(f'J{36 + n}', 'bottom', 'top', IO_START + IO_PITCH * n, 0.24) for n in range(4)],
    ('J32', 'bottom', 'top', 163.2, 0.24),
    ('J33', 'bottom', 'top', 176.5, 0.24),
    ('SW3', 'right', 'top', 8.2, 3.0),
    ('J8', 'right', 'top', 20.75, 0.29),
    ('J9', 'right', 'top', 31.3, 0.29),
    ('J31', 'right', 'top', 41.2, 0.24),
    ('J30', 'right', 'top', 54.7, 0.24),
]
# connectors inside the board: placed like any other part, with its spacing
INBOARD_CONNECTORS = {'J15', 'J34', 'J35', 'J40'}

# Preferred spots, nudged to the nearest free one: ref -> (x, y, rotation, side)
base.PREFERRED = {
    # ─── 12 V path in one line at y = 64.5: J2 -> F1 -> Q1 -> shunt, its +12V end
    # above the fan and pump headers ───
    'F1': (26.5, 64.5, 0, 'top'),
    'Q1': (33.0, 64.5, 270, 'top'),
    'R78': (40.0, 64.5, 180, 'top'),
    'D1': (30.6, 58.8, 90, 'top'),
    'C65': (38.0, 53.0, 0, 'top'),
    'C66': (49.0, 56.5, 0, 'top'),
    'U11': (33.0, 58.5, 0, 'bottom'),
    'U23': (40.0, 59.5, 0, 'bottom'),
    # ─── logic rails ───
    'U15': (48.0, 46.0, 0, 'top'),
    'L1': (48.0, 40.0, 0, 'top'),
    'U16': (54.0, 45.5, 0, 'top'),
    'L4': (54.0, 34.0, 0, 'top'),
    'U28': (50.0, 32.0, 0, 'bottom'),
    # ─── MCU: buttons beside the module, chip-select decoder behind it ───
    'SW1': (124.0, 8.0, 90, 'top'),
    'SW2': (124.0, 16.0, 90, 'top'),
    'U2': (106.0, 68.0, 0, 'bottom'),
    'U32': (122.0, 22.0, 0, 'bottom'),
    'U25': (90.0, 20.0, 0, 'bottom'),
    # ─── cryocooler sensors ───
    'U36': (97.0, 64.0, 0, 'top'),
    'U14': (85.0, 62.0, 0, 'bottom'),
    # ─── isolated amplifier monitor: U17 straddles the barrier at x = 34 ───
    'U18': (22.0, 32.0, 0, 'top'),
    'U17': (34.0, 45.0, 180, 'top'),
    # ─── +-15 V rails, signal generator ───
    'U20': (150.0, 14.0, 0, 'top'),
    'L2': (150.0, 21.4, 0, 'top'),
    'L3': (150.0, 6.6, 0, 'top'),
    'U21': (160.0, 20.0, 0, 'top'),
    'U22': (160.0, 8.0, 0, 'top'),
    'U3': (167.0, 43.0, 0, 'top'),
    'U4': (172.0, 43.0, 0, 'top'),
    'U5': (177.0, 42.0, 0, 'top'),
    'U6': (172.0, 35.0, 0, 'top'),
    # ─── universal I/O: expanders, DAC, ADC, drivers, switches ───
    'U107': (120.0, 44.0, 0, 'bottom'),
    'U108': (140.0, 44.0, 0, 'bottom'),
    'U100': (152.0, 44.0, 0, 'top'),
    'U101': (158.0, 34.0, 0, 'top'),
    'U102': (116.0, 34.0, 0, 'top'),
    'U103': (136.0, 34.0, 0, 'top'),
    'U104': (126.0, 42.0, 0, 'top'),
    'U105': (146.0, 34.0, 0, 'top'),
    'U106': (130.0, 34.0, 0, 'bottom'),
    # ─── precision ports, expansion, display, ambient ───
    'U109': (197.0, 73.0, 0, 'top'),
    'J35': (87.5, 31.0, 0, 'top'),
    'J34': (95.0, 42.0, 0, 'top'),
    'J40': (87.0, 52.0, 0, 'top'),
    'U111': (85.0, 42.0, 0, 'top'),
    'U110': (77.0, 41.0, 0, 'top'),
    'J15': (56.0, 18.0, 0, 'top'),
    'U52': (56.0, 8.0, 0, 'bottom'),
    'F2': (62.0, 6.0, 0, 'top'),
    'U50': (183.0, 58.0, 0, 'top'),
}

# Isolated island: J12 pins 1 and 2 (pin 3 is board ground, above it), J11, U18
# and U17's isolated half
base.ISO_RECTS = [Rect(0.0, 23.8, 34.0, 59.6)]
base.ISO_OUTLINE = [(0.0, 23.8), (34.0, 23.8), (34.0, 59.6), (0.0, 59.6)]

# ─── floorplan: section -> rectangles (sheet -> section is rev 5's) ───
rev5.SECTIONS = {
    'POWER INPUT': [Rect(0, 61.6, 22.3, 84), Rect(22.3, 50, 62, 69.5), Rect(196, 7, 212, 24)],
    'WATER COOLING & RELAY': [Rect(22.3, 69.5, 79, 84), Rect(62, 50, 79, 69.5)],
    'CRYOCOOLER SENSORS': [Rect(79, 57, 102, 84)],
    'MCU & USB': [Rect(70, 0, 140, 26), Rect(102, 26, 110, 84)],
    'LOGIC RAILS': [Rect(44, 26, 72, 50)],
    'EXPANSION': [Rect(72, 26, 102, 57)],
    'UNIVERSAL I/O': [Rect(110, 26, 163, 50)],
    'PRESSURE PORTS': [Rect(163, 50, 176, 84), Rect(176, 68, 190, 84)],
    # beside the connector wall, clear of the rails: the wall is the low side when
    # the housing hangs upright, so warm air rises away from the sensor
    'AMBIENT': [Rect(176, 50, 190, 68)],
    'PRECISION PORTS': [Rect(190, 41, 212, 84), Rect(184, 41, 190, 50)],
    'SIGNAL GENERATOR': [Rect(163, 26, 184, 50), Rect(184, 26, 191, 41)],
    'AMP CONTROL': [Rect(191, 24, 212, 41)],
    # shares the strip beside the island with POWER INPUT: U17 straddles the barrier there
    'AMP CURRENT (ISOLATED)': [Rect(0, 7.4, 40, 61.5)],
    'DISPLAY': [Rect(44, 0, 70, 26), Rect(0, 0, 44, 7.4)],
    'RAILS ±15V': [Rect(140, 0, 180, 26)],
}
# each universal I/O channel has the strip behind its own connector
CHANNEL_CONNECTORS = {f'IO Channel {n}': f'J{35 + n}' for n in range(1, 5)}
CHANNEL_DEPTH = 34.0
rev5.PRINTED_SECTIONS = {
    **rev5.SECTIONS,
    'I/O CHANNELS': [Rect(IO_START, HEIGHT - CHANNEL_DEPTH, IO_START + 4 * IO_PITCH, HEIGHT)],
}


def section_rects(layout, parts, ref):
    """Rectangles a part has to stay inside, or None if it may go anywhere."""
    sheet = parts[ref]['sheet']
    connector = CHANNEL_CONNECTORS.get(sheet)
    if connector is not None and connector in layout.spots:
        start = layout.courtyard(connector).min_x
        return [Rect(start, HEIGHT - CHANNEL_DEPTH, start + IO_PITCH, HEIGHT)]
    return rev5.SECTIONS.get(rev5.SECTION_OF_SHEET.get(sheet))


rev5.section_rects = section_rects


class Layout(rev5.SectionLayout):
    """rev 5's section layout; the in-board connectors keep a normal part gap."""

    def margin(self, ref, side):
        if ref in INBOARD_CONNECTORS:
            return base.Layout.margin(self, ref, side)
        return super().margin(ref, side)


rev5.SectionLayout = Layout

rev5_current_paths = rev5.current_paths
AMP_NETS = {'Net-(J12-Pin_1)', 'Net-(J11-Pin_1)'}
AMP_DROP = 2.35


def current_paths(pad):
    """rev 5's locked copper. The amplifier path is as on rev 5. The 12 V path is
    rev 5's seen upside down (its connectors are on the bottom wall here), with
    the +12V end redrawn: fan and pump sit side by side on the front, so one
    front track feeds both pin 2s."""
    def flip(x, y):
        return x, HEIGHT - y

    def flipped_pad(ref, number):
        return flip(*pad(ref, number))

    amp_tracks, amp_vias = rev5_current_paths(pad)
    tracks = []
    for net, layer, points, width in amp_tracks:
        if net not in AMP_NETS:
            continue
        if layer == 'B' and len(points) == 4:
            # the diagonal to J11 starts lower than on rev 5, clear of J12's fixing hole
            points = [points[0], *[(x, y + AMP_DROP) for x, y in points[1:3]], points[3]]
        tracks.append((net, layer, points, width))
    vias = [via for via in amp_vias if via[0] in AMP_NETS]
    input_tracks, input_vias = rev5_current_paths(flipped_pad)
    skipped = AMP_NETS | {'+12V'}
    input_tracks = [track for track in input_tracks if track[0] not in skipped]
    input_vias = [via for via in input_vias if via[0] not in skipped]
    shunt_out, fan, pump = flipped_pad('R78', '1'), flipped_pad('J3', '2'), flipped_pad('J4', '2')
    clear, level = shunt_out[0] + 2.6, fan[1] + 3.9
    input_tracks.append(('+12V', 'F', [shunt_out, (clear, shunt_out[1]), (clear, level)], 1.6))
    input_tracks.append(('+12V', 'F', [(min(fan[0], clear), level), (max(pump[0], clear), level)], 1.6))
    for pin in (fan, pump):
        input_tracks.append(('+12V', 'F', [(pin[0], level), pin], 1.1))
    tracks += [(net, layer, [flip(*point) for point in points], width)
               for net, layer, points, width in input_tracks]
    return tracks, vias + [(net, *flip(x, y)) for net, x, y in input_vias]


rev5.current_paths = current_paths


def tie_plane_pads(board):
    """rev 5's plane ties, kept on their own side of the isolation barrier: an
    ISO_GND tie stays inside the island, every other tie outside its keep-out band."""
    import cs_decoder_finish as ties

    def in_island(point, grow):
        x, y = pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)
        return any(rect.min_x - grow <= x <= rect.max_x + grow and rect.min_y - grow <= y <= rect.max_y + grow
                   for rect in base.ISO_RECTS)

    areas = [zone.Outline() for zone in board.Zones() if zone.GetIsRuleArea()]
    edge = rev5.MM(0.6)
    current = {'net': ''}

    def allowed(point):
        if not (edge <= point.x <= rev5.MM(WIDTH) - edge and edge <= point.y <= rev5.MM(HEIGHT) - edge):
            return False
        if any(area.Contains(point, -1, rev5.MM(0.4)) for area in areas):
            return False
        if current['net'] == 'ISO_GND':
            return in_island(point, -0.6)
        return not in_island(point, base.ISO_BAND + 0.4)

    via_clear, path_clear = ties.via_clear, ties.path_clear
    ties.via_clear = lambda copper, position: allowed(position) and via_clear(copper, position)
    ties.path_clear = lambda copper, points, layer: all(map(allowed, points)) and path_clear(copper, points, layer)
    try:
        for footprint in sorted(board.GetFootprints(), key=lambda part: part.GetReference()):
            ref = footprint.GetReference()
            for pad in footprint.Pads():
                if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or pad.GetNetname() not in rev5.PLANE_NETS:
                    continue
                if pad.GetNumber() in base.GROUND_VIA_PADS.get(ref, ()):
                    continue
                current['net'] = pad.GetNetname()
                try:
                    ties.tie_pad_to_ground(board, ref, pad.GetNumber())
                except RuntimeError as error:
                    print('not tied', ref, pad.GetNumber(), error)
    finally:
        ties.via_clear, ties.path_clear = via_clear, path_clear


rev5.tie_plane_pads = tie_plane_pads

# Freerouting necks tracks down to 0.11 mm at fine pads unless told not to
base.ROUTER_ARGS = [*base.ROUTER_ARGS, '--router.automatic_neckdown=false']
base_run_freerouting = base.run_freerouting
TIE_VIA = (0.45, 0.2)


def run_freerouting(board, work_dir, rounds):
    """Freerouting, then the plane-tie vias get their 0.2 mm drill back: the session
    import gives every via its net class's drill (0.3 mm on the supply classes)."""
    base_run_freerouting(board, work_dir, rounds)
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T and track.GetWidth(pcbnew.F_Cu) == rev5.MM(TIE_VIA[0]):
            track.SetDrill(rev5.MM(TIE_VIA[1]))


base.run_freerouting = run_freerouting

base.LABEL_FUNCTIONS = {**{ref: name for ref, name in base.LABEL_FUNCTIONS.items() if ref != 'J21'},
                        'J40': 'AUX'}
# connector -> [(body sides to try: N/S/E/W on the board, {pad: name})]
rev5.PIN_NAMES = {
    **{ref: rows for ref, rows in rev5.PIN_NAMES.items() if ref != 'J21'},
    # on the bottom wall here: names above the pins
    **{ref: [('N', rev5.PIN_NAMES[ref][0][1])] for ref in ('J3', 'J4', 'J5', 'J6', 'J10', 'J13')},
    'J15': [('NS', {'1': 'GND', '2': '12V', '3': 'CANH', '4': 'CANL', '5': 'BTN', '6': 'RST'})],
    'J34': [('NS', {'1': 'A', '2': 'B', '3': 'GND', '4': 'NC'})],
    'J35': [('NS', {'1': '3V3', '2': '5V', '3': 'SCK', '4': 'MOSI', '5': 'MISO', '6': 'INT',
                    '7': 'CSA', '8': 'CSB', '9': 'GND', '10': 'GND'})],
    'J40': [('NS', {'1': '5V', '2': '3V3', '3': 'IO11', '4': 'IO13', '5': 'GND'})],
}
rev5.REV_MARK = 'REV6'
# the board has room: a row of pin names may start further from its connector
rev5.PIN_NAME_REACH = 6.0

# Net classes the router sees. Rev 5 gave it 0.25 mm tracks and 0.6 / 0.3 mm vias and
# was then repaired by hand at 0.15 mm and 0.45 / 0.2 mm; rev 6 routes at those from
# the start. Clearance stays 0.15 mm (JLCPCB 4-layer minimum 0.09 mm).
SIGNAL_CLASSES = {'Default', 'Analog', 'Control', 'Ground', 'SPI'}
SIGNAL_RULES = {'clearance': 0.15, 'track_width': 0.15, 'via_diameter': 0.45, 'via_drill': 0.2}
# 12 V distribution beyond the locked 10 A copper (I/O supplies, buck inputs, display):
# 0.5 mm, about 1.5 A on 1 oz. At 0.8 mm the router left these nets open, and rev 5
# ended with 0.15 mm feeds.
CLASS_RULES = {'Power12V': {'track_width': 0.5}}


def apply_rules():
    """Writes SIGNAL_RULES into the signal net classes of cryocooler.kicad_pro."""
    path = Path(__file__).resolve().parent.parent / 'cryocooler.kicad_pro'
    project = json.loads(path.read_text())
    changed = []
    for item in project['net_settings']['classes']:
        if item['name'] in SIGNAL_CLASSES:
            item.update(SIGNAL_RULES)
            changed.append(item['name'])
        if item['name'] in CLASS_RULES:
            item.update(CLASS_RULES[item['name']])
            changed.append(item['name'])
    path.write_text(json.dumps(project, indent=2) + '\n')
    print('rules set on:', ' '.join(sorted(changed)))


if __name__ == '__main__':
    if sys.argv[1:] == ['rules']:
        apply_rules()
    else:
        rev5.main()
