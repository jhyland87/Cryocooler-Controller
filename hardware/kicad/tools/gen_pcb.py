"""Generates cryocooler.kicad_pcb from the schematic netlist.

Run with KiCad's bundled python (it provides `pcbnew`):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
    \
        hardware/kicad/tools/gen_pcb.py

Stage 1 (this file): board outline, footprints with nets, anchor placement from
PLACEMENT, automatic placement of every resistor/capacitor next to the pin it
serves, keep-outs and mounting holes.
"""

import collections
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

from pcbnetlist import KICAD_DIR, load_netlist
import export_fab
import pcbfloorplan
import pcbmodels
from pcbplace import Occupancy, Rect, placed_rect, ring_offsets, rotate_point

# Phoenix Contact UCS 145-125 housing PCB (drawing 2203447): 120 x 100 mm,
# 31 mm clearance above the board and 10 mm below
BOARD_WIDTH = 120.0
BOARD_HEIGHT = 100.0
EDGE_MARGIN = 0.5
PASSIVE_GAP = 0.3
# rev 1 reserved a label pocket beside every part before placing the next;
# labels are now fitted afterwards and the ones that do not fit stay hidden
RESERVE_LABEL_POCKETS = False
# JLCPCB needs 0.2 mm drills on 0.45 mm pads or larger, else a paid 4-wire test.
VIA_IN_PAD_DIAMETER = 0.45
STOCK_FOOTPRINTS = Path(
    '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
)

GROUND_NETS = {'GND', 'ISO_GND'}
# switched supply nets (one jumper each) -> module box they belong to
SWITCHED_NETS = {
    '+3V3_SG': 'SIGNAL GENERATOR',
    '+5V_PS15': 'RAILS ±15V',
    '+5V_ISO': 'AMP CURRENT (ISOLATED)',
    '+3V3_COOL': 'WATER COOLING',
    '+3V3_CH': 'COLD HEAD TEMP',
}
# sections too full for their test points: these sit in the nearest free
# spot of the roomy power box instead
TEST_POINTS_OUTSIDE = set()
# how far (mm, from the pad it serves) a test point may go before the retry
# pass
TEST_POINT_REACH = 8.0
# the fit check allows a little more: a crowded test point may land in the
# retry pass, still inside its section
TEST_POINT_CHECK_REACH = 12.0
TEST_POINT_OVERFLOW = 'POWER INPUT & RAILS'
POWER_NETS = GROUND_NETS | set(SWITCHED_NETS) | {
    '+3V3',
    '+5V',
    '+12V',
    'VIN',
    'VSW',
    'ISO_3V3',
    '+15V',
    '-15V',
    '+16V5',
    '-16V5',
    'USB_VBUS',
    '+5V_OR',
}

# ref -> (x, y, rotation[, side]); everything that is not a plain R/C is
# placed here. Side defaults to 'top'. Connectors face the housing walls
# (mating faces at or just past the board edge).
PLACEMENT = {
    # ─── top wall: display FPC (cable side to the edge), ESP32 over the
    # routed antenna notch; right wall: USB-C ───
    'J15': (42.0, 5.0, 180),
    'U1': (84.0, 12.75, 0),
    'SW1': (66.5, 11.0, 0),
    'SW2': (66.5, 18.5, 0),
    'J1': (54.3, 3.675, 180),
    # ─── left wall: amplifier output and cryocooler (isolated section, the
    # barrier at x = 25.25 under U17 / PS1), 12 V in, amplifier REM / signal ───
    'J11': (11.25, 21.0, 270),
    'J12': (11.25, 33.5, 270),
    'U18': (18.7, 14.0, 0),
    'U17': (26.0, 25.3, 180),
    'PS1': (26.0, 33.2, 0),
    'J2': (0.0, 85.5, 270),
    'J9': (0.0, 63.0, 270),
    'J8': (6.35, 72.4, 270),
    'Q5': (20.0, 69.9, 0),
    'Q6': (16.0, 73.4, 0),
    'Q21': (18.0, 79.5, 0),
    # ─── top: 12 V input path, 5 V buck and 3.3 V LDO, power switch ───
    'F1': (19.0, 47.5, 90),
    'D1': (19.0, 56.0, 0),
    'C54': (28.0, 48.5, 90),
    'Q1': (46.0, 65.0, 0),
    'C55': (39.0, 77.0, 0),
    'L1': (27.5, 66.5, 0),
    'U15': (27.5, 72.5, 0),
    'U16': (27.5, 80.0, 0),
    'U28': (27.0, 77.5, 0, 'bottom'),
    'U29': (27.0, 82.0, 0, 'bottom'),
    # ─── top: signal generator (the +-15 V stage sits beside it) ───
    'U3': (38.0, 18.5, 0),
    'U4': (46.5, 18.5, 0),
    'U7': (55.0, 19.5, 90),
    'U5': (38.0, 31.0, 90),
    'U6': (46.5, 31.0, 90),
    'U9': (55.0, 31.0, 90),
    'U8': (40.0, 42.0, 0),
    # ─── top: +-15 V rails. LT8582 upright: SW1 (pins 1, 24) north to D5 /
    # L2, SW2 (pins 12, 13) south to L3; the LT3097 west of it, its outputs
    # facing the signal generator ───
    'U20': (70.0, 54.0, 0),
    'D5': (66.0, 48.7, 0),
    'L2': (72.5, 44.5, 270),
    'L3': (70.9, 62.3, 180),
    'D6': (63.5, 62.3, 0),
    'U21': (80.0, 55.0, 180),
    # ─── top: indicators ───
    'D22': (68.0, 35.0, 0),
    'U24': (76.0, 35.0, 0),
    # ─── right wall: IMU RJ45, PT1000 header, pump; bottom wall: panel
    # button, relay out, NTC, flow, fan ───
    'J14': (116.65, 31.3, 90),
    'J10': (114.8, 52.0, 90),
    'J4': (92.2, 86.6, 0),
    'SW3': (27.0, 95.8, 0),
    'J7': (34.8, 86.7, 0),
    'J13': (40.6, 86.7, 0),
    'J6': (60.6, 86.7, 0),
    'J5': (68.5, 86.6, 0),
    'J3': (80.5, 86.6, 0),
    # ─── bottom ───
    'U27': (32.0, 6.5, 0, 'bottom'),
    'Q25': (50.9, 10.65, 0, 'bottom'),
    'U2': (54.3, 4.0, 0, 'bottom'),
    'U14': (106.0, 52.0, 90, 'bottom'),
    'U23': (29.0, 52.0, 0, 'bottom'),
    'U11': (10.5, 88.5, 0, 'bottom'),
    'U13': (16.5, 88.5, 0, 'bottom'),
    'U12': (10.5, 92.5, 0, 'bottom'),
    'Q2': (16.5, 93.0, 0, 'bottom'),
    'Q3': (12.0, 96.5, 0, 'bottom'),
    'Q4': (17.0, 97.3, 0, 'bottom'),
    'Q7': (47.5, 85.5, 0, 'bottom'),
    'Q8': (52.8, 85.5, 0, 'bottom'),
    'D23': (50.0, 89.5, 0, 'bottom'),
    'U25': (80.0, 78.0, 0, 'bottom'),
    'U26': (88.0, 78.0, 0, 'bottom'),
    'U10': (96.0, 82.5, 0, 'bottom'),
}

# Parts whose passives stay on their own side (switching loops and the LDO
# outputs keep off vias); every other passive goes on the bottom.
SAME_SIDE_TARGETS = {'U15', 'U16', 'U20', 'U21'}

# ISO_GND island (top-left corner, left of the barrier at x = 25.25 that U17
# and PS1 straddle); keep-out bands keep GND copper away from it. J12 pin 3
# (the cryocooler's protective ground, on board GND) sits just below it.
ISO_REGION = Rect(0.0, 0.0, 25.25, 40.5)
ISO_NETS = {'ISO_GND', 'ISO_3V3'}

# Same-net pad chains on 0.5 mm pitch parts, joined by locked F.Cu stubs before
# routing (the 0.3 mm power tracks do not fit between the pads): consecutive
# pads of each chain, plus the exposed-pad links.
PAD_BRIDGES = {
    'U21': (
        ('1', '2', '3'),  # INP, INP, ENP/UVP
        ('6', '7', '8'),  # INN, INN, ENN/UVN
        ('7', '24'),  # INN to its exposed pad
        ('14', '15', '16'),  # OUTSN, OUTN, OUTN
        ('20', '21', '22'),  # OUTSP, OUTP, OUTP
        ('19', '23'),  # GND to its exposed pad
    ),
}
BRIDGE_WIDTH = 0.2

# GND pads that get a locked via-in-pad before routing (fine-pitch LGA)
FINE_PITCH_GROUND_PADS = {
    'U23': {'7'},
    'U4': {'4', '9'},
    'U21': {'5', '11', '13', '19'},
    'U20': {'25'},
    'U25': {'13'},
    'U11': {'4'},
}
# signal pads of the 0.5 mm pitch regulators boxed in by their own passives:
# a locked via-in-pad lets them escape on the inner layers
SIGNAL_VIA_PADS = {
    'U20': {'3', '8', '10', '18', '23'},  # PGP, VC2, PGN, CLKOUT1 pair
}
# GND pads of placed passives that are boxed in by their own signal track and
# would otherwise get a via-in-pad after routing, on top of an inner track
LATE_GROUND_PADS = {}
MIN_TRACK_WIDTH = 0.15

# Anchors for ground test points (ground nets have no natural neighbour pad):
# the k-th TP on GND sits beside the k-th entry; ISO_GND beside the isolator.
GND_TP_ANCHORS = [('U25', '13'), ('U27', '6'), ('U10', '13')]
ISO_GND_TP_ANCHOR = ('U17', '9')
ISO_BAND = 1.5
# ESP32 antenna: the board is cut away under it (routed notch in the top
# edge) and the strips beside the notch, within the module's 15 mm keep-out,
# carry no copper and no parts.
ANTENNA_NOTCH = Rect(74.5, 0.0, 93.5, 6.0)
ANTENNA_KEEPOUTS = [Rect(60.0, 0.0, 74.5, 6.75), Rect(93.5, 0.0, 108.0, 6.75)]
# housing restricted areas (no parts, no copper, no solder mask): a 4.45 mm
# corner square joined with a 6 mm ring round each mounting hole; CORNER is
# the square that holds both, for part placement
CORNER = 7.4
CORNER_SQUARE = 4.45
HOLE_RING_RADIUS = 3.0
CORNER_KEEPOUTS = [
    Rect(0.0, 0.0, CORNER, CORNER),
    Rect(BOARD_WIDTH - CORNER, 0.0, BOARD_WIDTH, CORNER),
    Rect(0.0, BOARD_HEIGHT - CORNER, CORNER, BOARD_HEIGHT),
    Rect(BOARD_WIDTH - CORNER, BOARD_HEIGHT - CORNER, BOARD_WIDTH, BOARD_HEIGHT),
]
FREEROUTING_JAR = Path(sys.argv[2]) if len(sys.argv) > 2 else None
# a stuck modal dialog in the Freerouting window ends the run after this long
FREEROUTING_TIMEOUT = 7200


def freerouting_env():
    """Freerouting shows its window unless FREEROUTING_HIDE=1. The window can
    pop modal error dialogs; dismiss them or hide it for unattended runs."""
    if os.environ.get('FREEROUTING_HIDE') == '1':
        return {**os.environ, 'FREEROUTING__GUI__ENABLED': 'false'}
    return dict(os.environ)
MAX_PASSES = '20'
JAVA = (
    '/Library/Java/JavaVirtualMachines/temurin-25.jdk/Contents/Home/bin/java'
)

# Local rect overrides (the ESP32 courtyard includes a large antenna keep-out).
# ─── silkscreen ───
# Labels beside the buttons and indicator LEDs (ref -> text), placed on the
# first free side of the part.
SILK_LABELS = {
    'SW1': 'RESET',
    'SW2': 'BOOT',
    'SW3': 'POWER',
    'J1': 'USB',
    'J2': '12V IN',
    'J3': 'FAN',
    'J4': 'PUMP',
    'J5': 'FLOW',
    'J6': 'NTC',
    'J7': 'PANEL',
    'J8': 'AMP REM',
    'J9': 'AMP SIGNAL',
    'J10': 'PT1000',
    'J11': 'FROM AMP',
    'J12': 'TO CRYOCOOLER',
    'J13': 'RELAY 12V OUT',
    'J14': 'IMU',
    'J15': 'DISPLAY',
    'D2': 'POWER',
    'D3': 'AMP REM',
    'D7': 'ALERT',
    'D9': '3V3',
    'D10': 'READY',
    'D8': 'FAULT',
    'D22': 'STATUS',
    'D4': 'COMP RLY',
    'D11': '5V',
    'D14': 'ISO 3V3',
    'D20': '+15V PG',
    'D21': '-15V PG',
}
# Connector pin labels (pin 1 first): what each terminal is for, printed
# beside the pads on the side facing the board interior.
PIN_LABELS = {
    'J2': ['+12V', 'GND'],
    'J3': ['GND', '+12V', 'TACH', 'PWM'],
    'J4': ['GND', '+12V', 'TACH', 'PWM'],
    'J5': ['GND', '+12V', 'TACH'],
    'J6': ['NTC', 'GND'],
    'J7': ['BTN', 'GND'],
    'J8': ['REM', 'GND'],
    'J9': ['GND', 'SIG'],  # pads 1 (sleeve), 2 (tip)
    'J10': ['F+', 'S+', 'S-', 'F-'],
    'J11': ['+', '-'],
    'J12': ['+', '-', 'GND'],
    'J13': ['12V', 'GND'],
    # J14 (RJ45) has none: 1.0 mm text cannot fit its 1.02 mm pin pitch; its
    # pinout is in the schematic
}
# what each supply jumper switches (JP1 ... JP5, in schematic order)
JUMPER_LABELS = ('SG 3V3', '±15V EN', 'ISO PS', 'WATER EN', 'HEAD EN')
SILK_LABELS.update(
    {f'JP{index}': text for index, text in enumerate(JUMPER_LABELS, start=1)}
)
# JLCPCB minimums: 1.0 mm text height, 0.15 mm silk line / stroke
SILK_MIN_TEXT = 1.0
SILK_MIN_LINE = 0.15
# DRC floor: JLCPCB high-precision silkscreen (0.8 mm text, 0.1 mm stroke)
SILK_DRC_MIN_TEXT = 0.8
SILK_DRC_MIN_LINE = 0.1
# letters narrower than this drop under JLCPCB's 0.15 mm letter gap
SILK_WIDTH_RATIO = 0.9
SILK_TEXT_SIZE = SILK_MIN_TEXT
TP_TEXT_SIZE = SILK_MIN_TEXT
# silk keeps JLCPCB's 0.15 mm off pads, plus 0.05 mm for the mask margin
SILK_PAD_CLEARANCE = 0.2
# part numbers printed under the IC bodies as a placement aid: font sizes to
# try (largest first) and the refs that get one (modules and oversize parts skip)
IC_LABEL_SIZES = (SILK_MIN_TEXT,)
IC_LABEL_SKIP = ('U1',)
IC_LABEL_STEP = 0.25
# shorter text for parts whose full value will not fit under the body
IC_LABEL_TEXT = {
    'U3': 'SG-8002CA',
    'U7': 'MCP4921',
    'U18': 'ACS37800',
    'PS1': 'MIE1W0505',
}
SILK_TEXT_THICKNESS = SILK_MIN_LINE
# pin-1 dot radius, and the parts that get one (ICs, modules, connectors)
PIN1_DOT_RADIUS = 0.3
PIN1_PREFIXES = ('U', 'J', 'PS')
LOGO_FILE = KICAD_DIR / 'artwork' / 'cooler_trace.geojson'
LOGO_SOURCE_SIZE = (1658.0, 648.0)  # trace bitmap size in pixels
LOGO_CENTER = (65.0, 51.0)
LOGO_WIDTH = 80.0
TITLE_TEXT = 'STI Hybrid-98 Cryocooler Control Unit'
# board name printed in the board ID block
BOARD_NAME = 'Cryocooler Control Unit'
# development stage printed in the board ID block (rev 1 carried ALPHA)
BOARD_STAGE = 'BETA'
# solder mask colour: set in the board stackup, which the renders use; order
# the board in black
MASK_COLOUR = 'Black'
# preferred spot of the board ID block (back silkscreen, board coordinates),
# the same spot as on the earlier 145-125 layout
BOARD_ID_SPOT = (19.0, 2.4)
ALPHA_TEXT = 'ALPHA'

# 111.6 x 91.6 mm hole pattern, centred
HOLES = [(4.2, 4.2), (115.8, 4.2), (4.2, 95.8), (115.8, 95.8)]
LOCAL_RECT_OVERRIDES = {
    'RF_Module:ESP32-S3-WROOM-2': Rect(-9.2, -12.9, 9.2, 13.2),
    # the stock test point courtyard is 3.7 mm square around a 1.5 mm pad
    'TestPoint:TestPoint_Pad_D1.5mm': Rect(-1.15, -1.15, 1.15, 1.15),
}


# The stock ESP32 courtyard includes the antenna clearance zone; with the
# routed notch that zone has no board under it, so the courtyard is cut back
# to the module body (local coordinates).
BODY_COURTYARDS = {
    'RF_Module:ESP32-S3-WROOM-2': Rect(-9.25, -12.95, 9.25, 13.0),
}


def set_courtyard(footprint, rect):
    """Replaces a footprint's front courtyard with one rectangle."""
    for item in list(footprint.GraphicalItems()):
        if item.GetLayer() == pcbnew.F_CrtYd:
            footprint.Remove(item)
    shape = pcbnew.PCB_SHAPE(footprint)
    shape.SetShape(pcbnew.SHAPE_T_RECT)
    shape.SetLayer(pcbnew.F_CrtYd)
    shape.SetWidth(to_internal(0.05))
    shape.SetStart(pcbnew.VECTOR2I(to_internal(rect.min_x), to_internal(rect.min_y)))
    shape.SetEnd(pcbnew.VECTOR2I(to_internal(rect.max_x), to_internal(rect.max_y)))
    footprint.Add(shape)


def silk_text_size(height):
    """Silk text size in KiCad units for a text height in mm."""
    return pcbnew.VECTOR2I(to_internal(height * SILK_WIDTH_RATIO), to_internal(height))


def widen_silk(footprint):
    """Raises footprint silkscreen strokes to JLCPCB's 0.15 mm minimum (the
    stock KiCad libraries draw 0.12 mm); filled shapes are left alone.
    """
    for item in footprint.GraphicalItems():
        if item.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        if item.Type() == pcbnew.PCB_TEXT_T:
            # e.g. a pin-1 marker digit: up to the 1.0 mm minimum
            if item.GetTextHeight() < to_internal(SILK_MIN_TEXT):
                item.SetTextSize(silk_text_size(SILK_MIN_TEXT))
            if item.GetTextThickness() < to_internal(SILK_MIN_LINE):
                item.SetTextThickness(to_internal(SILK_MIN_LINE))
            continue
        if item.Type() == pcbnew.PCB_SHAPE_T and not item.IsAnyFill():
            if item.GetWidth() < to_internal(SILK_MIN_LINE):
                item.SetWidth(to_internal(SILK_MIN_LINE))


def link_to_symbol(footprint, part):
    """Stores the schematic symbol link (sheet path + symbol uuid) so KiCad's
    Update PCB from Schematic matches the footprint instead of adding a copy.
    """
    footprint.SetPath(pcbnew.KIID_PATH(part['path']))
    footprint.SetSheetname(part['sheet_names'])
    library, name = part['footprint'].split(':')
    footprint.SetFPID(pcbnew.LIB_ID(library, name))
    # match the symbol's attributes (the stock test points exclude
    # themselves from the BOM)
    footprint.SetExcludedFromBOM(part.get('exclude_from_bom', False))
    for field, value in part.get('fields', {}).items():
        footprint.SetField(field, value)
        footprint.GetField(field).SetVisible(False)


def stackup_block(copper_layers=4):
    """The 1.6 mm stackup (4 or 2 copper layers) with the board colours
    (MASK_COLOUR, white silk); pcbnew's Python API cannot set stackup colours.
    """
    def layer(name, kind, extra=''):
        return f'\t\t\t(layer "{name}"\n\t\t\t\t(type "{kind}"){extra}\n\t\t\t)\n'

    copper = '\n\t\t\t\t(thickness 0.035)'
    mask = f'\n\t\t\t\t(color "{MASK_COLOUR}")\n\t\t\t\t(thickness 0.01)'
    silk = '\n\t\t\t\t(color "White")'

    def dielectric(index, kind, thickness=0.48):
        return (
            f'\n\t\t\t\t(thickness {thickness})\n\t\t\t\t(material "FR4")'
            f'\n\t\t\t\t(epsilon_r 4.5)\n\t\t\t\t(loss_tangent 0.02)'
        ), f'dielectric {index}', kind

    body = layer('F.SilkS', 'Top Silk Screen', silk)
    body += layer('F.Paste', 'Top Solder Paste')
    body += layer('F.Mask', 'Top Solder Mask', mask)
    body += layer('F.Cu', 'copper', copper)
    inner_layers = (('In1.Cu', 'core'), ('In2.Cu', 'prepreg')) if copper_layers == 4 else ()
    for index, (inner, kind) in enumerate(inner_layers, start=1):
        extra, name, kind = dielectric(index, kind)
        body += layer(name, kind, extra)
        body += layer(inner, 'copper', copper)
    if copper_layers == 4:
        extra, name, kind = dielectric(3, 'core')
    else:
        extra, name, kind = dielectric(1, 'core', 1.51)
    body += layer(name, kind, extra)
    body += layer('B.Cu', 'copper', copper)
    body += layer('B.Mask', 'Bottom Solder Mask', mask)
    body += layer('B.Paste', 'Bottom Solder Paste')
    body += layer('B.SilkS', 'Bottom Silk Screen', silk)
    return (
        '\t\t(stackup\n' + body
        + '\t\t\t(copper_finish "None")\n\t\t\t(dielectric_constraints no)\n\t\t)\n'
    )


def save_board(board, path=None):
    """Saves the board, then writes the stackup (mask colour) into it."""
    path = Path(path or KICAD_DIR / 'cryocooler.kicad_pcb')
    pcbnew.SaveBoard(str(path), board)
    text = path.read_text()
    text = re.sub(r'\t\t\(stackup\n.*?\n\t\t\)\n', '', text, count=1, flags=re.S)
    text = text.replace('\t(setup\n', '\t(setup\n' + stackup_block(board.GetCopperLayerCount()), 1)
    path.write_text(text)


def covers(segment, candidate, tolerance=0.01):
    """True if an axis-aligned segment already covers the candidate one
    (same line, candidate's span inside it).
    """
    (ax, ay), (bx, by) = segment
    (cx, cy), (dx, dy) = candidate
    if abs(ay - by) < tolerance and abs(cy - dy) < tolerance and abs(ay - cy) < tolerance:
        low, high = sorted((ax, bx))
        return low - tolerance <= min(cx, dx) and max(cx, dx) <= high + tolerance
    if abs(ax - bx) < tolerance and abs(cx - dx) < tolerance and abs(ax - cx) < tolerance:
        low, high = sorted((ay, by))
        return low - tolerance <= min(cy, dy) and max(cy, dy) <= high + tolerance
    return False


def has_own_pin1_mark(footprint, pad_x, pad_y, reach=3.0):
    """True if the footprint's own silkscreen already marks pin 1 near the
    pin: a small filled shape (the stock triangle or dot) or a small closed
    outline of short lines (a drawn triangle).
    """
    segments = []
    for item in footprint.GraphicalItems():
        if item.Type() != pcbnew.PCB_SHAPE_T:
            continue
        if item.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        box = item.GetBoundingBox()
        centre = box.GetCenter()
        if math.dist((centre.x / 1e6, centre.y / 1e6), (pad_x, pad_y)) > reach:
            continue
        if max(box.GetWidth(), box.GetHeight()) / 1e6 > 1.5:
            continue
        if item.GetShape() in (pcbnew.SHAPE_T_POLY, pcbnew.SHAPE_T_CIRCLE):
            return True
        if item.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            segments.append(tuple(
                (round(end.x / 1e4), round(end.y / 1e4))
                for end in (item.GetStart(), item.GetEnd())
            ))
    # a closed loop of three or more short lines among them
    while segments:
        loop = [segments.pop()]
        grown = True
        while grown:
            grown = False
            corners = {end for segment in loop for end in segment}
            for segment in list(segments):
                if segment[0] in corners or segment[1] in corners:
                    loop.append(segment)
                    segments.remove(segment)
                    grown = True
        ends = collections.Counter(end for segment in loop for end in segment)
        if len(loop) >= 3 and all(count == 2 for count in ends.values()):
            return True
    return False


def silk_layer(side):
    """Silkscreen layer of a board side."""
    return pcbnew.B_SilkS if side == 'bottom' else pcbnew.F_SilkS


def restricted_outline(hole_x, hole_y, steps=32):
    """Polygon (mm points) of one restricted corner: the corner square joined
    with the ring round the hole, as drawn in the housing's PCB2D drawing.
    """
    corner_x = 0.0 if hole_x < BOARD_WIDTH / 2 else BOARD_WIDTH
    corner_y = 0.0 if hole_y < BOARD_HEIGHT / 2 else BOARD_HEIGHT
    sign_x = 1 if corner_x == 0.0 else -1
    sign_y = 1 if corner_y == 0.0 else -1
    # walk the circle from the edge parallel to x round to the edge parallel
    # to y, on the side away from the corner, then close along the square
    points = [(corner_x, corner_y), (corner_x + sign_x * CORNER_SQUARE, corner_y)]
    for step in range(steps + 1):
        angle = -math.pi / 2 + math.pi * 1.5 * step / steps
        offset_x = HOLE_RING_RADIUS * math.cos(angle)
        offset_y = HOLE_RING_RADIUS * math.sin(angle)
        points.append((hole_x + sign_x * offset_x, hole_y + sign_y * offset_y))
    points.append((corner_x, corner_y + sign_y * CORNER_SQUARE))
    return points


def footprint_path(footprint_id):
    library, name = footprint_id.split(':')
    if library == 'cryocooler':
        return str(KICAD_DIR / 'lib' / 'cryocooler.pretty'), name
    return str(STOCK_FOOTPRINTS / f'{library}.pretty'), name


def to_internal(value_mm):
    return pcbnew.FromMM(value_mm)


def short_net(name):
    return name.split('/')[-1]


class PcbBuilder:
    """Builds the board: footprints, nets, placement."""

    def __init__(self):
        self.parts, self.nets = load_netlist()
        self.board = pcbnew.BOARD()
        self.board.SetCopperLayerCount(4)
        self.footprints = {}
        self.local_rects = {}
        self.pad_local = {}
        self.centers = {}
        self.pad_net = collections.defaultdict(dict)
        self.net_pads = collections.defaultdict(list)
        self.occupancy = Occupancy(
            Rect(0, 0, BOARD_WIDTH, BOARD_HEIGHT), EDGE_MARGIN, PASSIVE_GAP
        )
        self.occupancy.keepouts.extend([*ANTENNA_KEEPOUTS, *CORNER_KEEPOUTS])
        self.side = {}
        self.forced_side = {}
        self.pin_label_side = {}
        self.net_items = {}
        self.module = {}
        self.bumps = {}
        self.box_lines = {}
        self.text_dims = {}
        self.pad_boxes = {}
        self.pockets = {}
        self.pin_pockets = {}
        self.require_pockets = True
        self.early_labels = {}
        self.label_pockets = {}
        for name, nodes in self.nets.items():
            for ref, pad in nodes:
                self.pad_net[ref][pad] = short_net(name)
                self.net_pads[short_net(name)].append((ref, pad))

    def load_footprints(self):
        for ref, part in self.parts.items():
            path, name = footprint_path(part['footprint'])
            footprint = pcbnew.FootprintLoad(path, name)
            if footprint is None:
                raise RuntimeError(f'missing footprint {part["footprint"]}')
            pcbmodels.attach_missing_models(footprint)
            widen_silk(footprint)
            if part['footprint'] in BODY_COURTYARDS:
                set_courtyard(footprint, BODY_COURTYARDS[part['footprint']])
                # its built-in antenna keep-out assumes an un-notched edge;
                # the board-level ANTENNA_KEEPOUTS cover the notch sides instead
                for zone in list(footprint.Zones()):
                    footprint.Remove(zone)
            footprint.SetReference(ref)
            link_to_symbol(footprint, part)
            pcbmodels.apply_connector_colour(footprint)
            footprint.SetValue(part['value'])
            footprint.Reference().SetTextSize(silk_text_size(SILK_MIN_TEXT))
            footprint.Reference().SetTextThickness(to_internal(0.15))
            if ref.startswith('TP'):
                # test points print what they probe (their value is the net
                # name) instead of TP#
                footprint.Value().SetTextSize(silk_text_size(TP_TEXT_SIZE))
                footprint.Value().SetTextThickness(to_internal(SILK_MIN_LINE))
            text_box = self.display_text(footprint, ref).GetBoundingBox()
            self.text_dims[ref] = (
                text_box.GetWidth() / 1e6 + 0.2,
                text_box.GetHeight() / 1e6 + 0.2,
            )
            footprint.Value().SetVisible(ref.startswith('TP'))
            footprint.Reference().SetVisible(not ref.startswith('TP'))
            self.footprints[ref] = footprint
            # on the board from the start: flipping a footprint that has no
            # parent board crashes pcbnew
            self.board.Add(footprint)
            courtyard = footprint.GetCourtyard(pcbnew.F_CrtYd).BBox()
            local = Rect(
                courtyard.GetX() / 1e6,
                courtyard.GetY() / 1e6,
                (courtyard.GetX() + courtyard.GetWidth()) / 1e6,
                (courtyard.GetY() + courtyard.GetHeight()) / 1e6,
            )
            self.local_rects[ref] = LOCAL_RECT_OVERRIDES.get(
                part['footprint'], local
            )
            self.pad_local[ref] = {}
            for pad in footprint.Pads():
                position = pad.GetPosition()
                self.pad_local[ref].setdefault(pad.GetNumber(), []).append(
                    (position.x / 1e6, position.y / 1e6)
                )
                net_name = self.pad_net[ref].get(pad.GetNumber())
                if net_name is not None:
                    pad.SetNet(self.net_item(self.full_net(net_name)))

    @staticmethod
    def display_text(footprint, ref):
        """The text printed for a part: the value (net name) for a test
        point, else the reference.
        """
        return footprint.Value() if ref.startswith('TP') else footprint.Reference()

    def full_net(self, short):
        for name in self.nets:
            if short_net(name) == short:
                return name
        raise KeyError(short)

    def net_item(self, name):
        item = self.net_items.get(name)
        if item is None:
            item = self.board.FindNet(name)
        if item is None:
            item = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(item)
            self.net_items[name] = item
        return item

    def pad_position(self, ref, pad, index=0):
        center_x, center_y, angle = self.centers[ref]
        local_x, local_y = self.pad_local[ref][pad][index]
        if self.side.get(ref) == 'bottom':
            local_y = -local_y  # KiCad's left-right flip mirrors y
        rotated_x, rotated_y = rotate_point(local_x, local_y, angle)
        return center_x + rotated_x, center_y + rotated_y

    def hole_rects(self, ref):
        """Plated and plain holes of a part: they block both sides."""
        footprint = self.footprints[ref]
        rects = []
        for pad in footprint.Pads():
            drill = pad.GetDrillSizeX() / 1e6
            if drill <= 0:
                continue  # SMD pad: its own side only
            size = max(pad.GetSizeX(), pad.GetSizeY()) / 1e6
            if drill < 0.5:
                size = drill + 0.3  # thermal via: its ring only
            half = max(size, drill) / 2 + 0.25
            position = pad.GetPosition()
            rects.append(
                Rect(
                    position.x / 1e6 - half,
                    position.y / 1e6 - half,
                    position.x / 1e6 + half,
                    position.y / 1e6 + half,
                )
            )
        return rects

    def place(self, ref, center_x, center_y, angle, side=None):
        side = side or self.side.get(ref, 'top')
        self.side[ref] = side
        footprint = self.footprints[ref]
        footprint.SetPosition(
            pcbnew.VECTOR2I(to_internal(center_x), to_internal(center_y))
        )
        if (side == 'bottom') != footprint.IsFlipped():
            footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        footprint.SetOrientationDegrees(angle)
        if ref.startswith('TP'):
            footprint.Value().SetLayer(silk_layer(side))
            footprint.Value().SetMirrored(side == 'bottom')
        self.centers[ref] = (center_x, center_y, angle)
        self.occupancy.add(
            ref,
            placed_rect(
                self.local_rects[ref], center_x, center_y, angle, side == 'bottom'
            ),
            side,
        )
        # pins and holes poke through: they block the other side too
        for index, rect in enumerate(self.hole_rects(ref)):
            self.occupancy.add(f'hole_{ref}_{index}', rect, 'both')

    def is_passive(self, ref):
        """R, C, test points, the Debug sheet's LEDs and everything on the
        Power Good sheet are placed beside the pad they serve.
        """
        if ref in PLACEMENT:
            return False
        return (
            ref[0] in 'RC'
            or ref.startswith(('TP', 'JP'))
            or 'LED' in self.parts[ref]['footprint']
            or self.parts[ref]['sheet'] == 'Power Good'
        )

    def iso_side_passives(self):
        """Passives of the Amp Current sheet that sit on the isolated side:
        those touching ISO_GND / ISO_3V3, plus passives chained to them
        through signal nets (the ACS37800 divider).
        """
        if getattr(self, '_iso_refs', None) is not None:
            return self._iso_refs
        candidates = [
            ref
            for ref in self.parts
            if ref[0] in 'RC' and self.parts[ref]['sheet'] == 'Amp Current'
        ]

        def nets_of(ref):
            return {self.pad_net[ref].get(pad) for pad in self.pad_local[ref]}

        iso = {ref for ref in candidates if nets_of(ref) & ISO_NETS}
        changed = True
        while changed:
            changed = False
            signal_nets = set()
            for ref in iso:
                signal_nets |= nets_of(ref) - POWER_NETS - {None}
            for ref in candidates:
                if ref not in iso and nets_of(ref) & signal_nets:
                    iso.add(ref)
                    changed = True
        self._iso_refs = iso
        return iso

    def is_iso_side(self, ref):
        """True for parts on the isolated (ISO_GND) side of the barrier."""
        if ref in self.iso_side_passives():
            return True
        if ref[0] in 'RC' and self.parts[ref]['sheet'] == 'Amp Current':
            return False
        if not (ref.startswith('TP') or self.parts[ref]['sheet'] == 'Debug'):
            return False
        return any(
            self.pad_net[ref].get(pad) in ISO_NETS
            for pad in self.pad_local[ref]
        )

    def part_module(self, ref, side=None):
        """Module region key of a part on `side` (default: its own side): its
        sheet's module, else the module of the switched supply net it sits on
        (jumpers and their LEDs), else None.
        """
        side = side or self.side.get(ref, 'top')
        module = pcbfloorplan.module_of_sheet(self.parts[ref]['sheet'])
        if module is None:
            for pad in self.pad_local[ref]:
                module = SWITCHED_NETS.get(self.pad_net[ref].get(pad))
                if module is not None:
                    break
        if module is None:
            return None
        return pcbfloorplan.module_key(module, side)

    def is_led(self, ref):
        return 'LED' in self.parts[ref]['footprint']

    def passive_side(self, ref, target_ref):
        """LEDs stay on top where they can be seen; test points and the
        passives of SAME_SIDE_TARGETS sit on their part's side; every other
        passive goes on the bottom, unless its module has no bottom region.
        """
        if ref in self.forced_side:
            return self.forced_side[ref]
        if self.is_led(ref):
            return 'top'
        if ref.startswith('TP') or target_ref in SAME_SIDE_TARGETS:
            return self.side.get(target_ref, 'top')
        key = self.part_module(ref, 'bottom')
        if key is None:
            target_key = self.module.get(target_ref)
            if target_key is not None:
                key = pcbfloorplan.module_key(
                    pcbfloorplan.split_key(target_key)[0], 'bottom'
                )
        if key is not None and key not in pcbfloorplan.MODULE_REGIONS:
            return 'top'
        return 'bottom'

    def place_anchors(self):
        for ref, (center_x, center_y, angle, *side) in PLACEMENT.items():
            if ref not in self.footprints:
                raise KeyError(f'PLACEMENT names unknown ref {ref}')
            self.place(ref, center_x, center_y, angle, side[0] if side else 'top')
            self.module[ref] = self.part_module(ref)
        for index, (hole_x, hole_y) in enumerate(HOLES):
            self.occupancy.add(
                f'hole{index}',
                Rect(hole_x - 3.4, hole_y - 3.4, hole_x + 3.4, hole_y + 3.4),
                'both',
            )

    def add_track(self, net, layer, points, width, locked=True):
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(self.board)
            track.SetLayer(layer)
            track.SetWidth(to_internal(width))
            track.SetStart(
                pcbnew.VECTOR2I(to_internal(start[0]), to_internal(start[1]))
            )
            track.SetEnd(
                pcbnew.VECTOR2I(to_internal(end[0]), to_internal(end[1]))
            )
            track.SetNet(self.net_item(self.full_net(net)))
            track.SetLocked(locked)
            self.board.Add(track)

    def pre_route_current_path(self, width=2.0):
        """Wide locked F.Cu traces for the amplifier current path J11 -> U18
        pins 1-4 / 5-8 -> J12. The connectors sit on the left wall level with
        U18's current pins: each trace runs across from the connector's pin 1
        to the pin column, then along its four pads.
        """
        for connector, net, pins, end_cap in (
            ('J11', 'Net-(J11-Pin_1)', ('1', '2', '3', '4'), 'down'),
            ('J12', 'Net-(J12-Pin_1)', ('5', '6', '7', '8'), 'up'),
        ):
            start_x, start_y = self.pad_position(connector, '1')
            pad_points = [self.pad_position('U18', pin) for pin in pins]
            column_x = sum(point[0] for point in pad_points) / len(pad_points)
            top = min(point[1] for point in pad_points)
            bottom = max(point[1] for point in pad_points)
            end_y = bottom - 0.8 if end_cap == 'down' else top + 0.8
            self.add_track(
                net,
                pcbnew.F_Cu,
                [(start_x, start_y), (column_x, start_y), (column_x, end_y)],
                width,
            )
            margin = width / 2 + 0.6
            self.occupancy.add(
                f'{connector}_current_a',
                Rect(
                    min(start_x, column_x) - margin,
                    start_y - margin,
                    max(start_x, column_x) + margin,
                    start_y + margin,
                ),
                'top',
            )
            self.occupancy.add(
                f'{connector}_current_b',
                Rect(
                    column_x - margin,
                    min(start_y, end_y) - margin,
                    column_x + margin,
                    max(start_y, end_y) + margin,
                ),
                'top',
            )

    def add_outline_and_keepouts(self):
        # rectangle with the routed antenna notch cut into the top edge
        notch = ANTENNA_NOTCH
        corners = [
            (0, 0),
            (notch.min_x, 0),
            (notch.min_x, notch.max_y),
            (notch.max_x, notch.max_y),
            (notch.max_x, 0),
            (BOARD_WIDTH, 0),
            (BOARD_WIDTH, BOARD_HEIGHT),
            (0, BOARD_HEIGHT),
        ]
        for index, (start_x, start_y) in enumerate(corners):
            end_x, end_y = corners[(index + 1) % len(corners)]
            segment = pcbnew.PCB_SHAPE(self.board)
            segment.SetShape(pcbnew.SHAPE_T_SEGMENT)
            segment.SetLayer(pcbnew.Edge_Cuts)
            segment.SetWidth(to_internal(0.1))
            segment.SetStart(
                pcbnew.VECTOR2I(to_internal(start_x), to_internal(start_y))
            )
            segment.SetEnd(
                pcbnew.VECTOR2I(to_internal(end_x), to_internal(end_y))
            )
            self.board.Add(segment)
        # the housing's restricted corners: mask opened on both sides, kept
        # free of copper
        for hole_x, hole_y in HOLES:
            points = restricted_outline(hole_x, hole_y)
            self.add_keepout(None, points=points)
            for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
                polygon = pcbnew.SHAPE_POLY_SET()
                outline = polygon.NewOutline()
                for point_x, point_y in points:
                    polygon.Append(
                        pcbnew.VECTOR2I(to_internal(point_x), to_internal(point_y)),
                        outline,
                    )
                shape = pcbnew.PCB_SHAPE(self.board)
                shape.SetShape(pcbnew.SHAPE_T_POLY)
                shape.SetLayer(layer)
                shape.SetFilled(True)
                shape.SetWidth(0)
                shape.SetPolyShape(polygon)
                self.board.Add(shape)

    # ─── passive placement ───

    def candidate_targets(self, ref, pad):
        """Placed pads (other than ref's) that this passive pin should sit next
        to.
        """
        net = self.pad_net[ref].get(pad)
        if ref.startswith('JP') and net not in SWITCHED_NETS:
            return []
        if ref.startswith('TP') and net in GROUND_NETS:
            return [self.ground_tp_anchor(ref, net)]
        if net is None or net in GROUND_NETS:
            return []
        if ref.startswith('TP'):
            owners = self.test_point_owners(ref, net)
            if owners:
                return [
                    (other_ref, other_pad)
                    for other_ref, other_pad in self.net_pads[net]
                    if other_ref in owners
                ]
        sheet = self.parts[ref]['sheet']
        found = []
        for other_ref, other_pad in self.net_pads[net]:
            if other_ref == ref or other_ref not in self.centers:
                continue
            is_passive = self.is_passive(other_ref)
            if net in POWER_NETS and (
                is_passive or self.parts[other_ref]['sheet'] != sheet
            ):
                continue
            found.append((other_ref, other_pad))
        if not found and net in POWER_NETS:
            found = [
                (r, p)
                for r, p in self.net_pads[net]
                if r != ref and r in self.centers and not self.is_passive(r)
            ]
        return found

    def test_point_owners(self, ref, net):
        """Placed parts a test point on `net` can be for: the ICs and
        connectors on the net (the MCU only if nothing else), those on the
        test point's own sheet first.
        """
        placed = [
            other
            for other, _ in self.net_pads.get(net, [])
            if other != ref and other in self.centers
            and not other.startswith('TP') and not self.is_passive(other)
        ]
        # the MCU reaches every GPIO net: a test point there is for the load
        placed = [other for other in placed if other != 'U1'] or placed
        sheet = self.parts[ref]['sheet']
        return [o for o in placed if self.parts[o]['sheet'] == sheet] or placed

    def ground_tp_anchor(self, ref, net):
        if net == 'ISO_GND':
            return ISO_GND_TP_ANCHOR
        ground_tps = sorted(
            (
                r
                for r in self.parts
                if r.startswith('TP')
                and self.pad_net[r].get('1') == 'GND'
            ),
            key=lambda r: int(r[2:]),
        )
        return GND_TP_ANCHORS[ground_tps.index(ref) % len(GND_TP_ANCHORS)]

    # ─── label pockets ───

    def find_pocket(self, part_rect, module, width, height, gap=0.15):
        """Free spot for a label box of the given size right beside a part
        rectangle (inside the module box); returns (x, y, turned, rect) or
        None. Labels beside the long sides are tried upright, then turned.
        """
        center_x = (part_rect.min_x + part_rect.max_x) / 2
        center_y = (part_rect.min_y + part_rect.max_y) / 2
        obstacles = self.pocket_obstacles()
        for turned in (False, True):
            box_w, box_h = (height, width) if turned else (width, height)
            for shift in (0.0, 0.6, -0.6, 1.2, -1.2, 1.8, -1.8):
                for spot_x, spot_y in (
                    (center_x + shift, part_rect.min_y - gap - box_h / 2),
                    (center_x + shift, part_rect.max_y + gap + box_h / 2),
                    (part_rect.min_x - gap - box_w / 2, center_y + shift),
                    (part_rect.max_x + gap + box_w / 2, center_y + shift),
                ):
                    rect = Rect(
                        spot_x - box_w / 2,
                        spot_y - box_h / 2,
                        spot_x + box_w / 2,
                        spot_y + box_h / 2,
                    )
                    if module and not pcbfloorplan.text_inside(module, rect):
                        continue
                    if not rect.inside(self.occupancy.board_rect):
                        continue
                    if any(rect.overlaps(k) for k in self.occupancy.keepouts):
                        continue
                    if any(rect.overlaps(other) for other in obstacles):
                        continue
                    return spot_x, spot_y, turned, rect
        return None

    def pocket_obstacles(self):
        """Boxes a label pocket must keep off: other pockets, silk, holes,
        the candidate being tested, and for placed parts only their pad
        boxes (the courtyard margin around them is free for text).
        """
        boxes = []
        for name, rect in self.occupancy.on_side():
            if name.startswith('txt_pin'):
                boxes.append(rect.inflated(0.25))
            elif name.startswith(('txt_', 'silk_', 'hole', 'candidate')):
                boxes.append(rect.inflated(0.05))
            elif name in self.centers:
                pad_box = self.pad_boxes.get(name)
                if pad_box is None:
                    boxes_for_part = [
                        pad.GetBoundingBox()
                        for pad in self.footprints[name].Pads()
                    ]
                    pad_box = Rect(
                        min(b.GetLeft() for b in boxes_for_part) / 1e6,
                        min(b.GetTop() for b in boxes_for_part) / 1e6,
                        max(b.GetRight() for b in boxes_for_part) / 1e6,
                        max(b.GetBottom() for b in boxes_for_part) / 1e6,
                    )
                    self.pad_boxes[name] = pad_box
                boxes.append(pad_box.inflated(0.1))
            else:
                boxes.append(rect)
        return boxes

    def label_size(self, ref):
        """Box size of the part label (SILK_LABELS) for a ref, or None."""
        if ref not in SILK_LABELS:
            return None
        box = self.text_rect(SILK_LABELS[ref], 0, 0, SILK_TEXT_SIZE)
        return box.max_x - box.min_x, box.max_y - box.min_y

    def reserve_pockets(self, ref, part_rect, module):
        """Reserves room for the reference text (and the part label, if the
        part has one) beside a part; returns False if either has no room.
        """
        taken = []
        ok = True
        for kind, size in (
            ('ref', self.text_dims[ref]),
            ('label', self.label_size(ref)),
        ):
            if size is None:
                continue
            pocket = self.find_pocket(part_rect, module, *size)
            if pocket is None:
                ok = False
                break
            spot_x, spot_y, turned, rect = pocket
            name = f'txt_{kind}_{ref}'
            self.occupancy.add(name, rect)
            taken.append((name, kind, (spot_x, spot_y, turned)))
        if not ok:
            for name, _, _ in taken:
                del self.occupancy.rects[name]
            return False
        for name, kind, spot in taken:
            (self.pockets if kind == 'ref' else self.label_pockets)[ref] = spot
        return True

    def pin_label_boxes(self, ref, side, body=None):
        """Label boxes for a connector's pins on one side of its body:
        [(text, centre x, centre y, turned, rect)], or None if any is off the
        board.
        """
        footprint = self.footprints[ref]
        pads = {
            int(pad.GetNumber()): (
                pad.GetPosition().x / 1e6,
                pad.GetPosition().y / 1e6,
            )
            for pad in footprint.Pads()
            if pad.GetNumber().isdigit()
        }
        body = body or self.occupancy.rects[ref]
        column = side in ('left', 'right')
        boxes = []
        for number, text in enumerate(PIN_LABELS[ref], start=1):
            pad_x, pad_y = pads[number]
            base = self.text_rect(text, 0, 0, SILK_TEXT_SIZE)
            length, thickness = 2 * base.max_x, 2 * base.max_y
            if column:
                width, height = length, thickness
                center_y = pad_y
                center_x = (
                    body.max_x + 0.2 + width / 2
                    if side == 'right'
                    else body.min_x - 0.2 - width / 2
                )
            else:
                width, height = thickness, length
                center_x = pad_x
                center_y = (
                    body.max_y + 0.2 + height / 2
                    if side == 'down'
                    else body.min_y - 0.2 - height / 2
                )
            rect = Rect(
                center_x - width / 2,
                center_y - height / 2,
                center_x + width / 2,
                center_y + height / 2,
            )
            boxes.append((text, center_x, center_y, not column, rect))
        return boxes

    def reserve_pin_labels(self, ref):
        """Reserves a label beside every pad of a connector, on the side
        facing the board interior if it is free, else the other sides.
        """
        body = self.occupancy.rects[ref]
        centre_x = (body.min_x + body.max_x) / 2
        centre_y = (body.min_y + body.max_y) / 2
        pads = [
            pad.GetPosition()
            for pad in self.footprints[ref].Pads()
            if pad.GetNumber().isdigit()
        ]
        spread_x = max(p.x for p in pads) - min(p.x for p in pads)
        spread_y = max(p.y for p in pads) - min(p.y for p in pads)
        if spread_x < spread_y:
            sides = ['right', 'left'] if centre_x < BOARD_WIDTH / 2 else ['left', 'right']
        else:
            sides = ['up', 'down'] if centre_y > BOARD_HEIGHT / 2 else ['down', 'up']
        module = self.module_of_ref(ref)
        for side in sides:
            boxes = self.pin_label_boxes(ref, side)
            # pin labels also keep off other parts' bodies (print on bare board)
            obstacles = self.pocket_obstacles() + [
                rect
                for name, rect in self.occupancy.on_side()
                if name in self.centers and name != ref
            ]
            if all(
                rect.inside(self.occupancy.board_rect)
                and not any(rect.overlaps(k) for k in self.occupancy.keepouts)
                and not any(rect.overlaps(o) for o in obstacles)
                for *_, rect in boxes
            ):
                for index, (_, _, _, _, rect) in enumerate(boxes):
                    self.occupancy.add(f'txt_pin_{ref}_{index}', rect)
                self.pin_pockets[ref] = boxes
                return True
        # no room on top: print them on the back, beside the through pins
        if self.side.get(ref) == 'top' and self.hole_rects(ref):
            self.occupancy.side = 'bottom'
            # on the back only the pins show: measure from the pad span
            holes = self.hole_rects(ref)
            pins = Rect(
                min(r.min_x for r in holes), min(r.min_y for r in holes),
                max(r.max_x for r in holes), max(r.max_y for r in holes),
            )
            for side in sides:
                boxes = self.pin_label_boxes(ref, side, pins)
                obstacles = self.pocket_obstacles() + [
                    rect
                    for name, rect in self.occupancy.on_side('bottom')
                    if name in self.centers and name != ref
                ]
                if all(
                    rect.inside(self.occupancy.board_rect)
                    and not any(rect.overlaps(k) for k in self.occupancy.keepouts)
                    and not any(rect.overlaps(o) for o in obstacles)
                    for *_, rect in boxes
                ):
                    for index, (_, _, _, _, rect) in enumerate(boxes):
                        self.occupancy.add(f'txt_pin_{ref}_{index}', rect, 'bottom')
                    self.pin_pockets[ref] = boxes
                    self.pin_label_side[ref] = 'bottom'
                    self.occupancy.side = 'top'
                    return True
            self.occupancy.side = 'top'
        blockers = sorted({
            name
            for side in sides
            for *_, rect in self.pin_label_boxes(ref, side)
            for name, other in self.occupancy.on_side('top')
            if rect.overlaps(other) and name != ref
        })
        print('no room for the pin labels of', ref, 'blocked by', blockers[:8])
        return False

    def add_pin_labels(self):
        """Prints the connector pin labels reserved above."""
        for ref, labels in self.pin_pockets.items():
            side = self.pin_label_side.get(ref, 'top')
            self.occupancy.side = side
            for index, (text, spot_x, spot_y, turned, rect) in enumerate(labels):
                item = self.add_text(
                    text,
                    spot_x,
                    spot_y,
                    SILK_TEXT_SIZE,
                    layer=silk_layer(side),
                    mirrored=side == 'bottom',
                    thickness=SILK_TEXT_THICKNESS,
                )
                if turned:
                    item.SetTextAngleDegrees(90)
                self.occupancy.add(f'silk_pin_{ref}_{index}', rect)

    def reserve_module_labels(self):
        """Picks each module box's title spot now, so parts placed later keep
        clear of it.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 2.4) for hole_x, hole_y in HOLES]
        self.early_labels = {}
        for module in pcbfloorplan.MODULE_REGIONS:
            spot = self.module_label_spot(module, board_rect, holes)
            self.early_labels[module] = spot
            if spot is not None:
                text, left_x, line_y = spot
                width = pcbfloorplan.label_width(text)
                self.occupancy.add(
                    f'silk_label_{module}',
                    Rect(left_x, line_y - 0.5, left_x + width, line_y + 0.5),
                    pcbfloorplan.split_key(module)[1],
                )

    def reserve_anchor_pockets(self):
        """Reserves label room beside every placed (non-passive) part before
        the passives crowd in.
        """
        for ref in PIN_LABELS:
            self.occupancy.side = self.side[ref]
            self.reserve_pin_labels(ref)
        missing = []
        for ref in PLACEMENT if RESERVE_LABEL_POCKETS else ():
            self.occupancy.side = self.side[ref]
            module = self.module.get(ref)
            part = self.occupancy.rects[ref]
            if not self.reserve_pockets(ref, part, module):
                missing.append(ref)
        print('no label room beside:', missing)

    def place_passives(self):
        crowd = collections.Counter()
        pending = [ref for ref in self.parts if self.is_passive(ref)]
        offsets = ring_offsets(60.0, 0.5)
        unplaced = []
        while pending:
            progressed = False
            # signal-net passives first, then pure decoupling
            # the Power Good sheet goes last so it only takes what is left
            pending.sort(
                key=lambda r: (
                    self.parts[r]['sheet'] == 'Power Good',
                    self.is_decoupling(r),
                    int(r.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
                )
            )
            for ref in list(pending):
                choice = self.pick_target(ref, crowd)
                if choice is None:
                    continue
                pad_index, target = choice
                if not self.place_near(ref, pad_index, target, offsets):
                    unplaced.append(ref)
                else:
                    crowd[target] += 1
                pending.remove(ref)
                progressed = True
                break
            if not progressed:
                unplaced.extend(pending)
                break
        # second pass for the parts that found no spot with room for their
        # labels: place them anyway, their labels are searched for afterwards
        retry, unplaced = unplaced, []
        self.require_pockets = False
        for ref in retry:
            choice = self.pick_target(ref, crowd)
            if choice is not None and self.place_near(
                ref, choice[0], choice[1], offsets
            ):
                crowd[choice[1]] += 1
                continue
            # last resort: the other side of the board, over / under its target
            if choice is not None and not self.is_led(ref) and not ref.startswith('TP'):
                first = self.passive_side(ref, choice[1][0])
                self.forced_side[ref] = 'top' if first == 'bottom' else 'bottom'
                if self.place_near(ref, choice[0], choice[1], offsets):
                    crowd[choice[1]] += 1
                    continue
                del self.forced_side[ref]
            unplaced.append(ref)
        self.require_pockets = True
        return unplaced

    def is_decoupling(self, ref):
        nets = [self.pad_net[ref].get(pad) for pad in self.pad_local[ref]]
        return all(net in POWER_NETS for net in nets)

    def pick_target(self, ref, crowd):
        """Returns (pad number to bring close, (target ref, target pad)) or
        None if nothing placed yet.
        """
        best = None
        for pad in self.pad_local[ref]:
            targets = self.candidate_targets(ref, pad)
            if not targets:
                continue
            signal = self.pad_net[ref][pad] not in POWER_NETS
            for target in targets:
                crowd_penalty = crowd[target]
                key = (
                    0 if signal else 1,
                    crowd_penalty,
                    self.parts[target[0]]['sheet'] != self.parts[ref]['sheet'],
                )
                if best is None or key < best[0]:
                    best = (key, pad, target)
        if best is None:
            return None
        return best[1], best[2]

    def place_near(self, ref, primary_pad, target, offsets):
        target_x, target_y = self.pad_position(*target)
        other_pad = next(
            (pad for pad in self.pad_local[ref] if pad != primary_pad), None
        )
        other_net = self.pad_net[ref].get(other_pad)
        other_points = []
        if other_net is not None and other_net not in POWER_NETS:
            other_points = [
                self.pad_position(r, p)
                for r, p in self.net_pads[other_net]
                if r != ref and r in self.centers and r != target[0]
            ]
        local_rect = self.local_rects[ref]
        side = self.passive_side(ref, target[0])
        self.side[ref] = side
        # a through-hole passive (test-point loop) must be clear on both sides
        self.occupancy.side = 'both' if self.hole_rects(ref) else side
        # a passive stays in its own module's box; debug parts (no module)
        # join the box of the part they sit beside
        module = self.part_module(ref, side) or (
            self.module.get(target[0])
            and pcbfloorplan.module_key(
                pcbfloorplan.split_key(self.module[target[0]])[0], side
            )
        )
        if ref.startswith('TP') and module in TEST_POINTS_OUTSIDE:
            module = TEST_POINT_OVERFLOW
        if module not in pcbfloorplan.MODULE_REGIONS or self.is_led(ref):
            module = None  # LEDs go wherever the top has room near their driver
        # a test point keeps close to its part until the retry pass (ground
        # loops excepted: any ground will do)
        reach = None
        if (
            ref.startswith('TP')
            and self.require_pockets
            and self.pad_net[ref].get(primary_pad) not in GROUND_NETS
        ):
            reach = TEST_POINT_REACH
        best = None
        for offset_x, offset_y in offsets:
            distance = (offset_x**2 + offset_y**2) ** 0.5
            if best is not None and distance > best[0] + 1.5:
                break
            if reach is not None and distance > reach:
                break
            for angle in (0, 90, 180, 270):
                center_x, center_y = target_x + offset_x, target_y + offset_y
                rect = placed_rect(
                    local_rect, center_x, center_y, angle, side == 'bottom'
                )
                if module and not pcbfloorplan.region_contains(module, rect):
                    continue
                if module is None and self.is_led(ref) and not any(
                    pcbfloorplan.region_contains(key, rect)
                    for key in pcbfloorplan.MODULE_REGIONS
                    if pcbfloorplan.split_key(key)[1] == 'top'
                ):
                    continue  # an LED never straddles a section line
                if not self.occupancy.is_free(rect):
                    continue
                inside_iso = rect.inside(ISO_REGION.inflated(-0.3))
                touches_iso = rect.inflated(ISO_BAND).overlaps(ISO_REGION)
                iso_side = self.is_iso_side(ref)
                if iso_side != inside_iso or (not iso_side and touches_iso):
                    continue
                self.centers[ref] = (center_x, center_y, angle)
                primary = self.pad_position(ref, primary_pad)
                score = (
                    (primary[0] - target_x) ** 2 + (primary[1] - target_y) ** 2
                ) ** 0.5
                if other_points:
                    other = self.pad_position(ref, other_pad)
                    score += 0.2 * min(
                        ((other[0] - x) ** 2 + (other[1] - y) ** 2) ** 0.5
                        for x, y in other_points
                    )
                del self.centers[ref]
                if best is None or score < best[0]:
                    pockets = self.pockets_for(ref, rect, module)
                    if pockets is not None:
                        best = (score, center_x, center_y, angle, pockets)
        if best is None:
            del self.side[ref]
            return False
        self.place(ref, best[1], best[2], best[3], side)
        self.module[ref] = module
        for name, kind, spot, pocket_rect in best[4]:
            self.occupancy.add(name, pocket_rect)
            (self.pockets if kind == 'ref' else self.label_pockets)[ref] = spot
        return True

    def pockets_for(self, ref, rect, module):
        """Pockets for a candidate position of a passive, or None if there is
        no room beside it for its label(s). The candidate itself is held in
        the occupancy while looking so the pockets stay clear of it.
        """
        found = []
        if not RESERVE_LABEL_POCKETS and not ref.startswith('TP'):
            # labels are fitted after placement, where room is left; test
            # points keep a pocket for the net name they print
            return found
        self.occupancy.add('candidate', rect)
        try:
            for kind, size in (
                ('ref', self.text_dims[ref]),
                ('label', self.label_size(ref)),
            ):
                if size is None:
                    continue
                pocket = self.find_pocket(rect, module, *size)
                if pocket is None:
                    if self.require_pockets:
                        return None
                    continue  # second pass: the label is searched for later
                spot_x, spot_y, turned, pocket_rect = pocket
                name = f'txt_{kind}_{ref}'
                found.append(
                    (name, kind, (spot_x, spot_y, turned), pocket_rect)
                )
                self.occupancy.add(name + '_tmp', pocket_rect)
        finally:
            del self.occupancy.rects['candidate']
            for tmp in [n for n in self.occupancy.rects if n.endswith('_tmp')]:
                del self.occupancy.rects[tmp]
        return found

    # ─── rules, zones, routing ───

    def add_net_classes(self):
        settings = self.board.GetDesignSettings()
        # JLCPCB 4-layer / 1 oz limits (pcb-capabilities, design-rules blog),
        # with margin: trace/space >= 0.09 mm, via >= 0.15 / 0.25 mm and
        # 0.1 mm ring, hole to copper 0.2 mm, via hole to hole 0.2 mm, copper
        # to routed edge >= 0.2 mm, silk >= 0.15 mm line / 1.0 mm text and
        # 0.15 mm off pads, mask dam >= 0.1 mm (blue). Pad hole to hole
        # (0.45 mm), PTH ring (0.15 mm) and inner-layer PTH clearance (0.3 mm)
        # are in cryocooler.kicad_dru.
        settings.m_MinClearance = to_internal(0.15)
        settings.m_TrackMinWidth = to_internal(0.15)
        settings.m_ViasMinSize = to_internal(VIA_IN_PAD_DIAMETER)
        settings.m_ViasMinAnnularWidth = to_internal(0.1)
        settings.m_MinThroughDrill = to_internal(0.2)
        settings.m_CopperEdgeClearance = to_internal(0.3)
        settings.m_HoleClearance = to_internal(0.2)
        settings.m_HoleToHoleMin = to_internal(0.2)
        settings.m_SilkClearance = to_internal(0.15)
        settings.m_MinSilkTextHeight = to_internal(SILK_MIN_TEXT)
        settings.m_MinSilkTextThickness = to_internal(SILK_MIN_LINE)
        # apertures closer than this merge in DRC; 0.099 lets a web of exactly
        # JLCPCB's 0.10 mm (PS1's land pattern) pass
        settings.m_SolderMaskMinWidth = to_internal(0.099)
        settings.m_SolderMaskExpansion = 0
        net_settings = settings.m_NetSettings
        default = net_settings.GetDefaultNetclass()
        default.SetClearance(to_internal(0.15))
        default.SetTrackWidth(to_internal(0.25))
        default.SetViaDiameter(to_internal(0.6))
        default.SetViaDrill(to_internal(0.3))
        classes = {
            'Power': (
                0.3,
                0.6,
                0.3,
                [
                    '+3V3',
                    '+5V',
                    '+15V',
                    '-15V',
                    '+16V5',
                    '-16V5',
                    'ISO_3V3',
                    'USB_VBUS',
                    '+5V_OR',
                    '+3V3_SG',
                    '+5V_PS15',
                    '+5V_ISO',
                    '+3V3_COOL',
                    '+3V3_CH',
                ],
            ),
            'Power12V': (
                0.8,
                0.7,
                0.35,
                ['VIN', 'VSW', '+12V', 'Net-(F1-Pad1)'],
            ),
            'Usb': (
                0.2,
                0.6,
                0.3,
                [
                    'Net-(U1-USB_D+)',
                    'Net-(U1-USB_D-)',
                    'Net-(J1-D+-PadA6)',
                    'Net-(J1-D--PadA7)',
                ],
            ),
        }
        for name, (width, via_diameter, via_drill, nets) in classes.items():
            netclass = pcbnew.NETCLASS(name)
            netclass.SetClearance(to_internal(0.15))
            netclass.SetTrackWidth(to_internal(width))
            netclass.SetViaDiameter(to_internal(via_diameter))
            netclass.SetViaDrill(to_internal(via_drill))
            if name == 'Usb':
                netclass.SetDiffPairWidth(to_internal(0.2))
                netclass.SetDiffPairGap(to_internal(0.18))
            net_settings.SetNetclass(name, netclass)
            for net in nets:
                net_settings.SetNetclassPatternAssignment(
                    self.full_net(net), name
                )

    def add_zone(self, net, layer, rect, priority, clearance=0.3):
        zone = pcbnew.ZONE(self.board)
        zone.SetLayer(layer)
        zone.SetNet(self.net_item(self.full_net(net)))
        zone.SetAssignedPriority(priority)
        zone.SetLocalClearance(to_internal(clearance))
        zone.SetMinThickness(to_internal(0.2))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.SetPadConnection(
            pcbnew.ZONE_CONNECTION_FULL
            if net in GROUND_NETS
            else pcbnew.ZONE_CONNECTION_THERMAL
        )
        zone.SetThermalReliefGap(to_internal(0.3))
        zone.SetThermalReliefSpokeWidth(to_internal(0.4))
        self.set_outline(zone, rect)
        self.board.Add(zone)
        return zone

    def set_outline(self, zone, rect):
        outline = zone.Outline()
        outline.NewOutline()
        for corner_x, corner_y in (
            (rect.min_x, rect.min_y),
            (rect.max_x, rect.min_y),
            (rect.max_x, rect.max_y),
            (rect.min_x, rect.max_y),
        ):
            outline.Append(to_internal(corner_x), to_internal(corner_y))

    def add_keepout(self, rect, footprints=False, points=None):
        zone = pcbnew.ZONE(self.board)
        zone.SetIsRuleArea(True)
        zone.SetDoNotAllowZoneFills(True)
        zone.SetDoNotAllowTracks(True)
        zone.SetDoNotAllowVias(True)
        zone.SetDoNotAllowFootprints(footprints)
        zone.SetDoNotAllowPads(False)
        zone.SetLayerSet(pcbnew.LSET.AllCuMask())
        if points is None:
            self.set_outline(zone, rect)
        else:
            outline = zone.Outline()
            outline.NewOutline()
            for point_x, point_y in points:
                outline.Append(to_internal(point_x), to_internal(point_y))
        self.board.Add(zone)

    def add_planes(self):
        board_rect = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT)
        region = ISO_REGION
        # isolation bands on every side of the ISO island that is not a board
        # edge (it sits in the bottom-right corner: left and top bands)
        if region.min_x > 0:
            self.add_keepout(
                Rect(
                    region.min_x - ISO_BAND,
                    region.min_y - ISO_BAND,
                    region.min_x,
                    region.max_y,
                )
            )
        if region.min_y > 0:
            self.add_keepout(
                Rect(region.min_x, region.min_y - ISO_BAND, region.max_x, region.min_y)
            )
        if region.max_x < BOARD_WIDTH:
            self.add_keepout(
                Rect(region.max_x, region.min_y, region.max_x + ISO_BAND, region.max_y)
            )
        if region.max_y < BOARD_HEIGHT:
            self.add_keepout(
                Rect(region.min_x, region.max_y, region.max_x, region.max_y + ISO_BAND)
            )
        for keepout in ANTENNA_KEEPOUTS:
            self.add_keepout(keepout)
        self.add_zone('GND', pcbnew.In1_Cu, board_rect, 1)
        self.add_zone('ISO_GND', pcbnew.In1_Cu, region, 2)

    def add_outer_pours(self):
        """GND / ISO_GND pours on the outer layers, added after routing."""
        board_rect = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT)
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            self.add_zone('GND', layer, board_rect, 1)
            self.add_zone('ISO_GND', layer, ISO_REGION, 2)

    def add_inner_power_planes(self):
        """In2 pours go on after routing so the router can use In2 as a signal
        layer.
        """
        board_rect = Rect(0.0, 0.0, BOARD_WIDTH, BOARD_HEIGHT)
        self.add_zone('+3V3', pcbnew.In2_Cu, board_rect, 1)
        self.add_zone('ISO_GND', pcbnew.In2_Cu, ISO_REGION, 2)

    def add_mounting_holes(self):
        for hole_x, hole_y in HOLES:
            footprint = pcbnew.FootprintLoad(
                str(STOCK_FOOTPRINTS / 'MountingHole.pretty'),
                'MountingHole_3.2mm_M3',
            )
            footprint.SetReference('')
            footprint.Reference().SetVisible(False)
            footprint.SetBoardOnly(True)  # mechanical: not in the schematic
            footprint.Value().SetVisible(False)
            footprint.SetPosition(
                pcbnew.VECTOR2I(to_internal(hole_x), to_internal(hole_y))
            )
            self.board.Add(footprint)

    def fill_zones(self):
        filler = pcbnew.ZONE_FILLER(self.board)
        filler.Fill(self.board.Zones())

    def stitch_ground(self, pitch=4.0, clearance=0.55):
        """Adds GND / ISO_GND stitching vias on a grid wherever the spot is
        clear of other copper.
        """
        self.fill_zones()
        obstacles = []
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                box = pad.GetBoundingBox()
                obstacles.append(
                    (
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                        None,
                    )
                )
        for track in self.board.GetTracks():
            half = track.GetWidth() / 2e6
            if track.Type() == pcbnew.PCB_VIA_T:
                position = track.GetPosition()
                obstacles.append(
                    (
                        position.x / 1e6 - half,
                        position.y / 1e6 - half,
                        position.x / 1e6 + half,
                        position.y / 1e6 + half,
                        None,
                    )
                )
            else:
                start, end = track.GetStart(), track.GetEnd()
                obstacles.append(
                    (
                        min(start.x, end.x) / 1e6 - half,
                        min(start.y, end.y) / 1e6 - half,
                        max(start.x, end.x) / 1e6 + half,
                        max(start.y, end.y) / 1e6 + half,
                        (
                            start.x / 1e6,
                            start.y / 1e6,
                            end.x / 1e6,
                            end.y / 1e6,
                            half,
                        ),
                    )
                )
        zones = {}
        for zone in self.board.Zones():
            if not zone.GetIsRuleArea() and zone.GetNetname() in GROUND_NETS:
                zones[(zone.GetNetname(), zone.GetLayer())] = zone
        via_radius = 0.3
        added = 0
        grid_y = pitch
        while grid_y < BOARD_HEIGHT - 2:
            grid_x = pitch
            while grid_x < BOARD_WIDTH - 2:
                grid_x += pitch
                inside_iso = (
                    ISO_REGION.min_x <= grid_x <= ISO_REGION.max_x
                    and ISO_REGION.min_y <= grid_y <= ISO_REGION.max_y
                )
                net = 'ISO_GND' if inside_iso else 'GND'
                point = pcbnew.VECTOR2I(
                    to_internal(grid_x), to_internal(grid_y)
                )
                needed = (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu)
                if not all(
                    zones.get((net, layer)) is not None
                    and zones[(net, layer)].HitTestFilledArea(layer, point)
                    for layer in needed
                ):
                    continue
                if any(
                    self.point_blocked(
                        grid_x, grid_y, via_radius + clearance, obstacle
                    )
                    for obstacle in obstacles
                ) or self.in_via_keepout(grid_x, grid_y, via_radius + clearance):
                    continue
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(point)
                via.SetWidth(to_internal(0.6))
                via.SetDrill(to_internal(0.3))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(self.full_net(net)))
                self.board.Add(via)
                obstacles.append(
                    (
                        grid_x - via_radius,
                        grid_y - via_radius,
                        grid_x + via_radius,
                        grid_y + via_radius,
                        None,
                    )
                )
                added += 1
            grid_y += pitch
        return added

    def in_via_keepout(self, x, y, margin):
        """True if a via at (x, y) would reach within `margin` mm of a rule
        area that forbids vias (antenna and corner keep-outs).
        """
        point = pcbnew.VECTOR2I(to_internal(x), to_internal(y))
        return any(
            zone.GetIsRuleArea()
            and zone.GetDoNotAllowVias()
            and zone.Outline().Collide(point, to_internal(margin))
            for zone in self.board.Zones()
        )

    def obstacle_list(self, skip_net=None):
        """Pad, via and track boxes; tracks of `skip_net` are left out."""
        obstacles = []
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                box = pad.GetBoundingBox()
                obstacles.append(
                    (
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                        None,
                    )
                )
        for track in self.board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                position = track.GetPosition()
                obstacles.append(
                    (
                        position.x / 1e6 - 0.3,
                        position.y / 1e6 - 0.3,
                        position.x / 1e6 + 0.3,
                        position.y / 1e6 + 0.3,
                        None,
                    )
                )
                continue
            if skip_net is not None and track.GetNetname() == skip_net:
                continue
            half = track.GetWidth() / 2e6
            start, end = track.GetStart(), track.GetEnd()
            obstacles.append(
                (
                    min(start.x, end.x) / 1e6 - half,
                    min(start.y, end.y) / 1e6 - half,
                    max(start.x, end.x) / 1e6 + half,
                    max(start.y, end.y) / 1e6 + half,
                    (
                        start.x / 1e6,
                        start.y / 1e6,
                        end.x / 1e6,
                        end.y / 1e6,
                        half,
                    ),
                )
            )
        return obstacles

    def connect_pour_islands(self, clearance=0.4, via_diameter=0.6):
        """Adds a via to every outer-layer GND/ISO_GND pour fragment that has
        none.
        """
        self.fill_zones()
        added = 0
        for zone in list(self.board.Zones()):
            if zone.GetIsRuleArea() or zone.GetNetname() not in GROUND_NETS:
                continue
            layer = zone.GetLayer()
            if layer not in (pcbnew.F_Cu, pcbnew.B_Cu):
                continue
            filled = zone.GetFilledPolysList(layer)
            vias = [
                t
                for t in self.board.GetTracks()
                if t.Type() == pcbnew.PCB_VIA_T
                and t.GetNetname() == zone.GetNetname()
            ]
            for index in range(filled.OutlineCount()):
                if any(
                    filled.Contains(via.GetPosition(), index) for via in vias
                ):
                    continue
                box = filled.Outline(index).BBox()
                obstacles = self.obstacle_list()
                placed = False
                step = 0.25
                position_y = box.GetTop() / 1e6
                while position_y < box.GetBottom() / 1e6 and not placed:
                    position_x = box.GetLeft() / 1e6
                    while position_x < box.GetRight() / 1e6 and not placed:
                        point = pcbnew.VECTOR2I(
                            to_internal(position_x), to_internal(position_y)
                        )
                        if filled.Contains(point, index) and not any(
                            self.point_blocked(
                                position_x,
                                position_y,
                                via_diameter / 2 + clearance,
                                obstacle,
                            )
                            for obstacle in obstacles
                        ) and not self.in_via_keepout(
                            position_x, position_y, via_diameter / 2 + clearance
                        ):
                            via = pcbnew.PCB_VIA(self.board)
                            via.SetPosition(point)
                            via.SetWidth(to_internal(via_diameter))
                            via.SetDrill(to_internal(0.3))
                            via.SetViaType(pcbnew.VIATYPE_THROUGH)
                            via.SetNet(self.net_item(zone.GetNetname()))
                            self.board.Add(via)
                            added += 1
                            placed = True
                        position_x += step
                    position_y += step
        return added

    def escape_ground_pads(self, via_diameter=0.5, clearance=0.2):
        """Gives each GND/ISO_GND SMD pad that sits in a via-less pour fragment
        its own via + stub.
        """
        self.fill_zones()
        added = 0
        vias = [
            item
            for item in self.board.GetTracks()
            if item.Type() == pcbnew.PCB_VIA_T
            and item.GetNetname() in GROUND_NETS
        ]
        for zone in list(self.board.Zones()):
            if (
                zone.GetIsRuleArea()
                or zone.GetNetname() not in GROUND_NETS
                or zone.GetLayer() != pcbnew.F_Cu
            ):
                continue
            filled = zone.GetFilledPolysList(pcbnew.F_Cu)
            for index in range(filled.OutlineCount()):
                if any(
                    filled.Contains(via.GetPosition(), index) for via in vias
                ):
                    continue
                for footprint in self.board.GetFootprints():
                    for pad in footprint.Pads():
                        if (
                            pad.GetNetname() != zone.GetNetname()
                            or not filled.Contains(pad.GetPosition(), index)
                        ):
                            continue
                        if pad.HasHole():
                            continue
                        added += self.add_escape_via(
                            pad, zone.GetNetname(), via_diameter, clearance
                        )
        added += self.escape_uncovered_ground_pads(
            via_diameter, clearance
        )
        return added

    def other_side_pad_near(self, pad, net, center_x, center_y, reach):
        """True when another net's pad on the other copper layer, or with a
        hole, lies within `reach` of the point (a via-in-pad goes through)."""
        for footprint in self.board.GetFootprints():
            for other in footprint.Pads():
                if other.GetNetname() == net or (other.IsOnLayer(pad.GetLayer()) and not other.HasHole()):
                    continue
                box = other.GetBoundingBox()
                obstacle = (box.GetLeft() / 1e6, box.GetTop() / 1e6,
                            box.GetRight() / 1e6, box.GetBottom() / 1e6, None)
                if self.point_blocked(center_x, center_y, reach, obstacle):
                    return True
        return False

    def escape_uncovered_ground_pads(self, via_diameter, clearance):
        """Escape via for GND/ISO_GND SMD pads that no pour fragment reaches
        (boxed in by tracks), which the fragment scan above never sees.
        """
        added = 0
        zones = {
            zone.GetNetname(): zone
            for zone in self.board.Zones()
            if not zone.GetIsRuleArea()
            and zone.GetNetname() in GROUND_NETS
            and zone.GetLayer() == pcbnew.F_Cu
        }
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                net = pad.GetNetname()
                zone = zones.get(net)
                if (
                    zone is None
                    or pad.HasHole()
                    or not pad.IsOnLayer(pcbnew.F_Cu)
                ):
                    continue
                filled = zone.GetFilledPolysList(pcbnew.F_Cu)
                if any(
                    filled.Contains(pad.GetPosition(), index)
                    for index in range(filled.OutlineCount())
                ):
                    continue
                if any(
                    via.GetNetname() == net
                    and via.GetPosition() == pad.GetPosition()
                    for via in self.board.GetTracks()
                    if via.Type() == pcbnew.PCB_VIA_T
                ):
                    continue
                added += self.add_escape_via(
                    pad, net, via_diameter, clearance
                )
        return added

    def add_escape_via(self, pad, net, via_diameter, clearance):
        center = pad.GetPosition()
        center_x, center_y = center.x / 1e6, center.y / 1e6
        own = pad.GetBoundingBox()
        own_box = (
            own.GetLeft() / 1e6, own.GetTop() / 1e6,
            own.GetRight() / 1e6, own.GetBottom() / 1e6,
        )
        # drop the pad itself and its own net's tracks; other nets' tracks
        # under the pad (on any layer) still block a via
        obstacles = [
            o
            for o in self.obstacle_list(skip_net=net)
            if not (o[4] is None and all(abs(a - b) < 1e-6 for a, b in zip(o[:4], own_box)))
        ]
        for distance in (0.9, 1.1, 1.4, 1.8, 2.4, 3.0, 4.0):
            for direction_x, direction_y in (
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (0.7, 0.7),
                (-0.7, 0.7),
                (0.7, -0.7),
                (-0.7, -0.7),
                (0.92, 0.38),
                (0.38, 0.92),
                (-0.38, 0.92),
                (-0.92, 0.38),
                (0.92, -0.38),
                (0.38, -0.92),
                (-0.38, -0.92),
                (-0.92, -0.38),
            ):
                via_x, via_y = (
                    center_x + distance * direction_x,
                    center_y + distance * direction_y,
                )
                if any(
                    self.point_blocked(
                        via_x, via_y, via_diameter / 2 + clearance, o
                    )
                    for o in obstacles
                ):
                    continue
                # sample the whole stub every ~0.2 mm, starting just off the pad
                stub_length = distance
                count = max(3, int(stub_length / 0.2))
                samples = [
                    (
                        center_x + (via_x - center_x) * step / count,
                        center_y + (via_y - center_y) * step / count,
                    )
                    for step in range(1, count)
                ]
                if any(
                    self.point_blocked(sample_x, sample_y, 0.1 + clearance, o)
                    for sample_x, sample_y in samples
                    for o in obstacles
                ):
                    continue
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(
                    pcbnew.VECTOR2I(to_internal(via_x), to_internal(via_y))
                )
                via.SetWidth(to_internal(via_diameter))
                via.SetDrill(to_internal(0.3))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(net))
                self.board.Add(via)
                self.add_track(
                    net,
                    pcbnew.F_Cu,
                    [(center_x, center_y), (via_x, via_y)],
                    0.2,
                    locked=False,
                )
                return 1
        # no room for a stub: via-in-pad (order filled/capped vias for these,
        # see VIA_IN_PAD_REFS), but only where no other net's track runs
        # under the pad on any layer (the via goes through all of them)
        reach = VIA_IN_PAD_DIAMETER / 2 + clearance
        if any(
            o[4] is not None
            and self.point_blocked(center_x, center_y, reach, o)
            for o in obstacles
        ) or self.other_side_pad_near(pad, net, center_x, center_y, reach):
            print('no escape for', pad.GetParentFootprint().GetReference(), pad.GetNumber())
            return 0
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(center)
        via.SetWidth(to_internal(VIA_IN_PAD_DIAMETER))
        via.SetDrill(to_internal(0.2))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetNet(self.net_item(net))
        self.board.Add(via)
        print(
            'via-in-pad:',
            pad.GetParentFootprint().GetReference(),
            pad.GetNumber(),
        )
        return 1

    @staticmethod
    def point_blocked(point_x, point_y, radius, obstacle):
        min_x, min_y, max_x, max_y, segment = obstacle
        if not (
            min_x - radius <= point_x <= max_x + radius
            and min_y - radius <= point_y <= max_y + radius
        ):
            return False
        if segment is None:
            return True
        start_x, start_y, end_x, end_y, half_width = segment
        delta_x, delta_y = end_x - start_x, end_y - start_y
        length_squared = delta_x * delta_x + delta_y * delta_y
        fraction = (
            0.0
            if length_squared == 0
            else max(
                0.0,
                min(
                    1.0,
                    (
                        (point_x - start_x) * delta_x
                        + (point_y - start_y) * delta_y
                    )
                    / length_squared,
                ),
            )
        )
        nearest_x, nearest_y = (
            start_x + fraction * delta_x,
            start_y + fraction * delta_y,
        )
        return (
            (point_x - nearest_x) ** 2 + (point_y - nearest_y) ** 2
        ) ** 0.5 <= radius + half_width

    def autoroute(self, work_dir, rounds=2):
        """Runs Freerouting; extra rounds re-route whatever the previous round
        left unconnected.
        """
        for round_index in range(rounds):
            dsn = work_dir / f'board{round_index}.dsn'
            ses = work_dir / f'board{round_index}.ses'
            if not pcbnew.ExportSpecctraDSN(self.board, str(dsn)):
                raise RuntimeError('DSN export failed')
            text = dsn.read_text()
            text = text.replace(
                '(layer In1.Cu\n      (type signal)',
                '(layer In1.Cu\n      (type power)',
            )
            dsn.write_text(text)
            subprocess.run(
                [
                    JAVA,
                    '-jar',
                    str(FREEROUTING_JAR),
                    '-de',
                    str(dsn),
                    '-do',
                    str(ses),
                    '-mp',
                    MAX_PASSES,
                    # 0 optimiser threads skips the optimisation stage, which
                    # crashes in v2.4.1 (NullPointerException in
                    # SearchTreeObject.shapeLayer) and never writes the session
                    '-mt',
                    '0',
                ],
                check=False,
                env=freerouting_env(),
                timeout=FREEROUTING_TIMEOUT,
            )
            if not ses.exists() or ses.stat().st_size == 0:
                raise RuntimeError('Freerouting produced no session file')
            if not pcbnew.ImportSpecctraSES(self.board, str(ses)):
                raise RuntimeError('SES import failed')

    def pre_place_pad_bridges(self):
        """Locked 0.2 mm F.Cu stubs between same-net pads of PAD_BRIDGES, so
        the router sees one pad group per net instead of pads it cannot reach.
        """
        for ref, chains in PAD_BRIDGES.items():
            if ref not in self.footprints:
                continue
            for chain in chains:
                for first, second in zip(chain, chain[1:]):
                    net = self.pad_net[ref].get(first)
                    if net is None or net != self.pad_net[ref].get(second):
                        raise RuntimeError(
                            f'{ref} pads {first} and {second} are not on '
                            'one net'
                        )
                    start = self.pad_position(ref, first)
                    end = self.pad_position(ref, second)
                    # exposed pads are large: end the stub 0.5 mm inside them
                    if second in ('23', '24'):
                        end = (start[0] + (end[0] - start[0]) * 0.6, start[1])
                    track = pcbnew.PCB_TRACK(self.board)
                    track.SetStart(
                        pcbnew.VECTOR2I(
                            to_internal(start[0]), to_internal(start[1])
                        )
                    )
                    track.SetEnd(
                        pcbnew.VECTOR2I(
                            to_internal(end[0]), to_internal(end[1])
                        )
                    )
                    track.SetWidth(to_internal(BRIDGE_WIDTH))
                    track.SetLayer(
                        pcbnew.B_Cu if self.side.get(ref) == 'bottom' else pcbnew.F_Cu
                    )
                    track.SetNet(self.net_item(self.full_net(net)))
                    track.SetLocked(True)
                    self.board.Add(track)

    def widen_thin_tracks(self):
        """Freerouting squeezes a few stubs down to 0.125 mm; widen them to
        the board's minimum track width.
        """
        widened = 0
        for track in self.board.GetTracks():
            if (
                track.Type() == pcbnew.PCB_TRACE_T
                and track.GetWidth() < to_internal(MIN_TRACK_WIDTH)
            ):
                track.SetWidth(to_internal(MIN_TRACK_WIDTH))
                widened += 1
        return widened

    def pre_place_fine_pitch_ground_vias(self, table=None):
        """Locked 0.35 mm via-in-pad on the fine-pitch LGA/MSOP ground pads before
        autorouting. The LGA pads are 0.5 mm apart, so a router-placed via
        or an inner-layer track under them cannot be kept clear; 0.35 mm
        keeps 0.15 mm to the neighbouring pads (order filled/capped vias).
        """
        for ref, pads in (FINE_PITCH_GROUND_PADS if table is None else table).items():
            footprint = self.footprints.get(ref)
            if footprint is None:
                continue
            for pad in footprint.Pads():
                if pad.GetNumber() not in pads:
                    continue
                net = self.pad_net[ref].get(pad.GetNumber())
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(
                    pcbnew.VECTOR2I(
                        to_internal(
                            self.pad_position(ref, pad.GetNumber())[0]
                        ),
                        to_internal(
                            self.pad_position(ref, pad.GetNumber())[1]
                        ),
                    )
                )
                via.SetWidth(to_internal(VIA_IN_PAD_DIAMETER))
                via.SetDrill(to_internal(0.2))
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(self.net_item(self.full_net(net)))
                via.SetLocked(True)
                self.board.Add(via)
                # a through via: parts on the other side must keep off it
                via_x, via_y = self.pad_position(ref, pad.GetNumber())
                half = VIA_IN_PAD_DIAMETER / 2 + 0.25
                self.occupancy.add(
                    f'via_{ref}_{pad.GetNumber()}',
                    Rect(via_x - half, via_y - half, via_x + half, via_y + half),
                    'both',
                )


    # ─── silkscreen ───

    def silk_free(self, rect, side='top'):
        """True if a text box fits inside the board, clear of every placed
        footprint, hole and keep-out on that side.
        """
        if not rect.inside(self.occupancy.board_rect):
            return False
        if any(rect.overlaps(keepout) for keepout in self.occupancy.keepouts):
            return False
        if any(
            rect.overlaps(text.inflated(0.1)) for text in self.footprint_texts()
        ):
            return False
        return not any(
            rect.overlaps(other.inflated(0.15))
            for _, other in self.occupancy.on_side(side)
        )

    def board_id_lines(self):
        revision = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=KICAD_DIR,
        ).stdout.strip()
        return (BOARD_NAME, f'{BOARD_STAGE} rev {revision}')

    def reserve_board_id(self):
        """Claims the board ID block's spot on the back before the passives
        are placed, as near BOARD_ID_SPOT as the anchors allow.
        """
        lines = self.board_id_lines()
        half_w = max(len(line) for line in lines) * SILK_MIN_TEXT * 0.45 + 0.4
        half_h = SILK_MIN_TEXT * 1.4
        best = None
        for step_y in range(3, int(BOARD_HEIGHT) - 3):
            for step_x in range(3, int(BOARD_WIDTH) - 3):
                rect = Rect(step_x - half_w, step_y - half_h, step_x + half_w, step_y + half_h)
                if not rect.inside(self.occupancy.board_rect) or any(
                    rect.overlaps(k) for k in self.occupancy.keepouts
                ) or any(
                    rect.overlaps(other.inflated(0.3))
                    for _, other in self.occupancy.on_side('bottom')
                ):
                    continue
                distance = (step_x - BOARD_ID_SPOT[0]) ** 2 + (step_y - BOARD_ID_SPOT[1]) ** 2
                if best is None or distance < best[0]:
                    best = (distance, step_x, step_y, rect)
        if best is None:
            print('board ID: no free spot on the back')
            return
        self.board_id_spot = best[1:]
        self.occupancy.add('silk_board_id', best[3], 'bottom')

    def add_board_id(self):
        """Board name and the git revision the files were generated from, in
        a small block on the back silkscreen nearest BOARD_ID_SPOT (same place
        and format on every revision, per .claude/rules/hardware-pcb.md).
        """
        lines = self.board_id_lines()
        size = SILK_MIN_TEXT
        if getattr(self, 'board_id_spot', None) is not None:
            center_x, center_y, rect = self.board_id_spot
            for offset, line in zip((-0.6, 0.6), lines):
                self.add_text(
                    line, center_x, center_y + offset * size * 1.2, size,
                    layer=pcbnew.B_SilkS, mirrored=True,
                )
            print('board ID at', (center_x, center_y), lines)
            return
        half_w = max(len(line) for line in lines) * size * 0.45 + 0.4
        half_h = size * 1.4
        best = None
        for step_y in range(3, int(BOARD_HEIGHT) - 3):
            for step_x in range(3, int(BOARD_WIDTH) - 3):
                rect = Rect(
                    step_x - half_w, step_y - half_h,
                    step_x + half_w, step_y + half_h,
                )
                if not self.silk_free(rect, 'bottom'):
                    continue
                distance = (step_x - BOARD_ID_SPOT[0]) ** 2 + (
                    step_y - BOARD_ID_SPOT[1]
                ) ** 2
                if best is None or distance < best[0]:
                    best = (distance, step_x, step_y, rect)
        if best is None:
            print('board ID: no free spot on the back')
            return
        _, center_x, center_y, rect = best
        for offset, line in zip((-0.6, 0.6), lines):
            self.add_text(
                line, center_x, center_y + offset * size * 1.2, size,
                layer=pcbnew.B_SilkS, mirrored=True,
            )
        self.occupancy.add('silk_board_id', rect, 'bottom')
        print('board ID at', (center_x, center_y), lines)

    def footprint_texts(self):
        """Boxes of the visible reference / value texts, so labels keep clear
        of them (cached after the first call).
        """
        if getattr(self, '_text_boxes', None) is None:
            boxes = []
            for footprint in self.board.GetFootprints():
                for item in (footprint.Reference(), footprint.Value()):
                    if not item.IsVisible():
                        continue
                    box = item.GetBoundingBox()
                    boxes.append(
                        Rect(
                            box.GetLeft() / 1e6,
                            box.GetTop() / 1e6,
                            box.GetRight() / 1e6,
                            box.GetBottom() / 1e6,
                        )
                    )
            self._text_boxes = boxes
        return self._text_boxes

    def add_text(
        self,
        text,
        x,
        y,
        size,
        layer=None,
        mirrored=False,
        thickness=None,
        justify='center',
    ):
        item = pcbnew.PCB_TEXT(self.board)
        item.SetText(text)
        item.SetLayer(layer if layer is not None else pcbnew.F_SilkS)
        item.SetPosition(pcbnew.VECTOR2I(to_internal(x), to_internal(y)))
        item.SetTextSize(silk_text_size(size))
        item.SetTextThickness(
            to_internal(max(SILK_MIN_LINE, thickness or size * 0.15))
        )
        item.SetHorizJustify(
            {
                'center': pcbnew.GR_TEXT_H_ALIGN_CENTER,
                'left': pcbnew.GR_TEXT_H_ALIGN_LEFT,
                'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT,
            }[justify]
        )
        item.SetMirrored(mirrored)
        self.board.Add(item)
        return item

    def text_rect(self, text, center_x, center_y, size):
        half_width = len(text) * size * 0.45 + 0.2
        half_height = size * 0.6
        return Rect(
            center_x - half_width,
            center_y - half_height,
            center_x + half_width,
            center_y + half_height,
        )

    def add_part_labels(self):
        """Little labels next to the buttons and LEDs: the best free spot
        within 3.5 mm of the part, preferring one inside its module box and
        close to the part.
        """
        obstacles_by_side = {s: self.silk_obstacles(s) for s in ('top', 'bottom')}
        courtyards_by_side = {
            s: self.keep_out_courtyards(s) for s in ('top', 'bottom')
        }
        inner = self.occupancy.board_rect.inflated(EDGE_MARGIN - 0.45)
        texts_by_side = {
            s: [
                self.text_box(self.display_text(footprint, ref))
                for ref, footprint in self.footprints.items()
                if self.display_text(footprint, ref).IsVisible()
                and self.side.get(ref, 'top') == s
            ]
            for s in ('top', 'bottom')
        }
        for ref, text in SILK_LABELS.items():
            if ref not in self.centers or ref not in self.occupancy.rects:
                continue
            side = self.side.get(ref, 'top')
            obstacles = obstacles_by_side[side]
            courtyards = courtyards_by_side[side]
            texts = texts_by_side[side]
            if ref in self.label_pockets:
                spot_x, spot_y, turned = self.label_pockets[ref]
                item = self.add_text(
                    text,
                    spot_x,
                    spot_y,
                    SILK_TEXT_SIZE,
                    thickness=SILK_TEXT_THICKNESS,
                )
                if turned:
                    item.SetTextAngleDegrees(90)
                continue
            part = self.body_rect(ref)
            center_x = (part.min_x + part.max_x) / 2
            center_y = (part.min_y + part.max_y) / 2
            module = self.module_of_ref(ref)
            base = self.text_rect(text, 0, 0, SILK_TEXT_SIZE)
            best = None
            for gap in (0.3, 0.7, 1.2, 1.8, 2.5, 3.5, 5.0):
                for turned in (False, True):
                    half_w, half_h = (
                        (base.max_y, base.max_x)
                        if turned
                        else (base.max_x, base.max_y)
                    )
                    for center in (
                        (part.max_x + gap + half_w, center_y),
                        (part.min_x - gap - half_w, center_y),
                        (center_x, part.min_y - gap - half_h),
                        (center_x, part.max_y + gap + half_h),
                        (part.max_x + gap + half_w, part.min_y - gap - half_h),
                        (part.min_x - gap - half_w, part.min_y - gap - half_h),
                        (part.max_x + gap + half_w, part.max_y + gap + half_h),
                        (part.min_x - gap - half_w, part.max_y + gap + half_h),
                    ):
                        rect = Rect(
                            center[0] - half_w,
                            center[1] - half_h,
                            center[0] + half_w,
                            center[1] + half_h,
                        )
                        if (
                            not rect.inside(inner)
                            or any(rect.overlaps(t) for t in texts)
                            or any(
                                rect.overlaps(c)
                                for owner, c in courtyards.items()
                                if owner != ref
                            )
                            or any(rect.overlaps(o) for o in obstacles)
                            or any(
                                rect.overlaps(k)
                                for k in self.occupancy.keepouts
                            )
                        ):
                            continue
                        level = (
                            pcbfloorplan.text_level(module, rect)
                            if module is not None
                            else 0
                        )
                        score = (
                            2 if level == 2 else 0,
                            level,
                            pcbfloorplan.rect_gap(rect, part),
                        )
                        if best is None or score < best[0]:
                            best = (score, center, rect, turned)
                if best is not None and best[0][0] == 0:
                    break
            if best is None:
                print('silk label not placed:', ref, text)
                continue
            if best[0][0] > 0:
                print('silk label sits outside its box:', ref, text)
            _, center, rect, turned = best
            if best[0][1] == 1:
                self.bumps.setdefault(module, []).append(rect)
            item = self.add_text(
                text, *center, SILK_TEXT_SIZE,
                layer=silk_layer(side), mirrored=side == 'bottom',
                thickness=SILK_TEXT_THICKNESS,
            )
            if turned:
                item.SetTextAngleDegrees(90)
            self.occupancy.add(f'silk_{ref}', rect, side)
            obstacles.append(rect)

    def add_logo(self):
        """Black-and-white trace of the cryocooler on the back silkscreen
        (mirrored so it reads correctly from the back) with the unit name
        below it.
        """
        geometry = json.loads(LOGO_FILE.read_text())
        features = geometry['features'] if 'features' in geometry else [geometry]
        source_w, source_h = LOGO_SOURCE_SIZE
        scale = LOGO_WIDTH / source_w
        center_x, center_y = LOGO_CENTER

        def to_board(point):
            # potrace's GeoJSON is y-up; the board is y-down. The back layer is
            # mirrored, so x runs the other way.
            x = center_x - (point[0] - source_w / 2) * scale
            y = center_y - (point[1] - source_h / 2) * scale
            return pcbnew.VECTOR2I(to_internal(x), to_internal(y))

        for feature in features:
            shape_geometry = feature['geometry']
            polygons = (
                shape_geometry['coordinates']
                if shape_geometry['type'] == 'MultiPolygon'
                else [shape_geometry['coordinates']]
            )
            for rings in polygons:
                polygon = pcbnew.SHAPE_POLY_SET()
                outline = polygon.NewOutline()
                for point in rings[0][:-1]:
                    polygon.Append(to_board(point), outline)
                for ring in rings[1:]:
                    hole = polygon.NewHole(outline)
                    for point in ring[:-1]:
                        polygon.Append(to_board(point), outline, hole)
                shape = pcbnew.PCB_SHAPE(self.board)
                shape.SetShape(pcbnew.SHAPE_T_POLY)
                shape.SetLayer(pcbnew.B_SilkS)
                shape.SetFilled(True)
                shape.SetWidth(0)
                shape.SetPolyShape(polygon)
                self.board.Add(shape)
        logo_height = LOGO_WIDTH * source_h / source_w
        title_y = center_y + logo_height / 2 + 4.0
        self.add_text(
            TITLE_TEXT, center_x, title_y, 2.0, pcbnew.B_SilkS, mirrored=True,
            thickness=0.3,
        )
        self.add_text(
            ALPHA_TEXT + ' DEV UNIT', center_x, title_y + 4.0, 2.0,
            pcbnew.B_SilkS, mirrored=True, thickness=0.3,
        )

    def add_alpha_mark(self):
        """Large ALPHA on the front silkscreen, in the free spot nearest the
        board centre.
        """
        size = 3.0
        half_w, half_h = len(ALPHA_TEXT) * size * 0.5 + 0.5, size * 0.7
        best = None
        for step_y in range(2, int(BOARD_HEIGHT) - 2):
            for step_x in range(2, int(BOARD_WIDTH) - 2):
                rect = Rect(
                    step_x - half_w, step_y - half_h,
                    step_x + half_w, step_y + half_h,
                )
                if not self.silk_free(rect):
                    continue
                distance = (step_x - 65.0) ** 2 + (step_y - 50.0) ** 2
                if best is None or distance < best[0]:
                    best = (distance, step_x, step_y, rect)
        if best is None:
            print('ALPHA mark: no free spot on the front')
            return
        _, mark_x, mark_y, rect = best
        self.add_text(ALPHA_TEXT, mark_x, mark_y, size, thickness=0.45)
        self.occupancy.add('silk_alpha', rect)

    def check_floorplan(self):
        """Returns messages for parts outside their module's box and for
        boxes closer together than the minimum gap.
        """
        problems = pcbfloorplan.check_regions(self.occupancy.board_rect.inflated(EDGE_MARGIN))
        for ref, module in self.module.items():
            if module is None:
                continue
            center_x, center_y, angle = self.centers[ref]
            rect = placed_rect(
                self.local_rects[ref], center_x, center_y, angle,
                self.side.get(ref) == 'bottom',
            )
            if not pcbfloorplan.region_contains(module, rect):
                problems.append(
                    f'{ref} is outside the {module} box '
                    f'({rect.min_x:.1f},{rect.min_y:.1f})-'
                    f'({rect.max_x:.1f},{rect.max_y:.1f})'
                )
        return problems

    def module_label_spot(self, module, board_rect, holes):
        """First (text, left_x, line_y) on a drawn border that clears every
        part, hole and earlier label, or None.
        """
        plain = pcbfloorplan.outline_segments(module, board_rect, holes)
        gap = pcbfloorplan.LABEL_GAP
        for text in pcbfloorplan.label_texts(module):
            width = pcbfloorplan.label_width(text)
            for left_x, line_y in pcbfloorplan.label_candidates(
                module, text, board_rect
            ):
                if not pcbfloorplan.covered(
                    plain, line_y, left_x - gap, left_x + width + gap
                ):
                    continue
                if pcbfloorplan.text_hits_hole(left_x, line_y, width, holes):
                    continue
                box = Rect(left_x, line_y - 0.5, left_x + width, line_y + 0.5)
                # labels sharing a wall keep 1.5 mm apart so they read apart
                spaced = Rect(box.min_x - 1.5, box.min_y, box.max_x + 1.5, box.max_y)
                if any(
                    (spaced if name.startswith('silk_label_') else box).overlaps(other)
                    for name, other in self.occupancy.on_side(
                        pcbfloorplan.split_key(module)[1]
                    )
                    if not name.startswith('silk_box') and name != f'silk_label_{module}'
                ):
                    continue
                return text, left_x, line_y
        return None

    def set_silk_avoid(self):
        """Tells the box outliner where it may not draw: the antenna notch
        and every pad on each side, 0.2 mm around (JLCPCB silk-to-pad 0.15 mm
        plus the mask margin).
        """
        notch = ANTENNA_NOTCH.inflated(0.5)
        for side, copper in (('top', pcbnew.F_Cu), ('bottom', pcbnew.B_Cu)):
            avoid = [notch]
            for footprint in self.board.GetFootprints():
                for pad in footprint.Pads():
                    if not pad.IsOnLayer(copper):
                        continue
                    box = pad.GetBoundingBox()
                    avoid.append(
                        Rect(
                            box.GetLeft() / 1e6, box.GetTop() / 1e6,
                            box.GetRight() / 1e6, box.GetBottom() / 1e6,
                        ).inflated(SILK_PAD_CLEARANCE)
                    )
            pcbfloorplan.SILK_AVOID[side] = avoid

    def draw_module_lines(self, module, spot, board_rect, holes):
        """Draws the silk outline of one module (replacing any earlier one)
        and reserves the line areas.
        """
        for shape in self.box_lines.pop(module, []):
            self.board.Remove(shape)
            self._removed_shapes.append(shape)
        for name in [
            n for n in self.occupancy.rects if n.startswith(f'silk_box_{module}_')
        ]:
            del self.occupancy.rects[name]
        shapes = []
        side = pcbfloorplan.split_key(module)[1]
        drawn = self.drawn_walls.setdefault(side, [])
        # a redraw (bulge) first forgets this module's own earlier walls
        for segment in self.module_walls.pop(module, []):
            if segment in drawn:
                drawn.remove(segment)
        own = self.module_walls.setdefault(module, [])
        for index, (start, end) in enumerate(
            pcbfloorplan.outline_segments(module, board_rect, holes, spot)
        ):
            # a wall shared with a neighbouring section is drawn once
            if any(covers(other, (start, end)) for other in drawn):
                continue
            drawn.append((start, end))
            own.append((start, end))
            line = pcbnew.PCB_SHAPE(self.board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(silk_layer(side))
            line.SetWidth(to_internal(pcbfloorplan.LINE_WIDTH))
            line.SetStart(
                pcbnew.VECTOR2I(to_internal(start[0]), to_internal(start[1]))
            )
            line.SetEnd(
                pcbnew.VECTOR2I(to_internal(end[0]), to_internal(end[1]))
            )
            self.board.Add(line)
            shapes.append(line)
            self.occupancy.add(
                f'silk_box_{module}_{index}',
                Rect(
                    min(start[0], end[0]) - 0.1,
                    min(start[1], end[1]) - 0.1,
                    max(start[0], end[0]) + 0.1,
                    max(start[1], end[1]) + 0.1,
                ),
                side,
            )
        self.box_lines[module] = shapes

    def add_module_boxes(self):
        """Draws each module's outline and label on the front silkscreen and
        reserves the line and label areas so other silk keeps clear.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 2.4) for hole_x, hole_y in HOLES]
        self.set_silk_avoid()
        self.drawn_walls = {}
        self.module_walls = {}
        self._removed_shapes = []
        self.box_labels = {}
        self.label_items = {}
        for module in pcbfloorplan.MODULE_REGIONS:
            spot = self.early_labels.get(module)
            if spot is None:
                spot = self.module_label_spot(module, board_rect, holes)
            if spot is None:
                print('no free border for the label of', module)
            self.box_labels[module] = spot
            self.draw_module_lines(module, spot, board_rect, holes)
            if spot is None:
                continue
            text, left_x, line_y = spot
            width = pcbfloorplan.label_width(text)
            side = pcbfloorplan.split_key(module)[1]
            # mirrored (bottom) text grows to the left of its anchor
            self.label_items[module] = self.add_text(
                text,
                left_x + width - 0.4 if side == 'bottom' else left_x,
                line_y,
                pcbfloorplan.LABEL_SIZE,
                layer=silk_layer(side),
                mirrored=side == 'bottom',
                thickness=SILK_TEXT_THICKNESS + 0.03,
                justify='left',
            )
            self.occupancy.add(
                f'silk_label_{module}',
                Rect(left_x, line_y - 0.5, left_x + width, line_y + 0.5),
                side,
            )

    def bulge_module_boxes(self):
        """Redraws the outline of every module whose labels did not fit
        inside it so the line goes around them.
        """
        board_rect = self.occupancy.board_rect.inflated(EDGE_MARGIN)
        holes = [(hole_x, hole_y, 2.4) for hole_x, hole_y in HOLES]
        for module, rects in self.bumps.items():
            pcbfloorplan.EXTRA_REGIONS[module] = [
                pcbfloorplan.bump_rect(rect) for rect in rects
            ]
            self.draw_module_lines(
                module, self.box_labels.get(module), board_rect, holes
            )
        print(
            'module outlines bulged around labels:',
            {m: len(r) for m, r in self.bumps.items()},
        )

    def cut_lines_at_labels(self, gap=0.3):
        """Breaks every section line where it crosses a section label on the
        same side; a wall drawn by the neighbouring section has no gap for it.
        Returns the number of lines cut.
        """
        cut = 0
        for module, label in self.label_items.items():
            side = pcbfloorplan.split_key(module)[1]
            box = self.text_box(label).inflated(gap)
            for owner, shapes in self.box_lines.items():
                if pcbfloorplan.split_key(owner)[1] != side:
                    continue
                for shape in list(shapes):
                    start, end = shape.GetStart(), shape.GetEnd()
                    x1, y1, x2, y2 = (start.x / 1e6, start.y / 1e6, end.x / 1e6, end.y / 1e6)
                    horizontal = abs(y1 - y2) < 1e-3
                    if horizontal and box.min_y <= y1 <= box.max_y:
                        low, high, pieces = min(x1, x2), max(x1, x2), []
                        if high <= box.min_x or low >= box.max_x:
                            continue
                        if low < box.min_x:
                            pieces.append(((low, y1), (box.min_x, y1)))
                        if high > box.max_x:
                            pieces.append(((box.max_x, y1), (high, y1)))
                    elif not horizontal and box.min_x <= x1 <= box.max_x:
                        low, high, pieces = min(y1, y2), max(y1, y2), []
                        if high <= box.min_y or low >= box.max_y:
                            continue
                        if low < box.min_y:
                            pieces.append(((x1, low), (x1, box.min_y)))
                        if high > box.max_y:
                            pieces.append(((x1, box.max_y), (x1, high)))
                    else:
                        continue
                    shapes.remove(shape)
                    self.board.Remove(shape)
                    self._removed_shapes.append(shape)
                    for piece_start, piece_end in pieces:
                        line = pcbnew.PCB_SHAPE(self.board)
                        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
                        line.SetLayer(shape.GetLayer())
                        line.SetWidth(shape.GetWidth())
                        line.SetStart(pcbnew.VECTOR2I(to_internal(piece_start[0]), to_internal(piece_start[1])))
                        line.SetEnd(pcbnew.VECTOR2I(to_internal(piece_end[0]), to_internal(piece_end[1])))
                        self.board.Add(line)
                        shapes.append(line)
                    cut += 1
        return cut

    def text_box(self, item):
        box = item.GetBoundingBox()
        return Rect(
            box.GetLeft() / 1e6,
            box.GetTop() / 1e6,
            box.GetRight() / 1e6,
            box.GetBottom() / 1e6,
        )

    def silk_obstacles(self, side='top'):
        """Boxes that reference text on `side` must not cover: every pad
        reaching that side, every footprint silk graphic there, the module box
        lines and labels, and the mounting holes (as squares).
        """
        copper = pcbnew.B_Cu if side == 'bottom' else pcbnew.F_Cu
        silk = silk_layer(side)
        boxes = []
        for footprint in self.footprints.values():
            for pad in footprint.Pads():
                if not pad.IsOnLayer(copper):
                    continue
                box = pad.GetBoundingBox()
                boxes.append(
                    Rect(
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                    ).inflated(SILK_PAD_CLEARANCE)
                )
            for graphic in footprint.GraphicalItems():
                if graphic.GetLayer() != silk:
                    continue
                box = graphic.GetBoundingBox()
                boxes.append(
                    Rect(
                        box.GetLeft() / 1e6,
                        box.GetTop() / 1e6,
                        box.GetRight() / 1e6,
                        box.GetBottom() / 1e6,
                    ).inflated(0.05)
                )
        for name, rect in self.occupancy.on_side(side):
            if name.startswith('silk_pin'):
                # keep other labels (and the connector's own reference) off
                # the pin label strip
                boxes.append(rect.inflated(0.25))
            elif name.startswith(('silk_', 'mark_', 'hole_')):
                boxes.append(rect)
        for hole_x, hole_y in HOLES:
            boxes.append(
                Rect(hole_x - 2.9, hole_y - 2.9, hole_x + 2.9, hole_y + 2.9)
            )
        return boxes

    def keep_out_courtyards(self, side='top'):
        """Courtyards of the big placed parts on `side`, by owner: another
        part's label inside one reads as that part's label (the ESP32 antenna
        area is exempt).
        """
        return {
            ref: rect
            for ref, rect in self.occupancy.on_side(side)
            if ref in PLACEMENT and ref != 'U1'
        }

    def module_of_ref(self, ref):
        """Module box a part belongs to (debug parts: the box they sit in)."""
        module = self.module.get(ref)
        if module is not None:
            return module
        center_x, center_y, _ = self.centers[ref]
        side = self.side.get(ref, 'top')
        for name, rects in pcbfloorplan.MODULE_REGIONS.items():
            if pcbfloorplan.split_key(name)[1] != side:
                continue
            if any(
                r.min_x <= center_x <= r.max_x and r.min_y <= center_y <= r.max_y
                for r in rects
            ):
                self.module[ref] = name
                return name
        return None

    def body_rect(self, ref):
        """Box around a part's pads: what a reader sees as "the part" (the
        courtyard is bigger and overlaps neighbours).
        """
        cache = self.__dict__.setdefault('_body_rects', {})
        if ref not in cache:
            boxes = [pad.GetBoundingBox() for pad in self.footprints[ref].Pads()]
            if not boxes:
                cache[ref] = self.occupancy.rects[ref]
            else:
                cache[ref] = Rect(
                    min(b.GetLeft() for b in boxes) / 1e6,
                    min(b.GetTop() for b in boxes) / 1e6,
                    max(b.GetRight() for b in boxes) / 1e6,
                    max(b.GetBottom() for b in boxes) / 1e6,
                )
        return cache[ref]

    def label_score(self, ref, rect, neighbours, module):
        """Ranks a label box for `ref` (lower is better): ambiguous (another
        part's pads as close or closer) or out of reach of its module box
        first, then needing an outline bulge, then distance to the part.
        """
        level = (
            pcbfloorplan.text_level(module, rect) if module is not None else 0
        )
        own = pcbfloorplan.rect_gap(rect, self.body_rect(ref))
        ambiguous = int(
            any(
                pcbfloorplan.rect_gap(rect, other) <= own
                for other in neighbours
            )
        )
        return (ambiguous + (2 if level == 2 else 0), level, own)

    def neighbour_rects(self, ref, reach=6.0):
        part = self.body_rect(ref).inflated(reach)
        side = self.side.get(ref, 'top')
        return [
            self.body_rect(name)
            for name in self.footprints
            if name != ref
            and self.side.get(name, 'top') == side
            and self.body_rect(name).overlaps(part)
        ]

    def place_reference_texts(self):
        """Places the reference texts of each board side in turn."""
        for side in ('top', 'bottom'):
            self.place_reference_texts_on(side)

    def place_reference_texts_on(self, side):
        """Keeps every reference designator beside its own part: inside the
        part's module box, nearer to that part than to any other, and off
        pads, other silk, the box lines and the board edge. Texts that fail
        move to the nearest spot that qualifies (rotating 90 degrees if that
        helps); a text with no free spot at all is hidden (allowed on this
        crowded board).
        """
        obstacles = self.silk_obstacles(side)
        courtyards = self.keep_out_courtyards(side)
        inner = self.occupancy.board_rect.inflated(EDGE_MARGIN - 0.45)
        finished = {}
        moved = 0
        stuck = []
        weak = []
        order = sorted(
            (r for r in self.footprints if self.side.get(r, 'top') == side),
            key=lambda r: (
                not self.is_passive(r),
                int(r.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ') or 0),
            ),
        )

        def clear(rect, near, own):
            if not rect.inside(inner):
                return False
            if any(rect.overlaps(other) for other in finished.values()):
                return False
            if any(
                rect.overlaps(courtyard)
                for owner, courtyard in courtyards.items()
                if owner != own
            ):
                return False
            return not any(
                rect.overlaps(obstacle)
                for obstacle in near
                if obstacle.min_x < rect.max_x + 0.1
                and obstacle.max_x > rect.min_x - 0.1
            )

        for ref in order:
            footprint = self.footprints[ref]
            item = self.display_text(footprint, ref)
            if not item.IsVisible() or ref not in self.occupancy.rects:
                continue
            module = self.module_of_ref(ref)
            if ref in self.pockets:
                spot_x, spot_y, turned = self.pockets[ref]
                item.SetTextAngleDegrees(90 if turned else 0)
                item.SetPosition(
                    pcbnew.VECTOR2I(to_internal(spot_x), to_internal(spot_y))
                )
                finished[ref] = self.text_box(item)
                moved += 1
                continue
            neighbours = self.neighbour_rects(ref)
            box = self.text_box(item)
            near = [
                obstacle
                for obstacle in obstacles
                if obstacle.min_y < box.max_y + 8.0
                and obstacle.max_y > box.min_y - 8.0
                and obstacle.min_x < box.max_x + 8.0
                and obstacle.max_x > box.min_x - 8.0
            ]
            part = self.occupancy.rects[ref]
            width = box.max_x - box.min_x
            height = box.max_y - box.min_y
            center_x = (part.min_x + part.max_x) / 2
            center_y = (part.min_y + part.max_y) / 2
            angle = item.GetTextAngleDegrees()
            best = None
            if clear(box, near, ref):
                best = (
                    self.label_score(ref, box, neighbours, module),
                    box.min_x + width / 2,
                    box.min_y + height / 2,
                    box,
                    False,
                )
            if best is None or best[0][0] > 0:
                for gap in (0.0, 0.2, 0.4, 0.7, 1.0, 1.4, 2.0, 2.8):
                    for turned in (False, True):
                        text_w, text_h = (
                            (height, width) if turned else (width, height)
                        )
                        spots = []
                        for shift in (0.0, 0.6, -0.6, 1.2, -1.2, 1.8, -1.8, 2.6, -2.6):
                            spots.append(
                                (center_x + shift, part.min_y - gap - text_h / 2)
                            )
                            spots.append(
                                (center_x + shift, part.max_y + gap + text_h / 2)
                            )
                            spots.append(
                                (part.min_x - gap - text_w / 2, center_y + shift)
                            )
                            spots.append(
                                (part.max_x + gap + text_w / 2, center_y + shift)
                            )
                        for spot_x, spot_y in spots:
                            rect = Rect(
                                spot_x - text_w / 2,
                                spot_y - text_h / 2,
                                spot_x + text_w / 2,
                                spot_y + text_h / 2,
                            )
                            if not clear(rect, near, ref):
                                continue
                            score = self.label_score(
                                ref, rect, neighbours, module
                            )
                            if best is None or score < best[0]:
                                best = (score, spot_x, spot_y, rect, turned)
                    if best is not None and best[0][0] == 0:
                        break
            if best is None:
                stuck.append(ref)
                item.SetVisible(False)
                continue
            if best[0][0] > 0:
                weak.append(ref)
            if best[0][1] == 1 and module is not None:
                self.bumps.setdefault(module, []).append(best[3])
            _, spot_x, spot_y, rect, turned = best
            if rect is box and not turned:
                finished[ref] = box
                continue
            if turned:
                item.SetTextAngleDegrees((angle + 90) % 180)
            item.SetPosition(
                pcbnew.VECTOR2I(to_internal(spot_x), to_internal(spot_y))
            )
            finished[ref] = rect
            moved += 1
        print(f'{side} reference texts moved:', moved, 'hidden (no free spot):', stuck)
        print(f'{side} reference texts ambiguous or outside their box:', weak)

    def adopt_board(self):
        """Takes footprints, courtyards and silk graphics from an already
        built (possibly routed) board so the silkscreen steps can run on it
        without placing or routing again.
        """
        self.footprints = {
            fp.GetReference(): fp
            for fp in self.board.GetFootprints()
            if fp.GetReference()
        }
        for ref, footprint in self.footprints.items():
            position = footprint.GetPosition()
            self.centers[ref] = (
                position.x / 1e6,
                position.y / 1e6,
                footprint.GetOrientationDegrees(),
            )
            override = LOCAL_RECT_OVERRIDES.get(
                self.parts.get(ref, {}).get('footprint')
            )
            if override is not None:
                x_pos, y_pos, angle = self.centers[ref]
                self.occupancy.add(
                    ref, placed_rect(override, x_pos, y_pos, angle)
                )
                continue
            box = footprint.GetCourtyard(pcbnew.F_CrtYd).BBox()
            if box.GetWidth() == 0:
                box = footprint.GetBoundingBox(False, False)
            self.occupancy.add(
                ref,
                Rect(
                    box.GetLeft() / 1e6,
                    box.GetTop() / 1e6,
                    box.GetRight() / 1e6,
                    box.GetBottom() / 1e6,
                ),
            )
        for index, (hole_x, hole_y) in enumerate(HOLES):
            self.occupancy.add(
                f'hole{index}',
                Rect(hole_x - 3.4, hole_y - 3.4, hole_x + 3.4, hole_y + 3.4),
            )

    @staticmethod
    def ic_label_variants(text):
        """The part number as one line, and as two lines split at the hyphen
        (or letter/digit boundary) nearest the middle."""
        variants = [text]
        cuts = [
            index
            for index in range(2, len(text) - 1)
            if text[index - 1] == '-'
            or text[index].isdigit() != text[index - 1].isdigit()
        ]
        if cuts:
            cut = min(cuts, key=lambda index: abs(index - len(text) / 2))
            variants.append(text[:cut] + '\n' + text[cut:])
        return variants

    @staticmethod
    def ic_label_text(footprint):
        """Text printed for an IC: its value, or the shorter override."""
        return IC_LABEL_TEXT.get(footprint.GetReference(), footprint.GetValue())

    def ic_label_obstacles(self, footprint):
        """Boxes an IC part number must stay off: the part's pads and silk
        graphics, plus every visible reference / value text on the board.
        """
        boxes = []
        for pad in footprint.Pads():
            box = pad.GetBoundingBox()
            boxes.append(
                Rect(
                    box.GetLeft() / 1e6 - 0.2,
                    box.GetTop() / 1e6 - 0.2,
                    box.GetRight() / 1e6 + 0.2,
                    box.GetBottom() / 1e6 + 0.2,
                )
            )
        for item in footprint.GraphicalItems():
            if item.GetLayer() != pcbnew.F_SilkS:
                continue
            box = item.GetBoundingBox()
            boxes.append(
                Rect(
                    box.GetLeft() / 1e6 - 0.15,
                    box.GetTop() / 1e6 - 0.15,
                    box.GetRight() / 1e6 + 0.15,
                    box.GetBottom() / 1e6 + 0.15,
                )
            )
        boxes.extend(self.footprint_texts())
        return boxes

    def ic_body_rect(self, footprint):
        """Package body from the footprint's fab outline (falls back to the
        pad box)."""
        boxes = [
            item.GetBoundingBox()
            for item in footprint.GraphicalItems()
            if item.GetLayer() == pcbnew.F_Fab
            and not isinstance(item, pcbnew.PCB_TEXT)
        ]
        if not boxes:
            boxes = [pad.GetBoundingBox() for pad in footprint.Pads()]
        return Rect(
            min(box.GetLeft() for box in boxes) / 1e6,
            min(box.GetTop() for box in boxes) / 1e6,
            max(box.GetRight() for box in boxes) / 1e6,
            max(box.GetBottom() for box in boxes) / 1e6,
        )

    def fit_ic_label(self, footprint):
        """Finds the largest part-number text that fits between the part's
        pads inside its body, nearest the body centre. Returns
        (text, size, angle, x, y) or None.
        """
        body = self.ic_body_rect(footprint)
        obstacles = self.ic_label_obstacles(footprint)
        center_x = (body.min_x + body.max_x) / 2
        center_y = (body.min_y + body.max_y) / 2
        for size in IC_LABEL_SIZES:
            for variant in self.ic_label_variants(
                IC_LABEL_TEXT.get(footprint.GetReference(), footprint.GetValue())
            ):
                for angle in (0, 90):
                    # measured on a text that is never added to the board
                    probe = pcbnew.PCB_TEXT(self.board)
                    probe.SetText(variant)
                    probe.SetLayer(pcbnew.F_SilkS)
                    probe.SetTextSize(silk_text_size(size))
                    probe.SetTextThickness(to_internal(SILK_TEXT_THICKNESS))
                    probe.SetTextAngleDegrees(angle)
                    extent = self.text_box(probe)
                    half_width = (extent.max_x - extent.min_x) / 2
                    half_height = (extent.max_y - extent.min_y) / 2
                    reach_x = (body.max_x - body.min_x) / 2 - half_width - 0.1
                    reach_y = (body.max_y - body.min_y) / 2 - half_height - 0.1
                    if reach_x < 0 or reach_y < 0:
                        continue
                    steps_x = int(reach_x / IC_LABEL_STEP)
                    steps_y = int(reach_y / IC_LABEL_STEP)
                    spots = sorted(
                        (
                            (step_x * IC_LABEL_STEP) ** 2
                            + (step_y * IC_LABEL_STEP) ** 2,
                            center_x + step_x * IC_LABEL_STEP,
                            center_y + step_y * IC_LABEL_STEP,
                        )
                        for step_x in range(-steps_x, steps_x + 1)
                        for step_y in range(-steps_y, steps_y + 1)
                    )
                    for _, spot_x, spot_y in spots:
                        rect = Rect(
                            spot_x - half_width,
                            spot_y - half_height,
                            spot_x + half_width,
                            spot_y + half_height,
                        )
                        if not any(rect.overlaps(other) for other in obstacles):
                            return variant, size, angle, spot_x, spot_y
        return None

    def add_ic_labels(self):
        """Prints each IC's part number on the silkscreen inside its body,
        between the pads, so the soldered part covers it. Returns
        (placed refs, skipped refs).
        """
        placed = []
        skipped = []
        for ref, footprint in sorted(self.footprints.items()):
            if not ref.startswith(('U', 'PS')) or ref in IC_LABEL_SKIP:
                continue
            fit = None
            if footprint.GetLayer() == pcbnew.F_Cu:
                fit = self.fit_ic_label(footprint)
            if fit is None:
                skipped.append(ref)
                continue
            variant, size, angle, spot_x, spot_y = fit
            item = self.add_text(
                variant, spot_x, spot_y, size, thickness=SILK_TEXT_THICKNESS
            )
            item.SetTextAngleDegrees(angle)
            placed.append(ref)
        return placed, skipped

    def remove_ic_labels(self):
        """Removes earlier IC part-number texts (silk text equal to a part's
        value, centred inside its body) so add_ic_labels can run again."""
        removed = 0
        for item in list(self.board.GetDrawings()):
            if (
                not isinstance(item, pcbnew.PCB_TEXT)
                or item.GetLayer() != pcbnew.F_SilkS
            ):
                continue
            position = item.GetPosition()
            for ref, footprint in self.footprints.items():
                if not ref.startswith(('U', 'PS')):
                    continue
                body = self.ic_body_rect(footprint)
                if (
                    item.GetText().replace('\n', '').replace('-', '')
                    == self.ic_label_text(footprint).replace('-', '')
                    and body.min_x <= position.x / 1e6 <= body.max_x
                    and body.min_y <= position.y / 1e6 <= body.max_y
                ):
                    self.board.Remove(item)
                    self._removed_ic_labels = getattr(
                        self, '_removed_ic_labels', []
                    ) + [item]
                    removed += 1
                    break
        return removed

    def free_mark_spot(self, rect, obstacles):
        """True if a pin-1 dot or pin name fits there: on the board, off the
        keep-outs, the visible footprint texts (test point net names) and
        every silk obstacle on its side.
        """
        if not rect.inside(self.occupancy.board_rect):
            return False
        if any(rect.overlaps(keepout) for keepout in self.occupancy.keepouts):
            return False
        if any(rect.overlaps(text.inflated(0.1)) for text in self.footprint_texts()):
            return False
        return not any(rect.overlaps(other) for other in obstacles)

    def add_esp32_pin_names(self):
        """Prints each ESP32 pin name beside its pad: just outside the module
        past the pad, else on the module outline inside it. Returns the names
        with room in neither spot.
        """
        footprint = self.footprints.get('U1')
        if footprint is None:
            return []
        side = self.side.get('U1', 'top')
        mirrored = side == 'bottom'
        names = self.parts['U1'].get('pins', {})
        center_x, _, _ = self.centers['U1']
        obstacles = self.silk_obstacles(side)
        left = 'left'
        right = 'right'
        skipped = []
        for pad in sorted(footprint.Pads(), key=lambda item: int(item.GetNumber())):
            number = pad.GetNumber()
            # the netlist suffixes repeated pin names with the pin number
            name = names.get(number, '').removesuffix(f'_{number}')
            if not name or name == 'GND':
                continue
            pad_x = pad.GetPosition().x / 1e6
            pad_y = pad.GetPosition().y / 1e6
            box = pad.GetBoundingBox()
            width = box.GetWidth() / 1e6
            height = box.GetHeight() / 1e6
            if width >= height:  # side column, reads across
                outward = -1 if pad_x < center_x else 1
                reach = width / 2 + SILK_PAD_CLEARANCE + 0.05
                spots = [
                    (pad_x + outward * reach, pad_y, left if outward > 0 else right, 0),
                    (pad_x - outward * reach, pad_y, right if outward > 0 else left, 0),
                ]
            else:  # bottom row, turned
                reach = height / 2 + SILK_PAD_CLEARANCE + 0.05
                spots = [
                    (pad_x, pad_y + reach, right, 90),
                    (pad_x, pad_y - reach, left, 90),
                ]
            for spot_x, spot_y, justify, angle in spots:
                item = self.add_text(
                    name, spot_x, spot_y, SILK_TEXT_SIZE,
                    layer=silk_layer(side), mirrored=mirrored,
                    thickness=SILK_TEXT_THICKNESS, justify=justify,
                )
                item.SetTextAngleDegrees(angle)
                rect = self.text_box(item).inflated(0.05)
                if self.free_mark_spot(rect, obstacles):
                    obstacles.append(rect)
                    self.occupancy.add(f'mark_esp32_{number}', rect, side)
                    break
                self.board.Remove(item)
            else:
                skipped.append(name)
        return skipped

    def add_pin1_marks(self):
        """A filled dot beside pin 1 of every IC, module and connector that
        lacks its own marker, in the first spot clear of pads and silk.
        Returns the parts with no room for one.
        """
        missing = []
        radius = PIN1_DOT_RADIUS
        for side in ('top', 'bottom'):
            obstacles = self.silk_obstacles(side)
            for ref, footprint in sorted(self.footprints.items()):
                if self.side.get(ref, 'top') != side or not ref.startswith(PIN1_PREFIXES):
                    continue
                first = [pad for pad in footprint.Pads() if pad.GetNumber() in ('1', 'A1')]
                if not first:
                    continue
                pad = first[0]
                pad_x = pad.GetPosition().x / 1e6
                pad_y = pad.GetPosition().y / 1e6
                if has_own_pin1_mark(footprint, pad_x, pad_y):
                    continue
                box = pad.GetBoundingBox()
                center_x, center_y, _ = self.centers[ref]
                reach_x = box.GetWidth() / 2e6 + radius + SILK_PAD_CLEARANCE
                reach_y = box.GetHeight() / 2e6 + radius + SILK_PAD_CLEARANCE
                away_x = 1 if pad_x >= center_x else -1
                away_y = 1 if pad_y >= center_y else -1
                for scale in (1.0, 1.5, 2.2):
                    spots = [
                        (pad_x + away_x * reach_x * scale, pad_y),
                        (pad_x, pad_y + away_y * reach_y * scale),
                        (pad_x + away_x * reach_x * scale, pad_y + away_y * reach_y * scale),
                        (pad_x - away_x * reach_x * scale, pad_y),
                        (pad_x, pad_y - away_y * reach_y * scale),
                    ]
                    spot = next(
                        (
                            (dot_x, dot_y)
                            for dot_x, dot_y in spots
                            if self.free_mark_spot(
                                Rect(dot_x - radius, dot_y - radius,
                                     dot_x + radius, dot_y + radius).inflated(0.1),
                                obstacles,
                            )
                        ),
                        None,
                    )
                    if spot is not None:
                        break
                if spot is None:
                    missing.append(ref)
                    continue
                dot_x, dot_y = spot
                shape = pcbnew.PCB_SHAPE(self.board)
                shape.SetShape(pcbnew.SHAPE_T_CIRCLE)
                shape.SetLayer(silk_layer(side))
                shape.SetFilled(True)
                shape.SetWidth(pcbnew.FromMM(SILK_MIN_LINE))
                shape.SetCenter(pcbnew.VECTOR2I(pcbnew.FromMM(dot_x), pcbnew.FromMM(dot_y)))
                shape.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(dot_x + radius), pcbnew.FromMM(dot_y)))
                self.board.Add(shape)
                rect = Rect(dot_x - radius, dot_y - radius, dot_x + radius, dot_y + radius)
                obstacles.append(rect.inflated(0.1))
                self.occupancy.add(f'mark_pin1_{ref}', rect, side)
        return missing

    def tested_part(self, ref):
        """The part a test point tests: the nearest of its owners
        (test_point_owners), else the nearest part on its net.
        """
        net = self.pad_net[ref].get('1')
        here_x, here_y, _ = self.centers[ref]
        owners = self.test_point_owners(ref, net) or [
            other
            for other, _ in self.net_pads.get(net, [])
            if other in self.centers and other != ref and not other.startswith('TP')
        ]
        if not owners:
            return None
        return min(
            owners,
            key=lambda other: (self.centers[other][0] - here_x) ** 2
            + (self.centers[other][1] - here_y) ** 2,
        )

    def test_point_problems(self):
        """Test points on the other side from the part they test, or more
        than TEST_POINT_CHECK_REACH mm from it (.claude/rules/hardware-pcb.md: same side, close by).
        Ground loops go through the board and are reachable from both sides.
        """
        problems = []
        for ref in sorted(self.centers):
            if not ref.startswith('TP'):
                continue
            if self.pad_net[ref].get('1') in GROUND_NETS:
                continue
            tested = self.tested_part(ref)
            if tested is None:
                continue
            if self.side.get(tested, 'top') != self.side.get(ref, 'top'):
                problems.append(f'{ref} is on the other side from {tested}')
                continue
            # measured pad to pad, as place_near reaches for the target pad
            net = self.pad_net[ref].get('1')
            here = self.pad_position(ref, '1')
            gap = min(
                math.dist(here, self.pad_position(tested, pad))
                for other, pad in self.net_pads[net]
                if other == tested
            )
            if gap > TEST_POINT_CHECK_REACH:
                problems.append(f'{ref} is {gap:.1f} mm from {tested}')
        return problems

    def add_silkscreen(self):
        self.add_module_boxes()
        if not self.pin_pockets:
            # silk-only runs on an existing board: find the spots now
            for ref in PIN_LABELS:
                self.reserve_pin_labels(ref)
        self.add_pin_labels()
        print('pin-1 marks with no room:', self.add_pin1_marks())
        print('ESP32 pin names left out (no room):', self.add_esp32_pin_names())
        self.place_reference_texts()
        self.add_part_labels()
        placed, skipped = self.add_ic_labels()
        print('IC part numbers placed:', placed, 'skipped:', skipped)
        self.bulge_module_boxes()
        print('section lines cut at labels:', self.cut_lines_at_labels())
        self.add_board_id()

    def build(self):
        self.load_footprints()
        self.place_anchors()
        self.reserve_board_id()
        self.reserve_module_labels()
        self.reserve_anchor_pockets()
        self.pre_route_current_path()
        self.pre_place_fine_pitch_ground_vias()
        self.pre_place_fine_pitch_ground_vias(SIGNAL_VIA_PADS)
        self.pre_place_pad_bridges()
        unplaced = self.place_passives()
        self.pre_place_fine_pitch_ground_vias(LATE_GROUND_PADS)
        self.add_outline_and_keepouts()
        self.add_net_classes()
        self.add_mounting_holes()
        self.add_planes()
        self.add_silkscreen()
        return unplaced


def patch_project_rules():
    """Writes the fine-pitch via limits into cryocooler.kicad_pro (pcbnew does
    not persist the annular-width minimum): 0.45 mm vias, 0.2 mm drills and a
    0.125 mm ring (JLCPCB's minimum is 0.1 mm), plus the JLCPCB hole, silk
    and mask limits.
    """
    path = KICAD_DIR / 'cryocooler.kicad_pro'
    project = json.loads(path.read_text())
    rules = project['board']['design_settings']['rules']
    defaults = project['board']['design_settings']['defaults']
    defaults['silk_line_width'] = SILK_MIN_LINE
    defaults['silk_text_thickness'] = SILK_MIN_LINE
    defaults['silk_text_size_h'] = SILK_MIN_TEXT * SILK_WIDTH_RATIO
    defaults['silk_text_size_v'] = SILK_MIN_TEXT
    rules['min_via_annular_width'] = 0.1
    rules['min_hole_clearance'] = 0.2
    rules['min_hole_to_hole'] = 0.2
    rules['min_silk_clearance'] = 0.15
    rules['min_text_height'] = SILK_DRC_MIN_TEXT
    rules['min_text_thickness'] = SILK_DRC_MIN_LINE
    rules['solder_mask_min_width'] = 0.099
    rules['min_via_diameter'] = VIA_IN_PAD_DIAMETER
    rules['min_through_hole_diameter'] = 0.2
    path.write_text(json.dumps(project, indent=2) + '\n')


def main():
    """Usage: gen_pcb.py [place|route|finish|texts|iclabels] [freerouting.jar] —
    `route` also autoroutes and fills zones; `texts` redoes all silkscreen
    and adds 3D envelope models on the existing board; `iclabels` only adds
    the IC part numbers under the IC bodies.
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else 'place'
    builder = PcbBuilder()
    if mode == 'finish':
        # re-open the routed board, tidy zones, add stitching vias
        builder.board = pcbnew.LoadBoard(
            str(KICAD_DIR / 'cryocooler.kicad_pcb')
        )
        builder.board.GetDesignSettings().m_ViasMinSize = to_internal(
            VIA_IN_PAD_DIAMETER
        )
        for zone in builder.board.Zones():
            if not zone.GetIsRuleArea() and zone.GetNetname() in GROUND_NETS:
                zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        print('stitching vias:', builder.stitch_ground())
        print(
            'island vias:',
            builder.connect_pour_islands(),
            builder.connect_pour_islands(0.2, 0.5),
        )
        print('escape vias:', builder.escape_ground_pads())
        builder.fill_zones()
        save_board(builder.board)
        patch_project_rules()
        return 0
    if mode == 'reroute':
        # one more Freerouting round on the saved board: existing copper
        # stays, only the missing connections are added
        builder.board = pcbnew.LoadBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'))
        work_dir = Path(tempfile.mkdtemp(prefix='cryo_reroute_'))
        builder.autoroute(work_dir, rounds=1)
        print('thin tracks widened:', builder.widen_thin_tracks())
        builder.fill_zones()
        save_board(builder.board)
        patch_project_rules()
        return 0
    if mode == 'link':
        # stamp the symbol links onto an existing (routed) board
        builder.board = pcbnew.LoadBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'))
        linked = 0
        for footprint in builder.board.GetFootprints():
            if not footprint.GetReference():
                footprint.SetBoardOnly(True)  # mounting holes
            part = builder.parts.get(footprint.GetReference())
            if part is not None:
                link_to_symbol(footprint, part)
                linked += 1
        save_board(builder.board)
        print('footprints linked to their symbols:', linked)
        return 0
    if mode == 'iclabels':
        # add only the IC part numbers on the existing board
        builder.board = pcbnew.LoadBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'))
        builder.adopt_board()
        print('old IC labels removed:', builder.remove_ic_labels())
        placed, skipped = builder.add_ic_labels()
        print('IC part numbers placed:', placed, 'skipped:', skipped)
        save_board(builder.board)
        return 0
    if mode == 'texts':
        # redo all silkscreen (module boxes, reference texts, part labels,
        # ALPHA, back logo) and the 3D envelope models on the routed board
        # without touching placement or tracks
        builder.board = pcbnew.LoadBoard(str(KICAD_DIR / 'cryocooler.kicad_pcb'))
        builder.adopt_board()
        # keep the removed items referenced: freeing them while the board is
        # still in use corrupts the footprint objects
        removed = []
        for drawing in list(builder.board.GetDrawings()):
            if drawing.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                builder.board.Remove(drawing)
                removed.append(drawing)
        added = [
            ref
            for ref, footprint in builder.footprints.items()
            if pcbmodels.attach_missing_models(footprint)
        ]
        print('3D envelope models added to:', added)
        coloured = [
            ref
            for ref, footprint in builder.footprints.items()
            if pcbmodels.apply_connector_colour(footprint)
        ]
        print('connector colours applied to:', coloured)
        builder.add_silkscreen()
        save_board(builder.board)
        return 0
    unplaced = builder.build()
    def own_hole(pair):
        first, second = pair
        owner = lambda name: name.split('_')[1] if name.startswith('hole_') else name
        return owner(first) == owner(second)

    overlaps = [
        pair
        for pair in builder.occupancy.overlaps_report()
        if not own_hole(pair)
        # pre-placed vias only steer the passives; DRC checks real clearances
        and not any(name.startswith('via_') for name in pair)
        if not any('_current_' in name for name in pair)
        and not any(name.startswith('silk_box') for name in pair)
        # pin-1 dots, pin names and a part's own label sit on its courtyard
        and not any(name.startswith('mark_') for name in pair)
        and not (pair[1] == f'silk_{pair[0]}' or pair[0] == f'silk_{pair[1]}')
        and not (
            any(name.startswith('txt_') for name in pair)
            and not all(name.startswith('txt_') for name in pair)
        )
    ]
    floorplan_problems = builder.check_floorplan() + builder.test_point_problems()
    out_path = KICAD_DIR / 'cryocooler.kicad_pcb'
    print('unplaced:', unplaced)
    print('overlapping pairs:', overlaps)
    print('floorplan problems:', floorplan_problems)
    if mode == 'route':
        work_dir = Path(tempfile.mkdtemp(prefix='cryo_route_'))
        builder.autoroute(work_dir)
        print('routing files in', work_dir)
        print('thin tracks widened:', builder.widen_thin_tracks())
        builder.add_inner_power_planes()
        builder.add_outer_pours()
    else:
        builder.add_inner_power_planes()
        builder.add_outer_pours()
    print('stitching vias:', builder.stitch_ground())
    print(
        'island vias:',
        builder.connect_pour_islands(),
        builder.connect_pour_islands(0.2, 0.5),
    )
    print('escape vias:', builder.escape_ground_pads())
    builder.fill_zones()
    save_board(builder.board, out_path)
    patch_project_rules()
    print(f'wrote {out_path}; {len(builder.footprints)} footprints')
    return 1 if unplaced or overlaps or floorplan_problems else 0


if __name__ == '__main__':
    # set iteration order follows the string hash seed: pin it so a placement
    # run repeats exactly
    if os.environ.get('PYTHONHASHSEED') != '0':
        os.execve(sys.executable, [sys.executable, *sys.argv], {**os.environ, 'PYTHONHASHSEED': '0'})
    exit_code = main()
    # Gerbers, zip and renders follow every board write
    export_fab.export_fabrication()
    sys.exit(exit_code)
